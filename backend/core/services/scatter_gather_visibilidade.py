"""Visibilidade de tramitações scatter-gather — oculta eventos internos do sistema."""

from __future__ import annotations

from django.db.models import Q

from core.models import Tramitacao
from core.models_no_operacional import AcaoNoOperacional

ACOES_SCATTER_USUARIO = frozenset(
    {
        AcaoNoOperacional.DESPACHAR,
        AcaoNoOperacional.DESPACHAR_ENCERRAR,
        AcaoNoOperacional.ENCERRAR,
        "CONSOLIDAR",
    }
)

ACOES_SCATTER_OCULTAS_TIMELINE = frozenset(
    {
        "BOOTSTRAP",
        "ABERTURA_NO",
        "ENCAMINHAMENTO_NO",
    }
)


def _meta(tram: Tramitacao) -> dict:
    raw = tram.metadata
    return raw if isinstance(raw, dict) else {}


def tramitacao_scatter_sistema(tram: Tramitacao) -> bool:
    """Tramitação gerada automaticamente (bootstrap, entrada em operação)."""
    meta = _meta(tram)
    if tram.tipo == "OPERACAO_NO" and meta.get("acao_no") == "BOOTSTRAP":
        return True
    if tram.tipo == "STATUS_UPDATE" and meta.get("scatter_gather") and meta.get("automatico"):
        return True
    if tram.tipo == "TRIAGEM_PROTOCOLO":
        return meta.get("acao") != "VINCULAR_SERVICO"
    if tram.tipo == "CONCLUSAO_TECNICA" and meta.get("consolidacao_nos"):
        return True
    return False


def tramitacao_scatter_usuario(tram: Tramitacao) -> bool:
    """Despacho/encerramento redigido por setor na etapa operacional."""
    if tram.tipo != "OPERACAO_NO":
        return False
    return _meta(tram).get("acao_no") in ACOES_SCATTER_USUARIO


def tramitacao_operacional_visivel(tram: Tramitacao) -> bool:
    """False para ruído interno scatter; demais tipos permanecem visíveis."""
    if tram.tipo != "OPERACAO_NO":
        if tramitacao_scatter_sistema(tram):
            return False
        return True
    acao = _meta(tram).get("acao_no")
    if acao in ACOES_SCATTER_OCULTAS_TIMELINE:
        return False
    return tramitacao_scatter_usuario(tram)


def queryset_excluir_scatter_sistema(qs):
    """Exclui eventos automáticos scatter-gather de querysets de tramitação."""
    return qs.exclude(
        tipo="OPERACAO_NO",
        metadata__acao_no="BOOTSTRAP",
    ).exclude(
        tipo="STATUS_UPDATE",
        metadata__scatter_gather=True,
        metadata__automatico=True,
    ).exclude(
        Q(tipo="TRIAGEM_PROTOCOLO") & ~Q(metadata__acao="VINCULAR_SERVICO")
    ).exclude(
        tipo="CONCLUSAO_TECNICA",
        metadata__consolidacao_nos=True,
    )
