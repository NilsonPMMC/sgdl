"""
Comando para regenerar embeddings da base otimizada com textos melhorados.

Corrige problemas identificados na integração:
- Limpeza mais eficaz de HTML e entidades
- Texto RAG mais descritivo e rico em contexto
- Embeddings de maior qualidade para busca semântica
"""

import logging
from typing import List, Dict, Any
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, models
from django.utils import timezone
import re

from core.models_carta_otimizada import ServicoOtimizado, LogOtimizacao
from core.services.vector_service import VectorService
from integrations.models_sinapse import CatalogServico, SINAPSE_DB_ALIAS

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """
    Regenera embeddings da base otimizada com textos melhorados.
    
    Corrige problemas de qualidade identificados na integração,
    melhorando limpeza HTML e geração de texto RAG.
    
    Exemplos:
    python manage.py regenerar_embeddings_base_otimizada --limite 20
    python manage.py regenerar_embeddings_base_otimizada --servico-id 80
    python manage.py regenerar_embeddings_base_otimizada --todos
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--limite',
            type=int,
            default=50,
            help='Número de serviços para processar (default: 50)'
        )
        parser.add_argument(
            '--servico-id',
            type=int,
            help='ID específico do serviço para regenerar'
        )
        parser.add_argument(
            '--todos',
            action='store_true',
            help='Regenerar todos os serviços da base'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forçar regeneração mesmo com embeddings existentes'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS("🔄 Regenerando embeddings da base otimizada...")
        )
        
        try:
            # Configurar vector service
            self.vector_service = VectorService()
            
            # Selecionar serviços para processar
            servicos = self._selecionar_servicos(options)
            
            if not servicos:
                self.stdout.write(
                    self.style.WARNING("❌ Nenhum serviço selecionado para processamento")
                )
                return
            
            self.stdout.write(f"🎯 Processando {len(servicos)} serviços...")
            
            # Processar serviços
            resultados = self._processar_servicos(servicos, options)
            
            # Relatório final
            self._exibir_relatorio(resultados)
            
        except Exception as e:
            raise CommandError(f"Erro na regeneração: {str(e)}")

    def _selecionar_servicos(self, options: Dict[str, Any]) -> List[ServicoOtimizado]:
        """Seleciona serviços para regeneração baseado nas opções."""
        
        if options.get('servico_id'):
            # Serviço específico
            try:
                servico = ServicoOtimizado.objects.get(sinapse_servico_id=options['servico_id'])
                return [servico]
            except ServicoOtimizado.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"Serviço {options['servico_id']} não encontrado na base otimizada")
                )
                return []
        
        # Query base
        queryset = ServicoOtimizado.objects.filter(ativo=True)
        
        if not options.get('force'):
            # Priorizar serviços com problemas identificados
            queryset = queryset.filter(
                models.Q(embedding_otimizado__isnull=True) |
                models.Q(palavras_chave__icontains='atilde') |  # HTML entities
                models.Q(palavras_chave__icontains='ccedil') |
                models.Q(palavras_chave__icontains='eacute') |
                models.Q(score_qualidade_otimizado__lt=6)
            )
        
        if options.get('todos'):
            return list(queryset)
        
        return list(queryset[:options['limite']])

    def _processar_servicos(
        self,
        servicos: List[ServicoOtimizado],
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Processa lista de serviços para regeneração."""
        
        resultados = {
            'total_processados': 0,
            'sucessos': 0,
            'erros': 0,
            'melhorias': []
        }
        
        for i, servico in enumerate(servicos, 1):
            self.stdout.write(f"\n🔄 {i}/{len(servicos)}: Serviço {servico.sinapse_servico_id}")
            
            try:
                resultado = self._regenerar_servico_individual(servico)
                
                if resultado['sucesso']:
                    resultados['sucessos'] += 1
                    if resultado.get('melhoria_detectada'):
                        resultados['melhorias'].append(resultado)
                else:
                    resultados['erros'] += 1
                
                resultados['total_processados'] += 1
                
                # Log do resultado
                if resultado['sucesso']:
                    self.stdout.write(f"   ✅ Regenerado - Score: {resultado['novo_score']}")
                else:
                    self.stdout.write(f"   ❌ Erro: {resultado['erro']}")
                
            except Exception as e:
                resultados['erros'] += 1
                resultados['total_processados'] += 1
                self.stdout.write(f"   ❌ Erro inesperado: {str(e)}")
                logger.error(f"Erro ao regenerar serviço {servico.sinapse_servico_id}: {str(e)}")
        
        return resultados

    def _regenerar_servico_individual(self, servico: ServicoOtimizado) -> Dict[str, Any]:
        """Regenera um serviço individual com melhorias."""
        
        resultado = {
            'servico_id': servico.sinapse_servico_id,
            'sucesso': False,
            'erro': None,
            'novo_score': servico.score_qualidade_otimizado,
            'melhoria_detectada': False
        }
        
        try:
            # Buscar dados originais do Sinapse
            servico_original = CatalogServico.objects.using(SINAPSE_DB_ALIAS).get(
                id=servico.sinapse_servico_id
            )
            
            # Gerar texto RAG melhorado
            texto_rag_novo = self._gerar_texto_rag_melhorado(
                servico_original, servico
            )
            
            # Gerar palavras-chave limpas
            palavras_chave_novas = self._extrair_palavras_chave_limpas(
                texto_rag_novo, servico_original
            )
            
            # Gerar novo embedding
            novo_embedding = self.vector_service.generate_embedding(texto_rag_novo)
            
            if not novo_embedding:
                resultado['erro'] = 'Falha ao gerar embedding'
                return resultado
            
            # Calcular novo score baseado na melhoria
            novo_score = self._calcular_score_qualidade(
                texto_rag_novo, palavras_chave_novas, servico.score_qualidade_otimizado
            )
            
            # Atualizar no banco
            with transaction.atomic():
                servico.texto_rag_otimizado = texto_rag_novo
                servico.palavras_chave = palavras_chave_novas
                servico.embedding_otimizado = novo_embedding
                servico.score_qualidade_otimizado = novo_score
                servico.versao_otimizacao = "1.1"  # Atualizar versão
                servico.save()
                
                # Log da operação
                LogOtimizacao.objects.create(
                    servico_otimizado=servico,
                    operacao='ATUALIZACAO',
                    detalhes={
                        'tipo': 'regeneracao_embedding',
                        'score_antes': servico.score_qualidade_otimizado,
                        'score_depois': novo_score,
                        'palavras_chave_limpas': len(palavras_chave_novas),
                        'texto_melhorado': len(texto_rag_novo) > len(servico.texto_rag_otimizado)
                    },
                    usuario='sistema_regeneracao'
                )
            
            resultado['sucesso'] = True
            resultado['novo_score'] = novo_score
            resultado['melhoria_detectada'] = novo_score > servico.score_qualidade_otimizado
            
            return resultado
            
        except Exception as e:
            resultado['erro'] = str(e)
            return resultado

    def _gerar_texto_rag_melhorado(
        self,
        servico_original: CatalogServico,
        servico_otimizado: ServicoOtimizado
    ) -> str:
        """Gera texto RAG com melhor qualidade para embedding."""
        
        # Limpar textos básicos
        titulo = self._limpar_texto_completo(servico_original.titulo)
        descricao = self._limpar_texto_completo(servico_original.descricao_html)
        documentos = self._limpar_texto_completo(servico_original.documentos_necessarios)
        requisitos = self._limpar_texto_completo(servico_original.requisitos_html)
        
        # Extrair palavras-chave específicas do domínio
        palavras_contexto = self._identificar_contexto_servico(titulo, descricao)
        
        # Montar texto estruturado
        partes = []
        
        # Título otimizado
        partes.append(f"SERVIÇO: {titulo}")
        
        # Descrição limpa
        if descricao:
            partes.append(f"DESCRIÇÃO: {descricao}")
        
        # Contexto específico
        if palavras_contexto:
            partes.append(f"ÁREA: {', '.join(palavras_contexto)}")
        
        # Documentos se relevantes
        if documentos and len(documentos) > 10:
            docs_resumo = self._resumir_documentos(documentos)
            if docs_resumo:
                partes.append(f"DOCUMENTOS: {docs_resumo}")
        
        # Requisitos principais
        if requisitos and len(requisitos) > 10:
            requisitos_resumo = self._extrair_requisitos_principais(requisitos)
            if requisitos_resumo:
                partes.append(f"REQUISITOS: {requisitos_resumo}")
        
        # Palavras-chave expandidas para busca
        palavras_busca = self._expandir_palavras_chave_busca(titulo, descricao, palavras_contexto)
        if palavras_busca:
            partes.append(f"PALAVRAS-CHAVE: {', '.join(palavras_busca)}")
        
        return ' | '.join(partes)

    def _limpar_texto_completo(self, texto_html: str) -> str:
        """Limpeza completa de HTML e entidades."""
        if not texto_html:
            return ""
        
        # Converter entidades HTML primeiro
        import html
        texto = html.unescape(texto_html)
        
        # Remover tags HTML
        texto = re.sub(r'<[^>]+>', ' ', texto)
        
        # Limpar entidades restantes manualmente
        entidades = {
            '&nbsp;': ' ',
            '&amp;': '&',
            '&lt;': '<',
            '&gt;': '>',
            '&quot;': '"',
            '&apos;': "'",
            '&ccedil;': 'ç',
            '&aacute;': 'á',
            '&eacute;': 'é',
            '&iacute;': 'í',
            '&oacute;': 'ó',
            '&uacute;': 'ú',
            '&atilde;': 'ã',
            '&otilde;': 'õ',
            '&agrave;': 'à',
            '&egrave;': 'è',
            '&igrave;': 'ì',
            '&ograve;': 'ò',
            '&ugrave;': 'ù',
            '&acirc;': 'â',
            '&ecirc;': 'ê',
            '&icirc;': 'î',
            '&ocirc;': 'ô',
            '&ucirc;': 'û'
        }
        
        for entidade, char in entidades.items():
            texto = texto.replace(entidade, char)
        
        # Limpar espaços múltiplos e caracteres especiais
        texto = re.sub(r'\s+', ' ', texto)
        texto = re.sub(r'[^\w\sáéíóúàèìòùâêîôûãõç.,;:!?()-]', ' ', texto)
        texto = re.sub(r'\s+', ' ', texto)
        
        return texto.strip()

    def _identificar_contexto_servico(self, titulo: str, descricao: str) -> List[str]:
        """Identifica contexto/área do serviço para palavras-chave."""
        
        texto_completo = f"{titulo} {descricao}".lower()
        
        contextos = {
            'pavimentação': ['buraco', 'tapa', 'asfalto', 'pavimento', 'rua', 'via'],
            'iluminação': ['luz', 'poste', 'luminária', 'iluminação', 'lâmpada'],
            'licenciamento': ['licença', 'alvará', 'funcionamento', 'estabelecimento'],
            'tributário': ['iptu', 'imposto', 'taxa', 'débito', 'cobrança'],
            'saúde': ['saúde', 'medicamento', 'vacina', 'posto', 'ubs'],
            'educação': ['escola', 'educação', 'ensino', 'vaga', 'matrícula'],
            'meio_ambiente': ['lixo', 'coleta', 'limpeza', 'terreno', 'ecoponto'],
            'transporte': ['transporte', 'ônibus', 'escolar', 'mobilidade'],
            'habitação': ['habitação', 'moradia', 'casa', 'terreno', 'lote'],
            'assistência_social': ['social', 'assistência', 'benefício', 'cadastro_único'],
            'cultura_esporte': ['cultura', 'esporte', 'evento', 'espaço', 'quadra'],
            'documento': ['certidão', 'declaração', 'comprovante', 'documento']
        }
        
        contextos_identificados = []
        for contexto, palavras in contextos.items():
            if any(palavra in texto_completo for palavra in palavras):
                contextos_identificados.append(contexto.replace('_', ' '))
        
        return contextos_identificados

    def _expandir_palavras_chave_busca(
        self,
        titulo: str,
        descricao: str,
        contextos: List[str]
    ) -> List[str]:
        """Expande palavras-chave para melhorar busca."""
        
        texto_base = f"{titulo} {descricao}".lower()
        palavras_base = re.findall(r'\b[a-záéíóúàèìòùâêîôûãõç]{3,}\b', texto_base)
        
        # Expansões específicas por contexto
        expansoes = {
            'pavimentação': ['buraco', 'cratera', 'asfalto', 'pavimento', 'rua', 'via', 'calçada'],
            'iluminação': ['luz', 'poste', 'luminária', 'lâmpada', 'iluminação', 'escuro'],
            'licenciamento': ['licença', 'alvará', 'autorização', 'permissão', 'funcionamento'],
            'tributário': ['imposto', 'taxa', 'débito', 'pagamento', 'cobrança', 'boleto'],
            'documento': ['certidão', 'declaração', 'comprovante', 'atestado', 'segunda via']
        }
        
        palavras_expandidas = set(palavras_base)
        
        for contexto in contextos:
            contexto_key = contexto.replace(' ', '_')
            if contexto_key in expansoes:
                palavras_expandidas.update(expansoes[contexto_key])
        
        # Filtrar palavras muito comuns
        stopwords = {'para', 'com', 'por', 'em', 'de', 'da', 'do', 'na', 'no', 'um', 'uma', 'o', 'a'}
        palavras_filtradas = [p for p in palavras_expandidas if len(p) >= 3 and p not in stopwords]
        
        return sorted(set(palavras_filtradas))[:20]  # Limitar a 20 palavras-chave

    def _resumir_documentos(self, documentos_html: str) -> str:
        """Extrai resumo dos documentos necessários."""
        
        texto_limpo = self._limpar_texto_completo(documentos_html)
        
        # Padrões comuns de documentos
        padroes_docs = [
            r'\b(rg|identidade)\b',
            r'\b(cpf)\b',
            r'\b(comprovante.*residência|endereço)\b',
            r'\b(certidão.*nascimento)\b',
            r'\b(título.*eleitor)\b',
            r'\b(carteira.*trabalho)\b'
        ]
        
        docs_encontrados = []
        texto_lower = texto_limpo.lower()
        
        for padrao in padroes_docs:
            if re.search(padrao, texto_lower):
                match = re.search(padrao, texto_lower)
                docs_encontrados.append(match.group(0))
        
        if docs_encontrados:
            return ', '.join(docs_encontrados)
        
        # Fallback: primeiras palavras relevantes
        palavras = texto_limpo.split()[:10]
        return ' '.join(palavras) if palavras else ""

    def _extrair_requisitos_principais(self, requisitos_html: str) -> str:
        """Extrai requisitos principais."""
        
        texto_limpo = self._limpar_texto_completo(requisitos_html)
        
        # Palavras-chave de requisitos
        if any(word in texto_limpo.lower() for word in ['maior', 'idade', 'anos']):
            return "maioridade civil"
        
        if any(word in texto_limpo.lower() for word in ['empresa', 'estabelecimento']):
            return "estabelecimento comercial"
        
        # Fallback
        return texto_limpo[:50] + "..." if len(texto_limpo) > 50 else texto_limpo

    def _extrair_palavras_chave_limpas(
        self,
        texto_rag: str,
        servico_original: CatalogServico
    ) -> List[str]:
        """Extrai palavras-chave limpas sem entidades HTML."""
        
        # Extrair do texto RAG melhorado
        palavras = re.findall(r'\b[a-záéíóúàèìòùâêîôûãõç]{3,}\b', texto_rag.lower())
        
        # Filtrar palavras comuns
        stopwords = {
            'para', 'com', 'por', 'em', 'de', 'da', 'do', 'na', 'no', 'um', 'uma', 'o', 'a',
            'que', 'se', 'ou', 'e', 'são', 'dos', 'das', 'pelo', 'pela', 'aos', 'às',
            'serviço', 'descrição', 'área', 'documentos', 'requisitos', 'palavras', 'chave'
        }
        
        palavras_filtradas = [
            p for p in set(palavras) 
            if len(p) >= 3 and p not in stopwords
        ]
        
        return sorted(palavras_filtradas)[:15]  # Top 15 palavras-chave

    def _calcular_score_qualidade(
        self,
        texto_rag: str,
        palavras_chave: List[str],
        score_anterior: int
    ) -> int:
        """Calcula novo score de qualidade baseado nas melhorias."""
        
        score = score_anterior
        
        # Bonificações
        if len(texto_rag) > 100:
            score += 0.5  # Texto mais descritivo
        
        if len(palavras_chave) >= 10:
            score += 0.5  # Boas palavras-chave
        
        # Verificar se não há entidades HTML
        if not any(ent in palavras_chave for ent in ['atilde', 'ccedil', 'eacute', 'nbsp']):
            score += 1  # Texto limpo
        
        # Verificar contexto específico
        if any(word in texto_rag.lower() for word in ['buraco', 'iluminação', 'licença', 'iptu']):
            score += 0.5  # Contexto específico
        
        return min(10, int(score))

    def _exibir_relatorio(self, resultados: Dict[str, Any]):
        """Exibe relatório final da regeneração."""
        
        total = resultados['total_processados']
        sucessos = resultados['sucessos']
        erros = resultados['erros']
        
        self.stdout.write(f"\n" + "="*60)
        self.stdout.write(self.style.SUCCESS("🏆 REGENERAÇÃO CONCLUÍDA"))
        self.stdout.write("="*60)
        
        self.stdout.write(f"\n📊 RESULTADOS:")
        self.stdout.write(f"   Total processados: {total}")
        self.stdout.write(f"   Sucessos: {sucessos}")
        self.stdout.write(f"   Erros: {erros}")
        
        if total > 0:
            taxa_sucesso = (sucessos / total) * 100
            self.stdout.write(f"   Taxa de sucesso: {taxa_sucesso:.1f}%")
        
        melhorias = resultados.get('melhorias', [])
        if melhorias:
            self.stdout.write(f"\n✨ MELHORIAS DETECTADAS: {len(melhorias)}")
            for melhoria in melhorias[:5]:  # Top 5
                self.stdout.write(
                    f"   • Serviço {melhoria['servico_id']}: score {melhoria['novo_score']}"
                )
        
        self.stdout.write(f"\n" + "="*60)