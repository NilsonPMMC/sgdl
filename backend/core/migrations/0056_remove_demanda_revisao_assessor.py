from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0055_demanda_revisao_assessor"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="demanda",
            name="revisao_assessor_observacao",
        ),
        migrations.RemoveField(
            model_name="demanda",
            name="revisao_assessor_por",
        ),
        migrations.RemoveField(
            model_name="demanda",
            name="revisao_assessor_em",
        ),
        migrations.RemoveField(
            model_name="demanda",
            name="revisao_assessor_status",
        ),
    ]
