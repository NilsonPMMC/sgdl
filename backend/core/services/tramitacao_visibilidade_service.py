"""Regras de visibilidade de tramitações por perfil (P8 — timeline vereador)."""

from __future__ import annotations

TIPOS_TRAMITACAO_VISIVEIS_VEREADOR = frozenset(
    {
        "ENVIO_OFICIAL",
        "DESPACHO",
        "CONCLUSAO",
        "SOLICITACAO_DEVOLUTIVA",
        "DEVOLUTIVA_PROTOCOLO",
        "CIENCIA_VEREADOR",
        "ENCERRAMENTO_DEVOLUTIVA",
    }
)


def _perfil_usuario(usuario) -> str | None:
    if not usuario or not getattr(usuario, "is_authenticated", False):
        return None
    perfil = getattr(usuario, "perfil", None)
    return str(perfil).upper().strip() if perfil else None


def tramitacao_visivel_para_vereador(tipo: str) -> bool:
    return (tipo or "").upper() in TIPOS_TRAMITACAO_VISIVEIS_VEREADOR


def filtrar_tramitacoes_para_usuario(queryset, usuario):
    """Retorna queryset filtrado quando o usuário é VEREADOR."""
    if _perfil_usuario(usuario) != "VEREADOR":
        return queryset
    return queryset.filter(tipo__in=TIPOS_TRAMITACAO_VISIVEIS_VEREADOR)
