"""Verificação de demandas atrasadas e notificações (SLA operacional)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from core.models import Demanda
from core.services.notificacao_service import NotificacaoService


@dataclass
class ResultadoVerificacaoAtrasos:
    demandas_verificadas: int = 0
    demandas_atrasadas: int = 0
    notificacoes_criadas: int = 0

    def as_dict(self) -> dict:
        return {
            "demandas_verificadas": self.demandas_verificadas,
            "demandas_atrasadas": self.demandas_atrasadas,
            "notificacoes_criadas": self.notificacoes_criadas,
        }


class AtrasoDemandaService:
    STATUS_EM_ANDAMENTO = ["PROTOCOLADO", "EM_EXECUCAO", "AGUARDANDO_TRANSFERENCIA"]

    def executar(self) -> ResultadoVerificacaoAtrasos:
        hoje = timezone.now().date()
        resultado = ResultadoVerificacaoAtrasos()
        notif_svc = NotificacaoService()

        demandas = Demanda.objects.filter(
            status__in=self.STATUS_EM_ANDAMENTO,
            notificacao_atraso_enviada=False,
            data_inicio_prazo__isnull=False,
        )
        resultado.demandas_verificadas = demandas.count()

        demandas_atrasadas_ids: list[int] = []

        for demanda in demandas:
            prazo_dias = demanda.prazo_dias()
            if prazo_dias is None:
                continue

            data_inicio = demanda.data_inicio_prazo.date()
            data_vencimento = data_inicio + timedelta(days=prazo_dias)

            if hoje <= data_vencimento:
                continue

            demandas_atrasadas_ids.append(demanda.id)
            resultado.notificacoes_criadas += notif_svc.notificar_sla_atraso(demanda)

        if demandas_atrasadas_ids:
            Demanda.objects.filter(id__in=demandas_atrasadas_ids).update(
                notificacao_atraso_enviada=True
            )
            resultado.demandas_atrasadas = len(demandas_atrasadas_ids)

        return resultado
