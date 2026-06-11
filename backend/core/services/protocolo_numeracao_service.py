"""Geração de numeração de ofício legislativo e protocolo executivo (P7)."""

from __future__ import annotations

import logging
import re

from django.utils import timezone

from core.models import Demanda

logger = logging.getLogger(__name__)

_PREFIXO_OFICIO = "OFICIO"
_RE_OFICIO = re.compile(r"^OFICIO-(\d{4})-(\d+)$")


def proximo_protocolo_legislativo(autor_id: int, *, ano: int | None = None) -> str:
    """Retorna OFICIO-AAAA-NNNN com sequência anual **por autor** (vereador)."""
    if not autor_id:
        raise ValueError("Autor da demanda é obrigatório para gerar o número do ofício.")

    ano_ref = ano or timezone.now().year
    prefixo = f"{_PREFIXO_OFICIO}-{ano_ref}-"

    ultimo = (
        Demanda.objects.filter(
            autor_id=autor_id,
            protocolo_legislativo__startswith=prefixo,
        )
        .order_by("-protocolo_legislativo")
        .first()
    )

    novo = 1
    if ultimo and ultimo.protocolo_legislativo:
        match = _RE_OFICIO.match(ultimo.protocolo_legislativo.strip())
        if match and int(match.group(1)) == ano_ref:
            try:
                novo = int(match.group(2)) + 1
            except ValueError:
                novo = (
                    Demanda.objects.filter(
                        autor_id=autor_id,
                        protocolo_legislativo__startswith=prefixo,
                    ).count()
                    + 1
                )
        else:
            logger.warning(
                "Formato inesperado de protocolo_legislativo para autor %s: %s",
                autor_id,
                ultimo.protocolo_legislativo,
            )

    return f"{prefixo}{novo:04d}"
