"""Orquestração de fluxo automático vs manual por serviço da carta."""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from core.models import Demanda
from core.models_fluxo_protocolo import ServicoFluxoProtocolo
from core.services.cluster_despacho_service import ClusterDespachoService
from core.services.cluster_service import CLUSTER_MIN_DEMANDAS, ClusterService, embedding_presente
from core.services.demanda_despacho_service import DemandaDespachoService
from integrations import sinapse_catalog

logger = logging.getLogger(__name__)


class FluxoProtocoloService:
    def get_config(self, sinapse_servico_id: int | None) -> ServicoFluxoProtocolo | None:
        if not sinapse_servico_id:
            return None
        return ServicoFluxoProtocolo.objects.filter(
            sinapse_servico_id=int(sinapse_servico_id)
        ).first()

    def modo_efetivo(self, sinapse_servico_id: int | None) -> str:
        cfg = self.get_config(sinapse_servico_id)
        if cfg and cfg.despacho_automatico:
            return ServicoFluxoProtocolo.MODO_AUTOMATICO
        return ServicoFluxoProtocolo.MODO_MANUAL

    def despacho_automatico_habilitado(self, demanda: Demanda) -> bool:
        if demanda.origem_vinculo == Demanda.ORIGEM_VINCULO_TENDENCIA:
            return False
        if demanda.tendencia_id:
            return False
        if not demanda.sinapse_servico_id:
            return False
        cfg = self.get_config(int(demanda.sinapse_servico_id))
        return bool(cfg and cfg.despacho_automatico)

    def _tem_pares_aguardando_cluster(self, demanda: Demanda) -> bool:
        """Outras demandas do mesmo serviço ainda aguardando embedding/cluster."""
        return (
            Demanda.objects.filter(
                sinapse_servico_id=demanda.sinapse_servico_id,
                status="AGUARDANDO_PROTOCOLO",
                cluster__isnull=True,
            )
            .exclude(pk=demanda.pk)
            .exists()
        )

    def tentar_despacho_automatico_pk(self, demanda_pk: int) -> bool:
        try:
            demanda = Demanda.objects.select_related("cluster").get(pk=demanda_pk)
        except Demanda.DoesNotExist:
            return False

        if demanda.status != "AGUARDANDO_PROTOCOLO":
            return False
        if not self.despacho_automatico_habilitado(demanda):
            return False
        if not demanda.sinapse_servico_id:
            return False

        return self.processar_cohorte_servico(int(demanda.sinapse_servico_id)) > 0

    def processar_cohorte_servico(self, sinapse_servico_id: int) -> int:
        """Clusteriza e despacha em lote todas as demandas automáticas do serviço."""
        cfg = self.get_config(sinapse_servico_id)
        if not cfg or not cfg.despacho_automatico:
            return 0

        orgao_id = sinapse_catalog.get_orgao_id_for_servico(sinapse_servico_id)
        if not orgao_id:
            logger.warning(
                "Fluxo automático: serviço %s sem órgão; coorte permanece na fila.",
                sinapse_servico_id,
            )
            return 0

        aguardando = Demanda.objects.filter(
            sinapse_servico_id=sinapse_servico_id,
            status="AGUARDANDO_PROTOCOLO",
            tendencia__isnull=True,
        ).exclude(origem_vinculo=Demanda.ORIGEM_VINCULO_TENDENCIA)

        if aguardando.filter(embedding__isnull=True).exists():
            logger.info(
                "Fluxo automático adiado: serviço %s aguardando embedding de pares.",
                sinapse_servico_id,
            )
            return 0

        cluster_svc = ClusterService()
        com_embedding = list(aguardando.select_related("cluster").order_by("pk"))
        for demanda in com_embedding:
            cluster_svc.atribuir_demanda(demanda)

        cluster_svc.reconciliar_servico(int(sinapse_servico_id))

        fila = list(
            Demanda.objects.filter(
                sinapse_servico_id=sinapse_servico_id,
                status="AGUARDANDO_PROTOCOLO",
                tendencia__isnull=True,
            )
            .exclude(origem_vinculo=Demanda.ORIGEM_VINCULO_TENDENCIA)
            .select_related("cluster")
            .order_by("pk")
        )

        despachadas = 0
        clusters_processados: set[int] = set()

        for demanda in fila:
            if not demanda.cluster_id:
                continue
            cid = int(demanda.cluster_id)
            if cid in clusters_processados:
                continue
            membros = [
                d
                for d in fila
                if d.cluster_id == cid
            ]
            if len(membros) >= CLUSTER_MIN_DEMANDAS:
                if self._despachar_super_os_automatico(
                    demanda.cluster, secretaria_id=int(orgao_id)
                ):
                    despachadas += len(membros)
                clusters_processados.add(cid)

        solos = [d for d in fila if not d.cluster_id]
        for demanda in solos:
            if cluster_svc.deve_aguardar_par_para_demanda(demanda):
                logger.info(
                    "Fluxo automático adiado: demanda pk=%s aguardando par em formação (serviço %s).",
                    demanda.pk,
                    sinapse_servico_id,
                )
                continue
            if self._despachar_individual(demanda, secretaria_id=int(orgao_id)):
                despachadas += 1

        return despachadas

    def _despachar_individual(self, demanda: Demanda, *, secretaria_id: int) -> bool:
        try:
            DemandaDespachoService().despachar(
                demanda,
                secretaria_id=secretaria_id,
                usuario=None,
                automatico=True,
            )
        except ValueError as exc:
            logger.warning("Fluxo automático falhou demanda pk=%s: %s", demanda.pk, exc)
            return False
        return True

    def _despachar_super_os_automatico(
        self, cluster, *, secretaria_id: int
    ) -> bool:
        if cluster.protocolo_super_os:
            return True
        try:
            with transaction.atomic():
                ClusterDespachoService().despachar_super_os(
                    cluster,
                    secretaria_id=secretaria_id,
                    usuario=None,
                )
        except ValueError as exc:
            logger.warning(
                "Super OS automática falhou cluster pk=%s: %s", cluster.pk, exc
            )
            return False
        logger.info(
            "Super OS automática despachada cluster pk=%s em %s",
            cluster.pk,
            timezone.now().isoformat(),
        )
        return True

    def upsert_config(
        self,
        *,
        sinapse_servico_id: int,
        modo: str,
        ativo: bool = True,
        observacoes: str = "",
        usuario=None,
    ) -> ServicoFluxoProtocolo:
        if modo not in (
            ServicoFluxoProtocolo.MODO_MANUAL,
            ServicoFluxoProtocolo.MODO_AUTOMATICO,
        ):
            raise ValueError("modo inválido.")
        if not sinapse_catalog.get_servico(sinapse_servico_id):
            raise ValueError("Serviço não encontrado na carta Sinapse.")

        obj, _ = ServicoFluxoProtocolo.objects.update_or_create(
            sinapse_servico_id=int(sinapse_servico_id),
            defaults={
                "modo": modo,
                "ativo": ativo,
                "observacoes": (observacoes or "")[:2000],
                "atualizado_por": usuario,
            },
        )
        return obj

    def listar_carta_com_fluxo(
        self,
        *,
        q: str = "",
        orgao_id: int | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> dict:
        busca = sinapse_catalog.buscar_servicos_catalogo(
            q=q,
            orgao_id=orgao_id,
            limit=limit,
            offset=offset,
        )
        configs = {
            c.sinapse_servico_id: c
            for c in ServicoFluxoProtocolo.objects.all()
        }
        from core.services.carta_setor_service import CartaSetorService

        setor_svc = CartaSetorService()
        results = []
        for item in busca.get("results") or []:
            sid = item.get("id")
            if sid is None:
                continue
            sid_int = int(sid)
            cfg = configs.get(sid_int)
            orgao = item.get("secretaria_responsavel") or {}
            row = {
                "sinapse_servico_id": sid_int,
                "titulo": item.get("nome") or item.get("titulo") or "",
                "orgao_id": orgao.get("id"),
                "orgao_nome": orgao.get("nome"),
                "modo": cfg.modo if cfg else ServicoFluxoProtocolo.MODO_MANUAL,
                "ativo": cfg.ativo if cfg else True,
                "despacho_automatico": cfg.despacho_automatico if cfg else False,
                "config_id": cfg.pk if cfg else None,
                "observacoes": cfg.observacoes if cfg else "",
            }
            results.append(setor_svc.enriquecer_item_carta(row))
        return {
            "total": busca.get("total", len(results)),
            "offset": offset,
            "limit": limit,
            "catalogo_disponivel": busca.get("catalogo_disponivel", True),
            "results": results,
        }
