from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0037_usuario_assinatura_imagem"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="clusterexecucao",
            name="protocolo_super_os",
            field=models.CharField(
                blank=True,
                help_text="Referência interna do lote (ex.: SUPER-2026-0001).",
                max_length=30,
                null=True,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name="clusterexecucao",
            name="numero_externo",
            field=models.CharField(
                blank=True,
                help_text="Processo único no SEI/1Doc para o agrupamento.",
                max_length=100,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="clusterexecucao",
            name="link_externo",
            field=models.URLField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name="clusterexecucao",
            name="despachado_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="clusterexecucao",
            name="despachado_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="clusters_despachados",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
