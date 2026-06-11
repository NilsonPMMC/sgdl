"""Assuntos temáticos da carta e política de utilização no SGDL (C5)."""

from django.db import models


class ModoUtilizacaoSgdl(models.TextChoices):
    PROTOCOLAVEL = "PROTOCOLAVEL", "Protocolável"
    INFORMATIVO = "INFORMATIVO", "Somente orientação"
    PROTOCOLAVEL_CONDICIONAL = "PROTOCOLAVEL_CONDICIONAL", "Protocolável com condição"


class AssuntoCarta(models.Model):
    nome = models.CharField(max_length=120)
    slug = models.SlugField(max_length=80, unique=True)
    ordem = models.PositiveSmallIntegerField(default=0)
    modo_utilizacao_sgdl = models.CharField(
        max_length=32,
        choices=ModoUtilizacaoSgdl.choices,
        default=ModoUtilizacaoSgdl.PROTOCOLAVEL,
    )
    mensagem_orientacao = models.TextField(
        blank=True,
        help_text="Texto exibido no Copiloto quando o modo efetivo for informativo.",
    )
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Assunto temático (carta)"
        verbose_name_plural = "Assuntos temáticos (carta)"
        ordering = ["ordem", "nome"]

    def __str__(self) -> str:
        return self.nome
