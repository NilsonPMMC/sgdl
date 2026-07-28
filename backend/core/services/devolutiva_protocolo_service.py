"""Ciclo de devolutiva operacional → Protocolo → vereador → encerramento."""

from __future__ import annotations

import json
import logging
from typing import Any

from django.utils.html import strip_tags
from django.utils import timezone

from core.models import Demanda, Tramitacao
from core.models_operacional import ESTADO_AGUARDANDO_CONCLUSAO_FINAL, FluxoRoteamento
from core.services.devolutiva_alerta_service import registrar_alertas_devolutiva
from core.services.operacional_estado_service import OperacionalEstadoService
from integrations import sinapse_catalog

logger = logging.getLogger(__name__)


def _texto_parecer_valido(texto: str, *, minimo: int = 10) -> str:
    limpo = strip_tags(texto or "").strip()
    if len(limpo) < minimo:
        raise ValueError(f"Informe o parecer/resposta (mínimo {minimo} caracteres).")
    return (texto or "").strip()


def _parse_destinos(raw) -> list[dict[str, Any]]:
    if raw is None or raw == "":
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


def _parse_ids(raw) -> list[int]:
    if raw is None or raw == "":
        return []
    if isinstance(raw, list):
        return [int(x) for x in raw if str(x).isdigit() or isinstance(x, int)]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [int(x) for x in parsed]
        except json.JSONDecodeError:
            pass
        return [int(x) for x in raw.split(",") if x.strip().isdigit()]
    return []


