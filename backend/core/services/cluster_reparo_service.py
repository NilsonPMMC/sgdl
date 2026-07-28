"""Reparo operacional de Super OS — integração de seguidoras e tramitações scatter."""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from core.models import Demanda, Tramitacao, Usuario
from core.models_no_operacional import NoOperacional
from core.services.cluster_aderencia_service import (
    ClusterAderenciaService,
    demanda_integrada_ao_lider,
)
from core.services.cluster_service import CLUSTER_MIN_DEMANDAS, ClusterService

logger = logging.getLogger(__name__)


def _usuario_reparo(username: str | None) -> Usuario | None:
    if username:
        return Usuario.objects.filter(username=username, is_active=True).first()
    return (
        Usuario.objects.filter(perfil="PROTOCOLO", is_active=True).order_by("pk").first()
        or Usuario.objects.filter(is_superuser=True, is_active=True).order_by("pk").first()
    )


def _lider_operacional_reparo(cluster_id: int, demandas: list[dict]) -> int | None:
    """Demanda protocolada do cluster — independente do critério legado min(pk)."""
    com_protocolo = [
        d for d in demandas if (d.get("protocolo_executivo") or "").strip()
    ]
    if len(com_protocolo) == 1:
        return int(com_protocolo[0]["pk"])
    if len(com_protocolo) > 1:
        return int(
            max(
                com_protocolo,
                key=lambda d: (
                    int(d.get("nos_ativos") or 0),
                    int(d["pk"]),
                ),
            )["pk"]
        )
    return ClusterService().lider_cluster_pk(int(cluster_id))


def _tramitacoes_scatter_com_lacunas(demanda_id: int) -> int:
    """Conta OPERACAO_NO scatter sem unidade origem/destino reparável."""
    from core.services.tramitacao_setor_service import UnidadeAdministrativaService

    ua_svc = UnidadeAdministrativaService()
    total = 0
    for tram in Tramitacao.objects.filter(demanda_id=demanda_id, tipo="OPERACAO_NO"):
        meta = tram.metadata if isinstance(tram.metadata, dict) else {}
        if not meta.get("scatter_gather"):
            continue
        falta_destino = False
        if not tram.unidade_destino_id:
            no_id = meta.get("no_id")
            if no_id and NoOperacional.objects.filter(
                pk=int(no_id), unidade_administrativa_id__isnull=False
            ).exists():
                falta_destino = True
        falta_origem = False
        if not tram.unidade_origem_id and tram.responsavel_id:
            if ua_svc.ids_unidades_do_usuario(tram.responsavel):
                falta_origem = True
        if falta_destino or falta_origem:
            total += 1
    return total


def _tramitacoes_scatter_lacunas_cluster(cluster_id: int) -> int:
    ids = Demanda.objects.filter(cluster_id=cluster_id).values_list("pk", flat=True)
    return sum(_tramitacoes_scatter_com_lacunas(int(did)) for did in ids)


