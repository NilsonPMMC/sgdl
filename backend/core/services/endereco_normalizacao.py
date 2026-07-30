"""Normalização canônica de endereços para geocodificação e cluster (~300 m)."""

import re
import unicodedata
from typing import Any

_RE_PREFIXO_VIA = (
    r"^(?:rua|r\.?\s+|av\.?\s+|avenida\s+|trav\.?\s+|travessa\s+|al\.?\s+|alameda\s+)"
)

_TIPO_VIA_EXPAND: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^av\.?\s+", re.IGNORECASE), "Avenida "),
    (re.compile(r"^avenida\s+", re.IGNORECASE), "Avenida "),
    (re.compile(r"^r\.?\s+", re.IGNORECASE), "Rua "),
    (re.compile(r"^rua\s+", re.IGNORECASE), "Rua "),
    (re.compile(r"^trav\.?\s+", re.IGNORECASE), "Travessa "),
    (re.compile(r"^travessa\s+", re.IGNORECASE), "Travessa "),
    (re.compile(r"^al\.?\s+", re.IGNORECASE), "Alameda "),
    (re.compile(r"^alameda\s+", re.IGNORECASE), "Alameda "),
)

_BAIRRO_PREFIXO_EXPAND: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^vl\.?\s+", re.IGNORECASE), "Vila "),
    (re.compile(r"^vila\s+", re.IGNORECASE), "Vila "),
    (re.compile(r"^jd\.?\s+", re.IGNORECASE), "Jardim "),
    (re.compile(r"^jardim\s+", re.IGNORECASE), "Jardim "),
    (re.compile(r"^pq\.?\s+", re.IGNORECASE), "Parque "),
    (re.compile(r"^parque\s+", re.IGNORECASE), "Parque "),
)

_FONTES_COORDENADA_PRECISA = frozenset(
    {"logradouro", "viacep_logradouro", "gps_dispositivo", "gps", "via_referencia_local", "ajuste_mapa"}
)
_FONTES_COORDENADA_APROXIMADA = frozenset({"cep", "bairro_cep", "aproximada"})


