from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0056_remove_demanda_revisao_assessor"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConfiguracaoCarta",
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
                    "prazo_padrao_dias",
                    models.PositiveIntegerField(
                        default=30,
                        help_text="Prazo operacional padrão (dias) quando política usar fallback ou PADRAO.",
                    ),
                ),
                (
                    "politica_prazo",
                    models.CharField(
                        choices=[
                            ("SERVICO", "Somente prazo do serviço"),
                            ("PADRAO", "Sempre prazo padrão"),
                            (
                                "SERVICO_COM_FALLBACK",
                                "Serviço com fallback para padrão",
                            ),
                        ],
                        default="SERVICO_COM_FALLBACK",
                        max_length=24,
                    ),
                ),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Configuração da carta (SLA)",
                "verbose_name_plural": "Configuração da carta (SLA)",
            },
        ),
        migrations.AddField(
            model_name="demanda",
            name="prazo_efetivo_dias",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="SLA em dias fixado ao protocolar (snapshot da política vigente).",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="demanda",
            name="prazo_origem",
            field=models.CharField(
                blank=True,
                choices=[
                    ("SERVICO", "Prazo do serviço"),
                    ("PADRAO", "Prazo padrão institucional"),
                    ("INDEFINIDO", "Sem prazo definido"),
                ],
                default="",
                help_text="Origem do prazo efetivo ao protocolar.",
                max_length=16,
            ),
        ),
    ]
