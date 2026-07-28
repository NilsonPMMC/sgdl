"""
Camada de compatibilidade do Copiloto — FAQ carregada do banco (ver copiloto_faq_service).
"""

from __future__ import annotations

from typing import Any

from .copiloto_faq_service import (
    FaqOrientacaoRegistro,
    aplicar_sugestao_llm,
    carregar_catalogo_faq,
    categorias_orientacao_ativas,
    detectar_faq_por_texto,
    faq_para_dict,
    faq_por_categoria,
    invalidar_cache_faq,
    listar_categorias_para_prompt,
    listar_faq_detalhada_para_prompt,
    montar_motivo_recusa,
    montar_resposta_chat_fora_competencia,
)

# Alias histórico usado em testes e type hints
FaqOrientacao = FaqOrientacaoRegistro


def normalizar_competencia_llm(valor: Any) -> str | None:
    if valor is None:
        return None
    s = str(valor).strip().lower()
    if s in ("sim", "s", "yes", "municipal", "true"):
        return "sim"
    if s in ("nao", "não", "n", "no", "false", "fora"):
        return "nao"
    if s in ("incerto", "duvida", "dúvida", "uncertain", "talvez"):
        return "incerto"
    return None


def normalizar_categoria_orientacao(valor: Any) -> str | None:
    if valor is None or str(valor).strip() == "":
        return None
    cat = str(valor).strip().upper().replace(" ", "_")
    if cat in categorias_orientacao_ativas():
        return cat
    return None
