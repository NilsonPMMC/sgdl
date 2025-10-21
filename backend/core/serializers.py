# /var/www/sgdl/backend/core/serializers.py

from rest_framework import serializers
from .models import Demanda, Servico, Secretaria, Usuario, Anexo, Tramitacao, AnexoTramitacao

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
            'anexos', 'tramitacoes'
        ]
        read_only_fields = [
            'protocolo_legislativo', 'protocolo_executivo', 'status', 'status_display',
            'data_criacao', 'secretaria_destino', 'anexos', 'tramitacoes', 'autor'
        ]