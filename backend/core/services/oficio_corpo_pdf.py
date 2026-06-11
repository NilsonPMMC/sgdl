"""Prepara o corpo do ofício para PDF — texto simples ou HTML do editor (Quill)."""

from __future__ import annotations

import re
from typing import Any

import bleach
from bleach.css_sanitizer import CSSSanitizer

# Tags típicas do PrimeVue Editor / Quill
_TAGS_PERMITIDAS = frozenset(
    {
        "p",
        "br",
        "strong",
        "b",
        "em",
        "i",
        "u",
        "s",
        "ul",
        "ol",
        "li",
        "h1",
        "h2",
        "h3",
        "blockquote",
        "span",
    }
)

_ATRIBUTOS_PERMITIDOS = {
    "*": ["class"],
    "p": ["class", "style"],
    "span": ["class", "style"],
    "li": ["class"],
}

_CSS_SANITIZER = CSSSanitizer(
    allowed_css_properties=frozenset({"text-align", "margin-left", "padding-left"})
)

_TAG_HTML_RE = re.compile(
    r"<\s*/?\s*(?:p|br|div|span|strong|b|em|i|u|s|ul|ol|li|h[1-6]|blockquote)\b",
    re.IGNORECASE,
)

_P_VAZIO_RE = re.compile(r"<p(\s[^>]*)?>\s*</p>", re.IGNORECASE)


def normalizar_html_quill(html: str) -> str:
    """
    Ajusta HTML do Quill/PrimeVue Editor para PDF:
    - div → p (Quill 2)
    - &nbsp; → espaço comum (permite quebra na margem)
    - parágrafos vazios → <br> (espaço vertical visível)
    """
    texto = html.replace("\u00a0", " ").replace("&nbsp;", " ")
    texto = re.sub(r"<\s*div\b", "<p", texto, flags=re.IGNORECASE)
    texto = re.sub(r"<\s*/\s*div\s*>", "</p>", texto, flags=re.IGNORECASE)
    texto = _P_VAZIO_RE.sub(r"<p\1><br></p>", texto)
    return texto


def sanitizar_html_oficio(html: str) -> str:
    """Remove scripts/eventos e mantém formatação segura para WeasyPrint."""
    preparado = normalizar_html_quill(html)
    limpo = bleach.clean(
        preparado,
        tags=list(_TAGS_PERMITIDAS),
        attributes=_ATRIBUTOS_PERMITIDOS,
        css_sanitizer=_CSS_SANITIZER,
        strip=True,
    )
    return limpo.strip()


def parece_html_rico(texto: str) -> bool:
    """Detecta conteúdo gerado pelo editor rich-text (não texto plano)."""
    return bool(_TAG_HTML_RE.search(texto))


def preparar_corpo_pdf(texto: str | None) -> dict[str, Any]:
    """
    Retorna contexto do template:
    - corpo_texto: texto plano ou HTML sanitizado
    - corpo_richtext: True quando deve usar |safe no template
    """
    raw = (texto or "").strip()
    if not raw:
        return {"corpo_texto": "", "corpo_richtext": False}
    if not parece_html_rico(raw):
        return {"corpo_texto": raw, "corpo_richtext": False}
    return {"corpo_texto": sanitizar_html_oficio(raw), "corpo_richtext": True}