def diagnosticar_cluster(cluster_id: int) -> dict[str, Any]:
    """Identifica divergências entre líder legado (min pk) e líder operacional."""
    svc = ClusterService()
    if svc.cluster_e_multi_destino_orgaos(int(cluster_id)):
        return {
            "cluster_id": int(cluster_id),
            "tipo": "multi_destino",
            "reparavel": False,
            "motivo": "Cluster multi-órgão — reparo Super OS não aplicável.",
        }

    demandas = list(
        Demanda.objects.filter(cluster_id=cluster_id).order_by("pk").values(
            "pk",
            "protocolo_executivo",
            "status",
            "nos_ativos",
        )
    )
    if len(demandas) < CLUSTER_MIN_DEMANDAS:
        return {
            "cluster_id": int(cluster_id),
            "reparavel": False,
            "motivo": "Cluster com menos de duas demandas.",
        }

    lider_operacional = _lider_operacional_reparo(int(cluster_id), demandas)
    lider_legado = demandas[0]["pk"]
    lider = Demanda.objects.filter(pk=lider_operacional).first() if lider_operacional else None

    seguidoras_pendentes: list[int] = []
    for row in demandas:
        pk = int(row["pk"])
        if lider_operacional and pk == int(lider_operacional):
            continue
        if (row.get("protocolo_executivo") or "").strip():
            continue
        seg = Demanda.objects.get(pk=pk)
        if not demanda_integrada_ao_lider(seg):
            seguidoras_pendentes.append(pk)

    trams_sem_setor = _tramitacoes_scatter_lacunas_cluster(int(cluster_id))

    protocolo_fora_primeira = False
    min_pk_row = demandas[0]
    if not (min_pk_row.get("protocolo_executivo") or "").strip():
        for row in demandas[1:]:
            if (row.get("protocolo_executivo") or "").strip():
                protocolo_fora_primeira = True
                break

    nos_fora_lider_legado = any(
        int(d.get("nos_ativos") or 0) > 0 and int(d["pk"]) != int(lider_legado)
        for d in demandas
    )

    lider_divergente = lider_operacional and int(lider_legado) != int(lider_operacional)

    reparavel = bool(
        (lider and seguidoras_pendentes)
        or trams_sem_setor > 0
        or (lider_divergente and (protocolo_fora_primeira or nos_fora_lider_legado))
    )

    motivo = None
    if not reparavel:
        motivo = "Nada pendente — seguidoras integradas e tramitações OK."

    return {
        "cluster_id": int(cluster_id),
        "tipo": "super_os",
        "reparavel": reparavel,
        "lider_operacional_id": lider_operacional,
        "lider_legado_id": lider_legado,
        "lider_divergente": lider_divergente,
        "protocolo_fora_primeira": protocolo_fora_primeira,
        "nos_fora_lider_legado": nos_fora_lider_legado,
        "seguidoras_pendentes": seguidoras_pendentes,
        "tramitacoes_scatter_sem_unidade": trams_sem_setor,
        "protocolo_executivo": (lider.protocolo_executivo if lider else None),
        "motivo": motivo,
    }


def _contar_tramitacoes_scatter_sem_unidade(demanda_id: int) -> int:
    """Compatibilidade — delega para contagem de lacunas origem/destino."""
    return _tramitacoes_scatter_com_lacunas(int(demanda_id))


def corrigir_tramitacoes_scatter_unidade(demanda_id: int, *, dry_run: bool = False) -> int:
    """Preenche unidade_origem/destino em OPERACAO_NO scatter (nó + setor do operador)."""
    from core.services.tramitacao_setor_service import UnidadeAdministrativaService

    corrigidas = 0
    ua_svc = UnidadeAdministrativaService()
    for tram in Tramitacao.objects.filter(demanda_id=demanda_id, tipo="OPERACAO_NO"):
        meta = tram.metadata if isinstance(tram.metadata, dict) else {}
        if not meta.get("scatter_gather"):
            continue
        update_fields: list[str] = []
        if not tram.unidade_destino_id:
            no_id = meta.get("no_id")
            if no_id:
                no = NoOperacional.objects.filter(pk=int(no_id)).first()
                if no and no.unidade_administrativa_id:
                    tram.unidade_destino_id = no.unidade_administrativa_id
                    update_fields.append("unidade_destino_id")
        if not tram.unidade_origem_id and tram.responsavel_id:
            ids = ua_svc.ids_unidades_do_usuario(tram.responsavel)
            if ids:
                tram.unidade_origem_id = ids[0]
                update_fields.append("unidade_origem_id")
        if not update_fields:
            continue
        if dry_run:
            corrigidas += 1
            continue
        tram.save(update_fields=update_fields)
        corrigidas += 1
    return corrigidas


def clusters_super_os_com_protocolo() -> list[int]:
    """Clusters Super OS (≥2 demandas) com ao menos uma demanda protocolada."""
    svc = ClusterService()
    ids: list[int] = []
    for cid in Demanda.objects.filter(cluster_id__isnull=False).values_list(
        "cluster_id", flat=True
    ).distinct():
        if svc.cluster_e_multi_destino_orgaos(int(cid)):
            continue
        if Demanda.objects.filter(cluster_id=cid).count() < CLUSTER_MIN_DEMANDAS:
            continue
        if Demanda.objects.filter(cluster_id=cid).exclude(
            protocolo_executivo__isnull=True
        ).exclude(protocolo_executivo="").exists():
            ids.append(int(cid))
    return sorted(set(ids))


