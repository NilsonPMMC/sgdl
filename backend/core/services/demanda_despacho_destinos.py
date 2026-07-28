"""Normalização de destinos no despacho multi-secretaria (B5 + P2 multi-setor)."""

from __future__ import annotations

import json
from typing import Any

from core.models import Demanda
from core.models_unidade_administrativa import UnidadeAdministrativa
from integrations import sinapse_catalog

MAX_ORGAOS_DESPACHO = 5
MAX_PERNAS_DESPACHO = 30


def orgao_competente_servico(demanda: Demanda) -> int | None:
    """Órgão responsável na carta de serviços — não deve ser substituído por integrados."""
    if demanda.sinapse_servico_id:
        orgao_id = sinapse_catalog.get_orgao_id_for_servico(int(demanda.sinapse_servico_id))
        if orgao_id:
            return int(orgao_id)
    if demanda.sinapse_orgao_id:
        return int(demanda.sinapse_orgao_id)
    return None


def _destino_dict(
    item: dict[str, Any],
    secretaria_id: int,
    *,
    unidade_administrativa_ids: list[int] | None = None,
) -> dict[str, Any]:
    uids = unidade_administrativa_ids
    if uids is None:
        uids = []
        raw_list = item.get("unidade_administrativa_ids")
        if isinstance(raw_list, list):
            for uid in raw_list:
                if uid not in (None, ""):
                    uids.append(int(uid))
        uid = item.get("unidade_administrativa_id")
        if uid not in (None, ""):
            uid_int = int(uid)
            if uid_int not in uids:
                uids.append(uid_int)
    return {
        "secretaria_id": int(secretaria_id),
        "unidade_administrativa_id": uids[0] if uids else None,
        "unidade_administrativa_ids": uids,
    }


def expandir_pernas_destinos(destinos_agrupados: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expande órgão × N setores em lista plana de pernas operacionais."""
    pernas: list[dict[str, Any]] = []
    vistos: set[tuple[int, int | None]] = set()
    for item in destinos_agrupados:
        sid = int(item["secretaria_id"])
        uids = list(item.get("unidade_administrativa_ids") or [])
        if not uids and item.get("unidade_administrativa_id") not in (None, ""):
            uids = [int(item["unidade_administrativa_id"])]
        if not uids:
            chave = (sid, None)
            if chave not in vistos:
                vistos.add(chave)
                pernas.append({"secretaria_id": sid, "unidade_administrativa_id": None})
            continue
        for uid in uids:
            chave = (sid, int(uid))
            if chave in vistos:
                continue
            vistos.add(chave)
            pernas.append({"secretaria_id": sid, "unidade_administrativa_id": int(uid)})
    return pernas


def agrupar_pernas_por_orgao(pernas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Uma linha por órgão, preservando ordem de primeira aparição."""
    ordem: list[int] = []
    grupos: dict[int, dict[str, Any]] = {}
    for perna in pernas:
        sid = int(perna["secretaria_id"])
        if sid not in grupos:
            ordem.append(sid)
            grupos[sid] = {"secretaria_id": sid, "unidade_administrativa_ids": []}
        uids_list = perna.get("unidade_administrativa_ids")
        if isinstance(uids_list, list):
            for uid in uids_list:
                if uid not in (None, ""):
                    uid_int = int(uid)
                    if uid_int not in grupos[sid]["unidade_administrativa_ids"]:
                        grupos[sid]["unidade_administrativa_ids"].append(uid_int)
        uid = perna.get("unidade_administrativa_id")
        if uid not in (None, ""):
            uid_int = int(uid)
            if uid_int not in grupos[sid]["unidade_administrativa_ids"]:
                grupos[sid]["unidade_administrativa_ids"].append(uid_int)
    destinos: list[dict[str, Any]] = []
    for sid in ordem:
        g = grupos[sid]
        uids = g["unidade_administrativa_ids"]
        destinos.append(
            {
                "secretaria_id": sid,
                "unidade_administrativa_id": uids[0] if uids else None,
                "unidade_administrativa_ids": uids,
            }
        )
    return destinos


def pernas_para_resumo(pernas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "secretaria_id": int(p["secretaria_id"]),
            "unidade_administrativa_id": p.get("unidade_administrativa_id"),
        }
        for p in pernas
    ]


