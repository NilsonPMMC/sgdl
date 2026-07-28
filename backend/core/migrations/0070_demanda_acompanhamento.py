# Generated manually for DemandaAcompanhamento

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0069_assinatura_operacao_scatter"),
    ]

    operations = [
        migrations.CreateModel(
            name="DemandaAcompanhamento",
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
                    "origem",
                    models.CharField(
                        choices=[
                            ("ENCERRAMENTO", "Após encerramento de nó"),
                            ("MANUAL", "Fixação manual"),
                        ],
                        default="MANUAL",
                        max_length=16,
                    ),
                ),
                ("ativo", models.BooleanField(db_index=True, default=True)),
                (
                    "criado_em",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                ("encerrado_em", models.DateTimeField(blank=True, null=True)),
                (
                    "demanda",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="acompanhamentos",
                        to="core.demanda",
                    ),
                ),
                (
                    "no_operacional",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="acompanhamentos_origem",
                        to="core.nooperacional",
                    ),
                ),
                (
                    "usuario",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="acompanhamentos_demanda",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-criado_em"],
            },
        ),
        migrations.AddConstraint(
            model_name="demandaacompanhamento",
            constraint=models.UniqueConstraint(
                fields=("usuario", "demanda"),
                name="uniq_demanda_acompanhamento_usuario_demanda",
            ),
        ),
    ]
