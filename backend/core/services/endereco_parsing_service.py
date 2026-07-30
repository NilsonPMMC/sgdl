"""
Parsing assistivo de endereço via LLM (Fase 3).

Extrai logradouro/bairro/CEP do relato — NUNCA coordenadas.
Resultado validado por regex/heurísticas existentes do Copiloto.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import requests
from django.conf import settings

from core.services.endereco_normalizacao import normalizar_bairro, normalizar_logradouro

logger = logging.getLogger(__name__)

_ENDERECO_LLM_SYSTEM = """
Você extrai endereços de pedidos de cidadãos em Mogi das Cruzes (SP).

REGRAS:
1. Retorne APENAS JSON válido.
2. Extraia somente campos estruturados do texto — NÃO invente coordenadas.
3. logradouro: via pública ou nome de parque/área pública (ex.: Parque Centenário).
4. bairro: bairro do município quando mencionado.
5. cep: formato 99999-999 se explícito no texto.
6. numero: número da via quando explícito.
7. referencia: ponto de referência textual (padaria, escola) — opcional, não geocodificar.
8. Se não houver endereço, retorne campos null.

FORMATO:
{"logradouro": null, "bairro": null, "cep": null, "numero": null, "referencia": null}
""".strip()


class EnderecoParsingService:
    def __init__(self) -> None:
        self.enabled = bool(getattr(settings, "GEOCODING_LLM_PARSING_ENABLED", True))
        self.api_key = getattr(settings, "GROQ_API_KEY", "") or ""
        self.base_url = getattr(
            settings,
            "GROQ_BASE_URL",
            "https://api.groq.com/openai/v1/chat/completions",
        )
        self.model = getattr(
            settings,
            "GROQ_MODEL",
            "llama-3.3-70b-versatile",
        )
        self.timeout = int(getattr(settings, "GROQ_TIMEOUT", 15))
        self.temperature = float(getattr(settings, "GROQ_TEMPERATURE", 0.0))

    @staticmethod
    def _endereco_incompleto(ext: dict[str, Any]) -> bool:
        logr = (ext.get("logradouro") or "").strip()
        bairro = (ext.get("bairro") or "").strip()
        cep = re.sub(r"\D", "", (ext.get("cep") or ""))
        if logr and bairro:
            return False
        if len(cep) == 8 and logr:
            return False
        if logr or bairro or len(cep) == 8:
            return True
        return True

    def enriquecer_com_llm(
        self, base: dict[str, Any], texto: str
    ) -> dict[str, Any]:
        """Completa campos faltantes com LLM quando regex não bastou."""
        if not self.enabled or not self.api_key:
            return base
        if not self._endereco_incompleto(base):
            return base
        t = (texto or "").strip()
        if len(t) < 12:
            return base

        llm = self._extrair_llm(t)
        if not llm:
            return base
        return self._merge_endereco(base, llm)

    def _extrair_llm(self, texto: str) -> dict[str, Any] | None:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _ENDERECO_LLM_SYSTEM},
                {
                    "role": "user",
                    "content": f"Texto do cidadão:\n{texto[:4000]}",
                },
            ],
            "response_format": {"type": "json_object"},
            "temperature": self.temperature,
        }
        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            logger.warning("Endereco LLM parsing indisponível: %s", exc)
            return None

        if response.status_code == 429:
            time.sleep(2.0)
            try:
                response = requests.post(
                    self.base_url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
            except requests.RequestException:
                return None

        if not response.ok:
            logger.warning(
                "Endereco LLM HTTP %s: %s",
                response.status_code,
                (response.text or "")[:200],
            )
            return None

        try:
            data = response.json()
            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "{}")
            )
            parsed = json.loads(content)
        except (ValueError, IndexError, TypeError, json.JSONDecodeError):
            return None
        if not isinstance(parsed, dict):
            return None
        return self._sanitizar_llm(parsed)

    def _sanitizar_llm(self, raw: dict[str, Any]) -> dict[str, Any]:
        from core.services.chatbot_service import ChatbotService

        out: dict[str, Any] = {}
        for chave in ("logradouro", "bairro", "numero", "referencia"):
            val = raw.get(chave)
            if val in (None, "", []):
                continue
            v = str(val).strip()
            if chave in ("logradouro", "bairro", "numero") and not ChatbotService._valor_campo_endereco_valido(
                chave, v
            ):
                continue
            if chave == "logradouro":
                out[chave] = normalizar_logradouro(v)[:240]
            elif chave == "bairro":
                out[chave] = normalizar_bairro(v)[:120]
            else:
                out[chave] = v[:120]
        cep_raw = raw.get("cep")
        if cep_raw:
            m = re.search(r"\d{5}-?\d{3}", str(cep_raw))
            if m:
                digits = re.sub(r"\D", "", m.group(0))
                if len(digits) == 8:
                    out["cep"] = f"{digits[:5]}-{digits[5:]}"
        return out

    @staticmethod
    def _merge_endereco(base: dict[str, Any], llm: dict[str, Any]) -> dict[str, Any]:
        merged = dict(base)
        for chave in ("cep", "logradouro", "numero", "bairro", "complemento"):
            if (merged.get(chave) or "").strip():
                continue
            val = llm.get(chave)
            if val not in (None, "", []):
                merged[chave] = val
        ref = (llm.get("referencia") or "").strip()
        if ref and not (merged.get("complemento") or "").strip():
            merged["complemento"] = ref[:120]
        return merged
