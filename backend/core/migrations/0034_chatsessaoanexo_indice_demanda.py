from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0033_configuracao_oficio_chatsessaoanexo"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatsessaoanexo",
            name="indice_demanda",
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                help_text=(
                    "Índice 0-based em demandas_extraidas ao enviar o arquivo. "
                    "Vazio = vínculo só via anexos_indices no rascunho ou inferência na mensagem."
                ),
            ),
        ),
    ]
