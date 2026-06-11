"""
Serviço de triagem otimizada usando a base local de serviços otimizados.

Substitui o TriagemService original que consulta diretamente o Sinapse,
usando a nova base otimizada com embeddings de alta qualidade.

Mantém compatibilidade total com a interface original.
"""

import logging
import re
from typing import Any, List, Dict
from django.db.models import Q
from pgvector.django import CosineDistance

from core.models_carta_otimizada import ServicoOtimizado
from core.services.triagem_service import TriagemService
from core.services.vector_service import VectorService

logger = logging.getLogger(__name__)

# Mapeamento de sinônimos para expansão lexical
SINONIMOS_SERVICOS = {
    'cratera': ['buraco', 'buraco grande', 'tapa buraco', 'reparo na rua', 'afundamento na via'],
    'buraco': ['cratera', 'tapa buraco', 'asfalto quebrado', 'reparo de via', 'pavimentação'],
    'buracos': ['cratera', 'tapa buraco', 'via esburacada', 'reparo'],
    'reparo': ['tapa buraco', 'manutenção', 'conserto', 'pavimentação'],
    'acidente': ['buraco', 'cratera', 'via perigosa', 'desvio'],
    'poste': ['iluminação pública', 'luz da rua', 'lâmpada'],
    'mato': ['poda', 'capina', 'vegetação alta', 'mato alto'],
    'lixo': ['coleta de lixo', 'limpeza', 'resíduo', 'entulho'],
    'esgoto': ['saneamento', 'fossa', 'vazamento'],
    'água': ['abastecimento', 'falta de água', 'caixa d\'água'],
    'agua': ['abastecimento', 'falta de água', 'vazamento'],
    'cachorro': ['animal', 'cão', 'pet', 'recolhimento'],
    'gato': ['animal', 'felino', 'pet'],
    'sujeira': ['varrição', 'limpeza urbana', 'rua suja', 'lixo', 'entulho'],
    'sujo': ['sujeira', 'varrição', 'limpeza', 'rua suja'],
    'varrição': ['varricao', 'limpeza de rua', 'sujeira', 'rua suja'],
    'varricao': ['varrição', 'limpeza', 'sujeira'],
    'taxista': ['táxi', 'taxi', 'alvará de táxi', 'renovação alvará táxi', 'permissão táxi', 'inscrição motorista auxiliar'],
    'taxistas': ['táxi', 'taxi', 'alvará taxista'],
    'taxi': ['táxi', 'taxista', 'alvará táxi', 'renovação alvará'],
    'táxi': ['taxi', 'taxista', 'alvará', 'motorista de táxi'],
    'estacionar': ['proibido estacionar', 'sinalização', 'placa', 'trânsito'],
    'sinalização': ['sinalizacao', 'proibido estacionar', 'pintura de guia', 'trânsito'],
    'sinalizacao': ['sinalização', 'proibido estacionar', 'pintura de guia'],
    'guia': ['pintura de guia', 'sinalização horizontal', 'calçada', 'trânsito'],
    'ronda': ['rondas', 'guarda civil', 'gcm', 'patrimônio público', 'segurança escolar'],
    'rondas': ['ronda', 'guarda civil', 'patrimônio', 'escola'],
    'consumidor': ['procon', 'proteção ao consumidor', 'defesa do consumidor', 'reclamação'],
    'procon': ['consumidor', 'proteção ao consumidor', 'defesa do consumidor', 'reclamação'],
    'redutor': ['lombada', 'lombadas', 'velocidade', 'trânsito', 'transito', 'mobilidade'],
    'redutores': ['lombada', 'redutor de velocidade', 'trânsito'],
    'lombada': ['redutor', 'redutor de velocidade', 'velocidade', 'trânsito', 'manutenção lombada'],
    'lombadas': ['lombada', 'redutor', 'trânsito'],
    'revitalização': ['manutenção', 'reparo', 'conservação', 'lombada', 'via'],
    'revitalizacao': ['manutenção', 'reparo', 'lombada', 'via'],
    'manutenção': ['manutencao', 'reparo', 'conservação', 'revitalização'],
    'manutencao': ['manutenção', 'reparo', 'lombada'],
    'nivelamento': ['cascalhamento', 'cascalho', 'estrada municipal', 'conservação de via', 'pavimentação'],
    'nivelamentos': ['nivelamento', 'cascalhamento', 'estrada'],
    'cascalhamento': ['nivelamento', 'cascalho', 'estrada municipal', 'conservação de via'],
    'cascalhamentos': ['nivelamento', 'cascalhamento', 'estrada'],
    'cascalho': ['nivelamento', 'cascalhamento', 'estrada municipal'],
    'coletivo': ['transporte coletivo', 'linha ônibus', 'mobilidade'],
    'linha': ['transporte coletivo', 'ônibus', 'alteração linhas', 'horários'],
}

