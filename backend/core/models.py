# /var/www/sgdl/backend/core/models.py

import logging
import uuid
from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from pgvector.django import VectorField

from integrations import sinapse_catalog

logger = logging.getLogger(__name__)


class Usuario(AbstractUser):
    PERFIL_CHOICES = (
        ('VEREADOR', 'Vereador'),
        ('ASSESSOR', 'Assessor Legislativo'),
        ('PROTOCOLO', 'Protocolo'),
        ('SECRETARIA', 'Secretaria'),
        ('GESTOR', 'Gestor'),
    )
    perfil = models.CharField(max_length=20, choices=PERFIL_CHOICES, blank=True, null=True)
    sinapse_orgao_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="ID do órgão (CatalogOrgao) no Sinapse vinculado ao usuário de secretaria.",
    )
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    cargo = models.CharField(max_length=100, blank=True, null=True)
    telefone = models.CharField(max_length=20, blank=True, null=True)
    ramal = models.CharField(max_length=10, blank=True, null=True)
    assinatura = models.TextField(
        blank=True,
        null=True,
        help_text="Texto/HTML exibido na assinatura do ofício quando não houver imagem.",
    )
    assinatura_imagem = models.ImageField(
        upload_to="assinaturas/%Y/%m/",
        null=True,
        blank=True,
        help_text="Imagem da assinatura (PNG/JPG) usada no rodapé do ofício em PDF.",
    )


class ClusterExecucao(models.Model):
    STATUS_CHOICES = (
        ('ABERTO', 'Aberto'),
        ('EM_ANDAMENTO', 'Em Andamento'),
        ('RESOLVIDO', 'Resolvido'),
    )

    titulo = models.CharField(max_length=200)
    descricao_resumo = models.TextField(blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='ABERTO')
    secretaria_responsavel = models.CharField(max_length=150, blank=True)
    bairro_referencia = models.CharField(max_length=100, blank=True)
    sinapse_servico_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Serviço Sinapse que unifica o agrupamento (mesmo serviço + proximidade).",
    )
    centroide = VectorField(dimensions=1024, null=True, blank=True)
    protocolo_super_os = models.CharField(
        max_length=30,
        unique=True,
        null=True,
        blank=True,
        help_text="Referência interna do lote (ex.: SUPER-2026-0001).",
    )
    despachado_em = models.DateTimeField(null=True, blank=True)
    despachado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clusters_despachados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.titulo


