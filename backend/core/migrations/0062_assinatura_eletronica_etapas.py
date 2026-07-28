from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def preencher_etapa_envio(apps, schema_editor):
    AssinaturaEletronica = apps.get_model("core", "AssinaturaEletronica")
    AssinaturaEletronica.objects.update(etapa="ENVIO_OFICIO", papel="OPERADOR")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0061_alter_configuracaooficio_brasao_largura_cm_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="assinaturaeletronica",
            name="etapa",
            field=models.CharField(
                choices=[
                    ("ENVIO_OFICIO", "Envio oficial do ofício"),
                    ("DESPACHO_INICIAL", "Despacho inicial (Protocolo)"),
                    ("CONCLUSAO_SECRETARIA", "Conclusão operacional (Secretaria)"),
                    ("DESPACHO_DEVOLUTIVA", "Despacho de devolutiva (Protocolo)"),
                ],
                default="ENVIO_OFICIO",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="assinaturaeletronica",
            name="papel",
            field=models.CharField(
                choices=[
                    ("OPERADOR", "Operador"),
                    ("GESTOR_PROTOCOLO", "Gestor do Protocolo"),
                    ("CHEFIA_SETOR", "Chefia do setor"),
                ],
                default="OPERADOR",
                max_length=24,
            ),
        ),
        migrations.AlterField(
            model_name="assinaturaeletronica",
            name="demanda",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="assinaturas_eletronicas",
                to="core.demanda",
            ),
        ),
        migrations.AlterField(
            model_name="assinaturaeletronica",
            name="usuario",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="assinaturas_eletronicas_registradas",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="assinaturaeletronica",
            name="hash_documento",
            field=models.CharField(
                help_text="SHA-256 do conteúdo canônico assinado.",
                max_length=64,
            ),
        ),
        migrations.RunPython(preencher_etapa_envio, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="assinaturaeletronica",
            constraint=models.UniqueConstraint(
                fields=("demanda", "etapa", "papel"),
                name="uniq_assinatura_demanda_etapa_papel",
            ),
        ),
    ]
