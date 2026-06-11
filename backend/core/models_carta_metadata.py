# /var/www/sgdl/backend/core/models_carta_metadata.py

"""
Estruturas de dados para metadados ricos da carta de serviços.
Complementa os dados do Sinapse com informações estruturadas para melhorar RAG.
"""

import logging
from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.utils import timezone

logger = logging.getLogger(__name__)


class ServicoMetadataRico(models.Model):
    """
    Metadados estruturados extraídos e enriquecidos dos serviços da carta Sinapse.
    Melhora a qualidade da busca semântica e gestão operacional.
    """
    
    TIPO_PROCESSO_CHOICES = [
        ('administrativo_simples', 'Administrativo Simples'),
        ('administrativo_licenca', 'Administrativo com Licenciamento'),
        ('operacional_vistoria', 'Operacional com Vistoria'),
        ('digital_automatizado', 'Digital Automatizado'),
        ('terceirizado', 'Terceirizado/Parceria'),
        ('hibrido', 'Híbrido (Digital + Presencial)'),
    ]
    
    PUBLICO_ALVO_CHOICES = [
        ('cidadaos', 'Cidadãos em Geral'),
        ('empresarios', 'Empresários'),
        ('servidores_publicos', 'Servidores Públicos'),
        ('profissionais_liberais', 'Profissionais Liberais'),
        ('organizacoes', 'Organizações/Entidades'),
        ('especifico', 'Público Específico'),
    ]
    
    CANAL_PREFERENCIAL_CHOICES = [
        ('presencial', 'Presencial'),
        ('digital', 'Digital/Online'),
        ('telefone', 'Telefone'),
        ('hibrido', 'Híbrido'),
        ('terceirizado', 'Terceirizado'),
    ]
    
    CATEGORIA_PRAZO_CHOICES = [
        ('IMEDIATO', 'Imediato (0 dias)'),
        ('RAPIDO', 'Rápido (1-5 dias)'),
        ('NORMAL', 'Normal (6-30 dias)'),
        ('LONGO', 'Longo (31+ dias)'),
        ('INDEFINIDO', 'Indefinido/Variável'),
    ]
    
    # Identificação
    sinapse_servico_id = models.BigIntegerField(
        unique=True,
        help_text="ID do serviço na carta Sinapse (chave estrangeira)"
    )
    
    # Metadados de processo
    tipo_processo = models.CharField(
        max_length=32,
        choices=TIPO_PROCESSO_CHOICES,
        blank=True,
        null=True,
        help_text="Tipo de processo inferido automaticamente"
    )
    
    publico_alvo = ArrayField(
        models.CharField(max_length=32, choices=PUBLICO_ALVO_CHOICES),
        size=5,
        default=list,
        blank=True,
        help_text="Público(s) alvo identificado(s)"
    )
    
    canal_preferencial = models.CharField(
        max_length=16,
        choices=CANAL_PREFERENCIAL_CHOICES,
        blank=True,
        null=True,
        help_text="Canal preferencial inferido"
    )
    
    # Metadados de prazo estruturado
    prazo_dias_numericos = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Prazo em dias (extraído do texto livre)"
    )
    
    prazo_categoria = models.CharField(
        max_length=16,
        choices=CATEGORIA_PRAZO_CHOICES,
        default='INDEFINIDO',
        help_text="Categoria do prazo estruturada"
    )
    
    prazo_observacoes = models.TextField(
        blank=True,
        help_text="Observações sobre o prazo (texto original ou exceções)"
    )
    
    # Metadados semânticos para RAG
    problemas_resolve = ArrayField(
        models.TextField(),
        size=5,
        default=list,
        blank=True,
        help_text="Lista de problemas que o serviço resolve (linguagem cidadã)"
    )
    
    palavras_chave_expandidas = ArrayField(
        models.CharField(max_length=50),
        size=20,
        default=list,
        blank=True,
        help_text="Palavras-chave + sinônimos para melhorar busca"
    )
    
    contexto_uso_estruturado = models.JSONField(
        default=dict,
        blank=True,
        help_text="Contexto de uso estruturado (quando, quem, onde)"
    )
    
    # Metadados de qualidade
    score_qualidade_texto = models.PositiveSmallIntegerField(
        default=5,
        help_text="Score de qualidade do texto RAG (1-10)"
    )
    
    tem_problemas_html = models.BooleanField(
        default=False,
        help_text="Indica se havia problemas de HTML no texto original"
    )
    
    necessita_revisao = models.BooleanField(
        default=False,
        help_text="Indica se necessita revisão manual"
    )
    
    # Metadados operacionais
    dependencias_internas = ArrayField(
        models.CharField(max_length=100),
        size=10,
        default=list,
        blank=True,
        help_text="Dependências internas identificadas (outros setores, aprovações)"
    )
    
    documentos_estruturados = models.JSONField(
        default=dict,
        blank=True,
        help_text="Documentos necessários estruturados (obrigatórios/opcionais)"
    )
    
    custo_estimado_horas = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Estimativa de horas de trabalho interno"
    )
    
    # Auditoria e versionamento
    versao_otimizacao = models.PositiveIntegerField(
        default=1,
        help_text="Versão da otimização aplicada"
    )
    
    texto_rag_otimizado = models.TextField(
        blank=True,
        help_text="Texto otimizado para RAG (backup local)"
    )
    
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    otimizado_por_ia_em = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Última otimização por IA"
    )
    
    revisado_manualmente_em = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Última revisão manual"
    )
    
    class Meta:
        verbose_name = "Metadado Rico de Serviço"
        verbose_name_plural = "Metadados Ricos de Serviços"
        indexes = [
            models.Index(fields=['sinapse_servico_id']),
            models.Index(fields=['tipo_processo']),
            models.Index(fields=['prazo_categoria']),
            models.Index(fields=['score_qualidade_texto']),
            models.Index(fields=['-atualizado_em']),
        ]
    
    def __str__(self):
        return f"Metadados Serviço {self.sinapse_servico_id} (v{self.versao_otimizacao})"
    
    def marcar_otimizado_por_ia(self):
        """Marca que foi otimizado por IA agora."""
        self.otimizado_por_ia_em = timezone.now()
        self.versao_otimizacao += 1
    
    def marcar_revisado_manualmente(self):
        """Marca que foi revisado manualmente agora."""
        self.revisado_manualmente_em = timezone.now()
        self.necessita_revisao = False
    
    def get_publico_alvo_display_list(self):
        """Retorna lista legível do público-alvo."""
        choices_dict = dict(self.PUBLICO_ALVO_CHOICES)
        return [choices_dict.get(p, p) for p in self.publico_alvo]
    
    def get_problemas_principais(self):
        """Retorna os 3 principais problemas que resolve."""
        return self.problemas_resolve[:3]
    
    def is_prazo_confiavel(self):
        """Indica se o prazo é confiável (não indefinido)."""
        return self.prazo_categoria != 'INDEFINIDO' and self.prazo_dias_numericos is not None
    
    def get_contexto_resumido(self):
        """Retorna contexto de uso resumido."""
        if not self.contexto_uso_estruturado:
            return "Contexto não estruturado"
        
        quando = self.contexto_uso_estruturado.get('quando', '')
        quem = self.contexto_uso_estruturado.get('quem', '')
        
        partes = []
        if quando:
            partes.append(f"Quando: {quando}")
        if quem:
            partes.append(f"Quem: {quem}")
        
        return " | ".join(partes) if partes else "Contexto disponível"


