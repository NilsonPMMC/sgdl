"""Geocodificação via Nominatim (OpenStreetMap), restrita a Mogi das Cruzes."""

from __future__ import annotations

import hashlib
import logging
import re
import threading
import time
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
VIACEP_URL = "https://viacep.com.br/ws/{cep}/json/"
CIDADE_PADRAO = "Mogi das Cruzes"
UF_PADRAO = "SP"
PAIS_PADRAO = "Brasil"

_LOGRADOURO_SUJO_RE = re.compile(
    r"\b(of[ií]cio|solicit|tapa|buraco|lombada|instala)\b",
    re.IGNORECASE,
)
_TIPO_VIA_RE = re.compile(
    r"^(?:(?:na|no|em)\s+)?((?:rua|r\.|av\.?|avenida|travessa|alameda)\s+)(.+)$",
    re.IGNORECASE,
)

# Nominatim público: máx. ~1 req/s por IP — serializamos e cacheamos resultados
_nominatim_lock = threading.Lock()
_last_nominatim_request_at = 0.0
_nominatim_backoff_until = 0.0
_geo_result_cache: dict[str, tuple[float, float, str, float]] = {}
_viacep_cache: dict[str, tuple[dict[str, str] | None, float]] = {}


class GeocodingService:
    """Busca coordenadas geográficas para endereços do município."""

    def __init__(self) -> None:
        self.timeout = int(getattr(settings, "GEOCODING_TIMEOUT", 12))
        self.user_agent = getattr(
            settings,
            "GEOCODING_USER_AGENT",
            "SGDL-Gabinete/1.0 (homologacao@gabinete.local)",
        )
        self.cidade = getattr(settings, "GEOCODING_CIDADE", CIDADE_PADRAO)
        self.uf = getattr(settings, "GEOCODING_UF", UF_PADRAO)
        self._nominatim_min_interval = float(
            getattr(settings, "GEOCODING_NOMINATIM_MIN_INTERVAL", 1.1)
        )
        self._cache_ttl = int(getattr(settings, "GEOCODING_CACHE_TTL", 86400))
        self._max_variantes_via = int(getattr(settings, "GEOCODING_MAX_VARIANTES_VIA", 2))
        self._429_backoff_seconds = int(
            getattr(settings, "GEOCODING_NOMINATIM_429_BACKOFF", 90)
        )

    def buscar_coordenadas_com_fonte(
        self,
        logradouro: str | None,
        bairro: str | None,
        cep: str | None,
    ) -> tuple[float | None, float | None, str]:
        """
        Retorna (lat, lng, fonte).
        fonte: indisponivel | cep | bairro_cep | logradouro | viacep_logradouro | aproximada
        """
        logr_in = (logradouro or "").strip()
        lat, lng, fonte_busca = self.buscar_coordenadas(logradouro, bairro, cep)
        if lat is None:
            return None, None, "indisponivel"
        if fonte_busca in ("logradouro", "viacep_logradouro"):
            return lat, lng, fonte_busca
        if fonte_busca == "bairro_cep":
            return lat, lng, "bairro_cep"
        if fonte_busca == "cep":
            if logr_in and _LOGRADOURO_SUJO_RE.search(logr_in):
                return lat, lng, "cep"
            if logr_in:
                return lat, lng, "logradouro"
            return lat, lng, "cep"
        return lat, lng, fonte_busca

    def buscar_endereco_por_coordenadas(
        self, latitude: float, longitude: float
    ) -> dict[str, str | None] | None:
        """
        Geocodificação reversa (Nominatim) para preencher logradouro/bairro/CEP a partir do GPS.
        Restringe ao município configurado (Mogi das Cruzes por padrão).
        """
        try:
            lat = round(float(latitude), 6)
            lng = round(float(longitude), 6)
        except (TypeError, ValueError):
            return None

        cache_key = f"rev:{lat},{lng}"
        with _nominatim_lock:
            rev_entry = _viacep_cache.get(cache_key)
            if rev_entry and rev_entry[1] > time.monotonic():
                return rev_entry[0]

        if self._nominatim_em_backoff():
            return None

        self._aguardar_intervalo_nominatim()
        params: dict[str, Any] = {
            "lat": lat,
            "lon": lng,
            "format": "json",
            "addressdetails": 1,
            "zoom": 18,
        }
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }
        try:
            response = requests.get(
                NOMINATIM_REVERSE_URL,
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            logger.warning("Nominatim reverse indisponível lat=%s lng=%s: %s", lat, lng, exc)
            return None

        if response.status_code == 429:
            self._registrar_backoff_429()
            return None
        if not response.ok:
            return None

        try:
            data = response.json()
        except ValueError:
            return None
        if not isinstance(data, dict):
            return None

        addr = data.get("address")
        if not isinstance(addr, dict):
            return None

        cidade_ref = self.cidade.lower()
        local_keys = (
            "city",
            "town",
            "municipality",
            "county",
            "state_district",
        )
        local_nome = ""
        for ch in local_keys:
            val = (addr.get(ch) or "").strip()
            if val:
                local_nome = val
                break
        if local_nome and cidade_ref not in local_nome.lower():
            logger.info(
                "Reverse geocode fora de %s: lat=%s lng=%s local=%s",
                self.cidade,
                lat,
                lng,
                local_nome,
            )
            return None

        logradouro = (
            (addr.get("road") or addr.get("pedestrian") or addr.get("footway") or "")
        ).strip()
        if not logradouro:
            logradouro = (addr.get("residential") or addr.get("neighbourhood") or "").strip()

        bairro = (
            (addr.get("suburb") or addr.get("neighbourhood") or addr.get("quarter") or "")
        ).strip()
        numero = (addr.get("house_number") or "").strip() or None
        cep_raw = re.sub(r"\D", "", (addr.get("postcode") or ""))
        cep_fmt = (
            f"{cep_raw[:5]}-{cep_raw[5:8]}" if len(cep_raw) >= 8 else None
        )

        if not logradouro and not bairro and not cep_fmt:
            return None

        out: dict[str, str | None] = {
            "logradouro": logradouro or None,
            "bairro": bairro or None,
            "numero": numero,
            "cep": cep_fmt,
        }

        with _nominatim_lock:
            _viacep_cache[cache_key] = (out, time.monotonic() + self._cache_ttl)
        return out

    def buscar_endereco_por_cep(self, cep: str | None) -> dict[str, str] | None:
        """Consulta ViaCEP (cache interno). Retorna logradouro, bairro, localidade, uf."""
        cep_limpo = re.sub(r"\D", "", cep or "")
        if len(cep_limpo) != 8:
            return None
        return self._consultar_viacep(cep_limpo)

    def buscar_coordenadas(
        self,
        logradouro: str | None,
        bairro: str | None,
        cep: str | None,
    ) -> tuple[float | None, float | None, str]:
        """
        Retorna (latitude, longitude, fonte_interna) ou (None, None, indisponivel).

        Prioriza via pública (nome enxuto compatível com OSM), depois bairro+CEP; CEP sozinho por último.
        CEP é normalizado via ViaCEP quando possível.
        """
        logr, bai, cep_fmt, cep_limpo, via_viacep = self._preparar_endereco(
            logradouro, bairro, cep
        )

        if not logr and not bai and len(cep_limpo) < 8:
            return None, None, "indisponivel"

        cache_key = self._cache_key_endereco(logr, bai, cep_limpo)
        cached = self._geo_cache_get(cache_key)
        if cached is not None:
            return cached

        logr_sujo = bool(logr and _LOGRADOURO_SUJO_RE.search(logr))
        if logr_sujo:
            logr = None

        tentativas: list[tuple[str, str]] = []

        def add(q: str, fonte: str) -> None:
            qn = q.strip(" ,")
            if len(qn) < 8:
                return
            if any(qn == existente for existente, _ in tentativas):
                return
            tentativas.append((qn, fonte))

        sufixo_cidade = f"{self.cidade}, {self.uf}, {PAIS_PADRAO}"
        fonte_via = "viacep_logradouro" if via_viacep else "logradouro"

        if logr:
            variantes = self._variantes_logradouro(logr)
            variantes = sorted(variantes, key=len)[: self._max_variantes_via]
            for variante in variantes:
                add(
                    ", ".join(p for p in (variante, bai, cep_fmt, sufixo_cidade) if p),
                    fonte_via,
                )
                if len(tentativas) >= self._max_variantes_via:
                    break

        if bai and cep_fmt:
            add(f"{bai}, {cep_fmt}, {sufixo_cidade}", "bairro_cep")

        if cep_fmt:
            add(f"{cep_fmt}, {sufixo_cidade}", "cep")

        for query, fonte in tentativas:
            if self._nominatim_em_backoff():
                break
            coords = self._consultar_nominatim(query)
            if coords[0] is not None:
                resultado = (coords[0], coords[1], fonte)
                self._geo_cache_set(cache_key, resultado)
                return resultado

        return None, None, "indisponivel"

    @staticmethod
    def chave_endereco(
        logradouro: str | None, bairro: str | None, cep: str | None
    ) -> str:
        """Chave estável para reutilizar coordenadas já calculadas no rascunho."""
        cep_limpo = re.sub(r"\D", "", (cep or "").strip())
        logr = (logradouro or "").strip()
        bai = (bairro or "").strip()
        return GeocodingService._cache_key_endereco(logr, bai, cep_limpo)

    @staticmethod
    def _cache_key_endereco(logr: str, bai: str, cep_limpo: str) -> str:
        raw = f"{cep_limpo}|{logr.lower().strip()}|{bai.lower().strip()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def _geo_cache_get(
        self, key: str
    ) -> tuple[float, float, str] | None:
        now = time.monotonic()
        with _nominatim_lock:
            entry = _geo_result_cache.get(key)
            if not entry:
                return None
            lat, lng, fonte, expires = entry
            if expires < now:
                _geo_result_cache.pop(key, None)
                return None
            return lat, lng, fonte

    def _geo_cache_set(
        self, key: str, value: tuple[float, float, str]
    ) -> None:
        expires = time.monotonic() + self._cache_ttl
        with _nominatim_lock:
            _geo_result_cache[key] = (value[0], value[1], value[2], expires)

    def _preparar_endereco(
        self,
        logradouro: str | None,
        bairro: str | None,
        cep: str | None,
    ) -> tuple[str, str, str, str, bool]:
        """Normaliza CEP/logradouro/bairro; retorna (logr, bai, cep_fmt, cep_limpo, usou_viacep)."""
        logr = (logradouro or "").strip()
        bai = (bairro or "").strip()
        cep_limpo = re.sub(r"\D", "", (cep or "").strip())
        cep_fmt = (
            f"{cep_limpo[:5]}-{cep_limpo[5:8]}" if len(cep_limpo) >= 8 else ""
        )
        via_viacep = False

        if len(cep_limpo) == 8:
            dados = self._consultar_viacep(cep_limpo)
            if dados:
                via_viacep = True
                if dados.get("logradouro"):
                    logr = dados["logradouro"].strip()
                if dados.get("bairro"):
                    bai = dados["bairro"].strip()
                localidade = (dados.get("localidade") or "").strip()
                uf = (dados.get("uf") or "").strip()
                if localidade and localidade.lower() != self.cidade.lower():
                    logger.info(
                        "ViaCEP %s fora de %s (%s); mantendo geocode local.",
                        cep_fmt,
                        self.cidade,
                        localidade,
                    )
                if uf and uf.upper() != self.uf.upper():
                    logger.info("ViaCEP %s UF=%s diferente de %s.", cep_fmt, uf, self.uf)

        return logr, bai, cep_fmt, cep_limpo, via_viacep

    @staticmethod
    def _variantes_logradouro(logradouro: str) -> list[str]:
        """Gera nomes de via progressivamente mais curtos (OSM costuma abreviar)."""
        logr = logradouro.strip()
        if not logr:
            return []

        vistos: set[str] = set()
        ordem: list[str] = []

        def push(v: str) -> None:
            v = re.sub(r"\s+", " ", v).strip()
            if len(v) < 6:
                return
            chave = v.lower()
            if chave in vistos:
                return
            vistos.add(chave)
            ordem.append(v)

        push(logr)

        m = _TIPO_VIA_RE.match(logr)
        if not m:
            return ordem

        prefixo, resto = m.group(1), m.group(2).strip()
        partes = resto.split()
        if len(partes) >= 4:
            push(f"{prefixo}{partes[0]} {partes[1]}")
            push(f"{prefixo}{partes[0]} {partes[-1]}")
        elif len(partes) >= 3:
            push(f"{prefixo}{partes[0]} {partes[1]}")
            push(f"{prefixo}{partes[0]} {partes[-1]}")
        elif len(partes) >= 2:
            push(f"{prefixo}{partes[0]} {partes[1]}")

        return ordem

    def _consultar_viacep(self, cep_limpo: str) -> dict[str, str] | None:
        now = time.monotonic()
        with _nominatim_lock:
            cached = _viacep_cache.get(cep_limpo)
            if cached and cached[1] > now:
                return cached[0]

        url = VIACEP_URL.format(cep=cep_limpo)
        headers = {"User-Agent": self.user_agent, "Accept": "application/json"}
        try:
            response = requests.get(url, headers=headers, timeout=self.timeout)
        except requests.RequestException as exc:
            logger.warning("ViaCEP indisponível cep=%s: %s", cep_limpo, exc)
            return None

        if not response.ok:
            return None
        try:
            data = response.json()
        except ValueError:
            return None
        if not isinstance(data, dict) or data.get("erro"):
            return None

        out: dict[str, str] = {}
        for chave in ("logradouro", "bairro", "localidade", "uf"):
            val = (data.get(chave) or "").strip()
            if val:
                out[chave] = val

        with _nominatim_lock:
            _viacep_cache[cep_limpo] = (out or None, now + self._cache_ttl)
        return out or None

    def _nominatim_em_backoff(self) -> bool:
        return time.monotonic() < _nominatim_backoff_until

    def _aguardar_intervalo_nominatim(self) -> None:
        global _last_nominatim_request_at
        with _nominatim_lock:
            agora = time.monotonic()
            espera = self._nominatim_min_interval - (agora - _last_nominatim_request_at)
            if espera > 0:
                time.sleep(espera)
            _last_nominatim_request_at = time.monotonic()

    def _registrar_backoff_429(self) -> None:
        global _nominatim_backoff_until
        with _nominatim_lock:
            _nominatim_backoff_until = time.monotonic() + self._429_backoff_seconds
        logger.warning(
            "Nominatim rate limit (429); pausando novas consultas por %ss.",
            self._429_backoff_seconds,
        )

    def _consultar_nominatim(self, query: str) -> tuple[float | None, float | None]:
        if self._nominatim_em_backoff():
            return None, None

        cache_q = f"q:{query.strip().lower()}"
        cached = self._geo_cache_get(cache_q)
        if cached is not None:
            return cached[0], cached[1]

        self._aguardar_intervalo_nominatim()

        params: dict[str, Any] = {
            "q": query,
            "format": "json",
            "limit": 1,
            "countrycodes": "br",
            "addressdetails": 0,
        }
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }
        try:
            response = requests.get(
                NOMINATIM_SEARCH_URL,
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            logger.warning("Nominatim indisponível para query=%s: %s", query[:120], exc)
            return None, None

        if response.status_code == 429:
            self._registrar_backoff_429()
            return None, None

        if not response.ok:
            if response.status_code >= 500:
                logger.warning(
                    "Nominatim HTTP %s para query=%s",
                    response.status_code,
                    query[:120],
                )
            return None, None

        try:
            resultados = response.json()
        except ValueError:
            return None, None

        if not isinstance(resultados, list) or not resultados:
            return None, None

        primeiro = resultados[0]
        if not isinstance(primeiro, dict):
            return None, None
        try:
            lat, lng = float(primeiro["lat"]), float(primeiro["lon"])
            self._geo_cache_set(cache_q, (lat, lng, "logradouro"))
            return lat, lng
        except (KeyError, TypeError, ValueError):
            return None, None
