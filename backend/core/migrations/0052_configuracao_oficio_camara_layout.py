from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0051_oficio_legislativo_por_autor"),
    ]

    operations = [
        migrations.AddField(
            model_name="configuracaooficio",
            name="imagem_cabecalho",
            field=models.ImageField(
                blank=True,
                help_text="Brasão ou arte institucional do cabeçalho.",
                null=True,
                upload_to="oficio_config/",
            ),
        ),
        migrations.AddField(
            model_name="configuracaooficio",
            name="pagina_formato",
            field=models.CharField(
                choices=[("A4", "A4"), ("LETTER", "Carta")],
                default="A4",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="configuracaooficio",
            name="pagina_orientacao",
            field=models.CharField(
                choices=[("portrait", "Retrato"), ("landscape", "Paisagem")],
                default="portrait",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="configuracaooficio",
            name="margem_superior_cm",
            field=models.DecimalField(decimal_places=2, default=Decimal("2.20"), max_digits=4),
        ),
        migrations.AddField(
            model_name="configuracaooficio",
            name="margem_inferior_cm",
            field=models.DecimalField(decimal_places=2, default=Decimal("2.20"), max_digits=4),
        ),
        migrations.AddField(
            model_name="configuracaooficio",
            name="margem_esquerda_cm",
            field=models.DecimalField(decimal_places=2, default=Decimal("2.00"), max_digits=4),
        ),
        migrations.AddField(
            model_name="configuracaooficio",
            name="margem_direita_cm",
            field=models.DecimalField(decimal_places=2, default=Decimal("2.00"), max_digits=4),
        ),
        migrations.RemoveField(
            model_name="configuracaooficio",
            name="gabinete_nome",
        ),
        migrations.RemoveField(
            model_name="configuracaooficio",
            name="texto_abertura",
        ),
        migrations.RemoveField(
            model_name="configuracaooficio",
            name="texto_encerramento",
        ),
    ]
