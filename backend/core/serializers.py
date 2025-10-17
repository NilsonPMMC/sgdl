# /var/www/sgdl/backend/core/serializers.py

from rest_framework import serializers
from .models import Demanda, Servico, Secretaria, Usuario, Anexo, Tramitacao, AnexoTramitacao

class SecretariaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Secretaria
        fields = ['id', 'nome']

class UsuarioSerializer(serializers.ModelSerializer):
    secretariaId = serializers.IntegerField(source='secretaria.id', read_only=True)
    class Meta:
        model = Usuario
        fields = ['id', 'username', 'first_name', 'last_name', 'perfil', 'secretariaId']

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
            'tipo',
            'tipo_display',
            'descricao', 
            'timestamp', 
            'anexos', 
            'arquivos_anexos'
        ]
        
        extra_kwargs = {
            'demanda': {'write_only': True},
            'tipo': {'write_only': True} 
        }

class DemandaSerializer(serializers.ModelSerializer):
    autor = UsuarioSerializer(read_only=True)
    servico = ServicoSerializer(read_only=True)
    secretaria_destino = SecretariaSerializer(read_only=True)
    anexos = AnexoSerializer(many=True, read_only=True)
    tramitacoes = TramitacaoSerializer(many=True, read_only=True)

    autor_id = serializers.PrimaryKeyRelatedField(queryset=Usuario.objects.all(), source='autor', write_only=True)
    servico_id = serializers.PrimaryKeyRelatedField(queryset=Servico.objects.all(), source='servico', write_only=True)

    class Meta:
        model = Demanda
        fields = [
            'id', 'protocolo_legislativo', 'protocolo_executivo', 'titulo', 'descricao', 
            'cep', 'logradouro', 'numero', 'complemento', 'bairro',
            'status', 'data_criacao', 'autor', 'servico', 'secretaria_destino',
            'autor_id', 'servico_id',
            'anexos', 'tramitacoes'
        ]
        read_only_fields = ['protocolo_legislativo', 'protocolo_executivo', 'status', 'data_criacao', 'secretaria_destino', 'anexos', 'tramitacoes']