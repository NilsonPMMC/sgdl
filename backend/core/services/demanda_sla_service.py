"""Filtros de SLA operacional reutilizados na listagem e nos contadores."""

from __future__ import annotations

from datetime import timedelta

from django.db import connections
from django.utils import timezone

STATUS_ABERTO_SLA = (
    "PROTOCOLADO",
    "EM_EXECUCAO",
    "AGUARDANDO_TRANSFERENCIA",
    "AGUARDANDO_PROTOCOLO",
)


def demanda_esta_atrasada(demanda, agora=None) -> bool:
    agora = agora or timezone.now()
    prazo = demanda.prazo_dias()
    if demanda.status not in STATUS_ABERTO_SLA:
        return False
    if not demanda.data_inicio_prazo or prazo is None:
        return False
    return demanda.data_inicio_prazo + timedelta(days=prazo) < agora


def filtrar_demandas_atrasadas(queryset):
    """Demandas abertas com SLA vencido (prioriza snapshot `prazo_efetivo_dias`)."""
    agora = timezone.now()
    qs = queryset.filter(
        status__in=STATUS_ABERTO_SLA,
        data_inicio_prazo__isnull=False,
        prazo_efetivo_dias__isnull=False,
    )
    if connections[qs.db].vendor == "postgresql":
        table = qs.model._meta.db_table
        return qs.extra(
            where=[
                f'"{table}".data_inicio_prazo + ("{table}".prazo_efetivo_dias * INTERVAL \'1 day\') < %s'
            ],
            params=[agora],
        )

    ids = [
        demanda.pk
        for demanda in qs.only(
            "pk",
            "status",
            "data_inicio_prazo",
            "prazo_efetivo_dias",
            "prazo_origem",
            "sinapse_servico_id",
        )
        if demanda_esta_atrasada(demanda, agora)
    ]
    return qs.filter(pk__in=ids)


def contar_demandas_atrasadas(queryset) -> int:
    return filtrar_demandas_atrasadas(queryset).count()
