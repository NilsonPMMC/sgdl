"""Geração de numeração de ofício legislativo e protocolo executivo (P7)."""

from __future__ import annotations

import logging
import re

from django.utils import timezone

from core.models import Demanda

logger = logging.getLogger(__name__)

_PREFIXO_OFICIO = "OFICIO"
_RE_OFICIO = re.compile(r"^OFICIO-(\d{4})-(\d+)(?:-D\d+)?$")


def proximo_protocolo_legislativo(autor_id: int, *, ano: int | None = None) -> str:
    """Retorna OFICIO-AAAA-NNNN com sequência anual **por autor** (vereador)."""
    if not autor_id:
        raise ValueError("Autor da demanda é obrigatório para gerar o número do ofício.")

    ano_ref = ano or timezone.now().year
    prefixo = f"{_PREFIXO_OFICIO}-{ano_ref}-"

    max_seq = 0
    for protocolo in Demanda.objects.filter(
        autor_id=autor_id,
        protocolo_legislativo__startswith=prefixo,
    ).values_list("protocolo_legislativo", flat=True):
        if not protocolo:
            continue
        texto = protocolo.strip()
        match = _RE_OFICIO.match(texto)
        if match and int(match.group(1)) == ano_ref:
            max_seq = max(max_seq, int(match.group(2)))
            continue
        if texto.startswith(prefixo):
            logger.warning(
                "Formato inesperado de protocolo_legislativo para autor %s: %s",
                autor_id,
                texto,
            )

    return f"{prefixo}{max_seq + 1:04d}"
