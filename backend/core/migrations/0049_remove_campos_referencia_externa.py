# Generated manually — SGDL tramita ponta a ponta; referências externas (SEI/1Doc) removidas.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0048_encerramento_legislativo"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="demanda",
            name="link_externo",
        ),
        migrations.RemoveField(
            model_name="demanda",
            name="numero_externo",
        ),
        migrations.RemoveField(
            model_name="clusterexecucao",
            name="link_externo",
        ),
        migrations.RemoveField(
            model_name="clusterexecucao",
            name="numero_externo",
        ),
    ]
