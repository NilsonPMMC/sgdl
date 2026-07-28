"""Otimização assistiva de texto para tramitações (H3-17)."""

from __future__ import annotations

import re

from core.services.ai_kernel_client import AIKernelClient, AIKernelClientError

_MINIMO_CARACTERES = 10
_MAXIMO_CARACTERES = 12000


def _strip_html(texto: str) -> str:
    return re.sub(r"<[^>]+>", " ", texto or "").replace("&nbsp;", " ").strip()


def otimizar_texto_tramitacao(texto: str, *, contexto: str = "andamento") -> str:
    limpo = _strip_html(texto)
    if len(limpo) < _MINIMO_CARACTERES:
        raise ValueError(
            f"Informe ao menos {_MINIMO_CARACTERES} caracteres para otimizar o texto."
        )
    if len(limpo) > _MAXIMO_CARACTERES:
        raise ValueError("Texto muito longo para otimização.")

    ctx = (contexto or "andamento").strip().lower()
    system_prompt = (
        "Você reescreve textos de tramitação administrativa de uma Prefeitura/Câmara Municipal. "
        "Mantenha todos os fatos, pedidos, prazos e nomes; melhore clareza, objetividade, "
        "correção gramatical e tom institucional profissional. "
        "Não invente informações. Responda APENAS com o texto final, sem markdown, "
        "sem aspas envolvendo tudo e sem prefácio."
    )
    user_prompt = (
        f"Tipo de tramitação: {ctx}.\n\n"
        f"Texto original:\n{limpo}\n\n"
        "Texto otimizado:"
    )
    client = AIKernelClient()
    try:
        resultado = client.chat(system_prompt, user_prompt)
    except AIKernelClientError as exc:
        raise ValueError(
            "Serviço de IA indisponível no momento. Revise o texto manualmente ou tente mais tarde."
        ) from exc
    out = (resultado or "").strip()
    if not out or len(out) < 5:
        raise ValueError("A IA não retornou texto utilizável. Mantenha o original.")
    return out
