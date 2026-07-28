"""Regras de visibilidade de tramitações por perfil (P8 — timeline vereador)."""

from __future__ import annotations

import html
import re
from typing import Any

from integrations import sinapse_catalog

# Marcos visíveis ao vereador — fluxo legislativo externo (sem trânsito Protocolo ↔ Secretaria).
TIPOS_TRAMITACAO_VISIVEIS_VEREADOR = frozenset(
    {
        "ENVIO_OFICIAL",
        "CONCLUSAO",
        "CONCLUSAO_FINAL",
        "DEVOLUTIVA_PROTOCOLO",
        "ENCERRAMENTO_DEVOLUTIVA",
    }
)

# Tipos internos sempre ocultos (gestão operacional / trânsito administrativo).
TIPOS_TRAMITACAO_OCULTOS_VEREADOR = frozenset(
    {
        "DESPACHO",
        "SOLICITACAO_DEVOLUTIVA",
        "CIENCIA_VEREADOR",
        "EXECUCAO",
        "ANALISE_TECNICA",
        "COMENTARIO",
        "TRANSFERENCIA",
        "ENCAMINHAMENTO_SETOR",
        "PROGRAMACAO",
        "ATRASO",
        "STATUS_UPDATE",
    }
)

STATUS_EXECUCAO_OPERACIONAL = frozenset(
    {
        "PROTOCOLADO",
        "EM_EXECUCAO",
        "AGUARDANDO_TRANSFERENCIA",
        "AGUARDANDO_DEVOLUTIVA_PROTOCOLO",
    }
)

_RESPOSTA_DEVOLUTIVA_RE = re.compile(r"Resposta:\s*\n(.+)", re.DOTALL | re.IGNORECASE)

TEXTO_INSTITUCIONAL_VEREADOR = {
    "ENVIO_OFICIAL": "Ofício enviado oficialmente ao Protocolo.",
    "CONCLUSAO": "Serviço concluído pela secretaria responsável.",
    "CONCLUSAO_FINAL": "Devolutiva recebida do Protocolo.",
    "DEVOLUTIVA_PROTOCOLO": "Devolutiva recebida do Protocolo.",
    "ENCERRAMENTO_DEVOLUTIVA": "Demanda encerrada após devolutiva ao vereador.",
}

_ROTULO_POR_TIPO = {
    "ENVIO_OFICIAL": "Gabinete Legislativo",
    "CONCLUSAO_FINAL": "Protocolo Legislativo",
    "DEVOLUTIVA_PROTOCOLO": "Protocolo Legislativo",
    "ENCERRAMENTO_DEVOLUTIVA": "Gabinete Legislativo",
}


def _rotulo_unidade(unidade) -> str | None:
    if unidade is None:
        return None
    sigla = (getattr(unidade, "sigla", None) or "").strip()
    nome = (getattr(unidade, "nome", None) or "").strip()
    return sigla or nome or None


def _contexto_orgao_unidade_demanda(demanda) -> tuple[str | None, str | None]:
    if demanda is None:
        return None, None
    orgao_id = getattr(demanda, "sinapse_orgao_id", None)
    orgao_nome = sinapse_catalog.get_orgao_nome(orgao_id) if orgao_id else None
    unidade = getattr(demanda, "unidade_administrativa", None)
    if unidade is None and hasattr(demanda, "unidade_administrativa_id"):
        unidade = demanda.unidade_administrativa
    unidade_nome = _rotulo_unidade(unidade)
    return orgao_nome, unidade_nome


def _contexto_orgao_unidade_tramitacao(tramitacao) -> tuple[str | None, str | None]:
    if tramitacao is None:
        return None, None
    unidade = getattr(tramitacao, "unidade_destino", None) or getattr(
        tramitacao, "unidade_origem", None
    )
    orgao_id = getattr(unidade, "sinapse_orgao_id", None) if unidade else None
    orgao_nome = sinapse_catalog.get_orgao_nome(orgao_id) if orgao_id else None
    unidade_nome = _rotulo_unidade(unidade)
    return orgao_nome, unidade_nome