def sem_acentos(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def colapsar_espacos(texto: str) -> str:
    return re.sub(r"\s+", " ", (texto or "").strip())


def expandir_tipo_via(texto: str) -> str:
    t = colapsar_espacos(texto)
    if not t:
        return ""
    for pattern, substituto in _TIPO_VIA_EXPAND:
        if pattern.match(t):
            resto = pattern.sub("", t, count=1).strip()
            return f"{substituto.strip()} {resto}".strip()
    return t


def expandir_prefixo_bairro(texto: str) -> str:
    t = colapsar_espacos(texto)
    if not t:
        return ""
    for pattern, substituto in _BAIRRO_PREFIXO_EXPAND:
        if pattern.match(t):
            resto = pattern.sub("", t, count=1).strip()
            return f"{substituto.strip()} {resto}".strip()
    return t


def normalizar_logradouro(logradouro: str | None) -> str:
    expandido = expandir_tipo_via(colapsar_espacos(logradouro or ""))
    return expandir_iniciais_nomes_logradouro(expandido)


_INICIAIS_NOME_VIA: dict[str, str] = {
    "j": "José",
    "a": "Antônio",
    "f": "Francisco",
    "m": "Maria",
    "p": "Pedro",
    "l": "Luiz",
    "r": "Rodrigues",
    "g": "Gabriel",
    "c": "Carlos",
    "e": "Eduardo",
}


def expandir_iniciais_nomes_logradouro(texto: str) -> str:
    """Expande iniciais comuns em nomes de vias (ex.: «laurindo j gonçalves» → «… José …»)."""
    t = colapsar_espacos(texto)
    if not t:
        return ""
    for ini, nome in _INICIAIS_NOME_VIA.items():
        if len(ini) != 1:
            continue
        t = re.sub(
            rf"(\S+)\s+{re.escape(ini)}\s+(\S+)",
            rf"\1 {nome} \2",
            t,
            flags=re.IGNORECASE,
        )
        t = re.sub(
            rf"(\S+)\s+{re.escape(ini)}\.\s+(\S+)",
            rf"\1 {nome} \2",
            t,
            flags=re.IGNORECASE,
        )
    return colapsar_espacos(t)


def normalizar_bairro(bairro: str | None) -> str:
    return expandir_prefixo_bairro(colapsar_espacos(bairro or ""))


def chave_endereco_canonica(
    logradouro: str | None,
    bairro: str | None,
    cep: str | None,
) -> str:
    cep_limpo = re.sub(r"\D", "", (cep or "").strip())
    logr = sem_acentos(normalizar_logradouro(logradouro).lower())
    bai = sem_acentos(normalizar_bairro(bairro).lower())
    return f"{cep_limpo}|{logr}|{bai}"


def endereco_minimo_para_geocode(logradouro: str | None, bairro: str | None) -> bool:
    return bool(normalizar_logradouro(logradouro) and normalizar_bairro(bairro))


def fonte_coordenada_precisa(fonte: str | None) -> bool:
    return (fonte or "").strip().lower() in _FONTES_COORDENADA_PRECISA


def fonte_coordenada_aproximada(fonte: str | None) -> bool:
    return (fonte or "").strip().lower() in _FONTES_COORDENADA_APROXIMADA


def coordenadas_elegiveis_cluster(
    latitude: float | None,
    longitude: float | None,
    fonte: str | None,
    logradouro: str | None,
    bairro: str | None,
) -> bool:
    if latitude is None or longitude is None:
        return False
    if not endereco_minimo_para_geocode(logradouro, bairro):
        return False
    return fonte_coordenada_precisa(fonte)


def filtrar_coordenadas_para_persistencia(
    latitude: float | None,
    longitude: float | None,
    fonte: str | None,
    logradouro: str | None,
    bairro: str | None,
) -> tuple[float | None, float | None, str]:
    """
    Retorna coordenadas apenas quando há logradouro+bairro e fonte precisa o bastante
    para cluster (~300 m). Caso contrário, descarta lat/lng na persistência.
    """
    if latitude is None or longitude is None:
        return None, None, "indisponivel"
    fonte_norm = (fonte or "indisponivel").strip().lower()
    if not endereco_minimo_para_geocode(logradouro, bairro):
        return None, None, fonte_norm
    if fonte_coordenada_aproximada(fonte_norm):
        return None, None, fonte_norm
    if not fonte_coordenada_precisa(fonte_norm):
        return None, None, fonte_norm
    return latitude, longitude, fonte_norm


def bairros_equivalentes(
    bairro_a: str | None,
    bairro_b: str | None,
    *,
    fuzzy_threshold: int | None = None,
) -> bool:
    a = sem_acentos(normalizar_bairro(bairro_a).lower())
    b = sem_acentos(normalizar_bairro(bairro_b).lower())
    if not a or not b:
        return False
    if a == b:
        return True
    limiar = fuzzy_threshold
    if limiar is None:
        from django.conf import settings

        limiar = int(getattr(settings, "GEOCODING_BAIRRO_FUZZY_THRESHOLD", 90))
    if limiar <= 0:
        return False
    try:
        from fuzzywuzzy import fuzz

        return fuzz.ratio(a, b) >= limiar
    except ImportError:
        return False


def endereco_resumo_humano(
    endereco: dict[str, Any] | None,
    *,
    logradouro: str | None = None,
    bairro: str | None = None,
    cep: str | None = None,
    numero: str | None = None,
) -> str:
    """Texto legível para exibição no Copiloto (logradouro, bairro, CEP)."""
    end = endereco if isinstance(endereco, dict) else {}
    logr = normalizar_logradouro(logradouro or end.get("logradouro") or "")
    bai = normalizar_bairro(bairro or end.get("bairro") or "")
    cep_fmt = (cep or end.get("cep") or "").strip()
    num = (numero or end.get("numero") or "").strip()
    partes: list[str] = []
    if logr:
        trecho = f"{logr}{f', {num}' if num else ''}"
        partes.append(trecho)
    if bai:
        partes.append(f"Bairro {bai}")
    if cep_fmt:
        partes.append(f"CEP {cep_fmt}")
    return " · ".join(partes)


def montar_alerta_geocode(
    *,
    logradouro: str | None,
    bairro: str | None,
    cep: str | None,
    latitude: float | None,
    longitude: float | None,
    endereco_informado: bool = False,
) -> str | None:
    """
    Alerta não bloqueante quando há tentativa de informar local sem lat/lng persistível.
    """
    if latitude is not None and longitude is not None:
        return None
    logr = normalizar_logradouro(logradouro or "")
    bai = normalizar_bairro(bairro or "")
    cep_limpo = re.sub(r"\D", "", (cep or "").strip())
    if not endereco_informado and not logr and not bai and len(cep_limpo) < 8:
        return None
    if logr and bai:
        return (
            "Endereço identificado (logradouro e bairro), mas não foi possível obter "
            "coordenadas precisas no mapa. O fluxo continua; o agrupamento por proximidade "
            "usará o bairro quando necessário."
        )
    if logr or bai or len(cep_limpo) == 8:
        return (
            "Local parcialmente identificado. Informe CEP ou complete logradouro e bairro "
            "para melhorar a localização. O fluxo continua normalmente."
        )
    return None


def variantes_tipo_via_logradouro(logradouro: str) -> list[str]:
    """Gera formas alternativas Av./Avenida e R./Rua para consulta OSM."""
    base = normalizar_logradouro(logradouro)
    if not base:
        return []

    vistos: set[str] = set()
    ordem: list[str] = []

    def push(valor: str) -> None:
        v = colapsar_espacos(valor)
        if len(v) < 6:
            return
        chave = sem_acentos(v.lower())
        if chave in vistos:
            return
        vistos.add(chave)
        ordem.append(v)

    push(base)

    m = re.match(
        r"^(Avenida|Av\.?|Rua|R\.?|Travessa|Trav\.?|Alameda|Al\.?)\s+(.+)$",
        base,
        re.IGNORECASE,
    )
    if not m:
        return ordem

    tipo, resto = m.group(1), m.group(2).strip()
    tl = tipo.lower()
    if tl.startswith("av") or tl == "avenida":
        push(f"Avenida {resto}")
        push(f"Av. {resto}")
        push(f"Av {resto}")
    elif tl.startswith("r") or tl == "rua":
        push(f"Rua {resto}")
        push(f"R. {resto}")
    elif tl.startswith("trav") or tl == "travessa":
        push(f"Travessa {resto}")
        push(f"Trav. {resto}")

    return ordem
