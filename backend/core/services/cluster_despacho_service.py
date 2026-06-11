"""Despacho em lote de uma Super Ordem de Serviço (cluster)."""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.models import ClusterExecucao, Demanda, Tramitacao
from integrations import sinapse_catalog

logger = logging.getLogger(__name__)


def _proximo_protocolo_executivo() -> str:
    ano = timezone.now().year
    ultimo = (
        Demanda.objects.filter(protocolo_executivo__startswith=f"{ano}-")
        .order_by("-protocolo_executivo")
        .first()
    )
    novo = 1
    if ultimo and ultimo.protocolo_executivo:
        try:
            novo = int(ultimo.protocolo_executivo.split("-")[-1]) + 1
        except (ValueError, IndexError):
            novo = (
                Demanda.objects.filter(protocolo_executivo__startswith=f"{ano}-").count()
                + 1
            )
    return f"{ano}-{novo:04d}"


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
    """Protocolo despacha todas as demandas pendentes de um cluster de uma vez."""

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

        protocolo_super = cluster.protocolo_super_os or _proximo_protocolo_super_os()
        agora = timezone.now()
        protocolados: list[int] = []

        with transaction.atomic():
            from core.services.carta_setor_service import CartaSetorService

            setor_svc = CartaSetorService()
            for demanda in pendentes:
                protocolo_exec = _proximo_protocolo_executivo()
                demanda.sinapse_orgao_id = secretaria_id
                demanda.protocolo_executivo = protocolo_exec
                demanda.status = "PROTOCOLADO"
                demanda.data_inicio_prazo = agora
                from core.services.prazo_demanda_service import PrazoDemandaService

                PrazoDemandaService().aplicar_snapshot_protocolo(demanda)
                unidade = setor_svc.resolver_unidade_demanda(demanda)
                if unidade:
                    demanda.unidade_administrativa = unidade
                update_fields = [
                    "sinapse_orgao_id",
                    "protocolo_executivo",
                    "status",
                    "data_inicio_prazo",
                    "prazo_efetivo_dias",
                    "prazo_origem",
                ]
                if unidade:
                    update_fields.append("unidade_administrativa")
                demanda.save(update_fields=update_fields)
                desc = (
                    f"Despacho Super OS {protocolo_super} — secretaria {orgao_nome}. "
                    f"Protocolo executivo: {protocolo_exec}."
                )
                if unidade:
                    rotulo = unidade.sigla or unidade.nome
                    desc += f"\nSetor operacional: {rotulo}."
                Tramitacao.objects.create(
                    demanda=demanda,
                    responsavel=usuario,
                    tipo="DESPACHO",
                    descricao=desc,
                    unidade_destino=unidade,
                )
                protocolados.append(int(demanda.pk))

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
            "Super OS %s despachada: cluster_id=%s demandas=%s",
            protocolo_super,
            cluster.pk,
            protocolados,
        )
        return {
            "cluster_id": cluster.pk,
            "protocolo_super_os": protocolo_super,
            "demandas_protocoladas": protocolados,
            "total": len(protocolados),
            "secretaria": orgao_nome,
        }
