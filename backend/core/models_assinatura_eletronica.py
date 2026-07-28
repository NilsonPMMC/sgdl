"""Registro de assinaturas eletrônicas nativas (ofício e etapas operacionais)."""

from django.conf import settings
from django.db import models


class AssinaturaEletronica(models.Model):
    ETAPA_ENVIO_OFICIO = "ENVIO_OFICIO"
    ETAPA_DESPACHO_INICIAL = "DESPACHO_INICIAL"
    ETAPA_CONCLUSAO_SECRETARIA = "CONCLUSAO_SECRETARIA"
    ETAPA_DESPACHO_DEVOLUTIVA = "DESPACHO_DEVOLUTIVA"
    ETAPA_CONCLUSAO_FINAL = "CONCLUSAO_FINAL"
    ETAPA_OPERACAO_SCATTER = "OPERACAO_SCATTER"

    ETAPA_CHOICES = (
        (ETAPA_ENVIO_OFICIO, "Envio oficial do ofício"),
        (ETAPA_DESPACHO_INICIAL, "Despacho inicial (Protocolo)"),
        (ETAPA_CONCLUSAO_SECRETARIA, "Conclusão operacional (Secretaria)"),
        (ETAPA_DESPACHO_DEVOLUTIVA, "Despacho de devolutiva (Protocolo)"),
        (ETAPA_CONCLUSAO_FINAL, "Conclusão final (Protocolo)"),
        (ETAPA_OPERACAO_SCATTER, "Operação scatter-gather"),
    )

    PAPEL_OPERADOR = "OPERADOR"
    PAPEL_GESTOR_PROTOCOLO = "GESTOR_PROTOCOLO"
    PAPEL_GESTOR_SETOR = "GESTOR_SETOR"
    PAPEL_CHEFIA_SETOR = "CHEFIA_SETOR"

    PAPEL_CHOICES = (
        (PAPEL_OPERADOR, "Operador"),
        (PAPEL_GESTOR_PROTOCOLO, "Gestor do Protocolo"),
        (PAPEL_GESTOR_SETOR, "Gestor do setor"),
        (PAPEL_CHEFIA_SETOR, "Chefia do setor"),
    )

    demanda = models.ForeignKey(
        "core.Demanda",
        on_delete=models.CASCADE,
        related_name="assinaturas_eletronicas",
    )
    tramitacao = models.ForeignKey(
        "core.Tramitacao",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assinaturas_eletronicas",
        help_text="Tramitação OPERACAO_NO vinculada (scatter-gather).",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assinaturas_eletronicas_registradas",
    )
    etapa = models.CharField(max_length=32, choices=ETAPA_CHOICES, default=ETAPA_ENVIO_OFICIO)
    papel = models.CharField(max_length=24, choices=PAPEL_CHOICES, default=PAPEL_OPERADOR)
    hash_documento = models.CharField(
        max_length=64,
        help_text="SHA-256 do conteúdo canônico assinado.",
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
        constraints = [
            models.UniqueConstraint(
                fields=["demanda", "etapa", "papel"],
                condition=models.Q(tramitacao__isnull=True),
                name="uniq_assinatura_demanda_etapa_papel_sem_tram",
            ),
            models.UniqueConstraint(
                fields=["tramitacao", "papel"],
                condition=models.Q(tramitacao__isnull=False),
                name="uniq_assinatura_tramitacao_papel",
            ),
        ]

    def __str__(self) -> str:
        return f"Assinatura #{self.demanda_id} {self.etapa}/{self.papel} ({self.codigo_validacao[:8]}…)"


class AssinaturaPendingAcao(models.Model):
    """Prévia pendente de assinatura (substitui arquivo em disco; seguro com múltiplos workers)."""

    demanda = models.ForeignKey(
        "core.Demanda",
        on_delete=models.CASCADE,
        related_name="assinaturas_pendentes",
    )
    etapa = models.CharField(max_length=32, choices=AssinaturaEletronica.ETAPA_CHOICES)
    payload = models.JSONField(default=dict)
    hash_documento = models.CharField(max_length=64)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Prévia de assinatura pendente"
        verbose_name_plural = "Prévias de assinatura pendentes"
        constraints = [
            models.UniqueConstraint(
                fields=["demanda", "etapa"],
                name="uniq_assinatura_pending_demanda_etapa",
            ),
        ]

    def __str__(self) -> str:
        return f"Pending #{self.demanda_id} {self.etapa} ({self.hash_documento[:8]}…)"


class AssinaturaValidacaoGestor(models.Model):
    """Validação assíncrona pelo gestor após assinatura do operador/chefia."""

    STATUS_PENDENTE = "PENDENTE"
    STATUS_CONCLUIDA = "CONCLUIDA"
    STATUS_CANCELADA = "CANCELADA"
    STATUS_CHOICES = (
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_CONCLUIDA, "Concluída"),
        (STATUS_CANCELADA, "Cancelada"),
    )

    TIPO_GESTOR_PROTOCOLO = "PROTOCOLO"
    TIPO_GESTOR_SETOR = "SETOR"
    TIPO_GESTOR_CHOICES = (
        (TIPO_GESTOR_PROTOCOLO, "Gestor do Protocolo"),
        (TIPO_GESTOR_SETOR, "Gestor do setor"),
    )

    demanda = models.ForeignKey(
        "core.Demanda",
        on_delete=models.CASCADE,
        related_name="validacoes_assinatura_gestor",
    )
    tramitacao = models.ForeignKey(
        "core.Tramitacao",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="validacoes_assinatura_gestor",
    )
    etapa = models.CharField(max_length=32, choices=AssinaturaEletronica.ETAPA_CHOICES)
    tipo_gestor = models.CharField(max_length=16, choices=TIPO_GESTOR_CHOICES)
    hash_documento = models.CharField(max_length=64)
    payload = models.JSONField(default=dict)
    operador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="validacoes_assinatura_solicitadas",
    )
    unidade_administrativa = models.ForeignKey(
        "core.UnidadeAdministrativa",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="validacoes_assinatura_gestor",
    )
    sinapse_orgao_id = models.IntegerField(null=True, blank=True)
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_PENDENTE,
        db_index=True,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    concluido_em = models.DateTimeField(null=True, blank=True)
    gestor_validador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="validacoes_assinatura_concluidas",
    )

    class Meta:
        verbose_name = "Validação de assinatura (gestor)"
        verbose_name_plural = "Validações de assinatura (gestor)"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["status", "tipo_gestor"]),
        ]

    def __str__(self) -> str:
        return f"Validação #{self.demanda_id} {self.etapa} ({self.status})"
