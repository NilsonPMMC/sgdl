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

        # Filtros: (Esta consulta já estava correta)
        demandas_para_verificar = Demanda.objects.filter(
            status__in=status_em_andamento,
            notificacao_atraso_enviada=False,
            servico__prazo__isnull=False,
            data_inicio_prazo__isnull=False
        ).select_related('servico', 'secretaria_destino') # Boa otimização!

        self.stdout.write(f"Encontradas {demandas_para_verificar.count()} demandas para verificar.")

        # --- CORREÇÃO: Otimizar busca por usuários ---
            
        # 1. Usuários globais (Protocolo, Gestor)
        usuarios_protocolo = list(Usuario.objects.filter(perfil='PROTOCOLO'))
        usuarios_gestor = list(Usuario.objects.filter(perfil='GESTOR'))

        # 2. Usuários de Secretaria (agrupados por ID da secretaria para NUNCA consultar no loop)
        usuarios_secretaria_por_id = {}
        
        # Filtra usuários que SÃO de secretaria E têm uma secretaria associada
        qs_secretaria = Usuario.objects.filter(
            perfil='SECRETARIA', 
            secretaria__isnull=False
        )
        
        for usuario in qs_secretaria:
            # Se o ID da secretaria ainda não é uma chave, cria uma lista vazia
            if usuario.secretaria_id not in usuarios_secretaria_por_id:
                usuarios_secretaria_por_id[usuario.secretaria_id] = []
            # Adiciona o usuário à lista daquela secretaria
            usuarios_secretaria_por_id[usuario.secretaria_id].append(usuario)
        
        self.stdout.write(f"Encontrados {len(usuarios_protocolo)} usuários 'Protocolo'.")
        self.stdout.write(f"Encontrados {len(usuarios_gestor)} usuários 'Gestor'.")
        self.stdout.write(f"Mapeados usuários para {len(usuarios_secretaria_por_id)} secretarias.")
        # --- FIM DA CORREÇÃO ---

        demandas_atrasadas_ids = []
        notificacoes_para_criar = []

        for demanda in demandas_para_verificar:
            prazo_dias = demanda.servico.prazo
            
            # Garante que estamos comparando 'date' com 'date'
            data_inicio = demanda.data_inicio_prazo.date()
            data_vencimento = data_inicio + timedelta(days=prazo_dias)

            if hoje > data_vencimento:
                # A DEMANDA ESTÁ ATRASADA!
                demandas_atrasadas_ids.append(demanda.id)
                protocolo = demanda.protocolo_executivo or demanda.id
                link = f'/demandas/detalhes/{demanda.id}'
                msg = f'Alerta: A demanda nº {protocolo} ({demanda.titulo}) está atrasada.'

                # --- CORREÇÃO: Usar o lookup de secretarias ---
                # 1. Notificar Secretaria responsável
                if demanda.secretaria_destino_id:
                    # Pega a lista de usuários daquele ID, ou uma lista vazia se não houver
                    usuarios_da_secretaria = usuarios_secretaria_por_id.get(demanda.secretaria_destino_id, [])
                    
                    for usuario in usuarios_da_secretaria:
                        notificacoes_para_criar.append(
                            Notificacao(destinatario=usuario, mensagem=msg, link=link, tipo='ATRASO')
                        )
                # --- FIM DA CORREÇÃO ---
                
                # 2. Notificar Protocolo (já estava correto)
                for usuario in usuarios_protocolo:
                    notificacoes_para_criar.append(
                        Notificacao(destinatario=usuario, mensagem=msg, link=link, tipo='ATRASO')
                    )

                # 3. Notificar Gestor (já estava correto)
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