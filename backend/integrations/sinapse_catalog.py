"""Leitura do catálogo Sinapse (CatalogServico / CatalogOrgao) para o SGDL."""

from __future__ import annotations

import re
from functools import lru_cache
from html import unescape
from typing import Any

from django.db import connections

from integrations.models_sinapse import CatalogOrgao, CatalogServico, SINAPSE_DB_ALIAS

DEFAULT_TIPO_SERVICO = "SERVIÇO"
CHOICES_SERVICO_LIMIT = 2000
CHOICES_ORGAO_LIMIT = 500


def _strip_html(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


_CHAVES_SERVICO_REQUER_LOCAL = (
    "zeladoria",
    "tapa",
    "buraco",
    "lombada",
    "reserva",
    "espaço",
    "espaco",
    "parque",
    "evento",
    "reforma",
    "implanta",
    "poda",
    "capina",
    "iluminação",
    "iluminacao",
    "coleta",
    "limpeza",
    "vistoria",
    "alvará",
    "alvara",
    "paviment",
    "asfalt",
    "cascalh",
    "nivelamento",
    "drenagem",
    "bueiro",
    "galeria",
    "calçada",
    "calcada",
    "praça",
    "praca",
    "via",
    "rua",
    "avenida",
    "logradouro",
    "endereço",
    "endereco",
    "bairro",
)


@lru_cache(maxsize=1024)
def servico_requer_localizacao(servico_id: int | None) -> bool:
    """Heurística: serviços de local físico exigem proximidade geográfica no cluster."""
    if not servico_id:
        return True
    servico = get_servico(servico_id)
    if not servico:
        return True
    titulo = (getattr(servico, "titulo", None) or "").strip()
    descricao = _strip_html(
        getattr(servico, "descricao_html", None)
        or getattr(servico, "descricao", None)
    )
    blob = f"{titulo} {descricao}".lower().strip()
    if not blob:
        return True
    return any(chave in blob for chave in _CHAVES_SERVICO_REQUER_LOCAL)


def parse_prazo_dias(value: Any) -> int | None:
    text = _strip_html(value).lower()
    if not text:
        return None
    match = re.search(r"\d+", text)
    if not match:
        return None
    number = int(match.group(0))
    if "mes" in text:
        return number * 30
    return number


@lru_cache(maxsize=512)
def get_orgao(orgao_id: int | None) -> CatalogOrgao | None:
    if not orgao_id:
        return None
    return (
        CatalogOrgao.objects.using(SINAPSE_DB_ALIAS)
        .filter(pk=orgao_id)
        .first()
    )


@lru_cache(maxsize=2048)
def get_servico(servico_id: int | None) -> CatalogServico | None:
    if not servico_id:
        return None
    return (
        CatalogServico.objects.using(SINAPSE_DB_ALIAS)
        .select_related("id_orgao")
        .filter(pk=servico_id)
        .first()
    )


def orgao_to_dict(orgao: CatalogOrgao | None) -> dict[str, Any] | None:
    if not orgao:
        return None
    return {"id": orgao.id, "nome": orgao.nome}


def servico_to_dict(servico: CatalogServico | None) -> dict[str, Any] | None:
    if not servico:
        return None
    orgao = servico.id_orgao
    return {
        "id": servico.id,
        "nome": servico.titulo,
        "tipo": DEFAULT_TIPO_SERVICO,
        "prazo": parse_prazo_dias(servico.prazo),
        "secretaria_responsavel": orgao_to_dict(orgao),
    }


def get_orgao_id_for_servico(servico_id: int | None) -> int | None:
    servico = get_servico(servico_id)
    if not servico or not servico.id_orgao_id:
        return None
    return int(servico.id_orgao_id)


def prazo_dias(servico_id: int | None) -> int | None:
    servico = get_servico(servico_id)
    if not servico:
        return None
    return parse_prazo_dias(servico.prazo)


def get_orgao_nome(orgao_id: int | None) -> str | None:
    orgao = get_orgao(orgao_id)
    return orgao.nome if orgao else None


def servico_existe(servico_id: int) -> bool:
    return (
        CatalogServico.objects.using(SINAPSE_DB_ALIAS)
        .filter(pk=servico_id)
        .exists()
    )


def orgao_existe(orgao_id: int) -> bool:
    return (
        CatalogOrgao.objects.using(SINAPSE_DB_ALIAS)
        .filter(pk=orgao_id)
        .exists()
    )


def catalog_disponivel() -> bool:
    return SINAPSE_DB_ALIAS in connections.databases


def _label_orgao(orgao: CatalogOrgao) -> str:
    return f"[{orgao.id}] {orgao.nome}"


def _label_servico(servico: CatalogServico) -> str:
    titulo = (servico.titulo or "").strip()
    if len(titulo) > 90:
        titulo = titulo[:90] + "…"
    orgao_nome = ""
    if servico.id_orgao_id:
        orgao = servico.id_orgao
        if orgao:
            orgao_nome = f" — {orgao.nome}"
    return f"[{servico.id}] {titulo}{orgao_nome}"


def choices_orgaos(
    *,
    limit: int = CHOICES_ORGAO_LIMIT,
    include_id: int | None = None,
) -> list[tuple[int, str]]:
    """Opções para `<select>` de órgãos (admin e formulários internos)."""
    if not catalog_disponivel():
        return []
    seen: set[int] = set()
    out: list[tuple[int, str]] = []
    if include_id is not None:
        extra = get_orgao(int(include_id))
        if extra:
            seen.add(int(extra.id))
            out.append((int(extra.id), _label_orgao(extra)))
    for orgao in CatalogOrgao.objects.using(SINAPSE_DB_ALIAS).order_by("nome")[:limit]:
        oid = int(orgao.id)
        if oid in seen:
            continue
        seen.add(oid)
        out.append((oid, _label_orgao(orgao)))
    return out


def choices_servicos(
    *,
    limit: int = CHOICES_SERVICO_LIMIT,
    orgao_id: int | None = None,
    include_id: int | None = None,
) -> list[tuple[int, str]]:
    """Opções para `<select>` de serviços da carta Sinapse."""
    if not catalog_disponivel():
        return []
    seen: set[int] = set()
    out: list[tuple[int, str]] = []

    def _append(servico: CatalogServico) -> None:
        sid = int(servico.id)
        if sid in seen:
            return
        seen.add(sid)
        out.append((sid, _label_servico(servico)))

    if include_id is not None:
        extra = get_servico(int(include_id))
        if extra:
            _append(extra)

    qs = CatalogServico.objects.using(SINAPSE_DB_ALIAS).select_related("id_orgao").order_by("titulo")
    if orgao_id:
        qs = qs.filter(id_orgao_id=orgao_id)
    for servico in qs[:limit]:
        _append(servico)
    return out


def list_orgaos_api(*, limit: int = 500) -> list[dict[str, Any]]:
    if not catalog_disponivel():
        return []
    qs = CatalogOrgao.objects.using(SINAPSE_DB_ALIAS).order_by("nome")[:limit]
    return [orgao_to_dict(o) for o in qs if o]


def list_servicos_api(*, limit: int = 2000, orgao_id: int | None = None) -> list[dict[str, Any]]:
    if not catalog_disponivel():
        return []
    qs = CatalogServico.objects.using(SINAPSE_DB_ALIAS).select_related("id_orgao").order_by("titulo")
    if orgao_id:
        qs = qs.filter(id_orgao_id=orgao_id)
    qs = qs[:limit]
    return [servico_to_dict(s) for s in qs if s]


def servico_detalhe_dict(servico_id: int) -> dict[str, Any] | None:
    """Ficha completa do serviço para o Explorer da Carta."""
    servico = get_servico(servico_id)
    if not servico:
        return None
    categoria = servico.id_categoria
    orgao = servico.id_orgao
    docs = _strip_html(servico.documentos_necessarios)
    return {
        "id": servico.id,
        "titulo": (servico.titulo or "").strip(),
        "slug": (servico.slug or "").strip() or None,
        "status": servico.status,
        "descricao": _strip_html(servico.descricao_html),
        "documentos_necessarios": docs,
        "prazo_texto": _strip_html(servico.prazo),
        "prazo_dias": parse_prazo_dias(servico.prazo),
        "requisitos": _strip_html(servico.requisitos_html),
        "observacoes": _strip_html(servico.observacoes_html),
        "departamento": _strip_html(servico.departamento),
        "orgao": orgao_to_dict(orgao),
        "categoria": (
            {"id": categoria.id, "nome": categoria.nome} if categoria else None
        ),
        "tem_embedding": servico.embedding is not None,
    }


def buscar_servicos_catalogo(
    *,
    q: str = "",
    orgao_id: int | None = None,
    limit: int = 40,
    offset: int = 0,
) -> dict[str, Any]:
    """Busca paginada na carta Sinapse (título, texto RAG, documentos)."""
    if not catalog_disponivel():
        return {"total": 0, "results": [], "catalogo_disponivel": False}

    from django.db.models import Q

    qs = (
        CatalogServico.objects.using(SINAPSE_DB_ALIAS)
        .select_related("id_orgao", "id_categoria")
        .filter(status=1)
    )
    if orgao_id:
        qs = qs.filter(id_orgao_id=int(orgao_id))
    termo = (q or "").strip()
    if termo:
        qs = qs.filter(
            Q(titulo__icontains=termo)
            | Q(texto_limpo_rag__icontains=termo)
            | Q(documentos_necessarios__icontains=termo)
        )
    total = qs.count()
    rows = list(qs.order_by("titulo")[offset : offset + limit])
    results: list[dict[str, Any]] = []
    for servico in rows:
        base = servico_to_dict(servico)
        if not base:
            continue
        docs = _strip_html(servico.documentos_necessarios)
        base["prazo_texto"] = _strip_html(servico.prazo)
        base["documentos_resumo"] = (docs[:220] + "…") if len(docs) > 220 else docs
        base["tem_embedding"] = servico.embedding is not None
        results.append(base)
    return {
        "total": total,
        "results": results,
        "catalogo_disponivel": True,
        "offset": offset,
        "limit": limit,
    }


_STOPWORDS_SERVICO = frozenset(
    {
        "solicitação",
        "solicitacao",
        "serviço",
        "servico",
        "gerar",
        "oficio",
        "ofício",
        "pedido",
        "para",
        "com",
        "uma",
        "instalação",
        "instalacao",
    }
)


def _tokens_busca_servico(texto: str) -> list[str]:
    t = (texto or "").lower()
    tokens = [
        w
        for w in re.findall(r"[a-záàâãéêíóôõúç0-9]+", t, flags=re.IGNORECASE)
        if len(w) >= 4 and w not in _STOPWORDS_SERVICO
    ]
    seen: set[str] = set()
    out: list[str] = []
    for w in tokens:
        if w not in seen:
            seen.add(w)
            out.append(w)
    return out[:10]


def _termos_obrigatorios(texto: str) -> list[str]:
    """Substrings que devem aparecer no título do serviço da carta."""
    t = (texto or "").lower()
    obrig: list[str] = []
    if "lombada" in t or "lombadas" in t:
        obrig.append("lombad")
    if any(w in t for w in ("tapa", "buraco", "buracos", "asfalto")):
        obrig.append("tapa")
        if "burac" in t:
            obrig.append("burac")
    if any(w in t for w in ("ilum", "lâmpada", "lampada", "luminária", "luminaria")):
        obrig.append("ilum")
    return obrig


def resolver_servico_por_titulo(titulo: str | None, *, texto_extra: str | None = None) -> int | None:
    """Resolve serviço na carta por pontuação lexical (evita «instalação» → luminária)."""
    texto = " ".join(x for x in (titulo, texto_extra) if x and str(x).strip()).strip()
    if len(texto) < 4:
        return None

    if SINAPSE_DB_ALIAS not in connections.databases:
        return None

    t = texto.strip()
    row = (
        CatalogServico.objects.using(SINAPSE_DB_ALIAS)
        .filter(titulo__iexact=t)
        .values_list("id", flat=True)
        .first()
    )
    if row:
        return int(row)

    tokens = _tokens_busca_servico(t)
    obrig = _termos_obrigatorios(t)
    if not tokens and not obrig:
        return None

    from django.db.models import Q

    q = Q()
    for tok in tokens:
        q |= Q(titulo__icontains=tok)
    for ob in obrig:
        q |= Q(titulo__icontains=ob)
    if not q:
        return None

    candidatos = list(
        CatalogServico.objects.using(SINAPSE_DB_ALIAS)
        .filter(status=1)
        .filter(q)
        .only("id", "titulo")[:40]
    )
    if not candidatos:
        return None

    melhor_id: int | None = None
    melhor_score = -999
    for s in candidatos:
        st = (s.titulo or "").lower()
        score = 0
        for tok in tokens:
            if tok in st:
                score += 4
        if obrig and all(o in st for o in obrig):
            score += 12
        elif obrig:
            score -= 25
        if "lombad" in obrig and "ilumina" in st and "lombad" not in st:
            score -= 30
        if "instala" in tokens and "lombad" in t and "lombad" not in st:
            score -= 15
        if score > melhor_score:
            melhor_score = score
            melhor_id = int(s.id)

    if melhor_id is None or melhor_score < 4:
        return None
    return melhor_id
