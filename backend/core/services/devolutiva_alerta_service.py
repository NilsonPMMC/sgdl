"""Alertas de devolutiva final — leitura para órgãos/setores informados pelo Protocolo."""

from __future__ import annotations

import logging
from typing import Any

from core.models import Demanda, Notificacao, Tramitacao, Usuario

logger = logging.getLogger(__name__)


def demanda_ids_alerta_devolutiva(orgao_id: int) -> list[int]:
    """Demandas em que o órgão recebeu alerta de devolutiva final (somente leitura)."""
    ids: set[int] = set()
    for tram in Tramitacao.objects.filter(
        tipo__in=("DEVOLUTIVA_PROTOCOLO", "CONCLUSAO_FINAL"),
    ).only("demanda_id", "metadata"):
        meta = tram.metadata if isinstance(tram.metadata, dict) else {}
        for dest in meta.get("alerta_destinos") or []:
            if int(dest.get("secretaria_id") or 0) == int(orgao_id):
                ids.add(int(tram.demanda_id))
                break
    return list(ids)


def usuario_tem_alerta_devolutiva_leitura(user, demanda: Demanda) -> bool:
    """Secretaria informada na devolutiva final — acesso somente leitura."""
    if getattr(user, "perfil", None) != "SECRETARIA":
        return False
    orgao_id = getattr(user, "sinapse_orgao_id", None)
    if not orgao_id:
        return False
    if demanda.sinapse_orgao_id == orgao_id:
        return False
    from core.services.perna_operacional_service import PernaOperacionalService

    if demanda.pk in PernaOperacionalService().demanda_ids_visiveis_por_orgao(int(orgao_id)):
        return False
    return demanda.pk in demanda_ids_alerta_devolutiva(int(orgao_id))


def registrar_alertas_devolutiva(
    demanda: Demanda,
    tram: Tramitacao,
    destinos: list[dict[str, Any]],
    *,
    operador,
) -> None:
    if not destinos:
        return

    from core.services.demanda_despacho_destinos import parse_destinos_despacho

    try:
        parse_destinos_despacho({"destinos": destinos})
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    meta = tram.metadata if isinstance(tram.metadata, dict) else {}
    normalizados: list[dict[str, Any]] = []
    for item in destinos:
        sid = item.get("secretaria_id")
        if sid in (None, ""):
            continue
        entry: dict[str, Any] = {"secretaria_id": int(sid)}
        uid = item.get("unidade_administrativa_id")
        if uid not in (None, ""):
            entry["unidade_administrativa_id"] = int(uid)
        normalizados.append(entry)

    if not normalizados:
        return

    meta["alerta_destinos"] = normalizados
    meta["devolutiva_leitura"] = True
    tram.metadata = meta
    tram.save(update_fields=["metadata"])

    link = f"/demandas/detalhes/{demanda.pk}"
    protocolo = demanda.protocolo_executivo or demanda.protocolo_legislativo or str(demanda.pk)
    for dest in normalizados:
        orgao_id = int(dest["secretaria_id"])
        qs = Usuario.objects.filter(perfil="SECRETARIA", sinapse_orgao_id=orgao_id, is_active=True)
        uid = dest.get("unidade_administrativa_id")
        if uid:
            qs_setor = qs.filter(
                unidades_responsaveis__unidade_id=int(uid),
                unidades_responsaveis__ativo=True,
            ).distinct()
            if qs_setor.exists():
                qs = qs_setor
        for usuario in qs:
            Notificacao.objects.create(
                destinatario=usuario,
                tipo="DEVOLUTIVA",
                mensagem=(
                    f"Protocolo encaminhou devolutiva final do processo {protocolo} "
                    "para sua ciência (somente leitura)."
                ),
                link=link,
            )
    logger.info(
        "Alertas devolutiva demanda=%s destinos=%s operador=%s",
        demanda.pk,
        len(normalizados),
        operador.pk,
    )
