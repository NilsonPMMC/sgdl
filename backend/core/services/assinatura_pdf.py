"""Contexto de assinatura do autor para templates PDF (WeasyPrint)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from django.utils.html import strip_tags

from ..models import Usuario


def contexto_assinatura_pdf(usuario: Usuario | None) -> dict[str, Any]:
    """Monta variáveis para o bloco de assinatura no ofício."""
    if usuario is None:
        return {
            "assinatura_imagem_url": None,
            "assinatura_texto": "",
            "assinatura_nome": "",
            "assinatura_cargo": "",
            "tem_assinatura": False,
        }

    nome = (usuario.get_full_name() or usuario.username or "").strip()
    cargo = (getattr(usuario, "cargo", None) or "").strip()
    texto = ""
    if usuario.assinatura:
        texto = strip_tags(usuario.assinatura).strip()

    imagem_url: str | None = None
    if usuario.assinatura_imagem:
        try:
            path = Path(usuario.assinatura_imagem.path)
            if path.is_file():
                imagem_url = path.resolve().as_uri()
        except (ValueError, OSError):
            imagem_url = None

    tem = bool(imagem_url or texto or nome)
    return {
        "assinatura_imagem_url": imagem_url,
        "assinatura_texto": texto,
        "assinatura_nome": nome,
        "assinatura_cargo": cargo,
        "tem_assinatura": tem,
    }
