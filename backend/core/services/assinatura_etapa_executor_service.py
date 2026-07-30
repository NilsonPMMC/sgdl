"""Execução diferida de etapas operacionais — só após assinatura do gestor."""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from core.models import Demanda, Tramitacao
from core.models_assinatura_eletronica import AssinaturaEletronica, AssinaturaValidacaoGestor
from core.models_no_operacional import NoOperacional

logger = logging.getLogger(__name__)

ACAO_DESPACHO_INICIAL = "DESPACHO_INICIAL"
ACAO_CONCLUSAO_SECRETARIA = "CONCLUSAO_SECRETARIA"
ACAO_CONCLUSAO_SECRETARIA_FLUXO_DIRETO = "CONCLUSAO_SECRETARIA_FLUXO_DIRETO"
ACAO_CONCLUSAO_FINAL = "CONCLUSAO_FINAL"
ACAO_SCATTER_ENCERRAR = "SCATTER_ENCERRAR"
ACAO_SCATTER_DESPACHAR_ENCERRAR = "SCATTER_DESPACHAR_ENCERRAR"


class AssinaturaEtapaExecutorService:
    def executar_apos_validacao_gestor(
        self,
        validacao: AssinaturaValidacaoGestor,
        *,
        request=None,
    ) -> dict[str, Any]:
        if validacao.status != AssinaturaValidacaoGestor.STATUS_PENDENTE:
            raise ValueError("Validação não está pendente.")

        payload = validacao.payload if isinstance(validacao.payload, dict) else {}
        acao = payload.get("acao_executiva") or validacao.etapa

        handlers = {
            ACAO_DESPACHO_INICIAL: self._executar_despacho_inicial,
            AssinaturaEletronica.ETAPA_DESPACHO_INICIAL: self._executar_despacho_inicial,
            ACAO_CONCLUSAO_SECRETARIA: self._executar_conclusao_secretaria,
            AssinaturaEletronica.ETAPA_CONCLUSAO_SECRETARIA: self._executar_conclusao_secretaria,
            ACAO_CONCLUSAO_SECRETARIA_FLUXO_DIRETO: self._executar_conclusao_secretaria_fluxo_direto,
            ACAO_CONCLUSAO_FINAL: self._executar_conclusao_final,
            AssinaturaEletronica.ETAPA_CONCLUSAO_FINAL: self._executar_conclusao_final,
            ACAO_SCATTER_ENCERRAR: self._executar_scatter_encerrar,
            ACAO_SCATTER_DESPACHAR_ENCERRAR: self._executar_scatter_despachar_encerrar,
            AssinaturaEletronica.ETAPA_OPERACAO_SCATTER: self._executar_scatter_encerrar,
        }
        handler = handlers.get(acao)
        if not handler:
            raise ValueError(f"Ação executiva não suportada: {acao}")

        with transaction.atomic():
            resultado = handler(validacao, payload, request=request)
        return resultado

    def _demanda(self, validacao: AssinaturaValidacaoGestor) -> Demanda:
        return Demanda.objects.select_for_update().get(pk=validacao.demanda_id)

    def _executar_despacho_inicial(
        self,
        validacao: AssinaturaValidacaoGestor,
        payload: dict[str, Any],
        *,
        request=None,
    ) -> dict[str, Any]:
        from core.services.demanda_despacho_service import DemandaDespachoService

        demanda = self._demanda(validacao)
        if demanda.status != "AGUARDANDO_PROTOCOLO":
            raise ValueError("Demanda não está mais aguardando protocolo.")

        destinos = payload.get("destinos") or []
        if not destinos:
            raise ValueError("Destinos do despacho não encontrados na validação pendente.")

        operador = validacao.operador
        svc = DemandaDespachoService()
        svc.preparar_redespacho_protocolo(demanda)
        demanda.refresh_from_db()

        tram_pendente = validacao.tramitacao
        staging_id = payload.get("tramitacao_staging_id")
        arquivos = None
        if tram_pendente:
            arquivos = list(tram_pendente.anexos.all())
        elif staging_id:
            staging = Tramitacao.objects.filter(pk=int(staging_id)).first()
            if staging:
                arquivos = list(staging.anexos.all())

        resultado = svc.despachar_multiplo(
            demanda,
            destinos,
            usuario=operador,
            automatico=False,
            protocolo_executivo=payload.get("protocolo_executivo"),
            arquivos_anexos=arquivos or None,
            texto_despacho=payload.get("texto_despacho") or "",
            tramitacao_existente=tram_pendente,
        )

        if staging_id and not tram_pendente:
            Tramitacao.objects.filter(pk=int(staging_id)).delete()

        tram_final_id = resultado.get("tramitacao_despacho_id")
        if tram_final_id:
            from core.services.tramitacao_janela_edicao_service import TramitacaoJanelaEdicaoService

            tram_final = Tramitacao.objects.filter(pk=int(tram_final_id)).first()
            if tram_final:
                TramitacaoJanelaEdicaoService.finalizar_apos_validacao_gestor(tram_final)

        logger.info(
            "Despacho inicial executado após gestor demanda=%s validacao=%s",
            demanda.pk,
            validacao.pk,
        )
        return {"demanda_id": demanda.pk, "despacho": resultado}

    def _executar_conclusao_secretaria(
        self,
        validacao: AssinaturaValidacaoGestor,
        payload: dict[str, Any],
        *,
        request=None,
    ) -> dict[str, Any]:
        from core.services.devolutiva_protocolo_service import DevolutivaProtocoloService

        demanda = self._demanda(validacao)
        parecer = str(payload.get("parecer_operacional") or "")
        operador = validacao.operador

        DevolutivaProtocoloService().solicitar_devolutiva(
            demanda,
            operador,
            parecer_operacional=parecer,
        )
        if payload.get("resultado_operacional"):
            from core.services.estudo_viabilidade_service import EstudoViabilidadeService

            EstudoViabilidadeService().registrar_conclusao_operacional(
                demanda,
                operador,
                parecer=parecer,
                payload=payload["resultado_operacional"],
            )
        demanda.refresh_from_db()
        return {"demanda_id": demanda.pk, "status": demanda.status}

    def _executar_conclusao_secretaria_fluxo_direto(
        self,
        validacao: AssinaturaValidacaoGestor,
        payload: dict[str, Any],
        *,
        request=None,
    ) -> dict[str, Any]:
        from core.services.estudo_viabilidade_service import EstudoViabilidadeService
        from core.services.operacional_estado_service import OperacionalEstadoService

        demanda = self._demanda(validacao)
        parecer = str(payload.get("parecer_operacional") or "")
        operador = validacao.operador

        demanda = OperacionalEstadoService().aplicar_conclusao_tecnica(
            demanda, operador, parecer=parecer
        )
        if payload.get("resultado_operacional"):
            from core.services.estudo_viabilidade_service import EstudoViabilidadeService

            EstudoViabilidadeService().registrar_conclusao_operacional(
                demanda,
                operador,
                parecer=parecer,
                payload=payload["resultado_operacional"],
            )
        return {"demanda_id": demanda.pk, "status": demanda.status}

    def _executar_conclusao_final(
        self,
        validacao: AssinaturaValidacaoGestor,
        payload: dict[str, Any],
        *,
        request=None,
    ) -> dict[str, Any]:
        from core.services.devolutiva_protocolo_service import (
            DevolutivaProtocoloService,
            _parse_destinos,
            _parse_ids,
        )
        from core.services.operacional_estado_service import OperacionalEstadoService

        demanda = self._demanda(validacao)
        operador = validacao.operador
        parecer = str(payload.get("parecer_resposta") or "")
        operacional = OperacionalEstadoService()
        historico = operacional.compilar_historico_tecnico(demanda)
        tram_pendente = validacao.tramitacao

        demanda = operacional.aplicar_conclusao_final(
            demanda,
            operador,
            parecer=parecer,
            historico_compilado=historico,
            tramitacao_existente=tram_pendente,
        )
        tram = tram_pendente or demanda.tramitacoes.filter(tipo="CONCLUSAO_FINAL").order_by(
            "-timestamp"
        ).first()
        if tram:
            anexos_ids = _parse_ids(payload.get("anexos_tramitacao_ids"))
            alerta_destinos = _parse_destinos(payload.get("alerta_destinos"))
            staging_id = payload.get("tramitacao_staging_id")
            arquivos = None
            if tram_pendente:
                arquivos = list(tram_pendente.anexos.all())
            elif staging_id:
                staging = Tramitacao.objects.filter(pk=int(staging_id)).first()
                if staging:
                    arquivos = list(staging.anexos.all())
            DevolutivaProtocoloService().complementar_tramitacao_devolutiva(
                tram,
                demanda,
                operador,
                arquivos_anexos=arquivos or None,
                anexos_tramitacao_ids=anexos_ids or None,
                alerta_destinos=alerta_destinos or None,
            )
            DevolutivaProtocoloService().remover_devolutiva_redundante(demanda)
            if staging_id and not tram_pendente:
                Tramitacao.objects.filter(pk=int(staging_id)).delete()

            from core.services.tramitacao_janela_edicao_service import TramitacaoJanelaEdicaoService

            TramitacaoJanelaEdicaoService.finalizar_apos_validacao_gestor(tram)

        demanda.refresh_from_db()
        return {"demanda_id": demanda.pk, "status": demanda.status}

    def _executar_scatter_encerrar(
        self,
        validacao: AssinaturaValidacaoGestor,
        payload: dict[str, Any],
        *,
        request=None,
    ) -> dict[str, Any]:
        from core.services.scatter_gather_service import NoOperacionalService

        demanda = self._demanda(validacao)
        no_id = payload.get("no_id")
        if no_id in (None, ""):
            raise ValueError("Nó operacional não informado na validação.")
        no = NoOperacional.objects.select_for_update().get(
            pk=int(no_id), demanda_id=demanda.pk
        )
        tram = validacao.tramitacao
        if not tram:
            raise ValueError("Tramitação de encerramento não vinculada.")

        svc = NoOperacionalService()
        return svc.finalizar_encerrar_apos_gestor(
            demanda,
            no,
            tram,
            validacao.operador,
            observacao=str(payload.get("observacao") or ""),
            payload=payload,
        )

    def _executar_scatter_despachar_encerrar(
        self,
        validacao: AssinaturaValidacaoGestor,
        payload: dict[str, Any],
        *,
        request=None,
    ) -> dict[str, Any]:
        from core.services.scatter_gather_service import NoOperacionalService

        demanda = self._demanda(validacao)
        no_id = payload.get("no_id")
        if no_id in (None, ""):
            raise ValueError("Nó operacional não informado na validação.")
        svc = NoOperacionalService()
        return svc.finalizar_despachar_encerrar_apos_gestor(
            demanda,
            int(no_id),
            validacao.operador,
            payload,
        )