class HistoricoOtimizacaoServico(models.Model):
    """
    Histórico de otimizações aplicadas em serviços da carta.
    Permite auditoria e rollback das melhorias.
    """
    
    TIPO_OTIMIZACAO_CHOICES = [
        ('limpeza_html', 'Limpeza de HTML'),
        ('estruturacao_prazo', 'Estruturação de Prazo'),
        ('extracao_palavras_chave', 'Extração de Palavras-chave'),
        ('inferencia_problemas', 'Inferência de Problemas'),
        ('otimizacao_embedding', 'Otimização de Embedding'),
        ('revisao_manual', 'Revisão Manual'),
        ('correcao_automatica', 'Correção Automática'),
    ]
    
    servico_metadata = models.ForeignKey(
        ServicoMetadataRico,
        on_delete=models.CASCADE,
        related_name='historico_otimizacoes'
    )
    
    tipo_otimizacao = models.CharField(
        max_length=32,
        choices=TIPO_OTIMIZACAO_CHOICES
    )
    
    descricao_mudanca = models.TextField(
        help_text="Descrição detalhada da mudança aplicada"
    )
    
    dados_antes = models.JSONField(
        null=True,
        blank=True,
        help_text="Estado antes da otimização (para rollback)"
    )
    
    dados_depois = models.JSONField(
        null=True,
        blank=True, 
        help_text="Estado depois da otimização"
    )
    
    score_qualidade_antes = models.PositiveSmallIntegerField(
        null=True,
        blank=True
    )
    
    score_qualidade_depois = models.PositiveSmallIntegerField(
        null=True,
        blank=True
    )
    
    aplicado_automaticamente = models.BooleanField(
        default=True,
        help_text="Se foi aplicado automaticamente ou por intervenção manual"
    )
    
    usuario_aplicou = models.ForeignKey(
        'Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Usuário que aplicou manualmente (se aplicável)"
    )
    
    timestamp_aplicacao = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Histórico de Otimização"
        verbose_name_plural = "Históricos de Otimizações"
        ordering = ['-timestamp_aplicacao']
        indexes = [
            models.Index(fields=['servico_metadata', '-timestamp_aplicacao']),
            models.Index(fields=['tipo_otimizacao']),
        ]
    
    def __str__(self):
        return f"{self.get_tipo_otimizacao_display()} - Serviço {self.servico_metadata.sinapse_servico_id}"
    
    def get_melhoria_score(self):
        """Calcula melhoria no score de qualidade."""
        if self.score_qualidade_antes and self.score_qualidade_depois:
            return self.score_qualidade_depois - self.score_qualidade_antes
        return None


