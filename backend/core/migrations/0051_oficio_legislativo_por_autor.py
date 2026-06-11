from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0050_tramitacao_execucao_tipo"),
    ]

    operations = [
        migrations.AlterField(
            model_name="demanda",
            name="protocolo_legislativo",
            field=models.CharField(
                blank=True,
                help_text="Nº do ofício (OFICIO-AAAA-NNNN), sequência anual por autor.",
                max_length=20,
                null=True,
            ),
        ),
        migrations.AddConstraint(
            model_name="demanda",
            constraint=models.UniqueConstraint(
                condition=models.Q(("protocolo_legislativo__isnull", False)),
                fields=("autor", "protocolo_legislativo"),
                name="unique_oficio_legislativo_por_autor",
            ),
        ),
    ]
