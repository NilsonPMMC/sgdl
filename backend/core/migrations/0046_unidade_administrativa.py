from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0045_assinaturaeletronica"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UnidadeAdministrativa",
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
                    "sinapse_orgao_id",
                    models.BigIntegerField(
                        db_index=True,
                        help_text="Órgão (secretaria) no catálogo Sinapse.",
                    ),
                ),
                ("nome", models.CharField(max_length=200)),
                ("sigla", models.CharField(blank=True, max_length=20)),
                ("ativo", models.BooleanField(default=True)),
                (
                    "sinapse_unidade_id",
                    models.BigIntegerField(
                        blank=True,
                        help_text="Referência opcional à unidade no barramento Sinapse.",
                        null=True,
                    ),
                ),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Unidade administrativa (setor)",
                "verbose_name_plural": "Unidades administrativas (setores)",
                "ordering": ["sinapse_orgao_id", "nome"],
            },
        ),
        migrations.CreateModel(
            name="UnidadeAdministrativaResponsavel",
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
                    "pode_tramitar",
                    models.BooleanField(
                        default=True,
                        help_text="Permite encaminhar demandas entre setores.",
                    ),
                ),
                ("ativo", models.BooleanField(default=True)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                (
                    "unidade",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="responsaveis",
                        to="core.unidadeadministrativa",
                    ),
                ),
                (
                    "usuario",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="unidades_responsaveis",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Responsável por setor",
                "verbose_name_plural": "Responsáveis por setor",
                "ordering": ["unidade_id", "usuario_id"],
            },
        ),
        migrations.AddConstraint(
            model_name="unidadeadministrativa",
            constraint=models.UniqueConstraint(
                condition=models.Q(("sigla__gt", "")),
                fields=("sinapse_orgao_id", "sigla"),
                name="core_unidade_orgao_sigla_unica",
            ),
        ),
        migrations.AddConstraint(
            model_name="unidadeadministrativaresponsavel",
            constraint=models.UniqueConstraint(
                fields=("unidade", "usuario"),
                name="core_unidade_usuario_unico",
            ),
        ),
        migrations.AddField(
            model_name="demanda",
            name="unidade_administrativa",
            field=models.ForeignKey(
                blank=True,
                help_text="Setor operacional responsável pela execução.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="demandas",
                to="core.unidadeadministrativa",
            ),
        ),
        migrations.AlterField(
            model_name="tramitacao",
            name="tipo",
            field=models.CharField(
                choices=[
                    ("ENVIO_OFICIAL", "Envio Oficial"),
                    ("DESPACHO", "Despacho para Secretaria"),
                    ("STATUS_UPDATE", "Atualização de Status"),
                    ("COMENTARIO", "Comentário"),
                    ("ANALISE_TECNICA", "Análise Técnica"),
                    ("ATRASO", "Registro de Atraso"),
                    ("PROGRAMACAO", "Programação do Serviço"),
                    ("CONCLUSAO", "Conclusão do Serviço"),
                    ("TRANSFERENCIA", "Transferência de Setor/Secretaria"),
                    ("ENCAMINHAMENTO_SETOR", "Encaminhamento entre setores"),
                ],
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="tramitacao",
            name="unidade_destino",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="tramitacoes_entrada",
                to="core.unidadeadministrativa",
            ),
        ),
        migrations.AddField(
            model_name="tramitacao",
            name="unidade_origem",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="tramitacoes_saida",
                to="core.unidadeadministrativa",
            ),
        ),
    ]
