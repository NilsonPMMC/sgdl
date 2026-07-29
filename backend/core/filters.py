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
    escopo_setor = django_filters.CharFilter(method='filter_escopo_setor_noop', label='Escopo setor secretaria')
    origem_vinculo = django_filters.ChoiceFilter(choices=Demanda.ORIGEM_VINCULO_CHOICES)
    trilha = django_filters.CharFilter(method='filter_trilha', label='Trilha (carta/tendencia)')
    consulta = django_filters.CharFilter(method='filter_consulta', label='Atalho de consulta (hub)')
    stand_by_estudo = django_filters.BooleanFilter(field_name='stand_by_estudo_viabilidade')
    tipo_legislativo = django_filters.ChoiceFilter(choices=Demanda.TIPO_LEGISLATIVO_CHOICES)

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
            'tipo_legislativo',
            'q',
            'fila',
            'minha_unidade',
            'escopo_setor',
            'consulta',
            'stand_by_estudo',
        ]

    def filter_escopo_setor_noop(self, queryset, name, value):
        """Escopo de setor (em_operacao/encerrado) aplicado em DemandaViewSet.get_queryset."""
        return queryset

    def filter_consulta(self, queryset, name, value):
        consulta = (value or "").strip().lower()
        if consulta == "atrasadas":
            from core.services.demanda_sla_service import filtrar_demandas_atrasadas

            return filtrar_demandas_atrasadas(queryset)
        return queryset

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
        from core.services.demanda_visibilidade import filtrar_demandas_minha_unidade

        if not getattr(self.request, "user", None) or not self.request.user.is_authenticated:
            return queryset.none()
        return filtrar_demandas_minha_unidade(queryset, self.request.user)

    def _parametro_consulta(self, nome: str) -> str:
        data = getattr(self, "data", None)
        if data is not None and hasattr(data, "get"):
            valor = data.get(nome)
            if valor not in (None, ""):
                return str(valor).strip().lower()
        request = getattr(self, "request", None)
        if request is not None:
            query_params = getattr(request, "query_params", None)
            if query_params is not None:
                valor = query_params.get(nome)
                if valor not in (None, ""):
                    return str(valor).strip().lower()
            get = getattr(request, "GET", None)
            if get is not None:
                valor = get.get(nome)
                if valor not in (None, ""):
                    return str(valor).strip().lower()
        return ""

    def filter_fila(self, queryset, name, value):
        fila = (value or "").strip().lower()
        escopo_setor = self._parametro_consulta("escopo_setor")
        if fila == "protocolados":
            return queryset.filter(status="AGUARDANDO_PROTOCOLO")
        if fila == "operacionais":
            if escopo_setor == "encerrado":
                return queryset.filter(
                    status__in=(
                        "PROTOCOLADO",
                        "EM_EXECUCAO",
                        "AGUARDANDO_TRANSFERENCIA",
                        "AGUARDANDO_DEVOLUTIVA_PROTOCOLO",
                        "DEVOLVIDO_VEREADOR",
                        "FINALIZADO",
                    )
                )
            return queryset.filter(
                status__in=("PROTOCOLADO", "EM_EXECUCAO", "AGUARDANDO_TRANSFERENCIA")
            )
        if fila == "devolutivas":
            return queryset.filter(
                status__in=("AGUARDANDO_DEVOLUTIVA_PROTOCOLO", "DEVOLVIDO_VEREADOR")
            )
        if fila == "finalizados":
            return queryset.filter(status="FINALIZADO")
        if fila == "stand_by":
            return queryset.filter(stand_by_estudo_viabilidade=True)
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