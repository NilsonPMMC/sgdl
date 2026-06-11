from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def marcar_rascunhos_pendentes(apps, schema_editor):
    Demanda = apps.get_model("core", "Demanda")
    Demanda.objects.filter(status="RASCUNHO").update(revisao_assessor_status="PENDENTE")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0054_configuracao_oficio_cabecalho_layout"),
    ]

    operations = [
        migrations.AlterField(
            model_name="usuario",
            name="perfil",
            field=models.CharField(
                blank=True,
                choices=[
                    ("VEREADOR", "Vereador"),
                    ("ASSESSOR", "Assessor Legislativo"),
                    ("PROTOCOLO", "Protocolo"),
                    ("SECRETARIA", "Secretaria"),
                    ("GESTOR", "Gestor"),
                ],
                max_length=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="demanda",
            name="revisao_assessor_status",
            field=models.CharField(
                choices=[
                    ("PENDENTE", "Aguardando revisão"),
                    ("REVISADO", "Revisado pelo assessor"),
                    ("DEVOLVIDO", "Devolvido ao vereador"),
                ],
                default="PENDENTE",
                help_text="Controle de revisão de texto antes do envio oficial.",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="demanda",
            name="revisao_assessor_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="demanda",
            name="revisao_assessor_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="demandas_revisadas_assessor",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="demanda",
            name="revisao_assessor_observacao",
            field=models.TextField(
                blank=True,
                help_text="Observação do assessor (ex.: motivo de devolutiva).",
            ),
        ),
        migrations.RunPython(marcar_rascunhos_pendentes, migrations.RunPython.noop),
    ]
