"""Serializers e helpers SLA para relatórios gerenciais."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from core.models import Demanda
from integrations import sinapse_catalog

STATUS_ABERTO_RELATORIO = [
    'AGUARDANDO_PROTOCOLO',
    'PROTOCOLADO',
    'EM_EXECUCAO',
    'AGUARDANDO_TRANSFERENCIA',
    'AGUARDANDO_DEVOLUTIVA_PROTOCOLO',
    'DEVOLVIDO_VEREADOR',
]


def calcular_sla_demanda(demanda: Demanda) -> dict:
    """Prazo, vencimento, dias pós-protocolo e flag de atraso."""
    agora = timezone.now()
    prazo_dias = demanda.prazo_dias()
    data_vencimento = None
    dias_restantes = None
    is_atrasada = False

    if demanda.data_inicio_prazo and prazo_dias is not None:
        data_vencimento = demanda.data_inicio_prazo + timedelta(days=prazo_dias)
        dias_restantes = (data_vencimento.date() - agora.date()).days
        if demanda.status in STATUS_ABERTO_RELATORIO:
            is_atrasada = data_vencimento < agora

    dias_pos_protocolo = None
    if demanda.data_inicio_prazo:
        dias_pos_protocolo = max(0, (agora.date() - demanda.data_inicio_prazo.date()).days)

    referencia_etapa = demanda.data_entrada_etapa or demanda.data_criacao
    tempo_etapa_segundos = None
    if referencia_etapa:
        tempo_etapa_segundos = max(0, int((agora - referencia_etapa).total_seconds()))

    return {
        'prazo_dias': prazo_dias,
        'prazo_efetivo_dias': demanda.prazo_efetivo_dias,
        'prazo_origem': demanda.prazo_origem or None,
        'data_inicio_prazo': demanda.data_inicio_prazo,
        'data_vencimento': data_vencimento,
        'dias_restantes_sla': dias_restantes,
        'dias_pos_protocolo': dias_pos_protocolo,
        'is_atrasada': is_atrasada,
        'tempo_etapa_segundos': tempo_etapa_segundos,
    }


class DemandaRelatorioSerializer(serializers.ModelSerializer):
    criado_por_id = serializers.ReadOnlyField(source='autor_id')
    autor_nome = serializers.SerializerMethodField()
    servico_nome = serializers.SerializerMethodField()
    secretaria_destino_nome = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    unidade_administrativa = serializers.SerializerMethodField()
    prazo_resolvido = serializers.SerializerMethodField()
    sla = serializers.SerializerMethodField()
    cluster = serializers.SerializerMethodField()
    tem_geolocalizacao = serializers.SerializerMethodField()

    class Meta:
        model = Demanda
        fields = [
            'id',
            'titulo',
            'protocolo_legislativo',
            'protocolo_executivo',
            'criado_por_id',
            'autor_nome',
            'secretaria_destino_nome',
            'status',
            'status_display',
            'data_criacao',
            'data_entrada_etapa',
            'data_inicio_prazo',
            'data_finalizacao',
            'servico_nome',
            'sinapse_servico_id',
            'prazo_efetivo_dias',
            'prazo_origem',
            'prazo_resolvido',
            'unidade_administrativa',
            'sla',
            'cluster',
            'latitude',
            'longitude',
            'bairro',
            'tem_geolocalizacao',
        ]

    def get_autor_nome(self, obj: Demanda) -> str:
        autor = obj.autor
        if not autor:
            return 'Sem autor'
        nome = f'{autor.first_name or ""} {autor.last_name or ""}'.strip()
        return nome or autor.username

    def get_servico_nome(self, obj: Demanda) -> str:
        catalog = sinapse_catalog.get_servico(obj.sinapse_servico_id)
        return catalog.titulo if catalog else ''

    def get_secretaria_destino_nome(self, obj: Demanda) -> str:
        nome = sinapse_catalog.get_orgao_nome(obj.sinapse_orgao_id)
        return nome or 'Aguardando Protocolo'

    def get_prazo_resolvido(self, obj: Demanda) -> dict:
        return obj.prazo_resolvido_dict()

    def get_unidade_administrativa(self, obj: Demanda):
        unidade = obj.unidade_administrativa
        if not unidade:
            return None
        return {
            'id': unidade.pk,
            'nome': unidade.nome,
            'sigla': unidade.sigla,
        }

    def get_sla(self, obj: Demanda) -> dict:
        info = calcular_sla_demanda(obj)
        return {
            'prazo_dias': info['prazo_dias'],
            'data_vencimento': info['data_vencimento'].isoformat() if info['data_vencimento'] else None,
            'dias_restantes': info['dias_restantes_sla'],
            'dias_pos_protocolo': info['dias_pos_protocolo'],
            'is_atrasada': info['is_atrasada'],
            'tempo_etapa_segundos': info['tempo_etapa_segundos'],
        }

    def get_cluster(self, obj: Demanda):
        cluster = obj.cluster
        if not cluster:
            return None
        return {
            'id': cluster.pk,
            'titulo': cluster.titulo,
            'protocolo_super_os': cluster.protocolo_super_os,
        }

    def get_tem_geolocalizacao(self, obj: Demanda) -> bool:
        return obj.latitude is not None and obj.longitude is not None