class EstatisticasOtimizacaoCarta(models.Model):
    """
    Estatísticas consolidadas sobre otimizações da carta de serviços.
    Permite acompanhar progresso e impacto das melhorias.
    """
    
    # Identificação do período
    data_referencia = models.DateField(
        unique=True,
        help_text="Data de referência para as estatísticas"
    )
    
    # Contadores gerais
    total_servicos_carta = models.PositiveIntegerField(
        default=0,
        help_text="Total de serviços na carta Sinapse"
    )
    
    total_servicos_otimizados = models.PositiveIntegerField(
        default=0,
        help_text="Total de serviços com otimizações aplicadas"
    )
    
    total_servicos_necessitam_revisao = models.PositiveIntegerField(
        default=0,
        help_text="Total de serviços que necessitam revisão manual"
    )
    
    # Métricas de qualidade
    score_qualidade_medio_anterior = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Score médio antes das otimizações"
    )
    
    score_qualidade_medio_atual = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Score médio após as otimizações"
    )
    
    # Problemas identificados
    servicos_com_html_residual = models.PositiveIntegerField(
        default=0,
        help_text="Serviços com problemas de HTML"
    )
    
    servicos_prazo_nao_estruturado = models.PositiveIntegerField(
        default=0,
        help_text="Serviços com prazos não estruturados"
    )
    
    servicos_titulo_tecnico = models.PositiveIntegerField(
        default=0,
        help_text="Serviços com títulos muito técnicos"
    )
    
    # Melhorias aplicadas
    total_otimizacoes_aplicadas = models.PositiveIntegerField(
        default=0,
        help_text="Total de otimizações aplicadas no período"
    )
    
    otimizacoes_por_tipo = models.JSONField(
        default=dict,
        blank=True,
        help_text="Contadores por tipo de otimização"
    )
    
    # Metadados do processamento
    processado_em = models.DateTimeField(auto_now_add=True)
    tempo_processamento_minutos = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Tempo total de processamento em minutos"
    )
    
    class Meta:
        verbose_name = "Estatística de Otimização da Carta"
        verbose_name_plural = "Estatísticas de Otimização da Carta"
        ordering = ['-data_referencia']
    
    def __str__(self):
        return f"Estatísticas {self.data_referencia}"
    
    def get_percentual_otimizado(self):
        """Calcula percentual de serviços otimizados."""
        if self.total_servicos_carta > 0:
            return (self.total_servicos_otimizados / self.total_servicos_carta) * 100
        return 0
    
    def get_melhoria_score_medio(self):
        """Calcula melhoria no score médio."""
        if self.score_qualidade_medio_anterior and self.score_qualidade_medio_atual:
            return float(self.score_qualidade_medio_atual - self.score_qualidade_medio_anterior)
        return None
    
    def get_problemas_mais_frequentes(self):
        """Retorna lista de problemas ordenados por frequência."""
        problemas = [
            ('HTML residual', self.servicos_com_html_residual),
            ('Prazo não estruturado', self.servicos_prazo_nao_estruturado),
            ('Título técnico', self.servicos_titulo_tecnico),
        ]
        
        # Ordenar por frequência (maior primeiro)
        return sorted(problemas, key=lambda x: x[1], reverse=True)
    
    def get_top_otimizacoes(self, limite=5):
        """Retorna top N otimizações por frequência."""
        if not self.otimizacoes_por_tipo:
            return []
        
        items = list(self.otimizacoes_por_tipo.items())
        items.sort(key=lambda x: x[1], reverse=True)
        
        return items[:limite]