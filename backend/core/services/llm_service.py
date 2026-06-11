"""Serviço de triagem semântica de demandas via Groq (LLM).

Extrai entidades estruturadas (categoria, sentimento, urgência, bairro,
resumo técnico) a partir de título + descrição da demanda. Todas as
configurações (chave, modelo, URL, timeout, temperatura) vêm de
`settings`/`.env`.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """
Você é um arquiteto de dados especializado em triagem de demandas governamentais
(Zeladoria, Saúde, Educação, Trânsito, Iluminação, Segurança, etc.).
Analise o texto do munícipe e extraia as informações estritamente no formato
JSON abaixo. Não adicione explicações, retorne APENAS o JSON válido.

ESTRUTURA ESPERADA:
{
    "categoria_principal": "string (ex: Zeladoria, Trânsito, Saúde, Segurança, Iluminação)",
    "sentimento_municipe": "string (ex: Neutro, Frustrado, Urgente, Agradecimento)",
    "urgencia": "integer (1 a 5, onde 5 é risco de vida ou infraestrutura crítica)",
    "bairro_identificado": "string (nome do bairro se mencionado, ou nulo)",
    "resumo_tecnico": "string (resumo em 1 frase limpa e objetiva para o sistema)"
}
""".strip()


class LLMService:
    """Wrapper minimalista para o endpoint de chat completions da Groq.

    Configurado para retorno JSON estruturado (`response_format=json_object`)
    e temperatura baixa para previsibilidade da triagem.
    """

    def __init__(self) -> None:
        self.api_key: str = getattr(settings, "GROQ_API_KEY", "") or ""
        self.base_url: str = getattr(
            settings, "GROQ_BASE_URL", "https://api.groq.com/openai/v1/chat/completions"
        )
        self.model: str = getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile")
        self.timeout: int = int(getattr(settings, "GROQ_TIMEOUT", 15))
        self.temperature: float = float(getattr(settings, "GROQ_TEMPERATURE", 0.1))

    def extrair_entidades(self, titulo: str, descricao: str) -> dict[str, Any]:
        """Retorna um dict com as entidades extraídas ou {} em qualquer falha."""
        if not self.api_key:
            logger.warning("GROQ_API_KEY não configurada; triagem semântica desativada.")
            return {}

        titulo = (titulo or "").strip()
        descricao = (descricao or "").strip()
        if not titulo and not descricao:
            logger.debug("Texto vazio em extrair_entidades; nada a fazer.")
            return {}

        texto_analise = f"TÍTULO: {titulo}\nDESCRIÇÃO: {descricao}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": texto_analise},
            ],
            "response_format": {"type": "json_object"},
            "temperature": self.temperature,
        }

        try:
            response = requests.post(
                self.base_url, headers=headers, json=payload, timeout=self.timeout
            )
        except requests.Timeout:
            logger.error("Timeout (%ss) chamando Groq em %s.", self.timeout, self.base_url)
            return {}
        except requests.ConnectionError as exc:
            logger.error("Falha de conexão com Groq (%s): %s", self.base_url, exc)
            return {}

        if not response.ok:
            body = (response.text or "")[:300]
            logger.error(
                "Groq retornou HTTP %s em %s: %s",
                response.status_code,
                self.base_url,
                body,
            )
            return {}

        try:
            data = response.json()
        except ValueError as exc:
            logger.error("Groq não retornou JSON parseável: %s", exc)
            return {}

        return self._parse_content(data)

    @staticmethod
    def _parse_content(data: dict[str, Any]) -> dict[str, Any]:
        """Acesso defensivo a data['choices'][0]['message']['content'] + json.loads."""
        if not isinstance(data, dict):
            logger.error("Resposta Groq não é dict: %s", type(data).__name__)
            return {}

        if "error" in data:
            logger.error("Groq retornou erro estruturado: %s", data.get("error"))
            return {}

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            logger.error("Resposta Groq sem 'choices' válido: %s", list(data.keys()))
            return {}

        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            logger.error("Resposta Groq sem 'content' textual.")
            return {}

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.error("Conteúdo Groq não é JSON válido: %s | trecho=%s", exc, content[:200])
            return {}

        if not isinstance(parsed, dict):
            logger.error("JSON Groq não é objeto: %s", type(parsed).__name__)
            return {}
        return parsed

    def completar_texto(self, system_prompt: str, user_prompt: str) -> str:
        """Chat completion Groq retornando texto livre (sem JSON forçado)."""
        if not self.api_key:
            logger.warning("GROQ_API_KEY não configurada.")
            return ""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": (system_prompt or "").strip()},
                {"role": "user", "content": (user_prompt or "").strip()},
            ],
            "temperature": self.temperature,
        }

        for tentativa in range(3):
            try:
                response = requests.post(
                    self.base_url, headers=headers, json=payload, timeout=self.timeout
                )
            except requests.Timeout:
                logger.error("Timeout (%ss) Groq chat.", self.timeout)
                return ""
            except requests.ConnectionError as exc:
                logger.error("Falha de conexão Groq: %s", exc)
                return ""

            if response.status_code == 429 and tentativa < 2:
                import time
                time.sleep(5.0 * (tentativa + 1))
                continue

            if not response.ok:
                logger.error(
                    "Groq HTTP %s: %s",
                    response.status_code,
                    (response.text or "")[:300],
                )
                return ""
            break
        else:
            return ""

        try:
            data = response.json()
        except ValueError:
            return ""

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        return content.strip() if isinstance(content, str) else ""
