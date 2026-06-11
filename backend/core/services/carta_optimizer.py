# /var/www/sgdl/backend/core/services/carta_optimizer.py

"""
Serviço para otimização da carta de serviços baseado em análise dos problemas identificados.
Implementa melhorias práticas sem dependência de LLM externo.
"""

import re
import logging
import html
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from collections import Counter

logger = logging.getLogger(__name__)


@dataclass
class TextOptimizationResult:
    """Resultado da otimização de texto para RAG."""
    texto_otimizado: str
    problemas_encontrados: List[str]
    melhorias_aplicadas: List[str]
    score_qualidade: int  # 1-10
    metadados_extraidos: Dict[str, Any]


@dataclass
class PrazoInfo:
    """Informações estruturadas sobre prazo de serviço."""
    dias_numericos: Optional[int]
    categoria: str  # IMEDIATO, RAPIDO, NORMAL, LONGO, INDEFINIDO
    texto_original: str
    observacoes: str


class CartaOptimizerService:
    """Serviço principal para otimização da carta de serviços."""
    
    # Padrões de limpeza HTML
    HTML_PATTERNS = [
        (r'<p>\s*<br\s*/?>\s*</p>', ''),  # Parágrafos vazios
        (r'<p>\s*</p>', ''),              # Parágrafos vazios
        (r'<br\s*/?>\s*<br\s*/?>', '\n'),  # BRs duplos
        (r'<[^>]+>', ' '),                # Tags HTML restantes
        (r'\s+', ' '),                    # Espaços múltiplos
        (r'&nbsp;', ' '),                 # Entidades HTML
        (r'&amp;', '&'),
        (r'&lt;', '<'),
        (r'&gt;', '>'),
    ]
    
    # Padrões de prazo
    PRAZO_PATTERNS = [
        (r'imediato|instantâneo|na hora', 'IMEDIATO', 0),
        (r'até?\s*(\d+)\s*dias?\s*úteis?', 'NORMAL', None),
        (r'até?\s*(\d+)\s*dias?', 'NORMAL', None),
        (r'(\d+)\s*a\s*(\d+)\s*dias', 'NORMAL', None),
        (r'conforme\s+demanda|demanda|necessidade', 'INDEFINIDO', None),
        (r'análise|avaliação|vistoria', 'LONGO', 30),
        (r'rápido|urgente', 'RAPIDO', 5),
    ]
    
    # Sinônimos comuns para enriquecer texto RAG
    SINONIMOS = {
        'licença': ['autorização', 'permissão', 'alvará'],
        'certidão': ['certificado', 'comprovante', 'documento'],
        'requerimento': ['solicitação', 'pedido', 'requisição'],
        'alvará': ['licença', 'autorização', 'permissão'],
        'declaração': ['comprovante', 'atestado', 'certidão'],
        'cadastro': ['registro', 'inscrição', 'habilitação'],
        'vistoria': ['inspeção', 'fiscalização', 'verificação'],
        'protocolo': ['registro', 'número', 'processo'],
    }
    
    def limpar_html_residual(self, texto: str) -> Tuple[str, List[str]]:
        """
        Limpa HTML residual e ruído do texto.
        
        Returns:
            Tuple com texto limpo e lista de problemas encontrados
        """
        problemas = []
        texto_limpo = texto.strip()
        
        # Detectar problemas HTML
        if '<' in texto and '>' in texto:
            problemas.append("HTML residual detectado")
            
        if '&nbsp;' in texto or '&amp;' in texto:
            problemas.append("Entidades HTML não convertidas")
            
        # Aplicar limpeza
        for pattern, replacement in self.HTML_PATTERNS:
            if re.search(pattern, texto_limpo, re.IGNORECASE):
                texto_limpo = re.sub(pattern, replacement, texto_limpo, flags=re.IGNORECASE)
        
        # Decodificar HTML entities
        texto_limpo = html.unescape(texto_limpo)
        
        # Limpar espaços e quebras desnecessárias
        texto_limpo = texto_limpo.strip()
        texto_limpo = re.sub(r'\n\s*\n', '\n\n', texto_limpo)
        
        return texto_limpo, problemas
    
    def extrair_prazo_estruturado(self, prazo_texto: str) -> PrazoInfo:
        """
        Extrai informações estruturadas de prazo de texto livre.
        """
        if not prazo_texto:
            return PrazoInfo(None, 'INDEFINIDO', '', 'Prazo não informado')
        
        prazo_lower = prazo_texto.lower().strip()
        
        # Buscar padrões conhecidos
        for pattern, categoria, dias_default in self.PRAZO_PATTERNS:
            match = re.search(pattern, prazo_lower)
            if match:
                dias = None
                if match.groups():
                    # Extrair número de dias do primeiro grupo
                    try:
                        dias = int(match.group(1))
                    except (ValueError, IndexError):
                        pass
                    
                    # Caso especial: intervalo de dias (5 a 10 dias)
                    if len(match.groups()) > 1:
                        try:
                            dias_max = int(match.group(2))
                            dias = dias_max  # Usar o máximo do intervalo
                        except (ValueError, IndexError):
                            pass
                
                if dias is None and dias_default is not None:
                    dias = dias_default
                    
                return PrazoInfo(
                    dias_numericos=dias,
                    categoria=categoria,
                    texto_original=prazo_texto,
                    observacoes=prazo_texto if categoria != 'IMEDIATO' else ''
                )
        
        # Padrão não reconhecido
        return PrazoInfo(
            dias_numericos=None,
            categoria='INDEFINIDO',
            texto_original=prazo_texto,
            observacoes=f'Prazo não estruturado: {prazo_texto}'
        )
    
    def extrair_palavras_chave_contexto(self, titulo: str, descricao: str) -> List[str]:
        """
        Extrai palavras-chave e contexto relevante do título e descrição.
        """
        # Combinar texto
        texto_completo = f"{titulo} {descricao}".lower()
        
        # Extrair palavras importantes (não stop words)
        stop_words = {
            'de', 'da', 'do', 'das', 'dos', 'para', 'com', 'em', 'no', 'na',
            'por', 'sem', 'sob', 'sobre', 'até', 'ao', 'aos', 'às', 'e', 'ou',
            'mas', 'que', 'se', 'o', 'a', 'os', 'as', 'um', 'uma', 'uns', 'umas',
            'este', 'esta', 'estes', 'estas', 'esse', 'essa', 'esses', 'essas'
        }
        
        # Extrair palavras significativas
        palavras = re.findall(r'\b[a-záéíóúçãõàêô]{3,}\b', texto_completo)
        palavras_importantes = [p for p in palavras if p not in stop_words]
        
        # Contar frequência e pegar as mais relevantes
        contador = Counter(palavras_importantes)
        palavras_chave = [palavra for palavra, freq in contador.most_common(10)]
        
        # Adicionar sinônimos
        palavras_expandidas = set(palavras_chave)
        for palavra in palavras_chave[:5]:  # Apenas para as 5 principais
            if palavra in self.SINONIMOS:
                palavras_expandidas.update(self.SINONIMOS[palavra])
        
        return list(palavras_expandidas)
    
    def estruturar_texto_rag(self, servico_data: Dict[str, Any]) -> str:
        """
        Estrutura texto no formato PROBLEMA/SOLUÇÃO/CONTEXTO para otimizar embeddings.
        """
        titulo = servico_data.get('titulo', '').strip()
        descricao = servico_data.get('descricao_html', '').strip()
        requisitos = servico_data.get('requisitos_html', '').strip()
        prazo_info = servico_data.get('prazo_estruturado')
        palavras_chave = servico_data.get('palavras_chave', [])
        
        # Limpar textos
        descricao_limpa, _ = self.limpar_html_residual(descricao)
        requisitos_limpos, _ = self.limpar_html_residual(requisitos)
        
        # Construir texto estruturado
        secoes = []
        
        # PROBLEMA: Inferir do título e contexto
        problema = self._inferir_problema_cidadao(titulo, descricao_limpa)
        if problema:
            secoes.append(f"PROBLEMA: {problema}")
        
        # SOLUÇÃO: Baseada na descrição
        solucao = self._extrair_solucao(titulo, descricao_limpa)
        if solucao:
            secoes.append(f"SOLUÇÃO: {solucao}")
        
        # CONTEXTO: Quando usar, quem pode solicitar
        contexto = self._extrair_contexto_uso(descricao_limpa, requisitos_limpos)
        if contexto:
            secoes.append(f"CONTEXTO: {contexto}")
        
        # PRAZO: Se estruturado
        if prazo_info and prazo_info.categoria != 'INDEFINIDO':
            prazo_desc = self._descrever_prazo(prazo_info)
            secoes.append(f"PRAZO: {prazo_desc}")
        
        # PALAVRAS-CHAVE: Para melhorar busca
        if palavras_chave:
            secoes.append(f"RELACIONADO: {', '.join(palavras_chave[:8])}")
        
        return ' | '.join(secoes)
    
    def _inferir_problema_cidadao(self, titulo: str, descricao: str) -> str:
        """Infere o problema que o cidadão está tentando resolver."""
        titulo_lower = titulo.lower()
        descricao_lower = descricao.lower()
        
        # Padrões de problemas comuns
        if any(word in titulo_lower for word in ['licença', 'alvará', 'autorização']):
            return "Preciso de autorização oficial para abrir ou operar meu negócio/atividade"
        
        if any(word in titulo_lower for word in ['certidão', 'certificado', 'comprovante']):
            return "Preciso comprovar uma situação ou direito perante terceiros"
        
        if any(word in titulo_lower for word in ['cadastro', 'inscrição', 'registro']):
            return "Preciso me registrar ou cadastrar em sistema municipal"
        
        if any(word in titulo_lower for word in ['vistoria', 'fiscalização']):
            return "Preciso de verificação técnica oficial do poder público"
        
        if 'segunda via' in titulo_lower:
            return "Perdi um documento oficial e preciso de nova via"
        
        # Padrão genérico baseado no título
        if titulo.startswith('Requerimento'):
            return f"Preciso solicitar oficialmente: {titulo.replace('Requerimento de', '').replace('Requerimento para', '').strip()}"
        
        return ""
    
    def _extrair_solucao(self, titulo: str, descricao: str) -> str:
        """Extrai a solução oferecida pelo serviço."""
        # Simplificar o título removendo jargões
        solucao = titulo
        
        # Remover palavras técnicas desnecessárias
        solucao = re.sub(r'^(Requerimento|Solicitação)\s+(de|para)\s*', '', solucao, flags=re.IGNORECASE)
        
        # Adicionar contexto da descrição se relevante
        if len(descricao) > 50 and len(descricao) < 200:
            primeira_frase = descricao.split('.')[0].strip()
            if primeira_frase and len(primeira_frase) < 100:
                solucao += f". {primeira_frase}"
        
        return solucao.strip()
    
    def _extrair_contexto_uso(self, descricao: str, requisitos: str) -> str:
        """Extrai contexto sobre quando e quem pode usar o serviço."""
        contexto_partes = []
        
        # Buscar indicações de público-alvo
        texto_completo = f"{descricao} {requisitos}".lower()
        
        if any(word in texto_completo for word in ['empresa', 'empresário', 'negócio', 'estabelecimento']):
            contexto_partes.append("Para empresários e estabelecimentos")
        
        if any(word in texto_completo for word in ['servidor', 'funcionário público']):
            contexto_partes.append("Para servidores públicos municipais")
        
        if any(word in texto_completo for word in ['cidadão', 'munícipe', 'morador']):
            contexto_partes.append("Para cidadãos e moradores do município")
        
        if any(word in texto_completo for word in ['profissional', 'liberal', 'autônomo']):
            contexto_partes.append("Para profissionais autônomos")
        
        # Se não encontrou público específico, usar genérico
        if not contexto_partes:
            contexto_partes.append("Para quem precisa de serviço municipal específico")
        
        return "; ".join(contexto_partes)
    
    def _descrever_prazo(self, prazo_info: PrazoInfo) -> str:
        """Descreve o prazo de forma padronizada."""
        if prazo_info.categoria == 'IMEDIATO':
            return "Atendimento imediato"
        elif prazo_info.dias_numericos:
            return f"Até {prazo_info.dias_numericos} dias"
        else:
            return prazo_info.observacoes or "Prazo variável conforme caso"
    
    def otimizar_servico(self, servico_data: Dict[str, Any]) -> TextOptimizationResult:
        """
        Otimiza um serviço completo da carta.
        
        Args:
            servico_data: Dicionário com dados do serviço (titulo, descricao_html, etc.)
            
        Returns:
            Resultado da otimização com texto otimizado e metadados
        """
        problemas = []
        melhorias = []
        
        # 1. Extrair prazo estruturado
        prazo_texto = servico_data.get('prazo', '')
        prazo_estruturado = self.extrair_prazo_estruturado(prazo_texto)
        if prazo_estruturado.categoria != 'INDEFINIDO':
            melhorias.append("Prazo estruturado extraído")
        else:
            problemas.append("Prazo não estruturado")
        
        # 2. Extrair palavras-chave
        palavras_chave = self.extrair_palavras_chave_contexto(
            servico_data.get('titulo', ''),
            servico_data.get('descricao_html', '')
        )
        if palavras_chave:
            melhorias.append(f"Extraídas {len(palavras_chave)} palavras-chave relevantes")
        
        # 3. Limpar HTML residual do texto RAG original
        texto_rag_original = servico_data.get('texto_limpo_rag', '')
        _, problemas_html = self.limpar_html_residual(texto_rag_original)
        problemas.extend(problemas_html)
        
        # 4. Estruturar texto otimizado para RAG
        servico_enriquecido = {
            **servico_data,
            'prazo_estruturado': prazo_estruturado,
            'palavras_chave': palavras_chave
        }
        
        texto_otimizado = self.estruturar_texto_rag(servico_enriquecido)
        
        if len(texto_otimizado) > len(texto_rag_original):
            melhorias.append("Texto RAG enriquecido com contexto estruturado")
        
        # 5. Calcular score de qualidade
        score = self._calcular_score_qualidade(servico_data, problemas, melhorias)
        
        # 6. Extrair metadados ricos
        metadados = {
            'prazo_estruturado': {
                'dias': prazo_estruturado.dias_numericos,
                'categoria': prazo_estruturado.categoria,
                'observacoes': prazo_estruturado.observacoes
            },
            'palavras_chave': palavras_chave,
            'publico_alvo_inferido': self._inferir_publico_alvo(servico_data),
            'tipo_processo_inferido': self._inferir_tipo_processo(servico_data),
            'problemas_resolve': [self._inferir_problema_cidadao(
                servico_data.get('titulo', ''),
                servico_data.get('descricao_html', '')
            )],
            'has_html_issues': len(problemas_html) > 0,
            'texto_original_length': len(texto_rag_original),
            'texto_otimizado_length': len(texto_otimizado)
        }
        
        return TextOptimizationResult(
            texto_otimizado=texto_otimizado,
            problemas_encontrados=problemas,
            melhorias_aplicadas=melhorias,
            score_qualidade=score,
            metadados_extraidos=metadados
        )
    
    def _calcular_score_qualidade(self, servico_data: Dict[str, Any], 
                                 problemas: List[str], melhorias: List[str]) -> int:
        """Calcula score de qualidade de 1-10 baseado em critérios objetivos."""
        score = 5  # Base média
        
        # Penalizar problemas
        score -= len(problemas) * 0.5
        
        # Bonificar melhorias
        score += len(melhorias) * 0.3
        
        # Critérios específicos
        titulo = servico_data.get('titulo', '')
        descricao = servico_data.get('descricao_html', '')
        
        # Título claro e específico
        if len(titulo) > 10 and not titulo.startswith('Requerimento'):
            score += 1
        
        # Descrição substancial
        if len(descricao) > 100:
            score += 0.5
        
        # Tem prazo definido
        prazo = servico_data.get('prazo', '')
        if prazo and 'imediato' not in prazo.lower() and 'conforme' not in prazo.lower():
            score += 1
        
        # Normalizar entre 1-10
        return max(1, min(10, int(score)))
    
    def _inferir_publico_alvo(self, servico_data: Dict[str, Any]) -> List[str]:
        """Infere público-alvo baseado no conteúdo do serviço."""
        texto_completo = f"{servico_data.get('titulo', '')} {servico_data.get('descricao_html', '')}".lower()
        
        publicos = []
        
        if any(word in texto_completo for word in ['empresa', 'empresário', 'estabelecimento', 'comercio']):
            publicos.append('empresários')
        
        if any(word in texto_completo for word in ['servidor', 'funcionário público']):
            publicos.append('servidores_publicos')
        
        if any(word in texto_completo for word in ['cidadão', 'munícipe', 'morador', 'pessoa física']):
            publicos.append('cidadaos')
        
        if any(word in texto_completo for word in ['profissional', 'liberal', 'autônomo']):
            publicos.append('profissionais_liberais')
        
        return publicos if publicos else ['geral']
    
    def _inferir_tipo_processo(self, servico_data: Dict[str, Any]) -> str:
        """Infere tipo de processo baseado no conteúdo."""
        texto_completo = f"{servico_data.get('titulo', '')} {servico_data.get('descricao_html', '')}".lower()
        
        if any(word in texto_completo for word in ['vistoria', 'fiscalização', 'análise técnica']):
            return 'operacional_vistoria'
        
        if any(word in texto_completo for word in ['certidão', 'certificado', 'declaração']):
            return 'administrativo_simples'
        
        if any(word in texto_completo for word in ['licença', 'alvará', 'autorização']):
            return 'administrativo_licenca'
        
        if any(word in texto_completo for word in ['agendamento', 'online', 'digital']):
            return 'digital_automatizado'
        
        return 'administrativo_geral'