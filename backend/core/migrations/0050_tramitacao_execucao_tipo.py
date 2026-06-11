# Generated manually — tipo EXECUCAO em tramitações operacionais.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0049_remove_campos_referencia_externa"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tramitacao",
            name="tipo",
            field=models.CharField(
                choices=[
                    ("ENVIO_OFICIAL", "Envio Oficial"),
                    ("DESPACHO", "Despacho para Secretaria"),
                    ("STATUS_UPDATE", "Atualização de Status"),
                    ("COMENTARIO", "Comentário"),
                    ("ANALISE_TECNICA", "Análise Técnica"),
                    ("EXECUCAO", "Execução"),
                    ("ATRASO", "Registro de Atraso"),
                    ("PROGRAMACAO", "Programação do Serviço"),
                    ("CONCLUSAO", "Conclusão do Serviço"),
                    ("TRANSFERENCIA", "Transferência de Setor/Secretaria"),
                    ("ENCAMINHAMENTO_SETOR", "Encaminhamento entre setores"),
                    ("SOLICITACAO_DEVOLUTIVA", "Solicitação de devolutiva"),
                    ("DEVOLUTIVA_PROTOCOLO", "Devolutiva ao vereador"),
                    ("ENCERRAMENTO_DEVOLUTIVA", "Encerramento legislativo"),
                    ("CIENCIA_VEREADOR", "Ciência do vereador"),
                ],
                max_length=24,
            ),
        ),
    ]
