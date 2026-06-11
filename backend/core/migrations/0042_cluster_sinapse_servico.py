from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0041_adicionar_campos_atendimento_sistema"),
    ]

    operations = [
        migrations.AddField(
            model_name="clusterexecucao",
            name="sinapse_servico_id",
            field=models.BigIntegerField(
                blank=True,
                null=True,
                help_text="Serviço Sinapse que unifica o agrupamento (mesmo serviço + proximidade).",
            ),
        ),
    ]
