# Generated manually — Gestão Operacional Portal dos Vereadores

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0063_assinatura_pending_acao"),
    ]

    operations = [
        migrations.AddField(
            model_name="demanda",
            name="fluxo_roteamento",
            field=models.CharField(
                blank=True,
                default="",
                help_text="FLUXO_DIRETO ou FLUXO_TRANSVERSAL — definido na triagem do Protocolo.",
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="demanda",
            name="sinapse_orgao_lider_id",
            field=models.BigIntegerField(
                blank=True,
                help_text="Órgão líder do processo (carta ou 1ª secretaria na triagem).",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="tramitacao",
            name="metadata",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Payload estruturado do evento (event sourcing operacional).",
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
                    ("TRIAGEM_PROTOCOLO", "Triagem do Protocolo"),
                    ("RECUSA_PROTOCOLO", "Recusa do Protocolo ao vereador"),
                    ("CONCLUSAO_TECNICA", "Conclusão técnica (fluxo direto)"),
                    ("CONCLUSAO_PARCIAL", "Conclusão parcial (fluxo transversal)"),
                    ("DEVOLUCAO", "Devolução ao Protocolo"),
                    ("CONCLUSAO_FINAL", "Conclusão final (Protocolo)"),
                ],
                max_length=24,
            ),
        ),
    ]
