# /var/www/sgdl/backend/reports/filters.py

import django_filters
from core.models import Demanda, Usuario, Secretaria, Servico

class DemandaReportFilter(django_filters.FilterSet):
    """
    Filtro avançado para a página de Relatórios/Dashboard.
    """

    # 1. Filtro de PERÍODO (Estes já estavam corretos)
    data_inicio = django_filters.DateFilter(
        field_name='data_criacao', 
        lookup_expr='gte',
        label='Data de Início'
    )
    data_fim = django_filters.DateFilter(
        field_name='data_criacao', 
        lookup_expr='lt',
        label='Data de Fim'
    )

    # 2. Filtro de STATUS (Múltipla Escolha)
    # CORREÇÃO: Alterado de MultipleChoiceFilter para BaseInFilter
    status__in = django_filters.BaseInFilter(
        field_name='status',
        lookup_expr='in', # Garante a consulta "WHERE status IN (...)"
        label='Status (Múltiplos)'
    )

    # 3. Filtro de SECRETARIA (Múltipla Escolha)
    # CORREÇÃO: Alterado de ModelMultipleChoiceFilter para BaseInFilter
    secretaria__in = django_filters.BaseInFilter(
        field_name='secretaria_destino_id', # Usar _id é mais rápido
        lookup_expr='in',
        label='Secretarias (Múltiplas)'
    )

    # 4. Filtro de SERVIÇO (Múltipla Escolha)
    # CORREÇÃO: Alterado de ModelMultipleChoiceFilter para BaseInFilter
    servico__in = django_filters.BaseInFilter(
        field_name='servico_id', # Usar _id é mais rápido
        lookup_expr='in',
        label='Serviços (Múltiplos)'
    )

    # 5. Filtro de VEREADOR (Fonte)
    # CORREÇÃO: Alterado de ModelMultipleChoiceFilter para BaseInFilter
    vereador__in = django_filters.BaseInFilter(
        field_name='autor_id', # O campo no modelo é 'autor', '_id' é a FK
        lookup_expr='in',
        label='Vereadores (Múltiplos)'
    )

    class Meta:
        model = Demanda
        fields = [
            'data_inicio', 
            'data_fim', 
            'status__in', 
            'secretaria__in', 
            'servico__in', 
            'vereador__in'
        ]