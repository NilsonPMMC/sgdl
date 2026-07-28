"""Estudo e viabilidade — demandas finalizadas sem execução material (stand-by)."""

from django.conf import settings
from django.db import models


class ResultadoOperacional(models.TextChoices):
    EXECUTADO = "EXECUTADO", "Executado"
    RESPONDIDO_SEM_EXECUCAO = "RESPONDIDO_SEM_EXECUCAO", "Respondido sem execução"
    ORIENTACAO = "ORIENTACAO", "Somente orientação"
    PARCIAL = "PARCIAL", "Parcialmente executado"


class MotivoNaoExecucao(models.TextChoices):
    ESTUDO_VIABILIDADE = "ESTUDO_VIABILIDADE", "Estudo / viabilidade técnica"
    DEPENDE_INVESTIMENTO = "DEPENDE_INVESTIMENTO", "Depende de investimento"
    DEPENDE_LICITACAO = "DEPENDE_LICITACAO", "Depende de licitação / contratação"
    DEPENDE_NORMATIVO = "DEPENDE_NORMATIVO", "Depende de norma / legislação"
    INVIAVEL_TECNICO = "INVIAVEL_TECNICO", "Inviável técnico no momento"
    INFORMACIONAL = "INFORMACIONAL", "Registro informativo"


class RegistroEstudoViabilidade(models.Model):
    """Base stand-by para gestão executiva — apenas demandas sinalizadas na conclusão."""

    demanda = models.OneToOneField(
        "Demanda",
        on_delete=models.CASCADE,
        related_name="registro_estudo_viabilidade",
    )
    resultado_operacional = models.CharField(
        max_length=32,
        choices=ResultadoOperacional.choices,
    )
    motivo_nao_execucao = models.CharField(
        max_length=32,
        choices=MotivoNaoExecucao.choices,
        blank=True,
        default="",
    )
    escopo_geografico = models.TextField(
        blank=True,
        help_text="Ex.: município inteiro, bairro X, trecho da Rua Y.",
    )
    parecer_snapshot = models.TextField(blank=True)
    sinapse_orgao_id = models.BigIntegerField(null=True, blank=True)
    unidade_administrativa = models.ForeignKey(
        "UnidadeAdministrativa",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="registros_estudo_viabilidade",
    )
    pode_retomar = models.BooleanField(default=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="registros_estudo_viabilidade",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Registro de estudo e viabilidade"
        verbose_name_plural = "Registros de estudo e viabilidade"
        indexes = [
            models.Index(fields=["resultado_operacional"]),
            models.Index(fields=["motivo_nao_execucao"]),
            models.Index(fields=["sinapse_orgao_id"]),
            models.Index(fields=["-criado_em"]),
        ]

    def __str__(self) -> str:
        return f"Estudo/viabilidade — demanda #{self.demanda_id}"
