import django_filters
from core.models import Demanda, Usuario, Secretaria, Servico

class DemandaReportFilter(django_filters.FilterSet):
    """
    Filtro avançado para a página de Relatórios/Dashboard.
    Permite múltiplas escolhas e filtros por intervalo de datas.
    """

    # 1. Filtro de PERÍODO (Data)
    # Permite filtrar por ?data_inicio=YYYY-MM-DD&data_fim=YYYY-MM-DD
    data_inicio = django_filters.DateFilter(
        field_name='criado_em', 
        lookup_expr='gte', 
        label='Data de Início'
    )
    data_fim = django_filters.DateFilter(
        field_name='criado_em', 
        lookup_expr='lte', 
        label='Data de Fim'
    )

    # 2. Filtro de STATUS (Múltipla Escolha)
    # Permite filtrar por ?status__in=ABERTA,PROTOCOLADA
    status__in = django_filters.MultipleChoiceFilter(
        field_name='status',
        choices=Demanda.STATUS_CHOICES,
        label='Status (Múltiplos)'
    )

    # 3. Filtro de SECRETARIA (Múltipla Escolha)
    # Permite filtrar por ?secretaria__in=1,2,5
    secretaria__in = django_filters.ModelMultipleChoiceFilter(
        field_name='secretaria_destino',
        to_field_name='id',
        queryset=Secretaria.objects.all(),
        label='Secretarias (Múltiplas)'
    )

    # 4. Filtro de SERVIÇO (Múltipla Escolha)
    # Permite filtrar por ?servico__in=10,12,15
    servico__in = django_filters.ModelMultipleChoiceFilter(
        field_name='servico',
        to_field_name='id',
        queryset=Servico.objects.all(),
        label='Serviços (Múltiplos)'
    )

    # 5. Filtro de GEOGRAFIA (Não é um filtro, é um dado)
    # Os endpoints de geolocalização (heatmap) usarão os outros 5 filtros.

    # 6. Filtro de VEREADOR (Fonte) (Múltipla Escolha)
    # Permite filtrar por ?vereador__in=3,4
    # (Usando 'criado_por', que vi no seu models.py)
    vereador__in = django_filters.ModelMultipleChoiceFilter(
        field_name='autor',
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