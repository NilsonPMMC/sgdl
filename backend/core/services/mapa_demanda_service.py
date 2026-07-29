"""Consulta geoespacial e agregações sazonais para o mapa operacional (E3)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from django.db.models import Count, Q, QuerySet
from django.db.models.functions import TruncMonth
from django.utils import timezone

from core.models import Demanda
from core.services.demanda_visibilidade import aplicar_escopo_demanda
from integrations import sinapse_catalog


STATUS_ABERTO = [
    'AGUARDANDO_PROTOCOLO',
    'PROTOCOLADO',
    'EM_EXECUCAO',
    'AGUARDANDO_TRANSFERENCIA',
    'AGUARDANDO_DEVOLUTIVA_PROTOCOLO',
    'DEVOLVIDO_VEREADOR',
]


def filtrar_demandas_mapa(request) -> QuerySet:
    """Queryset base do mapa com os mesmos filtros da API de locations."""
    queryset = (
        Demanda.objects.exclude(status='RASCUNHO')
        .filter(latitude__isnull=False, longitude__isnull=False)
        .select_related('cluster', 'unidade_administrativa', 'autor')
    )

    params = request.query_params
    servico_id = params.get('servico_id') or params.get('sinapse_servico_id')
    if servico_id:
        queryset = queryset.filter(sinapse_servico_id=servico_id)

    orgao_id = params.get('sinapse_orgao_id') or params.get('secretaria_id')
    if orgao_id:
        queryset = queryset.filter(sinapse_orgao_id=orgao_id)

    unidade_id = params.get('unidade_administrativa_id')
    if unidade_id:
        queryset = queryset.filter(unidade_administrativa_id=unidade_id)

    demanda_id = params.get('demanda_id')
    if demanda_id:
        queryset = queryset.filter(pk=demanda_id)

    status_filter = params.get('status')
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    status_in = params.get('status__in')
    if status_in:
        statuses = [s.strip() for s in status_in.split(',') if s.strip()]
        if statuses:
            queryset = queryset.filter(status__in=statuses)

    autor_id = params.get('autor') or params.get('vereador_id')
    if autor_id:
        from core.services.indicacao_service import filtro_demandas_por_vereador

        queryset = queryset.filter(filtro_demandas_por_vereador(int(autor_id))).distinct()

    q = (params.get('q') or '').strip()
    if q:
        queryset = queryset.filter(
            Q(titulo__icontains=q)
            | Q(protocolo_executivo__icontains=q)
            | Q(protocolo_legislativo__icontains=q)
            | Q(bairro__icontains=q)
            | Q(logradouro__icontains=q)
        )

    data_inicio = params.get('data_inicio')
    if data_inicio:
        queryset = queryset.filter(data_criacao__gte=datetime.strptime(data_inicio, '%Y-%m-%d'))

    data_fim = params.get('data_fim')
    if data_fim:
        fim = datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1)
        queryset = queryset.filter(data_criacao__lt=fim)

    user = request.user
    if user.is_authenticated:
        queryset = aplicar_escopo_demanda(queryset, user)

    if params.get('super_os') in ('1', 'true', 'True'):
        queryset = queryset.filter(cluster__isnull=False)

    return queryset


def _demanda_atrasada(demanda: Demanda, agora) -> bool:
    prazo = demanda.prazo_dias()
    if (
        demanda.status in STATUS_ABERTO
        and demanda.data_inicio_prazo
        and prazo is not None
    ):
        return demanda.data_inicio_prazo + timedelta(days=prazo) < agora
    return False


def serializar_locations(queryset, *, super_os_only: bool = False) -> list[dict[str, Any]]:
    from core.services.cluster_service import ClusterService

    cluster_svc = ClusterService()
    agora = timezone.now()
    locations: list[dict[str, Any]] = []

    for demanda in queryset:
        super_info = cluster_svc.info_operacional_super_os(demanda)
        if super_os_only and not super_info.get('ativo'):
            continue

        is_atrasada = _demanda_atrasada(demanda, agora)
        unidade = demanda.unidade_administrativa
        locations.append({
            'id': demanda.id,
            'lat': demanda.latitude,
            'lng': demanda.longitude,
            'titulo': demanda.titulo,
            'protocolo': demanda.protocolo_executivo or demanda.protocolo_legislativo,
            'protocolo_legislativo': demanda.protocolo_legislativo,
            'protocolo_executivo': demanda.protocolo_executivo,
            'status': demanda.status,
            'status_display': demanda.get_status_display(),
            'is_atrasada': is_atrasada,
            'bairro': demanda.bairro or '',
            'sinapse_servico_id': demanda.sinapse_servico_id,
            'sinapse_orgao_id': demanda.sinapse_orgao_id,
            'unidade_sigla': unidade.sigla if unidade else None,
            'unidade_nome': unidade.nome if unidade else None,
            'super_os': {
                'ativo': super_info.get('ativo', False),
                'protocolo_super_os': super_info.get('protocolo_super_os'),
                'eh_lider': super_info.get('eh_lider', True),
                'cluster_id': super_info.get('cluster_id'),
                'total_vinculados': super_info.get('total_vinculados', 0),
            },
        })

    return locations


def _nome_servico(servico_id: int | None) -> str:
    if not servico_id:
        return 'Sem serviço'
    svc = sinapse_catalog.get_servico(int(servico_id))
    if svc and svc.titulo:
        return svc.titulo.strip()
    return f'Serviço {servico_id}'


def agregar_espacial_sazonal(queryset, *, limit_bairros: int = 12) -> dict[str, Any]:
    """Agregação bairro × serviço × mês para painel lateral E3."""
    agora = timezone.now()

    por_bairro_counter: dict[str, int] = defaultdict(int)
    por_bairro_atrasadas: dict[str, int] = defaultdict(int)
    por_mes_counter: dict[str, int] = defaultdict(int)
    hotspot_counter: dict[tuple[str, int | None], int] = defaultdict(int)
    matriz: list[dict[str, Any]] = []

    mensal_qs = (
        queryset.annotate(mes=TruncMonth('data_criacao'))
        .values('bairro', 'sinapse_servico_id', 'mes')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    for row in mensal_qs[:200]:
        bairro = (row['bairro'] or '').strip() or 'Sem bairro'
        sid = row['sinapse_servico_id']
        mes_val = row['mes']
        mes_label = mes_val.strftime('%Y-%m') if mes_val else ''
        matriz.append({
            'bairro': bairro,
            'sinapse_servico_id': sid,
            'servico_nome': _nome_servico(sid),
            'mes': mes_label,
            'total': row['total'],
        })

    for demanda in queryset.iterator(chunk_size=500):
        bairro = (demanda.bairro or '').strip() or 'Sem bairro'
        por_bairro_counter[bairro] += 1
        if _demanda_atrasada(demanda, agora):
            por_bairro_atrasadas[bairro] += 1
        mes_label = demanda.data_criacao.strftime('%Y-%m') if demanda.data_criacao else ''
        if mes_label:
            por_mes_counter[mes_label] += 1
        chave = (bairro, demanda.sinapse_servico_id)
        hotspot_counter[chave] += 1

    por_bairro = sorted(
        [
            {
                'bairro': b,
                'total': t,
                'atrasadas': por_bairro_atrasadas.get(b, 0),
            }
            for b, t in por_bairro_counter.items()
        ],
        key=lambda x: x['total'],
        reverse=True,
    )[:limit_bairros]

    por_mes = sorted(
        [{'mes': m, 'total': t} for m, t in por_mes_counter.items()],
        key=lambda x: x['mes'],
    )

    hotspots = sorted(
        [
            {
                'bairro': b,
                'sinapse_servico_id': sid,
                'servico_nome': _nome_servico(sid),
                'total': total,
            }
            for (b, sid), total in hotspot_counter.items()
        ],
        key=lambda x: x['total'],
        reverse=True,
    )[:15]

    return {
        'por_bairro': por_bairro,
        'por_mes': por_mes,
        'por_bairro_servico_mes': matriz[:50],
        'hotspots': hotspots,
        'total_geolocalizadas': queryset.count(),
    }