def normalizar_destinos_multi_orgao(
    demanda: Demanda, destinos: list[dict[str, Any]]
) -> dict[str, Any]:
    """
    Garante que o processo principal permaneça no órgão da carta.
    Demais secretarias selecionadas viram desdobramentos integrados (clones).
    ``destinos`` pode ser lista plana de pernas ou agrupada por órgão.
    """
    if not destinos:
        raise ValueError("Informe ao menos um destino de despacho.")

    pernas = expandir_pernas_destinos(agrupar_pernas_por_orgao(destinos))
    if not pernas:
        raise ValueError("Informe ao menos um destino de despacho.")
    if len(pernas) > MAX_PERNAS_DESPACHO:
        raise ValueError(
            f"Máximo de {MAX_PERNAS_DESPACHO} pernas (órgão × setor) por despacho."
        )

    destinos_agrupados = agrupar_pernas_por_orgao(pernas)
    if len(destinos_agrupados) > MAX_ORGAOS_DESPACHO:
        raise ValueError(
            f"Máximo de {MAX_ORGAOS_DESPACHO} órgãos no despacho "
            "(órgão competente + integrados)."
        )

    orgao_carta = orgao_competente_servico(demanda)
    if not orgao_carta:
        selecionados = [int(d["secretaria_id"]) for d in destinos_agrupados]
        return {
            "destinos": destinos_agrupados,
            "pernas": pernas,
            "total_pernas": len(pernas),
            "orgao_competente_id": selecionados[0],
            "orgaos_integrados_ids": selecionados[1:],
            "multi_orgao": len(destinos_agrupados) > 1,
        }

    por_orgao = {int(d["secretaria_id"]): d for d in destinos_agrupados}
    integrados_ordenados = [
        int(d["secretaria_id"])
        for d in destinos_agrupados
        if int(d["secretaria_id"]) != orgao_carta
    ]

    if not integrados_ordenados:
        principal = por_orgao.get(orgao_carta) or {"secretaria_id": orgao_carta}
        normalizados = [_destino_dict(principal, orgao_carta)]
        pernas_final = expandir_pernas_destinos(normalizados)
        return {
            "destinos": normalizados,
            "pernas": pernas_final,
            "total_pernas": len(pernas_final),
            "orgao_competente_id": orgao_carta,
            "orgaos_integrados_ids": [],
            "multi_orgao": False,
        }

    principal = por_orgao.get(orgao_carta) or {"secretaria_id": orgao_carta}
    normalizados = [_destino_dict(principal, orgao_carta)]
    for orgao_id in integrados_ordenados:
        normalizados.append(_destino_dict(por_orgao[orgao_id], orgao_id))

    pernas_final = expandir_pernas_destinos(normalizados)
    return {
        "destinos": normalizados,
        "pernas": pernas_final,
        "total_pernas": len(pernas_final),
        "orgao_competente_id": orgao_carta,
        "orgaos_integrados_ids": integrados_ordenados,
        "multi_orgao": True,
    }


def _orgaos_distintos_nos_operacionais(
    demanda: Demanda,
    *,
    excluir_orgao_id: int | None,
) -> list[int]:
    """Órgãos distintos nos nós scatter-gather (ordem de abertura), exceto líder."""
    if not demanda.pk:
        return []
    from core.models_no_operacional import NoOperacional, StatusNoOperacional

    vistos: set[int] = set()
    orgaos: list[int] = []
    for oid in (
        NoOperacional.objects.filter(demanda_id=demanda.pk)
        .exclude(status=StatusNoOperacional.CANCELADO)
        .order_by("pk")
        .values_list("sinapse_orgao_id", flat=True)
    ):
        oid_int = int(oid)
        if excluir_orgao_id is not None and oid_int == int(excluir_orgao_id):
            continue
        if oid_int in vistos:
            continue
        vistos.add(oid_int)
        orgaos.append(oid_int)
    return orgaos


def _enriquecer_orgaos_scatter_gather(
    demanda: Demanda,
    integrados: list[dict[str, Any]],
    *,
    lider_orgao: int | None,
) -> list[dict[str, Any]]:
    """Inclui órgãos que entraram só via scatter-gather (nós operacionais)."""
    orgaos_ja = {
        int(item["sinapse_orgao_id"])
        for item in integrados
        if item.get("sinapse_orgao_id") is not None
    }
    for oid in _orgaos_distintos_nos_operacionais(demanda, excluir_orgao_id=lider_orgao):
        if oid in orgaos_ja:
            continue
        integrados.append(
            {
                "demanda_id": demanda.pk,
                "sinapse_orgao_id": oid,
                "orgao_nome": sinapse_catalog.get_orgao_nome(oid),
                "origem": "scatter_gather",
            }
        )
        orgaos_ja.add(oid)
    return integrados


