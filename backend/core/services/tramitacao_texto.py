"""Helpers de exibição de descrição de tramitação (B9)."""

from __future__ import annotations

import re

_TAG_HTML_RICO = re.compile(r"<\s*(p|div|br|ul|ol|li|h[1-6]|strong|em|span|blockquote)[\s>/]", re.I)


def parece_html_rico(texto: str | None) -> bool:
    return bool(_TAG_HTML_RICO.search(str(texto or "")))


def descricao_tramitacao_para_exibicao(descricao: str | None) -> dict[str, str]:
    raw = (descricao or "").strip()
    if not raw:
        return {"modo": "vazio"}
    if parece_html_rico(raw):
        return {"modo": "html", "html": raw}
    return {"modo": "texto", "texto": raw.replace("\r\n", "\n")}
