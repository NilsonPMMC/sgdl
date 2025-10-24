# /var/www/sgdl/backend/core/signals.py

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone # Importar timezone
from .models import Demanda, Notificacao, Usuario

@receiver(pre_save, sender=Demanda)
def atualizar_dados_demanda_on_status_change(sender, instance, **kwargs):
    """
    Este sinal é executado ANTES de salvar.
    Usamos ele para capturar o status antigo e para definir
    a data de início do prazo.
    """
    status_antigo = None
    if instance.pk: # Se o objeto já existe (não é uma criação)
        try:
            status_antigo = Demanda.objects.get(pk=instance.pk).status
        except Demanda.DoesNotExist:
            pass # Deixa status_antigo como None
    
    # Armazena o status antigo na instância para o post_save usar
    instance._status_antigo = status_antigo

    # REGRA DE NEGÓCIO: Se o status está mudando PARA 'PROTOCOLADO',
    # e ele não era 'PROTOCOLADO' antes, iniciamos o relógio do prazo.
    if instance.status == 'PROTOCOLADO' and status_antigo != 'PROTOCOLADO':
        instance.data_inicio_prazo = timezone.now()
        print(f"-> SINAL PRE-SAVE: Demanda {instance.id} terá prazo iniciado em {instance.data_inicio_prazo}")


@receiver(post_save, sender=Demanda)
def notificar_eventos_demanda(sender, instance, created, **kwargs):
    """
    Este sinal é executado DEPOIS de salvar.
    Usamos ele apenas para ENVIAR NOTIFICAÇÕES.
    """
    print(f"--- SINAL POST-SAVE: Demanda ID {instance.id} | Created={created} | Status='{instance.status}' ---")
    
    link_correto = f'/demandas/detalhes/{instance.id}'
    status_antigo = getattr(instance, '_status_antigo', None) # Pega o status_antigo que o pre_save guardou

    # 1. FLUXO DE CRIAÇÃO (Rascunho)
    # Não faz nada, pois o 'envio' é uma atualização de status.
    if created:
        print("-> Fluxo de CRIAÇÃO (Rascunho). Sem notificação.")
        return

    # Se o status não mudou, não faz nada.
    if status_antigo is None or status_antigo == instance.status:
        print(f"-> Fluxo de ATUALIZAÇÃO, mas status não mudou (era '{status_antigo}'). Sem notificação.")
        return

    # --- SÓ EXECUTAMOS NOTIFICAÇÕES SE O STATUS MUDOU ---
    print(f"-> Fluxo de ATUALIZAÇÃO de status: DE '{status_antigo}' PARA '{instance.status}'")

    # 1. NOVO OFÍCIO: Vereador envia para o Protocolo (Status muda para AGUARDANDO_PROTOCOLO)
    # (Esta é a correção do bug original)
    if instance.status == 'AGUARDANDO_PROTOCOLO':
        print("-> Status 'AGUARDANDO_PROTOCOLO' detectado.")
        usuarios_protocolo = Usuario.objects.filter(perfil='PROTOCOLO')
        if not usuarios_protocolo.exists():
            print("-> ALERTA: Nenhum usuário com perfil 'PROTOCOLO' foi encontrado!")
            return

        print(f"-> Notificando {usuarios_protocolo.count()} usuário(s) do protocolo.")
        for usuario in usuarios_protocolo:
            Notificacao.objects.create(
                destinatario=usuario,
                mensagem=f'Novo ofício nº {instance.protocolo_legislativo} aguardando protocolo.',
                link=link_correto,
                tipo='NOVO_OFICIO'
            )

    # 2. OFÍCIO PROTOCOLADO: Protocolo despacha para Secretaria
    elif instance.status == 'PROTOCOLADO':
        print("-> Status 'PROTOCOLADO' detectado.")
        # Notifica o vereador autor
        Notificacao.objects.create(
            destinatario=instance.autor,
            mensagem=f'Seu ofício nº {instance.protocolo_legislativo} foi protocolado (nº {instance.protocolo_executivo}) e despachado.',
            link=link_correto,
            tipo='DESPACHO'
        )
        # Notifica os usuários da secretaria de destino
        for usuario_secretaria in instance.secretaria_destino.usuarios.all():
            Notificacao.objects.create(
                destinatario=usuario_secretaria,
                mensagem=f'Nova demanda (protocolo nº {instance.protocolo_executivo}) foi enviada para sua secretaria.',
                link=link_correto,
                tipo='DESPACHO'
            )

    # 3. DEMANDA INICIADA: Secretaria inicia a execução
    elif instance.status == 'EM_EXECUCAO': 
        print("-> Status 'EM_EXECUCAO' detectado.")
        usuarios_protocolo = Usuario.objects.filter(perfil='PROTOCOLO') 
        Notificacao.objects.create(
            destinatario=instance.autor,
            mensagem=f'A execução da sua demanda (protocolo nº {instance.protocolo_executivo}) foi iniciada.',
            link=link_correto,
            tipo='ATUALIZACAO'
        )
        for usuario in usuarios_protocolo:
            Notificacao.objects.create(
                destinatario=usuario,
                mensagem=f'A demanda nº {instance.protocolo_executivo} teve sua execução iniciada.',
                link=link_correto,
                tipo='ATUALIZACAO'
            )

    # 4. SOLICITAÇÃO DE TRANSFERÊNCIA: Secretaria devolve para o Protocolo
    elif instance.status == 'AGUARDANDO_TRANSFERENCIA': 
        print("-> Status 'AGUARDANDO_TRANSFERENCIA' detectado.")
        usuarios_protocolo = Usuario.objects.filter(perfil='PROTOCOLO') 
        for usuario in usuarios_protocolo:
            Notificacao.objects.create(
                destinatario=usuario,
                mensagem=f'Transferência solicitada para a demanda nº {instance.protocolo_executivo}.',
                link=link_correto,
                tipo='TRANSFERENCIA'
            )

    # 5. DEMANDA CONCLUÍDA: Secretaria finaliza a demanda
    elif instance.status == 'FINALIZADO': 
        print("-> Status 'FINALIZADO' detectado.")
        usuarios_protocolo = Usuario.objects.filter(perfil='PROTOCOLO') 
        Notificacao.objects.create(
            destinatario=instance.autor,
            mensagem=f'A sua demanda (protocolo nº {instance.protocolo_executivo}) foi concluída.',
            link=link_correto,
            tipo='CONCLUSAO'
        )
        for usuario in usuarios_protocolo:
            Notificacao.objects.create(
                destinatario=usuario,
                mensagem=f'A demanda nº {instance.protocolo_executivo} foi marcada como concluída.',
                link=link_correto,
                tipo='CONCLUSAO'
            )