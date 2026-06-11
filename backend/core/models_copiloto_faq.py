"""Base de conhecimento FAQ do Copiloto — orientações fora da competência municipal."""

from __future__ import annotations

import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


def validar_expressao_regex(expressao: str) -> None:
    expr = (expressao or "").strip()
    if not expr:
        raise ValidationError("Informe uma expressão regular não vazia.")
    if len(expr) > 500:
        raise ValidationError("Expressão muito longa (máx. 500 caracteres).")
    try:
        re.compile(expr, re.IGNORECASE)
    except re.error as exc:
        raise ValidationError(f"Regex inválida: {exc}") from exc


class CopilotoFaqOrientacao(models.Model):
    """Tema de orientação exibido quando o pedido não compete ao gabinete / Prefeitura."""

    FONTE_MANUAL = "MANUAL"
    FONTE_LLM = "LLM"
    FONTE_MIGRACAO = "MIGRACAO"
    FONTE_CHOICES = (
        (FONTE_MANUAL, "Cadastro manual (Admin)"),
        (FONTE_LLM, "Sugestão / enriquecimento por IA"),
        (FONTE_MIGRACAO, "Migração ou seed inicial"),
    )

    slug = models.SlugField(
        max_length=80,
        unique=True,
        help_text="Identificador estável (ex.: energia-mogi).",
    )
    categoria_orientacao = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="Código usado pelo LLM em categoria_orientacao (ex.: ENERGIA_CONCESSIONARIA).",
    )
    titulo = models.CharField(max_length=200)
    mensagem = models.TextField(
        help_text="Texto exibido ao cidadão na recusa do Copiloto.",
    )
    orgao_hint = models.CharField(
        max_length=255,
        help_text="Para onde encaminhar (ex.: CPFL, SABESP, Procon).",
    )
    municipio_referencia = models.CharField(
        max_length=120,
        default="Mogi das Cruzes",
        help_text="Contexto local usado pela automação de IA ao enriquecer entradas.",
    )
    ativo = models.BooleanField(
        default=True,
        help_text="Somente entradas ativas entram na detecção do Copiloto.",
    )
    ordem = models.PositiveSmallIntegerField(
        default=100,
        help_text="Menor = maior prioridade na detecção por regex.",
    )
    fonte = models.CharField(
        max_length=16,
        choices=FONTE_CHOICES,
        default=FONTE_MANUAL,
    )
    notas_internas = models.TextField(
        blank=True,
        help_text="Notas para Protocolo / curadoria (não exibidas ao cidadão).",
    )
    ultima_sincronizacao_llm = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Última vez que a automação de IA alterou este registro.",
    )
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="faq_copiloto_revisadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ordem", "titulo"]
        verbose_name = "FAQ Copiloto (orientação)"
        verbose_name_plural = "FAQ Copiloto — base de conhecimento"
        indexes = [
            models.Index(fields=["ativo", "ordem"]),
            models.Index(fields=["municipio_referencia", "ativo"]),
        ]

    def __str__(self) -> str:
        return f"{self.titulo} ({self.categoria_orientacao})"


class CopilotoFaqPadraoRegex(models.Model):
    """Gatilho textual (regex) que associa o relato do cidadão a uma orientação FAQ."""

    faq = models.ForeignKey(
        CopilotoFaqOrientacao,
        on_delete=models.CASCADE,
        related_name="padroes",
    )
    expressao = models.CharField(
        max_length=500,
        help_text="Expressão regular (Python), flag IGNORECASE aplicada automaticamente.",
    )
    ativo = models.BooleanField(default=True)
    ordem = models.PositiveSmallIntegerField(default=100)
    fonte = models.CharField(
        max_length=16,
        choices=CopilotoFaqOrientacao.FONTE_CHOICES,
        default=CopilotoFaqOrientacao.FONTE_MANUAL,
    )
    notas = models.CharField(max_length=255, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["ordem", "id"]
        verbose_name = "Padrão regex (FAQ)"
        verbose_name_plural = "Padrões regex (FAQ)"

    def __str__(self) -> str:
        return (self.expressao or "")[:60]

    def clean(self):
        super().clean()
        validar_expressao_regex(self.expressao)
