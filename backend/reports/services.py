"""Agregações de process mining e métricas para relatórios."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from django.db.models import Count
from django.utils import timezone

from core.models import Demanda, Tramitacao

from .serializers import STATUS_ABERTO_RELATORIO, calcular_sla_demanda

GARGALO_ETAPA_HORAS = 48

_STATUS_PARA_CODIGO = {label: code for code, label in Demanda.STATUS_CHOICES}
_RE_STATUS_UPDATE = re.compile(
    r'Status alterado de "(.+?)" para "(.+?)"\.',
    re.IGNORECASE,
)

FUNIL_TRANSICOES = (
    {
        'codigo': 'criacao_protocolo',
        'rotulo': 'Criação → Protocolo',
        'de_status': 'AGUARDANDO_PROTOCOLO',
        'para_status': 'PROTOCOLADO',
    },
    {
        'codigo': 'protocolo_execucao',
        'rotulo': 'Protocolo → Execução',
        'de_status': 'PROTOCOLADO',
        'para_status': 'EM_EXECUCAO',
    },
    {
        'codigo': 'execucao_finalizacao',
        'rotulo': 'Execução → Finalização',
        'de_status': 'EM_EXECUCAO',
        'para_status': 'FINALIZADO',
    },
)


def _status_codigo_por_label(label: str) -> str | None:
    return _STATUS_PARA_CODIGO.get(label.strip())


def _timeline_status(demanda: Demanda) -> list[tuple[str, datetime]]:
    """Pontos (status, timestamp) ordenados cronologicamente."""
    pontos: list[tuple[str, timezone.datetime]] = []

    if demanda.data_criacao:
        pontos.append(('AGUARDANDO_PROTOCOLO', demanda.data_criacao))

    if demanda.data_inicio_prazo:
        pontos.append(('PROTOCOLADO', demanda.data_inicio_prazo))

    for tram in (
        Tramitacao.objects.filter(demanda_id=demanda.pk, tipo='STATUS_UPDATE')
        .order_by('timestamp')
        .values('descricao', 'timestamp')
    ):
        match = _RE_STATUS_UPDATE.search(tram['descricao'] or '')
        if not match:
            continue
        para_label = match.group(2)
        codigo = _status_codigo_por_label(para_label)
        if codigo:
            pontos.append((codigo, tram['timestamp']))

    if demanda.data_finalizacao and demanda.status == 'FINALIZADO':
        pontos.append(('FINALIZADO', demanda.data_finalizacao))
    elif demanda.status and demanda.data_entrada_etapa:
        pontos.append((demanda.status, demanda.data_entrada_etapa))

    pontos.sort(key=lambda x: x[1])
    dedup: list[tuple[str, timezone.datetime]] = []
    for status, ts in pontos:
        if dedup and dedup[-1][0] == status:
            continue
        dedup.append((status, ts))
    return dedup


def _duracao_transicao(timeline: list[tuple[str, datetime]], de: str, para: str) -> float | None:
    inicio = None
    for status, ts in timeline:
        if status == de and inicio is None:
            inicio = ts
        elif status == para and inicio is not None:
            return max(0.0, (ts - inicio).total_seconds() / 86400)
    return None


def agregar_funil_status(queryset) -> list[dict]:
    """Tempo médio (dias) entre etapas principais do fluxo."""
    acumuladores = {
        t['codigo']: {'total_dias': 0.0, 'count': 0}
        for t in FUNIL_TRANSICOES
    }

    for demanda in queryset.iterator(chunk_size=200):
        timeline = _timeline_status(demanda)
        for transicao in FUNIL_TRANSICOES:
            dias = _duracao_transicao(
                timeline,
                transicao['de_status'],
                transicao['para_status'],
            )
            if dias is not None:
                acc = acumuladores[transicao['codigo']]
                acc['total_dias'] += dias
                acc['count'] += 1

    resultado = []
    for transicao in FUNIL_TRANSICOES:
        acc = acumuladores[transicao['codigo']]
        media = round(acc['total_dias'] / acc['count'], 1) if acc['count'] else None
        resultado.append(
            {
                'codigo': transicao['codigo'],
                'rotulo': transicao['rotulo'],
                'de_status': transicao['de_status'],
                'para_status': transicao['para_status'],
                'amostras': acc['count'],
                'dias_medio': media,
            }
        )
    return resultado


def agregar_por_setor(queryset, *, gargalo_horas: float = GARGALO_ETAPA_HORAS) -> list[dict]:
    """Métricas operacionais por unidade administrativa (setor)."""
    buckets: dict[int | None, dict] = {}

    for demanda in queryset.select_related('unidade_administrativa'):
        unidade = demanda.unidade_administrativa
        uid = unidade.pk if unidade else None
        label = (unidade.sigla or unidade.nome) if unidade else 'Sem setor'

        bucket = buckets.setdefault(
            uid,
            {
                'unidade_id': uid,
                'setor': label,
                'total': 0,
                'atrasadas': 0,
                'em_aberto': 0,
                'tempo_etapa_total_seg': 0,
                'tempo_etapa_count': 0,
                'dias_pos_protocolo_total': 0,
                'dias_pos_protocolo_count': 0,
            },
        )
        bucket['total'] += 1

        sla = calcular_sla_demanda(demanda)
        if sla['is_atrasada']:
            bucket['atrasadas'] += 1
        if demanda.status in STATUS_ABERTO_RELATORIO:
            bucket['em_aberto'] += 1
        if sla['tempo_etapa_segundos'] is not None:
            bucket['tempo_etapa_total_seg'] += sla['tempo_etapa_segundos']
            bucket['tempo_etapa_count'] += 1
        if sla['dias_pos_protocolo'] is not None:
            bucket['dias_pos_protocolo_total'] += sla['dias_pos_protocolo']
            bucket['dias_pos_protocolo_count'] += 1

    resultado = []
    for bucket in buckets.values():
        tempo_medio_horas = None
        if bucket['tempo_etapa_count']:
            tempo_medio_horas = round(
                bucket['tempo_etapa_total_seg'] / bucket['tempo_etapa_count'] / 3600,
                1,
            )
        dias_medio_pos_protocolo = None
        if bucket['dias_pos_protocolo_count']:
            dias_medio_pos_protocolo = round(
                bucket['dias_pos_protocolo_total'] / bucket['dias_pos_protocolo_count'],
                1,
            )
        gargalo = (
            tempo_medio_horas is not None
            and tempo_medio_horas > gargalo_horas
        )
        resultado.append(
            {
                'setor': bucket['setor'],
                'unidade_id': bucket['unidade_id'],
                'total': bucket['total'],
                'em_aberto': bucket['em_aberto'],
                'atrasadas': bucket['atrasadas'],
                'tempo_medio_etapa_horas': tempo_medio_horas,
                'dias_medio_pos_protocolo': dias_medio_pos_protocolo,
                'gargalo': gargalo,
                'gargalo_limite_horas': gargalo_horas,
            }
        )

    return sorted(resultado, key=lambda x: x['total'], reverse=True)


def _metricas_vereador(queryset) -> dict:
    total = 0
    atrasadas = 0
    dias_pos_total = 0
    dias_pos_count = 0
    com_sla_aberto = 0

    for demanda in queryset.iterator(chunk_size=200):
        total += 1
        sla = calcular_sla_demanda(demanda)
        if sla['is_atrasada']:
            atrasadas += 1
        if demanda.status in STATUS_ABERTO_RELATORIO and sla['prazo_dias'] is not None:
            com_sla_aberto += 1
        if sla['dias_pos_protocolo'] is not None:
            dias_pos_total += sla['dias_pos_protocolo']
            dias_pos_count += 1

    pct_atraso = round(100 * atrasadas / com_sla_aberto, 1) if com_sla_aberto else None
    dias_medio = round(dias_pos_total / dias_pos_count, 1) if dias_pos_count else None
    return {
        'total': total,
        'atrasadas': atrasadas,
        'com_sla_aberto': com_sla_aberto,
        'pct_atraso': pct_atraso,
        'dias_medio_pos_protocolo': dias_medio,
    }


def agregar_comparativo_vereador(queryset) -> dict:
    """Comparativo por autor vs média geral."""
    media_geral = _metricas_vereador(queryset)

    por_autor = (
        queryset.filter(autor__isnull=False)
        .values('autor_id', 'autor__first_name', 'autor__last_name', 'autor__username')
        .annotate(total=Count('id'))
        .order_by('-total')
    )

    vereadores = []
    for item in por_autor:
        qs_autor = queryset.filter(autor_id=item['autor_id'])
        metricas = _metricas_vereador(qs_autor)
        nome = f"{item['autor__first_name'] or ''} {item['autor__last_name'] or ''}".strip()
        if not nome:
            nome = item['autor__username']

        delta_atraso = None
        if metricas['pct_atraso'] is not None and media_geral['pct_atraso'] is not None:
            delta_atraso = round(metricas['pct_atraso'] - media_geral['pct_atraso'], 1)

        delta_dias = None
        if (
            metricas['dias_medio_pos_protocolo'] is not None
            and media_geral['dias_medio_pos_protocolo'] is not None
        ):
            delta_dias = round(
                metricas['dias_medio_pos_protocolo'] - media_geral['dias_medio_pos_protocolo'],
                1,
            )

        vereadores.append(
            {
                'autor_id': item['autor_id'],
                'vereador': nome,
                'total': metricas['total'],
                'atrasadas': metricas['atrasadas'],
                'pct_atraso': metricas['pct_atraso'],
                'dias_medio_pos_protocolo': metricas['dias_medio_pos_protocolo'],
                'delta_pct_atraso_vs_media': delta_atraso,
                'delta_dias_pos_protocolo_vs_media': delta_dias,
            }
        )

    return {
        'media_geral': media_geral,
        'vereadores': vereadores,
    }


def calcular_metricas_sla(queryset) -> dict:
    """KPIs de SLA: abertas no prazo, encerradas no prazo."""
    agora = timezone.now()
    abertas_com_sla = 0
    abertas_no_prazo = 0
    abertas_atrasadas = 0

    encerradas_com_sla = 0
    encerradas_no_prazo = 0

    for demanda in queryset.iterator(chunk_size=200):
        prazo = demanda.prazo_dias()
        if demanda.status in STATUS_ABERTO_RELATORIO and demanda.data_inicio_prazo and prazo is not None:
            abertas_com_sla += 1
            vencimento = demanda.data_inicio_prazo + timedelta(days=prazo)
            if vencimento < agora:
                abertas_atrasadas += 1
            else:
                abertas_no_prazo += 1

        if (
            demanda.status == 'FINALIZADO'
            and demanda.data_inicio_prazo
            and demanda.data_finalizacao
            and prazo is not None
        ):
            encerradas_com_sla += 1
            vencimento = demanda.data_inicio_prazo + timedelta(days=prazo)
            if demanda.data_finalizacao <= vencimento:
                encerradas_no_prazo += 1

    pct_dentro_sla = (
        round(100 * abertas_no_prazo / abertas_com_sla, 1) if abertas_com_sla else None
    )
    pct_encerradas_no_sla = (
        round(100 * encerradas_no_prazo / encerradas_com_sla, 1) if encerradas_com_sla else None
    )

    return {
        'abertas_com_sla': abertas_com_sla,
        'abertas_no_prazo': abertas_no_prazo,
        'abertas_atrasadas': abertas_atrasadas,
        'pct_dentro_sla': pct_dentro_sla,
        'encerradas_com_sla': encerradas_com_sla,
        'encerradas_no_prazo': encerradas_no_prazo,
        'pct_encerradas_no_sla': pct_encerradas_no_sla,
    }
