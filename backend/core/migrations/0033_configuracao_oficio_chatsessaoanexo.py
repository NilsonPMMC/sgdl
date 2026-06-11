# Generated manually

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0032_remove_local_catalog_use_sinapse"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConfiguracaoOficio",
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
                ("municipio", models.CharField(default="Mogi das Cruzes", max_length=120)),
                ("uf", models.CharField(default="SP", max_length=2)),
                (
                    "orgao_destinatario",
                    models.CharField(
                        default="Prefeitura Municipal de Mogi das Cruzes",
                        max_length=255,
                    ),
                ),
                (
                    "destinatario_tratamento",
                    models.CharField(
                        default="Excelentíssima Senhora Prefeita Municipal",
                        max_length=80,
                    ),
                ),
                (
                    "destinatario_nome",
                    models.CharField(default="Mara Bertaiolli", max_length=200),
                ),
                (
                    "destinatario_cargo",
                    models.CharField(blank=True, default="Prefeita Municipal", max_length=200),
                ),
                (
                    "gabinete_nome",
                    models.CharField(
                        blank=True,
                        default="Gabinete do Legislativo Municipal",
                        max_length=255,
                    ),
                ),
                ("texto_abertura", models.TextField(blank=True)),
                (
                    "texto_encerramento",
                    models.CharField(
                        blank=True,
                        default="Nestes termos, pede deferimento.",
                        max_length=500,
                    ),
                ),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Configuração de ofício",
                "verbose_name_plural": "Configuração de ofício",
            },
        ),
        migrations.CreateModel(
            name="ChatSessaoAnexo",
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
                ("arquivo", models.FileField(upload_to="chat_anexos/%Y/%m/%d/")),
                (
                    "descricao",
                    models.CharField(
                        blank=True,
                        default="Anexo do copiloto",
                        max_length=200,
                    ),
                ),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="anexos_sessao",
                        to="core.chatsession",
                    ),
                ),
            ],
            options={
                "ordering": ["criado_em"],
            },
        ),
    ]
