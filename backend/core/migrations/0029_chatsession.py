# Generated manually for copiloto conversacional

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0028_clusterexecucao_demanda_embedding_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ChatSession",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "historico_mensagens",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text="Mensagens no formato OpenAI/Groq: role + content (sem o system fixo do copiloto).",
                    ),
                ),
                (
                    "estado_atual",
                    models.CharField(
                        choices=[
                            ("COLETA_DADOS", "Coleta de dados"),
                            ("CONFIRMACAO_SINAPSE", "Confirmação Sinapse"),
                            ("COLETA_ENDERECO", "Coleta de endereço"),
                            ("VALIDACAO_FINAL", "Validação final"),
                        ],
                        default="COLETA_DADOS",
                        max_length=32,
                    ),
                ),
                (
                    "demandas_rascunho",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text="Lista de dicts com rascunhos (titulo, descricao, endereco, servico_local_id, ...).",
                    ),
                ),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                (
                    "autor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chat_sessions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-atualizado_em"],
            },
        ),
        migrations.AddIndex(
            model_name="chatsession",
            index=models.Index(
                fields=["autor", "-atualizado_em"],
                name="chatsession_autor_upd",
            ),
        ),
    ]
