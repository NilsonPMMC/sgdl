"""
Comando para processar TODOS os serviços da carta Sinapse para a base otimizada local.

Este comando cria uma nova base de dados otimizada baseada no legado do Sinapse,
sem alterar os dados originais (read-only).
"""

import logging
from datetime import datetime
from typing import List, Dict, Any
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, models
from django.utils import timezone

from integrations.models_sinapse import CatalogServico, SINAPSE_DB_ALIAS
from core.models_carta_otimizada import ServicoOtimizado, LogOtimizacao, EstatisticasBaseOtimizada
from core.services.embedding_service import EmbeddingOptimizationService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """
    Processa TODOS os serviços da carta Sinapse para criar base otimizada local.
    
    Cria nova base sem alterar dados originais (Sinapse read-only).
    Inclui limpeza, estruturação e otimização de embeddings.
    
    Exemplos:
    python manage.py processar_todos_servicos_otimizados
    python manage.py processar_todos_servicos_otimizados --lote-tamanho 100
    python manage.py processar_todos_servicos_otimizados --reprocessar --verbose
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--lote-tamanho',
            type=int,
            default=50,
            help='Tamanho do lote para processamento (default: 50)',
        )
        parser.add_argument(
            '--reprocessar',
            action='store_true',
            help='Reprocessar serviços já otimizados',
        )
        parser.add_argument(
            '--limite-total',
            type=int,
            help='Limite total de serviços para processar (para testes)',
        )
        parser.add_argument(
            '--score-minimo',
            type=int,
            default=5,
            help='Score mínimo para aplicar otimizações (default: 5)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Saída mais detalhada',
        )

    def handle(self, *args, **options):
        inicio = timezone.now()
        
        self.stdout.write(
            self.style.SUCCESS("🚀 Processando TODOS os serviços para base otimizada...")
        )
        
        try:
            # Estatísticas iniciais
            total_sinapse = self._contar_servicos_sinapse()
            total_otimizados = ServicoOtimizado.objects.count()
            
            self.stdout.write(f"📊 Situação atual:")
            self.stdout.write(f"   Serviços no Sinapse: {total_sinapse}")
            self.stdout.write(f"   Já otimizados: {total_otimizados}")
            self.stdout.write(f"   Restantes: {total_sinapse - total_otimizados}")
            
            # Coletar IDs para processar
            ids_processar = self._coletar_ids_processar(options)
            
            if not ids_processar:
                self.stdout.write(
                    self.style.WARNING("✅ Todos os serviços já estão processados!")
                )
                return
            
            self.stdout.write(f"🎯 Processando {len(ids_processar)} serviços...")
            
            # Processar em lotes
            resultados = self._processar_em_lotes(ids_processar, options)
            
            # Gerar estatísticas finais
            self._gerar_estatisticas_finais(inicio)
            
            # Relatório final
            self._mostrar_relatorio_final(resultados, inicio)
            
        except Exception as e:
            raise CommandError(f"Erro no processamento: {str(e)}")

    def _contar_servicos_sinapse(self) -> int:
        """Conta total de serviços ativos no Sinapse."""
        return CatalogServico.objects.using(SINAPSE_DB_ALIAS).filter(status=1).count()

    def _coletar_ids_processar(self, options: Dict[str, Any]) -> List[int]:
        """Coleta IDs dos serviços que precisam ser processados."""
        
        # Todos os serviços ativos do Sinapse
        queryset = CatalogServico.objects.using(SINAPSE_DB_ALIAS).filter(status=1)
        
        if not options.get('reprocessar'):
            # Excluir já processados
            ids_processados = set(
                ServicoOtimizado.objects.values_list('sinapse_servico_id', flat=True)
            )
            queryset = queryset.exclude(id__in=ids_processados)
        
        # Aplicar limite se especificado
        if options.get('limite_total'):
            queryset = queryset[:options['limite_total']]
        
        return list(queryset.values_list('id', flat=True))

    def _processar_em_lotes(self, ids_processar: List[int], options: Dict[str, Any]) -> Dict[str, Any]:
        """Processa serviços em lotes."""
        
        lote_tamanho = options['lote_tamanho']
        verbose = options.get('verbose', False)
        
        resultados = {
            'total_processados': 0,
            'total_otimizados': 0,
            'total_aplicados': 0,
            'erros': 0,
            'detalhes_por_lote': []
        }
        
        # Dividir em lotes
        for i in range(0, len(ids_processar), lote_tamanho):
            lote_ids = ids_processar[i:i + lote_tamanho]
            lote_num = (i // lote_tamanho) + 1
            total_lotes = (len(ids_processar) + lote_tamanho - 1) // lote_tamanho
            
            self.stdout.write(f"\n🔄 Processando lote {lote_num}/{total_lotes} ({len(lote_ids)} serviços)")
            
            # Processar lote
            resultado_lote = self._processar_lote(lote_ids, options)
            
            # Acumular resultados
            resultados['total_processados'] += resultado_lote['total_processados']
            resultados['total_otimizados'] += resultado_lote['total_otimizados']  
            resultados['total_aplicados'] += resultado_lote['total_aplicados']
            resultados['erros'] += resultado_lote['erros']
            resultados['detalhes_por_lote'].append(resultado_lote)
            
            if verbose:
                self.stdout.write(f"   ✅ Processados: {resultado_lote['total_processados']}")
                self.stdout.write(f"   🎯 Otimizados: {resultado_lote['total_otimizados']}")
                self.stdout.write(f"   💾 Aplicados: {resultado_lote['total_aplicados']}")
                if resultado_lote['erros'] > 0:
                    self.stdout.write(f"   ⚠️  Erros: {resultado_lote['erros']}")
        
        return resultados

    def _processar_lote(self, servico_ids: List[int], options: Dict[str, Any]) -> Dict[str, Any]:
        """Processa um lote específico de serviços."""
        
        embedding_service = EmbeddingOptimizationService()
        score_minimo = options.get('score_minimo', 5)
        
        resultados = {
            'total_processados': 0,
            'total_otimizados': 0,
            'total_aplicados': 0,
            'erros': 0,
            'scores_antes': [],
            'scores_depois': []
        }
        
        for servico_id in servico_ids:
            try:
                # Otimizar serviço individual
                resultado = embedding_service.otimizar_embedding_servico(
                    servico_id=servico_id,
                    aplicar_alteracoes=True  # Sempre aplicar na nova base
                )
                
                resultados['total_processados'] += 1
                
                # Verificar se foi otimizado
                score_novo = resultado.get('score_qualidade_novo', 0)
                if score_novo >= score_minimo:
                    resultados['total_otimizados'] += 1
                
                # Verificar se foi aplicado (salvo na base)
                if resultado.get('alteracoes_aplicadas', False):
                    resultados['total_aplicados'] += 1
                
                # Coletar scores para estatísticas
                score_original = resultado.get('score_qualidade_original', 0)
                if score_original > 0:
                    resultados['scores_antes'].append(score_original)
                    resultados['scores_depois'].append(score_novo)
                
            except Exception as e:
                resultados['erros'] += 1
                logger.error(f"Erro ao processar serviço {servico_id}: {str(e)}")
                
                # Mostrar só primeiros erros para não poluir saída
                if resultados['erros'] <= 3:
                    self.stdout.write(
                        self.style.WARNING(f"   ⚠️  Erro serviço {servico_id}: {str(e)[:100]}...")
                    )
        
        return resultados

    def _gerar_estatisticas_finais(self, inicio: datetime):
        """Gera estatísticas consolidadas da base otimizada."""
        
        try:
            # Contadores básicos
            total_sinapse = self._contar_servicos_sinapse()
            total_otimizados = ServicoOtimizado.objects.count()
            total_validados = ServicoOtimizado.objects.filter(validado_humano=True).count()
            total_precisam_revisao = ServicoOtimizado.objects.filter(precisa_revisao=True).count()
            
            # Scores médios
            scores = ServicoOtimizado.objects.aggregate(
                score_medio_original=models.Avg('score_qualidade_original'),
                score_medio_otimizado=models.Avg('score_qualidade_otimizado')
            )
            
            # Contadores por tipo de processo
            contadores_processo = ServicoOtimizado.objects.values('tipo_processo').annotate(
                count=models.Count('id')
            ).order_by('tipo_processo')
            
            # Criar/atualizar estatísticas
            hoje = timezone.now().date()
            estatisticas, created = EstatisticasBaseOtimizada.objects.update_or_create(
                data_referencia=hoje,
                defaults={
                    'total_servicos_sinapse': total_sinapse,
                    'total_servicos_otimizados': total_otimizados,
                    'total_validados_humano': total_validados,
                    'total_precisam_revisao': total_precisam_revisao,
                    'score_medio_original': scores['score_medio_original'],
                    'score_medio_otimizado': scores['score_medio_otimizado'],
                    'melhoria_media': (
                        scores['score_medio_otimizado'] - scores['score_medio_original']
                        if scores['score_medio_original'] else 0
                    ),
                    'tempo_processamento': timezone.now() - inicio,
                }
            )
            
            # Atualizar contadores por tipo
            for item in contadores_processo:
                tipo = item['tipo_processo']
                count = item['count']
                if tipo == 'ADMINISTRATIVO':
                    estatisticas.processos_administrativo = count
                elif tipo == 'OPERACIONAL':
                    estatisticas.processos_operacional = count
                elif tipo == 'EQUIPAMENTOS':
                    estatisticas.processos_equipamentos = count
                elif tipo == 'MISTO':
                    estatisticas.processos_misto = count
                elif tipo == 'TERCEIRIZADO':
                    estatisticas.processos_terceirizado = count
            
            estatisticas.save()
            
        except Exception as e:
            logger.error(f"Erro ao gerar estatísticas: {str(e)}")

    def _mostrar_relatorio_final(self, resultados: Dict[str, Any], inicio: datetime):
        """Mostra relatório consolidado final."""
        
        duracao = timezone.now() - inicio
        
        self.stdout.write("\n" + "="*70)
        self.stdout.write(self.style.SUCCESS("🏆 PROCESSAMENTO COMPLETO - BASE OTIMIZADA"))
        self.stdout.write("="*70)
        
        # Números principais
        self.stdout.write(f"\n📊 RESULTADOS FINAIS:")
        self.stdout.write(f"   Total processados: {resultados['total_processados']}")
        self.stdout.write(f"   Total otimizados: {resultados['total_otimizados']}")
        self.stdout.write(f"   Total aplicados: {resultados['total_aplicados']}")
        
        if resultados['erros'] > 0:
            self.stdout.write(f"   ⚠️  Erros: {resultados['erros']}")
        
        # Taxa de sucesso
        if resultados['total_processados'] > 0:
            taxa_otimizacao = (resultados['total_otimizados'] / resultados['total_processados']) * 100
            taxa_aplicacao = (resultados['total_aplicados'] / resultados['total_processados']) * 100
            self.stdout.write(f"   Taxa de otimização: {taxa_otimizacao:.1f}%")
            self.stdout.write(f"   Taxa de aplicação: {taxa_aplicacao:.1f}%")
        
        # Performance
        self.stdout.write(f"\n⏱️  PERFORMANCE:")
        self.stdout.write(f"   Tempo total: {duracao}")
        if resultados['total_processados'] > 0:
            tempo_por_servico = duracao.total_seconds() / resultados['total_processados']
            self.stdout.write(f"   Tempo médio por serviço: {tempo_por_servico:.2f}s")
        
        # Estado da base
        self.stdout.write(f"\n📈 ESTADO DA BASE OTIMIZADA:")
        total_sinapse = self._contar_servicos_sinapse()
        total_otimizados = ServicoOtimizado.objects.count()
        percentual = (total_otimizados / total_sinapse) * 100 if total_sinapse > 0 else 0
        
        self.stdout.write(f"   Serviços Sinapse: {total_sinapse}")
        self.stdout.write(f"   Serviços otimizados: {total_otimizados}")
        self.stdout.write(f"   Cobertura: {percentual:.1f}%")
        
        # Próximos passos
        if percentual >= 100:
            self.stdout.write(self.style.SUCCESS(f"\n🎉 BASE OTIMIZADA COMPLETA!"))
            self.stdout.write(f"✅ Todos os serviços foram processados com sucesso")
        else:
            restantes = total_sinapse - total_otimizados
            self.stdout.write(self.style.WARNING(f"\n📋 PRÓXIMOS PASSOS:"))
            self.stdout.write(f"   • {restantes} serviços ainda precisam ser processados")
            self.stdout.write(f"   • Execute novamente para completar")
        
        self.stdout.write("\n" + "="*70)