class Demanda(models.Model):
    STATUS_CHOICES = (
        ('RASCUNHO', 'Rascunho'),
        ('AGUARDANDO_PROTOCOLO', 'Aguardando Protocolo'),
        ('PROTOCOLADO', 'Protocolado e Despachado'),
        ('EM_EXECUCAO', 'Em Execução'),
        ('AGUARDANDO_DEVOLUTIVA_PROTOCOLO', 'Aguardando devolutiva (Protocolo)'),
        ('DEVOLVIDO_VEREADOR', 'Devolutiva enviada ao vereador'),
        ('FINALIZADO', 'Finalizado'),
        ('CANCELADO', 'Cancelado'),
        ('AGUARDANDO_TRANSFERENCIA', 'Aguardando Transferência'),
    )

    protocolo_legislativo = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Nº do ofício (OFICIO-AAAA-NNNN), sequência anual por autor.",
    )
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
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default='RASCUNHO')
    data_criacao = models.DateTimeField(default=timezone.now)
    data_finalizacao = models.DateTimeField(blank=True, null=True)
    autor = models.ForeignKey('Usuario', on_delete=models.PROTECT, related_name='demandas_criadas')
    sinapse_servico_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="ID do serviço na carta Sinapse (CatalogServico).",
    )
    sinapse_orgao_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="ID do órgão destino no Sinapse (CatalogOrgao); preenchido no despacho ou pelo catálogo.",
    )
    data_inicio_prazo = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Data em que o status mudou para 'Protocolado', iniciando a contagem do prazo.",
    )
    data_entrada_etapa = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Momento em que a demanda entrou no status/etapa atual (temporizador de parada).",
    )
    notificacao_atraso_enviada = models.BooleanField(
        default=False,
        help_text="Marca se a notificação de atraso já foi enviada.",
    )
    PRAZO_ORIGEM_SERVICO = "SERVICO"
    PRAZO_ORIGEM_PADRAO = "PADRAO"
    PRAZO_ORIGEM_INDEFINIDO = "INDEFINIDO"
    PRAZO_ORIGEM_CHOICES = (
        (PRAZO_ORIGEM_SERVICO, "Prazo do serviço"),
        (PRAZO_ORIGEM_PADRAO, "Prazo padrão institucional"),
        (PRAZO_ORIGEM_INDEFINIDO, "Sem prazo definido"),
    )
    prazo_efetivo_dias = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="SLA em dias fixado ao protocolar (snapshot da política vigente).",
    )
    prazo_origem = models.CharField(
        max_length=16,
        choices=PRAZO_ORIGEM_CHOICES,
        blank=True,
        default="",
        help_text="Origem do prazo efetivo ao protocolar.",
    )
    embedding = VectorField(dimensions=1024, null=True, blank=True)
    ia_categoria = models.CharField(max_length=100, blank=True)
    ia_sentimento = models.CharField(max_length=20, blank=True)
    ia_processado = models.BooleanField(default=False)
    cluster = models.ForeignKey(
        ClusterExecucao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='demandas',
    )
    ORIGEM_VINCULO_CARTA = "CARTA"
    ORIGEM_VINCULO_TENDENCIA = "TENDENCIA"
    ORIGEM_VINCULO_CHOICES = (
        (ORIGEM_VINCULO_CARTA, "Carta de serviços"),
        (ORIGEM_VINCULO_TENDENCIA, "Tendência (fora da carta)"),
    )
    origem_vinculo = models.CharField(
        max_length=16,
        choices=ORIGEM_VINCULO_CHOICES,
        default=ORIGEM_VINCULO_CARTA,
        help_text="Trilha de vinculação ao protocolar (carta Sinapse ou tendência interna).",
    )
    tendencia = models.ForeignKey(
        "Tendencia",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="demandas",
    )
    unidade_administrativa = models.ForeignKey(
        "UnidadeAdministrativa",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="demandas",
        help_text="Setor operacional responsável pela execução.",
    )
    fluxo_roteamento = models.CharField(
        max_length=24,
        blank=True,
        default="",
        help_text="FLUXO_DIRETO ou FLUXO_TRANSVERSAL — definido na triagem do Protocolo.",
    )
    sinapse_orgao_lider_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Órgão líder do processo (carta ou 1ª secretaria na triagem).",
    )
    modo_entrada_processo = models.CharField(
        max_length=24,
        blank=True,
        default="",
        help_text="OFICIO_UNICO ou CLUSTER_SUPER_OS — definido no despacho.",
    )
    orquestrador_conclusao = models.CharField(
        max_length=24,
        blank=True,
        default="",
        help_text="SECRETARIA_LIDER ou PROTOCOLO — quem conduz a operação até o gate.",
    )
    inicio_execucao_automatico = models.BooleanField(
        default=False,
        help_text="True quando o Protocolo inicia execução automaticamente (C3/C5).",
    )
    nos_ativos = models.PositiveIntegerField(
        default=0,
        help_text="Nós operacionais abertos (scatter-gather) — contagem denormalizada.",
    )
    resultado_operacional = models.CharField(
        max_length=32,
        blank=True,
        default="",
        help_text="Resultado da conclusão operacional (executado, sem execução, etc.).",
    )
    motivo_nao_execucao = models.CharField(
        max_length=32,
        blank=True,
        default="",
        help_text="Motivo quando o pedido não foi executado materialmente.",
    )
    escopo_geografico = models.TextField(
        blank=True,
        help_text="Escopo geográfico declarado na conclusão (ex.: município inteiro, bairro).",
    )
    stand_by_estudo_viabilidade = models.BooleanField(
        default=False,
        help_text="Demanda registrada na base stand-by de estudo e viabilidade.",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["autor", "protocolo_legislativo"],
                condition=models.Q(protocolo_legislativo__isnull=False),
                name="unique_oficio_legislativo_por_autor",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.origem_vinculo == self.ORIGEM_VINCULO_TENDENCIA:
            self.sinapse_servico_id = None
        elif self.sinapse_servico_id and not self.sinapse_orgao_id:
            orgao_id = sinapse_catalog.get_orgao_id_for_servico(int(self.sinapse_servico_id))
            if orgao_id:
                self.sinapse_orgao_id = orgao_id
        super().save(*args, **kwargs)

    def prazo_dias(self) -> int | None:
        if self.prazo_efetivo_dias is not None:
            return int(self.prazo_efetivo_dias)
        from core.services.prazo_demanda_service import PrazoDemandaService

        return PrazoDemandaService().resolver_demanda(self).dias

    def prazo_resolvido_dict(self) -> dict:
        from core.services.prazo_demanda_service import PrazoDemandaService

        return PrazoDemandaService().resolver_demanda(self).as_dict()

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
        ('EXECUCAO', 'Execução'),
        ('ATRASO', 'Registro de Atraso'),
        ('PROGRAMACAO', 'Programação do Serviço'),
        ('CONCLUSAO', 'Conclusão do Serviço'),
        ('TRANSFERENCIA', 'Transferência de Setor/Secretaria'),
        ('ENCAMINHAMENTO_SETOR', 'Encaminhamento entre setores'),
        ('SOLICITACAO_DEVOLUTIVA', 'Solicitação de devolutiva'),
        ('DEVOLUTIVA_PROTOCOLO', 'Devolutiva ao vereador'),
        ('ENCERRAMENTO_DEVOLUTIVA', 'Encerramento legislativo'),
        ('CIENCIA_VEREADOR', 'Ciência do vereador'),
        ('TRIAGEM_PROTOCOLO', 'Triagem do Protocolo'),
        ('RECUSA_PROTOCOLO', 'Recusa do Protocolo ao vereador'),
        ('CONCLUSAO_TECNICA', 'Conclusão técnica (fluxo direto)'),
        ('CONCLUSAO_PARCIAL', 'Conclusão parcial (fluxo transversal)'),
        ('DEVOLUCAO', 'Devolução ao Protocolo'),
        ('CONCLUSAO_FINAL', 'Conclusão final (Protocolo)'),
        ('OPERACAO_NO', 'Operação scatter-gather (nó)'),
    ]

    demanda = models.ForeignKey(Demanda, on_delete=models.CASCADE, related_name='tramitacoes')
    responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    tipo = models.CharField(max_length=24, choices=TIPO_CHOICES)
    descricao = models.TextField(help_text="Descrição detalhada do passo, justificativa do atraso, etc.")
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Payload estruturado do evento (event sourcing operacional).",
    )
    unidade_origem = models.ForeignKey(
        "UnidadeAdministrativa",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tramitacoes_saida",
    )
    unidade_destino = models.ForeignKey(
        "UnidadeAdministrativa",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tramitacoes_entrada",
    )
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
    TIPO_NOTIFICACAO_CHOICES = [
        ('NOVO_OFICIO', 'Novo Ofício'),
        ('DESPACHO', 'Despacho'),
        ('ATUALIZACAO', 'Atualização'),
        ('TRANSFERENCIA', 'Transferência'),
        ('CONCLUSAO', 'Conclusão'),
        ('DEVOLUTIVA', 'Devolutiva'),
        ('ATRASO', 'Atraso'),
        ('ASSINATURA_PENDENTE', 'Assinatura pendente'),
    ]

    destinatario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notificacoes')
    tipo = models.CharField(
        max_length=24,
        choices=TIPO_NOTIFICACAO_CHOICES,
        default='ATUALIZACAO'
    )
    mensagem = models.TextField()
    lida = models.BooleanField(default=False)
    data_criacao = models.DateTimeField(auto_now_add=True)
    link = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f'Notificação para {self.destinatario.username}: {self.mensagem[:20]}'

    class Meta:
        ordering = ['-data_criacao']


