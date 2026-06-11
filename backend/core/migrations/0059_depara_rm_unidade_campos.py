from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0058_servico_otimizado_unidade_administrativa"),
    ]

    operations = [
        migrations.CreateModel(
            name="DeParaRmSinapse",
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
                    "cod_rm",
                    models.CharField(
                        help_text="Código da secretaria no 2.º segmento da sigla RM (ex.: SMSBE).",
                        max_length=20,
                        unique=True,
                    ),
                ),
                (
                    "sinapse_orgao_id",
                    models.BigIntegerField(
                        blank=True,
                        db_index=True,
                        help_text="ID do órgão no catálogo Sinapse. Vazio = pendente de mapeamento.",
                        null=True,
                    ),
                ),
                ("observacao", models.CharField(blank=True, max_length=255)),
                (
                    "ativo",
                    models.BooleanField(
                        default=True,
                        help_text="Se falso, unidades com este COD_RM não são importadas.",
                    ),
                ),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "De-para RM → Sinapse",
                "verbose_name_plural": "De-para RM → Sinapse",
                "ordering": ["cod_rm"],
            },
        ),
        migrations.AddField(
            model_name="unidadeadministrativa",
            name="cod_rm_orgao",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Código RM da secretaria (2.º segmento da sigla).",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="unidadeadministrativa",
            name="email_contato",
            field=models.EmailField(
                blank=True,
                help_text="E-mail de contato da unidade (importação RM271698).",
                max_length=254,
            ),
        ),
        migrations.AlterField(
            model_name="unidadeadministrativa",
            name="sigla",
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddConstraint(
            model_name="unidadeadministrativa",
            constraint=models.UniqueConstraint(
                condition=models.Q(("sinapse_unidade_id__isnull", False)),
                fields=("sinapse_unidade_id",),
                name="core_unidade_sinapse_unidade_id_unica",
            ),
        ),
    ]
