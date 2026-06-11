"""
Sincroniza prazo, documentos e taxas do catálogo Sinapse para ServicoOtimizado.

Referência operacional única (prazo completo do serviço), sem fatiamento de etapas.
"""

from __future__ import annotations

import re
from typing import Any

from integrations.models_sinapse import CatalogServico
from integrations.sinapse_catalog import _strip_html, parse_prazo_dias

RAG_GESTAO_MARKER = "## Gestão operacional (Sinapse)"

_PAG_RE = re.compile(
    r"\b(taxa|gratuit|isent|valor|R\$\s*\d|pagamento|custo|emolumento|preco|preço|tarifa)\b",
    re.I,
)


def extrair_lista_html(html: str | None) -> list[str]:
    """Extrai itens de listas HTML ou texto segmentado."""
    if not html or not str(html).strip():
        return []

    raw = str(html)
    items = re.findall(r"<li[^>]*>(.*?)</li>", raw, re.I | re.S)
    if items:
        out = [_strip_html(x) for x in items]
        return [x for x in out if len(x) >= 2]

    text = _strip_html(raw)
    if not text:
        return []

    if ";" in text:
        parts = [p.strip() for p in text.split(";")]
    else:
        parts = re.split(r"\n+|(?:\s*[-•]\s+)", text)

    return [p.strip() for p in parts if len(p.strip()) > 3]


def inferir_prazo_categoria(dias: int | None, texto_prazo: str) -> str:
    if dias is not None:
        if dias == 0:
            return "IMEDIATO"
        if dias <= 7:
            return "RAPIDO"
        if dias <= 30:
            return "NORMAL"
        return "LONGO"
    texto = (texto_prazo or "").lower()
    if re.search(r"\bimediato\b|\binstant", texto):
        return "IMEDIATO"
    if texto.strip():
        return "VARIAVEL"
    return ""


def extrair_pagamentos_sinapse(sin: CatalogServico) -> list[str]:
    fontes = (
        sin.requisitos_html,
        sin.observacoes_html,
        sin.agendamento,
        sin.documentos_necessarios,
        sin.descricao_html,
    )
    vistos: set[str] = set()
    out: list[str] = []

    for html in fontes:
        text = _strip_html(html)
        if not text or not _PAG_RE.search(text):
            continue
        for sent in re.split(r"[.\n;]+", text):
            s = sent.strip()
            if len(s) < 8 or not _PAG_RE.search(s):
                continue
            chave = s.lower()
            if chave in vistos:
                continue
            vistos.add(chave)
            out.append(s)

    texto_agregado = " ".join(_strip_html(h) for h in fontes if h).lower()
    if not out and "gratuit" in texto_agregado:
        out.append("Serviço gratuito (conforme catálogo Sinapse).")

    return out[:10]


def extrair_campos_gestao_sinapse(sin: CatalogServico) -> dict[str, Any]:
    prazo_obs = _strip_html(sin.prazo)
    prazo_dias = parse_prazo_dias(sin.prazo)
    return {
        "prazo_dias": prazo_dias,
        "prazo_categoria": inferir_prazo_categoria(prazo_dias, prazo_obs),
        "prazo_observacoes": prazo_obs,
        "dependencias_documentos": extrair_lista_html(sin.documentos_necessarios),
        "dependencias_realizacao": extrair_lista_html(sin.requisitos_html)[:15],
        "dependencias_pagamentos": extrair_pagamentos_sinapse(sin),
    }


def montar_bloco_gestao_operacional(
    *,
    prazo_dias: int | None,
    prazo_categoria: str,
    prazo_observacoes: str,
    dependencias_documentos: list[str],
    dependencias_pagamentos: list[str],
    dependencias_realizacao: list[str] | None = None,
) -> str:
    linhas = [RAG_GESTAO_MARKER]

    if prazo_dias is not None:
        cat = prazo_categoria.replace("_", " ").title() if prazo_categoria else ""
        sufixo = f" ({cat})" if cat else ""
        linhas.append(f"Prazo estimado do serviço: {prazo_dias} dias{sufixo}.")
    elif prazo_observacoes:
        linhas.append(f"Prazo do serviço: {prazo_observacoes}.")

    if dependencias_documentos:
        docs = "; ".join(dependencias_documentos[:12])
        linhas.append(f"Documentos necessários: {docs}.")

    if dependencias_pagamentos:
        taxas = "; ".join(dependencias_pagamentos[:8])
        linhas.append(f"Taxas e pagamentos: {taxas}.")

    if dependencias_realizacao:
        reqs = "; ".join(dependencias_realizacao[:8])
        linhas.append(f"Pré-requisitos: {reqs}.")

    return "" if len(linhas) == 1 else "\n".join(linhas)