class Tendencia(models.Model):
    """Tema recorrente não mapeado (ou ainda não) na carta Sinapse — gestão interna + embedding 1024d."""

    STATUS_ABERTA = "ABERTA"
    STATUS_EM_ANALISE = "EM_ANALISE"
    STATUS_VINCULADA_CARTA = "VINCULADA_CARTA"
    STATUS_ARQUIVADA = "ARQUIVADA"
    STATUS_CHOICES = (
        (STATUS_ABERTA, "Aberta"),
        (STATUS_EM_ANALISE, "Em análise"),
        (STATUS_VINCULADA_CARTA, "Vinculada à carta"),
        (STATUS_ARQUIVADA, "Arquivada"),
    )

    slug = models.SlugField(max_length=220, unique=True)
    titulo = models.CharField(max_length=200)
    texto_canonico = models.TextField(
        blank=True,
        help_text="Texto usado para gerar/atualizar o embedding (problema + contexto).",
    )
    descricao_resumo = models.TextField(blank=True)
    embedding = VectorField(dimensions=1024, null=True, blank=True)
    status = models.CharField(
        max_length=24,
        choices=STATUS_CHOICES,
        default=STATUS_ABERTA,
    )
    sinapse_orgao_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Órgão provável até promoção na carta ou análise do Protocolo.",
    )
    sinapse_servico_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Preenchido quando a tendência for promovida a serviço na carta.",
    )
    volume_total = models.PositiveIntegerField(default=0)
    primeira_ocorrencia = models.DateTimeField(auto_now_add=True)
    ultima_ocorrencia = models.DateTimeField(auto_now=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tendencias_criadas",
    )

    class Meta:
        ordering = ["-volume_total", "-ultima_ocorrencia"]
        indexes = [
            models.Index(fields=["status", "-volume_total"]),
            models.Index(fields=["slug"]),
        ]

    def __str__(self) -> str:
        return f"{self.titulo} (vol. {self.volume_total})"


