import csv
from django.core.management.base import BaseCommand
from core.models import Secretaria, Servico

class Command(BaseCommand):
    help = 'Importa serviços e secretarias de um arquivo CSV'

    def handle(self, *args, **kwargs):
        file_path = 'dados_iniciais.csv'
        self.stdout.write(self.style.SUCCESS(f'Iniciando importação do arquivo {file_path}...'))

        with open(file_path, mode='r', encoding='utf-8') as csv_file:
            reader = csv.DictReader(csv_file)
            
            servicos_criados = 0
            secretarias_criadas = 0

            for row in reader:
                tipo = row['tipo']
                nome_servico = row['serviço']
                nome_secretaria = row['secretaria']

                # Cria a Secretaria se ela não existir, ou apenas a busca se já existir
                secretaria, created = Secretaria.objects.get_or_create(
                    nome=nome_secretaria
                )
                if created:
                    secretarias_criadas += 1
                    self.stdout.write(f'  -> Secretaria criada: {secretaria.nome}')

                # Cria ou atualiza o Serviço, garantindo que não haja duplicatas
                servico, created = Servico.objects.update_or_create(
                    nome=nome_servico,
                    defaults={
                        'tipo': tipo.upper(),
                        'secretaria_responsavel': secretaria
                    }
                )
                if created:
                    servicos_criados += 1

            self.stdout.write(self.style.SUCCESS(f'\nImportação concluída!'))
            self.stdout.write(self.style.SUCCESS(f'{secretarias_criadas} novas secretarias foram criadas.'))
            self.stdout.write(self.style.SUCCESS(f'{servicos_criados} novos serviços foram criados.'))