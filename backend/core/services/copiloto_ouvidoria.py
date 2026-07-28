"""Trilha A′ — Ouvidoria (O1): denúncia, reclamação, sugestão ou elogio → serviço Ouvidoria."""

from __future__ import annotations

import re
from typing import Any

from django.conf import settings

SUBTIPO_DENUNCIA = "denuncia"
SUBTIPO_RECLAMACAO = "reclamacao"
SUBTIPO_SUGESTAO = "sugestao"
SUBTIPO_ELOGIO = "elogio"

SUBTIPOS_OUVIDORIA = (
    SUBTIPO_DENUNCIA,
    SUBTIPO_RECLAMACAO,
    SUBTIPO_SUGESTAO,
    SUBTIPO_ELOGIO,
)

FONTE_AGENTE = "agente"
FONTE_LEITURA_AUTOMATICA = "leitura_automatica"
FONTE_COMBINADA = "combinada"

# Compatibilidade com valores antigos (sessões em andamento).
_ALIASES_FONTE_CLASSIFICACAO = {
    "groq": FONTE_AGENTE,
    "regex": FONTE_LEITURA_AUTOMATICA,
    "hibrido": FONTE_COMBINADA,
}

_ROTULO_SUBTIPO = {
    SUBTIPO_DENUNCIA: "denúncia",
    SUBTIPO_RECLAMACAO: "reclamação",
    SUBTIPO_SUGESTAO: "sugestão",
    SUBTIPO_ELOGIO: "elogio",
}


def _rotulo_subtipo(subtipo: str) -> str:
    return _ROTULO_SUBTIPO.get(subtipo, subtipo.replace("_", " "))

# Pedido operacional municipal (zeladoria etc.) — não é canal Ouvidoria quando isolado.
_PEDIDO_SERVICO_MUNICIPAL_RE = re.compile(
    r"\b("
    r"lombad|burac|tapa|ilumina|luminária|luminaria|poda|árvore|arvore|"
    r"entulho|bueiro|valet|cascalh|paviment|asfalt|coleta|limpeza"
    r")\b",
    re.IGNORECASE,
)

_MARCADORES_SUBTIPO: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        SUBTIPO_ELOGIO,
        (
            r"\belogio\b",
            r"\belogiar\b",
            r"parabenizar",
            r"parabéns",
            r"paraben",
            r"bem\s+atendid",
            r"satisfeit[oa]\s+com\s+(?:o\s+)?(?:atendimento|serviço|servico)",
            r"agrade(?:ço|co)\s+(?:o|a)\s+(?:atendimento|serviço|servico|equipe|prefeitura)",
            r"excelente\s+atendimento",
            r"muito\s+bom\s+atendimento",
            r"elogio\s+ao\s+atendimento",
        ),
    ),
    (
        SUBTIPO_DENUNCIA,
        (
            r"\bdenúnci",
            r"\bdenunci",
            r"denunciar",
            r"ato\s+il[ií]cit",
            r"irregularidade",
            r"corrup",
            r"desvio",
            r"maus[- ]tratos",
            r"abuso\s+de",
            r"comunicar\s+(?:a\s+)?ocorr[eê]ncia",
        ),
    ),
    (
        SUBTIPO_SUGESTAO,
        (
            r"\bsugest",
            r"\bregistr(?:o|ar)\s+(?:uma\s+)?sugest",
            r"sugest(?:ão|ao)\s+para",
            r"proponho",
            r"sugiro",
            r"proposta\s+de\s+melhoria",
            r"ideia\s+(?:para|de)\s+melhor",
            r"seria\s+bom",
            r"recomendo\s+que",
            r"melhoria\s+(?:no|dos|das)\s+(?:atendimento|serviço|servico|processo|serviços|servicos)",
            r"totem\s+de\s+auto",
            r"toten\s+de\s+auto",
            r"auto\s*[- ]?atendimento",
        ),
    ),
    (
        SUBTIPO_RECLAMACAO,
        (
            r"\breclama(?:ção|cao)\b",
            r"insatisfeito",
            r"insatisfação",
            r"insatisfacao",
            r"demonstrar\s+(?:a\s+)?insatisf",
            r"crítica\s+ao\s+(?:atendimento|serviço|servico)",
            r"critica\s+ao\s+(?:atendimento|serviço|servico)",
            r"demora\s+no\s+atendimento",
            r"falta\s+de\s+retorno",
            r"não\s+fui\s+atendid",
            r"nao\s+fui\s+atendid",
            r"mau\s+atendimento",
            r"inefici[eê]ncia",
            r"omiss[aã]o",
        ),
    ),
)

