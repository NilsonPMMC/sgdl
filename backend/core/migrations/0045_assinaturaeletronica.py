from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0044_servico_fluxo_protocolo"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AssinaturaEletronica",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "hash_documento",
                    models.CharField(
                        help_text="SHA-256 do conteúdo canônico do ofício (PDF).",
                        max_length=64,
                    ),
                ),
                (
                    "hash_assinatura",
                    models.CharField(
                        help_text="SHA-256 da evidência criptográfica (documento + signatário + momento).",
                        max_length=64,
                        unique=True,
                    ),
                ),
                (
                    "codigo_validacao",
                    models.CharField(
                        db_index=True,
                        help_text="Código público para validação (QR Code / URL).",
                        max_length=32,
                        unique=True,
                    ),
                ),
                ("ip_origem", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.CharField(blank=True, max_length=500)),
                (
                    "declaracao",
                    models.CharField(default="ASSINO E ENVIO", max_length=120),
                ),
                ("assinado_em", models.DateTimeField(auto_now_add=True)),
                (
                    "demanda",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assinatura_eletronica",
                        to="core.demanda",
                    ),
                ),
                (
                    "usuario",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="assinaturas_eletronicas",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Assinatura eletrônica",
                "verbose_name_plural": "Assinaturas eletrônicas",
                "ordering": ["-assinado_em"],
            },
        ),
    ]
