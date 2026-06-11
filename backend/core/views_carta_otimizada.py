"""
Views para a base otimizada da carta de serviços.

Expõe a base otimizada via API REST para visualização no frontend.
"""

import logging
from django.db.models import Count, Avg, Q
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter

from .models_carta_otimizada import ServicoOtimizado, LogOtimizacao, EstatisticasBaseOtimizada
from .serializers_carta_otimizada import (
    ServicoOtimizadoSerializer, 
    LogOtimizacaoSerializer, 
    EstatisticasBaseOtimizadaSerializer
)

logger = logging.getLogger(__name__)


class ServicoOtimizadoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para serviços otimizados.
    
    Permite consulta e visualização da base otimizada,
    incluindo estatísticas e comparações.
    """
    
    queryset = ServicoOtimizado.objects.filter(ativo=True)
    serializer_class = ServicoOtimizadoSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['titulo_otimizado', 'descricao_objetiva', 'intencao_servico', 'texto_rag_otimizado']
    ordering_fields = ['score_qualidade_otimizado', 'titulo_otimizado', 'otimizado_em']
    ordering = ['-score_qualidade_otimizado']
    pagination_class = None  # limit/offset manual em get_queryset

    def get_queryset(self):
        queryset = super().get_queryset()
        query_params = getattr(self.request, 'query_params', getattr(self.request, 'GET', {}))
        
        # Filtro por score de qualidade
        score_min = query_params.get('score_min')
        if score_min:
            try:
                queryset = queryset.filter(score_qualidade_otimizado__gte=float(score_min))
            except (ValueError, TypeError):
                pass
        
        # Filtro por presença de embedding
        tem_embedding = query_params.get('tem_embedding')
        if tem_embedding in ['true', '1']:
            queryset = queryset.filter(embedding_otimizado__isnull=False)
        elif tem_embedding in ['false', '0']:
            queryset = queryset.filter(embedding_otimizado__isnull=True)

        try:
            limit = int(query_params.get('limit', 0))
            offset = int(query_params.get('offset', 0))
            if limit > 0:
                queryset = queryset[offset : offset + limit]
        except (TypeError, ValueError):
            pass

        return queryset

    def list(self, request, *args, **kwargs):
        """Lista com total para paginação no frontend."""
        base_qs = ServicoOtimizado.objects.filter(ativo=True)
        query_params = getattr(request, 'query_params', request.GET)
        search = query_params.get('search')
        if search:
            base_qs = base_qs.filter(
                Q(titulo_otimizado__icontains=search)
                | Q(descricao_objetiva__icontains=search)
                | Q(intencao_servico__icontains=search)
                | Q(texto_rag_otimizado__icontains=search)
            )
        score_min = query_params.get('score_min')
        if score_min:
            try:
                base_qs = base_qs.filter(score_qualidade_otimizado__gte=float(score_min))
            except (ValueError, TypeError):
                pass
        tem_embedding = query_params.get('tem_embedding')
        if tem_embedding in ['true', '1']:
            base_qs = base_qs.filter(embedding_otimizado__isnull=False)
        elif tem_embedding in ['false', '0']:
            base_qs = base_qs.filter(embedding_otimizado__isnull=True)

        total = base_qs.count()
        try:
            limit = int(query_params.get('limit', 20))
            offset = int(query_params.get('offset', 0))
        except (TypeError, ValueError):
            limit, offset = 20, 0
        page_qs = base_qs.order_by('-score_qualidade_otimizado')[offset : offset + limit]
        serializer = self.get_serializer(page_qs, many=True)
        return Response({'count': total, 'results': serializer.data})
    
    @action(detail=False, methods=['get'])
    def estatisticas(self, request):
        """Estatísticas gerais da base otimizada."""
        queryset = self.get_queryset()
        
        stats = {
            'total_servicos': queryset.count(),
            'com_embedding': queryset.filter(embedding_otimizado__isnull=False).count(),
            'sem_embedding': queryset.filter(embedding_otimizado__isnull=True).count(),
            'score_medio': queryset.aggregate(score_medio=Avg('score_qualidade_otimizado'))['score_medio'],
            'distribuicao_scores': {
                'excelente': queryset.filter(score_qualidade_otimizado__gte=8).count(),
                'bom': queryset.filter(score_qualidade_otimizado__gte=6, score_qualidade_otimizado__lt=8).count(),
                'regular': queryset.filter(score_qualidade_otimizado__gte=4, score_qualidade_otimizado__lt=6).count(),
                'ruim': queryset.filter(score_qualidade_otimizado__lt=4).count(),
            },
            'versoes': queryset.values('versao_otimizacao').annotate(
                count=Count('id')
            ).order_by('versao_otimizacao'),
            'tipos_processo': queryset.exclude(tipo_processo__isnull=True).values('tipo_processo').annotate(
                count=Count('id')
            ).order_by('-count'),
            'ultima_atualizacao': queryset.order_by('-atualizado_em').first().atualizado_em if queryset.exists() else None
        }
        
        # Adicionar percentual de cobertura
        if stats['total_servicos'] > 0:
            stats['percentual_cobertura'] = (stats['com_embedding'] / stats['total_servicos']) * 100
        else:
            stats['percentual_cobertura'] = 0
            
        return Response(stats)
    
    @action(detail=False, methods=['get'])
    def comparacao_scores(self, request):
        """Comparação entre scores originais e otimizados."""
        queryset = self.get_queryset()
        
        # Melhorias por faixa de score original
        comparacao = []
        faixas = [(0, 4), (4, 6), (6, 8), (8, 10)]
        
        for score_min, score_max in faixas:
            servicos_faixa = queryset.filter(
                score_qualidade_original__gte=score_min,
                score_qualidade_original__lt=score_max
            )
            
            if servicos_faixa.exists():
                faixa_stats = {
                    'faixa': f"{score_min}-{score_max}",
                    'quantidade': servicos_faixa.count(),
                    'score_original_medio': servicos_faixa.aggregate(
                        avg=Avg('score_qualidade_original')
                    )['avg'],
                    'score_otimizado_medio': servicos_faixa.aggregate(
                        avg=Avg('score_qualidade_otimizado')
                    )['avg'],
                }
                faixa_stats['melhoria_media'] = (
                    faixa_stats['score_otimizado_medio'] - faixa_stats['score_original_medio']
                )
                comparacao.append(faixa_stats)
        
        return Response({
            'comparacao_por_faixa': comparacao,
            'melhoria_geral': queryset.aggregate(
                original=Avg('score_qualidade_original'),
                otimizado=Avg('score_qualidade_otimizado')
            )
        })
    
    @action(detail=True, methods=['get'])
    def historico(self, request, pk=None):
        """Histórico de otimizações de um serviço específico."""
        servico = self.get_object()
        logs = LogOtimizacao.objects.filter(
            servico_otimizado=servico
        ).order_by('-timestamp')
        
        serializer = LogOtimizacaoSerializer(logs, many=True)
        return Response({
            'servico': ServicoOtimizadoSerializer(servico).data,
            'historico': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def problemas_comuns(self, request):
        """Análise dos problemas mais identificados."""
        queryset = self.get_queryset()
        
        # Contar problemas mais frequentes
        problemas_count = {}
        for servico in queryset.exclude(problemas_identificados__isnull=True):
            problemas = servico.problemas_identificados or []
            for problema in problemas:
                problemas_count[problema] = problemas_count.get(problema, 0) + 1
        
        # Ordenar por frequência
        problemas_ordenados = sorted(
            problemas_count.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:10]
        
        return Response({
            'problemas_comuns': [
                {'problema': problema, 'frequencia': freq}
                for problema, freq in problemas_ordenados
            ],
            'problemas_mais_frequentes': [
                {'problema': problema, 'frequencia': freq} 
                for problema, freq in problemas_ordenados
            ],
            'total_servicos_com_problemas': queryset.exclude(
                problemas_identificados__isnull=True
            ).exclude(problemas_identificados=[]).count()
        })


class LogOtimizacaoViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet para logs de otimização."""
    
    queryset = LogOtimizacao.objects.all()
    serializer_class = LogOtimizacaoSerializer
    permission_classes = [IsAuthenticated]
    
    filterset_fields = ['operacao', 'usuario']
    ordering = ['-timestamp']
    
    @action(detail=False, methods=['get'])
    def resumo_atividades(self, request):
        """Resumo das atividades de otimização."""
        queryset = self.get_queryset()
        
        # Últimos 30 dias
        desde = timezone.now() - timezone.timedelta(days=30)
        recentes = queryset.filter(timestamp__gte=desde)
        
        resumo = {
            'total_operacoes': queryset.count(),
            'operacoes_recentes': recentes.count(),
            'por_operacao': queryset.values('operacao').annotate(
                count=Count('id')
            ).order_by('-count'),
            'por_usuario': queryset.values('usuario').annotate(
                count=Count('id')
            ).order_by('-count')[:5],
            'timeline_recente': recentes.values(
                'timestamp__date'
            ).annotate(
                count=Count('id')
            ).order_by('timestamp__date')
        }
        
        return Response(resumo)


class EstatisticasBaseOtimizadaViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet para estatísticas históricas."""
    
    queryset = EstatisticasBaseOtimizada.objects.all()
    serializer_class = EstatisticasBaseOtimizadaSerializer
    permission_classes = [IsAuthenticated]
    
    ordering = ['-data_calculo']
    
    @action(detail=False, methods=['get'])
    def evolucao(self, request):
        """Evolução da qualidade da base ao longo do tempo."""
        queryset = self.get_queryset().order_by('data_calculo')
        
        evolucao = []
        for stat in queryset:
            evolucao.append({
                'data': stat.data_calculo,
                'total_servicos': stat.total_servicos,
                'cobertura_embedding': (
                    stat.servicos_com_embedding / stat.total_servicos * 100
                    if stat.total_servicos > 0 else 0
                ),
                'score_medio': stat.score_medio_qualidade
            })
        
        return Response({
            'evolucao_temporal': evolucao,
            'primeira_medicao': evolucao[0] if evolucao else None,
            'ultima_medicao': evolucao[-1] if evolucao else None
        })