def rotulo_institucional_tramitacao(
    tipo: str,
    *,
    demanda=None,
    tramitacao=None,
) -> str:
    """Rótulo público na timeline do vereador (órgão/setor — sem nome de servidor)."""
    t = (tipo or "").upper()
    if t in _ROTULO_POR_TIPO:
        return _ROTULO_POR_TIPO[t]

    orgao_tram, unidade_tram = _contexto_orgao_unidade_tramitacao(tramitacao)
    orgao_dem, unidade_dem = _contexto_orgao_unidade_demanda(demanda)
    orgao_nome = orgao_tram or orgao_dem
    unidade_nome = unidade_tram or unidade_dem

    if t == "CONCLUSAO":
        if orgao_nome and unidade_nome:
            return f"{orgao_nome} — {unidade_nome}"
        if orgao_nome:
            return orgao_nome
        return "Secretaria Municipal"

    if orgao_nome and unidade_nome:
        return f"{orgao_nome} — {unidade_nome}"
    if orgao_nome:
        return orgao_nome
    return "Prefeitura Municipal"


def _montar_unidade_visivel_vereador(
    *,
    orgao_nome: str | None,
    unidade_nome: str | None,
    tramitacao=None,
) -> dict[str, Any] | None:
    unidade = None
    if tramitacao is not None:
        unidade = getattr(tramitacao, "unidade_destino", None) or getattr(
            tramitacao, "unidade_origem", None
        )
    if not orgao_nome and not unidade_nome and unidade is None:
        return None
    out: dict[str, Any] = {}
    if unidade is not None:
        out["id"] = unidade.pk
        out["nome"] = (getattr(unidade, "nome", None) or "").strip() or unidade_nome
        out["sigla"] = (getattr(unidade, "sigla", None) or "").strip()
    elif unidade_nome:
        out["nome"] = unidade_nome
    if orgao_nome:
        out["orgao_nome"] = orgao_nome
    return out or None


def _perfil_usuario(usuario) -> str | None:
    if not usuario or not getattr(usuario, "is_authenticated", False):
        return None
    perfil = getattr(usuario, "perfil", None)
    return str(perfil).upper().strip() if perfil else None


def perfil_usuario(usuario) -> str | None:
    return _perfil_usuario(usuario)


def tramitacao_visivel_para_vereador(tipo: str) -> bool:
    return (tipo or "").upper() in TIPOS_TRAMITACAO_VISIVEIS_VEREADOR


def _demanda_em_execucao_operacional(demanda) -> bool:
    if demanda is None:
        return False
    return getattr(demanda, "status", None) in STATUS_EXECUCAO_OPERACIONAL


def _extrair_parecer_resposta(descricao: str, metadata: dict | None = None) -> str:
    meta = metadata if isinstance(metadata, dict) else {}
    parecer = (meta.get("parecer") or "").strip()
    if parecer:
        return parecer
    texto = (descricao or "").strip()
    match = _RESPOSTA_DEVOLUTIVA_RE.search(texto)
    if match:
        return match.group(1).strip()
    marker = "Parecer:"
    if marker in texto:
        return texto.split(marker, 1)[1].strip()
    return texto


def descricao_tramitacao_para_vereador(tramitacao, demanda=None) -> str:
    """Texto institucional — oculta trânsito interno Protocolo/Secretaria."""
    tipo = (getattr(tramitacao, "tipo", None) or "").upper()
    bruto = (getattr(tramitacao, "descricao", None) or "").strip()

    if tipo in ("DEVOLUTIVA_PROTOCOLO", "CONCLUSAO_FINAL"):
        meta = tramitacao.metadata if isinstance(getattr(tramitacao, "metadata", None), dict) else {}
        resposta = _extrair_parecer_resposta(bruto, meta)
        if resposta:
            return html.escape(resposta)
        return TEXTO_INSTITUCIONAL_VEREADOR.get(tipo, TEXTO_INSTITUCIONAL_VEREADOR["DEVOLUTIVA_PROTOCOLO"])

    if tipo == "CONCLUSAO":
        orgao_tram, unidade_tram = _contexto_orgao_unidade_tramitacao(tramitacao)
        orgao_dem, unidade_dem = _contexto_orgao_unidade_demanda(demanda)
        orgao_nome = orgao_tram or orgao_dem
        unidade_nome = unidade_tram or unidade_dem
        if orgao_nome and unidade_nome:
            return html.escape(f"Serviço concluído por {orgao_nome} — {unidade_nome}.")
        if orgao_nome:
            return html.escape(f"Serviço concluído por {orgao_nome}.")
        return TEXTO_INSTITUCIONAL_VEREADOR[tipo]

    return TEXTO_INSTITUCIONAL_VEREADOR.get(
        tipo,
        "Andamento registrado pela Prefeitura Municipal.",
    )