def orgaos_integrados_demanda(demanda: Demanda) -> list[dict[str, Any]]:
    """Pernas integradas, desdobramentos legados e órgãos scatter-gather (exceto líder)."""
    from core.services.perna_operacional_service import PernaOperacionalService

    lider_orgao = demanda.sinapse_orgao_lider_id or demanda.sinapse_orgao_id
    lider_orgao_int = int(lider_orgao) if lider_orgao is not None else None

    svc = PernaOperacionalService()
    if svc.demanda_usa_pernas(demanda):
        integrados = [
            p
            for p in svc.participantes_transversal(demanda)
            if p["sinapse_orgao_id"] != lider_orgao
        ]
        return _enriquecer_orgaos_scatter_gather(
            demanda, integrados, lider_orgao=lider_orgao_int
        )
    if not demanda.cluster_id or not demanda.pk:
        return _enriquecer_orgaos_scatter_gather(demanda, [], lider_orgao=lider_orgao_int)
    from core.services.cluster_service import ClusterService

    if not ClusterService().cluster_e_multi_destino_orgaos(int(demanda.cluster_id)):
        return _enriquecer_orgaos_scatter_gather(demanda, [], lider_orgao=lider_orgao_int)

    lider_pk = (
        Demanda.objects.filter(cluster_id=demanda.cluster_id)
        .order_by("pk")
        .values_list("pk", flat=True)
        .first()
    )
    if lider_pk is None:
        return _enriquecer_orgaos_scatter_gather(demanda, [], lider_orgao=lider_orgao_int)

    integrados: list[dict[str, Any]] = []
    for d in Demanda.objects.filter(cluster_id=demanda.cluster_id).exclude(pk=lider_pk).order_by("pk"):
        integrados.append(
            {
                "demanda_id": d.pk,
                "protocolo_executivo": d.protocolo_executivo,
                "protocolo_legislativo": d.protocolo_legislativo,
                "sinapse_orgao_id": d.sinapse_orgao_id,
                "orgao_nome": sinapse_catalog.get_orgao_nome(d.sinapse_orgao_id),
                "status": d.status,
                "status_display": d.get_status_display(),
            }
        )
    return _enriquecer_orgaos_scatter_gather(demanda, integrados, lider_orgao=lider_orgao_int)


