"""Encerramento legislativo — ciência do vereador e resposta ao cidadão (Fase 6)."""

from django.conf import settings
from django.db import models


class EncerramentoLegislativo(models.Model):
    demanda = models.OneToOneField(
        "Demanda",
        on_delete=models.CASCADE,
        related_name="encerramento_legislativo",
    )
    texto_resposta_cidadao = models.TextField(
        blank=True,
        help_text="Texto da resposta formal ao cidadão (ofício de devolutiva).",
    )
    ciencia_em = models.DateTimeField(null=True, blank=True)
    ciencia_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ciencias_devolutiva",
    )
    encerrado_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Encerramento legislativo"
        verbose_name_plural = "Encerramentos legislativos"

    def __str__(self) -> str:
        return f"Encerramento demanda {self.demanda_id}"
