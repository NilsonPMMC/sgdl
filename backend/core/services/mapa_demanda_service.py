"""Consulta geoespacial e agregações sazonais para o mapa operacional (E3)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Iterator

from django.db.models import Q, QuerySet
from django.utils import timezone

from core.models import Demanda
from core.services.demanda_visibilidade import aplicar_escopo_demanda
from core.services.endereco_normalizacao import endereco_minimo_para_geocode
from integrations import sinapse_catalog


STATUS_ABERTO = [
    'AGUARDANDO_PROTOCOLO',
    'PROTOCOLADO',
    'EM_EXECUCAO',
    'AGUARDANDO_TRANSFERENCIA',
    'AGUARDANDO_DEVOLUTIVA_PROTOCOLO',
    'DEVOLVIDO_VEREADOR',
]

_FILTRO_MAPA_COORDS_OU_ENDERECO = Q(
    latitude__isnull=False,
    longitude__isnull=False,
) | (
    Q(logradouro__isnull=False)
    & ~Q(logradouro='')
    & Q(bairro__isnull=False)
    & ~Q(bairro='')
)


def filtrar_demandas_mapa(request) -> QuerySet:
    """Queryset base do mapa com os mesmos filtros da API de locations."""
    queryset = (
        Demanda.objects.filter(_FILTRO_MAPA_COORDS_OU_ENDERECO)
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
    else:
        queryset = queryset.exclude(status='RASCUNHO')

    if params.get('super_os') in ('1', 'true', 'True'):
        queryset = queryset.filter(cluster__isnull=False)

    consulta = (params.get('consulta') or '').strip().lower()
    if consulta == 'atrasadas':
        from core.services.demanda_sla_service import filtrar_demandas_atrasadas

        queryset = filtrar_demandas_atrasadas(queryset)

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


def _demanda_endereco_geocodificavel(demanda: Demanda) -> bool:
    return endereco_minimo_para_geocode(demanda.logradouro, demanda.bairro)


def _persistir_coords_indicacao(demanda: Demanda, geo: dict[str, Any]) -> None:
    """Persiste coordenadas resolvidas para indicações ainda sem lat/lng."""
    if demanda.tipo_legislativo != Demanda.TIPO_LEGISLATIVO_INDICACAO:
        return
    if demanda.latitude is not None and demanda.longitude is not None:
        return

    lat = geo.get('latitude')
    lng = geo.get('longitude')
    if lat is None or lng is None:
        return

    updates: dict[str, Any] = {
        'latitude': Decimal(str(round(float(lat), 6))),
        'longitude': Decimal(str(round(float(lng), 6))),
    }
    if geo.get('logradouro') and not (demanda.logradouro or '').strip():
        updates['logradouro'] = geo['logradouro']
    if geo.get('bairro') and not (demanda.bairro or '').strip():
        updates['bairro'] = geo['bairro']
    if geo.get('cep') and not (demanda.cep or '').strip():
        updates['cep'] = geo['cep']

    Demanda.objects.filter(pk=demanda.pk, latitude__isnull=True).update(**updates)
    for campo, valor in updates.items():
        setattr(demanda, campo, valor)


def _resolver_coords_demanda_mapa(
    demanda: Demanda,
    geocoder,
    *,
    persistir_geocode: bool = True,
) -> tuple[float, float] | None:
    """Retorna lat/lng da demanda; geocodifica indicações com endereço quando necessário."""
    if demanda.latitude is not None and demanda.longitude is not None:
        return float(demanda.latitude), float(demanda.longitude)

    if not _demanda_endereco_geocodificavel(demanda):
        return None

    geo = geocoder.resolver_endereco_geocode(
        demanda.logradouro,
        demanda.bairro,
        demanda.cep,
    )
    lat = geo.get('latitude')
    lng = geo.get('longitude')
    if lat is None or lng is None:
        lat = geo.get('latitude_bruta')
        lng = geo.get('longitude_bruta')
    if lat is None or lng is None:
        return None

    if persistir_geocode:
        _persistir_coords_indicacao(demanda, geo)

    return float(lat), float(lng)


def iter_demandas_geolocalizadas_mapa(
    queryset,
    *,
    geocoder=None,
    persistir_geocode: bool = True,
) -> Iterator[tuple[Demanda, float, float]]:
    """Demandas com coordenadas válidas para exibição no mapa (salvas ou resolvidas)."""
    if geocoder is None:
        from core.services.geocoding_service import GeocodingService

        geocoder = GeocodingService()

    for demanda in queryset.iterator(chunk_size=200):
        coords = _resolver_coords_demanda_mapa(
            demanda,
            geocoder,
            persistir_geocode=persistir_geocode,
        )
        if coords is None:
            continue
        yield demanda, coords[0], coords[1]


def serializar_locations(queryset, *, super_os_only: bool = False) -> list[dict[str, Any]]:
    from core.services.cluster_service import ClusterService

    cluster_svc = ClusterService()
    agora = timezone.now()
    locations: list[dict[str, Any]] = []

    for demanda, lat, lng in iter_demandas_geolocalizadas_mapa(queryset):
        super_info = cluster_svc.info_operacional_super_os(demanda)
        if super_os_only and not super_info.get('ativo'):
            continue

        is_atrasada = _demanda_atrasada(demanda, agora)
        unidade = demanda.unidade_administrativa
        locations.append({
            'id': demanda.id,
            'lat': lat,
            'lng': lng,
            'titulo': demanda.titulo,
            'protocolo': demanda.protocolo_executivo or demanda.protocolo_legislativo,
            'protocolo_legislativo': demanda.protocolo_legislativo,
            'protocolo_executivo': demanda.protocolo_executivo,
            'status': demanda.status,
            'status_display': demanda.get_status_display(),
            'is_atrasada': is_atrasada,
            'bairro': demanda.bairro or '',
            'sinapse_servico_id': demanda.sinapse_servico_id,
            'servico_nome': _nome_servico(demanda.sinapse_servico_id),
            'data_criacao': demanda.data_criacao.isoformat() if demanda.data_criacao else None,
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


def agregar_espacial_sazonal(
    queryset,
    *,
    limit_bairros: int = 12,
    super_os_only: bool = False,
) -> dict[str, Any]:
    """Agregação bairro × serviço × mês — apenas pontos efetivamente no mapa."""
    locations = serializar_locations(queryset, super_os_only=super_os_only)
    return agregar_espacial_sazonal_de_locations(locations, limit_bairros=limit_bairros)


def agregar_espacial_sazonal_de_locations(
    locations: list[dict[str, Any]],
    *,
    limit_bairros: int = 12,
) -> dict[str, Any]:
    """Agrega somente locations com lat/lng válidos (mesma base do mapa)."""
    agora = timezone.now()

    por_bairro_counter: dict[str, int] = defaultdict(int)
    por_bairro_atrasadas: dict[str, int] = defaultdict(int)
    por_mes_counter: dict[str, int] = defaultdict(int)
    hotspot_counter: dict[tuple[str, int | None], int] = defaultdict(int)
    matriz_counter: dict[tuple[str, int | None, str], int] = defaultdict(int)

    for loc in locations:
        lat, lng = loc.get('lat'), loc.get('lng')
        if lat is None or lng is None:
            continue
        try:
            if not (-90 <= float(lat) <= 90 and -180 <= float(lng) <= 180):
                continue
        except (TypeError, ValueError):
            continue

        bairro = (loc.get('bairro') or '').strip() or 'Sem bairro'
        sid = loc.get('sinapse_servico_id')
        por_bairro_counter[bairro] += 1
        if loc.get('is_atrasada'):
            por_bairro_atrasadas[bairro] += 1
        mes_label = ''
        raw_data = loc.get('data_criacao')
        if raw_data:
            mes_label = str(raw_data)[:7]
        if mes_label:
            por_mes_counter[mes_label] += 1
        hotspot_counter[(bairro, sid)] += 1
        if mes_label:
            matriz_counter[(bairro, sid, mes_label)] += 1

    matriz = sorted(
        [
            {
                'bairro': bairro,
                'sinapse_servico_id': sid,
                'servico_nome': _nome_servico(sid),
                'mes': mes,
                'total': total,
            }
            for (bairro, sid, mes), total in matriz_counter.items()
        ],
        key=lambda x: x['total'],
        reverse=True,
    )[:50]

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
        'por_bairro_servico_mes': matriz,
        'hotspots': hotspots,
        'total_geolocalizadas': len(locations),
    }
