from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0066_perfil_processo_operacional"),
    ]

    operations = [
        migrations.CreateModel(
            name="PernaOperacional",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "sinapse_orgao_id",
                    models.BigIntegerField(help_text="Órgão/secretaria responsável por esta perna."),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDENTE", "Pendente"),
                            ("EM_EXECUCAO", "Em execução"),
                            ("CONCLUIDA", "Concluída"),
                            ("CANCELADA", "Cancelada"),
                        ],
                        default="PENDENTE",
                        max_length=16,
                    ),
                ),
                ("ordem", models.PositiveSmallIntegerField(default=1)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("criada_em", models.DateTimeField(auto_now_add=True)),
                ("atualizada_em", models.DateTimeField(auto_now=True)),
                (
                    "conclusao_tramitacao",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="perna_concluida",
                        to="core.tramitacao",
                    ),
                ),
                (
                    "demanda",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pernas_operacionais",
                        to="core.demanda",
                    ),
                ),
                (
                    "despacho_tramitacao",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="pernas_abertas",
                        to="core.tramitacao",
                    ),
                ),
                (
                    "unidade_administrativa",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="pernas_operacionais",
                        to="core.unidadeadministrativa",
                    ),
                ),
            ],
            options={
                "ordering": ["ordem", "pk"],
            },
        ),
        migrations.AddIndex(
            model_name="pernaoperacional",
            index=models.Index(fields=["demanda", "status"], name="core_perna_demanda_status_idx"),
        ),
        migrations.AddIndex(
            model_name="pernaoperacional",
            index=models.Index(fields=["sinapse_orgao_id", "status"], name="core_perna_orgao_status_idx"),
        ),
    ]
