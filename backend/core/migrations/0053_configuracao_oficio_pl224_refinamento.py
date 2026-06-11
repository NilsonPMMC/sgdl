from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0052_configuracao_oficio_camara_layout"),
    ]

    operations = [
        migrations.AddField(
            model_name="configuracaooficio",
            name="titulo_instituicao",
            field=models.CharField(
                blank=True,
                default="CÂMARA MUNICIPAL DE MOGI DAS CRUZES",
                help_text="Texto institucional ao lado do brasão.",
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="configuracaooficio",
            name="brasao_largura_cm",
            field=models.DecimalField(decimal_places=2, default=Decimal("2.80"), max_digits=4),
        ),
        migrations.AddField(
            model_name="configuracaooficio",
            name="rodape_protocolo_altura_cm",
            field=models.DecimalField(decimal_places=2, default=Decimal("2.50"), max_digits=4),
        ),
        migrations.AlterField(
            model_name="configuracaooficio",
            name="municipio",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Cidade usada no cabeçalho e na data do ofício (opcional).",
                max_length=120,
            ),
        ),
        migrations.AlterField(
            model_name="configuracaooficio",
            name="uf",
            field=models.CharField(blank=True, default="", max_length=2),
        ),
        migrations.AlterField(
            model_name="configuracaooficio",
            name="margem_superior_cm",
            field=models.DecimalField(decimal_places=2, default=Decimal("2.50"), max_digits=4),
        ),
        migrations.AlterField(
            model_name="configuracaooficio",
            name="margem_inferior_cm",
            field=models.DecimalField(decimal_places=2, default=Decimal("2.50"), max_digits=4),
        ),
        migrations.AlterField(
            model_name="configuracaooficio",
            name="margem_esquerda_cm",
            field=models.DecimalField(decimal_places=2, default=Decimal("3.00"), max_digits=4),
        ),
        migrations.AlterField(
            model_name="configuracaooficio",
            name="margem_direita_cm",
            field=models.DecimalField(decimal_places=2, default=Decimal("2.00"), max_digits=4),
        ),
    ]
