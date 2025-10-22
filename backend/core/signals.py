from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Demanda, Notificacao, Usuario

@receiver(post_save, sender=Demanda)
def notificar_eventos_demanda(sender, instance, created, **kwargs):
    # Usamos print para depurar o que está acontecendo no console do Django
    print(f"--- SINAL DISPARADO: Demanda ID {instance.id} | Created={created} | Status='{instance.status}' ---")

    link_correto = f'/demandas/detalhes/{instance.id}'

    # 1. NOVO OFÍCIO: Vereador envia para o Protocolo
    # O status inicial quando o vereador envia é 'AGUARDANDO_PROTOCOLO'
    if instance.status == 'AGUARDANDO_PROTOCOLO' and created:
        print("-> Fluxo de CRIAÇÃO / AGUARDANDO_PROTOCOLO detectado.")
        usuarios_protocolo = Usuario.objects.filter(perfil='PROTOCOLO') # CORRIGIDO: Maiúsculas
        if not usuarios_protocolo.exists():
            print("-> ALERTA: Nenhum usuário com perfil 'PROTOCOLO' foi encontrado!")
            return

        print(f"-> Notificando {usuarios_protocolo.count()} usuário(s) do protocolo.")
        for usuario in usuarios_protocolo:
            Notificacao.objects.create(
                destinatario=usuario,
                mensagem=f'Novo ofício nº {instance.protocolo_legislativo} aguardando protocolo.',
                link=link_correto
            )
        return

    # --- Lógica para ATUALIZAÇÕES de status ---
    print("-> Fluxo de ATUALIZAÇÃO detectado.")

    # 2. OFÍCIO PROTOCOLADO: Protocolo despacha para Secretaria
    if instance.status == 'PROTOCOLADO': # CORRIGIDO: Maiúsculas
        print("-> Status 'PROTOCOLADO' detectado.")
        # Notifica o vereador autor
        Notificacao.objects.create(
            destinatario=instance.autor,
            mensagem=f'Seu ofício nº {instance.protocolo_legislativo} foi protocolado (nº {instance.protocolo_executivo}) e despachado.',
            link=link_correto
        )
        # Notifica os usuários da secretaria de destino
        for usuario_secretaria in instance.secretaria_destino.usuarios.all():
            Notificacao.objects.create(
                destinatario=usuario_secretaria,
                mensagem=f'Nova demanda (protocolo nº {instance.protocolo_executivo}) foi enviada para sua secretaria.',
                link=link_correto
            )

    # 3. DEMANDA INICIADA: Secretaria inicia a execução
    elif instance.status == 'EM_EXECUCAO': # CORRIGIDO: Maiúsculas
        print("-> Status 'EM_EXECUCAO' detectado.")
        usuarios_protocolo = Usuario.objects.filter(perfil='PROTOCOLO') # CORRIGIDO: Maiúsculas
        Notificacao.objects.create(
            destinatario=instance.autor,
            mensagem=f'A execução da sua demanda (protocolo nº {instance.protocolo_executivo}) foi iniciada.',
            link=link_correto
        )
        for usuario in usuarios_protocolo:
            Notificacao.objects.create(
                destinatario=usuario,
                mensagem=f'A demanda nº {instance.protocolo_executivo} teve sua execução iniciada.',
                link=link_correto
            )

    # 4. SOLICITAÇÃO DE TRANSFERÊNCIA: Secretaria devolve para o Protocolo
    elif instance.status == 'AGUARDANDO_TRANSFERENCIA': # CORRIGIDO: Nome e Maiúsculas
        print("-> Status 'AGUARDANDO_TRANSFERENCIA' detectado.")
        usuarios_protocolo = Usuario.objects.filter(perfil='PROTOCOLO') # CORRIGIDO: Maiúsculas
        for usuario in usuarios_protocolo:
            Notificacao.objects.create(
                destinatario=usuario,
                mensagem=f'Transferência solicitada para a demanda nº {instance.protocolo_executivo}.',
                link=link_correto
            )

    # 5. DEMANDA CONCLUÍDA: Secretaria finaliza a demanda
    elif instance.status == 'FINALIZADO': # CORRIGIDO: Nome e Maiúsculas
        print("-> Status 'FINALIZADO' detectado.")
        usuarios_protocolo = Usuario.objects.filter(perfil='PROTOCOLO') # CORRIGIDO: Maiúsculas
        Notificacao.objects.create(
            destinatario=instance.autor,
            mensagem=f'A sua demanda (protocolo nº {instance.protocolo_executivo}) foi concluída.',
            link=link_correto
        )
        for usuario in usuarios_protocolo:
            Notificacao.objects.create(
                destinatario=usuario,
                mensagem=f'A demanda nº {instance.protocolo_executivo} foi marcada como concluída.',
                link=link_correto
            )