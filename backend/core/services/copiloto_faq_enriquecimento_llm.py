"""
Gera sugestões de FAQ do Copiloto via Groq (contexto Mogi das Cruzes) e grava no banco.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

import requests
from django.conf import settings
from django.utils import timezone

from core.models_config import ConfiguracaoOficio
from core.models_copiloto_faq import CopilotoFaqOrientacao, validar_expressao_regex
from core.services.copiloto_faq_service import (
    aplicar_sugestao_llm,
    carregar_catalogo_faq,
    listar_categorias_para_prompt,
)

logger = logging.getLogger(__name__)

FAQ_ENRIQUECIMENTO_SYSTEM_PROMPT = """
Você é especialista em competências administrativas do município de Mogi das Cruzes (SP)
e no fluxo do Gabinete Legislativo (ofícios à Prefeitura).

Sua tarefa é ENRIQUECER a base de FAQ usada quando o cidadão pede algo que **NÃO** deve virar
ofício municipal (assuntos de concessionárias, consumidor, órgãos estaduais/federais, etc.).

REGRAS:
1. NÃO inclua serviços que a Prefeitura / zeladoria municipal atende (buraco, iluminação pública
   em via, limpeza, poda em área pública, parques municipais, fiscalização de obras municipal).
2. Foque em confusões comuns em Mogi das Cruzes e região: energia (CPFL Piratininga), água (SABESP),
   telefonia, Procon, DETRAN, Receita Federal, INSS, Justiça, hospitais estaduais, rodovias, etc.
3. `categoria_orientacao`: código em MAIÚSCULAS_SNAKE_CASE, único, estável (ex.: ENERGIA_CONCESSIONARIA).
4. `padroes_regex`: lista de expressões regulares Python (sem delimitadores /.../); serão usadas com
   re.IGNORECASE. Use \\b para palavras inteiras. Máximo 8 padrões por entrada.
5. `mensagem`: texto claro ao cidadão (2–4 frases), sem prometer prazo.
6. `orgao_hint`: para onde encaminhar (nome realista da região quando souber).
7. Se a categoria já existir no catálogo anexo, coloque em `atualizacoes` (novos padrões ou textos
   revisados). Categorias inéditas vão em `novas_entradas`.
8. Retorne APENAS JSON válido no formato abaixo.

