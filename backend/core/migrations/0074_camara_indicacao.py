# Generated manually — perfil CAMARA, tipo indicação, vínculos vereador, numeração Câmara

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0073_rename_core_assina_status_8f3a21_idx_core_assina_status_1e1c27_idx"),
    ]

    operations = [
        migrations.AlterField(
            model_name="usuario",
            name="perfil",
            field=models.CharField(
                blank=True,
                choices=[
                    ("VEREADOR", "Vereador"),
                    ("ASSESSOR", "Assessor Legislativo"),
                    ("CAMARA", "Câmara Municipal"),
                    ("PROTOCOLO", "Protocolo"),
                    ("SECRETARIA", "Secretaria"),
                    ("GESTOR", "Gestor"),
                ],
                max_length=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="demanda",
            name="tipo_legislativo",
            field=models.CharField(
                choices=[("OFICIO", "Ofício"), ("INDICACAO", "Indicação")],
                default="OFICIO",
                help_text="Ofício (gabinete) ou indicação (protocolo legislativo da Câmara).",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="demanda",
            name="numero_indicacao",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Número sequencial da indicação no ano (parte numérica do protocolo Câmara).",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="demanda",
            name="ano_indicacao",
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text="Ano de referência da numeração da indicação.",
                null=True,
            ),
        ),
        migrations.CreateModel(
            name="NumeracaoIndicacaoCamara",
            fields=[
                (
                    "pk_fixo",
                    models.PositiveSmallIntegerField(
                        default=1,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "ano",
                    models.PositiveSmallIntegerField(
                        default=2026,
                        help_text="Ano corrente da sequência de indicações.",
                    ),
                ),
                (
                    "ultimo_numero",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Último número de indicação já utilizado no ano (informado pela Câmara).",
                    ),
                ),
                (
                    "mascara",
                    models.CharField(
                        default="IND nº {numero}/{ano}",
                        help_text="Formato exibido; use {numero} e {ano}.",
                        max_length=64,
                    ),
                ),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Numeração de indicações (Câmara)",
                "verbose_name_plural": "Numeração de indicações (Câmara)",
            },
        ),
        migrations.CreateModel(
            name="DemandaVereadorVinculo",
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
                    "papel",
                    models.CharField(
                        choices=[("AUTOR", "Autor"), ("COAUTOR", "Coautor")],
                        default="COAUTOR",
                        max_length=16,
                    ),
                ),
                ("data_vinculo", models.DateTimeField(auto_now_add=True)),
                (
                    "demanda",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="vinculos_vereador",
                        to="core.demanda",
                    ),
                ),
                (
                    "vereador",
                    models.ForeignKey(
                        limit_choices_to={"perfil": "VEREADOR"},
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="indicacoes_vinculadas",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="demanda",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("protocolo_legislativo__isnull", False),
                    ("tipo_legislativo", "INDICACAO"),
                ),
                fields=("protocolo_legislativo",),
                name="unique_protocolo_indicacao_camara",
            ),
        ),
        migrations.AddConstraint(
            model_name="demandavereadorvinculo",
            constraint=models.UniqueConstraint(
                fields=("demanda", "vereador"),
                name="unique_vereador_por_indicacao",
            ),
        ),
    ]
