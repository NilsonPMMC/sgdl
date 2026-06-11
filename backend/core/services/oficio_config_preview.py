"""Monta configuração temporária para pré-visualização PDF sem persistir."""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import Any

from django.core.files.uploadedfile import UploadedFile

from core.models_config import ConfiguracaoOficio


def clonar_config_para_preview(
    base: ConfiguracaoOficio,
    overrides: dict[str, Any] | None = None,
    *,
    imagem_arquivo: UploadedFile | None = None,
    remover_imagem: bool = False,
) -> tuple[ConfiguracaoOficio, Path | None]:
    """
    Retorna cópia em memória da configuração com overrides do formulário.
    Se imagem_arquivo for enviada, grava em arquivo temporário para o WeasyPrint.
    """
    overrides = overrides or {}
    cfg = ConfiguracaoOficio()
    for field in ConfiguracaoOficio._meta.concrete_fields:
        if field.primary_key:
            continue
        setattr(cfg, field.attname, getattr(base, field.attname))

    for key, value in overrides.items():
        if hasattr(cfg, key):
            setattr(cfg, key, value)

    temp_path: Path | None = None
    if remover_imagem:
        cfg.imagem_cabecalho = None
    elif imagem_arquivo is not None:
        suffix = Path(imagem_arquivo.name or "brasao.png").suffix or ".png"
        temp_path = Path(tempfile.gettempdir()) / f"sgdl_oficio_preview_{uuid.uuid4().hex}{suffix}"
        temp_path.write_bytes(imagem_arquivo.read())
        cfg.imagem_cabecalho.name = str(temp_path)
    elif base.imagem_cabecalho:
        cfg.imagem_cabecalho = base.imagem_cabecalho

    return cfg, temp_path


def limpar_imagem_preview_temp(temp_path: Path | None) -> None:
    if temp_path and temp_path.is_file():
        try:
            temp_path.unlink()
        except OSError:
            pass
