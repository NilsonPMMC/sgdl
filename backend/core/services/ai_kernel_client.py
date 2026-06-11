import logging
import time
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class AIKernelClientError(Exception):
    """Erro de comunicação com o Kernel AI."""


class AIKernelClient:
    def __init__(self):
        self.base_url = getattr(settings, "AI_KERNEL_BASE_URL", "http://localhost:8004").rstrip("/")
        self.timeout_embeddings = int(getattr(settings, "AI_KERNEL_TIMEOUT_EMBEDDINGS", 10))
        self.timeout_similarity = int(getattr(settings, "AI_KERNEL_TIMEOUT_SIMILARITY", 10))
        self.timeout_chat = int(getattr(settings, "AI_KERNEL_TIMEOUT_CHAT", 30))
        self.max_retries = int(getattr(settings, "AI_KERNEL_MAX_RETRIES", 2))
        self.retry_backoff_seconds = float(getattr(settings, "AI_KERNEL_RETRY_BACKOFF_SECONDS", 0.5))

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/", timeout=5)

    def embeddings(self, texts: list[str]) -> list[list[float]]:
        payload = {"texts": texts}
        response = self._request("POST", "/v1/embeddings", payload=payload, timeout=self.timeout_embeddings)
        return response.get("embeddings", [])

    def embeddings_safe(self, texts: list[str]) -> list[list[float]]:
        try:
            return self.embeddings(texts)
        except AIKernelClientError:
            logger.exception("Fallback embeddings_safe acionado.")
            return []

    def similarity(self, target_text: str, candidates: list[str]) -> list[dict[str, Any]]:
        payload = {"target_text": target_text, "candidates": candidates}
        response = self._request("POST", "/v1/similarity", payload=payload, timeout=self.timeout_similarity)
        return response.get("results", [])

    def similarity_safe(self, target_text: str, candidates: list[str]) -> list[dict[str, Any]]:
        try:
            return self.similarity(target_text, candidates)
        except AIKernelClientError:
            logger.exception("Fallback similarity_safe acionado.")
            return []

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        payload = {"system_prompt": system_prompt, "user_prompt": user_prompt}
        response = self._request("POST", "/v1/chat", payload=payload, timeout=self.timeout_chat, expect_json=False)
        if isinstance(response, str):
            return response
        return str(response)

    def chat_safe(self, system_prompt: str, user_prompt: str) -> str:
        try:
            return self.chat(system_prompt, user_prompt)
        except AIKernelClientError:
            logger.exception("Fallback chat_safe acionado.")
            return ""

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        timeout: int = 10,
        expect_json: bool = True,
    ) -> Any:
        url = f"{self.base_url}{path}"
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            started_at = time.monotonic()
            try:
                if method == "GET":
                    response = requests.get(url, timeout=timeout)
                else:
                    response = requests.post(url, json=payload, timeout=timeout)
                elapsed_ms = round((time.monotonic() - started_at) * 1000, 2)

                if response.status_code >= 500:
                    raise AIKernelClientError(
                        f"Kernel retornou {response.status_code} em {path}: {response.text[:200]}"
                    )
                if response.status_code >= 400:
                    raise AIKernelClientError(
                        f"Kernel retornou {response.status_code} em {path}: {response.text[:200]}"
                    )

                logger.info("Kernel request %s %s ok em %sms", method, path, elapsed_ms)
                return response.json() if expect_json else response.text
            except (requests.Timeout, requests.ConnectionError, AIKernelClientError, ValueError) as exc:
                elapsed_ms = round((time.monotonic() - started_at) * 1000, 2)
                last_error = exc
                should_retry = attempt < self.max_retries
                logger.warning(
                    "Kernel request falhou (%s %s), tentativa %s/%s, retry=%s, tempo=%sms, erro=%s",
                    method,
                    path,
                    attempt + 1,
                    self.max_retries + 1,
                    should_retry,
                    elapsed_ms,
                    exc,
                )
                if should_retry:
                    time.sleep(self.retry_backoff_seconds * (attempt + 1))
                else:
                    break

        raise AIKernelClientError(f"Falha ao chamar Kernel em {path}: {last_error}")
