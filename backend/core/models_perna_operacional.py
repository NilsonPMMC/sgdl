"""Pernas operacionais — roteamento órgão × setor na demanda única (P3)."""

from __future__ import annotations

from django.db import models


class StatusPernaOperacional:
    PENDENTE = "PENDENTE"
    EM_EXECUCAO = "EM_EXECUCAO"
    CONCLUIDA = "CONCLUIDA"
    CANCELADA = "CANCELADA"

    CHOICES = (
        (PENDENTE, "Pendente"),
        (EM_EXECUCAO, "Em execução"),
        (CONCLUIDA, "Concluída"),
        (CANCELADA, "Cancelada"),
    )

    # Pernas com participação operacional em aberto (exclui CONCLUIDA/CANCELADA).
    ATIVOS = frozenset({PENDENTE, EM_EXECUCAO})


class PernaOperacional(models.Model):
    """Linha de execução transversal (órgão + setor) vinculada a uma única Demanda."""

    demanda = models.ForeignKey(
        "Demanda",
        on_delete=models.CASCADE,
        related_name="pernas_operacionais",
    )
    sinapse_orgao_id = models.BigIntegerField(
        help_text="Órgão/secretaria responsável por esta perna.",
    )
    unidade_administrativa = models.ForeignKey(
        "UnidadeAdministrativa",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pernas_operacionais",
    )
    status = models.CharField(
        max_length=16,
        choices=StatusPernaOperacional.CHOICES,
        default=StatusPernaOperacional.PENDENTE,
    )
    ordem = models.PositiveSmallIntegerField(default=1)
    despacho_tramitacao = models.ForeignKey(
        "Tramitacao",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pernas_abertas",
    )
    conclusao_tramitacao = models.ForeignKey(
        "Tramitacao",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="perna_concluida",
    )
    metadata = models.JSONField(default=dict, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ordem", "pk"]
        indexes = [
            models.Index(fields=["demanda", "status"]),
            models.Index(fields=["sinapse_orgao_id", "status"]),
        ]

    def __str__(self) -> str:
        return f"Perna #{self.pk} demanda={self.demanda_id} orgao={self.sinapse_orgao_id}"