_CANAL_OUVIDORIA_RE = re.compile(
    r"\b("
    r"ouvidoria|"
    r"canal\s+do\s+cidad[aã]o|"
    r"atendimento\s+ao\s+cidad[aã]o|"
    r"\bpac\b|"
    r"posto\s+de\s+atendimento|"
    r"manifesta(?:ção|cao)\s+(?:formal|oficial|na\s+ouvidoria)"
    r")\b",
    re.IGNORECASE,
)


def _normalizar_subtipo_llm(valor: Any) -> str | None:
    if valor is None:
        return None
    s = str(valor).strip().lower().replace(" ", "_")
    aliases = {
        "denúncia": SUBTIPO_DENUNCIA,
        "denuncia": SUBTIPO_DENUNCIA,
        "reclamação": SUBTIPO_RECLAMACAO,
        "reclamacao": SUBTIPO_RECLAMACAO,
        "sugestão": SUBTIPO_SUGESTAO,
        "sugestao": SUBTIPO_SUGESTAO,
        "elogio": SUBTIPO_ELOGIO,
    }
    return aliases.get(s) or (s if s in SUBTIPOS_OUVIDORIA else None)


def _normalizar_teoria_llm(valor: Any) -> bool | None:
    if valor is None:
        return None
    if isinstance(valor, bool):
        return valor
    s = str(valor).strip().lower()
    if s in ("sim", "s", "true", "1", "yes"):
        return True
    if s in ("nao", "não", "n", "false", "0", "no"):
        return False
    return None


def _detectar_subtipo_texto(texto: str) -> tuple[str | None, str]:
    t = (texto or "").strip()
    for sid, patterns in _MARCADORES_SUBTIPO:
        if any(re.search(p, t, re.IGNORECASE) for p in patterns):
            return sid, f"Pedido interpretado automaticamente como {_rotulo_subtipo(sid)}."
    return None, ""


def _tem_intencao_ouvidoria(
    texto: str,
    *,
    subtipo_texto: str | None,
    llm_flag: bool | None,
    llm_sub: str | None,
) -> bool:
    if subtipo_texto or llm_sub:
        return True
    if llm_flag is True:
        return True
    if _CANAL_OUVIDORIA_RE.search(texto or ""):
        return True
    return False


def _resolver_fonte_classificacao(
    *,
    llm_flag: bool | None,
    llm_sub: str | None,
    subtipo_texto: str | None,
    subtipo_final: str,
    tem_canal: bool,
    motivo_texto: str,
) -> tuple[str, str]:
    """Indica se a decisão veio do Agente, da leitura automática ou de ambos."""
    agente_negou = llm_flag is False
    agente_teoria = llm_flag is True
    agente_deu_subtipo = llm_sub is not None and llm_sub == subtipo_final
    leitura_deu_subtipo = subtipo_texto is not None and subtipo_texto == subtipo_final
    rotulo = _rotulo_subtipo(subtipo_final)

    if agente_negou and leitura_deu_subtipo:
        return (
            FONTE_COMBINADA,
            "O Agente não classificou como Ouvidoria; o sistema reclassificou pela "
            f"leitura automática do pedido ({rotulo}).",
        )
    if agente_deu_subtipo:
        return FONTE_AGENTE, f"O Agente classificou como {rotulo}."
    if agente_teoria and leitura_deu_subtipo:
        return (
            FONTE_COMBINADA,
            f"O Agente confirmou manifestação à Ouvidoria; tipo refinado pela "
            f"leitura automática do pedido ({rotulo}).",
        )
    if agente_teoria and subtipo_final == SUBTIPO_RECLAMACAO:
        return FONTE_AGENTE, "O Agente classificou como reclamação à Ouvidoria."
    if tem_canal and subtipo_final == SUBTIPO_RECLAMACAO:
        return (
            FONTE_LEITURA_AUTOMATICA,
            "Canal Ouvidoria ou PAC identificado no pedido.",
        )
    if leitura_deu_subtipo:
        return FONTE_LEITURA_AUTOMATICA, motivo_texto or f"Pedido interpretado como {rotulo}."
    return FONTE_LEITURA_AUTOMATICA, "Leitura automática do pedido (sem classificação do Agente)."