FORMATO:
{
  "observacoes": "string curta sobre lacunas encontradas",
  "novas_entradas": [
    {
      "categoria_orientacao": "CODIGO",
      "titulo": "string",
      "mensagem": "string",
      "orgao_hint": "string",
      "padroes_regex": ["regex1", "regex2"],
      "ordem": 50,
      "ativo": true
    }
  ],
  "atualizacoes": [
    {
      "categoria_orientacao": "CODIGO_EXISTENTE",
      "titulo": null,
      "mensagem": null,
      "orgao_hint": null,
      "padroes_regex_novos": ["regex"],
      "notas_internas": "motivo da atualização"
    }
  ]
}
""".strip()


@dataclass
class ResultadoEnriquecimentoFaq:
    municipio: str
    observacoes: str = ""
    novas_aplicadas: int = 0
    atualizacoes_aplicadas: int = 0
    ignoradas: list[str] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)
    dry_run: bool = False
    sugestoes_brutas: dict[str, Any] = field(default_factory=dict)


class CopilotoFaqEnriquecimentoLlmService:
    def __init__(self) -> None:
        self.api_key: str = getattr(settings, "GROQ_API_KEY", "") or ""
        self.base_url: str = getattr(
            settings,
            "GROQ_BASE_URL",
            "https://api.groq.com/openai/v1/chat/completions",
        )
        self.model: str = getattr(
            settings,
            "GROQ_CHAT_MODEL",
            getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile"),
        )
        self.timeout: int = int(
            getattr(settings, "COPILOTO_FAQ_LLM_TIMEOUT", 90)
        )
        self.temperature: float = float(
            getattr(settings, "COPILOTO_FAQ_LLM_TEMPERATURE", 0.25)
        )

    def executar(
        self,
        *,
        municipio: str | None = None,
        max_novas: int = 5,
        dry_run: bool = False,
        usuario=None,
        foco: str | None = None,
    ) -> ResultadoEnriquecimentoFaq:
        cfg = ConfiguracaoOficio.carregar()
        municipio_ref = (municipio or cfg.municipio or "Mogi das Cruzes").strip()
        resultado = ResultadoEnriquecimentoFaq(municipio=municipio_ref, dry_run=dry_run)

        if not self.api_key:
            resultado.erros.append("GROQ_API_KEY não configurada.")
            return resultado

        user_prompt = self._montar_prompt_usuario(
            municipio_ref=municipio_ref,
            uf=cfg.uf or "SP",
            max_novas=max_novas,
            foco=foco,
        )
        parsed = self._chamar_groq(user_prompt)
        if not parsed:
            resultado.erros.append("Resposta vazia ou inválida do Groq.")
            return resultado

        resultado.sugestoes_brutas = parsed
        resultado.observacoes = str(parsed.get("observacoes") or "").strip()

        if dry_run:
            return resultado

        novas = parsed.get("novas_entradas")
        if isinstance(novas, list):
            for i, item in enumerate(novas[:max_novas]):
                ok, msg = self._aplicar_entrada(item, municipio_ref, usuario, substituir=False)
                if ok:
                    resultado.novas_aplicadas += 1
                elif msg:
                    resultado.ignoradas.append(f"nova[{i}]: {msg}")

        atualizacoes = parsed.get("atualizacoes")
        if isinstance(atualizacoes, list):
            for i, item in enumerate(atualizacoes):
                ok, msg = self._aplicar_atualizacao(item, municipio_ref, usuario)
                if ok:
                    resultado.atualizacoes_aplicadas += 1
                elif msg:
                    resultado.ignoradas.append(f"atualizacao[{i}]: {msg}")

        return resultado

    def _montar_prompt_usuario(
        self,
        *,
        municipio_ref: str,
        uf: str,
        max_novas: int,
        foco: str | None,
    ) -> str:
        catalogo = listar_categorias_para_prompt()
        linhas_cat = [
            f"- {c['categoria_orientacao']}: {c['titulo']} | {c['orgao_hint']}"
            for c in catalogo
        ]
        padroes_existentes: list[str] = []
        for reg in carregar_catalogo_faq(municipio=municipio_ref):
            padroes_existentes.append(
                f"  [{reg.categoria_orientacao}] slug={reg.id} | {reg.titulo}"
            )

        bloco_foco = ""
        if foco:
            bloco_foco = f"\nFOCO DESTA EXECUÇÃO: {foco.strip()}\n"

        return f"""
Município de referência: {municipio_ref}, {uf}.
Instituição: {ConfiguracaoOficio.carregar().instituicao_nome}.
Destinatário típico dos ofícios: Prefeitura Municipal de {municipio_ref}.

Proponha até {max_novas} entradas NOVAS em `novas_entradas` (lacunas reais fora da competência municipal).
Pode sugerir `atualizacoes` com padrões regex adicionais para categorias já cadastradas.
{bloco_foco}

CATEGORIAS JÁ CADASTRADAS (não duplique código; use `atualizacoes` se quiser melhorar):
{chr(10).join(linhas_cat) if linhas_cat else "(nenhuma — proponha o conjunto inicial)"}

ENTRADAS ATIVAS NO BANCO:
{chr(10).join(padroes_existentes) if padroes_existentes else "(vazio)"}

