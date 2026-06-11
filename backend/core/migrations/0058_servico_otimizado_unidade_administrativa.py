from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0057_configuracao_carta_prazo_demanda"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicootimizado",
            name="unidade_administrativa",
            field=models.ForeignKey(
                blank=True,
                help_text="Setor operacional sugerido para despacho (C2).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="servicos_otimizados",
                to="core.unidadeadministrativa",
            ),
        ),
    ]
