from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0075_mascara_indicacao_sem_prefixo"),
        ("core", "0070_via_referencia_mogi"),
    ]

    operations = [
        migrations.AddField(
            model_name="tramitacao",
            name="editavel_ate",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text="Até este instante a tramitação pode ser corrigida ou desfeita pelo operador.",
                null=True,
            ),
        ),
    ]
