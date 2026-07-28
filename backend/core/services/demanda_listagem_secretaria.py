"""Campos contextuais da listagem operacional para perfil Secretaria."""

from __future__ import annotations

from typing import Any

from core.models import Demanda, Tramitacao
from integrations import sinapse_catalog

_ACOES_ENCERRAMENTO = frozenset({"DESPACHAR_ENCERRAR", "ENCERRAR"})


def listagem_secretaria_encerrado(request) -> bool:
    if not request or getattr(getattr(request, "user", None), "perfil", None) != "SECRETARIA":
        return False
    escopo = (request.query_params.get("escopo_setor") or "").strip().lower()
    return escopo == "encerrado"


def _extrair_destino_encerramento(
    tram: Tramitacao, meta: dict[str, Any]
) -> dict[str, Any]:
    destinos = meta.get("destinos")
    destino = destinos[0] if isinstance(destinos, list) and destinos else {}

    org_id = destino.get("secretaria_id") or meta.get("destino_orgao_id")
    ua_id = (
        destino.get("unidade_administrativa_id")
        or meta.get("destino_setor_id")
        or tram.unidade_destino_id
    )

    secretaria_destino = None
    if org_id not in (None, ""):
        oid = int(org_id)
        secretaria_destino = sinapse_catalog.orgao_to_dict(sinapse_catalog.get_orgao(oid))
        if not secretaria_destino:
            nome = destino.get("orgao_nome") or meta.get("destino_orgao_nome")
            if nome:
                secretaria_destino = {"id": oid, "nome": nome}

    unidade_administrativa = None
    if ua_id not in (None, ""):
        uid = int(ua_id)
        from core.models_unidade_administrativa import UnidadeAdministrativa

        ua = UnidadeAdministrativa.objects.filter(pk=uid).first()
        if ua:
            unidade_administrativa = {
                "id": ua.pk,
                "nome": ua.nome,
                "sigla": ua.sigla,
                "sinapse_orgao_id": ua.sinapse_orgao_id,
            }
        else:
            setor_nome = destino.get("setor_nome")
            if setor_nome:
                unidade_administrativa = {
                    "id": uid,
                    "nome": setor_nome,
                    "sigla": setor_nome,
                    "sinapse_orgao_id": int(org_id) if org_id not in (None, "") else None,
                }

    return {
        "secretaria_destino": secretaria_destino,
        "unidade_administrativa": unidade_administrativa,
    }


def map_encaminhamento_pos_encerramento(
    orgao_id: int, demanda_ids: list[int]
) -> dict[int, dict[str, Any]]:
    """Último despacho de encerramento do órgão por demanda (scatter-gather)."""
    if not orgao_id or not demanda_ids:
        return {}

    oid = int(orgao_id)
    trams = Tramitacao.objects.filter(
        demanda_id__in=[int(d) for d in demanda_ids],
        tipo="OPERACAO_NO",
    ).order_by("-timestamp")

    melhor: dict[int, tuple[Any, dict[str, Any]]] = {}
    for tram in trams:
        did = int(tram.demanda_id)
        meta = tram.metadata if isinstance(tram.metadata, dict) else {}
        if not meta.get("scatter_gather"):
            continue
        if int(meta.get("orgao_id") or 0) != oid:
            continue
        acao = meta.get("acao_no") or meta.get("acao_encerramento")
        if acao not in _ACOES_ENCERRAMENTO:
            continue
        payload = _extrair_destino_encerramento(tram, meta)
        if did not in melhor or tram.timestamp >= melhor[did][0]:
            melhor[did] = (tram.timestamp, payload)

    return {did: payload for did, (_, payload) in melhor.items()}


def contexto_listagem_encerrado(user, demanda: Demanda) -> dict[str, Any] | None:
    orgao_id = getattr(user, "sinapse_orgao_id", None)
    if not orgao_id or not demanda.pk:
        return None
    return map_encaminhamento_pos_encerramento(int(orgao_id), [int(demanda.pk)]).get(
        int(demanda.pk)
    )
