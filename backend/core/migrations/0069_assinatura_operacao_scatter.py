# Generated manually — assinatura eletrônica por tramitação scatter-gather

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0068_no_operacional_scatter_gather"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="assinaturaeletronica",
            name="uniq_assinatura_demanda_etapa_papel",
        ),
        migrations.AddField(
            model_name="assinaturaeletronica",
            name="tramitacao",
            field=models.ForeignKey(
                blank=True,
                help_text="Tramitação OPERACAO_NO vinculada (scatter-gather).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="assinaturas_eletronicas",
                to="core.tramitacao",
            ),
        ),
        migrations.AlterField(
            model_name="assinaturaeletronica",
            name="etapa",
            field=models.CharField(
                choices=[
                    ("ENVIO_OFICIO", "Envio oficial do ofício"),
                    ("DESPACHO_INICIAL", "Despacho inicial (Protocolo)"),
                    ("CONCLUSAO_SECRETARIA", "Conclusão operacional (Secretaria)"),
                    ("DESPACHO_DEVOLUTIVA", "Despacho de devolutiva (Protocolo)"),
                    ("CONCLUSAO_FINAL", "Conclusão final (Protocolo)"),
                    ("OPERACAO_SCATTER", "Operação scatter-gather"),
                ],
                default="ENVIO_OFICIO",
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="assinaturapendingacao",
            name="etapa",
            field=models.CharField(
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
        migrations.AddConstraint(
            model_name="assinaturaeletronica",
            constraint=models.UniqueConstraint(
                condition=models.Q(("tramitacao__isnull", True)),
                fields=("demanda", "etapa", "papel"),
                name="uniq_assinatura_demanda_etapa_papel_sem_tram",
            ),
        ),
        migrations.AddConstraint(
            model_name="assinaturaeletronica",
            constraint=models.UniqueConstraint(
                condition=models.Q(("tramitacao__isnull", False)),
                fields=("tramitacao",),
                name="uniq_assinatura_tramitacao",
            ),
        ),
    ]