Contexto regional: Grande ABC paulista; concessionária de energia usual CPFL Piratininga;
saneamento SABESP; demandas estaduais (DETRAN, DER, Polícia) e federais não são ofício de zeladoria municipal.
""".strip()

    def _chamar_groq(self, user_content: str) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": FAQ_ENRIQUECIMENTO_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
            "temperature": self.temperature,
        }
        for tentativa in range(2):
            try:
                response = requests.post(
                    self.base_url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
            except requests.Timeout:
                logger.error("Timeout (%ss) Groq FAQ enriquecimento.", self.timeout)
                return {}
            except requests.ConnectionError as exc:
                logger.error("Conexão Groq FAQ: %s", exc)
                return {}

            if response.status_code == 429 and tentativa == 0:
                time.sleep(12.0)
                continue

            if not response.ok:
                logger.error(
                    "Groq FAQ HTTP %s: %s",
                    response.status_code,
                    (response.text or "")[:400],
                )
                return {}

            try:
                data = response.json()
            except ValueError:
                return {}

            return self._parse_content(data)
        return {}

    @staticmethod
    def _parse_content(data: dict[str, Any]) -> dict[str, Any]:
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            return {}
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            return {}
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.error("FAQ LLM JSON inválido: %s", exc)
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _normalizar_padroes(self, raw: Any, *, limite: int = 8) -> list[str]:
        if not isinstance(raw, list):
            return []
        out: list[str] = []
        for item in raw[:limite]:
            expr = str(item).strip()
            if not expr:
                continue
            try:
                validar_expressao_regex(expr)
                out.append(expr)
            except Exception as exc:
                logger.warning("Regex ignorada %r: %s", expr[:60], exc)
        return out

    def _aplicar_entrada(
        self,
        item: Any,
        municipio_ref: str,
        usuario,
        *,
        substituir: bool,
    ) -> tuple[bool, str | None]:
        if not isinstance(item, dict):
            return False, "item não é objeto"
        cat = str(item.get("categoria_orientacao") or "").strip().upper().replace(" ", "_")
        if not cat or not re.fullmatch(r"[A-Z0-9_]{3,64}", cat):
            return False, f"categoria inválida: {cat!r}"

        padroes = self._normalizar_padroes(item.get("padroes_regex"))
        if not padroes:
            return False, "sem padrões regex válidos"

        notas = (item.get("notas_internas") or "").strip()
        notas_llm = f"Enriquecimento Groq {timezone.now().isoformat(timespec='seconds')}"
        if notas:
            notas_llm = f"{notas_llm} — {notas}"

        try:
            aplicar_sugestao_llm(
                {
                    "categoria_orientacao": cat,
                    "titulo": item.get("titulo"),
                    "mensagem": item.get("mensagem"),
                    "orgao_hint": item.get("orgao_hint"),
                    "padroes_regex": padroes,
                    "municipio_referencia": municipio_ref,
                    "ordem": item.get("ordem"),
                    "ativo": item.get("ativo", True),
                    "notas_internas": notas_llm,
                    "substituir_padroes": substituir,
                },
                usuario=usuario,
            )
            return True, None
        except ValueError as exc:
            return False, str(exc)

    def _aplicar_atualizacao(
        self,
        item: Any,
        municipio_ref: str,
        usuario,
    ) -> tuple[bool, str | None]:
        if not isinstance(item, dict):
            return False, "item não é objeto"
        cat = str(item.get("categoria_orientacao") or "").strip().upper().replace(" ", "_")
        if not CopilotoFaqOrientacao.objects.filter(
            categoria_orientacao=cat, ativo=True
        ).exists():
            return False, f"categoria {cat} não existe"

        padroes_novos = self._normalizar_padroes(item.get("padroes_regex_novos"))
        payload: dict[str, Any] = {
            "categoria_orientacao": cat,
            "municipio_referencia": municipio_ref,
            "substituir_padroes": False,
            "notas_internas": (
                item.get("notas_internas")
                or f"Atualização Groq {timezone.now().isoformat(timespec='seconds')}"
            ),
        }
        faq = CopilotoFaqOrientacao.objects.filter(categoria_orientacao=cat).first()
        if not faq:
            return False, "FAQ não encontrada"

        if item.get("titulo"):
            payload["titulo"] = item["titulo"]
        else:
            payload["titulo"] = faq.titulo
        if item.get("mensagem"):
            payload["mensagem"] = item["mensagem"]
        else:
            payload["mensagem"] = faq.mensagem
        if item.get("orgao_hint"):
            payload["orgao_hint"] = item["orgao_hint"]
        else:
            payload["orgao_hint"] = faq.orgao_hint

        if not padroes_novos:
            return False, "sem padroes_regex_novos"

        payload["padroes_regex"] = padroes_novos

        try:
            aplicar_sugestao_llm(payload, usuario=usuario)
            return True, None
        except ValueError as exc:
            return False, str(exc)
