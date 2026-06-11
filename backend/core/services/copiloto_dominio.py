"""
Domínios operacionais do copiloto: quando não há match forte na carta,
sugere serviços do mesmo eixo (ex.: mobilidade) antes de ir só para tendência.
"""

from __future__ import annotations

from typing import Any

# id → metadados para triagem e UI
DOMINIOS_OPERACIONAIS: dict[str, dict[str, Any]] = {
    "mobilidade_transito": {
        "label": "Mobilidade e trânsito",
        "orgao_hint": "Secretaria de Mobilidade e Trânsito",
        "gatilhos": (
            "redutor",
            "redutores",
            "lombada",
            "lombadas",
            "velocidade",
            "sinaliza",
            "sinalização",
            "sinalizacao",
            "semáforo",
            "semaforo",
            "faixa de pedestre",
            "proibido estacionar",
            "pintura de guia",
            "mobilidade",
            "trânsito",
            "transito",
            "semob",
            "via pública",
            "cruzamento",
            "radar",
        ),
        "variantes_triagem": (
            "lombada redutor de velocidade manutenção via",
            "trânsito implantação alteração sinalização lombada",
            "mobilidade urbana secretaria mobilidade trânsito",
            "manutenção revitalização lombada via pública",
        ),
        "titulo_palavras": (
            "trânsito",
            "transito",
            "lombada",
            "redutor",
            "sinaliz",
            "semáforo",
            "semaforo",
            "mobilidade",
            "velocidade",
            "faixa",
            "guia",
        ),
    },
    "pavimentacao": {
        "label": "Pavimentação e vias",
        "orgao_hint": "Secretaria de Obras",
        "gatilhos": (
            "buraco",
            "buracos",
            "cratera",
            "tapa",
            "asfalto",
            "paviment",
            "afundamento",
            "esburacad",
            "nivelamento",
            "nivelamentos",
            "cascalhamento",
            "cascalhamentos",
            "cascalho",
            "estrada municipal",
        ),
        "variantes_triagem": (
            "tapa buraco cratera via pública",
            "reparo pavimentação asfalto",
            "nivelamento cascalhamento estrada municipal",
        ),
        "titulo_palavras": (
            "tapa",
            "burac",
            "paviment",
            "asfalto",
            "cratera",
            "nivelamento",
            "cascalh",
        ),
    },
    "limpeza_urbana": {
        "label": "Limpeza urbana",
        "orgao_hint": "Secretaria de Serviços Urbanos",
        "gatilhos": (
            "sujeira",
            "sujo",
            "varri",
            "varricao",
            "lixo",
            "entulho",
            "coleta",
            "limpeza",
            "capina",
        ),
        "variantes_triagem": ("varrição limpeza rua sujeira coleta",),
        "titulo_palavras": ("varri", "lixo", "coleta", "limpeza", "entulho", "capina"),
    },
    "transporte_coletivo": {
        "label": "Transporte coletivo",
        "orgao_hint": "Secretaria de Mobilidade e Trânsito",
        "gatilhos": (
            "transporte coletivo",
            "coletivo municipal",
            "linha ",
            "linha n",
            "linha nº",
            "linha no",
            "ônibus",
            "onibus",
            "veículo",
            "veiculos",
            "veículos",
            "frota",
            "passageiro",
            "passageiros",
            "horário de ônibus",
            "horario de onibus",
            "aumento de veículos",
        ),
        "variantes_triagem": (
            "transporte coletivo alteração linhas ônibus mobilidade",
            "aumento veículos linha transporte coletivo municipal",
            "alteração horários linhas ônibus secretaria mobilidade",
        ),
        "titulo_palavras": (
            "coletivo",
            "linha",
            "ônibus",
            "onibus",
            "horário",
            "horarios",
            "alteração",
            "alteracao",
            "veículo",
            "ponto",
        ),
    },
}


def detectar_dominio_operacional(texto: str) -> dict[str, Any] | None:
    """Retorna domínio operacional mais provável a partir do relato do cidadão."""
    t = (texto or "").lower()
    if not t.strip():
        return None

    melhor_id: str | None = None
    melhor_pts = 0
    for dom_id, meta in DOMINIOS_OPERACIONAIS.items():
        pts = sum(1 for g in meta["gatilhos"] if g in t)
        if pts > melhor_pts:
            melhor_pts = pts
            melhor_id = dom_id

    if not melhor_id or melhor_pts < 1:
        return None

    meta = DOMINIOS_OPERACIONAIS[melhor_id]
    return {
        "id": melhor_id,
        "label": meta["label"],
        "orgao_hint": meta["orgao_hint"],
        "variantes_triagem": list(meta["variantes_triagem"]),
    }


def variantes_triagem_por_dominio(texto: str) -> list[str]:
    dom = detectar_dominio_operacional(texto)
    if not dom:
        return []
    return list(dom.get("variantes_triagem") or [])


def candidatos_relevantes_dominio(
    candidatos: list[dict[str, Any]],
    dominio: dict[str, Any],
    *,
    score_minimo: float = 0.35,
    limite: int = 8,
) -> list[dict[str, Any]]:
    """Filtra candidatos da carta alinhados ao domínio (órgão/título)."""
    if not candidatos or not dominio:
        return []

    dom_id = dominio.get("id")
    meta = DOMINIOS_OPERACIONAIS.get(dom_id or "", {})
    palavras = meta.get("titulo_palavras") or ()
    orgao_hint = (dominio.get("orgao_hint") or meta.get("orgao_hint") or "").lower()

    out: list[dict[str, Any]] = []
    for c in candidatos:
        if not isinstance(c, dict) or c.get("servico_id") is None:
            continue
        score = float(c.get("score") or 0.0)
        if score < score_minimo:
            continue
        tit = (c.get("titulo") or "").lower()
        org = (c.get("orgao") or "").lower()
        if palavras and any(p in tit for p in palavras):
            out.append(c)
        elif orgao_hint and orgao_hint[:10] in org:
            out.append(c)

    out.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
    return out[:limite]
