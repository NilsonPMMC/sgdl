# Em /var/www/sgdl/backend/reports/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, generics
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
import logging
logger = logging.getLogger(__name__)

from core.models import Demanda
from integrations import sinapse_catalog
from core.serializers import DemandaListSerializer
from .filters import DemandaReportFilter

class BaseReportView(APIView):
    """
    View base para relatórios que usa o DemandaReportFilter.
    """
    permission_classes = [permissions.IsAuthenticated] # Protege os relatórios

    def get_filtered_queryset(self, request):
        logger.debug("Filtros recebidos para relatórios: %s", request.GET)
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
        
        por_orgao: dict[int, dict] = {}
        for row in qs_filtrado.filter(sinapse_orgao_id__isnull=False).values(
            "sinapse_orgao_id", "status"
        ):
            oid = row["sinapse_orgao_id"]
            bucket = por_orgao.setdefault(oid, {"total": 0, "abertas": 0})
            bucket["total"] += 1
            if row["status"] in status_aberto:
                bucket["abertas"] += 1

        dados = sorted(
            [
                {
                    "secretaria": sinapse_catalog.get_orgao_nome(oid) or str(oid),
                    "total": vals["total"],
                    "abertas": vals["abertas"],
                }
                for oid, vals in por_orgao.items()
            ],
            key=lambda x: x["total"],
            reverse=True,
        )
        
        return Response(dados)

class DemandasPorVereadorView(BaseReportView):
    """
    Endpoint: /api/reports/por-vereador/
    Versão Híbrida: Separa o processamento de demandas com autor
    daquelas que não têm (autor=NULL).
    """
    def get(self, request, *args, **kwargs):
        qs_filtrado = self.get_filtered_queryset(request)
        
        # --- ABORDAGEM HÍBRIDA ---

        # 1. Agrega apenas as demandas que TÊM um autor (autor != NULL)
        # Isso evita o crash do JOIN com NULLs.
        qs_com_autor = qs_filtrado.filter(autor__isnull=False)
        
        dados_agregados = qs_com_autor.values(
            'autor_id', 
            'autor__first_name', 
            'autor__last_name',
            'autor__username'
        ).annotate(
            total=Count('id')
        ).order_by('-total')

        # 2. Conta as demandas SEM autor (autor = NULL) separadamente
        total_sem_autor = qs_filtrado.filter(autor__isnull=True).count()

        # 3. Formata a resposta
        dados = []
        for item in dados_agregados:
            # Formata o nome de forma segura, com fallback para username
            nome = f"{item['autor__first_name'] or ''} {item['autor__last_name'] or ''}".strip()
            if not nome:
                nome = item['autor__username']
            
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
    
class DemandasFiltradasView(generics.ListAPIView):
    queryset = Demanda.objects.all().select_related(
        'secretaria_destino'
    )
    serializer_class = DemandaListSerializer 
    permission_classes = [permissions.IsAuthenticated]
    filterset_class = DemandaReportFilter 
    

    def get_queryset(self):
        """
        Sobrescreve o get_queryset para APLICAR O FILTRO MANUALMENTE,
        já que o modo automático (declarativo) não está funcionando.
        """
        logger.debug("Filtros recebidos para tabela: %s", self.request.GET)
        base_queryset = self.queryset
        filterset = DemandaReportFilter(self.request.GET, queryset=base_queryset)
        return filterset.qs.order_by('-data_criacao')

# Em backend/reports/views.py

class ReportKPIsView(BaseReportView):
    """
    Endpoint: /api/reports/kpis/
    Retorna os 4 KPIs (cards) para a tela de Relatórios,
    respeitando o DemandaReportFilter.
    """
    def get(self, request, *args, **kwargs):
        try:
            queryset = self.get_filtered_queryset(request)

            total_demandas = queryset.count()

            status_aberto = [
                'AGUARDANDO_PROTOCOLO', 
                'PROTOCOLADO', 
                'EM_EXECUCAO', 
                'AGUARDANDO_TRANSFERENCIA'
            ]
            demandas_abertas = queryset.filter(status__in=status_aberto).count()
            
            demandas_concluidas = queryset.filter(status='FINALIZADO').count()

            agora = timezone.now()
            demandas_com_vencimento = queryset.filter(
                status__in=status_aberto,
                data_inicio_prazo__isnull=False,
            )

            demandas_atrasadas = sum(
                1
                for demanda in demandas_com_vencimento
                if demanda.prazo_dias() is not None
                and demanda.data_inicio_prazo + timedelta(days=demanda.prazo_dias()) < agora
            )

            return Response({
                'total_demandas': total_demandas,
                'demandas_abertas': demandas_abertas,
                'demandas_concluidas': demandas_concluidas,
                'demandas_atrasadas': demandas_atrasadas
            })
        
        except Exception:
            logger.exception("Falha inesperada ao gerar KPIs.")
            return Response(
                {"erro": "Erro interno ao gerar os KPIs."}, 
                status=500 
            )