# Generated manually — cache local de vias Mogi (geocoding Fase 3)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0069_assinatura_operacao_scatter"),
    ]

    operations = [
        migrations.CreateModel(
            name="ViaReferenciaMogi",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("logradouro", models.CharField(max_length=255)),
                ("bairro", models.CharField(max_length=120)),
                ("cep", models.CharField(blank=True, default="", max_length=9)),
                ("chave_canonica", models.CharField(db_index=True, max_length=512, unique=True)),
                ("latitude", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ("longitude", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ("fonte", models.CharField(default="seed", max_length=32)),
                (
                    "origem",
                    models.CharField(
                        choices=[
                            ("seed", "Seed"),
                            ("homologacao", "Homologação"),
                            ("osm", "OSM"),
                            ("manual", "Manual"),
                        ],
                        default="seed",
                        max_length=20,
                    ),
                ),
                ("ativo", models.BooleanField(default=True)),
                ("observacao", models.CharField(blank=True, default="", max_length=255)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Via de referência (Mogi)",
                "verbose_name_plural": "Vias de referência (Mogi)",
                "ordering": ["logradouro", "bairro"],
            },
        ),
    ]
