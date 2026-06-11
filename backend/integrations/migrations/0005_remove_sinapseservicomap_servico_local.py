from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0004_catalogcategoria_catalogorgao_catalogpublico_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="sinapseservicomap",
            name="servico_local",
        ),
    ]
