"""
Comando para ativar a base otimizada em produção no SGDL.

Substitui o sistema de triagem original pela base otimizada,
com configurações e monitoramento adequados para ambiente de produção.
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import models

from core.services.triagem_otimizada_service import TriagemOtimizadaService
from core.models_carta_otimizada import ServicoOtimizado, EstatisticasBaseOtimizada

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """
    Ativa a base otimizada de serviços em produção.
    
    Executa verificações de qualidade e ativa o switch para usar
    a base otimizada ao invés do Sinapse nas buscas do copiloto.
    
    Exemplos:
    python manage.py ativar_base_otimizada_producao --verificar
    python manage.py ativar_base_otimizada_producao --ativar
    python manage.py ativar_base_otimizada_producao --desativar
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--verificar',
            action='store_true',
            help='Apenas verificar qualidade, não ativar'
        )
        parser.add_argument(
            '--ativar',
            action='store_true',
            help='Ativar base otimizada em produção'
        )
        parser.add_argument(
            '--desativar',
            action='store_true',
            help='Desativar e voltar ao Sinapse original'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forçar ativação mesmo se critérios não atendidos'
        )

    def handle(self, *args, **options):
        
        if options.get('verificar'):
            self._verificar_qualidade()
        elif options.get('ativar'):
            self._ativar_base_otimizada(options.get('force', False))
        elif options.get('desativar'):
            self._desativar_base_otimizada()
        else:
            self._status_atual()

    def _verificar_qualidade(self):
        """Verifica critérios de qualidade para ativação."""
        
        self.stdout.write(
            self.style.SUCCESS("🔍 Verificando critérios de qualidade...")
        )
        
        # Estatísticas básicas
        total_servicos = ServicoOtimizado.objects.count()
        com_embedding = ServicoOtimizado.objects.exclude(embedding_otimizado__isnull=True).count()
        score_medio = ServicoOtimizado.objects.aggregate(
            avg_score=models.Avg('score_qualidade_otimizado')
        )['avg_score'] or 0
        
        # Critérios de qualidade
        criterios = {
            'cobertura_minima': {
                'valor': (com_embedding / total_servicos * 100) if total_servicos > 0 else 0,
                'meta': 90.0,
                'nome': 'Cobertura de embeddings'
            },
            'score_medio': {
                'valor': score_medio,
                'meta': 6.0,
                'nome': 'Score médio de qualidade'
            },
            'total_servicos': {
                'valor': total_servicos,
                'meta': 500,
                'nome': 'Total de serviços otimizados'
            }
        }
        
        self.stdout.write(f"\n📊 CRITÉRIOS DE QUALIDADE:")
        
        todos_atendidos = True
        for criterio, dados in criterios.items():
            valor = dados['valor']
            meta = dados['meta']
            nome = dados['nome']
            atendido = valor >= meta
            
            if not atendido:
                todos_atendidos = False
            
            icon = "✅" if atendido else "❌"
            self.stdout.write(f"   {icon} {nome}: {valor:.1f} (meta: {meta:.1f})")
        
        # Casos de teste críticos
        self.stdout.write(f"\n🧪 CASOS CRÍTICOS:")
        casos_criticos = self._testar_casos_criticos()
        
        casos_ok = sum(1 for caso in casos_criticos if caso['passou'])
        total_casos = len(casos_criticos)
        
        for caso in casos_criticos:
            icon = "✅" if caso['passou'] else "❌"
            self.stdout.write(f"   {icon} {caso['nome']}: {caso['resultado']}")
        
        # Recomendação final
        self.stdout.write(f"\n🎯 AVALIAÇÃO FINAL:")
        
        if todos_atendidos and casos_ok >= (total_casos * 0.8):
            self.stdout.write(
                self.style.SUCCESS("   ✅ PRONTO PARA PRODUÇÃO - Todos os critérios atendidos")
            )
            return True
        elif casos_ok >= (total_casos * 0.6):
            self.stdout.write(
                self.style.WARNING("   🟡 ACEITÁVEL - Maioria dos critérios atendidos, recomenda-se mais testes")
            )
            return False
        else:
            self.stdout.write(
                self.style.ERROR("   ❌ NÃO RECOMENDADO - Muitos critérios não atendidos")
            )
            return False

    def _testar_casos_criticos(self):
        """Testa casos críticos específicos."""
        
        try:
            triagem = TriagemOtimizadaService()
            from core.services.vector_service import VectorService
            vector_svc = VectorService()
            
            casos_teste = [
                {
                    'nome': 'Buraco na rua → Tapa Buraco',
                    'consulta': 'buraco na rua precisa tapar',
                    'servico_esperado': 80,
                    'posicao_max': 1
                },
                {
                    'nome': 'Iluminação → Serviço correto',
                    'consulta': 'poste de luz piscando',
                    'servico_esperado': 14,
                    'posicao_max': 3
                },
                {
                    'nome': 'Receita de bolo → NÃO animais',
                    'consulta': 'receita de bolo',
                    'servico_nao_esperado': 323,
                    'posicao_max': 5
                }
            ]
            
            resultados = []
            
            for caso in casos_teste:
                try:
                    embedding = vector_svc.generate_embedding(caso['consulta'])
                    if not embedding:
                        resultados.append({
                            'nome': caso['nome'],
                            'passou': False,
                            'resultado': 'Erro ao gerar embedding'
                        })
                        continue
                    
                    resultados_busca = triagem.buscar_servico_sinapse(
                        embedding, 5, caso['consulta']
                    )
                    
                    if 'servico_esperado' in caso:
                        # Verificar se serviço correto está na posição esperada
                        servico_esperado = caso['servico_esperado']
                        posicao_max = caso['posicao_max']
                        
                        posicao_encontrada = None
                        for i, item in enumerate(resultados_busca[:posicao_max], 1):
                            if item.get('servico_id') == servico_esperado:
                                posicao_encontrada = i
                                break
                        
                        if posicao_encontrada:
                            resultados.append({
                                'nome': caso['nome'],
                                'passou': True,
                                'resultado': f'Encontrado na posição {posicao_encontrada}'
                            })
                        else:
                            resultados.append({
                                'nome': caso['nome'],
                                'passou': False,
                                'resultado': 'Serviço esperado não encontrado nas primeiras posições'
                            })
                    
                    elif 'servico_nao_esperado' in caso:
                        # Verificar se serviço incorreto NÃO está nas primeiras posições
                        servico_nao_esperado = caso['servico_nao_esperado']
                        posicao_max = caso['posicao_max']
                        
                        encontrou_incorreto = any(
                            item.get('servico_id') == servico_nao_esperado 
                            for item in resultados_busca[:posicao_max]
                        )
                        
                        if not encontrou_incorreto:
                            resultados.append({
                                'nome': caso['nome'],
                                'passou': True,
                                'resultado': 'Serviço incorreto não aparece nas primeiras posições'
                            })
                        else:
                            resultados.append({
                                'nome': caso['nome'],
                                'passou': False,
                                'resultado': 'Serviço incorreto ainda aparece inadequadamente'
                            })
                
                except Exception as e:
                    resultados.append({
                        'nome': caso['nome'],
                        'passou': False,
                        'resultado': f'Erro no teste: {str(e)}'
                    })
            
            return resultados
            
        except Exception as e:
            return [{
                'nome': 'Erro geral nos testes',
                'passou': False,
                'resultado': f'Erro: {str(e)}'
            }]

    def _ativar_base_otimizada(self, force: bool = False):
        """Ativa a base otimizada em produção."""
        
        self.stdout.write(
            self.style.SUCCESS("🚀 Ativando base otimizada em produção...")
        )
        
        # Verificar qualidade se não for force
        if not force:
            qualidade_ok = self._verificar_qualidade()
            if not qualidade_ok:
                self.stdout.write(
                    self.style.ERROR("❌ Qualidade insuficiente. Use --force para ativar mesmo assim.")
                )
                return
        
        # Ativar via variável de ambiente (requer restart)
        self.stdout.write(f"\n⚙️  INSTRUÇÕES PARA ATIVAÇÃO:")
        self.stdout.write(f"   1. Definir variável: USAR_BASE_SERVICOS_OTIMIZADA=True")
        self.stdout.write(f"   2. Reiniciar aplicação Django")
        self.stdout.write(f"   3. Verificar logs para confirmação")
        
        # Status atual
        usando_otimizada = getattr(settings, 'USAR_BASE_SERVICOS_OTIMIZADA', False)
        
        if usando_otimizada:
            self.stdout.write(
                self.style.SUCCESS(f"\n✅ Base otimizada JÁ está ATIVA na configuração atual")
            )
        else:
            self.stdout.write(
                self.style.WARNING(f"\n🟡 Base otimizada ainda NÃO está ativa - configure a variável")
            )

    def _desativar_base_otimizada(self):
        """Desativa a base otimizada, voltando ao Sinapse."""
        
        self.stdout.write(
            self.style.WARNING("⏸️  Desativando base otimizada...")
        )
        
        self.stdout.write(f"\n⚙️  INSTRUÇÕES PARA DESATIVAÇÃO:")
        self.stdout.write(f"   1. Definir variável: USAR_BASE_SERVICOS_OTIMIZADA=False")
        self.stdout.write(f"   2. Reiniciar aplicação Django")
        self.stdout.write(f"   3. Sistema voltará a usar Sinapse original")
        
        usando_otimizada = getattr(settings, 'USAR_BASE_SERVICOS_OTIMIZADA', False)
        
        if not usando_otimizada:
            self.stdout.write(
                self.style.SUCCESS(f"\n✅ Sistema JÁ está usando Sinapse original")
            )
        else:
            self.stdout.write(
                self.style.WARNING(f"\n🟡 Base otimizada ainda ATIVA - configure a variável")
            )

    def _status_atual(self):
        """Exibe status atual da integração."""
        
        self.stdout.write(
            self.style.SUCCESS("📊 Status da integração da base otimizada")
        )
        
        # Configuração atual
        usando_otimizada = getattr(settings, 'USAR_BASE_SERVICOS_OTIMIZADA', False)
        fallback_enabled = getattr(settings, 'BASE_OTIMIZADA_FALLBACK_ENABLED', True)
        
        self.stdout.write(f"\n⚙️  CONFIGURAÇÃO:")
        self.stdout.write(f"   Base otimizada ativa: {'✅ SIM' if usando_otimizada else '❌ NÃO'}")
        self.stdout.write(f"   Fallback habilitado: {'✅ SIM' if fallback_enabled else '❌ NÃO'}")
        
        # Estatísticas da base
        try:
            triagem = TriagemOtimizadaService()
            stats = triagem.estatisticas_base_otimizada()
            
            self.stdout.write(f"\n📈 ESTATÍSTICAS DA BASE:")
            self.stdout.write(f"   Total de serviços: {stats.get('total_servicos', 0)}")
            self.stdout.write(f"   Serviços ativos: {stats.get('servicos_ativos', 0)}")
            self.stdout.write(f"   Com embedding: {stats.get('com_embedding', 0)} ({stats.get('cobertura_embedding', 0)}%)")
            self.stdout.write(f"   Score médio: {stats.get('score_medio', 0)}")
            
        except Exception as e:
            self.stdout.write(f"   ⚠️ Erro ao obter estatísticas: {str(e)}")
        
        # Recomendações
        self.stdout.write(f"\n💡 COMANDOS DISPONÍVEIS:")
        self.stdout.write(f"   Verificar qualidade: --verificar")
        self.stdout.write(f"   Ativar em produção: --ativar")
        self.stdout.write(f"   Desativar: --desativar")