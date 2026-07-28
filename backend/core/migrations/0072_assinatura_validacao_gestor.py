# Generated manually — validação assíncrona de assinaturas pelo gestor

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0071_estudo_viabilidade"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="assinaturaeletronica",
            name="uniq_assinatura_tramitacao",
        ),
        migrations.AlterField(
            model_name="assinaturaeletronica",
            name="papel",
            field=models.CharField(
                choices=[
                    ("OPERADOR", "Operador"),
                    ("GESTOR_PROTOCOLO", "Gestor do Protocolo"),
                    ("GESTOR_SETOR", "Gestor do setor"),
                    ("CHEFIA_SETOR", "Chefia do setor"),
                ],
                default="OPERADOR",
                max_length=24,
            ),
        ),
        migrations.AddConstraint(
            model_name="assinaturaeletronica",
            constraint=models.UniqueConstraint(
                condition=models.Q(("tramitacao__isnull", False)),
                fields=("tramitacao", "papel"),
                name="uniq_assinatura_tramitacao_papel",
            ),
        ),
        migrations.CreateModel(
            name="AssinaturaValidacaoGestor",
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
                    "etapa",
                    models.CharField(
                        choices=[
                            ("ENVIO_OFICIO", "Envio oficial do ofício"),
                            ("DESPACHO_INICIAL", "Despacho inicial (Protocolo)"),
                            ("CONCLUSAO_SECRETARIA", "Conclusão operacional (Secretaria)"),
                            ("DESPACHO_DEVOLUTIVA", "Despacho de devolutiva (Protocolo)"),
                            ("CONCLUSAO_FINAL", "Conclusão final (Protocolo)"),
                            ("OPERACAO_SCATTER", "Operação scatter-gather"),
                        ],
                        max_length=32,
                    ),
                ),
                (
                    "tipo_gestor",
                    models.CharField(
                        choices=[
                            ("PROTOCOLO", "Gestor do Protocolo"),
                            ("SETOR", "Gestor do setor"),
                        ],
                        max_length=16,
                    ),
                ),
                ("hash_documento", models.CharField(max_length=64)),
                ("payload", models.JSONField(default=dict)),
                ("sinapse_orgao_id", models.IntegerField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDENTE", "Pendente"),
                            ("CONCLUIDA", "Concluída"),
                            ("CANCELADA", "Cancelada"),
                        ],
                        db_index=True,
                        default="PENDENTE",
                        max_length=16,
                    ),
                ),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("concluido_em", models.DateTimeField(blank=True, null=True)),
                (
                    "demanda",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="validacoes_assinatura_gestor",
                        to="core.demanda",
                    ),
                ),
                (
                    "gestor_validador",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="validacoes_assinatura_concluidas",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "operador",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="validacoes_assinatura_solicitadas",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "tramitacao",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="validacoes_assinatura_gestor",
                        to="core.tramitacao",
                    ),
                ),
                (
                    "unidade_administrativa",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="validacoes_assinatura_gestor",
                        to="core.unidadeadministrativa",
                    ),
                ),
            ],
            options={
                "verbose_name": "Validação de assinatura (gestor)",
                "verbose_name_plural": "Validações de assinatura (gestor)",
                "ordering": ["-criado_em"],
                "indexes": [
                    models.Index(
                        fields=["status", "tipo_gestor"],
                        name="core_assina_status_8f3a21_idx",
                    )
                ],
            },
        ),
        migrations.AlterField(
            model_name="notificacao",
            name="tipo",
            field=models.CharField(
                choices=[
                    ("NOVO_OFICIO", "Novo Ofício"),
                    ("DESPACHO", "Despacho"),
                    ("ATUALIZACAO", "Atualização"),
                    ("TRANSFERENCIA", "Transferência"),
                    ("CONCLUSAO", "Conclusão"),
                    ("DEVOLUTIVA", "Devolutiva"),
                    ("ATRASO", "Atraso"),
                    ("ASSINATURA_PENDENTE", "Assinatura pendente"),
                ],
                default="ATUALIZACAO",
                max_length=24,
            ),
        ),
    ]
