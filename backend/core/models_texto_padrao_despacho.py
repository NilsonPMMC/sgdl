"""Modelos de texto padrão para despachos e tramitações operacionais."""

from django.conf import settings
from django.db import models


class CategoriaTextoPadraoDespacho(models.TextChoices):
    """Duas famílias de uso — alinhadas ao fluxo institucional."""

    PROTOCOLO = "PROTOCOLO", "Protocolo (despacho inicial e final)"
    OPERACIONAL = "OPERACIONAL", "Operacional (secretaria / setores)"


class EscopoTextoPadraoDespacho(models.TextChoices):
    PROTOCOLO = "PROTOCOLO", "Protocolo"
    SECRETARIA = "SECRETARIA", "Secretaria"
    SETORIAL = "SETORIAL", "Setorial"
    GERAL = "GERAL", "Geral"


class TextoPadraoDespacho(models.Model):
    titulo = models.CharField(max_length=160)
    categoria = models.CharField(
        max_length=32,
        choices=CategoriaTextoPadraoDespacho.choices,
        default=CategoriaTextoPadraoDespacho.OPERACIONAL,
    )
    corpo = models.TextField(help_text="HTML formatado (Quill/Editor).")
    escopo_tipo = models.CharField(
        max_length=16,
        choices=EscopoTextoPadraoDespacho.choices,
        default=EscopoTextoPadraoDespacho.GERAL,
    )
    sinapse_orgao_id = models.PositiveIntegerField(null=True, blank=True)
    unidades = models.ManyToManyField(
        "core.UnidadeAdministrativa",
        blank=True,
        related_name="textos_padrao_despacho",
        help_text="Setores em que o modelo fica disponível. Vazio = todo o órgão/escopo.",
    )
    unidade_administrativa = models.ForeignKey(
        "core.UnidadeAdministrativa",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="textos_padrao_despacho_legado",
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="textos_padrao_despacho_criados",
    )
    ordem = models.PositiveSmallIntegerField(default=0)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Texto padrão de despacho"
        verbose_name_plural = "Textos padrão de despacho"
        ordering = ["ordem", "titulo"]
        indexes = [
            models.Index(fields=["categoria", "ativo", "escopo_tipo"]),
            models.Index(fields=["sinapse_orgao_id", "ativo"]),
        ]

    def __str__(self) -> str:
        return self.titulo