def resolve_destinos_despacho(demanda: Demanda, data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse destinos do payload; retorna pernas expandidas (órgão × setor)."""
    try:
        return parse_destinos_despacho(data)
    except ValueError as exc:
        if "secretaria_id ou destinos" not in str(exc):
            raise
        orgao = orgao_competente_servico(demanda)
        if not orgao:
            raise ValueError(
                "Informe secretarias integradas ou vincule um serviço da carta ao processo."
            ) from exc
        pernas = [{"secretaria_id": orgao, "unidade_administrativa_id": None}]
        validar_setores_obrigatorios_pernas(pernas)
        return pernas


def _merge_item_por_orgao(
    por_orgao: dict[int, dict[str, Any]],
    item: dict[str, Any],
    *,
    vistos_sem_setor: set[int],
) -> None:
    try:
        sid = int(item.get("secretaria_id"))
    except (TypeError, ValueError):
        raise ValueError("secretaria_id obrigatório em cada destino.") from None

    uids_raw = item.get("unidade_administrativa_ids")
    uid_single = item.get("unidade_administrativa_id")
    tem_multi = isinstance(uids_raw, list) and len(uids_raw) > 0
    tem_single = uid_single not in (None, "")

    if not tem_multi and not tem_single:
        if sid in vistos_sem_setor:
            raise ValueError(
                "Não repita a mesma secretaria nos destinos sem informar setores distintos."
            )
        vistos_sem_setor.add(sid)

    if sid not in por_orgao:
        por_orgao[sid] = {"secretaria_id": sid, "unidade_administrativa_ids": []}

    if tem_multi:
        for uid in uids_raw:
            if uid in (None, ""):
                continue
            uid_int = int(uid)
            if uid_int not in por_orgao[sid]["unidade_administrativa_ids"]:
                por_orgao[sid]["unidade_administrativa_ids"].append(uid_int)
    elif tem_single:
        uid_int = int(uid_single)
        if uid_int not in por_orgao[sid]["unidade_administrativa_ids"]:
            por_orgao[sid]["unidade_administrativa_ids"].append(uid_int)


def validar_setores_obrigatorios_pernas(pernas: list[dict[str, Any]]) -> None:
    """
    Órgãos com setores (UAs) ativos no cadastro exigem unidade_administrativa_id em cada perna.
    """
    orgaos_sem_setor: list[int] = []
    orgaos_a_verificar: set[int] = set()
    for perna in pernas:
        sid = int(perna["secretaria_id"])
        uid = perna.get("unidade_administrativa_id")
        if uid in (None, ""):
            orgaos_a_verificar.add(sid)

    if not orgaos_a_verificar:
        return

    orgaos_com_setores = set(
        UnidadeAdministrativa.objects.filter(
            sinapse_orgao_id__in=orgaos_a_verificar,
            ativo=True,
        )
        .values_list("sinapse_orgao_id", flat=True)
        .distinct()
    )
    if not orgaos_com_setores:
        return

    for perna in pernas:
        sid = int(perna["secretaria_id"])
        if sid not in orgaos_com_setores:
            continue
        uid = perna.get("unidade_administrativa_id")
        if uid in (None, ""):
            if sid not in orgaos_sem_setor:
                orgaos_sem_setor.append(sid)
            continue
        ua = UnidadeAdministrativa.objects.filter(
            pk=int(uid),
            sinapse_orgao_id=sid,
            ativo=True,
        ).first()
        if ua is None:
            raise ValueError(
                f"Setor inválido ou inativo para o órgão #{sid}."
            )

    if orgaos_sem_setor:
        if len(orgaos_sem_setor) == 1:
            raise ValueError(
                f"Selecione ao menos um setor do órgão #{orgaos_sem_setor[0]}."
            )
        ids = ", ".join(f"#{sid}" for sid in orgaos_sem_setor)
        raise ValueError(
            "Selecione ao menos um setor para cada secretaria que possui setores cadastrados "
            f"(órgãos: {ids})."
        )


def parse_destinos_despacho(data: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Aceita:
    - ``destinos``: [{secretaria_id, unidade_administrativa_id? | unidade_administrativa_ids?}, ...]
    - pernas planas com mesma secretaria e setores distintos
    - legado: secretaria_id + unidade_administrativa_id

    Retorna lista **plana de pernas** (órgão × setor).
    """
    raw = data.get("destinos")
    if raw not in (None, "", []):
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError("Campo destinos inválido (JSON esperado).") from exc
        if not isinstance(raw, list):
            raise ValueError("destinos deve ser uma lista.")

        por_orgao: dict[int, dict[str, Any]] = {}
        vistos_sem_setor: set[int] = set()
        for item in raw:
            if not isinstance(item, dict):
                raise ValueError("Cada destino deve ser um objeto.")
            _merge_item_por_orgao(por_orgao, item, vistos_sem_setor=vistos_sem_setor)

        if not por_orgao:
            raise ValueError("Informe ao menos um destino de despacho.")
        if len(por_orgao) > MAX_ORGAOS_DESPACHO:
            raise ValueError(f"Máximo de {MAX_ORGAOS_DESPACHO} secretarias por despacho.")

        ordem = list(por_orgao.keys())
        agrupados = [_destino_dict(por_orgao[sid], sid) for sid in ordem]
        pernas = expandir_pernas_destinos(agrupados)
        if len(pernas) > MAX_PERNAS_DESPACHO:
            raise ValueError(
                f"Máximo de {MAX_PERNAS_DESPACHO} pernas (órgão × setor) por despacho."
            )
        validar_setores_obrigatorios_pernas(pernas)
        return pernas

    secretaria_id = data.get("secretaria_id")
    if not secretaria_id:
        raise ValueError("Informe secretaria_id ou destinos.")
    try:
        sid = int(secretaria_id)
    except (TypeError, ValueError):
        raise ValueError("ID de secretaria inválido.")
    uid = data.get("unidade_administrativa_id")
    uids = data.get("unidade_administrativa_ids")
    item: dict[str, Any] = {"secretaria_id": sid}
    if isinstance(uids, list) and uids:
        item["unidade_administrativa_ids"] = uids
    elif uid not in (None, ""):
        item["unidade_administrativa_id"] = int(uid)
    pernas = expandir_pernas_destinos([_destino_dict(item, sid)])
    validar_setores_obrigatorios_pernas(pernas)
    return pernas


def filtrar_pernas_abertura_transversal(
    demanda: Demanda,
    pernas: list[dict[str, Any]],
    *,
    orgao_abridor_id: int,
) -> list[dict[str, Any]]:
    """
    Pernas novas em órgãos distintos do gestor (subpastas).
    Não abre perna para o próprio órgão — use andamento interno.
    """
    from core.models_perna_operacional import StatusPernaOperacional
    from core.services.perna_operacional_service import PernaOperacionalService

    abridor = int(orgao_abridor_id)
    existentes = {
        (p.sinapse_orgao_id, p.unidade_administrativa_id)
        for p in PernaOperacionalService().listar_pernas(demanda)
        if p.status in StatusPernaOperacional.ATIVOS
    }
    novas: list[dict[str, Any]] = []
    for perna in pernas:
        orgao_id = int(perna["secretaria_id"])
        uid = perna.get("unidade_administrativa_id")
        uid_norm = int(uid) if uid not in (None, "") else None
        if orgao_id == abridor:
            continue
        if (orgao_id, uid_norm) in existentes:
            continue
        novas.append(perna)
    return novas
