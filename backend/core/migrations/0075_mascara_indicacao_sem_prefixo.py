from django.db import migrations, models


def normalizar_mascara_indicacao(apps, schema_editor):
    NumeracaoIndicacaoCamara = apps.get_model("core", "NumeracaoIndicacaoCamara")
    NumeracaoIndicacaoCamara.objects.filter(mascara="IND nº {numero}/{ano}").update(
        mascara="{numero}/{ano}"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0074_camara_indicacao"),
    ]

    operations = [
        migrations.AlterField(
            model_name="numeracaoindicacaocamara",
            name="mascara",
            field=models.CharField(
                default="{numero}/{ano}",
                help_text="Formato exibido; use {numero} e {ano}.",
                max_length=64,
            ),
        ),
        migrations.RunPython(normalizar_mascara_indicacao, migrations.RunPython.noop),
    ]
