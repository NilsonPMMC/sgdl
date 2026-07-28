# Generated manually — scatter-gather (nós operacionais)

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0067_perna_operacional"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="demanda",
            name="nos_ativos",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Contagem denormalizada de nós operacionais abertos (scatter-gather).",
            ),
        ),
        migrations.AlterField(
            model_name="tramitacao",
            name="tipo",
            field=models.CharField(
                max_length=24,
                choices=[
                    ("ENVIO_OFICIAL", "Envio Oficial"),
                    ("DESPACHO", "Despacho para Secretaria"),
                    ("STATUS_UPDATE", "Atualização de Status"),
                    ("COMENTARIO", "Comentário"),
                    ("ANALISE_TECNICA", "Análise Técnica"),
                    ("EXECUCAO", "Execução"),
                    ("ATRASO", "Registro de Atraso"),
                    ("PROGRAMACAO", "Programação do Serviço"),
                    ("CONCLUSAO", "Conclusão do Serviço"),
                    ("TRANSFERENCIA", "Transferência de Setor/Secretaria"),
                    ("ENCAMINHAMENTO_SETOR", "Encaminhamento entre setores"),
                    ("SOLICITACAO_DEVOLUTIVA", "Solicitação de devolutiva"),
                    ("DEVOLUTIVA_PROTOCOLO", "Devolutiva ao vereador"),
                    ("ENCERRAMENTO_DEVOLUTIVA", "Encerramento legislativo"),
                    ("CIENCIA_VEREADOR", "Ciência do vereador"),
                    ("TRIAGEM_PROTOCOLO", "Triagem do Protocolo"),
                    ("RECUSA_PROTOCOLO", "Recusa do Protocolo ao vereador"),
                    ("CONCLUSAO_TECNICA", "Conclusão técnica (fluxo direto)"),
                    ("CONCLUSAO_PARCIAL", "Conclusão parcial (fluxo transversal)"),
                    ("DEVOLUCAO", "Devolução ao Protocolo"),
                    ("CONCLUSAO_FINAL", "Conclusão final (Protocolo)"),
                    ("OPERACAO_NO", "Operação scatter-gather (nó)"),
                ],
            ),
        ),
        migrations.CreateModel(
            name="NoOperacional",
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
                ("sinapse_orgao_id", models.BigIntegerField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("ABERTO", "Aberto"),
                            ("CONCLUIDO", "Concluído"),
                            ("CANCELADO", "Cancelado"),
                        ],
                        default="ABERTO",
                        max_length=16,
                    ),
                ),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("aberto_em", models.DateTimeField(auto_now_add=True)),
                ("concluido_em", models.DateTimeField(blank=True, null=True)),
                (
                    "abertura_tramitacao",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="nos_abertos",
                        to="core.tramitacao",
                    ),
                ),
                (
                    "demanda",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="nos_operacionais",
                        to="core.demanda",
                    ),
                ),
                (
                    "encerramento_tramitacao",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="nos_encerrados",
                        to="core.tramitacao",
                    ),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="filhos",
                        to="core.nooperacional",
                    ),
                ),
                (
                    "perna_operacional",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="nos_operacionais",
                        to="core.pernaoperacional",
                    ),
                ),
                (
                    "responsavel_abertura",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="nos_operacionais_abertos",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "unidade_administrativa",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="nos_operacionais",
                        to="core.unidadeadministrativa",
                    ),
                ),
            ],
            options={
                "ordering": ["aberto_em", "pk"],
            },
        ),
        migrations.AddIndex(
            model_name="nooperacional",
            index=models.Index(fields=["demanda", "status"], name="core_nooper_demanda_status_idx"),
        ),
        migrations.AddIndex(
            model_name="nooperacional",
            index=models.Index(fields=["parent", "status"], name="core_nooper_parent_status_idx"),
        ),
        migrations.AddIndex(
            model_name="nooperacional",
            index=models.Index(
                fields=["sinapse_orgao_id", "status"],
                name="core_nooper_orgao_status_idx",
            ),
        ),
    ]
