# Generated manually — catálogo Sinapse substitui Secretaria/Servico locais.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0031_rename_chatsession_index"),
        ("integrations", "0005_remove_sinapseservicomap_servico_local"),
    ]

    operations = [
        migrations.AddField(
            model_name="demanda",
            name="sinapse_orgao_id",
            field=models.BigIntegerField(
                blank=True,
                help_text="ID do órgão destino no Sinapse (CatalogOrgao); preenchido no despacho ou pelo catálogo.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="usuario",
            name="sinapse_orgao_id",
            field=models.BigIntegerField(
                blank=True,
                help_text="ID do órgão (CatalogOrgao) no Sinapse vinculado ao usuário de secretaria.",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="demanda",
            name="sinapse_servico_id",
            field=models.BigIntegerField(
                blank=True,
                help_text="ID do serviço na carta Sinapse (CatalogServico).",
                null=True,
            ),
        ),
        migrations.RemoveField(
            model_name="demanda",
            name="secretaria_destino",
        ),
        migrations.RemoveField(
            model_name="demanda",
            name="servico",
        ),
        migrations.RemoveField(
            model_name="usuario",
            name="secretaria",
        ),
        migrations.DeleteModel(
            name="Servico",
        ),
        migrations.DeleteModel(
            name="Secretaria",
        ),
    ]
