"""Vínculo opt-in de acompanhamento gerencial (fixar processo)."""

from django.conf import settings
from django.db import models
from django.utils import timezone


class DemandaAcompanhamento(models.Model):
    ORIGEM_ENCERRAMENTO = "ENCERRAMENTO"
    ORIGEM_MANUAL = "MANUAL"
    ORIGEM_CHOICES = (
        (ORIGEM_ENCERRAMENTO, "Após encerramento de nó"),
        (ORIGEM_MANUAL, "Fixação manual"),
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="acompanhamentos_demanda",
    )
    demanda = models.ForeignKey(
        "Demanda",
        on_delete=models.CASCADE,
        related_name="acompanhamentos",
    )
    no_operacional = models.ForeignKey(
        "NoOperacional",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acompanhamentos_origem",
    )
    origem = models.CharField(max_length=16, choices=ORIGEM_CHOICES, default=ORIGEM_MANUAL)
    ativo = models.BooleanField(default=True, db_index=True)
    criado_em = models.DateTimeField(default=timezone.now)
    encerrado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-criado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "demanda"],
                name="uniq_demanda_acompanhamento_usuario_demanda",
            )
        ]

    def __str__(self) -> str:
        return f"Acompanhamento u={self.usuario_id} d={self.demanda_id} ativo={self.ativo}"
