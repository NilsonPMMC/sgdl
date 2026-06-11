"""Unidades administrativas (setores) vinculadas a órgãos Sinapse."""

from django.conf import settings
from django.db import models


class UnidadeAdministrativa(models.Model):
    sinapse_orgao_id = models.BigIntegerField(
        help_text="Órgão (secretaria) no catálogo Sinapse.",
        db_index=True,
    )
    nome = models.CharField(max_length=200)
    sigla = models.CharField(max_length=32, blank=True)
    email_contato = models.EmailField(
        blank=True,
        help_text="E-mail de contato da unidade (importação RM271698).",
    )
    cod_rm_orgao = models.CharField(
        max_length=20,
        blank=True,
        db_index=True,
        help_text="Código RM da secretaria (2.º segmento da sigla).",
    )
    ativo = models.BooleanField(default=True)
    sinapse_unidade_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Referência opcional à unidade no barramento Sinapse.",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Unidade administrativa (setor)"
        verbose_name_plural = "Unidades administrativas (setores)"
        ordering = ["sinapse_orgao_id", "nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["sinapse_orgao_id", "sigla"],
                condition=models.Q(sigla__gt=""),
                name="core_unidade_orgao_sigla_unica",
            ),
            models.UniqueConstraint(
                fields=["sinapse_unidade_id"],
                condition=models.Q(sinapse_unidade_id__isnull=False),
                name="core_unidade_sinapse_unidade_id_unica",
            ),
        ]

    def __str__(self) -> str:
        rotulo = self.sigla or self.nome
        return f"{rotulo} (órgão {self.sinapse_orgao_id})"


class UnidadeAdministrativaResponsavel(models.Model):
    unidade = models.ForeignKey(
        UnidadeAdministrativa,
        on_delete=models.CASCADE,
        related_name="responsaveis",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="unidades_responsaveis",
    )
    pode_tramitar = models.BooleanField(
        default=True,
        help_text="Permite encaminhar demandas entre setores.",
    )
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Responsável por setor"
        verbose_name_plural = "Responsáveis por setor"
        ordering = ["unidade_id", "usuario_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["unidade", "usuario"],
                name="core_unidade_usuario_unico",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.usuario} → {self.unidade}"
