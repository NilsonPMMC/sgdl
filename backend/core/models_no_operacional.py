"""Nós operacionais — scatter-gather (coreografia livre na etapa EM_OPERACAO)."""

from __future__ import annotations

from django.conf import settings
from django.db import models


class StatusNoOperacional:
    ABERTO = "ABERTO"
    CONCLUIDO = "CONCLUIDO"
    CANCELADO = "CANCELADO"

    CHOICES = (
        (ABERTO, "Aberto"),
        (CONCLUIDO, "Concluído"),
        (CANCELADO, "Cancelado"),
    )

    ABERTOS = frozenset({ABERTO})


class AcaoNoOperacional:
    DESPACHAR = "DESPACHAR"
    DESPACHAR_ENCERRAR = "DESPACHAR_ENCERRAR"
    ENCERRAR = "ENCERRAR"

    CHOICES = (
        (DESPACHAR, "Despachar (nó permanece aberto)"),
        (DESPACHAR_ENCERRAR, "Despachar e encerrar participação"),
        (ENCERRAR, "Encerrar participação"),
    )


class NoOperacional(models.Model):
    """
    Participação de um setor/secretaria no grafo de tramitação livre.
    Cada nó aberto conta para ``Demanda.nos_ativos`` até ser encerrado.
    """

    demanda = models.ForeignKey(
        "Demanda",
        on_delete=models.CASCADE,
        related_name="nos_operacionais",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="filhos",
    )
    perna_operacional = models.ForeignKey(
        "PernaOperacional",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="nos_operacionais",
    )
    sinapse_orgao_id = models.BigIntegerField()
    unidade_administrativa = models.ForeignKey(
        "UnidadeAdministrativa",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="nos_operacionais",
    )
    status = models.CharField(
        max_length=16,
        choices=StatusNoOperacional.CHOICES,
        default=StatusNoOperacional.ABERTO,
    )
    responsavel_abertura = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="nos_operacionais_abertos",
    )
    abertura_tramitacao = models.ForeignKey(
        "Tramitacao",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="nos_abertos",
    )
    encerramento_tramitacao = models.ForeignKey(
        "Tramitacao",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="nos_encerrados",
    )
    metadata = models.JSONField(default=dict, blank=True)
    aberto_em = models.DateTimeField(auto_now_add=True)
    concluido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["aberto_em", "pk"]
        indexes = [
            models.Index(fields=["demanda", "status"]),
            models.Index(fields=["parent", "status"]),
            models.Index(fields=["sinapse_orgao_id", "status"]),
        ]

    def __str__(self) -> str:
        return f"No #{self.pk} demanda={self.demanda_id} orgao={self.sinapse_orgao_id} [{self.status}]"