def detectar_teoria_ouvidoria(
    texto: str,
    *,
    llm_teoria: Any = None,
    llm_subtipo: Any = None,
) -> dict[str, Any] | None:
    """
    Detecta trilha Ouvidoria (A′). Retorna dict com subtipo e motivo, ou None.

    Manifestações institucionais (sugestão, elogio, denúncia, reclamação) têm
    prioridade sobre palavras operacionais isoladas (ex.: «instalar totem» dentro
    de uma sugestão ao PAC). Pedidos puramente operacionais (buraco, lombada…)
    não entram na trilha.
    """
    t = (texto or "").strip()
    if len(t) < 8:
        return None

    llm_flag = _normalizar_teoria_llm(llm_teoria)
    llm_sub = _normalizar_subtipo_llm(llm_subtipo)
    subtipo_texto, motivo_texto = _detectar_subtipo_texto(t)
    tem_canal = bool(_CANAL_OUVIDORIA_RE.search(t))

    if not _tem_intencao_ouvidoria(
        t,
        subtipo_texto=subtipo_texto,
        llm_flag=llm_flag,
        llm_sub=llm_sub,
    ):
        if llm_flag is False:
            return None
        if _PEDIDO_SERVICO_MUNICIPAL_RE.search(t):
            return None
        return None

    if llm_flag is False and not subtipo_texto and not llm_sub and not tem_canal:
        return None

    subtipo: str | None = llm_sub or subtipo_texto
    motivo = "Classificação do Agente (manifestação à Ouvidoria)." if llm_sub else motivo_texto

    if tem_canal and not subtipo:
        subtipo = SUBTIPO_RECLAMACAO
        motivo = "Menção explícita ao canal Ouvidoria / atendimento ao cidadão."

    if llm_flag is True and not subtipo:
        subtipo = SUBTIPO_RECLAMACAO
        motivo = "O Agente classificou como manifestação à Ouvidoria."

    if not subtipo:
        return None

    if not motivo:
        motivo = f"Pedido interpretado como {_rotulo_subtipo(subtipo)}."

    fonte, detalhe_fonte = _resolver_fonte_classificacao(
        llm_flag=llm_flag,
        llm_sub=llm_sub,
        subtipo_texto=subtipo_texto,
        subtipo_final=subtipo,
        tem_canal=tem_canal,
        motivo_texto=motivo_texto,
    )

    return {
        "subtipo": subtipo,
        "motivo": motivo,
        "fonte_classificacao": fonte,
        "detalhe_fonte": detalhe_fonte,
        "agente_teoria": llm_flag,
        "agente_subtipo": llm_sub,
        "servico_sinapse_id": ouvidoria_sinapse_servico_id(),
    }


def normalizar_fonte_classificacao_ouvidoria(valor: Any) -> str | None:
    if valor is None:
        return None
    chave = str(valor).strip().lower()
    return _ALIASES_FONTE_CLASSIFICACAO.get(chave, chave)


def ouvidoria_sinapse_servico_id() -> int:
    return int(getattr(settings, "COPILOTO_OUVIDORIA_SINAPSE_SERVICO_ID", 13))


def orientacao_ouvidoria(subtipo: str) -> str:
    textos = {
        SUBTIPO_ELOGIO: (
            "Seu elogio será registrado na Ouvidoria Geral e encaminhado ao setor competente "
            "para ciência e eventual resposta institucional."
        ),
        SUBTIPO_DENUNCIA: (
            "Sua denúncia será protocolada pela Ouvidoria Geral. Quando possível, inclua datas, "
            "locais e detalhes objetivos para apuração."
        ),
        SUBTIPO_SUGESTAO: (
            "Sua sugestão será registrada na Ouvidoria Geral para análise e encaminhamento "
            "aos setores responsáveis."
        ),
        SUBTIPO_RECLAMACAO: (
            "Sua reclamação será registrada na Ouvidoria Geral para acompanhamento e resposta "
            "formal ao cidadão."
        ),
    }
    return textos.get(subtipo, textos[SUBTIPO_RECLAMACAO])
