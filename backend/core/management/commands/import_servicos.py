import csv
from django.core.management.base import BaseCommand
from core.models import Secretaria, Servico

class Command(BaseCommand):
    help = 'Importa serviços e secretarias de um arquivo CSV, incluindo o prazo.'

    def handle(self, *args, **kwargs):
        # Nome do novo arquivo CSV
        file_path = 'dados_iniciais.csv' 
        self.stdout.write(self.style.SUCCESS(f'Iniciando importação do arquivo {file_path}...'))

        # Contador para saber quantos serviços foram atualizados (já existiam)
        servicos_atualizados = 0 
        servicos_criados = 0
        secretarias_criadas = 0

        try:
            with open(file_path, mode='r', encoding='utf-8') as csv_file:
                reader = csv.DictReader(csv_file)
                
                if 'prazo' not in reader.fieldnames:
                     self.stdout.write(self.style.ERROR(f'Erro: A coluna "prazo" não foi encontrada no arquivo {file_path}.'))
                     return

                for row in reader:
                    tipo = row['tipo']
                    nome_servico = row['serviço']
                    nome_secretaria = row['secretaria']
                    prazo_str = row['prazo'] # Lê o prazo como string

                    # Valida se o prazo é um número inteiro
                    try:
                        prazo = int(prazo_str)
                    except ValueError:
                        self.stdout.write(self.style.WARNING(f'  - Aviso: Prazo inválido ("{prazo_str}") para o serviço "{nome_servico}". Usando NULL.'))
                        prazo = None # Define como nulo se não for um número

                    # Cria ou busca a Secretaria
                    secretaria, created = Secretaria.objects.get_or_create(
                        nome=nome_secretaria
                    )
                    if created:
                        secretarias_criadas += 1
                        self.stdout.write(f'  -> Secretaria criada: {secretaria.nome}')

                    # Cria ou atualiza o Serviço
                    servico, created = Servico.objects.update_or_create(
                        nome=nome_servico,
                        defaults={
                            'tipo': tipo.upper(),
                            'secretaria_responsavel': secretaria,
                            'prazo': prazo # Adiciona o prazo aqui
                        }
                    )
                    
                    if created:
                        servicos_criados += 1
                    else:
                        # Se não foi criado, significa que foi atualizado
                        servicos_atualizados += 1 

                self.stdout.write(self.style.SUCCESS(f'\nImportação concluída!'))
                self.stdout.write(self.style.SUCCESS(f'{secretarias_criadas} novas secretarias foram criadas.'))
                self.stdout.write(self.style.SUCCESS(f'{servicos_criados} novos serviços foram criados.'))
                self.stdout.write(self.style.SUCCESS(f'{servicos_atualizados} serviços existentes foram atualizados (com nome ou prazo).'))

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'Erro: O arquivo {file_path} não foi encontrado na pasta backend/.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ocorreu um erro inesperado: {e}'))
