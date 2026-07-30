"""Cache local de vias de Mogi das Cruzes para geocodificação estável (Fase 3)."""

from django.db import models


class ViaReferenciaMogi(models.Model):
    """Logradouro oficial + coordenadas validadas — evita divergência OSM entre variantes."""

    ORIGEM_SEED = "seed"
    ORIGEM_HOMOLOGACAO = "homologacao"
    ORIGEM_OSM = "osm"
    ORIGEM_MANUAL = "manual"
    ORIGEM_CHOICES = (
        (ORIGEM_SEED, "Seed"),
        (ORIGEM_HOMOLOGACAO, "Homologação"),
        (ORIGEM_OSM, "OSM"),
        (ORIGEM_MANUAL, "Manual"),
    )

    logradouro = models.CharField(max_length=255)
    bairro = models.CharField(max_length=120)
    cep = models.CharField(max_length=9, blank=True, default="")
    chave_canonica = models.CharField(max_length=512, unique=True, db_index=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    fonte = models.CharField(max_length=32, default=ORIGEM_SEED)
    origem = models.CharField(max_length=20, choices=ORIGEM_CHOICES, default=ORIGEM_SEED)
    ativo = models.BooleanField(default=True)
    observacao = models.CharField(max_length=255, blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Via de referência (Mogi)"
        verbose_name_plural = "Vias de referência (Mogi)"
        ordering = ["logradouro", "bairro"]

    def __str__(self) -> str:
        return f"{self.logradouro} — {self.bairro}"
