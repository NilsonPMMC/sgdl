# Simplifica categorias de textos padrão (PROTOCOLO | OPERACIONAL)

from django.db import migrations, models


def migrar_categorias(apps, schema_editor):
    TextoPadraoDespacho = apps.get_model("core", "TextoPadraoDespacho")
    proto = {"DESPACHO", "DEVOLUTIVA", "CONCLUSAO_FINAL", "RECUSA", "PROTOCOLO"}
    for obj in TextoPadraoDespacho.objects.all():
        cat = (obj.categoria or "").upper()
        obj.categoria = "PROTOCOLO" if cat in proto else "OPERACIONAL"
        obj.save(update_fields=["categoria"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0078_texto_padrao_unidades_m2m"),
    ]

    operations = [
        migrations.RunPython(migrar_categorias, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="textopadraodespacho",
            name="categoria",
            field=models.CharField(
                choices=[
                    ("PROTOCOLO", "Protocolo (despacho inicial e final)"),
                    ("OPERACIONAL", "Operacional (secretaria / setores)"),
                ],
                default="OPERACIONAL",
                max_length=32,
            ),
        ),
    ]
