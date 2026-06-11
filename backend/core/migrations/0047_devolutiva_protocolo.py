from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0046_unidade_administrativa"),
    ]

    operations = [
        migrations.AlterField(
            model_name="demanda",
            name="status",
            field=models.CharField(
                choices=[
                    ("RASCUNHO", "Rascunho"),
                    ("AGUARDANDO_PROTOCOLO", "Aguardando Protocolo"),
                    ("PROTOCOLADO", "Protocolado e Despachado"),
                    ("EM_EXECUCAO", "Em Execução"),
                    (
                        "AGUARDANDO_DEVOLUTIVA_PROTOCOLO",
                        "Aguardando devolutiva (Protocolo)",
                    ),
                    ("DEVOLVIDO_VEREADOR", "Devolutiva enviada ao vereador"),
                    ("FINALIZADO", "Finalizado"),
                    ("CANCELADO", "Cancelado"),
                    ("AGUARDANDO_TRANSFERENCIA", "Aguardando Transferência"),
                ],
                default="RASCUNHO",
                max_length=40,
            ),
        ),
        migrations.AlterField(
            model_name="notificacao",
            name="tipo",
            field=models.CharField(
                choices=[
                    ("NOVO_OFICIO", "Novo Ofício"),
                    ("DESPACHO", "Despacho"),
                    ("ATUALIZACAO", "Atualização"),
                    ("TRANSFERENCIA", "Transferência"),
                    ("CONCLUSAO", "Conclusão"),
                    ("DEVOLUTIVA", "Devolutiva"),
                    ("ATRASO", "Atraso"),
                ],
                default="ATUALIZACAO",
                max_length=20,
            ),
        ),
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
                    ("ATRASO", "Registro de Atraso"),
                    ("PROGRAMACAO", "Programação do Serviço"),
                    ("CONCLUSAO", "Conclusão do Serviço"),
                    ("TRANSFERENCIA", "Transferência de Setor/Secretaria"),
                    ("ENCAMINHAMENTO_SETOR", "Encaminhamento entre setores"),
                    ("SOLICITACAO_DEVOLUTIVA", "Solicitação de devolutiva"),
                    ("DEVOLUTIVA_PROTOCOLO", "Devolutiva ao vereador"),
                    ("ENCERRAMENTO_DEVOLUTIVA", "Encerramento legislativo"),
                ],
                max_length=24,
            ),
        ),
    ]
