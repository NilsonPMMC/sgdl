"""Despacho em lote de uma Super Ordem de Serviço (cluster)."""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.utils import timezone

from core.models import ClusterExecucao, Demanda
from integrations import sinapse_catalog

logger = logging.getLogger(__name__)


def _proximo_protocolo_super_os() -> str:
    ano = timezone.now().year
    prefixo = f"SUPER-{ano}-"
    ultimo = (
        ClusterExecucao.objects.filter(protocolo_super_os__startswith=prefixo)
        .order_by("-protocolo_super_os")
        .first()
    )
    novo = 1
    if ultimo and ultimo.protocolo_super_os:
        try:
            novo = int(ultimo.protocolo_super_os.split("-")[-1]) + 1
        except (ValueError, IndexError):
            novo = ClusterExecucao.objects.filter(
                protocolo_super_os__startswith=prefixo
            ).count() + 1
    return f"{prefixo}{novo:04d}"


class ClusterDespachoService:
    """Protocola apenas o líder da Super OS e integra seguidoras ao processo."""

    def despachar_super_os(
        self,
        cluster: ClusterExecucao,
        *,
        secretaria_id: int,
        usuario,
    ) -> dict[str, Any]:
        if not sinapse_catalog.orgao_existe(secretaria_id):
            raise ValueError("Órgão não encontrado no catálogo Sinapse.")

        orgao_nome = sinapse_catalog.get_orgao_nome(secretaria_id) or str(secretaria_id)
        pendentes = list(
            Demanda.objects.filter(
                cluster=cluster,
                status="AGUARDANDO_PROTOCOLO",
            ).select_related("autor")
        )
        if not pendentes:
            raise ValueError(
                "Não há demandas aguardando protocolo neste cluster."
            )

        from core.services.cluster_service import ClusterService

        lider_pk = ClusterService().lider_cluster_pk(cluster.pk)
        lider = next((d for d in pendentes if int(d.pk) == int(lider_pk)), None) if lider_pk else None
        if lider is None:
            lider = pendentes[0]

        protocolo_super = cluster.protocolo_super_os or _proximo_protocolo_super_os()
        agora = timezone.now()
        integradas: list[int] = []

        with transaction.atomic():
            from core.services.carta_setor_service import CartaSetorService
            from core.services.cluster_aderencia_service import ClusterAderenciaService
            from core.services.demanda_despacho_service import DemandaDespachoService

            unidade = CartaSetorService().resolver_unidade_demanda(lider)
            texto = (
                f"Despacho Super OS {protocolo_super} — secretaria {orgao_nome}."
            )
            if unidade:
                texto += f" Setor operacional: {unidade.sigla or unidade.nome}."

            despacho_svc = DemandaDespachoService()
            automatico = usuario is None
            despacho_svc.despachar(
                lider,
                secretaria_id=int(secretaria_id),
                usuario=usuario,
                automatico=automatico,
                unidade_administrativa_id=unidade.pk if unidade else None,
                texto_despacho=texto if not automatico else None,
            )
            lider._notificacao_super_os_lote = True  # noqa: SLF001

            integradas = ClusterAderenciaService().integrar_seguidoras_sem_protocolo_ao_operacional(
                lider, usuario=usuario
            )

            cluster.protocolo_super_os = protocolo_super
            cluster.despachado_em = agora
            cluster.despachado_por = usuario
            if cluster.status == "ABERTO":
                cluster.status = "EM_ANDAMENTO"
            cluster.secretaria_responsavel = orgao_nome[:150]
            cluster.save(
                update_fields=[
                    "protocolo_super_os",
                    "despachado_em",
                    "despachado_por",
                    "status",
                    "secretaria_responsavel",
                    "atualizado_em",
                ]
            )

        logger.info(
            "Super OS %s despachada: cluster_id=%s lider=%s integradas=%s",
            protocolo_super,
            cluster.pk,
            lider.pk,
            integradas,
        )
        from core.services.notificacao_service import NotificacaoService

        NotificacaoService().notificar_despacho_inicial_super_os(
            cluster,
            [lider],
            orgao_nome=orgao_nome,
        )
        return {
            "cluster_id": cluster.pk,
            "protocolo_super_os": protocolo_super,
            "demandas_protocoladas": [int(lider.pk)],
            "demandas_integradas": integradas,
            "total": 1 + len(integradas),
            "secretaria": orgao_nome,
        }