class TendenciaOcorrencia(models.Model):
    """Registro de cada demanda (ou rascunho) associada a uma tendência."""

    tendencia = models.ForeignKey(
        Tendencia,
        on_delete=models.CASCADE,
        related_name="ocorrencias",
    )
    demanda = models.ForeignKey(
        Demanda,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ocorrencias_tendencia",
    )
    session = models.ForeignKey(
        "ChatSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ocorrencias_tendencia",
    )
    indice_demanda = models.PositiveSmallIntegerField(null=True, blank=True)
    score_triagem_max = models.FloatField(
        null=True,
        blank=True,
        help_text="Maior score Sinapse na triagem desta ocorrência (se houver).",
    )
    texto_origem = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["tendencia", "-criado_em"]),
        ]

    def __str__(self) -> str:
        ref = self.demanda_id or self.session_id or "?"
        return f"Ocorrência tendência {self.tendencia_id} → {ref}"


class ChatSession(models.Model):
    """Sessão temporária de copiloto conversacional (slot filling + Sinapse)."""

    ESTADO_COLETA_DADOS = "COLETA_DADOS"
    ESTADO_CONFIRMACAO_SINAPSE = "CONFIRMACAO_SINAPSE"
    ESTADO_COLETA_ENDERECO = "COLETA_ENDERECO"
    ESTADO_VALIDACAO_FINAL = "VALIDACAO_FINAL"

    ESTADO_CHOICES = (
        (ESTADO_COLETA_DADOS, "Coleta de dados"),
        (ESTADO_CONFIRMACAO_SINAPSE, "Confirmação Sinapse"),
        (ESTADO_COLETA_ENDERECO, "Coleta de endereço"),
        (ESTADO_VALIDACAO_FINAL, "Validação final"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_sessions",
    )
    historico_mensagens = models.JSONField(
        default=list,
        blank=True,
        help_text="Mensagens no formato OpenAI/Groq: role + content (sem o system fixo do copiloto).",
    )
    estado_atual = models.CharField(
        max_length=32,
        choices=ESTADO_CHOICES,
        default=ESTADO_COLETA_DADOS,
    )
    demandas_rascunho = models.JSONField(
        default=list,
        blank=True,
        help_text="Lista de dicts com rascunhos (titulo, descricao, endereco, sinapse_servico_id_sugerido, ...).",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-atualizado_em"]
        indexes = [
            models.Index(fields=["autor", "-atualizado_em"]),
        ]

    def __str__(self):
        return f"ChatSession {self.id} ({self.get_estado_atual_display()})"


class ChatSessaoAnexo(models.Model):
    """Arquivos enviados pelo usuário durante o copiloto (copiados para Demanda na materialização)."""

    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="anexos_sessao",
    )
    arquivo = models.FileField(upload_to="chat_anexos/%Y/%m/%d/")
    descricao = models.CharField(max_length=200, blank=True, default="Anexo do copiloto")
    indice_demanda = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Demanda do rascunho (0-based) à qual o arquivo se refere.",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["criado_em"]

    def __str__(self) -> str:
        return self.arquivo.name if self.arquivo else f"Anexo sessão {self.session_id}"


# Reexporta singleton de ofício para `from core.models import ConfiguracaoOficio`.
from core.models_config import ConfiguracaoOficio  # noqa: E402,F401
from core.models_fluxo_protocolo import ServicoFluxoProtocolo  # noqa: E402,F401
from core.models_assinatura_eletronica import AssinaturaEletronica, AssinaturaPendingAcao  # noqa: E402,F401
from core.models_copiloto_faq import (  # noqa: E402,F401
    CopilotoFaqOrientacao,
    CopilotoFaqPadraoRegex,
)
from core.models_carta_metadata import (  # noqa: E402,F401
    ServicoMetadataRico,
    HistoricoOtimizacaoServico,
    EstatisticasOtimizacaoCarta,
)

# Modelos da base otimizada (nova arquitetura)
from core.models_carta_otimizada import (  # noqa: E402,F401
    ServicoOtimizado,
    LogOtimizacao, 
    EstatisticasBaseOtimizada,
)
from core.models_unidade_administrativa import (  # noqa: E402,F401
    UnidadeAdministrativa,
    UnidadeAdministrativaResponsavel,
)
from core.models_encerramento_legislativo import EncerramentoLegislativo  # noqa: E402,F401
from core.models_estudo_viabilidade import RegistroEstudoViabilidade  # noqa: E402,F401
from core.models_acompanhamento import DemandaAcompanhamento  # noqa: E402,F401
from core.models_perna_operacional import PernaOperacional  # noqa: E402,F401
from core.models_no_operacional import NoOperacional  # noqa: E402,F401
from core.models_perna_operacional import PernaOperacional  # noqa: E402,F401
from core.models_no_operacional import NoOperacional  # noqa: E402,F401
