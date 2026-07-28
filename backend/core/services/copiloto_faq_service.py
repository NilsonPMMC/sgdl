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


def listar_faq_detalhada_para_prompt(*, limite: int = 20) -> list[dict[str, str]]:
    """Entradas completas da FAQ para calibrar o prompt Groq (A1)."""
    out: list[dict[str, str]] = []
    for faq in carregar_catalogo_faq():
        out.append(
            {
                "categoria_orientacao": faq.categoria_orientacao,
                "titulo": faq.titulo,
                "mensagem": faq.mensagem,
                "orgao_hint": faq.orgao_hint,
            }
        )
        if len(out) >= limite:
            break
    return out


def montar_resposta_chat_fora_competencia(rascunho: list[Any]) -> str:
    """Mensagem ao cidadão alinhada à FAQ cadastrada (itens fora_competencia)."""
    blocos: list[str] = []
    for i, item in enumerate(rascunho or []):
        if not isinstance(item, dict) or not item.get("fora_competencia"):
            continue
        titulo = (item.get("titulo") or f"Solicitação {i + 1}").strip()
        faq = item.get("faq_orientacao") if isinstance(item.get("faq_orientacao"), dict) else {}
        motivo = (item.get("motivo_recusa") or "").strip()
        linhas: list[str] = [f"«{titulo}»"]
        if motivo:
            linhas.append(motivo)
        elif faq.get("mensagem"):
            linhas.append(str(faq["mensagem"]).strip())
        if faq.get("orgao_hint"):
            linhas.append(f"Orientação: {faq['orgao_hint']}.")
        blocos.append("\n".join(linhas))

    if not blocos:
        return ""

    if len(blocos) == 1:
        intro = (
            "Não consigo gerar ofício pelo gabinete para este pedido, "
            "pois não se trata de serviço público municipal:"
        )
    else:
        intro = (
            "Não consigo gerar ofício pelo gabinete para os pedidos abaixo, "
            "pois não se tratam de serviço público municipal:"
        )
    fechamento = (
        "Se precisar de zeladoria, obras, meio ambiente ou outro serviço da Prefeitura, "
        "descreva o problema e o local (rua ou bairro)."
    )
    return intro + "\n\n" + "\n\n".join(blocos) + "\n\n" + fechamento


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


# Fallback quando regex cadastradas no banco são estreitas (ex.: «prisão» sem «preventiva»).
_FALLBACK_FAQ_CATEGORIA_RE: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"\b(?:(?:mandato|madato)\s+de\s+pris[aã]o|"
            r"pris[aã]o\s+(?:preventiva|tempor[aá]ria|domiciliar)|"
            r"(?:solicit(?:o|a|ar)|ped(?:ido|ir)|requisit(?:o|ar))\s+(?:a\s+)?pris[aã]o|"
            r"pris[aã]o\s+(?:de\s+)?(?:um?\s+)?(?:cidad[aã]o|pessoa|indiv[ií]duo)|"
            r"pris[aã]o\b)",
            re.IGNORECASE,
        ),
        "MADATO_DE_PRISAO",
    ),
    (
        re.compile(
            r"\b(?:justi[cç]a\s+estadual|processo\s+judicial|"
            r"vara\s+(?:criminal|c[ií]vel)|delegacia|boletim\s+de\s+ocorr[eê]ncia|"
            r"(?:furto|roubo|assalto|sequestro|homic[ií]dio|estupro|"
            r"tr[aá]fico\s+(?:de\s+)?(?:drogas|entorpecentes)))\b",
            re.IGNORECASE,
        ),
        "JUSTICA_ESTADUAL",
    ),
    (
        re.compile(
            r"\b(?:ju[ií]z(?:a)?|promotor(?:a)?|defensor(?:a)?\s+p[uú]blico)\b",
            re.IGNORECASE,
        ),
        "JUSTICA_ESTADUAL",
    ),
)

_ALIASES_CATEGORIA_FAQ: dict[str, tuple[str, ...]] = {
    "MADATO_DE_PRISAO": ("MANDATO_DE_PRISAO",),
    "MANDATO_DE_PRISAO": ("MADATO_DE_PRISAO",),
}


def _faq_por_categoria_com_alias(
    categoria: str, *, municipio: str | None = None
) -> FaqOrientacaoRegistro | None:
    cat = str(categoria).strip().upper().replace(" ", "_")
    faq = faq_por_categoria(cat, municipio=municipio)
    if faq:
        return faq
    for alias in _ALIASES_CATEGORIA_FAQ.get(cat, ()):
        faq = faq_por_categoria(alias, municipio=municipio)
        if faq:
            return faq
    return None


def _detectar_faq_fallback_por_texto(
    texto: str, *, municipio: str | None = None
) -> FaqOrientacaoRegistro | None:
    t = (texto or "").strip()
    if not t:
        return None
    for pat, cat in _FALLBACK_FAQ_CATEGORIA_RE:
        if pat.search(t):
            faq = _faq_por_categoria_com_alias(cat, municipio=municipio)
            if faq:
                return faq
    return None


def detectar_faq_por_texto(texto: str, *, municipio: str | None = None) -> FaqOrientacaoRegistro | None:
    t = (texto or "").strip()
    if not t:
        return None
    for faq in carregar_catalogo_faq(municipio=municipio):
        for pat in faq.patterns:
            if pat.search(t):
                return faq
    return _detectar_faq_fallback_por_texto(t, municipio=municipio)


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
