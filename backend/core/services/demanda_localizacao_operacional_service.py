"""Localização operacional aberta das demandas (nós/pernas/setores) para listagem e filtros."""

from __future__ import annotations

from typing import Any

from core.models import Demanda
from integrations import sinapse_catalog

_STATUS_OPERACIONAIS = ("PROTOCOLADO", "EM_EXECUCAO", "AGUARDANDO_TRANSFERENCIA")


def _serializar_setor(unidade) -> dict[str, Any]:
    if not unidade:
        return {"setor_id": None, "setor_sigla": "", "setor_nome": ""}
    return {
        "setor_id": int(unidade.pk),
        "setor_sigla": unidade.sigla or "",
        "setor_nome": unidade.nome or "",
    }


def _serializar_orgao(orgao_id: int | None) -> dict[str, Any]:
    if orgao_id in (None, ""):
        return {"orgao_id": None, "orgao_nome": ""}
    oid = int(orgao_id)
    return {
        "orgao_id": oid,
        "orgao_nome": sinapse_catalog.get_orgao_nome(oid) or str(oid),
    }


def _item_localizacao(
    *,
    tipo: str,
    orgao_id: int | None,
    unidade,
    aberto: bool = True,
    no_id: int | None = None,
    perna_id: int | None = None,
) -> dict[str, Any]:
    item = {
        "tipo": tipo,
        "aberto": bool(aberto),
        "no_id": no_id,
        "perna_id": perna_id,
    }
    item.update(_serializar_orgao(orgao_id))
    item.update(_serializar_setor(unidade))
    return item


def demanda_em_fluxo_direto_sem_scatter(demanda: Demanda) -> bool:
    """Demanda titular do órgão em fluxo direto, sem nós/pernas scatter ativos."""
    from core.models_no_operacional import NoOperacional, StatusNoOperacional
    from core.models_operacional import FluxoRoteamento
    from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional

    if demanda.status not in _STATUS_OPERACIONAIS:
        return False
    fluxo = demanda.fluxo_roteamento or ""
    nos = int(demanda.nos_ativos or 0)
    if fluxo == FluxoRoteamento.FLUXO_TRANSVERSAL or nos > 0:
        return False
    if PernaOperacional.objects.filter(
        demanda_id=demanda.pk,
        status__in=StatusPernaOperacional.ATIVOS,
    ).exists():
        return False
    if NoOperacional.objects.filter(
        demanda_id=demanda.pk,
        status=StatusNoOperacional.ABERTO,
    ).exists():
        return False
    return True


def demanda_ids_com_setores_operacionais_abertos(unidades_ids: list[int]) -> list[int]:
    """
    Demandas com execução aberta nos setores informados.

    Considera nós abertos, pernas ativas e fluxo direto titular na UA —
    não apenas ``Demanda.unidade_administrativa`` do despacho inicial.
    """
    from core.models_no_operacional import NoOperacional, StatusNoOperacional
    from core.models_operacional import FluxoRoteamento
    from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional

    uas = [int(u) for u in unidades_ids if u not in (None, "")]
    if not uas:
        return []

    ids: set[int] = set()
    ids.update(
        NoOperacional.objects.filter(
            unidade_administrativa_id__in=uas,
            status=StatusNoOperacional.ABERTO,
        ).values_list("demanda_id", flat=True)
    )
    ids.update(
        PernaOperacional.objects.filter(
            unidade_administrativa_id__in=uas,
            status__in=StatusPernaOperacional.ATIVOS,
        ).values_list("demanda_id", flat=True)
    )

    for row in Demanda.objects.filter(
        unidade_administrativa_id__in=uas,
        status__in=_STATUS_OPERACIONAIS,
    ).values("pk", "fluxo_roteamento", "nos_ativos"):
        pk = int(row["pk"])
        if pk in ids:
            continue
        fluxo = row.get("fluxo_roteamento") or ""
        nos = int(row.get("nos_ativos") or 0)
        if fluxo == FluxoRoteamento.FLUXO_TRANSVERSAL or nos > 0:
            continue
        if PernaOperacional.objects.filter(
            demanda_id=pk,
            status__in=StatusPernaOperacional.ATIVOS,
        ).exists():
            continue
        if NoOperacional.objects.filter(
            demanda_id=pk,
            status=StatusNoOperacional.ABERTO,
        ).exists():
            continue
        ids.add(pk)

    return list(ids)


def map_localizacao_operacional_aberta(demanda_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    """Mapa demanda_id → trilha operacional (nós/pernas abertos e concluídos)."""
    from core.models_no_operacional import NoOperacional, StatusNoOperacional
    from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional

    ids = [int(d) for d in demanda_ids if d]
    resultado: dict[int, list[dict[str, Any]]] = {did: [] for did in ids}
    if not ids:
        return resultado

    id_set = set(ids)

    for no in (
        NoOperacional.objects.filter(
            demanda_id__in=id_set,
            status__in=(StatusNoOperacional.ABERTO, StatusNoOperacional.CONCLUIDO),
        )
        .select_related("unidade_administrativa")
        .order_by("-status", "aberto_em", "pk")
    ):
        did = int(no.demanda_id)
        resultado[did].append(
            _item_localizacao(
                tipo="no",
                orgao_id=no.sinapse_orgao_id,
                unidade=no.unidade_administrativa,
                aberto=no.status == StatusNoOperacional.ABERTO,
                no_id=int(no.pk),
            )
        )

    for perna in (
        PernaOperacional.objects.filter(
            demanda_id__in=id_set,
            status__in=(
                *StatusPernaOperacional.ATIVOS,
                StatusPernaOperacional.CONCLUIDA,
            ),
        )
        .select_related("unidade_administrativa")
        .order_by("-status", "ordem", "pk")
    ):
        did = int(perna.demanda_id)
        resultado[did].append(
            _item_localizacao(
                tipo="perna",
                orgao_id=perna.sinapse_orgao_id,
                unidade=perna.unidade_administrativa,
                aberto=perna.status in StatusPernaOperacional.ATIVOS,
                perna_id=int(perna.pk),
            )
        )

    com_operacional = {did for did, itens in resultado.items() if itens}
    faltantes = id_set - com_operacional
    if faltantes:
        for demanda in Demanda.objects.filter(pk__in=faltantes).select_related(
            "unidade_administrativa"
        ):
            if not demanda_em_fluxo_direto_sem_scatter(demanda):
                continue
            resultado[int(demanda.pk)].append(
                _item_localizacao(
                    tipo="direto",
                    orgao_id=demanda.sinapse_orgao_id,
                    unidade=demanda.unidade_administrativa,
                    aberto=True,
                )
            )

    for did in resultado:
        resultado[did] = _agrupar_itens_localizacao(resultado[did])

    return resultado


def _agrupar_itens_localizacao(itens: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Uma entrada por setor; aberto prevalece sobre concluído no mesmo setor."""
    grupos: dict[str, dict[str, Any]] = {}
    for item in itens:
        chave = str(item.get("setor_id") or f"org:{item.get('orgao_id')}")
        prev = grupos.get(chave)
        if not prev:
            grupos[chave] = {**item, "quantidade": 1}
            continue
        prev["quantidade"] = int(prev.get("quantidade") or 1) + 1
        if item.get("aberto"):
            prev["aberto"] = True
    return sorted(
        grupos.values(),
        key=lambda row: (not row.get("aberto", False), row.get("setor_sigla") or row.get("orgao_nome") or ""),
    )
