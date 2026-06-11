"""Verificação de demandas atrasadas e notificações (SLA operacional)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from core.models import Demanda, Notificacao, Usuario


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

        demandas = Demanda.objects.filter(
            status__in=self.STATUS_EM_ANDAMENTO,
            notificacao_atraso_enviada=False,
            data_inicio_prazo__isnull=False,
        )
        resultado.demandas_verificadas = demandas.count()

        usuarios_protocolo = list(Usuario.objects.filter(perfil="PROTOCOLO"))
        usuarios_gestor = list(Usuario.objects.filter(perfil="GESTOR"))

        usuarios_secretaria_por_orgao: dict[int, list[Usuario]] = {}
        for usuario in Usuario.objects.filter(
            perfil="SECRETARIA",
            sinapse_orgao_id__isnull=False,
        ):
            oid = int(usuario.sinapse_orgao_id)
            usuarios_secretaria_por_orgao.setdefault(oid, []).append(usuario)

        demandas_atrasadas_ids: list[int] = []
        notificacoes_para_criar: list[Notificacao] = []

        for demanda in demandas:
            prazo_dias = demanda.prazo_dias()
            if prazo_dias is None:
                continue

            data_inicio = demanda.data_inicio_prazo.date()
            data_vencimento = data_inicio + timedelta(days=prazo_dias)

            if hoje <= data_vencimento:
                continue

            demandas_atrasadas_ids.append(demanda.id)
            protocolo = demanda.protocolo_executivo or demanda.id
            link = f"/demandas/detalhes/{demanda.id}"
            msg = f"Alerta: A demanda nº {protocolo} ({demanda.titulo}) está atrasada."

            if demanda.sinapse_orgao_id:
                for usuario in usuarios_secretaria_por_orgao.get(int(demanda.sinapse_orgao_id), []):
                    notificacoes_para_criar.append(
                        Notificacao(destinatario=usuario, mensagem=msg, link=link, tipo="ATRASO")
                    )

            for usuario in usuarios_protocolo:
                notificacoes_para_criar.append(
                    Notificacao(destinatario=usuario, mensagem=msg, link=link, tipo="ATRASO")
                )
            for usuario in usuarios_gestor:
                notificacoes_para_criar.append(
                    Notificacao(destinatario=usuario, mensagem=msg, link=link, tipo="ATRASO")
                )

        if notificacoes_para_criar:
            Notificacao.objects.bulk_create(notificacoes_para_criar)
            resultado.notificacoes_criadas = len(notificacoes_para_criar)

        if demandas_atrasadas_ids:
            Demanda.objects.filter(id__in=demandas_atrasadas_ids).update(
                notificacao_atraso_enviada=True
            )
            resultado.demandas_atrasadas = len(demandas_atrasadas_ids)

        return resultado
