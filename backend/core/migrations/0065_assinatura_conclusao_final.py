# Generated manually — etapa CONCLUSAO_FINAL na assinatura eletrônica

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0064_operacional_portal_vereadores"),
    ]

    operations = [
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
                ],
                max_length=32,
            ),
        ),
    ]
