"""
Comando para limpeza de entidades HTML nos textos otimizados.
"""

import re
import html
import logging
from django.core.management.base import BaseCommand
from core.models_carta_otimizada import ServicoOtimizado, LogOtimizacao

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Limpa entidades HTML dos textos otimizados e melhora formatação'

    def add_arguments(self, parser):
        parser.add_argument(
            '--servico-id', 
            type=int, 
            help='ID específico do serviço para limpar'
        )
        parser.add_argument(
            '--dry-run', 
            action='store_true', 
            help='Apenas mostrar o que seria alterado'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🧹 Iniciando Limpeza de Entidades HTML...')
        )
        
        # Filtrar serviços
        if options['servico_id']:
            servicos = ServicoOtimizado.objects.filter(id=options['servico_id'])
        else:
            # Apenas serviços que têm problemas de HTML
            servicos = ServicoOtimizado.objects.filter(
                descricao_objetiva__icontains='&'
            ) | ServicoOtimizado.objects.filter(
                texto_rag_otimizado__icontains='&'
            )
            
        total = servicos.count()
        self.stdout.write(f"📊 Encontrados {total} serviços com entidades HTML")
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('🔍 MODO DRY-RUN - Nenhuma alteração será feita'))
        
        sucesso = 0
        for i, servico in enumerate(servicos, 1):
            self.stdout.write(
                f"\n🔄 [{i}/{total}] Processando: {servico.titulo_otimizado[:50]}..."
            )
            
            # Campos a limpar
            campos_alterados = []
            
            # Limpar descrição objetiva
            desc_original = servico.descricao_objetiva or ""
            desc_limpa = self._limpar_entidades_html(desc_original)
            if desc_limpa != desc_original:
                campos_alterados.append('descricao_objetiva')
                self.stdout.write(f"   📝 Descrição: {len(desc_original)} → {len(desc_limpa)} chars")
                if not options['dry_run']:
                    servico.descricao_objetiva = desc_limpa
            
            # Limpar texto RAG
            rag_original = servico.texto_rag_otimizado or ""
            rag_limpo = self._limpar_entidades_html(rag_original)
            if rag_limpo != rag_original:
                campos_alterados.append('texto_rag_otimizado')
                self.stdout.write(f"   📄 Texto RAG: {len(rag_original)} → {len(rag_limpo)} chars")
                if not options['dry_run']:
                    servico.texto_rag_otimizado = rag_limpo
            
            # Limpar intenção se existir
            if servico.intencao_servico:
                intencao_original = servico.intencao_servico
                intencao_limpa = self._limpar_entidades_html(intencao_original)
                if intencao_limpa != intencao_original:
                    campos_alterados.append('intencao_servico')
                    if not options['dry_run']:
                        servico.intencao_servico = intencao_limpa
            
            if campos_alterados:
                if not options['dry_run']:
                    # Atualizar versão se ainda for 1.0
                    if servico.versao_otimizacao == '1.0':
                        servico.versao_otimizacao = '1.1'
                    
                    servico.save()
                    
                    # Log da limpeza
                    LogOtimizacao.objects.create(
                        servico_otimizado=servico,
                        operacao='ATUALIZACAO',
                        detalhes={
                            'tipo': 'LIMPEZA_HTML',
                            'campos_limpos': campos_alterados,
                            'entidades_removidas': self._contar_entidades_html(desc_original + rag_original)
                        },
                        usuario='sistema_limpeza'
                    )
                    
                sucesso += 1
                self.stdout.write(
                    self.style.SUCCESS(f"   ✅ Limpo: {', '.join(campos_alterados)}")
                )
            else:
                self.stdout.write(f"   ⏭️  Já limpo")
        
        # Resultado final
        if not options['dry_run']:
            self.stdout.write(
                self.style.SUCCESS(f"\n🎯 LIMPEZA CONCLUÍDA: {sucesso} serviços processados")
            )
        else:
            self.stdout.write(
                f"\n🔍 DRY-RUN: {sucesso} serviços seriam processados"
            )

    def _limpar_entidades_html(self, texto):
        """Remove entidades HTML e melhora formatação."""
        if not texto:
            return texto
            
        # Usar html.unescape do Python (mais robusto)
        texto_limpo = html.unescape(texto)
        
        # Substituições específicas que podem não ser cobertas
        substituicoes_extras = {
            '&nbsp;': ' ',
            '&amp;': '&',
            '&lt;': '<',
            '&gt;': '>',
            '&quot;': '"',
            '&#39;': "'",
            '&ordm;': 'º',
            '&ordf;': 'ª',
        }
        
        for entidade, char in substituicoes_extras.items():
            texto_limpo = texto_limpo.replace(entidade, char)
        
        # Remover tags HTML se existirem
        texto_limpo = re.sub(r'<[^>]+>', '', texto_limpo)
        
        # Normalizar espaços
        texto_limpo = re.sub(r'\s+', ' ', texto_limpo)
        texto_limpo = texto_limpo.strip()
        
        return texto_limpo

    def _contar_entidades_html(self, texto):
        """Conta quantas entidades HTML existem no texto."""
        if not texto:
            return 0
        
        entidades = ['&oacute;', '&aacute;', '&eacute;', '&ccedil;', '&atilde;', '&nbsp;', '&ordm;', '&amp;', '&lt;', '&gt;', '&quot;']
        return sum(texto.count(entidade) for entidade in entidades)