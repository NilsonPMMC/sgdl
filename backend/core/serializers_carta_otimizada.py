"""
Serializers para a base otimizada da carta de serviços.
"""

from rest_framework import serializers
from .models_carta_otimizada import ServicoOtimizado, LogOtimizacao, EstatisticasBaseOtimizada


class ServicoOtimizadoSerializer(serializers.ModelSerializer):
    """Serializer para ServicoOtimizado."""
    
    tem_embedding = serializers.SerializerMethodField()
    percentual_melhoria = serializers.SerializerMethodField()
    preview_texto_rag = serializers.SerializerMethodField()
    orgao_nome = serializers.SerializerMethodField()
    unidade_administrativa_resumo = serializers.SerializerMethodField()
    
    class Meta:
        model = ServicoOtimizado
        fields = [
            'id', 'sinapse_servico_id', 'titulo_otimizado', 'descricao_objetiva',
            'intencao_servico', 'problemas_resolve', 'palavras_chave',
            'tipo_processo', 'prazo_dias', 'prazo_categoria', 'prazo_observacoes',
            'dependencias_realizacao', 'dependencias_documentos', 'dependencias_pagamentos',
            'tipos_atendimento', 'sistema_solicitacao', 'link_sistema',
            'score_qualidade_original', 'score_qualidade_otimizado',
            'problemas_identificados', 'melhorias_aplicadas',
            'versao_otimizacao', 'ativo', 'otimizado_em', 'atualizado_em',
            'unidade_administrativa', 'unidade_administrativa_resumo',
            'tem_embedding', 'percentual_melhoria', 'preview_texto_rag', 'orgao_nome',
        ]
        read_only_fields = ['otimizado_em', 'atualizado_em', 'unidade_administrativa_resumo']
    
    def get_unidade_administrativa_resumo(self, obj):
        unidade = obj.unidade_administrativa
        if not unidade:
            return None
        return {
            "id": unidade.pk,
            "nome": unidade.nome,
            "sigla": unidade.sigla,
        }
    
    def get_tem_embedding(self, obj):
        """Indica se o serviço tem embedding."""
        return obj.embedding_otimizado is not None
    
    def get_percentual_melhoria(self, obj):
        """Calcula percentual de melhoria no score."""
        if obj.score_qualidade_original > 0:
            melhoria = ((obj.score_qualidade_otimizado - obj.score_qualidade_original) 
                       / obj.score_qualidade_original * 100)
            return round(melhoria, 1)
        return 0
    
    def get_preview_texto_rag(self, obj):
        """Preview do texto RAG (primeiros 150 caracteres)."""
        if obj.texto_rag_otimizado:
            return obj.texto_rag_otimizado[:150] + "..." if len(obj.texto_rag_otimizado) > 150 else obj.texto_rag_otimizado
        return None
    
    def get_orgao_nome(self, obj):
        """Nome do órgão responsável (via Sinapse)."""
        # Aqui você pode fazer uma consulta ao Sinapse se necessário
        # Por enquanto, retorna apenas um placeholder
        return f"Órgão {obj.sinapse_servico_id}"  # Substitua pela lógica real


class LogOtimizacaoSerializer(serializers.ModelSerializer):
    """Serializer para LogOtimizacao."""
    
    servico_titulo = serializers.CharField(source='servico_otimizado.titulo_otimizado', read_only=True)
    servico_id_sinapse = serializers.IntegerField(source='servico_otimizado.sinapse_servico_id', read_only=True)
    resumo_detalhes = serializers.SerializerMethodField()
    
    class Meta:
        model = LogOtimizacao
        fields = [
            'id', 'operacao', 'timestamp', 'usuario', 'detalhes',
            'servico_titulo', 'servico_id_sinapse', 'resumo_detalhes'
        ]
    
    def get_resumo_detalhes(self, obj):
        """Resumo legível dos detalhes."""
        if not obj.detalhes:
            return None
            
        detalhes = obj.detalhes
        resumo = {}
        
        if 'score_depois' in detalhes:
            resumo['score_antes'] = detalhes.get('score_antes', 'N/A')
            resumo['score_depois'] = detalhes['score_depois']
            resumo['melhoria'] = (
                detalhes['score_depois'] - detalhes.get('score_antes', 0)
                if isinstance(detalhes.get('score_antes'), (int, float)) else 0
            )
        
        if 'melhorias' in detalhes:
            resumo['quantidade_melhorias'] = len(detalhes['melhorias'])
            resumo['melhorias'] = detalhes['melhorias']
        
        if 'embedding_gerado' in detalhes:
            resumo['embedding_gerado'] = detalhes['embedding_gerado']
        
        return resumo


class EstatisticasBaseOtimizadaSerializer(serializers.ModelSerializer):
    """Serializer para EstatisticasBaseOtimizada."""
    
    percentual_cobertura = serializers.SerializerMethodField()
    classificacao_qualidade = serializers.SerializerMethodField()
    
    class Meta:
        model = EstatisticasBaseOtimizada
        fields = [
            'id', 'data_calculo', 'total_servicos', 'servicos_com_embedding',
            'score_medio_qualidade', 'dados_detalhados',
            'percentual_cobertura', 'classificacao_qualidade'
        ]
    
    def get_percentual_cobertura(self, obj):
        """Percentual de serviços com embedding."""
        if obj.total_servicos > 0:
            return round((obj.servicos_com_embedding / obj.total_servicos) * 100, 1)
        return 0
    
    def get_classificacao_qualidade(self, obj):
        """Classificação da qualidade baseada no score médio."""
        score = obj.score_medio_qualidade
        if score >= 8:
            return {'nivel': 'Excelente', 'cor': 'success'}
        elif score >= 6:
            return {'nivel': 'Bom', 'cor': 'primary'}
        elif score >= 4:
            return {'nivel': 'Regular', 'cor': 'warning'}
        else:
            return {'nivel': 'Precisa Melhorias', 'cor': 'danger'}