from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0065_assinatura_conclusao_final"),
    ]

    operations = [
        migrations.AddField(
            model_name="demanda",
            name="inicio_execucao_automatico",
            field=models.BooleanField(
                default=False,
                help_text="True quando o Protocolo inicia execução automaticamente (C3/C5).",
            ),
        ),
        migrations.AddField(
            model_name="demanda",
            name="modo_entrada_processo",
            field=models.CharField(
                blank=True,
                default="",
                help_text="OFICIO_UNICO ou CLUSTER_SUPER_OS — definido no despacho.",
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="demanda",
            name="orquestrador_conclusao",
            field=models.CharField(
                blank=True,
                default="",
                help_text="SECRETARIA_LIDER ou PROTOCOLO — quem conduz a operação até o gate.",
                max_length=24,
            ),
        ),
    ]
