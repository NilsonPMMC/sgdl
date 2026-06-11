"""Registro e deduplicação de tendências (solicitações fora da carta Sinapse)."""

from __future__ import annotations

import logging
import unicodedata
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.text import slugify

from core.models import Demanda, Tendencia, TendenciaOcorrencia
from core.services.vector_service import EMBEDDING_DIMENSIONS, VectorService

logger = logging.getLogger(__name__)

STATUS_ATIVOS = (
    Tendencia.STATUS_ABERTA,
    Tendencia.STATUS_EM_ANALISE,
)


def normalizar_slug(texto: str) -> str:
    """Slug ASCII estável para dedup lexical."""
    bruto = (texto or "").strip()
    if not bruto:
        return "tendencia"
    nfkd = unicodedata.normalize("NFKD", bruto)
    ascii_txt = nfkd.encode("ascii", "ignore").decode("ascii")
    base = slugify(ascii_txt) or slugify(bruto) or "tendencia"
    return base[:200]


class TendenciaService:
    """Busca tendências similares (1024d) e registra ocorrências."""

    def __init__(self) -> None:
        self.vector = VectorService()
        self.threshold = float(
            getattr(settings, "TENDENCIA_SIMILARITY_THRESHOLD", 0.85)
        )

    def texto_para_embedding(self, *, titulo: str, descricao: str = "", extra: str = "") -> str:
        partes = [titulo.strip(), descricao.strip(), extra.strip()]
        return " — ".join(p for p in partes if p)[:2000]

    def buscar_similares(
        self,
        texto: str,
        *,
        limite: int = 5,
        embedding: list[float] | None = None,
    ) -> list[dict[str, Any]]:
        """Retorna tendências ativas semanticamente próximas do texto."""
        vetor = embedding or self.vector.generate_embedding(
            self.texto_para_embedding(titulo=texto, extra=texto)
        )
        if not vetor:
            return []

        qs = self._queryset_similares(vetor, limite=limite)
        out: list[dict[str, Any]] = []
        for t in qs:
            dist = getattr(t, "distancia", None)
            sim = None
            if dist is not None:
                sim = max(0.0, min(1.0, 1.0 - float(dist)))
            out.append(self._serializar_tendencia(t, similaridade=sim))
        return out

    def buscar_ou_criar(
        self,
        *,
        titulo: str,
        texto_embedding: str | None = None,
        descricao_resumo: str = "",
        sinapse_orgao_id: int | None = None,
        criado_por=None,
        score_triagem_max: float | None = None,
    ) -> Tendencia:
        """Reutiliza tendência similar ou cria nova com embedding."""
        titulo_limpo = (titulo or "Solicitação fora da carta").strip()[:200]
        texto_emb = (
            texto_embedding
            or self.texto_para_embedding(titulo=titulo_limpo, descricao=descricao_resumo)
        )
        vetor = self.vector.generate_embedding(texto_emb)

        existente = None
        if vetor:
            candidatos = list(self._queryset_similares(vetor, limite=1))
            if candidatos:
                existente = candidatos[0]

        if existente is None:
            slug_base = normalizar_slug(titulo_limpo)
            existente = Tendencia.objects.filter(slug=slug_base).first()

        if existente:
            return self._atualizar_tendencia_existente(
                existente,
                vetor=vetor,
                texto_canonico=texto_emb,
                sinapse_orgao_id=sinapse_orgao_id,
            )

        slug = self._slug_unico(normalizar_slug(titulo_limpo))
        return Tendencia.objects.create(
            slug=slug,
            titulo=titulo_limpo,
            texto_canonico=texto_emb[:5000],
            descricao_resumo=(descricao_resumo or "")[:5000],
            embedding=vetor if vetor else None,
            sinapse_orgao_id=sinapse_orgao_id,
            criado_por=criado_por,
            status=Tendencia.STATUS_ABERTA,
            volume_total=0,
        )

    @transaction.atomic
    def registrar_ocorrencia(
        self,
        tendencia: Tendencia,
        *,
        demanda: Demanda | None = None,
        session=None,
        indice_demanda: int | None = None,
        texto_origem: str = "",
        score_triagem_max: float | None = None,
    ) -> TendenciaOcorrencia:
        """Incrementa volume e grava ocorrência."""
        Tendencia.objects.filter(pk=tendencia.pk).update(
            volume_total=F("volume_total") + 1,
            ultima_ocorrencia=timezone.now(),
        )
        tendencia.refresh_from_db(fields=["volume_total", "ultima_ocorrencia"])
        return TendenciaOcorrencia.objects.create(
            tendencia=tendencia,
            demanda=demanda,
            session=session,
            indice_demanda=indice_demanda,
            texto_origem=(texto_origem or "")[:8000],
            score_triagem_max=score_triagem_max,
        )

    def promover_para_carta(
        self,
        tendencia: Tendencia,
        *,
        sinapse_servico_id: int,
        usuario=None,
    ) -> Tendencia:
        if not sinapse_catalog_servico_existe(sinapse_servico_id):
            raise ValueError("Serviço não encontrado na carta Sinapse.")
        tendencia.sinapse_servico_id = int(sinapse_servico_id)
        tendencia.status = Tendencia.STATUS_VINCULADA_CARTA
        orgao_id = get_orgao_id_for_servico(sinapse_servico_id)
        if orgao_id:
            tendencia.sinapse_orgao_id = orgao_id
        tendencia.save(
            update_fields=[
                "sinapse_servico_id",
                "sinapse_orgao_id",
                "status",
                "ultima_ocorrencia",
            ]
        )
        logger.info(
            "Tendência %s promovida ao serviço Sinapse %s por %s",
            tendencia.pk,
            sinapse_servico_id,
            getattr(usuario, "username", "?"),
        )
        return tendencia

    def _queryset_similares(self, embedding: list[float], *, limite: int):
        if len(embedding) != EMBEDDING_DIMENSIONS:
            return Tendencia.objects.none()

        from django.db import connection

        if connection.vendor != "postgresql":
            return Tendencia.objects.none()

        try:
            from pgvector.django import CosineDistance
        except ImportError:
            logger.error("pgvector indisponível para busca de tendências.")
            return Tendencia.objects.none()

        max_distance = max(0.0, min(2.0, 1.0 - self.threshold))
        return (
            Tendencia.objects.filter(
                embedding__isnull=False,
                status__in=STATUS_ATIVOS,
            )
            .annotate(distancia=CosineDistance("embedding", embedding))
            .filter(distancia__lte=max_distance)
            .order_by("distancia")[:limite]
        )

    def _slug_unico(self, base: str) -> str:
        slug = base or "tendencia"
        if not Tendencia.objects.filter(slug=slug).exists():
            return slug
        for n in range(2, 1000):
            candidato = f"{slug[:200]}-{n}"
            if not Tendencia.objects.filter(slug=candidato).exists():
                return candidato
        return f"{slug}-{timezone.now().strftime('%Y%m%d%H%M%S')}"

    def _atualizar_tendencia_existente(
        self,
        tendencia: Tendencia,
        *,
        vetor: list[float],
        texto_canonico: str,
        sinapse_orgao_id: int | None,
    ) -> Tendencia:
        updates: dict[str, Any] = {"ultima_ocorrencia": timezone.now()}
        if vetor and tendencia.embedding is None:
            updates["embedding"] = vetor
        if texto_canonico and not tendencia.texto_canonico:
            updates["texto_canonico"] = texto_canonico[:5000]
        if sinapse_orgao_id and not tendencia.sinapse_orgao_id:
            updates["sinapse_orgao_id"] = sinapse_orgao_id
        if updates:
            for k, v in updates.items():
                setattr(tendencia, k, v)
            tendencia.save(update_fields=list(updates.keys()))
        return tendencia

    @staticmethod
    def _serializar_tendencia(
        tendencia: Tendencia, *, similaridade: float | None = None
    ) -> dict[str, Any]:
        from integrations import sinapse_catalog

        return {
            "id": tendencia.id,
            "slug": tendencia.slug,
            "titulo": tendencia.titulo,
            "descricao_resumo": tendencia.descricao_resumo,
            "status": tendencia.status,
            "volume_total": tendencia.volume_total,
            "sinapse_orgao_id": tendencia.sinapse_orgao_id,
            "sinapse_orgao_nome": sinapse_catalog.get_orgao_nome(tendencia.sinapse_orgao_id),
            "sinapse_servico_id": tendencia.sinapse_servico_id,
            "similaridade": similaridade,
            "primeira_ocorrencia": tendencia.primeira_ocorrencia,
            "ultima_ocorrencia": tendencia.ultima_ocorrencia,
        }


def sinapse_catalog_servico_existe(servico_id: int) -> bool:
    from integrations import sinapse_catalog

    return sinapse_catalog.servico_existe(servico_id)


def get_orgao_id_for_servico(servico_id: int) -> int | None:
    from integrations import sinapse_catalog

    return sinapse_catalog.get_orgao_id_for_servico(servico_id)
