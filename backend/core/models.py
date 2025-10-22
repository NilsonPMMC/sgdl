# /var/www/sgdl/backend/core/models.py

import logging
from django.db import models
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
from django.conf import settings
from django.contrib.auth.models import AbstractUser

class Secretaria(models.Model):
    nome = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.nome
    
class Usuario(AbstractUser):
    PERFIL_CHOICES = (
        ('VEREADOR', 'Vereador'),
        ('PROTOCOLO', 'Protocolo'),
        ('SECRETARIA', 'Secretaria'),
        ('GESTOR', 'Gestor'),
    )
    perfil = models.CharField(max_length=20, choices=PERFIL_CHOICES, blank=True, null=True)
    secretaria = models.ForeignKey(Secretaria, on_delete=models.SET_NULL, null=True, blank=True, related_name='usuarios')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    cargo = models.CharField(max_length=100, blank=True, null=True)
    telefone = models.CharField(max_length=20, blank=True, null=True)
    ramal = models.CharField(max_length=10, blank=True, null=True)
    assinatura = models.TextField(blank=True, null=True, help_text="Texto que aparecerá como assinatura. Ex: Nome Completo, Cargo, Secretaria.")

class Servico(models.Model):
    TIPO_CHOICES = [
        ('EVENTO', 'Evento'),
        ('ATENDIMENTO', 'Atendimento'),
        ('SERVIÇO', 'Serviço'),
        ('VISTORIA', 'Vistoria'),
        ('IMPLANTAÇÃO', 'Implantação'),
    ]
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='SERVIÇO')

    nome = models.CharField(max_length=255)
    secretaria_responsavel = models.ForeignKey(Secretaria, on_delete=models.PROTECT, related_name='servicos')

    def __str__(self):
        return self.nome
    
logger = logging.getLogger(__name__)

class Demanda(models.Model):
    STATUS_CHOICES = (
        ('RASCUNHO', 'Rascunho'),
        ('AGUARDANDO_PROTOCOLO', 'Aguardando Protocolo'),
        ('PROTOCOLADO', 'Protocolado e Despachado'),
        ('EM_EXECUCAO', 'Em Execução'),
        ('FINALIZADO', 'Finalizado'),
        ('CANCELADO', 'Cancelado'),
        ('AGUARDANDO_TRANSFERENCIA', 'Aguardando Transferência'),
    )

    protocolo_legislativo = models.CharField(max_length=20, unique=True, blank=True, null=True)
    protocolo_executivo = models.CharField(max_length=20, unique=True, blank=True, null=True)
    titulo = models.CharField(max_length=200)
    descricao = models.TextField()
    cep = models.CharField(max_length=10, blank=True, null=True)
    logradouro = models.CharField(max_length=255, blank=True, null=True)
    numero = models.CharField(max_length=20, blank=True, null=True)
    complemento = models.CharField(max_length=100, blank=True, null=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    bairro = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='RASCUNHO')
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_finalizacao = models.DateTimeField(blank=True, null=True)
    autor = models.ForeignKey('Usuario', on_delete=models.PROTECT, related_name='demandas_criadas')
    servico = models.ForeignKey(Servico, on_delete=models.PROTECT, related_name='demandas')
    secretaria_destino = models.ForeignKey(Secretaria, on_delete=models.PROTECT, related_name='demandas_recebidas', blank=True, null=True)

    def save(self, *args, **kwargs):              
        super().save(*args, **kwargs)
    
    def __str__(self):
        protocolo = self.protocolo_executivo or self.protocolo_legislativo or "Rascunho"
        return f'[{protocolo}] {self.titulo}'

class Anexo(models.Model):
    demanda = models.ForeignKey(Demanda, on_delete=models.CASCADE, related_name='anexos')
    arquivo = models.FileField(upload_to='anexos/%Y/%m/%d/')
    descricao = models.CharField(max_length=100, blank=True)
    data_upload = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.arquivo.name
    
class Tramitacao(models.Model):
    TIPO_CHOICES = [
        ('ENVIO_OFICIAL', 'Envio Oficial'),
        ('DESPACHO', 'Despacho para Secretaria'),
        ('STATUS_UPDATE', 'Atualização de Status'),
        ('COMENTARIO', 'Comentário'),
        ('ANALISE_TECNICA', 'Análise Técnica'),
        ('ATRASO', 'Registro de Atraso'),
        ('PROGRAMACAO', 'Programação do Serviço'),
        ('CONCLUSAO', 'Conclusão do Serviço'),
        ('TRANSFERENCIA', 'Transferência de Setor/Secretaria'), 
    ]

    demanda = models.ForeignKey(Demanda, on_delete=models.CASCADE, related_name='tramitacoes')
    responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    descricao = models.TextField(help_text="Descrição detalhada do passo, justificativa do atraso, etc.")
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.demanda.id} - {self.get_tipo_display()}'


class AnexoTramitacao(models.Model):
    tramitacao = models.ForeignKey(Tramitacao, on_delete=models.CASCADE, related_name='anexos')
    arquivo = models.FileField(upload_to='anexos_tramitacao/%Y/%m/%d/')

    def __str__(self):
        return self.arquivo.name
    
class Notificacao(models.Model):
    destinatario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notificacoes')
    mensagem = models.TextField()
    lida = models.BooleanField(default=False)
    data_criacao = models.DateTimeField(auto_now_add=True)
    link = models.CharField(max_length=255, blank=True, null=True) # Para redirecionar o usuário

    def __str__(self):
        return f'Notificação para {self.destinatario.username}: {self.mensagem[:20]}'

    class Meta:
        ordering = ['-data_criacao']