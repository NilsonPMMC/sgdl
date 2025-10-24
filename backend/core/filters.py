import django_filters
from .models import Demanda, Usuario
from django.db.models import Q

class DemandaFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method='filter_q', label='Busca Geral')
    
    status = django_filters.ChoiceFilter(choices=Demanda.STATUS_CHOICES)
    
    status__exclude = django_filters.ChoiceFilter(
        field_name='status', 
        choices=Demanda.STATUS_CHOICES, 
        exclude=True
    )
    
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
    
class UsuarioFilter(django_filters.FilterSet):
    id__in = django_filters.BaseInFilter(field_name='id', lookup_expr='in')

    class Meta:
        model = Usuario
        fields = ['id', 'perfil', 'id__in']