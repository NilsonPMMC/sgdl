"""De-para COD_RM (planilha RM271698) ↔ órgão Sinapse."""

from django.db import models


class DeParaRmSinapse(models.Model):
    cod_rm = models.CharField(
        max_length=20,
        unique=True,
        help_text="Código da secretaria no 2.º segmento da sigla RM (ex.: SMSBE).",
    )
    sinapse_orgao_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="ID do órgão no catálogo Sinapse. Vazio = pendente de mapeamento.",
        db_index=True,
    )
    observacao = models.CharField(max_length=255, blank=True)
    ativo = models.BooleanField(
        default=True,
        help_text="Se falso, unidades com este COD_RM não são importadas.",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "De-para RM → Sinapse"
        verbose_name_plural = "De-para RM → Sinapse"
        ordering = ["cod_rm"]

    def __str__(self) -> str:
        return f"{self.cod_rm} → {self.sinapse_orgao_id or 'pendente'}"
