# /var/www/sgdl/backend/core/serializers.py

from datetime import datetime, timedelta
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import serializers
from .models import Demanda, Servico, Secretaria, Usuario, Anexo, Tramitacao, AnexoTramitacao, Notificacao
from django.conf import settings

class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer para o perfil do usuário.
    Permite visualizar e atualizar os campos de perfil.
    """
    class Meta:
        model = Usuario
        # Adicionados todos os novos campos aqui
        fields = [
            'id', 'username', 'first_name', 'last_name', 'email', 
            'avatar', 'cargo', 'telefone', 'ramal', 
            'assinatura', 'perfil', 'secretaria'
        ]
        # Campos que o usuário não pode editar por conta própria
        read_only_fields = ['username', 'perfil', 'secretaria']

class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer para a troca de senha.
    """
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = [
            'id', 'username', 'first_name', 'last_name', 
            'perfil', 'secretaria', 'avatar', 
            'cargo', 'telefone', 'ramal', 'assinatura'
        ]

class SecretariaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Secretaria
        fields = ['id', 'nome']

class ServicoSerializer(serializers.ModelSerializer):
    secretaria_responsavel = SecretariaSerializer(read_only=True)
    
    class Meta:
        model = Servico
        fields = ['id', 'nome', 'tipo', 'secretaria_responsavel']

class AnexoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Anexo
        fields = '__all__'
        read_only_fields = ['id', 'data_upload']

class AnexoTramitacaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnexoTramitacao
        fields = ['id', 'arquivo']

class TramitacaoSerializer(serializers.ModelSerializer):
    responsavel = UsuarioSerializer(read_only=True)
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    anexos = AnexoTramitacaoSerializer(many=True, read_only=True)
    arquivos_anexos = serializers.ListField(
        child=serializers.FileField(), write_only=True, required=False
    )

    class Meta:
        model = Tramitacao
        fields = [
            'id', 
            'demanda', 
            'responsavel',
            'tipo',
            'tipo_display',
            'descricao', 
            'timestamp', 
            'anexos', 
            'arquivos_anexos'
        ]
        
        extra_kwargs = {
            'demanda': {'write_only': True},
        }

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Customiza o serializer de token para incluir o campo 'remember_me'
    e alterar o tempo de vida do refresh token.
    """
    remember_me = serializers.BooleanField(write_only=True, required=False)

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        return token

    def validate(self, attrs):
        # Chama o 'validate' original
        data = super().validate(attrs)
        
        remember_me = self.initial_data.get('remember_me', False)
        
        print(f"--- DEBUG: 'remember_me' recebido = {remember_me} ---")
        
        if remember_me:
            print("--- DEBUG: 'remember_me' é TRUE. Definindo token para 30 dias. ---")
            refresh = self.get_token(self.user)
            refresh.set_exp(
                lifetime=settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME_REMEMBER_ME']
            )
            data['refresh'] = str(refresh)
        else:
            print("--- DEBUG: 'remember_me' é FALSE. Usando token padrão (1 dia). ---")
            
        return data
    
class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Serializer para validar os dados da tela de confirmação de 
    redefinição de senha.
    """
    uidb64 = serializers.CharField(required=True)
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, write_only=True)
    
class DemandaSerializer(serializers.ModelSerializer):
    autor = UsuarioSerializer(read_only=True)
    servico = ServicoSerializer(read_only=True)
    secretaria_destino = SecretariaSerializer(read_only=True)
    anexos = AnexoSerializer(many=True, read_only=True)
    tramitacoes = TramitacaoSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    servico_id = serializers.PrimaryKeyRelatedField(queryset=Servico.objects.all(), source='servico', write_only=True)

    class Meta:
        model = Demanda
        fields = [
            'id', 'protocolo_legislativo', 'protocolo_executivo', 'titulo', 'descricao', 
            'cep', 'logradouro', 'numero', 'complemento', 'bairro', 'latitude', 'longitude',
            'status', 'status_display', 'data_criacao', 'autor', 'servico', 'secretaria_destino',
            'servico_id',
            'anexos', 'tramitacoes',
            'numero_externo', 
            'link_externo'
        ]
        read_only_fields = [
            'protocolo_legislativo', 'protocolo_executivo', 'status', 'status_display',
            'data_criacao', 'secretaria_destino', 'anexos', 'tramitacoes', 'autor',
            'numero_externo', 
            'link_externo'
        ]

class NotificacaoSerializer(serializers.ModelSerializer):
    """
    Serializer para o modelo Notificacao.
    """
    class Meta:
        model = Notificacao
        fields = [
            'id',
            'destinatario',
            'mensagem',
            'lida',
            'data_criacao',
            'link',
            'tipo'
        ]
        read_only_fields = ['data_criacao']

class DemandaListSerializer(serializers.ModelSerializer):
    """
    Serializer para a lista de demandas (WORKAROUND - Retorna ID do autor).
    (Versão FINAL CORRIGIDA v2)
    """
    criado_por_id = serializers.ReadOnlyField(source='autor_id')

    secretaria_destino_nome = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Demanda
        fields = [
            'id', 'protocolo_legislativo', 'protocolo_executivo',
            'criado_por_id', # <-- Campo corrigido
            'secretaria_destino_nome', 'status',
            'status_display', 'data_criacao'
        ]

    # get_criado_por_nome NÃO É NECESSÁRIO AQUI

    def get_secretaria_destino_nome(self, obj):
        if obj.secretaria_destino:
            return obj.secretaria_destino.nome
        return "Aguardando Protocolo"