"""Configuração de fluxo Protocolo por serviço da carta Sinapse."""

from django.conf import settings
from django.db import models


class ServicoFluxoProtocolo(models.Model):
    MODO_MANUAL = "MANUAL"
    MODO_AUTOMATICO = "AUTOMATICO"
    MODOS = (
        (MODO_MANUAL, "Triagem manual no Protocolo"),
        (MODO_AUTOMATICO, "Despacho automático ao órgão do serviço"),
    )

    sinapse_servico_id = models.BigIntegerField(
        unique=True,
        help_text="ID do serviço na carta Sinapse (CatalogServico).",
    )
    modo = models.CharField(max_length=16, choices=MODOS, default=MODO_MANUAL)
    ativo = models.BooleanField(
        default=True,
        help_text="Desativado: trata como triagem manual mesmo com modo automático.",
    )
    observacoes = models.TextField(blank=True)
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fluxos_servico_alterados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Fluxo de serviço (Protocolo)"
        verbose_name_plural = "Fluxos de serviços (Protocolo)"
        ordering = ["sinapse_servico_id"]

    def __str__(self) -> str:
        return f"Serviço {self.sinapse_servico_id} → {self.get_modo_display()}"

    @property
    def despacho_automatico(self) -> bool:
        return self.ativo and self.modo == self.MODO_AUTOMATICO
