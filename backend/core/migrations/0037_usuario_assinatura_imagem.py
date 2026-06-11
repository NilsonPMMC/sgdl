from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0036_copiloto_faq_orientacao"),
    ]

    operations = [
        migrations.AddField(
            model_name="usuario",
            name="assinatura_imagem",
            field=models.ImageField(
                blank=True,
                help_text="Imagem da assinatura (PNG/JPG) usada no rodapé do ofício em PDF.",
                null=True,
                upload_to="assinaturas/%Y/%m/",
            ),
        ),
    ]
