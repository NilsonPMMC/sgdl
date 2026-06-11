"""Registro de assinatura eletrônica nativa (envio oficial do ofício)."""

from django.conf import settings
from django.db import models


class AssinaturaEletronica(models.Model):
    demanda = models.OneToOneField(
        "core.Demanda",
        on_delete=models.CASCADE,
        related_name="assinatura_eletronica",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assinaturas_eletronicas",
    )
    hash_documento = models.CharField(
        max_length=64,
        help_text="SHA-256 do conteúdo canônico do ofício (PDF).",
    )
    hash_assinatura = models.CharField(
        max_length=64,
        unique=True,
        help_text="SHA-256 da evidência criptográfica (documento + signatário + momento).",
    )
    codigo_validacao = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        help_text="Código público para validação (QR Code / URL).",
    )
    ip_origem = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    declaracao = models.CharField(max_length=120, default="ASSINO E ENVIO")
    assinado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Assinatura eletrônica"
        verbose_name_plural = "Assinaturas eletrônicas"
        ordering = ["-assinado_em"]

    def __str__(self) -> str:
        return f"Assinatura demanda #{self.demanda_id} ({self.codigo_validacao[:8]}…)"
