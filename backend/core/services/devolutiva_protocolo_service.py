"""Ciclo de devolutiva operacional → Protocolo → vereador → encerramento."""

from __future__ import annotations

import logging

from django.utils import timezone

from core.models import Demanda, Tramitacao, Usuario
from integrations import sinapse_catalog

logger = logging.getLogger(__name__)


class DevolutivaProtocoloService:
    def solicitar_devolutiva(
        self,
        demanda: Demanda,
        usuario,
        *,
        parecer_operacional: str,
    ) -> Demanda:
        if getattr(usuario, "perfil", None) != "SECRETARIA":
            raise ValueError("Apenas a secretaria responsável pode solicitar devolutiva.")
        if not usuario.sinapse_orgao_id or demanda.sinapse_orgao_id != usuario.sinapse_orgao_id:
            raise ValueError("Demanda não pertence à sua secretaria.")
        if demanda.status != "EM_EXECUCAO":
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

        Tramitacao.objects.create(
            demanda=demanda,
            responsavel=usuario,
            tipo="SOLICITACAO_DEVOLUTIVA",
            descricao=descricao,
        )
        logger.info("Devolutiva solicitada demanda=%s por usuario=%s", demanda.pk, usuario.pk)
        return demanda

    def despachar_devolutiva(
        self,
        demanda: Demanda,
        usuario,
        *,
        parecer_resposta: str,
    ) -> Demanda:
        if getattr(usuario, "perfil", None) not in ("PROTOCOLO", "GESTOR") and not usuario.is_staff:
            raise ValueError("Apenas o Protocolo pode despachar a devolutiva ao vereador.")
        if demanda.status != "AGUARDANDO_DEVOLUTIVA_PROTOCOLO":
            raise ValueError("Demanda não está aguardando devolutiva no Protocolo.")

        texto = (parecer_resposta or "").strip()
        if len(texto) < 10:
            raise ValueError("Informe a resposta de devolutiva ao vereador (mínimo 10 caracteres).")

        demanda.status = "DEVOLVIDO_VEREADOR"
        demanda.save(update_fields=["status"])

        Tramitacao.objects.create(
            demanda=demanda,
            responsavel=usuario,
            tipo="DEVOLUTIVA_PROTOCOLO",
            descricao=(
                f"Protocolo despachou devolutiva ao vereador "
                f"({demanda.autor.get_full_name() or demanda.autor.username}).\n"
                f"Resposta:\n{texto}"
            ),
        )
        logger.info("Devolutiva despachada demanda=%s protocolo=%s", demanda.pk, usuario.pk)
        return demanda

    def encerrar_devolutiva(self, demanda: Demanda, usuario) -> Demanda:
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
