"""
Modelos para base otimizada da carta de serviços.

Esta base local armazena versões otimizadas dos serviços do Sinapse,
sem alterar os dados originais (read-only).
"""

from django.db import models
from pgvector.django import VectorField
import json


class ServicoOtimizado(models.Model):
    """
    Versão otimizada de um serviço da carta Sinapse.
    
    Mantem referência ao ID original mas com dados limpos e estruturados
    para melhor performance na busca semântica.
    """
    
    # Referência ao serviço original
    sinapse_servico_id = models.PositiveIntegerField(
        unique=True,
        help_text="ID do serviço original no Sinapse"
    )
    
    # Dados básicos otimizados
    titulo_otimizado = models.CharField(
        max_length=200,
        help_text="Título limpo e orientado ao cidadão"
    )
    descricao_objetiva = models.TextField(
        help_text="Descrição clara sem HTML, linguagem acessível"
    )
    intencao_servico = models.TextField(
        blank=True,
        help_text="Para que serve este serviço (1-2 frases)"
    )
    problemas_resolve = models.JSONField(
        default=list,
        help_text="Lista dos problemas/situações que este serviço resolve"
    )
    
    # Texto otimizado para RAG
    texto_rag_otimizado = models.TextField(
        help_text="Texto concatenado e estruturado para embedding"
    )
    
    # Embedding otimizado
    embedding_otimizado = VectorField(
        dimensions=1024, 
        blank=True, 
        null=True,
        help_text="Vetor 1024d gerado do texto otimizado"
    )
    
    # Dados de gestão estruturados
    tipo_processo = models.CharField(
        max_length=20,
        choices=[
            ('ADMINISTRATIVO', 'Apenas Administrativo'),
            ('OPERACIONAL', 'Operacional'),
            ('EQUIPAMENTOS', 'Depende de Equipamentos'),
            ('MISTO', 'Administrativo + Operacional'),
            ('TERCEIRIZADO', 'Terceirizado'),
        ],
        blank=True,
        help_text="Tipo de processo envolvido"
    )
    
    prazo_dias = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text="Prazo em dias (estruturado)"
    )
    prazo_categoria = models.CharField(
        max_length=15,
        choices=[
            ('IMEDIATO', 'Imediato'),
            ('RAPIDO', 'Rápido (até 7 dias)'),
            ('NORMAL', 'Normal (até 30 dias)'),
            ('LONGO', 'Longo (mais de 30 dias)'),
            ('VARIAVEL', 'Variável'),
        ],
        blank=True,
        help_text="Categoria do prazo"
    )
    prazo_observacoes = models.TextField(
        blank=True,
        help_text="Observações sobre o prazo"
    )
    
    # Dependências estruturadas
    dependencias_documentos = models.JSONField(
        default=list,
        help_text="Lista estruturada de documentos necessários"
    )
    dependencias_realizacao = models.JSONField(
        default=list,
        help_text="Pré-requisitos para realização do serviço"
    )
    dependencias_pagamentos = models.JSONField(
        default=list,
        help_text="Informações sobre taxas e pagamentos"
    )
    
    # Informações de atendimento e sistemas
    tipos_atendimento = models.JSONField(
        default=list,
        help_text="Tipos de atendimento disponíveis (presencial, online, telefone, etc.)"
    )
    sistema_solicitacao = models.CharField(
        max_length=100,
        blank=True,
        help_text="Canal de atendimento ao cidadão na carta (ColabGov, portal online, etc.)"
    )
    link_sistema = models.URLField(
        blank=True,
        help_text="Link direto para o sistema de solicitação"
    )
    
    # Palavras-chave e sinônimos para busca
    palavras_chave = models.JSONField(
        default=list,
        help_text="Palavras-chave e sinônimos para busca semântica"
    )
    
    # Metadados de qualidade
    score_qualidade_original = models.PositiveSmallIntegerField(
        default=1,
        help_text="Score de qualidade do serviço original (1-10)"
    )
    score_qualidade_otimizado = models.PositiveSmallIntegerField(
        default=5,
        help_text="Score de qualidade após otimização (1-10)"
    )
    
    # Problemas identificados e melhorias aplicadas
    problemas_identificados = models.JSONField(
        default=list,
        help_text="Lista de problemas encontrados no serviço original"
    )
    melhorias_aplicadas = models.JSONField(
        default=list,
        help_text="Lista de melhorias aplicadas na otimização"
    )
    
    # Controle de versão
    versao_otimizacao = models.CharField(
        max_length=10,
        default="1.0",
        help_text="Versão do algoritmo de otimização usado"
    )
    otimizado_em = models.DateTimeField(
        auto_now_add=True,
        help_text="Data/hora da otimização"
    )
    atualizado_em = models.DateTimeField(
        auto_now=True,
        help_text="Última atualização"
    )
    
    # Flags de controle
    ativo = models.BooleanField(
        default=True,
        help_text="Se o serviço otimizado está ativo"
    )
    validado_humano = models.BooleanField(
        default=False,
        help_text="Se passou por validação humana"
    )
    precisa_revisao = models.BooleanField(
        default=False,
        help_text="Se necessita revisão manual"
    )
    unidade_administrativa = models.ForeignKey(
        "UnidadeAdministrativa",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="servicos_otimizados",
        help_text="Setor operacional sugerido para despacho (C2).",
    )
    assunto = models.ForeignKey(
        "AssuntoCarta",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="servicos_otimizados",
        help_text="Assunto temático de gestão (C5).",
    )
    modo_utilizacao_sgdl = models.CharField(
        max_length=32,
        blank=True,
        choices=[
            ("PROTOCOLAVEL", "Protocolável"),
            ("INFORMATIVO", "Somente orientação"),
            ("PROTOCOLAVEL_CONDICIONAL", "Protocolável com condição"),
        ],
        help_text="Override do modo do assunto; vazio = herda do assunto.",
    )
    mensagem_orientacao = models.TextField(
        blank=True,
        help_text="Orientação específica deste serviço (quando informativo).",
    )

    class Meta:
        db_table = 'core_servico_otimizado'
        verbose_name = 'Serviço Otimizado'
        verbose_name_plural = 'Serviços Otimizados'
        indexes = [
            models.Index(fields=['sinapse_servico_id']),
            models.Index(fields=['score_qualidade_otimizado']),
            models.Index(fields=['tipo_processo']),
            models.Index(fields=['prazo_categoria']),
            models.Index(fields=['ativo', 'validado_humano']),
        ]
    
    def __str__(self):
        return f"Otimizado: {self.titulo_otimizado[:50]}..."
    
    @property
    def melhoria_score(self):
        """Calcula melhoria no score de qualidade."""
        return self.score_qualidade_otimizado - self.score_qualidade_original
    
    @property
    def texto_completo_busca(self):
        """Texto completo para indexação de busca."""
        partes = [
            self.titulo_otimizado,
            self.descricao_objetiva,
            self.intencao_servico,
            ' '.join(self.problemas_resolve),
            ' '.join(self.palavras_chave),
        ]
        return ' '.join(filter(None, partes))
    
    def adicionar_problema(self, problema: str):
        """Adiciona um problema identificado à lista."""
        if problema not in self.problemas_identificados:
            self.problemas_identificados.append(problema)
    
    def adicionar_melhoria(self, melhoria: str):
        """Adiciona uma melhoria aplicada à lista.""" 
        if melhoria not in self.melhorias_aplicadas:
            self.melhorias_aplicadas.append(melhoria)
    
    def adicionar_palavra_chave(self, palavra: str):
        """Adiciona uma palavra-chave à lista."""
        palavra_limpa = palavra.lower().strip()
        if palavra_limpa and palavra_limpa not in self.palavras_chave:
            self.palavras_chave.append(palavra_limpa)


