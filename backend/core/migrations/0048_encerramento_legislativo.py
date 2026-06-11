from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0047_devolutiva_protocolo"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EncerramentoLegislativo",
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
                    "texto_resposta_cidadao",
                    models.TextField(
                        blank=True,
                        help_text="Texto da resposta formal ao cidadão (ofício de devolutiva).",
                    ),
                ),
                ("ciencia_em", models.DateTimeField(blank=True, null=True)),
                ("encerrado_em", models.DateTimeField(blank=True, null=True)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                (
                    "ciencia_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ciencias_devolutiva",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "demanda",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="encerramento_legislativo",
                        to="core.demanda",
                    ),
                ),
            ],
            options={
                "verbose_name": "Encerramento legislativo",
                "verbose_name_plural": "Encerramentos legislativos",
            },
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
                    ("SOLICITACAO_DEVOLUTIVA", "Solicitação de devolutiva"),
                    ("DEVOLUTIVA_PROTOCOLO", "Devolutiva ao vereador"),
                    ("ENCERRAMENTO_DEVOLUTIVA", "Encerramento legislativo"),
                    ("CIENCIA_VEREADOR", "Ciência do vereador"),
                ],
                max_length=24,
            ),
        ),
    ]
