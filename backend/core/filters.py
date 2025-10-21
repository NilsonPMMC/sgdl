import django_filters
from .models import Demanda
from django.db.models import Q

class DemandaFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method='filter_q', label='Busca Geral')
    
    status = django_filters.ChoiceFilter(choices=Demanda.STATUS_CHOICES)
    
    # --- INÍCIO DA CORREÇÃO ---
    # Adicionamos 'field_name' para dizer explicitamente qual campo filtrar,
    # resolvendo a ambiguidade do nome do filtro.
    status__exclude = django_filters.ChoiceFilter(
        field_name='status', 
        choices=Demanda.STATUS_CHOICES, 
        exclude=True
    )
    # --- FIM DA CORREÇÃO ---
    
    status__in = django_filters.BaseInFilter(field_name='status', lookup_expr='in')
    autor = django_filters.NumberFilter(field_name='autor_id')
    secretaria_destino = django_filters.NumberFilter(field_name='secretaria_destino_id')

    class Meta:
        model = Demanda
        fields = ['status', 'autor', 'secretaria_destino', 'q']

    def filter_q(self, queryset, name, value):
        if not value:
            return queryset
        
        return queryset.filter(
            Q(protocolo_legislativo__icontains=value) |
            Q(protocolo_executivo__icontains=value) |
            Q(titulo__icontains=value)
        )