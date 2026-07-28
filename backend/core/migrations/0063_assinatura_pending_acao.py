from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0062_assinatura_eletronica_etapas"),
    ]

    operations = [
        migrations.CreateModel(
            name="AssinaturaPendingAcao",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("etapa", models.CharField(choices=[("ENVIO_OFICIO", "Envio oficial do ofício"), ("DESPACHO_INICIAL", "Despacho inicial (Protocolo)"), ("CONCLUSAO_SECRETARIA", "Conclusão operacional (Secretaria)"), ("DESPACHO_DEVOLUTIVA", "Despacho de devolutiva (Protocolo)")], max_length=32)),
                ("payload", models.JSONField(default=dict)),
                ("hash_documento", models.CharField(max_length=64)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("demanda", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="assinaturas_pendentes", to="core.demanda")),
            ],
            options={
                "verbose_name": "Prévia de assinatura pendente",
                "verbose_name_plural": "Prévias de assinatura pendentes",
            },
        ),
        migrations.AddConstraint(
            model_name="assinaturapendingacao",
            constraint=models.UniqueConstraint(fields=("demanda", "etapa"), name="uniq_assinatura_pending_demanda_etapa"),
        ),
    ]
