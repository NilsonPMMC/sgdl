"""
Carrega a FAQ do Copiloto a partir do banco e expõe API interna para automação LLM.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.text import slugify

from core.models_copiloto_faq import CopilotoFaqOrientacao, CopilotoFaqPadraoRegex

logger = logging.getLogger(__name__)

_CACHE: list[FaqOrientacaoRegistro] | None = None
_CATEGORIAS_CACHE: frozenset[str] | None = None


@dataclass(frozen=True)
class FaqOrientacaoRegistro:
    """Snapshot imutável usado na detecção do Copiloto."""

    id: str
    db_id: int
    categoria_orientacao: str
    titulo: str
    mensagem: str
    orgao_hint: str
    municipio_referencia: str
    ordem: int
    patterns: tuple[re.Pattern[str], ...]


def invalidar_cache_faq() -> None:
    global _CACHE, _CATEGORIAS_CACHE
    _CACHE = None
    _CATEGORIAS_CACHE = None


def _compilar_padroes(faq: CopilotoFaqOrientacao) -> tuple[re.Pattern[str], ...]:
    compilados: list[re.Pattern[str]] = []
    padroes = faq.padroes.filter(ativo=True).order_by("ordem", "id")
    for p in padroes:
        expr = (p.expressao or "").strip()
        if not expr:
            continue
        try:
            compilados.append(re.compile(expr, re.IGNORECASE))
        except re.error as exc:
            logger.warning(
                "FAQ #%s: regex ignorada %r: %s",
                faq.pk,
                expr[:80],
                exc,
            )
    return tuple(compilados)


def carregar_catalogo_faq(*, municipio: str | None = None) -> list[FaqOrientacaoRegistro]:
    """
    Lista entradas ativas ordenadas por `ordem`.
    Opcionalmente filtra por municipio_referencia (case-insensitive contains).
    """
    global _CACHE
    if _CACHE is not None and municipio is None:
        return _CACHE

    qs = (
        CopilotoFaqOrientacao.objects.filter(ativo=True)
        .prefetch_related("padroes")
        .order_by("ordem", "titulo")
    )
    if municipio:
        qs = qs.filter(municipio_referencia__icontains=municipio.strip())

    registros: list[FaqOrientacaoRegistro] = []
    for row in qs:
        patterns = _compilar_padroes(row)
        if not patterns:
            continue
        registros.append(
            FaqOrientacaoRegistro(
                id=row.slug,
                db_id=row.pk,
                categoria_orientacao=row.categoria_orientacao,
                titulo=row.titulo,
                mensagem=row.mensagem,
                orgao_hint=row.orgao_hint,
                municipio_referencia=row.municipio_referencia,
                ordem=row.ordem,
                patterns=patterns,
            )
        )

    if municipio is None:
        _CACHE = registros
    return registros


def categorias_orientacao_ativas() -> frozenset[str]:
    global _CATEGORIAS_CACHE
    if _CATEGORIAS_CACHE is not None:
        return _CATEGORIAS_CACHE
    cats = frozenset(
        CopilotoFaqOrientacao.objects.filter(ativo=True).values_list(
            "categoria_orientacao", flat=True
        )
    )
    _CATEGORIAS_CACHE = cats
    return cats


def listar_categorias_para_prompt() -> list[dict[str, str]]:
    """Resumo para injeção em prompt de enriquecimento / triagem LLM."""
    out: list[dict[str, str]] = []
    for row in CopilotoFaqOrientacao.objects.filter(ativo=True).order_by("ordem", "titulo"):
        out.append(
            {
                "categoria_orientacao": row.categoria_orientacao,
                "titulo": row.titulo,
                "orgao_hint": row.orgao_hint,
                "municipio_referencia": row.municipio_referencia,
            }
        )
    return out


def detectar_faq_por_texto(texto: str, *, municipio: str | None = None) -> FaqOrientacaoRegistro | None:
    t = (texto or "").strip()
    if not t:
        return None
    for faq in carregar_catalogo_faq(municipio=municipio):
        for pat in faq.patterns:
            if pat.search(t):
                return faq
    return None


def faq_por_categoria(
    categoria: str | None, *, municipio: str | None = None
) -> FaqOrientacaoRegistro | None:
    if not categoria:
        return None
    cat = str(categoria).strip().upper().replace(" ", "_")
    for faq in carregar_catalogo_faq(municipio=municipio):
        if faq.categoria_orientacao == cat:
            return faq
    return None


def faq_para_dict(faq: FaqOrientacaoRegistro) -> dict[str, str]:
    return {
        "id": faq.id,
        "db_id": str(faq.db_id),
        "categoria_orientacao": faq.categoria_orientacao,
        "titulo": faq.titulo,
        "mensagem": faq.mensagem,
        "orgao_hint": faq.orgao_hint,
        "municipio_referencia": faq.municipio_referencia,
    }


def montar_motivo_recusa(
    *,
    motivo_llm: str | None = None,
    faq: FaqOrientacaoRegistro | None = None,
    padrao: str | None = None,
) -> str:
    partes: list[str] = []
    if motivo_llm and motivo_llm.strip():
        partes.append(motivo_llm.strip())
    elif padrao:
        partes.append(padrao)
    if faq:
        partes.append(faq.mensagem)
        partes.append(f"Orientação: {faq.orgao_hint}.")
    return " ".join(partes).strip()


@transaction.atomic
def aplicar_sugestao_llm(
    payload: dict[str, Any],
    *,
    usuario=None,
) -> CopilotoFaqOrientacao:
    """
    Cria ou atualiza uma entrada FAQ a partir de payload estruturado da automação LLM.

    payload esperado:
      categoria_orientacao, titulo, mensagem, orgao_hint,
      padroes_regex: list[str], slug?, municipio_referencia?, ativo?, ordem?, notas_internas?
    """
    cat = str(payload.get("categoria_orientacao") or "").strip().upper().replace(" ", "_")
    if not cat:
        raise ValueError("categoria_orientacao é obrigatória.")

    titulo = (payload.get("titulo") or "").strip()
    mensagem = (payload.get("mensagem") or "").strip()
    orgao_hint = (payload.get("orgao_hint") or "").strip()
    if not titulo or not mensagem or not orgao_hint:
        raise ValueError("titulo, mensagem e orgao_hint são obrigatórios.")

    slug = (payload.get("slug") or "").strip() or slugify(titulo)[:80] or slugify(cat)[:80]
    municipio = (payload.get("municipio_referencia") or "Mogi das Cruzes").strip()

    faq, created = CopilotoFaqOrientacao.objects.get_or_create(
        categoria_orientacao=cat,
        defaults={
            "slug": slug,
            "titulo": titulo,
            "mensagem": mensagem,
            "orgao_hint": orgao_hint,
            "municipio_referencia": municipio,
            "fonte": CopilotoFaqOrientacao.FONTE_LLM,
            "ativo": bool(payload.get("ativo", True)),
            "ordem": int(payload.get("ordem") or 100),
            "notas_internas": (payload.get("notas_internas") or "").strip(),
            "revisado_por": usuario,
            "ultima_sincronizacao_llm": timezone.now(),
        },
    )
    if not created:
        faq.titulo = titulo
        faq.mensagem = mensagem
        faq.orgao_hint = orgao_hint
        faq.municipio_referencia = municipio
        faq.fonte = CopilotoFaqOrientacao.FONTE_LLM
        faq.ativo = bool(payload.get("ativo", faq.ativo))
        if payload.get("ordem") is not None:
            faq.ordem = int(payload["ordem"])
        notas = (payload.get("notas_internas") or "").strip()
        if notas:
            faq.notas_internas = notas
        faq.revisado_por = usuario
        faq.ultima_sincronizacao_llm = timezone.now()
        faq.save()

    padroes = payload.get("padroes_regex") or payload.get("padroes") or []
    if isinstance(padroes, list) and padroes:
        if payload.get("substituir_padroes"):
            faq.padroes.all().delete()
        for i, expr in enumerate(padroes):
            expr_s = str(expr).strip()
            if not expr_s:
                continue
            validar_expressao_regex(expr_s)
            existe = faq.padroes.filter(expressao=expr_s).exists()
            if not existe:
                CopilotoFaqPadraoRegex.objects.create(
                    faq=faq,
                    expressao=expr_s,
                    ordem=int(payload.get("ordem_padrao_base") or 10) + i,
                    fonte=CopilotoFaqOrientacao.FONTE_LLM,
                )

    invalidar_cache_faq()
    return faq


def validar_expressao_regex(expressao: str) -> None:
    from core.models_copiloto_faq import validar_expressao_regex as _v

    _v(expressao)


def _receiver_invalidar(*args, **kwargs):
    invalidar_cache_faq()


@receiver(post_save, sender=CopilotoFaqOrientacao)
def _faq_orientacao_saved(sender, **kwargs):
    _receiver_invalidar()


@receiver(post_delete, sender=CopilotoFaqOrientacao)
def _faq_orientacao_deleted(sender, **kwargs):
    _receiver_invalidar()


@receiver(post_save, sender=CopilotoFaqPadraoRegex)
def _faq_padrao_saved(sender, **kwargs):
    _receiver_invalidar()


@receiver(post_delete, sender=CopilotoFaqPadraoRegex)
def _faq_padrao_deleted(sender, **kwargs):
    _receiver_invalidar()