def expandir_consulta_lexical(texto_original: str) -> str:
    """
    Expande consulta com sinônimos para melhorar busca semântica.
    
    Args:
        texto_original: Texto da consulta original
        
    Returns:
        Texto expandido com sinônimos relevantes
    """
    if not texto_original:
        return texto_original
        
    texto_expandido = texto_original.lower()
    
    # Adiciona sinônimos se palavra-chave encontrada
    for palavra_chave, lista_sinonimos in SINONIMOS_SERVICOS.items():
        if palavra_chave in texto_expandido:
            # Adiciona sinônimos mais relevantes (máximo 2)
            texto_expandido += f' {" ".join(lista_sinonimos[:2])}'
    
    return texto_expandido


class TriagemOtimizadaService:
    """
    Serviço de triagem usando base otimizada local.
    
    Substitui consultas ao Sinapse por consultas à base otimizada,
    mantendo interface compatível com TriagemService original.
    """
    
    def __init__(self):
        self.triagem_original = TriagemService()  # Fallback se necessário
    
    def buscar_servico_sinapse(
        self,
        embedding_demanda: List[float],
        top_k: int = 3,
        texto_consulta: str | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Busca serviços na base otimizada usando embedding.
        
        Mantém interface idêntica ao TriagemService original para 
        compatibilidade total com código existente.
        
        Args:
            embedding_demanda: Embedding 1024d da demanda
            top_k: Número de resultados a retornar
            texto_consulta: Texto opcional para reforço lexical
            
        Returns:
            Lista de serviços com scores de similaridade
        """
        try:
            # EXPANSÃO LEXICAL: Se há texto de consulta, expande com sinônimos
            embedding_final = embedding_demanda
            if texto_consulta:
                texto_expandido = expandir_consulta_lexical(texto_consulta)
                if texto_expandido != texto_consulta.lower():
                    # Regenerar embedding com consulta expandida
                    logger.info(
                        "TriagemOtimizada: expandindo '%s' → '%s'", 
                        texto_consulta[:50], texto_expandido[:80]
                    )
                    vector_svc = VectorService()
                    embedding_expandido = vector_svc.generate_embedding(texto_expandido)
                    if embedding_expandido and len(embedding_expandido) == 1024:
                        embedding_final = embedding_expandido
            
            # Usar base otimizada com embedding (possivelmente expandido)
            resultados = self._buscar_via_base_otimizada(
                embedding_final, top_k, texto_consulta
            )
            
            # Se encontrou resultados suficientes, usar base otimizada
            if len(resultados) >= max(1, top_k // 2):
                logger.debug(
                    f"TriagemOtimizada: encontrados {len(resultados)} via base otimizada"
                )
                return resultados[:top_k]
            
            # Fallback para base original se poucos resultados
            logger.warning(
                f"TriagemOtimizada: poucos resultados ({len(resultados)}) "
                f"na base otimizada, usando fallback Sinapse"
            )
            return self.triagem_original.buscar_servico_sinapse(
                embedding_demanda, top_k, texto_consulta
            )
            
        except Exception as e:
            logger.error(f"TriagemOtimizada: erro na busca otimizada: {str(e)}")
            # Fallback completo para sistema original
            return self.triagem_original.buscar_servico_sinapse(
                embedding_demanda, top_k, texto_consulta
            )
    
    def _buscar_via_base_otimizada(
        self,
        embedding_demanda: List[float], 
        top_k: int,
        texto_consulta: str | None = None
    ) -> List[Dict[str, Any]]:
        """Busca principal na base otimizada com pgvector."""
        
        if not embedding_demanda or len(embedding_demanda) != 1024:
            logger.warning("TriagemOtimizada: embedding inválido ou dimensão incorreta")
            return []
        
        # Busca vetorial principal (aumentar fetch para melhor qualidade)
        resultados_vetorial = self._buscar_pgvector_otimizado(embedding_demanda, top_k * 3)
        
        # Log para debug
        logger.debug(f"TriagemOtimizada: {len(resultados_vetorial)} resultados vetoriais")
        
        # Se busca vetorial falhou, tentar lexical
        if not resultados_vetorial and texto_consulta and texto_consulta.strip():
            logger.info("TriagemOtimizada: falback para busca lexical")
            resultados_vetorial = self._buscar_lexical_otimizado(texto_consulta, top_k)
        elif texto_consulta and texto_consulta.strip():
            resultados_lexical = self._buscar_lexical_otimizado(texto_consulta, max(top_k * 5, 15))
            if resultados_lexical:
                resultados_vetorial = self._mesclar_resultados(
                    resultados_vetorial, resultados_lexical, top_k * 4
                )
        
        if texto_consulta and texto_consulta.strip():
            resultados_vetorial = self._aplicar_boost_dominio_consulta(
                texto_consulta, resultados_vetorial
            )

        resultados_filtrados = [
            r for r in resultados_vetorial
            if r.get('score', 0) > 0.1
        ]

        return resultados_filtrados[:top_k]
    
    def _buscar_pgvector_otimizado(
        self, 
        embedding_demanda: List[float], 
        limit: int
    ) -> List[Dict[str, Any]]:
        """Busca vetorial usando embeddings otimizados."""
        
        try:
            # Query pgvector na base otimizada
            queryset = (
                ServicoOtimizado.objects
                .filter(
                    ativo=True,
                    embedding_otimizado__isnull=False
                )
                .annotate(
                    distancia=CosineDistance('embedding_otimizado', embedding_demanda)
                )
                .order_by('distancia')
                [:limit]
            )
            
            resultados = []
            for servico in queryset:
                # Calcular score de similaridade (1 - distancia)
                distancia = float(servico.distancia)
                score = 1.0 - distancia
                
                # Buscar metadados do serviço original se necessário
                categoria_nome = self._obter_categoria_nome(servico.sinapse_servico_id)
                orgao_nome = self._obter_orgao_nome(servico.sinapse_servico_id)
                
                resultado = {
                    "servico_id": servico.sinapse_servico_id,  # ID original do Sinapse
                    "titulo": servico.titulo_otimizado,
                    "orgao": orgao_nome,
                    "categoria": categoria_nome,
                    "score": round(score, 4),
                    "distancia": round(distancia, 6),
                    "fonte": "base_otimizada",  # Identificador da fonte
                    "score_qualidade": servico.score_qualidade_otimizado,
                    "texto_rag": servico.texto_rag_otimizado[:200] + "..." if len(servico.texto_rag_otimizado) > 200 else servico.texto_rag_otimizado
                }
                resultados.append(resultado)
            
            logger.debug(f"TriagemOtimizada: {len(resultados)} resultados pgvector")
            return resultados
            
        except Exception as e:
            logger.error(f"TriagemOtimizada: erro pgvector - {str(e)}")
            return []
    
    def _buscar_lexical_otimizado(
        self, 
        texto_consulta: str, 
        limit: int
    ) -> List[Dict[str, Any]]:
        """Busca lexical complementar na base otimizada."""
        
        try:
            # Extrair termos de busca
            termos = self._extrair_termos_busca(texto_consulta)
            if not termos:
                return []
            
            # Query lexical em campos otimizados
            q_filter = Q()
            for termo in termos:
                q_filter |= (
                    Q(titulo_otimizado__icontains=termo) |
                    Q(descricao_objetiva__icontains=termo) |
                    Q(texto_rag_otimizado__icontains=termo) |
                    Q(palavras_chave__icontains=termo)
                )
            
            queryset = (
                ServicoOtimizado.objects
                .filter(ativo=True)
                .filter(q_filter)
                .distinct()
                [:limit]
            )
            
            resultados = []
            for servico in queryset:
                # Score lexical baseado em matches
                score_lexical = self._calcular_score_lexical(servico, termos)
                
                resultado = {
                    "servico_id": servico.sinapse_servico_id,
                    "titulo": servico.titulo_otimizado,
                    "orgao": self._obter_orgao_nome(servico.sinapse_servico_id),
                    "categoria": self._obter_categoria_nome(servico.sinapse_servico_id),
                    "score": score_lexical,
                    "distancia": 1.0 - score_lexical,
                    "fonte": "base_otimizada_lexical",
                    "score_qualidade": servico.score_qualidade_otimizado
                }
                resultados.append(resultado)
            
            logger.debug(f"TriagemOtimizada: {len(resultados)} resultados lexicais")
            return resultados
            
        except Exception as e:
            logger.error(f"TriagemOtimizada: erro busca lexical - {str(e)}")
            return []
    
    def _extrair_termos_busca(self, texto: str) -> List[str]:
        """Extrai termos relevantes para busca lexical (com expansão de sinônimos)."""
        import re

        texto_expandido = expandir_consulta_lexical(texto)
        texto_limpo = re.sub(r"[^\w\s]", " ", texto_expandido.lower())
        palavras = texto_limpo.split()

        stopwords = {
            "de", "da", "do", "em", "na", "no", "para", "com", "por", "e", "o", "a",
            "que", "um", "uma", "os", "as", "se", "ao", "dos", "das",
        }
        termos = [p for p in palavras if len(p) >= 3 and p not in stopwords]

        if "cratera" in texto.lower() and "buraco" not in termos:
            termos.append("buraco")
        if "buraco" in texto.lower() and "cratera" not in termos:
            termos.append("cratera")

        vistos: set[str] = set()
        unicos: list[str] = []
        for t in termos:
            if t not in vistos:
                vistos.add(t)
                unicos.append(t)
        return unicos[:12]
    
    def _calcular_score_lexical(self, servico: ServicoOtimizado, termos: List[str]) -> float:
        """Calcula score de relevância lexical com peso forte no título e palavras-chave."""
        if not termos:
            return 0.0

        titulo = (servico.titulo_otimizado or "").lower()
        rag = (servico.texto_rag_otimizado or "").lower()
        palavras = " ".join(servico.palavras_chave or []).lower()

        matches_titulo = sum(1 for t in termos if t in titulo)
        matches_rag = sum(1 for t in termos if t in rag)
        matches_kw = sum(1 for t in termos if t in palavras)

        score = (
            (matches_titulo / len(termos)) * 0.5
            + (matches_kw / len(termos)) * 0.35
            + (matches_rag / len(termos)) * 0.15
        )

        # Bônus: termo forte no título (ex.: "buraco" em "Tapa Buraco")
        for termo in termos:
            if termo in titulo and len(termo) >= 4:
                score += 0.25

        return min(0.98, score)

    def _detectar_dominio_consulta(self, texto: str) -> str | None:
        """Classifica a intenção da consulta — evita boost de buraco só por conter 'rua'."""
        t = texto.lower()
        if any(
            w in t
            for w in (
                "buraco", "buracos", "cratera", "crateras", "tapa", "asfalto",
                "paviment", "reparo", "esburacad", "afundamento",
                "nivelamento", "nivelamentos", "cascalhamento", "cascalhamentos", "cascalho",
            )
        ):
            return "pavimentacao"
        if any(
            w in t
            for w in (
                "sujeira", "sujo", "suj", "lixo", "entulho", "varri", "varricao",
                "varredura", "coleta", "limpeza", "resíduo", "residuo", "capina",
                "lixeira", "papel", "resto",
            )
        ):
            return "limpeza"
        if any(w in t for w in ("poste", "lâmpada", "lampada", "ilumina", "luz apagada")):
            return "iluminacao"
        if any(w in t for w in ("água", "agua", "esgoto", "vazamento", "semae")):
            return "saneamento"
        if any(w in t for w in ("cachorro", "gato", "animal", "pet")):
            return "animais"
        if any(w in t for w in ("táxi", "taxi", "taxista", "taxistas")):
            return "transporte_taxi"
        if any(
            w in t
            for w in (
                "transporte coletivo",
                "coletivo municipal",
                "linha ",
                "linha n",
                "linha nº",
                "linha no",
            )
        ) or (
            "coletivo" in t
            and any(w in t for w in ("ônibus", "onibus", "linha", "veículo", "veiculo", "passageiro"))
        ):
            return "transporte_coletivo"
        if any(
            w in t
            for w in (
                "proibido estacionar",
                "pintura de guia",
                "sinaliza",
                "sinalizacao",
                "sinalização",
                "lombada",
                "lombadas",
                "redutor",
                "redutores",
                "faixa de pedestre",
                "velocidade",
                "mobilidade",
                "semáforo",
                "semaforo",
                "revitaliz",
                "manutenção de via",
                "manutencao de via",
            )
        ):
            return "transito_sinalizacao"
        if "ronda" in t or "rondas" in t:
            return "seguranca_ronda"
        if any(
            w in t
            for w in (
                "consumidor", "procon", "proteção ao consumidor", "protecao ao consumidor",
                "defesa do consumidor", "reclamação contra", "reclamacao contra",
            )
        ):
            return "procon_consumidor"
        if ("alvará" in t or "alvara" in t) and any(
            w in t for w in ("renovação", "renovacao", "emissão", "emissao", "solicitação", "solicitacao")
        ):
            if any(w in t for w in ("escolar", "carga", "caminhão", "caminhao", "estacionamento")):
                return None
            # "renovação de alvará" sem modal — não forçar táxi; boost fraco só se título bater
        return None

    def _aplicar_boost_dominio_consulta(
        self, texto_consulta: str, resultados: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Boost/penalização por domínio — não usar 'rua' isolada como gatilho de buraco."""
        dominio = self._detectar_dominio_consulta(texto_consulta)
        if not dominio:
            return resultados

        texto = texto_consulta.lower()
        titulo_pavimentacao = (
            "tapa", "buraco", "paviment", "asfalto", "nivelamento", "cascalh",
        )
        titulo_limpeza = ("varri", "lixo", "coleta", "limpeza", "entulho", "resíduo", "residuo", "capina")
        titulo_irrelevante = (
            "alvará", "alvara", "conta", "iss", "iptu", "habitação", "habitacao",
            "multa", "cartão", "cartao", "nfe", "nota fiscal", "licenciamento",
        )

        for item in resultados:
            titulo = (item.get("titulo") or "").lower()
            score = float(item.get("score", 0))

            if dominio == "pavimentacao":
                if any(m in titulo for m in titulo_pavimentacao):
                    bonus = 0.35 if "buraco" in texto or "cratera" in texto else 0.28
                    score = min(0.99, score + bonus)
                elif any(m in titulo for m in titulo_irrelevante):
                    score = max(0.05, score - 0.2)
                elif "via" in titulo and not any(m in titulo for m in titulo_pavimentacao):
                    score = max(0.05, score - 0.15)

            elif dominio == "limpeza":
                if any(m in titulo for m in titulo_limpeza):
                    bonus = 0.38
                    if "sujeira" in texto or "sujo" in texto:
                        bonus = 0.45
                    score = min(0.99, score + bonus)
                elif any(m in titulo for m in titulo_pavimentacao):
                    # Consulta de sujeira não deve ir para tapa-buraco
                    score = max(0.05, score - 0.25)
                elif any(m in titulo for m in titulo_irrelevante):
                    score = max(0.05, score - 0.15)

            elif dominio == "transporte_coletivo":
                titulo_coletivo = (
                    "coletivo",
                    "linha",
                    "ônibus",
                    "onibus",
                    "horário",
                    "horarios",
                    "alteração",
                    "alteracao",
                    "ponto",
                )
                titulo_escolar = ("escolar", "escolares", "vaga", "creche", "pré-escola", "pre-escola", "eja")
                if any(m in titulo for m in titulo_coletivo):
                    bonus = 0.45
                    if "linha" in titulo and re.search(r"linha\s+\d", texto):
                        bonus = 0.58
                    elif "linha" in titulo and "linha" in texto:
                        bonus = 0.52
                    if ("alteração" in titulo or "alteracao" in titulo) and any(
                        w in texto for w in ("veículo", "veiculo", "veículos", "aumento", "frota", "linha")
                    ):
                        bonus = max(bonus, 0.60)
                    score = min(0.99, score + bonus)
                elif any(m in titulo for m in titulo_escolar):
                    score = max(0.05, score - 0.48)

            elif dominio == "transporte_taxi":
                titulo_taxi = ("táxi", "taxi")
                titulo_outra_modal = (
                    "escolar", "carga", "remunerado", "estacionamento",
                    "construção", "construcao", "cemitério", "cemiterio",
                    "funcionamento", "lotação", "lotacao", "demolição", "demolicao",
                )
                if any(m in titulo for m in titulo_taxi):
                    bonus = 0.42
                    if "taxista" in texto or "alvará" in texto or "alvara" in texto:
                        bonus = 0.48
                    score = min(0.99, score + bonus)
                    if any(w in texto for w in ("renovação", "renovacao")):
                        if any(w in titulo for w in ("renovação", "renovacao")) and any(
                            w in titulo for w in ("alvará", "alvara")
                        ):
                            score = min(0.99, score + 0.12)
                        elif not any(w in titulo for w in ("renovação", "renovacao", "alvará", "alvara")):
                            score = max(0.05, score - 0.15)
                elif any(m in titulo for m in titulo_outra_modal):
                    score = max(0.05, score - 0.28)

            elif dominio == "transito_sinalizacao":
                titulo_transito = (
                    "trânsito",
                    "transito",
                    "sinaliz",
                    "lombada",
                    "redutor",
                    "velocidade",
                    "semáforo",
                    "semaforo",
                    "faixa",
                )
                titulo_irrelevante_transito = (
                    "parque", "evento", "show", "cultura", "artista", "iptu", "iss",
                    "cadastro", "programa social", "mapa", "foto",
                )
                if any(m in titulo for m in titulo_transito):
                    bonus = 0.40
                    if "sinaliz" in titulo:
                        bonus = 0.48
                    if "lombad" in titulo or "redutor" in titulo:
                        bonus = 0.52
                    if any(w in texto for w in ("redutor", "lombad", "velocidade", "revitaliz")):
                        if "lombad" in titulo or "redutor" in titulo:
                            bonus = max(bonus, 0.55)
                    score = min(0.99, score + bonus)
                elif any(m in titulo for m in titulo_irrelevante_transito):
                    score = max(0.05, score - 0.30)

            elif dominio == "seguranca_ronda":
                titulo_ronda = ("ronda", "patrimônio", "patrimonio", "guarda")
                titulo_ruido = ("transporte escolar", "vaga", "pré-escola", "pre-escola", "eja", "creche")
                if any(m in titulo for m in titulo_ronda):
                    bonus = 0.42
                    if any(w in texto for w in ("escolar", "escola", "ensino", "colégio", "colegio")):
                        bonus = 0.50
                    score = min(0.99, score + bonus)
                elif any(m in titulo for m in titulo_ruido):
                    score = max(0.05, score - 0.28)

            elif dominio == "procon_consumidor":
                titulo_procon = ("procon", "consumidor")
                titulo_ruido = (
                    "família", "familia", "assistência social", "assistencia social",
                    "atendimento integral", "atendimento especializado",
                )
                if any(m in titulo for m in titulo_procon):
                    bonus = 0.45
                    if "consumidor" in texto or "proteção" in texto or "protecao" in texto:
                        bonus = 0.52
                    score = min(0.99, score + bonus)
                elif any(m in titulo for m in titulo_ruido):
                    score = max(0.05, score - 0.32)

            item["score"] = round(score, 4)

        return sorted(resultados, key=lambda x: x.get("score", 0), reverse=True)
    
    def _mesclar_resultados(
        self,
        vetorial: List[Dict],
        lexical: List[Dict],
        top_k: int
    ) -> List[Dict]:
        """Mescla vetorial + lexical com score híbrido (evita colapso de templates iguais)."""
        merged: dict[int, Dict[str, Any]] = {}

        for item in vetorial:
            sid = item["servico_id"]
            merged[sid] = {**item, "score_vetorial": item.get("score", 0), "score_lexical": 0.0}

        for item in lexical:
            sid = item["servico_id"]
            lex = item.get("score", 0)
            if sid in merged:
                merged[sid]["score_lexical"] = lex
            else:
                merged[sid] = {
                    **item,
                    "score_vetorial": 0.0,
                    "score_lexical": lex,
                }

        for sid, item in merged.items():
            sv = float(item.get("score_vetorial", 0))
            sl = float(item.get("score_lexical", 0))
            # Lexical forte (ex.: buraco + tapa buraco) ganha peso extra
            peso_lex = 0.45 if sl >= 0.5 else 0.25
            hibrido = (1 - peso_lex) * sv + peso_lex * sl
            if sl >= 0.65 and "buraco" in str(item.get("titulo", "")).lower():
                hibrido = max(hibrido, sl * 0.95)
            item["score"] = round(min(0.99, hibrido), 4)
            item["fonte"] = "base_otimizada_hibrida"

        return sorted(merged.values(), key=lambda x: x["score"], reverse=True)[:top_k]
    
    def _obter_categoria_nome(self, sinapse_servico_id: int) -> str | None:
        """Obtém nome da categoria do serviço original."""
        try:
            # Cache simples para evitar queries repetidas
            if not hasattr(self, '_cache_categorias'):
                self._cache_categorias = {}
            
            if sinapse_servico_id in self._cache_categorias:
                return self._cache_categorias[sinapse_servico_id]
            
            # Buscar no Sinapse se necessário
            from integrations.models_sinapse import CatalogServico, SINAPSE_DB_ALIAS
            
            servico = CatalogServico.objects.using(SINAPSE_DB_ALIAS).select_related(
                'id_categoria'
            ).filter(id=sinapse_servico_id).first()
            
            categoria = servico.id_categoria.nome if servico and servico.id_categoria else None
            self._cache_categorias[sinapse_servico_id] = categoria
            return categoria
            
        except Exception:
            return None
    
    def _obter_orgao_nome(self, sinapse_servico_id: int) -> str | None:
        """Obtém nome do órgão do serviço original."""
        try:
            # Cache simples para evitar queries repetidas  
            if not hasattr(self, '_cache_orgaos'):
                self._cache_orgaos = {}
                
            if sinapse_servico_id in self._cache_orgaos:
                return self._cache_orgaos[sinapse_servico_id]
            
            # Buscar no Sinapse se necessário
            from integrations.models_sinapse import CatalogServico, SINAPSE_DB_ALIAS
            
            servico = CatalogServico.objects.using(SINAPSE_DB_ALIAS).select_related(
                'id_orgao'
            ).filter(id=sinapse_servico_id).first()
            
            orgao = servico.id_orgao.nome if servico and servico.id_orgao else None
            self._cache_orgaos[sinapse_servico_id] = orgao
            return orgao
            
        except Exception:
            return None
    
    def estatisticas_base_otimizada(self) -> Dict[str, Any]:
        """Retorna estatísticas da base otimizada para monitoramento."""
        try:
            from django.db import models
            
            stats = ServicoOtimizado.objects.aggregate(
                total=models.Count('id'),
                ativos=models.Count('id', filter=models.Q(ativo=True)),
                com_embedding=models.Count('id', filter=models.Q(embedding_otimizado__isnull=False)),
                score_medio=models.Avg('score_qualidade_otimizado'),
                validados=models.Count('id', filter=models.Q(validado_humano=True))
            )
            
            return {
                'total_servicos': stats['total'],
                'servicos_ativos': stats['ativos'],
                'com_embedding': stats['com_embedding'],
                'score_medio': round(stats['score_medio'] or 0, 2),
                'validados_humano': stats['validados'],
                'cobertura_embedding': round(stats['com_embedding'] / stats['total'] * 100, 1) if stats['total'] > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas: {str(e)}")
            return {}


class AdapterTriagemOtimizada:
    """
    Adapter para substituir TriagemService transparentemente.
    
    Permite ativar/desativar a base otimizada via configuração.
    """
    
    def __init__(self, usar_base_otimizada: bool = True):
        self.usar_base_otimizada = usar_base_otimizada
        self.triagem_otimizada = TriagemOtimizadaService()
        self.triagem_original = TriagemService()
        
        logger.info(
            f"AdapterTriagem: usando {'base otimizada' if usar_base_otimizada else 'Sinapse original'}"
        )
    
    def buscar_servico_sinapse(self, *args, **kwargs):
        """Interface unificada que escolhe a implementação baseada na configuração."""
        if self.usar_base_otimizada:
            return self.triagem_otimizada.buscar_servico_sinapse(*args, **kwargs)
        else:
            return self.triagem_original.buscar_servico_sinapse(*args, **kwargs)