class LogOtimizacao(models.Model):
    """
    Log das operações de otimização executadas.
    """
    
    servico_otimizado = models.ForeignKey(
        ServicoOtimizado,
        on_delete=models.CASCADE,
        related_name='logs'
    )
    
    operacao = models.CharField(
        max_length=20,
        choices=[
            ('CRIACAO', 'Criação'),
            ('ATUALIZACAO', 'Atualização'),
            ('VALIDACAO', 'Validação Humana'),
            ('REVISAO', 'Revisão'),
            ('DESATIVACAO', 'Desativação'),
        ],
        help_text="Tipo de operação realizada"
    )
    
    detalhes = models.JSONField(
        default=dict,
        help_text="Detalhes da operação (scores, problemas, etc.)"
    )
    
    usuario = models.CharField(
        max_length=100,
        default="sistema",
        help_text="Usuário responsável pela operação"
    )
    
    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="Data/hora da operação"
    )
    
    class Meta:
        db_table = 'core_log_otimizacao'
        verbose_name = 'Log de Otimização'
        verbose_name_plural = 'Logs de Otimização'
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.operacao} - Serviço {self.servico_otimizado.sinapse_servico_id}"


class EstatisticasBaseOtimizada(models.Model):
    """
    Estatísticas consolidadas da base otimizada.
    """
    
    data_referencia = models.DateField(
        unique=True,
        help_text="Data de referência das estatísticas"
    )
    
    # Números gerais
    total_servicos_sinapse = models.PositiveIntegerField(
        default=0,
        help_text="Total de serviços na base Sinapse"
    )
    total_servicos_otimizados = models.PositiveIntegerField(
        default=0,
        help_text="Total de serviços na base otimizada"
    )
    total_validados_humano = models.PositiveIntegerField(
        default=0,
        help_text="Total validados por humanos"
    )
    total_precisam_revisao = models.PositiveIntegerField(
        default=0,
        help_text="Total que precisam de revisão"
    )
    
    # Qualidade
    score_medio_original = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Score médio original"
    )
    score_medio_otimizado = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Score médio otimizado"
    )
    melhoria_media = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Melhoria média nos scores"
    )
    
    # Contadores por problema
    problemas_html_residual = models.PositiveIntegerField(default=0)
    problemas_prazo_estruturado = models.PositiveIntegerField(default=0)
    problemas_titulo_tecnico = models.PositiveIntegerField(default=0)
    problemas_entidades_html = models.PositiveIntegerField(default=0)
    
    # Contadores por tipo de processo
    processos_administrativo = models.PositiveIntegerField(default=0)
    processos_operacional = models.PositiveIntegerField(default=0)
    processos_equipamentos = models.PositiveIntegerField(default=0)
    processos_misto = models.PositiveIntegerField(default=0)
    processos_terceirizado = models.PositiveIntegerField(default=0)
    
    # Metadados
    gerado_em = models.DateTimeField(auto_now_add=True)
    tempo_processamento = models.DurationField(
        null=True,
        blank=True,
        help_text="Tempo para gerar as estatísticas"
    )
    
    class Meta:
        db_table = 'core_estatisticas_base_otimizada'
        verbose_name = 'Estatísticas Base Otimizada'
        verbose_name_plural = 'Estatísticas Base Otimizada'
        ordering = ['-data_referencia']
    
    def __str__(self):
        return f"Stats {self.data_referencia}: {self.total_servicos_otimizados}/{self.total_servicos_sinapse}"
    
    @property
    def percentual_otimizado(self):
        """Calcula percentual de serviços otimizados."""
        if self.total_servicos_sinapse > 0:
            return (self.total_servicos_otimizados / self.total_servicos_sinapse) * 100
        return 0.0