def filtrar_tramitacoes_para_usuario(queryset, usuario, demanda=None):
    """Retorna queryset filtrado quando o usuário é VEREADOR."""
    if _perfil_usuario(usuario) != "VEREADOR":
        return queryset

    qs = queryset.filter(tipo__in=TIPOS_TRAMITACAO_VISIVEIS_VEREADOR)

    if demanda is not None and _demanda_em_execucao_operacional(demanda):
        qs = qs.filter(tipo="ENVIO_OFICIAL")

    return qs


def serializar_tramitacao_para_vereador(
    data: dict,
    *,
    demanda=None,
    tramitacao_obj=None,
) -> dict:
    """Sanitiza payload de tramitação já serializado para o perfil vereador."""
    tipo = (data.get("tipo") or "").upper()
    if tipo not in TIPOS_TRAMITACAO_VISIVEIS_VEREADOR:
        return data

    orgao_tram, unidade_tram = _contexto_orgao_unidade_tramitacao(tramitacao_obj)
    orgao_dem, unidade_dem = _contexto_orgao_unidade_demanda(demanda)
    orgao_nome = orgao_tram or orgao_dem
    unidade_nome = unidade_tram or unidade_dem

    rotulo = rotulo_institucional_tramitacao(
        tipo, demanda=demanda, tramitacao=tramitacao_obj
    )

    out = dict(data)
    bruto = (data.get("descricao") or "").strip()
    meta_obj = tramitacao_obj.metadata if tramitacao_obj and isinstance(tramitacao_obj.metadata, dict) else {}
    if tipo in ("DEVOLUTIVA_PROTOCOLO", "CONCLUSAO_FINAL"):
        resposta = _extrair_parecer_resposta(bruto, meta_obj)
        out["descricao"] = html.escape(resposta) if resposta else TEXTO_INSTITUCIONAL_VEREADOR.get(
            tipo, TEXTO_INSTITUCIONAL_VEREADOR["DEVOLUTIVA_PROTOCOLO"]
        )
    elif tipo == "CONCLUSAO":
        if orgao_nome and unidade_nome:
            out["descricao"] = html.escape(
                f"Serviço concluído por {orgao_nome} — {unidade_nome}."
            )
        elif orgao_nome:
            out["descricao"] = html.escape(f"Serviço concluído por {orgao_nome}.")
        else:
            out["descricao"] = TEXTO_INSTITUCIONAL_VEREADOR[tipo]
    else:
        out["descricao"] = TEXTO_INSTITUCIONAL_VEREADOR.get(
            tipo,
            "Andamento registrado pela Prefeitura Municipal.",
        )

    out["rotulo_institucional"] = rotulo
    out["orgao_nome"] = orgao_nome
    out["unidade_nome"] = unidade_nome
    out["anexos"] = []
    out["unidade_destino"] = _montar_unidade_visivel_vereador(
        orgao_nome=orgao_nome,
        unidade_nome=unidade_nome,
        tramitacao=tramitacao_obj,
    )
    if out.get("responsavel"):
        out["responsavel"] = {
            **out["responsavel"],
            "first_name": "",
            "last_name": "",
            "username": rotulo,
        }
    return out


def status_permite_pacote_devolutiva_vereador(status: str) -> bool:
    """Vereador só vê parecer após devolutiva formal do Protocolo."""
    return status in ("DEVOLVIDO_VEREADOR", "FINALIZADO")
