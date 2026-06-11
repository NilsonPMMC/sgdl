from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0043_demanda_data_entrada_etapa"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ServicoFluxoProtocolo",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "sinapse_servico_id",
                    models.BigIntegerField(
                        help_text="ID do serviço na carta Sinapse (CatalogServico).",
                        unique=True,
                    ),
                ),
                (
                    "modo",
                    models.CharField(
                        choices=[
                            ("MANUAL", "Triagem manual no Protocolo"),
                            (
                                "AUTOMATICO",
                                "Despacho automático ao órgão do serviço",
                            ),
                        ],
                        default="MANUAL",
                        max_length=16,
                    ),
                ),
                (
                    "ativo",
                    models.BooleanField(
                        default=True,
                        help_text="Desativado: trata como triagem manual mesmo com modo automático.",
                    ),
                ),
                ("observacoes", models.TextField(blank=True)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                (
                    "atualizado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="fluxos_servico_alterados",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Fluxo de serviço (Protocolo)",
                "verbose_name_plural": "Fluxos de serviços (Protocolo)",
                "ordering": ["sinapse_servico_id"],
            },
        ),
    ]
