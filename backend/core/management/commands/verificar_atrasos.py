# /var/www/sgdl/backend/core/management/commands/verificar_atrasos.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from core.models import Demanda, Usuario, Notificacao
from django.db.models import Q, F

class Command(BaseCommand):
    help = 'Verifica demandas atrasadas e envia notificações para Gestores, Protocolo e Secretarias.'

    def handle(self, *args, **options):
        hoje = timezone.now().date()
        self.stdout.write(f"--- {hoje}: Iniciando verificação de demandas atrasadas ---")

        # Status que consideramos "em andamento"
        status_em_andamento = ['PROTOCOLADO', 'EM_EXECUCAO', 'AGUARDANDO_TRANSFERENCIA']

        # Filtros:
        # 1. Status deve ser um dos "em andamento"
        # 2. A notificação de atraso ainda não foi enviada
        # 3. O serviço associado TEM um prazo definido
        # 4. A data de início do prazo ESTÁ definida
        demandas_para_verificar = Demanda.objects.filter(
            status__in=status_em_andamento,
            notificacao_atraso_enviada=False,
            servico__prazo__isnull=False,
            data_inicio_prazo__isnull=False
        ).select_related('servico', 'secretaria_destino')

        self.stdout.write(f"Encontradas {demandas_para_verificar.count()} demandas para verificar.")

        usuarios_protocolo = list(Usuario.objects.filter(perfil='PROTOCOLO'))
        usuarios_gestor = list(Usuario.objects.filter(perfil='GESTOR'))
        
        demandas_atrasadas_ids = []
        notificacoes_para_criar = []

        for demanda in demandas_para_verificar:
            prazo_dias = demanda.servico.prazo
            data_inicio = demanda.data_inicio_prazo.date()
            data_vencimento = data_inicio + timedelta(days=prazo_dias)

            if hoje > data_vencimento:
                # A DEMANDA ESTÁ ATRASADA!
                demandas_atrasadas_ids.append(demanda.id)
                protocolo = demanda.protocolo_executivo or demanda.id
                link = f'/demandas/detalhes/{demanda.id}'
                msg = f'Alerta: A demanda nº {protocolo} ({demanda.titulo}) está atrasada.'

                # 1. Notificar Secretaria responsável
                for usuario in usuarios_secretaria:
                    notificacoes_para_criar.append(
                        Notificacao(destinatario=usuario, mensagem=msg, link=link, tipo='ATRASO')
                    )
                
                # 2. Notificar Protocolo
                for usuario in usuarios_protocolo:
                    notificacoes_para_criar.append(
                        Notificacao(destinatario=usuario, mensagem=msg, link=link, tipo='ATRASO')
                    )

                # 3. Notificar Gestor
                for usuario in usuarios_gestor:
                    notificacoes_para_criar.append(
                        Notificacao(destinatario=usuario, mensagem=msg, link=link, tipo='ATRASO')
                    )

        # Criar todas as notificações de uma vez (melhor performance)
        if notificacoes_para_criar:
            Notificacao.objects.bulk_create(notificacoes_para_criar)
            self.stdout.write(f"Criadas {len(notificacoes_para_criar)} notificações.")

        # Marcar as demandas como "notificadas" para não enviar de novo
        if demandas_atrasadas_ids:
            Demanda.objects.filter(id__in=demandas_atrasadas_ids).update(notificacao_atraso_enviada=True)
            self.stdout.write(f"Marcadas {len(demandas_atrasadas_ids)} demandas como 'notificação de atraso enviada'.")

        self.stdout.write(self.style.SUCCESS("--- Verificação de atrasos concluída ---"))