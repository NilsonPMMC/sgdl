"""Servico de triagem: cruza o embedding da Demanda com a Carta de
Servicos do barramento Sinapse para sugerir o `Servico`/`Orgao`
responsavel.

Assinatura publica:

    TriagemService().buscar_servico_sinapse(
        embedding_demanda: list[float],
        top_k: int = 3,
        texto_consulta: str | None = None,
    ) -> list[dict]

Cada item retornado:

    {
        "servico_id": int,
        "titulo": str,
        "orgao": str | None,
        "categoria": str | None,
        "score": float,   # similaridade de cosseno em [-1, 1]; 1.0 = identico
        "distancia": float,  # CosineDistance pgvector = 1 - score
    }

Estrategia de calculo:
- A coluna `catalog_servico.embedding` no Sinapse e `vector(1024)` (pgvector
  0.8.1), nao TextField/JSON. Por isso a similaridade roda *no Postgres do
  Sinapse* via `pgvector.django.CosineDistance` (varredura nativa, sem
  carregar 557+ vetores para a memoria). Mantemos um fallback puro-Python
  (sem numpy) caso a coluna seja text/json em algum ambiente legado.
- Com `texto_consulta`, mescla resultados cujo `titulo` ou `texto_limpo_rag`
  contém termos típicos de zeladoria (ex.: buraco/tapa), para reduzir
  divergência entre o modelo de embedding da consulta e o usado na carta.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from django.conf import settings
from django.db import connections
from django.db.models import Q

logger = logging.getLogger(__name__)


SINAPSE_DB_ALIAS = "sinapse"


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosseno puro Python — fallback quando a base nao usa pgvector."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


class TriagemService:
    """Sugere Servico/Orgao do Sinapse para uma Demanda do SGDL."""

    def __init__(self) -> None:
        self._sinapse_available = SINAPSE_DB_ALIAS in connections.databases

    def buscar_servico_sinapse(
        self,
        embedding_demanda: list[float],
        top_k: int = 3,
        texto_consulta: str | None = None,
    ) -> list[dict[str, Any]]:
        """Busca por similaridade de vetor no Postgres Sinapse (pgvector).

        Opcionalmente mescla (`texto_consulta`) reforço lexical em `titulo` e
        `texto_limpo_rag` para casos em que o modelo de embedding da consulta
        diverge do usado na indexação da carta.
        """
        if not self._sinapse_available:
            logger.warning(
                "TriagemService: DB '%s' nao configurado; pulando triagem Sinapse.",
                SINAPSE_DB_ALIAS,
            )
            return []
        if not embedding_demanda:
            logger.debug("TriagemService: embedding vazio; nada a buscar.")
            return []
        if top_k <= 0:
            return []

        texto_opt = (texto_consulta or "").strip()
        fetch_k = max(top_k, 14) if texto_opt else top_k

        try:
            vetorial = self._buscar_via_pgvector(embedding_demanda, fetch_k)
        except Exception as exc:  # noqa: BLE001 - log + fallback
            logger.warning(
                "TriagemService: CosineDistance pgvector falhou (%s); "
                "tentando fallback in-memory.",
                exc,
            )
            try:
                vetorial = self._buscar_via_fallback(embedding_demanda, fetch_k)
            except Exception as exc2:  # noqa: BLE001
                logger.exception("TriagemService: fallback in-memory tambem falhou: %s", exc2)
                vetorial = []

        if texto_opt and getattr(settings, "SINAPSE_TRIAGEM_LEXICAL_MERGE", True):
            lexical = self._busca_lexical_sinapse(texto_opt, limit=max(top_k, 10))
            out = self._merge_vetorial_lexical(vetorial, lexical, top_k)
        else:
            out = vetorial[:top_k]

        if getattr(settings, "SINAPSE_TRIAGEM_LOG", False) and out:
            logger.info(
                "TriagemSinapse top_k=%s texto=%r -> %s",
                top_k,
                texto_opt[:200],
                [(r.get("servico_id"), (r.get("titulo") or "")[:56], r.get("score")) for r in out],
            )
        return out

    @staticmethod
    def _termos_lexicais(texto: str) -> list[str]:
        """Extrai termos para OR em titulo/texto_limpo_rag (zeladoria comum)."""
        t = (texto or "").lower()
        termos: list[str] = []
        if any(w in t for w in ("buraco", "buracos", "asfalto", "paviment", "via", "ladeira", "recape")):
            termos.extend(["buraco", "tapa", "asfalt", "paviment", "recape"])
        if "calçada" in t or "calcada" in t:
            termos.append("calçada")
        if any(w in t for w in ("lombada", "lombadas", "redutor", "velocidade")):
            # Não usar «trânsito»/«transito» soltos: poluem com dezenas de serviços da SMT.
            termos.extend(["lombada", "lombadas", "redutor", "implantação de lombada", "manutenção de lombada"])
        if any(w in t for w in ("ilum", "luz", "lâmpada", "lampada", "poste", "escuro")):
            termos.extend(["ilumina", "lâmpada", "poste"])
        if any(w in t for w in ("lixo", "entulho", "varri", "sujeira", "mato", "capina")):
            termos.extend(["lixo", "entulho", "varrição", "capina", "limpeza"])
        if any(w in t for w in ("bueiro", "boca de lobo", "galeria", "enxurrada")):
            termos.extend(["bueiro", "galeria", "drenag"])
        if any(w in t for w in ("reserva", "reservar", "espaço", "espaco", "evento", "eventos")):
            termos.extend(["reserva", "espaços", "eventos", "espaço"])
            if any(w in t for w in ("parque", "centenário", "centenario", "centen", "feffer")):
                termos.extend(
                    ["parque centen", "centenário", "centenario", "centen", "parque", "eventos"]
                )
        if any(w in t for w in ("ação social", "acao social")) and "parque" in t:
            termos.extend(["reserva", "eventos", "parque", "centen"])
        # dedupe preservando ordem
        seen: set[str] = set()
        out: list[str] = []
        for x in termos:
            k = x.lower()
            if k not in seen and len(k) >= 3:
                seen.add(k)
                out.append(x)
        return out[:12]

    @staticmethod
    def _termos_obrigatorios_lexical(texto: str) -> list[str]:
        """Substrings que devem aparecer no título/RAG (evita falso positivo em «trânsito» genérico)."""
        t = (texto or "").lower()
        obrig: list[str] = []
        if "lombad" in t:
            obrig.append("lombad")
        if any(w in t for w in ("tapa", "buraco", "buracos")):
            obrig.append("tapa")
            if "burac" in t:
                obrig.append("burac")
        if any(w in t for w in ("ilum", "lâmpada", "lampada", "luminária", "luminaria")):
            obrig.append("ilum")
        if "centen" in t and any(w in t for w in ("reserva", "parque", "evento", "espaço", "espaco")):
            obrig.extend(["centen", "reserva"])
        return obrig

    def _rows_lexicais_de_queryset(self, qs) -> list[dict[str, Any]]:
        return [
            {
                "servico_id": int(s.id),
                "titulo": (s.titulo or "").strip(),
                "orgao": getattr(s.id_orgao, "nome", None),
                "categoria": getattr(s.id_categoria, "nome", None),
                "score": None,
                "distancia": None,
            }
            for s in qs
        ]

    def _busca_lexical_sinapse(self, texto: str, limit: int) -> list[dict[str, Any]]:
        from integrations.models_sinapse import CatalogServico

        obrig = self._termos_obrigatorios_lexical(texto)
        needles = self._termos_lexicais(texto)
        if not obrig and not needles:
            return []

        out: list[dict[str, Any]] = []
        seen: set[int] = set()

        if obrig:
            q_obrig = Q()
            for o in obrig:
                q_obrig |= Q(titulo__icontains=o) | Q(texto_limpo_rag__icontains=o)
            qs_obrig = (
                CatalogServico.objects.using(SINAPSE_DB_ALIAS)
                .filter(status=1)
                .filter(q_obrig)
                .select_related("id_orgao", "id_categoria")
                .only("id", "titulo", "id_orgao__nome", "id_categoria__nome")
            )
            for row in self._rows_lexicais_de_queryset(qs_obrig):
                sid = int(row["servico_id"])
                if sid in seen:
                    continue
                seen.add(sid)
                titulo_low = (row.get("titulo") or "").lower()
                if all(o in titulo_low or o in (row.get("titulo") or "").lower() for o in obrig):
                    row = dict(row)
                    row["score"] = 0.92
                    row["distancia"] = 0.08
                    out.append(row)
                if len(out) >= limit:
                    return out

        if needles and len(out) < limit:
            q = Q()
            for n in needles:
                q |= Q(titulo__icontains=n) | Q(texto_limpo_rag__icontains=n)
            restante = int(limit) - len(out)
            qs = (
                CatalogServico.objects.using(SINAPSE_DB_ALIAS)
                .filter(status=1)
                .filter(q)
                .select_related("id_orgao", "id_categoria")
                .only("id", "titulo", "id_orgao__nome", "id_categoria__nome")[: max(restante, restante + 8)]
            )
            for row in self._rows_lexicais_de_queryset(qs):
                sid = int(row["servico_id"])
                if sid in seen:
                    continue
                seen.add(sid)
                out.append(row)
                if len(out) >= limit:
                    break
        return out

    @staticmethod
    def _merge_vetorial_lexical(
        vetorial: list[dict[str, Any]],
        lexical: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Prioriza matches lexicais, completa com ranking vetorial."""
        vec_by_id = {int(x["servico_id"]): dict(x) for x in vetorial if x.get("servico_id") is not None}
        seen: set[int] = set()
        merged: list[dict[str, Any]] = []

        for row in lexical:
            sid = int(row["servico_id"])
            if sid in seen:
                continue
            seen.add(sid)
            if sid in vec_by_id:
                entry = dict(vec_by_id[sid])
                lex_score = row.get("score")
                if lex_score is not None and (entry.get("score") or 0) < lex_score:
                    entry["score"] = lex_score
                merged.append(entry)
            else:
                merged.append(
                    {
                        **row,
                        "score": row.get("score") if row.get("score") is not None else 0.52,
                        "distancia": row.get("distancia") if row.get("distancia") is not None else 0.48,
                    }
                )
            if len(merged) >= top_k:
                return merged

        for row in vetorial:
            sid = int(row["servico_id"])
            if sid not in seen:
                merged.append(dict(row))
                seen.add(sid)
            if len(merged) >= top_k:
                break
        return merged[:top_k]

    def _buscar_via_pgvector(
        self, embedding_demanda: list[float], top_k: int
    ) -> list[dict[str, Any]]:
        """Caminho rapido: CosineDistance executado no Postgres do Sinapse."""
        from pgvector.django import CosineDistance

        from integrations.models_sinapse import CatalogServico

        qs = (
            CatalogServico.objects.using(SINAPSE_DB_ALIAS)
            .filter(status=1)
            .exclude(embedding__isnull=True)
            .annotate(distancia=CosineDistance("embedding", embedding_demanda))
            .select_related("id_orgao", "id_categoria")
            .only(
                "id",
                "titulo",
                "id_orgao__nome",
                "id_categoria__nome",
            )
            .order_by("distancia")[: int(top_k)]
        )

        resultados: list[dict[str, Any]] = []
        for servico in qs:
            distancia = float(getattr(servico, "distancia", 1.0))
            score = max(-1.0, min(1.0, 1.0 - distancia))
            resultados.append(
                {
                    "servico_id": int(servico.id),
                    "titulo": (servico.titulo or "").strip(),
                    "orgao": getattr(servico.id_orgao, "nome", None),
                    "categoria": getattr(servico.id_categoria, "nome", None),
                    "score": round(score, 4),
                    "distancia": round(distancia, 4),
                }
            )
        return resultados

    def _buscar_via_fallback(
        self, embedding_demanda: list[float], top_k: int
    ) -> list[dict[str, Any]]:
        """Fallback: traz vetores e calcula cosseno em Python.

        Usado se em algum ambiente legado a coluna ainda for TextField/JSON
        (formato MOVA antigo). Iteracao limitada para nao estourar memoria.
        """
        import json

        from integrations.models_sinapse import CatalogServico

        candidatos = (
            CatalogServico.objects.using(SINAPSE_DB_ALIAS)
            .filter(status=1)
            .exclude(embedding__isnull=True)
            .select_related("id_orgao", "id_categoria")
            .only("id", "titulo", "id_orgao__nome", "id_categoria__nome", "embedding")
            .iterator(chunk_size=200)
        )

        ranking: list[tuple[float, dict[str, Any]]] = []
        for servico in candidatos:
            raw = servico.embedding
            if raw is None:
                continue
            if isinstance(raw, (list, tuple)):
                vetor = list(raw)
            elif isinstance(raw, str):
                if not raw.strip():
                    continue
                try:
                    vetor = json.loads(raw)
                except (ValueError, TypeError):
                    continue
            else:
                continue

            score = cosine_similarity(list(embedding_demanda), list(vetor))
            ranking.append(
                (
                    score,
                    {
                        "servico_id": int(servico.id),
                        "titulo": (servico.titulo or "").strip(),
                        "orgao": getattr(servico.id_orgao, "nome", None),
                        "categoria": getattr(servico.id_categoria, "nome", None),
                        "score": round(score, 4),
                        "distancia": round(1.0 - score, 4),
                    },
                )
            )

        ranking.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in ranking[: int(top_k)]]
