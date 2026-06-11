"""
Comando para testar a integração da base otimizada no sistema de triagem.

Testa casos específicos que antes falhavam e valida melhorias na busca semântica.
"""

import logging
from typing import List, Dict, Any
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from core.services.triagem_service import TriagemService
from core.services.triagem_otimizada_service import TriagemOtimizadaService, AdapterTriagemOtimizada
from core.services.vector_service import VectorService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """
    Testa integração da base otimizada no sistema de triagem.
    
    Compara resultados entre triagem original (Sinapse) e otimizada,
    validando melhorias em casos que antes falhavam.
    
    Exemplos:
    python manage.py testar_triagem_otimizada
    python manage.py testar_triagem_otimizada --casos-criticos
    python manage.py testar_triagem_otimizada --consulta "buraco na rua"
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--casos-criticos',
            action='store_true',
            help='Testar apenas casos que antes falhavam'
        )
        parser.add_argument(
            '--consulta',
            type=str,
            help='Testar consulta específica'
        )
        parser.add_argument(
            '--top-k',
            type=int,
            default=5,
            help='Número de resultados a comparar (default: 5)'
        )
        parser.add_argument(
            '--detalhado',
            action='store_true',
            help='Saída mais detalhada com scores e comparações'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS("🔍 Testando integração da triagem otimizada...")
        )
        
        try:
            # Configurar serviços
            self._configurar_servicos()
            
            # Determinar casos de teste
            casos_teste = self._definir_casos_teste(options)
            
            if not casos_teste:
                self.stdout.write(
                    self.style.WARNING("❌ Nenhum caso de teste definido")
                )
                return
            
            self.stdout.write(f"🎯 Testando {len(casos_teste)} casos...")
            
            # Executar testes comparativos
            resultados = self._executar_testes_comparativos(casos_teste, options)
            
            # Exibir relatório
            self._exibir_relatorio_comparativo(resultados, options)
            
            # Estatísticas da base otimizada
            self._exibir_estatisticas_base()
            
        except Exception as e:
            raise CommandError(f"Erro nos testes: {str(e)}")

    def _configurar_servicos(self):
        """Configura os serviços de triagem."""
        self.triagem_original = TriagemService()
        self.triagem_otimizada = TriagemOtimizadaService()
        self.triagem_adapter = AdapterTriagemOtimizada(usar_base_otimizada=True)
        self.vector_service = VectorService()
        
        self.stdout.write("✅ Serviços configurados")

    def _definir_casos_teste(self, options: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Define casos de teste baseado nas opções."""
        
        if options.get('consulta'):
            # Caso único fornecido pelo usuário
            return [{
                'nome': 'Consulta específica',
                'texto': options['consulta'],
                'esperado': 'Definido pelo usuário'
            }]
        
        # Casos críticos identificados anteriormente
        casos_criticos = [
            {
                'nome': 'Receita de bolo (antes → recolhimento animais)',
                'texto': 'receita de bolo',
                'esperado': 'NÃO deve retornar recolhimento de animais',
                'problema_anterior': 'Serviço 323 aparecia incorretamente'
            },
            {
                'nome': 'Buraco na rua',
                'texto': 'buraco na rua precisa tapar',
                'esperado': 'Deve retornar serviço de tapa-buraco',
                'servico_correto': 80
            },
            {
                'nome': 'Iluminação pública',
                'texto': 'poste de luz piscando apagando',
                'esperado': 'Deve retornar serviço de iluminação',
                'servico_correto': 14
            },
            {
                'nome': 'Licença de funcionamento',
                'texto': 'preciso abrir minha empresa licença funcionamento',
                'esperado': 'Deve retornar licenciamento empresarial'
            },
            {
                'nome': 'IPTU',
                'texto': 'imposto predial IPTU segunda via',
                'esperado': 'Deve retornar serviços de IPTU'
            },
            {
                'nome': 'Alvará taxista',
                'texto': 'alvará para taxistas renovação',
                'esperado': 'Táxi: Renovação de Alvará',
                'servico_correto': 249,
            },
            {
                'nome': 'Proibido estacionar e pintura de guia',
                'texto': 'proibido estacionar e pintura de guia na rua',
                'esperado': 'Trânsito: Implantação ou Alteração de Sinalização',
                'servico_correto': 133,
            },
            {
                'nome': 'Rondas escolares Mogilar',
                'texto': 'rondas escolares intensificação bairro Mogilar instituições de ensino',
                'esperado': 'Ronda nas Praças e Patrimônios Públicos',
                'servico_correto': 143,
            },
            {
                'nome': 'Proteção ao consumidor',
                'texto': 'proteção ao consumidor atendimento solicitação',
                'esperado': 'PROCON: Atendimento ao Consumidor (ONLINE)',
                'servico_correto': 978,
            },
        ]
        
        # Casos gerais para comparação
        casos_gerais = [
            {
                'nome': 'Cadastro saúde da família',
                'texto': 'cadastro programa saúde da família',
                'esperado': 'Serviços de saúde'
            },
            {
                'nome': 'Vistoria sanitária',
                'texto': 'vistoria sanitária estabelecimento',
                'esperado': 'Serviços de vigilância sanitária'
            },
            {
                'nome': 'Certidão negativa',
                'texto': 'certidão negativa débitos municipais',
                'esperado': 'Certidões municipais'
            }
        ]
        
        if options.get('casos_criticos'):
            return casos_criticos
        
        return casos_criticos + casos_gerais[:3]  # Misturar críticos + alguns gerais

    def _executar_testes_comparativos(
        self, 
        casos_teste: List[Dict[str, Any]], 
        options: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Executa testes comparativos entre triagem original e otimizada."""
        
        top_k = options.get('top_k', 5)
        detalhado = options.get('detalhado', False)
        resultados = []
        
        for i, caso in enumerate(casos_teste, 1):
            self.stdout.write(f"\n🧪 Caso {i}/{len(casos_teste)}: {caso['nome']}")
            
            try:
                # Gerar embedding da consulta
                embedding = self.vector_service.generate_embedding(caso['texto'])
                
                if not embedding:
                    self.stdout.write(
                        self.style.WARNING(f"   ⚠️  Não foi possível gerar embedding")
                    )
                    continue
                
                # Busca com triagem original
                resultados_original = self.triagem_original.buscar_servico_sinapse(
                    embedding, top_k, caso['texto']
                )
                
                # Busca com triagem otimizada
                resultados_otimizada = self.triagem_otimizada.buscar_servico_sinapse(
                    embedding, top_k, caso['texto']
                )
                
                # Análise dos resultados
                analise = self._analisar_resultados_caso(
                    caso, resultados_original, resultados_otimizada
                )
                
                resultados.append({
                    'caso': caso,
                    'resultados_original': resultados_original,
                    'resultados_otimizada': resultados_otimizada,
                    'analise': analise
                })
                
                # Mostrar resultados se detalhado
                if detalhado:
                    self._mostrar_detalhes_caso(caso, resultados_original, resultados_otimizada, analise)
                else:
                    self._mostrar_resumo_caso(analise)
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"   ❌ Erro no caso: {str(e)}")
                )
                logger.error(f"Erro no teste {caso['nome']}: {str(e)}")
        
        return resultados

    def _analisar_resultados_caso(
        self,
        caso: Dict[str, Any],
        original: List[Dict],
        otimizada: List[Dict]
    ) -> Dict[str, Any]:
        """Analisa e compara resultados de um caso específico."""
        
        analise = {
            'melhoria_detectada': False,
            'score_melhor_original': 0.0,
            'score_melhor_otimizada': 0.0,
            'servico_correto_encontrado': False,
            'posicao_correto_original': None,
            'posicao_correto_otimizada': None,
            'problemas_resolvidos': []
        }
        
        # Scores dos melhores resultados
        if original:
            analise['score_melhor_original'] = original[0].get('score', 0)
        if otimizada:
            analise['score_melhor_otimizada'] = otimizada[0].get('score', 0)
        
        # Verificar se houve melhoria geral
        analise['melhoria_detectada'] = (
            analise['score_melhor_otimizada'] > analise['score_melhor_original']
        )
        
        # Verificar se serviço correto foi encontrado (se especificado)
        servico_correto = caso.get('servico_correto')
        if servico_correto:
            # Procurar nas listas
            for i, item in enumerate(original):
                if item.get('servico_id') == servico_correto:
                    analise['posicao_correto_original'] = i + 1
                    break
            
            for i, item in enumerate(otimizada):
                if item.get('servico_id') == servico_correto:
                    analise['posicao_correto_otimizada'] = i + 1
                    analise['servico_correto_encontrado'] = True
                    break
        
        # Verificar problemas específicos resolvidos
        problema_anterior = caso.get('problema_anterior', '')
        if 'recolhimento animais' in problema_anterior.lower():
            # Verificar se serviço 323 ainda aparece inadequadamente
            aparece_original = any(r.get('servico_id') == 323 for r in original)
            aparece_otimizada = any(r.get('servico_id') == 323 for r in otimizada)
            
            if aparece_original and not aparece_otimizada:
                analise['problemas_resolvidos'].append('Serviço 323 não aparece mais inadequadamente')
        
        return analise

    def _mostrar_resumo_caso(self, analise: Dict[str, Any]):
        """Mostra resumo rápido de um caso."""
        
        if analise['melhoria_detectada']:
            icon = "✅"
            status = f"MELHORIA (score {analise['score_melhor_original']:.3f} → {analise['score_melhor_otimizada']:.3f})"
        else:
            icon = "🟡"
            status = f"SIMILAR (scores {analise['score_melhor_original']:.3f} vs {analise['score_melhor_otimizada']:.3f})"
        
        if analise['servico_correto_encontrado']:
            status += f" - Correto encontrado (pos {analise['posicao_correto_otimizada']})"
        
        if analise['problemas_resolvidos']:
            status += f" - {len(analise['problemas_resolvidos'])} problemas resolvidos"
        
        self.stdout.write(f"   {icon} {status}")

    def _mostrar_detalhes_caso(
        self,
        caso: Dict[str, Any],
        original: List[Dict],
        otimizada: List[Dict],
        analise: Dict[str, Any]
    ):
        """Mostra detalhes completos de um caso."""
        
        self.stdout.write(f"   📝 Consulta: '{caso['texto']}'")
        self.stdout.write(f"   🎯 Esperado: {caso['esperado']}")
        
        self.stdout.write(f"\n   📊 ORIGINAL (Sinapse):")
        for i, item in enumerate(original[:3], 1):
            self.stdout.write(
                f"     {i}. [{item.get('servico_id')}] {item.get('titulo', 'N/A')[:60]}... "
                f"(score: {item.get('score', 0):.3f})"
            )
        
        self.stdout.write(f"\n   🚀 OTIMIZADA (Base Local):")
        for i, item in enumerate(otimizada[:3], 1):
            fonte = item.get('fonte', 'N/A')
            qualidade = item.get('score_qualidade', 'N/A')
            self.stdout.write(
                f"     {i}. [{item.get('servico_id')}] {item.get('titulo', 'N/A')[:60]}... "
                f"(score: {item.get('score', 0):.3f}, Q: {qualidade}, fonte: {fonte})"
            )
        
        if analise['problemas_resolvidos']:
            self.stdout.write(f"\n   ✅ Problemas resolvidos:")
            for problema in analise['problemas_resolvidos']:
                self.stdout.write(f"     • {problema}")

    def _exibir_relatorio_comparativo(
        self, 
        resultados: List[Dict[str, Any]], 
        options: Dict[str, Any]
    ):
        """Exibe relatório consolidado dos testes."""
        
        if not resultados:
            return
        
        self.stdout.write(f"\n" + "="*70)
        self.stdout.write(self.style.SUCCESS("📊 RELATÓRIO COMPARATIVO - TRIAGEM OTIMIZADA"))
        self.stdout.write("="*70)
        
        # Estatísticas gerais
        total_casos = len(resultados)
        melhorias = sum(1 for r in resultados if r['analise']['melhoria_detectada'])
        servicos_corretos = sum(1 for r in resultados if r['analise']['servico_correto_encontrado'])
        problemas_resolvidos = sum(len(r['analise']['problemas_resolvidos']) for r in resultados)
        
        self.stdout.write(f"\n📈 RESULTADOS GERAIS:")
        self.stdout.write(f"   Total de casos testados: {total_casos}")
        self.stdout.write(f"   Casos com melhoria: {melhorias} ({melhorias/total_casos*100:.1f}%)")
        self.stdout.write(f"   Serviços corretos encontrados: {servicos_corretos}")
        self.stdout.write(f"   Problemas específicos resolvidos: {problemas_resolvidos}")
        
        # Análise de scores
        scores_original = [r['analise']['score_melhor_original'] for r in resultados]
        scores_otimizada = [r['analise']['score_melhor_otimizada'] for r in resultados]
        
        if scores_original and scores_otimizada:
            avg_original = sum(scores_original) / len(scores_original)
            avg_otimizada = sum(scores_otimizada) / len(scores_otimizada)
            melhoria_avg = avg_otimizada - avg_original
            
            self.stdout.write(f"\n📊 ANÁLISE DE SCORES:")
            self.stdout.write(f"   Score médio original: {avg_original:.3f}")
            self.stdout.write(f"   Score médio otimizado: {avg_otimizada:.3f}")
            self.stdout.write(f"   Melhoria média: {melhoria_avg:+.3f}")
        
        # Casos de destaque
        casos_destaque = [r for r in resultados if r['analise']['melhoria_detectada'] or r['analise']['problemas_resolvidos']]
        if casos_destaque:
            self.stdout.write(f"\n🌟 CASOS DE DESTAQUE:")
            for r in casos_destaque[:5]:
                nome = r['caso']['nome']
                analise = r['analise']
                melhoria = analise['score_melhor_otimizada'] - analise['score_melhor_original']
                self.stdout.write(f"   • {nome}: melhoria {melhoria:+.3f}")

    def _exibir_estatisticas_base(self):
        """Exibe estatísticas da base otimizada."""
        
        try:
            stats = self.triagem_otimizada.estatisticas_base_otimizada()
            
            self.stdout.write(f"\n📈 ESTATÍSTICAS DA BASE OTIMIZADA:")
            self.stdout.write(f"   Total de serviços: {stats.get('total_servicos', 0)}")
            self.stdout.write(f"   Serviços ativos: {stats.get('servicos_ativos', 0)}")
            self.stdout.write(f"   Com embedding: {stats.get('com_embedding', 0)} ({stats.get('cobertura_embedding', 0)}%)")
            self.stdout.write(f"   Score médio: {stats.get('score_medio', 0)}")
            self.stdout.write(f"   Validados por humano: {stats.get('validados_humano', 0)}")
            
        except Exception as e:
            self.stdout.write(f"   ⚠️ Erro ao obter estatísticas: {str(e)}")
        
        self.stdout.write(f"\n" + "="*70)