def montar_bloco_gestao_de_servico(servico) -> str:
    return montar_bloco_gestao_operacional(
        prazo_dias=servico.prazo_dias,
        prazo_categoria=servico.prazo_categoria or "",
        prazo_observacoes=servico.prazo_observacoes or "",
        dependencias_documentos=servico.dependencias_documentos or [],
        dependencias_pagamentos=servico.dependencias_pagamentos or [],
        dependencias_realizacao=servico.dependencias_realizacao or [],
    )


def aplicar_bloco_gestao_no_rag(texto_rag: str, bloco: str) -> str:
    base = (texto_rag or "").rstrip()
    idx = base.find(RAG_GESTAO_MARKER)
    if idx >= 0:
        base = base[:idx].rstrip()
    if not bloco:
        return base
    return f"{base}\n\n{bloco}" if base else bloco


def gestao_operacional_para_copiloto(sinapse_servico_id: int | None) -> dict[str, Any] | None:
    if not sinapse_servico_id:
        return None
    from core.models_carta_otimizada import ServicoOtimizado

    local = (
        ServicoOtimizado.objects.filter(sinapse_servico_id=sinapse_servico_id, ativo=True)
        .only(
            "prazo_dias",
            "prazo_categoria",
            "prazo_observacoes",
            "dependencias_documentos",
            "dependencias_pagamentos",
            "dependencias_realizacao",
            "sistema_solicitacao",
            "link_sistema",
        )
        .first()
    )
    if not local:
        return None

    tem_dado = any(
        [
            local.prazo_dias is not None,
            bool(local.prazo_observacoes),
            bool(local.dependencias_documentos),
            bool(local.dependencias_pagamentos),
            bool(local.dependencias_realizacao),
        ]
    )
    if not tem_dado:
        return None

    return {
        "prazo_dias": local.prazo_dias,
        "prazo_categoria": local.prazo_categoria or None,
        "prazo_observacoes": local.prazo_observacoes or None,
        "documentos": list(local.dependencias_documentos or []),
        "pagamentos": list(local.dependencias_pagamentos or []),
        "pre_requisitos": list(local.dependencias_realizacao or []),
        "sistema_solicitacao": local.sistema_solicitacao or None,
        "link_sistema": local.link_sistema or None,
    }


def sincronizar_gestao_operacional_local(local, sin: CatalogServico) -> tuple[list[str], bool]:
    """
    Aplica campos de gestão operacional no ServicoOtimizado local.
    Retorna (update_fields, rag_alterou).
    """
    campos = extrair_campos_gestao_sinapse(sin)
    update_fields: list[str] = []

    for nome, valor in campos.items():
        atual = getattr(local, nome)
        if atual != valor:
            setattr(local, nome, valor)
            update_fields.append(nome)

    bloco = montar_bloco_gestao_operacional(**campos)
    novo_rag = aplicar_bloco_gestao_no_rag(local.texto_rag_otimizado or "", bloco)
    rag_alterou = novo_rag != (local.texto_rag_otimizado or "")
    if rag_alterou:
        local.texto_rag_otimizado = novo_rag
        update_fields.append("texto_rag_otimizado")

    return update_fields, rag_alterou


def regenerar_embedding_servico(local, vector_service=None) -> bool:
    from core.services.vector_service import VectorService

    vs = vector_service or VectorService()
    texto = (local.texto_rag_otimizado or "").strip()
    if not texto:
        return False
    emb = vs.generate_embedding(texto)
    if not emb:
        return False
    local.embedding_otimizado = emb
    return True