def clusters_candidatos_reparo() -> list[int]:
    """Clusters Super OS com ao menos uma demanda protocolada e divergência reparável."""
    svc = ClusterService()
    candidatos: list[int] = []
    for cid in Demanda.objects.filter(cluster_id__isnull=False).values_list(
        "cluster_id", flat=True
    ).distinct():
        if svc.cluster_e_multi_destino_orgaos(int(cid)):
            continue
        if Demanda.objects.filter(cluster_id=cid).count() < CLUSTER_MIN_DEMANDAS:
            continue
        if not Demanda.objects.filter(cluster_id=cid).exclude(
            protocolo_executivo__isnull=True
        ).exclude(protocolo_executivo="").exists():
            continue
        diag = diagnosticar_cluster(int(cid))
        if diag.get("reparavel"):
            candidatos.append(int(cid))
    return sorted(set(candidatos))


@transaction.atomic
def reparar_cluster_super_os(
    cluster_id: int,
    *,
    usuario: Usuario | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Integra seguidoras órfãs ao líder operacional e corrige tramitações scatter."""
    diag = diagnosticar_cluster(int(cluster_id))
    resultado: dict[str, Any] = {
        **diag,
        "dry_run": dry_run,
        "integradas": [],
        "tramitacoes_corrigidas": 0,
        "erro": None,
    }
    from core.services.scatter_gather_service import NoOperacionalService

    sg = NoOperacionalService()
    demanda_ids_cluster = list(
        Demanda.objects.filter(cluster_id=int(cluster_id)).values_list("pk", flat=True)
    )
    pernas_sync = sg.sincronizar_pernas_scatter_obsoletas(
        cluster_id=int(cluster_id),
        dry_run=dry_run,
    )
    resultado["pernas_sincronizadas"] = pernas_sync

    if not diag.get("reparavel"):
        resultado["motivo_skip"] = diag.get("motivo") or "Nada a reparar."
        for did in demanda_ids_cluster:
            if dry_run:
                continue
            demanda = Demanda.objects.filter(pk=int(did)).first()
            if demanda:
                sg.sincronizar_contador_nos(demanda)
        return resultado

    lider_id = diag.get("lider_operacional_id")
    if not lider_id:
        resultado["erro"] = "Líder operacional não identificado."
        return resultado

    lider = Demanda.objects.get(pk=int(lider_id))
    user = usuario or _usuario_reparo(None)
    if not user:
        resultado["erro"] = "Nenhum usuário Protocolo/superuser para registrar integração."
        return resultado

    if dry_run:
        resultado["tramitacoes_corrigidas"] = corrigir_tramitacoes_scatter_unidade(
            int(lider_id), dry_run=True
        )
        resultado["integradas"] = list(diag.get("seguidoras_pendentes") or [])
        return resultado

    aderencia = ClusterAderenciaService()
    integradas = aderencia.integrar_seguidoras_sem_protocolo_ao_operacional(
        lider, usuario=user
    )
    resultado["integradas"] = integradas
    resultado["tramitacoes_corrigidas"] = corrigir_tramitacoes_scatter_unidade(
        int(lider_id)
    )

    sg.sincronizar_contador_nos(lider)
    for did in demanda_ids_cluster:
        demanda = Demanda.objects.filter(pk=int(did)).first()
        if demanda:
            sg.sincronizar_contador_nos(demanda)
    if sg.processo_scatter_gather(lider):
        sg.reparar_tramitacoes_operacionais(lider, user)

    logger.info(
        "Reparo Super OS cluster=%s lider=%s integradas=%s trams=%s user=%s",
        cluster_id,
        lider_id,
        integradas,
        resultado["tramitacoes_corrigidas"],
        user.pk,
    )
    return resultado


def reparar_clusters_super_os(
    *,
    cluster_ids: list[int] | None = None,
    usuario: Usuario | None = None,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Repara um ou todos os clusters candidatos."""
    ids = cluster_ids if cluster_ids is not None else clusters_candidatos_reparo()
    return [
        reparar_cluster_super_os(int(cid), usuario=usuario, dry_run=dry_run)
        for cid in ids
    ]
