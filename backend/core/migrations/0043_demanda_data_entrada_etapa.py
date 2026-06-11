from django.db import migrations, models
from django.utils import timezone


def preencher_data_entrada_etapa(apps, schema_editor):
    Demanda = apps.get_model("core", "Demanda")
    for demanda in Demanda.objects.iterator():
        if demanda.data_inicio_prazo:
            etapa = demanda.data_inicio_prazo
        else:
            etapa = demanda.data_criacao or timezone.now()
        Demanda.objects.filter(pk=demanda.pk).update(data_entrada_etapa=etapa)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0042_cluster_sinapse_servico"),
    ]

    operations = [
        migrations.AddField(
            model_name="demanda",
            name="data_entrada_etapa",
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text="Momento em que a demanda entrou no status/etapa atual (SLA visual do despacho).",
            ),
        ),
        migrations.RunPython(preencher_data_entrada_etapa, migrations.RunPython.noop),
    ]
