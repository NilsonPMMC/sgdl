"""Serviço de geração de embeddings e busca semântica do SGDL.

Segue o padrão do MOVA: consome o Kernel AI (mxbai-embed-large, 1024 dims)
para produzir vetores e usa `pgvector.django.CosineDistance` para localizar
demandas similares já indexadas no banco.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import requests
from django.conf import settings
from django.db.models import QuerySet

if TYPE_CHECKING:
    from core.models import Demanda

logger = logging.getLogger(__name__)


EMBEDDING_DIMENSIONS = 1024


class VectorService:
    """Encapsula chamadas ao Kernel AI e a busca por similaridade no Postgres.

    Suporta dois formatos de payload no POST `/v1/embeddings`:
      - "gabinete" (default, Kernel SGDL/MOVA): {"texts": [text], "model": ...}
      - "openai"   (OpenAI-compatible / Ollama): {"input": text, "model": ...}

    Controle via `settings.AI_KERNEL_EMBEDDING_PAYLOAD` ou env var de mesmo nome.
    """

    def __init__(self) -> None:
        self.base_url = getattr(
            settings, "AI_KERNEL_BASE_URL", "http://localhost:8004"
        ).rstrip("/")
        self.timeout = int(getattr(settings, "AI_KERNEL_TIMEOUT_EMBEDDINGS", 10))
        self.model = getattr(
            settings, "AI_KERNEL_EMBEDDING_MODEL", "mxbai-embed-large"
        )
        self.payload_format = getattr(
            settings, "AI_KERNEL_EMBEDDING_PAYLOAD", "gabinete"
        ).lower()

    def _build_payload(self, text: str) -> dict:
        if self.payload_format == "openai":
            return {"input": text, "model": self.model}
        return {"texts": [text], "model": self.model}

    def generate_embedding(self, text: str) -> list[float]:
        """Gera o embedding (1024 dim) para o texto informado.

        Retorna lista vazia em caso de falha (timeout, indisponibilidade
        do Kernel, payload inesperado, etc.), registrando o erro no log.
        """
        cleaned = (text or "").strip()
        if not cleaned:
            logger.debug("generate_embedding chamado com texto vazio; retornando [].")
            return []

        url = f"{self.base_url}/v1/embeddings"
        payload = self._build_payload(cleaned)

        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except requests.Timeout:
            logger.error(
                "Timeout (%ss) ao gerar embedding no Kernel AI: %s",
                self.timeout,
                url,
            )
            return []
        except requests.ConnectionError as exc:
            logger.error("Falha de conexão com Kernel AI (%s): %s", url, exc)
            return []
        except requests.HTTPError as exc:
            status = getattr(exc.response, "status_code", "?")
            body = getattr(exc.response, "text", "")[:300]
            logger.error(
                "Kernel AI retornou HTTP %s em %s: %s", status, url, body
            )
            return []
        except ValueError as exc:
            logger.error("Resposta inválida (JSON) do Kernel AI em %s: %s", url, exc)
            return []

        embedding = self._extract_embedding(data)
        if not embedding:
            logger.error(
                "Resposta do Kernel AI sem campo de embedding reconhecido: chaves=%s",
                list(data.keys()) if isinstance(data, dict) else type(data).__name__,
            )
            return []

        if len(embedding) != EMBEDDING_DIMENSIONS:
            logger.warning(
                "Dimensão inesperada do embedding: %s (esperado %s).",
                len(embedding),
                EMBEDDING_DIMENSIONS,
            )

        return embedding

    @staticmethod
    def _extract_embedding(data: dict) -> list[float]:
        """Normaliza formatos comuns: OpenAI-like, Ollama e Kernel Gabinete."""
        if not isinstance(data, dict):
            return []
        if "embedding" in data and isinstance(data["embedding"], list):
            return data["embedding"]
        if "embeddings" in data and isinstance(data["embeddings"], list) and data["embeddings"]:
            first = data["embeddings"][0]
            return first if isinstance(first, list) else []
        if "data" in data and isinstance(data["data"], list) and data["data"]:
            first = data["data"][0]
            if isinstance(first, dict) and isinstance(first.get("embedding"), list):
                return first["embedding"]
        return []

    @staticmethod
    def find_similar_demanda(
        embedding: list[float], threshold: float = 0.7
    ) -> "QuerySet[Demanda]":
        """Retorna demandas com similaridade de cosseno >= threshold.

        Usa `pgvector.django.CosineDistance` (distância de cosseno = 1 - sim).
        Ex.: threshold=0.7 -> distância <= 0.3.
        """
        from core.models import Demanda  # noqa: WPS433 (import tardio p/ evitar ciclo)

        if not embedding:
            return Demanda.objects.none()

        try:
            from pgvector.django import CosineDistance
        except ImportError:
            logger.error(
                "pgvector.django não instalado; busca semântica indisponível."
            )
            return Demanda.objects.none()

        max_distance = max(0.0, min(2.0, 1.0 - float(threshold)))

        return (
            Demanda.objects
            .filter(embedding__isnull=False)
            .annotate(distancia=CosineDistance("embedding", embedding))
            .filter(distancia__lte=max_distance)
            .order_by("distancia")
        )
