# /var/www/sgdl/backend/core/management/commands/otimizar_carta_servicos.py

"""
Comando Django para otimização prática da carta de serviços.
Implementa melhorias baseadas nos problemas identificados na análise anterior.
"""

import json
import logging
from typing import Dict, Any, List
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.services import CartaOptimizerService
from core.services.embedding_service import EmbeddingOptimizationService
from integrations.models_sinapse import CatalogServico

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """
    Otimiza a carta de serviços com melhorias práticas:
    - Limpeza de HTML residual
    - Estruturação de texto RAG (PROBLEMA/SOLUÇÃO/CONTEXTO)
    - Extração de prazos estruturados
    - Enriquecimento com palavras-chave e sinônimos
    - Geração de metadados ricos
    
    Exemplos:
    python manage.py otimizar_carta_servicos --preview --limite 10
    python manage.py otimizar_carta_servicos --aplicar --score-minimo 7
    python manage.py otimizar_carta_servicos --problematicos --limite 20 --aplicar
    """

    def add_arguments(self, parser):
        # Modo de operação
        parser.add_argument(
            '--preview',
            action='store_true',
            help='Modo preview: mostra otimizações sem aplicar',
        )
        parser.add_argument(
            '--aplicar',
            action='store_true',
            help='Aplica as otimizações no banco de dados',
        )
        
        # Filtros de seleção
        parser.add_argument(
            '--limite',
            type=int,
            default=10,
            help='Número máximo de serviços a processar',
        )
        parser.add_argument(
            '--servico-id',
            type=int,
            help='ID específico de serviço para otimizar',
        )
        parser.add_argument(
            '--problematicos',
            action='store_true',
            help='Foca nos serviços com mais problemas identificados',
        )
        parser.add_argument(
            '--orgao-id',
            type=int,
            help='Filtrar por ID do órgão específico',
        )
        parser.add_argument(
            '--categoria-id',
            type=int,
            help='Filtrar por ID da categoria específica',
        )
        
        # Critérios de qualidade
        parser.add_argument(
            '--score-minimo',
            type=int,
            default=6,
            help='Score mínimo para aplicar otimizações (1-10)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Força aplicação mesmo com score baixo',
        )
        
        # Saída e relatórios
        parser.add_argument(
            '--exportar',
            type=str,
            help='Arquivo JSON para exportar relatório detalhado',
        )
        parser.add_argument(
            '--validar',
            action='store_true',
            help='Executa validação de qualidade após otimizações',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Saída detalhada do processamento',
        )

    def handle(self, *args, **options):
        self.verbosity = options.get('verbosity', 1)
        self.verbose = options.get('verbose', False)
        
        # Validar argumentos
        if not options['preview'] and not options['aplicar']:
            raise CommandError("Especifique --preview ou --aplicar")
        
        if options['aplicar'] and options['preview']:
            raise CommandError("--preview e --aplicar são mutuamente exclusivos")
        
        # Inicializar serviços
        self.optimizer_service = EmbeddingOptimizationService()
        
        try:
            # Selecionar serviços para processar
            servicos_ids = self._selecionar_servicos(options)
            
            if not servicos_ids:
                self.stdout.write(
                    self.style.WARNING("Nenhum serviço encontrado com os critérios especificados")
                )
                return
            
            self.stdout.write(
                f"🔧 Processando {len(servicos_ids)} serviços em modo "
                f"{'APLICAR' if options['aplicar'] else 'PREVIEW'}"
            )
            
            # Processar lote de serviços
            resultado_lote = self._processar_lote(servicos_ids, options)
            
            # Mostrar relatório
            self._mostrar_relatorio(resultado_lote, options)
            
            # Executar validação se solicitado
            if options['validar'] and options['aplicar']:
                self._validar_otimizacoes(servicos_ids, options)
            
            # Exportar relatório se solicitado
            if options['exportar']:
                self._exportar_relatorio(resultado_lote, options['exportar'])
            
        except Exception as e:
            logger.exception("Erro durante otimização da carta")
            raise CommandError(f"Erro durante processamento: {e}")

    def _selecionar_servicos(self, options: Dict[str, Any]) -> List[int]:
        """Seleciona IDs dos serviços a serem processados."""
        
        # Serviço específico
        if options['servico_id']:
            return [options['servico_id']]
        
        # Serviços problemáticos identificados automaticamente
        if options['problematicos']:
            if self.verbose:
                self.stdout.write("🔍 Identificando serviços problemáticos...")
            
            ids_problematicos = self.optimizer_service.buscar_servicos_problematicos(
                limite=options['limite']
            )
            
            if self.verbose:
                self.stdout.write(f"   Encontrados {len(ids_problematicos)} serviços com problemas")
            
            return ids_problematicos
        
        # Filtros manuais
        queryset = CatalogServico.objects.using('sinapse').filter(status=1)
        
        if options['orgao_id']:
            queryset = queryset.filter(id_orgao=options['orgao_id'])
        
        if options['categoria_id']:
            queryset = queryset.filter(id_categoria=options['categoria_id'])
        
        # Ordenar por updated_at para pegar os mais recentes primeiro
        ids = list(queryset.order_by('-updated_at').values_list('id', flat=True)[:options['limite']])
        
        if self.verbose:
            self.stdout.write(f"🎯 Selecionados {len(ids)} serviços pelos filtros especificados")
        
        return ids

    def _processar_lote(self, servicos_ids: List[int], options: Dict[str, Any]) -> Dict[str, Any]:
        """Processa um lote de serviços."""
        
        aplicar_automaticamente = options['aplicar'] and not options['force']
        score_minimo = options['score_minimo'] if not options['force'] else 1
        
        if self.verbose:
            self.stdout.write(
                f"⚙️  Configuração: aplicar={aplicar_automaticamente}, "
                f"score_mínimo={score_minimo}, força={options['force']}"
            )
        
        return self.optimizer_service.otimizar_lote_servicos(
            servico_ids=servicos_ids,
            aplicar_automaticamente=aplicar_automaticamente,
            score_minimo=score_minimo
        )

    def _mostrar_relatorio(self, resultado_lote: Dict[str, Any], options: Dict[str, Any]):
        """Mostra relatório consolidado na saída."""
        
        resumo = resultado_lote['resumo']
        resultados = resultado_lote['resultados_individuais']
        
        # Cabeçalho do relatório
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS("📊 RELATÓRIO DE OTIMIZAÇÃO DA CARTA"))
        self.stdout.write("="*60)
        
        # Estatísticas gerais
        self.stdout.write(f"\n📈 ESTATÍSTICAS GERAIS:")
        self.stdout.write(f"   Total processados: {resumo['total_processados']}")
        self.stdout.write(f"   Total otimizados: {resumo['total_otimizados']}")
        self.stdout.write(f"   Total aplicados: {resumo['total_aplicados']}")
        
        if resumo['score_medio_antes'] > 0:
            melhoria = resumo['score_medio_depois'] - resumo['score_medio_antes']
            self.stdout.write(f"   Score médio antes: {resumo['score_medio_antes']:.1f}")
            self.stdout.write(f"   Score médio depois: {resumo['score_medio_depois']:.1f}")
            self.stdout.write(
                f"   Melhoria média: {melhoria:+.1f} pontos"
            )
        
        # Problemas mais comuns
        if resumo['problemas_mais_comuns']:
            self.stdout.write(f"\n🚨 PROBLEMAS MAIS COMUNS:")
            for problema, count in resumo['problemas_mais_comuns']:
                self.stdout.write(f"   • {problema}: {count} ocorrências")
        
        # Melhorias mais frequentes
        if resumo['melhorias_mais_frequentes']:
            self.stdout.write(f"\n✅ MELHORIAS MAIS APLICADAS:")
            for melhoria, count in resumo['melhorias_mais_frequentes']:
                self.stdout.write(f"   • {melhoria}: {count} aplicações")
        
        # Detalhes individuais (se verbose ou poucos serviços)
        if self.verbose or len(resultados) <= 5:
            self.stdout.write(f"\n📋 DETALHES POR SERVIÇO:")
            
            for resultado in resultados[:10]:  # Máximo 10 detalhes
                if 'erro' in resultado:
                    self.stdout.write(
                        f"\n❌ Serviço {resultado['servico_id']}: {resultado['erro']}"
                    )
                    continue
                
                score_antes = resultado['score_qualidade_anterior']
                score_depois = resultado['score_qualidade_novo']
                delta = score_depois - score_antes
                
                aplicado = resultado.get('alteracoes_aplicadas', False)
                status_icon = "✅" if aplicado else "👁️ "
                
                self.stdout.write(
                    f"\n{status_icon} Serviço {resultado['servico_id']}: {resultado['titulo'][:50]}..."
                )
                self.stdout.write(
                    f"   Score: {score_antes} → {score_depois} ({delta:+.0f})"
                )
                
                if resultado['problemas_encontrados']:
                    self.stdout.write(
                        f"   Problemas: {', '.join(resultado['problemas_encontrados'])}"
                    )
                
                if resultado['melhorias_aplicadas']:
                    self.stdout.write(
                        f"   Melhorias: {', '.join(resultado['melhorias_aplicadas'])}"
                    )
        
        # Resumo final
        modo = "PREVIEW" if not options['aplicar'] else "APLICAÇÃO"
        self.stdout.write(f"\n🎯 RESUMO {modo}:")
        
        if options['aplicar']:
            if resumo['total_aplicados'] > 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"   ✅ {resumo['total_aplicados']} serviços otimizados com sucesso!"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        "   ⚠️  Nenhum serviço foi otimizado (scores insuficientes)"
                    )
                )
        else:
            otimizaveis = sum(1 for r in resultados 
                            if r.get('recomenda_aplicar', False) and 'erro' not in r)
            self.stdout.write(
                f"   👀 {otimizaveis} serviços recomendados para otimização"
            )
            if otimizaveis > 0:
                self.stdout.write(
                    "   💡 Execute com --aplicar para implementar as melhorias"
                )

    def _validar_otimizacoes(self, servicos_ids: List[int], options: Dict[str, Any]):
        """Executa validação de qualidade das otimizações aplicadas."""
        
        self.stdout.write("\n🔍 VALIDANDO QUALIDADE DAS OTIMIZAÇÕES...")
        
        # Queries de teste baseadas nos casos problemáticos identificados
        queries_teste = [
            "receita de bolo",
            "recolhimento de animais",
            "licença para empresa", 
            "certidão de tempo de serviço",
            "alvará de funcionamento",
            "segunda via documento",
            "vistoria técnica",
            "cadastro municipal"
        ]
        
        resultados_validacao = []
        
        # Validar alguns serviços otimizados (máximo 5)
        for servico_id in servicos_ids[:5]:
            try:
                resultado_validacao = self.optimizer_service.validar_melhoria_embedding(
                    servico_id, queries_teste
                )
                
                if 'erro' not in resultado_validacao:
                    resultados_validacao.append(resultado_validacao)
                    
                    if self.verbose:
                        self.stdout.write(f"\n📊 Validação Serviço {servico_id}:")
                        self.stdout.write(f"   {resultado_validacao['titulo'][:60]}...")
                        
                        if resultado_validacao['separacao_adequada']:
                            self.stdout.write("   ✅ Separação adequada entre relevantes/irrelevantes")
                        else:
                            self.stdout.write("   ⚠️  Separação inadequada entre relevantes/irrelevantes")
                        
                        self.stdout.write(
                            f"   Score médio relevantes: {resultado_validacao['media_score_relevantes']:.3f}"
                        )
                        self.stdout.write(
                            f"   Score médio irrelevantes: {resultado_validacao['media_score_irrelevantes']:.3f}"
                        )
                
            except Exception as e:
                logger.error(f"Erro na validação do serviço {servico_id}: {e}")
        
        # Resumo da validação
        if resultados_validacao:
            separacoes_adequadas = sum(1 for r in resultados_validacao if r['separacao_adequada'])
            
            self.stdout.write(f"\n✅ RESULTADO DA VALIDAÇÃO:")
            self.stdout.write(f"   Serviços validados: {len(resultados_validacao)}")
            self.stdout.write(f"   Separação adequada: {separacoes_adequadas}/{len(resultados_validacao)}")
            
            if separacoes_adequadas / len(resultados_validacao) >= 0.7:
                self.stdout.write(
                    self.style.SUCCESS("   🎯 Qualidade das otimizações: BOA")
                )
            else:
                self.stdout.write(
                    self.style.WARNING("   ⚠️  Qualidade das otimizações: REQUER AJUSTES")
                )

    def _exportar_relatorio(self, resultado_lote: Dict[str, Any], arquivo_exportacao: str):
        """Exporta relatório detalhado para arquivo JSON."""
        
        relatorio_completo = {
            'metadata': {
                'timestamp': timezone.now().isoformat(),
                'comando': 'otimizar_carta_servicos',
                'versao': '1.0',
            },
            'configuracao': {
                'limite_processamento': len(resultado_lote['resultados_individuais']),
                'modo_aplicacao': any(r.get('alteracoes_aplicadas', False) 
                                   for r in resultado_lote['resultados_individuais']),
            },
            'resumo_executivo': resultado_lote['resumo'],
            'resultados_detalhados': resultado_lote['resultados_individuais']
        }
        
        try:
            with open(arquivo_exportacao, 'w', encoding='utf-8') as f:
                json.dump(relatorio_completo, f, indent=2, ensure_ascii=False)
            
            self.stdout.write(
                self.style.SUCCESS(f"\n💾 Relatório exportado para: {arquivo_exportacao}")
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"\n❌ Erro ao exportar relatório: {e}")
            )