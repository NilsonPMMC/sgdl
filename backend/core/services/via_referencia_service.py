"""Consulta e manutenção do cache local de vias de Mogi das Cruzes."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from django.conf import settings

from core.models_via_referencia import ViaReferenciaMogi
from core.services.endereco_normalizacao import chave_endereco_canonica, normalizar_bairro, normalizar_logradouro

logger = logging.getLogger(__name__)


class ViaReferenciaService:
    def __init__(self) -> None:
        self.enabled = bool(getattr(settings, "GEOCODING_VIA_REFERENCIA_ENABLED", True))
        self.auto_register = bool(
            getattr(settings, "GEOCODING_VIA_REFERENCIA_AUTO_REGISTER", True)
        )

    def buscar(
        self,
        logradouro: str | None,
        bairro: str | None,
        cep: str | None = None,
    ) -> ViaReferenciaMogi | None:
        if not self.enabled:
            return None
        chave = chave_endereco_canonica(logradouro, bairro, cep)
        if not chave or chave == "||":
            return None
        try:
            return ViaReferenciaMogi.objects.filter(
                chave_canonica=chave, ativo=True
            ).first()
        except Exception as exc:
            logger.warning("ViaReferencia lookup falhou: %s", exc)
            return None

    def registrar(
        self,
        *,
        logradouro: str,
        bairro: str,
        cep: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        fonte: str = "via_referencia_local",
        origem: str = ViaReferenciaMogi.ORIGEM_OSM,
        observacao: str = "",
    ) -> ViaReferenciaMogi | None:
        if not self.enabled:
            return None
        logr = normalizar_logradouro(logradouro)
        bai = normalizar_bairro(bairro)
        if not logr or not bai:
            return None
        chave = chave_endereco_canonica(logr, bai, cep)
        defaults: dict[str, Any] = {
            "logradouro": logr[:255],
            "bairro": bai[:120],
            "cep": (cep or "").strip()[:9],
            "fonte": fonte[:32],
            "origem": origem,
            "ativo": True,
            "observacao": (observacao or "")[:255],
        }
        if latitude is not None and longitude is not None:
            defaults["latitude"] = Decimal(str(round(float(latitude), 6)))
            defaults["longitude"] = Decimal(str(round(float(longitude), 6)))
        try:
            obj, _ = ViaReferenciaMogi.objects.update_or_create(
                chave_canonica=chave,
                defaults=defaults,
            )
            return obj
        except Exception as exc:
            logger.warning("ViaReferencia registrar falhou: %s", exc)
            return None

    def registrar_de_geocode(
        self,
        logradouro: str | None,
        bairro: str | None,
        cep: str | None,
        latitude: float | None,
        longitude: float | None,
        *,
        fonte_osm: str = "logradouro",
    ) -> None:
        if not self.auto_register or latitude is None or longitude is None:
            return
        if fonte_osm not in ("logradouro", "viacep_logradouro", "via_referencia_local"):
            return
        self.registrar(
            logradouro=logradouro or "",
            bairro=bairro or "",
            cep=cep,
            latitude=latitude,
            longitude=longitude,
            fonte="via_referencia_local",
            origem=ViaReferenciaMogi.ORIGEM_OSM,
            observacao=f"auto:{fonte_osm}",
        )
