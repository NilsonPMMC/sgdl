import random
from django.core.management.base import BaseCommand
from django.db import transaction
from faker import Faker
from core.models import Usuario, Secretaria, Servico, Demanda
from django.utils import timezone # Importar timezone
from datetime import timedelta # Importar timedelta

# Define o número de itens a serem criados
NUM_VEREADORES = 13
NUM_PROTOCOLO = 2
NUM_USUARIOS_SECRETARIA = 3 # por secretaria
NUM_DEMANDAS = 250 # Total de demandas a serem criadas

# Limites geográficos de Mogi das Cruzes
MOGI_LAT_MIN = -23.67
MOGI_LAT_MAX = -23.37
MOGI_LON_MIN = -46.33
MOGI_LON_MAX = -46.03

class Command(BaseCommand):
    help = 'Popula o banco de dados com dados de teste (faker) realistas.'

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write('Limpando dados antigos...')
        Demanda.objects.all().delete()
        Servico.objects.all().delete()
        Usuario.objects.filter(is_superuser=False).delete() 
        Secretaria.objects.all().delete()

        fake = Faker('pt_BR')
        self.stdout.write('Criando novos dados realistas...')

        # --- 1. Criar Secretarias ---
        secretarias_map = {}
        nomes_secretarias = [
            'Serviços Urbanos e Zeladoria', 'Obras', 'Saúde',
            'Educação', 'Governo', 'Gabinete do Prefeito',
        ]
        for nome in nomes_secretarias:
            chave = nome.split(' ')[0].lower() 
            sec, _ = Secretaria.objects.get_or_create(nome=f"Secretaria Municipal de {nome}")
            secretarias_map[chave] = sec
        self.stdout.write(f'-> {len(secretarias_map)} secretarias criadas.')

        # --- 2. Criar Usuários ---
        # (Esta seção não muda)
        vereadores = []
        for i in range(NUM_VEREADORES):
            profile = fake.profile(fields=['name', 'username', 'mail'])
            nome_completo = profile['name'].split(' ')
            user = Usuario.objects.create_user(
                username=f"vereador_{i}_{profile['username']}", password='123',
                first_name=nome_completo[0], last_name=' '.join(nome_completo[1:]),
                email=profile['mail'], perfil='VEREADOR'
            )
            vereadores.append(user)
        
        for i in range(NUM_PROTOCOLO):
            profile = fake.profile(fields=['name', 'username', 'mail'])
            nome_completo = profile['name'].split(' ')
            Usuario.objects.create_user(
                username=f"protocolo_{i}", password='123',
                first_name=nome_completo[0], last_name=' '.join(nome_completo[1:]),
                email=profile['mail'], perfil='PROTOCOLO'
            )
        
        for chave_sec, sec in secretarias_map.items():
            for i in range(NUM_USUARIOS_SECRETARIA):
                profile = fake.profile(fields=['name', 'username', 'mail'])
                nome_completo = profile['name'].split(' ')
                Usuario.objects.create_user(
                    username=f"sec_{chave_sec}_{i}", password='123',
                    first_name=nome_completo[0], last_name=' '.join(nome_completo[1:]),
                    email=profile['mail'], perfil='SECRETARIA', secretaria=sec
                )
        self.stdout.write(f'-> {Usuario.objects.count()} usuários criados.')

        # --- 3. Criar Serviços Realistas ---
        # (Esta seção não muda)
        servicos_criados = []
        servicos_a_criar = [
            ('Tapa-buraco', 'obras', 'SERVIÇO'),
            ('Reparo de iluminação pública', 'serviços', 'SERVIÇO'),
            ('Poda de árvore em via pública', 'serviços', 'SERVIÇO'),
            ('Limpeza de bueiro', 'serviços', 'SERVIÇO'),
            ('Remoção de entulho', 'serviços', 'SERVIÇO'),
            ('Solicitação de vaga em creche', 'educação', 'ATENDIMENTO'),
            ('Matrícula escolar (Ensino Fundamental)', 'educação', 'ATENDIMENTO'),
            ('Agendamento de consulta (Clínico Geral)', 'saúde', 'ATENDIMENTO'),
            ('Agendamento de exame (Ex: Sangue)', 'saúde', 'ATENDIMENTO'),
            ('Solicitação de medicamentos (Farmácia Básica)', 'saúde', 'ATENDIMENTO'),
            ('Vistoria de terreno baldio (Dengue)', 'saúde', 'VISTORIA'),
            ('Sinalização de via (Placa/Pintura)', 'obras', 'IMPLANTAÇÃO'),
        ]
        for nome, chave_sec, tipo in servicos_a_criar:
            if chave_sec in secretarias_map:
                serv = Servico.objects.create(
                    nome=nome, tipo=tipo,
                    secretaria_responsavel=secretarias_map[chave_sec]
                )
                servicos_criados.append(serv)
        self.stdout.write(f'-> {len(servicos_criados)} serviços realistas criados.')

        # --- 4. Criar Demandas Realistas (COM DATAS VARIADAS) ---
        
        # --- ATUALIZAÇÃO AQUI ---
        # Define as datas de início e fim ANTES do loop
        # Isso é mais confiável do que usar 'start_date="-6m"'
        agora = timezone.now()
        data_inicio = agora - timedelta(days=180) # 6 meses atrás
        # ------------------------

        for i in range(NUM_DEMANDAS):
            autor = random.choice(vereadores)
            servico = random.choice(servicos_criados)
            
            # 1. Gera uma data de criação aleatória
            data_criacao_faker = fake.date_time_between(
                start_date=data_inicio, # <-- Usa a data calculada
                end_date=agora,         # <-- Usa a data calculada
                tzinfo=timezone.get_current_timezone()
            )
            
            # (Resto da lógica de status, etc...)
            status = random.choice(['RASCUNHO', 'AGUARDANDO_PROTOCOLO', 'PROTOCOLADO', 'EM_EXECUCAO', 'FINALIZADO'])
            data_limite_atraso = agora - timedelta(days=30)
            if data_criacao_faker < data_limite_atraso and status == 'FINALIZADO':
                status = 'EM_EXECUCAO'
            
            logradouro = fake.street_name()
            numero = fake.building_number()
            bairro = fake.bairro()
            cep = fake.postcode()
            
            # (Lógica de Título/Descrição)
            titulo = f"Solicitação Urgente: {servico.nome}"
            descricao = f"Prezados,\n\nVenho por meio deste solicitar a realização do serviço de '{servico.nome}'."

            if servico.nome == 'Tapa-buraco':
                titulo = f"Necessidade de tapa-buraco na {logradouro}, nº {numero}"
                descricao = f"Buraco de grande proporção na via (próximo ao nº {numero}, bairro {bairro}) está causando transtornos e risco de acidentes. Solicitamos reparo urgente."
            elif servico.nome == 'Reparo de iluminação pública':
                titulo = f"Poste sem luz na {logradouro} (Bairro {bairro})"
                descricao = f"O poste em frente ao número {numero} da {logradouro} (CEP {cep}) está com a lâmpada queimada há {random.randint(3, 20)} dias, deixando a rua escura e perigosa."
            elif servico.nome == 'Poda de árvore em via pública':
                titulo = f"Risco de queda de galhos na {logradouro}"
                descricao = f"A árvore na calçada da {logradouro}, {numero} está com galhos secos e muito grandes, apresentando risco iminente para pedestres e fiação elétrica."
            elif servico.nome == 'Solicitação de vaga em creche':
                titulo = f"Pedido de vaga em creche para {fake.name()}"
                descricao = f"Munícipe do bairro {bairro} necessita com urgência de vaga em creche (período integral) para a criança {fake.name()}, de {random.randint(1, 4)} anos de idade."
            elif servico.nome == 'Agendamento de consulta (Clínico Geral)':
                titulo = f"Dificuldade em agendar consulta no Posto de Saúde {bairro}"
                descricao = f"O munícipe {fake.name()} (CPF {fake.cpf()}) relata que não consegue agendamento de clínico geral no posto de saúde do bairro {bairro} há mais de {random.randint(2, 6)} semanas."
                
            demanda_data = {
                'autor': autor,
                'servico': servico,
                'titulo': titulo,
                'descricao': descricao,
                'cep': cep,
                'logradouro': logradouro,
                'numero': numero,
                'bairro': bairro,
                'latitude': fake.pyfloat(min_value=MOGI_LAT_MIN, max_value=MOGI_LAT_MAX, right_digits=6),
                'longitude': fake.pyfloat(min_value=MOGI_LON_MIN, max_value=MOGI_LON_MAX, right_digits=6),
                'status': status,
                'data_criacao': data_criacao_faker # <-- Passando a data aleatória
            }
            
            if status != 'RASCUNHO':
                demanda_data['protocolo_legislativo'] = f'OFICIO-2025-{i+1:04d}'
            
            if status in ['PROTOCOLADO', 'EM_EXECUCAO', 'FINALIZADO']:
                 demanda_data['secretaria_destino'] = servico.secretaria_responsavel
                 demanda_data['protocolo_executivo'] = f'2025-{i+1:04d}'
                 demanda_data['data_inicio_prazo'] = data_criacao_faker + timedelta(days=random.randint(1, 3))

            if status == 'FINALIZADO':
                start_date = demanda_data.get('data_inicio_prazo') or data_criacao_faker
                demanda_data['data_finalizacao'] = start_date + timedelta(days=random.randint(5, 45))

            Demanda.objects.create(**demanda_data)

        self.stdout.write(f'\n-> {Demanda.objects.count()} demandas realistas criadas.')
        self.stdout.write(self.style.SUCCESS('Banco de dados populado com sucesso!'))