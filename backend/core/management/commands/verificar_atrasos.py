# /var/www/sgdl/backend/core/management/commands/verificar_atrasos.py

from django.core.management.base import BaseCommand

from core.services.atraso_demanda_service import AtrasoDemandaService


class Command(BaseCommand):
    help = "Verifica demandas atrasadas e envia notificações para Gestores, Protocolo e Secretarias."

    def handle(self, *args, **options):
        self.stdout.write("--- Iniciando verificação de demandas atrasadas ---")
        resultado = AtrasoDemandaService().executar()
        self.stdout.write(
            f"Verificadas: {resultado.demandas_verificadas}; "
            f"atrasadas: {resultado.demandas_atrasadas}; "
            f"notificações: {resultado.notificacoes_criadas}."
        )
        self.stdout.write(self.style.SUCCESS("--- Verificação de atrasos concluída ---"))
