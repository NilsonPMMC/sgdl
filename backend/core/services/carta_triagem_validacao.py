"""
Geração de frases-teste e validação de retrieval por serviço (Carta otimizada).
"""

from __future__ import annotations

import re
from typing import Any

from django.conf import settings

from core.models_carta_otimizada import ServicoOtimizado
from core.services.triagem_otimizada_service import TriagemOtimizadaService
from core.services.vector_service import VectorService


def limiar_triagem_carta() -> float:
    return float(getattr(settings, "COPILOTO_CARTA_SCORE_MINIMO", 0.6666))


def gerar_frases_teste(servico: ServicoOtimizado, *, com_llm: bool = False) -> list[str]:
    """Frases coloquiais esperadas para recuperar este serviço."""
    titulo = (servico.titulo_otimizado or "").strip()
    assunto = titulo.split(":", 1)[-1].strip() if ":" in titulo else titulo
    prefixo = titulo.split(":", 1)[0].strip().lower() if ":" in titulo else ""

    frases: list[str] = []
    seen: set[str] = set()

    def add(texto: str) -> None:
        t = re.sub(r"\s+", " ", (texto or "").strip().lower())
        if t and t not in seen and len(t) >= 8:
            seen.add(t)
            frases.append(t)

    add(assunto)
    add(f"solicitação de {assunto.lower()}")
    add(f"preciso de {assunto.lower()}")

    tl = titulo.lower()
    if "procon" in tl or "consumidor" in tl:
        add("proteção ao consumidor")
        add("atendimento de proteção ao consumidor")
        add("defesa do consumidor reclamação")
    if "ronda" in tl:
        add("intensificar rondas escolares no bairro")
    if "táxi" in tl or "taxi" in tl:
        add("inscrição de taxista")
    if "tapa" in tl or "buraco" in tl:
        add("buraco na rua")

    if com_llm:
        frases_llm = _frases_via_llm(servico)
        for f in frases_llm:
            add(f)

    return frases[:5]


def _frases_via_llm(servico: ServicoOtimizado) -> list[str]:
    from core.services.llm_service import LLMService

    llm = LLMService()
    prompt = (
        f"Serviço público municipal: «{servico.titulo_otimizado}»\n"
        f"Descrição: {(servico.descricao_objetiva or '')[:250]}\n\n"
        "Liste 3 frases curtas que um cidadão comum usaria para pedir ESTE serviço "
        "(uma por linha, sem numeração, linguagem coloquial)."
    )
    raw = llm.completar_texto(
        "Você gera frases de teste para busca semântica em carta de serviços.",
        prompt,
    )
    if not raw:
        return []
    out: list[str] = []
    for line in raw.splitlines():
        line = re.sub(r"^[\d\.\-\*\)]+\s*", "", line.strip())
        if len(line) >= 8:
            out.append(line.lower())
    return out[:3]


def avaliar_frases_servico(
    servico: ServicoOtimizado,
    frases: list[str] | None = None,
    *,
    top_k: int = 5,
    limiar: float | None = None,
    posicao_max: int = 3,
) -> dict[str, Any]:
    """Valida se o serviço é recuperado nas frases-teste."""
    lim = limiar if limiar is not None else limiar_triagem_carta()
    sid = servico.sinapse_servico_id
    frases = frases or gerar_frases_teste(servico)
    triagem = TriagemOtimizadaService()
    vector = VectorService()

    detalhes: list[dict[str, Any]] = []
    ok_count = 0

    for frase in frases:
        emb = vector.generate_embedding(frase)
        if not emb:
            detalhes.append({"frase": frase, "ok": False, "motivo": "embedding_vazio"})
            continue
        resultados = triagem.buscar_servico_sinapse(emb, top_k=top_k, texto_consulta=frase)
        pos = None
        score = 0.0
        for i, r in enumerate(resultados, 1):
            if int(r.get("servico_id") or 0) == sid:
                pos = i
                score = float(r.get("score") or 0)
                break
        top = resultados[0] if resultados else {}
        ok = pos is not None and pos <= posicao_max and score >= lim
        if ok:
            ok_count += 1
        detalhes.append({
            "frase": frase,
            "ok": ok,
            "posicao": pos,
            "score": round(score, 4),
            "top1_id": top.get("servico_id"),
            "top1_titulo": (top.get("titulo") or "")[:60],
            "top1_score": round(float(top.get("score") or 0), 4),
        })

    return {
        "sinapse_servico_id": sid,
        "titulo": servico.titulo_otimizado,
        "versao_otimizacao": servico.versao_otimizacao,
        "frases_testadas": len(frases),
        "frases_ok": ok_count,
        "aprovado": ok_count >= max(1, len(frases) // 2),
        "detalhes": detalhes,
    }


def listar_servicos_genericos():
    from core.services.carta_rag_builder import _detectar_categoria

    out: list[ServicoOtimizado] = []
    for s in ServicoOtimizado.objects.filter(ativo=True).order_by("id"):
        cat = _detectar_categoria(s.titulo_otimizado, s.descricao_objetiva or "")
        if cat == "generico":
            out.append(s)
    return out
