# /backend/core/filters.py
import django_filters
from .models import Demanda

class DemandaFilter(django_filters.FilterSet):
    # Permite filtrar por múltiplos status (ex: status__in=PROTOCOLADO,EM_EXECUCAO)
    status__in = django_filters.BaseInFilter(field_name='status', lookup_expr='in')
    
    # Permite excluir um status (ex: status__exclude=RASCUNHO)
    status__exclude = django_filters.CharFilter(field_name='status', exclude=True)

    class Meta:
        model = Demanda
        fields = ['status', 'autor', 'secretaria_destino']