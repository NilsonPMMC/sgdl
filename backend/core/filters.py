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
    secretaria_destino = django_filters.NumberFilter(field_name='sinapse_orgao_id')
    unidade_administrativa = django_filters.NumberFilter(field_name='unidade_administrativa_id')
    cluster = django_filters.NumberFilter(field_name='cluster_id')
    minha_unidade = django_filters.BooleanFilter(method='filter_minha_unidade')
    fila = django_filters.CharFilter(method='filter_fila', label='Fila operacional')
    origem_vinculo = django_filters.ChoiceFilter(choices=Demanda.ORIGEM_VINCULO_CHOICES)
    trilha = django_filters.CharFilter(method='filter_trilha', label='Trilha (carta/tendencia)')

    class Meta:
        model = Demanda
        fields = [
            'status',
            'autor',
            'secretaria_destino',
            'unidade_administrativa',
            'cluster',
            'origem_vinculo',
            'trilha',
            'q',
            'fila',
            'minha_unidade',
        ]

    def filter_trilha(self, queryset, name, value):
        trilha = (value or "").strip().lower()
        if trilha == "carta":
            return queryset.filter(
                origem_vinculo=Demanda.ORIGEM_VINCULO_CARTA,
                tendencia__isnull=True,
            )
        if trilha == "tendencia":
            return queryset.filter(
                Q(origem_vinculo=Demanda.ORIGEM_VINCULO_TENDENCIA)
                | Q(tendencia_id__isnull=False)
            )
        return queryset

    def filter_minha_unidade(self, queryset, name, value):
        if not value:
            return queryset
        from core.services.tramitacao_setor_service import UnidadeAdministrativaService

        if not getattr(self.request, 'user', None) or not self.request.user.is_authenticated:
            return queryset.none()
        ids = UnidadeAdministrativaService().ids_unidades_do_usuario(self.request.user)
        if not ids:
            return queryset.none()
        return queryset.filter(unidade_administrativa_id__in=ids)

    def filter_fila(self, queryset, name, value):
        fila = (value or "").strip().lower()
        if fila == "protocolados":
            return queryset.filter(status="AGUARDANDO_PROTOCOLO")
        if fila == "operacionais":
            return queryset.filter(
                status__in=("PROTOCOLADO", "EM_EXECUCAO", "AGUARDANDO_TRANSFERENCIA")
            )
        if fila == "devolutivas":
            return queryset.filter(
                status__in=("AGUARDANDO_DEVOLUTIVA_PROTOCOLO", "DEVOLVIDO_VEREADOR")
            )
        return queryset

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