"""Conclusão final de Super OS — unificada ou individual por ofício vinculado."""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from core.models import Demanda, Tramitacao
from core.models_operacional import EventoOperacional
from core.services.cluster_service import ClusterService

logger = logging.getLogger(__name__)

MODO_CONCLUSAO_UNIFICADO = "unificado"
MODO_CONCLUSAO_INDIVIDUAL = "individual"


class ClusterConclusaoService:
    def concluir_super_os(
        self,
        lider: Demanda,
        *,
        usuario,
        parecer: str,
        historico: dict[str, Any] | None,
        tram_lider: Tramitacao | None,
        modo_conclusao: str = MODO_CONCLUSAO_UNIFICADO,
    ) -> dict[str, Any]:
        """Após conclusão na líder, propaga encerramento às seguidoras do cluster."""
        svc = ClusterService()
        if not svc.grupo_super_os_ativo(lider) or not lider.cluster_id:
            return {"modo": modo_conclusao, "seguidoras": []}

        modo = (modo_conclusao or MODO_CONCLUSAO_UNIFICADO).strip().lower()
        if modo not in (MODO_CONCLUSAO_UNIFICADO, MODO_CONCLUSAO_INDIVIDUAL):
            raise ValueError('modo_conclusao inválido. Use "unificado" ou "individual".')

        seguidoras: list[int] = []
        with transaction.atomic():
            if modo == MODO_CONCLUSAO_INDIVIDUAL:
                seguidoras = self._concluir_seguidoras_individual(
                    lider,
                    usuario=usuario,
                    parecer_template=parecer,
                    historico=historico,
                    tram_lider=tram_lider,
                )
            else:
                seguidoras = self._concluir_seguidoras_unificado(
                    lider, usuario=usuario, tram_lider=tram_lider
                )

        return {"modo": modo, "seguidoras": seguidoras}

    def _concluir_seguidoras_unificado(
        self,
        lider: Demanda,
        *,
        usuario,
        tram_lider: Tramitacao | None,
    ) -> list[int]:
        from django.utils import timezone

        from core.services.cluster_aderencia_service import ClusterAderenciaService

        aderencia = ClusterAderenciaService()
        atualizados = aderencia.sincronizar_seguidoras_integradas(lider, usuario=usuario)
        ClusterService().propagar_status_no_cluster(lider, usuario=usuario)
        lider.refresh_from_db()

        for sib in Demanda.objects.filter(cluster_id=lider.cluster_id).exclude(pk=lider.pk):
            if sib.status == "FINALIZADO":
                continue
            if tram_lider and not Tramitacao.objects.filter(
                demanda=sib,
                metadata__espelhada_do_lider=True,
                metadata__tramitacao_lider_id=int(tram_lider.pk),
            ).exists():
                aderencia.ressincronizar_com_lider(sib, lider=lider, usuario=usuario)
            if sib.status != "FINALIZADO":
                sib._propagando_cluster_status = True  # noqa: SLF001
                sib.status = "FINALIZADO"
                sib.data_finalizacao = lider.data_finalizacao or timezone.now()
                sib.save(update_fields=["status", "data_finalizacao"])
            if int(sib.pk) not in atualizados:
                atualizados.append(int(sib.pk))

        return atualizados

    def _concluir_seguidoras_individual(
        self,
        lider: Demanda,
        *,
        usuario,
        parecer_template: str,
        historico: dict[str, Any] | None,
        tram_lider: Tramitacao | None,
    ) -> list[int]:
        from core.services.devolutiva_protocolo_service import DevolutivaProtocoloService
        from core.services.texto_padrao_despacho_service import resolver_descricao_tramitacao
        from core.services.tramitacao_janela_edicao_service import TramitacaoJanelaEdicaoService

        if tram_lider:
            meta_lider = dict(tram_lider.metadata if isinstance(tram_lider.metadata, dict) else {})
            meta_lider["modo_conclusao"] = MODO_CONCLUSAO_INDIVIDUAL
            tram_lider.metadata = meta_lider
            tram_lider.save(update_fields=["metadata"])

        concluidas: list[int] = []
        for sib in (
            Demanda.objects.filter(cluster_id=lider.cluster_id)
            .select_related("autor")
            .exclude(pk=lider.pk)
        ):
            if sib.status == "FINALIZADO":
                continue
            Tramitacao.objects.filter(
                demanda=sib,
                tipo=EventoOperacional.CONCLUSAO_FINAL,
            ).delete()
            texto = resolver_descricao_tramitacao(sib, parecer_template)
            descricao = (
                f"Conclusão final da Super OS (ofício nº {sib.protocolo_legislativo}).\n"
                f"Parecer:\n{texto}"
            )
            meta = {
                "parecer": texto,
                "historico_tecnico": historico or {},
                "super_os_conclusao_individual": True,
                "modo_conclusao": MODO_CONCLUSAO_INDIVIDUAL,
                "lider_demanda_id": int(lider.pk),
            }
            if tram_lider:
                meta["tramitacao_lider_id"] = int(tram_lider.pk)

            tram = Tramitacao.objects.create(
                demanda=sib,
                responsavel=usuario,
                tipo=EventoOperacional.CONCLUSAO_FINAL,
                descricao=descricao,
                metadata=meta,
            )
            TramitacaoJanelaEdicaoService.abrir_janela(tram)
            DevolutivaProtocoloService().finalizar_apos_despacho_protocolo(sib, usuario)
            concluidas.append(int(sib.pk))
            logger.info(
                "Super OS conclusão individual seguidora pk=%s (líder pk=%s)",
                sib.pk,
                lider.pk,
            )
        return concluidas