class DevolutivaProtocoloService:
    def solicitar_devolutiva(
        self,
        demanda: Demanda,
        usuario,
        *,
        parecer_operacional: str,
        registrar_tramitacao: bool = True,
    ) -> Demanda:
        if demanda.fluxo_roteamento == FluxoRoteamento.FLUXO_TRANSVERSAL:
            raise ValueError(
                "No fluxo transversal use conclusão parcial por secretaria; "
                "a conclusão geral ocorre quando todas as áreas concluírem."
            )

        operacional = OperacionalEstadoService()
        if demanda.fluxo_roteamento:
            operacional.validar_conclusao_tecnica(
                demanda, usuario, parecer=parecer_operacional
            )
        elif getattr(usuario, "perfil", None) != "SECRETARIA":
            raise ValueError("Apenas a secretaria responsável pode solicitar devolutiva.")
        elif (
            not usuario.sinapse_orgao_id
            or demanda.sinapse_orgao_id != usuario.sinapse_orgao_id
        ):
            raise ValueError("Demanda não pertence à sua secretaria.")
        elif demanda.status != "EM_EXECUCAO":
            raise ValueError("A devolutiva só pode ser solicitada com a demanda em execução.")

        texto = (parecer_operacional or "").strip()
        if len(texto) < 10:
            raise ValueError("Informe o parecer operacional (mínimo 10 caracteres).")

        demanda.status = "AGUARDANDO_DEVOLUTIVA_PROTOCOLO"
        demanda.save(update_fields=["status"])

        orgao = sinapse_catalog.get_orgao_nome(demanda.sinapse_orgao_id) or "Secretaria"
        descricao = (
            f"{orgao} concluiu a operação e encaminhou ao Protocolo para devolutiva ao vereador.\n"
            f"Parecer operacional:\n{texto}"
        )

        if registrar_tramitacao:
            if demanda.fluxo_roteamento:
                operacional.registrar_evento(
                    demanda,
                    tipo="CONCLUSAO_TECNICA",
                    usuario=usuario,
                    descricao=descricao,
                    metadata={"parecer": texto, "fluxo_roteamento": demanda.fluxo_roteamento},
                )
            Tramitacao.objects.create(
                demanda=demanda,
                responsavel=usuario,
                tipo="SOLICITACAO_DEVOLUTIVA",
                descricao=descricao,
            )
        logger.info("Devolutiva solicitada demanda=%s por usuario=%s", demanda.pk, usuario.pk)
        return demanda

    def complementar_tramitacao_devolutiva(
        self,
        tram: Tramitacao,
        demanda: Demanda,
        usuario,
        *,
        arquivos_anexos: list | None = None,
        anexos_tramitacao_ids: list[int] | None = None,
        alerta_destinos: list[dict[str, Any]] | None = None,
    ) -> Tramitacao:
        from core.services.tramitacao_anexo_service import (
            anexar_arquivos_tramitacao,
            vincular_anexos_existentes,
        )

        if anexos_tramitacao_ids:
            vincular_anexos_existentes(
                tram, anexos_tramitacao_ids, demanda_id=demanda.pk
            )
        if arquivos_anexos:
            anexar_arquivos_tramitacao(tram, arquivos_anexos)
        if alerta_destinos:
            registrar_alertas_devolutiva(demanda, tram, alerta_destinos, operador=usuario)
        return tram

    def remover_devolutiva_redundante(self, demanda: Demanda) -> int:
        """
        Remove DEVOLUTIVA_PROTOCOLO duplicada quando já existe CONCLUSAO_FINAL
        (fluxo transversal — um único marco na timeline e no banco).
        """
        if not demanda.tramitacoes.filter(tipo="CONCLUSAO_FINAL").exists():
            return 0
        removidas, _ = demanda.tramitacoes.filter(tipo="DEVOLUTIVA_PROTOCOLO").delete()
        if removidas:
            logger.info(
                "Devolutiva redundante removida demanda=%s (%s tramitação(ões))",
                demanda.pk,
                removidas,
            )
        return removidas

    def finalizar_apos_despacho_protocolo(self, demanda: Demanda, usuario) -> Demanda:
        """
        Encerra o ciclo legislativo logo após o despacho de devolutiva/conclusão final.
        O vereador continua com acesso ao laudo digital (pacote-devolutiva).
        """
        if demanda.status == "FINALIZADO":
            return demanda

        agora = timezone.now()
        demanda.status = "FINALIZADO"
        demanda.data_finalizacao = agora
        demanda.save(update_fields=["status", "data_finalizacao"])

        Tramitacao.objects.create(
            demanda=demanda,
            responsavel=usuario,
            tipo="ENCERRAMENTO_DEVOLUTIVA",
            descricao=(
                "Demanda finalizada automaticamente após despacho de devolutiva ao vereador "
                "(ciclo legislativo concluído)."
            ),
        )
        logger.info(
            "Demanda finalizada após devolutiva demanda=%s por usuario=%s",
            demanda.pk,
            usuario.pk,
        )
        return demanda

    def despachar_devolutiva(
        self,
        demanda: Demanda,
        usuario,
        *,
        parecer_resposta: str,
        arquivos_anexos: list | None = None,
        anexos_tramitacao_ids: list[int] | None = None,
        alerta_destinos: list[dict[str, Any]] | None = None,
    ) -> tuple[Demanda, Tramitacao]:
        operacional = OperacionalEstadoService()
        texto_plano = _texto_parecer_valido(parecer_resposta)
        if demanda.fluxo_roteamento:
            if demanda.status == ESTADO_AGUARDANDO_CONCLUSAO_FINAL:
                # Secretaria já concluiu (ou processo sincronizado) — Protocolo só despacha resposta.
                if getattr(usuario, "perfil", None) not in ("PROTOCOLO", "GESTOR") and not usuario.is_staff:
                    raise ValueError("Apenas o Protocolo pode despachar a devolutiva ao vereador.")
                texto = texto_plano
            else:
                texto = operacional.validar_conclusao_final(
                    demanda, usuario, parecer=texto_plano
                )
        else:
            if getattr(usuario, "perfil", None) not in ("PROTOCOLO", "GESTOR") and not usuario.is_staff:
                raise ValueError("Apenas o Protocolo pode despachar a devolutiva ao vereador.")
            if demanda.status != "AGUARDANDO_DEVOLUTIVA_PROTOCOLO":
                raise ValueError("Demanda não está aguardando devolutiva no Protocolo.")
            texto = _texto_parecer_valido(parecer_resposta)

        historico = operacional.compilar_historico_tecnico(demanda) if demanda.fluxo_roteamento else {}
        descricao_final = (
            f"Protocolo despachou devolutiva ao vereador "
            f"({demanda.autor.get_full_name() or demanda.autor.username}).\n"
            f"Resposta:\n{texto}"
        )
        if demanda.fluxo_roteamento:
            tram = operacional.registrar_evento(
                demanda,
                tipo="CONCLUSAO_FINAL",
                usuario=usuario,
                descricao=descricao_final,
                metadata={"parecer": texto, "historico_tecnico": historico},
            )
        else:
            tram = Tramitacao.objects.create(
                demanda=demanda,
                responsavel=usuario,
                tipo="DEVOLUTIVA_PROTOCOLO",
                descricao=descricao_final,
                metadata={"parecer": texto},
            )

        self.complementar_tramitacao_devolutiva(
            tram,
            demanda,
            usuario,
            arquivos_anexos=arquivos_anexos,
            anexos_tramitacao_ids=anexos_tramitacao_ids,
            alerta_destinos=alerta_destinos,
        )

        if demanda.fluxo_roteamento:
            self.remover_devolutiva_redundante(demanda)

        self.finalizar_apos_despacho_protocolo(demanda, usuario)

        logger.info("Devolutiva despachada demanda=%s protocolo=%s", demanda.pk, usuario.pk)
        return demanda, tram

    def encerrar_devolutiva(self, demanda: Demanda, usuario) -> Demanda:
        if demanda.status == "FINALIZADO":
            return demanda
        if demanda.status != "DEVOLVIDO_VEREADOR":
            raise ValueError("Demanda não está com devolutiva pendente de encerramento.")

        perfil = getattr(usuario, "perfil", None)
        if perfil == "VEREADOR" and demanda.autor_id != usuario.pk:
            raise ValueError("Apenas o autor do ofício pode encerrar esta devolutiva.")
        if perfil not in ("VEREADOR", "PROTOCOLO", "GESTOR") and not usuario.is_staff:
            raise ValueError("Sem permissão para encerrar a devolutiva.")

        agora = timezone.now()
        demanda.status = "FINALIZADO"
        demanda.data_finalizacao = agora
        demanda.save(update_fields=["status", "data_finalizacao"])

        Tramitacao.objects.create(
            demanda=demanda,
            responsavel=usuario,
            tipo="ENCERRAMENTO_DEVOLUTIVA",
            descricao="Demanda encerrada após devolutiva ao vereador (ciclo legislativo concluído).",
        )
        logger.info("Devolutiva encerrada demanda=%s por usuario=%s", demanda.pk, usuario.pk)
        return demanda
