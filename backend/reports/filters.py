# /var/www/sgdl/backend/reports/filters.py

import django_filters
from core.models import Demanda, Usuario, Secretaria, Servico

class DemandaReportFilter(django_filters.FilterSet):
    """
    Filtro avançado para a página de Relatórios/Dashboard.
    """

    # 1. Filtro de PERÍODO (Data)
    # CORREÇÃO: O campo no modelo é 'data_criacao'
    data_inicio = django_filters.DateFilter(
        field_name='data_criacao', # <-- CORRIGIDO
        lookup_expr='gte',         # Correto: >= (maior ou igual)
        label='Data de Início'
    )
    data_fim = django_filters.DateFilter(
        field_name='data_criacao', # <-- CORRIGIDO
        lookup_expr='lt',          # CORRIGIDO: < (menor que), para funcionar com o +1 dia do frontend
        label='Data de Fim'
    )

    # 2. Filtro de STATUS (Múltipla Escolha)
    status__in = django_filters.MultipleChoiceFilter(
        field_name='status',
        choices=Demanda.STATUS_CHOICES,
        label='Status (Múltiplos)'
    )

    # 3. Filtro de SECRETARIA (Múltipla Escolha)
    secretaria__in = django_filters.ModelMultipleChoiceFilter(
        field_name='secretaria_destino',
        to_field_name='id',
        queryset=Secretaria.objects.all(),
        label='Secretarias (Múltiplas)'
    )

    # 4. Filtro de SERVIÇO (Múltipla Escolha)
    servico__in = django_filters.ModelMultipleChoiceFilter(
        field_name='servico',
        to_field_name='id',
        queryset=Servico.objects.all(),
        label='Serviços (Múltiplos)'
    )

    # 5. Filtro de VEREADOR (Fonte)
    # CORREÇÃO: O campo no modelo é 'autor'
    vereador__in = django_filters.ModelMultipleChoiceFilter(
        field_name='autor', # <-- CORRIGIDO
        to_field_name='id',
        queryset=Usuario.objects.filter(perfil='VEREADOR'),
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