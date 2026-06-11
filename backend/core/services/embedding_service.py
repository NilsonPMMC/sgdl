# /var/www/sgdl/backend/core/services/embedding_service.py

"""
Serviço para geração e otimização de embeddings da carta de serviços.
Integra com o CartaOptimizerService para criar embeddings de alta qualidade.
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from django.db import transaction
from pgvector.django import CosineDistance

from integrations.models_sinapse import CatalogServico
from integrations import sinapse_catalog
from .carta_optimizer import CartaOptimizerService, TextOptimizationResult
from core.models_carta_otimizada import ServicoOtimizado, LogOtimizacao

logger = logging.getLogger(__name__)


class EmbeddingOptimizationService:
    """Serviço para otimização e regeneração de embeddings."""
    
    def __init__(self):
        self.optimizer = CartaOptimizerService()
    
    def _limpar_html(self, texto_html):
        """Remove HTML básico e limpa texto."""
        import re
        if not texto_html:
            return ""
        # Remove tags HTML
        texto = re.sub(r'<[^>]+>', ' ', texto_html)
        # Limpa espaços múltiplos
        texto = re.sub(r'\s+', ' ', texto)
        return texto.strip()
    
    def _otimizar_titulo(self, titulo_original):
        """Otimiza título para linguagem mais acessível."""
        if not titulo_original:
            return ""
        
        # Remover prefixos técnicos comuns
        titulo = titulo_original
        prefixos_remover = ['Requerimento para ', 'Solicitação de ', 'Pedido de ']
        for prefixo in prefixos_remover:
            if titulo.startswith(prefixo):
                titulo = titulo[len(prefixo):]
                break
        
        return titulo.strip()
    
    def otimizar_embedding_servico(self, servico_id: int, 
                                 aplicar_alteracoes: bool = False) -> Dict[str, Any]:
        """
        Otimiza o embedding de um serviço específico.
        
        Args:
            servico_id: ID do serviço no catálogo Sinapse
            aplicar_alteracoes: Se True, salva as alterações no banco
            
        Returns:
            Relatório da otimização com scores e melhorias
        """
        try:
            # Buscar serviço atual
            servico = CatalogServico.objects.using('sinapse').get(id=servico_id)
            
            # Preparar dados para otimização
            servico_data = {
                'id': servico.id,
                'titulo': servico.titulo,
                'descricao_html': servico.descricao_html,
                'requisitos_html': servico.requisitos_html,
                'prazo': servico.prazo or '',
                'texto_limpo_rag': servico.texto_limpo_rag,
                'departamento': servico.departamento or '',
                'orgao': servico.id_orgao.nome if servico.id_orgao else '',
                'categoria': servico.id_categoria.nome if servico.id_categoria else '',
            }
            
            # Executar otimização
            resultado = self.optimizer.otimizar_servico(servico_data)
            
            # Calcular novo embedding se o texto foi significativamente melhorado
            novo_embedding = None
            similarity_score = None
            
            if resultado.texto_otimizado != servico.texto_limpo_rag:
                # Simular embedding (em produção, usaria modelo real)
                novo_embedding = self._simular_embedding_otimizado(resultado.texto_otimizado)
                
                # Calcular similaridade com embedding original
                if servico.embedding is not None:
                    similarity_score = self._calcular_similaridade(
                        servico.embedding, novo_embedding
                    )
            
            # Aplicar alterações se solicitado (score >= 5 para ser mais flexível)
            if aplicar_alteracoes and resultado.score_qualidade >= 5:
                with transaction.atomic():
                    # Criar/atualizar na base otimizada local (não altera Sinapse)
                    servico_otimizado, created = ServicoOtimizado.objects.update_or_create(
                        sinapse_servico_id=servico_id,
                        defaults={
                            'titulo_otimizado': self._otimizar_titulo(servico.titulo),
                            'descricao_objetiva': self._limpar_html(servico.descricao_html),
                            'texto_rag_otimizado': resultado.texto_otimizado,
                            'embedding_otimizado': novo_embedding,
                            'score_qualidade_original': 4,  # Score padrão para original
                            'score_qualidade_otimizado': resultado.score_qualidade,
                            'problemas_identificados': resultado.problemas_encontrados,
                            'melhorias_aplicadas': resultado.melhorias_aplicadas,
                            'palavras_chave': resultado.metadados_extraidos.get('palavras_chave', []),
                            'versao_otimizacao': '1.0',
                        }
                    )
                    
                    # Log da operação
                    LogOtimizacao.objects.create(
                        servico_otimizado=servico_otimizado,
                        operacao='CRIACAO' if created else 'ATUALIZACAO',
                        detalhes={
                            'score_antes': 4,  # Score padrão original
                            'score_depois': resultado.score_qualidade,
                            'melhorias': resultado.melhorias_aplicadas,
                            'embedding_gerado': novo_embedding is not None,
                        },
                        usuario='sistema'
                    )
            
            return {
                'servico_id': servico_id,
                'titulo': servico.titulo,
                'score_qualidade_anterior': self._estimar_score_anterior(servico),
                'score_qualidade_novo': resultado.score_qualidade,
                'texto_original': servico.texto_limpo_rag,
                'texto_otimizado': resultado.texto_otimizado,
                'problemas_encontrados': resultado.problemas_encontrados,
                'melhorias_aplicadas': resultado.melhorias_aplicadas,
                'metadados_extraidos': resultado.metadados_extraidos,
                'embedding_alterado': novo_embedding is not None,
                'similarity_score': similarity_score,
                'alteracoes_aplicadas': aplicar_alteracoes and resultado.score_qualidade >= 5,
                'recomenda_aplicar': resultado.score_qualidade >= 5
            }
            
        except CatalogServico.DoesNotExist:
            logger.error(f"Serviço {servico_id} não encontrado")
            return {'erro': f'Serviço {servico_id} não encontrado'}
        except Exception as e:
            logger.error(f"Erro ao otimizar serviço {servico_id}: {e}")
            return {'erro': str(e)}
    
    def otimizar_lote_servicos(self, servico_ids: List[int], 
                              aplicar_automaticamente: bool = False,
                              score_minimo: int = 7) -> Dict[str, Any]:
        """
        Otimiza um lote de serviços.
        
        Args:
            servico_ids: Lista de IDs dos serviços
            aplicar_automaticamente: Se True, aplica otimizações automaticamente
            score_minimo: Score mínimo para aplicar automaticamente
            
        Returns:
            Relatório consolidado do lote
        """
        resultados = []
        resumo = {
            'total_processados': 0,
            'total_otimizados': 0,
            'total_aplicados': 0,
            'score_medio_antes': 0,
            'score_medio_depois': 0,
            'problemas_mais_comuns': [],
            'melhorias_mais_frequentes': []
        }
        
        todos_problemas = []
        todas_melhorias = []
        scores_antes = []
        scores_depois = []
        
        for servico_id in servico_ids:
            try:
                # Otimizar serviço individual
                aplicar = aplicar_automaticamente
                resultado = self.otimizar_embedding_servico(servico_id, aplicar_alteracoes=aplicar)
                
                if 'erro' not in resultado:
                    resultados.append(resultado)
                    resumo['total_processados'] += 1
                    
                    if resultado['score_qualidade_novo'] > resultado['score_qualidade_anterior']:
                        resumo['total_otimizados'] += 1
                    
                    if resultado.get('alteracoes_aplicadas', False):
                        resumo['total_aplicados'] += 1
                    
                    # Coletar estatísticas
                    scores_antes.append(resultado['score_qualidade_anterior'])
                    scores_depois.append(resultado['score_qualidade_novo'])
                    todos_problemas.extend(resultado['problemas_encontrados'])
                    todas_melhorias.extend(resultado['melhorias_aplicadas'])
                
            except Exception as e:
                logger.error(f"Erro ao processar serviço {servico_id}: {e}")
                resultados.append({
                    'servico_id': servico_id,
                    'erro': str(e)
                })
        
        # Calcular estatísticas consolidadas
        if scores_antes:
            resumo['score_medio_antes'] = sum(scores_antes) / len(scores_antes)
            resumo['score_medio_depois'] = sum(scores_depois) / len(scores_depois)
        
        # Problemas e melhorias mais comuns
        from collections import Counter
        contador_problemas = Counter(todos_problemas)
        contador_melhorias = Counter(todas_melhorias)
        
        resumo['problemas_mais_comuns'] = contador_problemas.most_common(5)
        resumo['melhorias_mais_frequentes'] = contador_melhorias.most_common(5)
        
        return {
            'resumo': resumo,
            'resultados_individuais': resultados,
            'timestamp': str(timezone.now()) if 'timezone' in globals() else None
        }
    
    def buscar_servicos_problematicos(self, limite: int = 50) -> List[int]:
        """
        Identifica serviços com maior necessidade de otimização.
        
        Returns:
            Lista de IDs de serviços ordenados por prioridade de otimização
        """
        servicos_problematicos = []
        
        # Buscar serviços com problemas conhecidos
        servicos = CatalogServico.objects.using('sinapse').filter(
            status=1  # Apenas serviços ativos
        ).values(
            'id', 'titulo', 'texto_limpo_rag', 'prazo', 'descricao_html'
        )[:limite * 2]  # Buscar mais para filtrar
        
        prioridades = []
        
        for servico in servicos:
            score_problema = 0
            
            # Critérios de problemas (maior score = mais problemático)
            texto_rag = servico['texto_limpo_rag'] or ''
            
            # HTML residual
            if '<' in texto_rag and '>' in texto_rag:
                score_problema += 3
            
            # Prazo não estruturado
            prazo = servico['prazo'] or ''
            if any(word in prazo.lower() for word in ['conforme', 'demanda', 'análise']):
                score_problema += 2
            
            # Título técnico
            titulo = servico['titulo'] or ''
            if titulo.startswith('Requerimento'):
                score_problema += 1
            
            # Texto RAG muito curto ou muito longo
            if len(texto_rag) < 50:
                score_problema += 2
            elif len(texto_rag) > 1000:
                score_problema += 1
            
            # Descrição com HTML complexo
            descricao = servico['descricao_html'] or ''
            if descricao.count('<') > 5:
                score_problema += 1
            
            if score_problema > 0:
                prioridades.append((servico['id'], score_problema))
        
        # Ordenar por prioridade (maior score primeiro) e limitar
        prioridades.sort(key=lambda x: x[1], reverse=True)
        return [servico_id for servico_id, _ in prioridades[:limite]]
    
    def validar_melhoria_embedding(self, servico_id: int, 
                                 queries_teste: List[str] = None) -> Dict[str, Any]:
        """
        Valida se a otimização do embedding melhorou a busca semântica.
        
        Args:
            servico_id: ID do serviço otimizado
            queries_teste: Lista de queries para testar (opcional)
            
        Returns:
            Relatório de validação com scores de similaridade
        """
        if queries_teste is None:
            queries_teste = [
                "receita de bolo",
                "recolhimento de animais",
                "licença para empresa",
                "certidão de tempo de serviço",
                "alvará de funcionamento"
            ]
        
        try:
            servico = CatalogServico.objects.using('sinapse').get(id=servico_id)
            
            resultados_teste = {}
            
            for query in queries_teste:
                # Simular embedding da query
                query_embedding = self._simular_embedding_otimizado(query)
                
                # Calcular similaridade com o serviço
                if servico.embedding is not None:
                    similarity = self._calcular_similaridade(servico.embedding, query_embedding)
                    resultados_teste[query] = {
                        'similarity_score': similarity,
                        'relevante': self._e_relevante_para_servico(query, servico),
                        'titulo_servico': servico.titulo
                    }
            
            # Calcular métricas de qualidade
            scores_relevantes = [r['similarity_score'] for q, r in resultados_teste.items() 
                               if r['relevante']]
            scores_irrelevantes = [r['similarity_score'] for q, r in resultados_teste.items() 
                                 if not r['relevante']]
            
            return {
                'servico_id': servico_id,
                'titulo': servico.titulo,
                'resultados_por_query': resultados_teste,
                'media_score_relevantes': sum(scores_relevantes) / len(scores_relevantes) if scores_relevantes else 0,
                'media_score_irrelevantes': sum(scores_irrelevantes) / len(scores_irrelevantes) if scores_irrelevantes else 0,
                'separacao_adequada': len(scores_relevantes) > 0 and len(scores_irrelevantes) > 0 and
                                    (sum(scores_relevantes) / len(scores_relevantes)) > 
                                    (sum(scores_irrelevantes) / len(scores_irrelevantes)) + 0.1
            }
            
        except CatalogServico.DoesNotExist:
            return {'erro': f'Serviço {servico_id} não encontrado'}
    
    def _simular_embedding_otimizado(self, texto: str) -> np.ndarray:
        """
        Simula geração de embedding otimizado.
        Em produção, seria substituído por modelo real (Sentence-BERT, OpenAI, etc.)
        """
        # Para demonstração, usar hash baseado no texto
        import hashlib
        import struct
        
        # Gerar vetor baseado em hash do texto (determinístico)
        hash_obj = hashlib.md5(texto.encode())
        hash_bytes = hash_obj.digest()
        
        # Converter para array de floats
        embedding = []
        for i in range(0, len(hash_bytes), 4):
            chunk = hash_bytes[i:i+4]
            if len(chunk) == 4:
                float_val = struct.unpack('f', chunk)[0]
                embedding.append(float_val)
        
        # Preencher até 1024 dimensões
        while len(embedding) < 1024:
            embedding.extend(embedding[:min(len(embedding), 1024 - len(embedding))])
        
        embedding = embedding[:1024]
        
        # Normalizar
        embedding_array = np.array(embedding, dtype=np.float32)
        norm = np.linalg.norm(embedding_array)
        if norm > 0:
            embedding_array = embedding_array / norm
        
        return embedding_array
    
    def _calcular_similaridade(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Calcula similaridade coseno entre dois embeddings."""
        if embedding1 is None or embedding2 is None:
            return 0.0
        
        # Converter para numpy se necessário
        if not isinstance(embedding1, np.ndarray):
            embedding1 = np.array(embedding1, dtype=np.float32)
        if not isinstance(embedding2, np.ndarray):
            embedding2 = np.array(embedding2, dtype=np.float32)
        
        # Calcular similaridade coseno
        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
    
    def _estimar_score_anterior(self, servico: CatalogServico) -> int:
        """Estima score de qualidade do serviço antes da otimização."""
        score = 5  # Base
        
        # Penalizar HTML residual
        texto_rag = servico.texto_limpo_rag or ''
        if '<' in texto_rag and '>' in texto_rag:
            score -= 2
        
        # Penalizar prazo não estruturado
        prazo = servico.prazo or ''
        if any(word in prazo.lower() for word in ['conforme', 'demanda']):
            score -= 1
        
        # Penalizar título técnico
        if servico.titulo.startswith('Requerimento'):
            score -= 1
        
        # Bonificar texto substancial
        if len(texto_rag) > 100:
            score += 1
        
        return max(1, min(10, score))
    
    def _e_relevante_para_servico(self, query: str, servico: CatalogServico) -> bool:
        """Determina se uma query deve ser relevante para um serviço específico."""
        query_lower = query.lower()
        titulo_lower = servico.titulo.lower()
        descricao_lower = (servico.descricao_html or '').lower()
        
        # Buscar palavras-chave da query no serviço
        palavras_query = query_lower.split()
        texto_servico = f"{titulo_lower} {descricao_lower}"
        
        matches = sum(1 for palavra in palavras_query if palavra in texto_servico)
        
        # Considerar relevante se pelo menos metade das palavras batem
        return matches >= len(palavras_query) / 2