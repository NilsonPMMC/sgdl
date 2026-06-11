from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0029_chatsession"),
    ]

    operations = [
        migrations.AddField(
            model_name="demanda",
            name="sinapse_servico_id",
            field=models.IntegerField(
                blank=True,
                help_text="ID do serviço na carta Sinapse escolhido na triagem do copiloto.",
                null=True,
            ),
        ),
    ]
