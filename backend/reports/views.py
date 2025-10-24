from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, generics
from django.db.models import Count, Q

from core.models import Demanda
from core.serializers import DemandaListSerializer
from .filters import DemandaReportFilter

class BaseReportView(APIView):
    """
    View base para relatórios que usa o DemandaReportFilter.
    """
    permission_classes = [permissions.IsAuthenticated] # Protege os relatórios

    def get_filtered_queryset(self, request):
        # Instancia o filtro com os parâmetros da URL (request.GET)
        filterset = DemandaReportFilter(request.GET, queryset=Demanda.objects.all())
        
        # Retorna o queryset já filtrado
        return filterset.qs

class DemandasPorStatusView(BaseReportView):
    """
    Endpoint: /api/reports/por-status/
    Retorna a contagem de demandas agrupadas por status.
    Ex: [{"status": "ABERTA", "total": 10}, {"status": "EM_EXECUCAO", "total": 5}]
    """
    def get(self, request, *args, **kwargs):
        qs_filtrado = self.get_filtered_queryset(request)
        
        # Agrega os dados em cima do queryset JÁ FILTRADO
        dados_agregados = qs_filtrado.values('status').annotate(
            total=Count('id')
        ).order_by('status')
        
        return Response(dados_agregados)

class DemandasPorSecretariaView(BaseReportView):
    def get(self, request, *args, **kwargs):
        qs_filtrado = self.get_filtered_queryset(request)
        
        status_aberto = [
            'AGUARDANDO_PROTOCOLO', 
            'PROTOCOLADO', 
            'EM_EXECUCAO', 
            'AGUARDANDO_TRANSFERENCIA'
        ]
        
        dados_agregados = qs_filtrado.filter(
            secretaria_destino__isnull=False
        ).values(
            'secretaria_destino__nome'
        ).annotate(
            total=Count('id'),
            abertas=Count('id', filter=Q(status__in=status_aberto))
        ).order_by('-total')
        
        dados = [
            {
                'secretaria': item['secretaria_destino__nome'], 
                'total': item['total'],
                'abertas': item['abertas']
            } 
            for item in dados_agregados
        ]
        
        return Response(dados)

class DemandasPorVereadorView(BaseReportView):
    """
    Endpoint: /api/reports/por-vereador/
    Versão Híbrida: Separa o processamento de demandas com autor
    daquelas que não têm (criado_por=NULL).
    """
    def get(self, request, *args, **kwargs):
        qs_filtrado = self.get_filtered_queryset(request)
        
        # --- ABORDAGEM HÍBRIDA ---

        # 1. Agrega apenas as demandas que TÊM um autor (criado_por != NULL)
        # Isso evita o crash do JOIN com NULLs.
        qs_com_autor = qs_filtrado.filter(criado_por__isnull=False)
        
        dados_agregados = qs_com_autor.values(
            'criado_por_id', 
            'criado_por__first_name', 
            'criado_por__last_name',
            'criado_por__username'
        ).annotate(
            total=Count('id')
        ).order_by('-total')

        # 2. Conta as demandas SEM autor (criado_por = NULL) separadamente
        total_sem_autor = qs_filtrado.filter(criado_por__isnull=True).count()

        # 3. Formata a resposta
        dados = []
        for item in dados_agregados:
            # Formata o nome de forma segura, com fallback para username
            nome = f"{item['criado_por__first_name'] or ''} {item['criado_por__last_name'] or ''}".strip()
            if not nome:
                nome = item['criado_por__username']
            
            dados.append({
                'vereador': nome,
                'total': item['total']
            })
        
        # 4. Adiciona a contagem de "Sem Autor" no final, se houver
        if total_sem_autor > 0:
            dados.append({
                'vereador': 'Sem Autor (Sistema/Antigo)',
                'total': total_sem_autor
            })
        
        return Response(dados)

class HeatmapView(BaseReportView):
    """
    Endpoint: /api/reports/heatmap/
    Retorna uma lista de coordenadas (latitude/longitude) das demandas filtradas.
    Ex: [{"lat": -23.55, "lng": -46.63}, {"lat": -23.56, "lng": -46.64}]
    """
    def get(self, request, *args, **kwargs):
        qs_filtrado = self.get_filtered_queryset(request)
        
        # Filtra apenas demandas que tenham geolocalização
        dados_geo = qs_filtrado.filter(
            latitude__isnull=False, 
            longitude__isnull=False
        ).values(
            'latitude', 
            'longitude'
        )
        
        # Renomeia os campos para o padrão (lat, lng)
        dados = [{'lat': item['latitude'], 'lng': item['longitude']} for item in dados_geo]
        
        return Response(dados)
    
# Em /var/www/sgdl/backend/reports/views.py

class DemandasFiltradasView(generics.ListAPIView):
    queryset = Demanda.objects.all().select_related(
        'secretaria_destino' # APENAS secretaria
    ).order_by('-data_criacao')

    # Usa o serializer que retorna o ID
    serializer_class = DemandaListSerializer 
    filterset_class = DemandaReportFilter # MANTENHA COMENTADO
    permission_classes = [permissions.IsAuthenticated]