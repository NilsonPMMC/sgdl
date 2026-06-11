from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0053_configuracao_oficio_pl224_refinamento"),
    ]

    operations = [
        migrations.AddField(
            model_name="configuracaooficio",
            name="cabecalho_layout",
            field=models.CharField(
                choices=[
                    ("BRASAO_ESQUERDA_TEXTO", "Brasão | Descrição"),
                    ("TEXTO_ESQUERDA_BRASAO", "Descrição | Brasão"),
                    ("BRASAO_CENTRO", "Somente brasão (centro)"),
                    ("BRASAO_ACIMA_TEXTO", "Brasão acima da descrição"),
                    ("TEXTO_CENTRO", "Somente descrição (centro)"),
                ],
                default="BRASAO_ESQUERDA_TEXTO",
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="configuracaooficio",
            name="titulo_instituicao",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Texto institucional ao lado do brasão (opcional).",
                max_length=255,
            ),
        ),
    ]
