# /var/www/sgdl/backend/core/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DemandaViewSet, ServicoViewSet, AnexoViewSet, SecretariaViewSet, 
    TramitacaoViewSet, DashboardStatsAPIView, CopilotoRecusasListAPIView, DemandaLocationsAPIView,
    DemandaMapAgregacaoAPIView, UsuarioViewSet, UserProfileView, ChangePasswordView, NotificacaoViewSet,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    ChatInteragirAPIView,
    ChatConfirmarServicoAPIView,
    ChatRevisarEtapaAPIView,
    ChatEditarPedidoAPIView,
    ChatEditarLocalAPIView,
    ChatRemoverAnexoSessaoAPIView,
    ChatRetriagemCartaAPIView,
    ChatIgnorarServicoAPIView,
    ChatAtualizarLocalizacaoAPIView,
    ChatMarcarDemandaRascunhoAPIView,
    ChatAtualizarIndicacaoCopilotoAPIView,
)
from .views_geocoding import (
    GeocodingCepAPIView,
    GeocodingLogradourosAPIView,
    GeocodingResolverAPIView,
    GeocodingReverseAPIView,
)
from .views_cluster import ClusterExecucaoViewSet
from .views_fluxo_protocolo import ServicoFluxoProtocoloViewSet
from .views_unidade_administrativa import UnidadeAdministrativaViewSet
from .views_assinatura import ValidarAssinaturaAPIView
from .views_assinatura_validacao import (
    AssinaturasValidacaoPendentesAPIView,
    PreviewValidacaoGestorAPIView,
    ValidarAssinaturaGestorAPIView,
)
from .views_tendencia import ChatConfirmarTendenciaAPIView, TendenciaViewSet
from .views_copiloto_faq import (
    CopilotoFaqAprovarLlmAPIView,
    CopilotoFaqOrientacaoViewSet,
    CopilotoFaqPadraoRegexViewSet,
    CopilotoFaqSugestoesLlmAPIView,
)
from .views_corpus_legado import (
    CorpusLegadoAtalhoDetalheAPIView,
    CorpusLegadoAtalhosCopilotoAPIView,
    CorpusLegadoSugerirAPIView,
    CorpusLegadoTopSetoresAPIView,
    CorpusLegadoTopTrendsAPIView,
)
from .views_carta_otimizada import (
    ServicoOtimizadoViewSet,
    LogOtimizacaoViewSet, 
    EstatisticasBaseOtimizadaViewSet
)
from .views_configuracao_oficio import (
    ConfiguracaoOficioAPIView,
    ConfiguracaoOficioPreviewPDFAPIView,
)
from .views_configuracao_carta import ConfiguracaoCartaAPIView
from .views_indicacao_camara import NumeracaoIndicacaoCamaraAPIView
from .views_carta_setor import CartaSetorViewSet
from .views_consulta_hub import ConsultaHubAPIView, ConsultaHubBuscaAPIView
from .views_depara_rm import DeParaRmSinapseViewSet
from .views_assunto_carta import AssuntoCartaViewSet, CartaAssuntoViewSet
from .views_texto_padrao_despacho import TextoPadraoDespachoViewSet
from .views_usuario_gestao import (
    GestaoUsuarioGestorViewSet,
    GestaoUsuarioSecretariaViewSet,
    GestaoUsuarioViewSet,
)
from .views_tramitacao_util import OtimizarTextoTramitacaoAPIView
from .views_estudo_viabilidade import EstudoViabilidadeListAPIView
from .views_operacional import (
    DemandaOperacionalAbrirPernasTransversalAPIView,
    DemandaOperacionalConclusaoFinalAPIView,
    DemandaOperacionalConclusaoParcialAPIView,
    DemandaOperacionalConclusaoTecnicaAPIView,
    DemandaOperacionalDevolverProtocoloAPIView,
    DemandaOperacionalEstadoAPIView,
    DemandaOperacionalHistoricoTecnicoAPIView,
    DemandaOperacionalIniciarExecucaoAPIView,
    DemandaOperacionalNosUnificadosAPIView,
    DemandaOperacionalPreviewConclusaoFinalAPIView,
    DemandaOperacionalRecusaProtocoloAPIView,
    DemandaOperacionalScatterGatherAPIView,
    DemandaOperacionalVincularServicoAPIView,
)

router = DefaultRouter()
router.register(r'demandas', DemandaViewSet, basename='demanda')
router.register(r'servicos', ServicoViewSet, basename='servico')
router.register(r'anexos', AnexoViewSet, basename='anexo')
router.register(r'secretarias', SecretariaViewSet, basename='secretaria')
router.register(r'tramitacoes', TramitacaoViewSet, basename='tramitacao')
router.register(r'usuarios', UsuarioViewSet)
router.register(r'notificacoes', NotificacaoViewSet, basename='notificacao')
router.register(r'tendencias', TendenciaViewSet, basename='tendencia')
router.register(r'clusters', ClusterExecucaoViewSet, basename='cluster')
router.register(r'fluxo-servicos', ServicoFluxoProtocoloViewSet, basename='fluxo-servico')
router.register(r'carta-setores', CartaSetorViewSet, basename='carta-setor')
router.register(r'carta-assuntos', CartaAssuntoViewSet, basename='carta-assunto')
router.register(r'assuntos-carta', AssuntoCartaViewSet, basename='assunto-carta')
router.register(r'textos-padrao-despacho', TextoPadraoDespachoViewSet, basename='texto-padrao-despacho')
router.register(r'depara-rm-sinapse', DeParaRmSinapseViewSet, basename='depara-rm-sinapse')
router.register(r'unidades-administrativas', UnidadeAdministrativaViewSet, basename='unidade-administrativa')
router.register(r'copiloto-faq', CopilotoFaqOrientacaoViewSet, basename='copiloto-faq')
router.register(r'copiloto-faq-padroes', CopilotoFaqPadraoRegexViewSet, basename='copiloto-faq-padrao')
router.register(r'carta-otimizada', ServicoOtimizadoViewSet, basename='carta-otimizada')
router.register(r'carta-logs', LogOtimizacaoViewSet, basename='carta-logs')
router.register(r'gestao-usuarios', GestaoUsuarioViewSet, basename='gestao-usuario')
router.register(r'gestao-usuarios-secretaria', GestaoUsuarioSecretariaViewSet, basename='gestao-usuario-secretaria')
router.register(r'gestao-usuarios-gestor', GestaoUsuarioGestorViewSet, basename='gestao-usuario-gestor')

urlpatterns = [
    path('v1/chat/interagir/', ChatInteragirAPIView.as_view(), name='chat-interagir'),
    path(
        'v1/chat/retriagem-carta/',
        ChatRetriagemCartaAPIView.as_view(),
        name='chat-retriagem-carta',
    ),
    path(
        'v1/chat/ignorar-servico/',
        ChatIgnorarServicoAPIView.as_view(),
        name='chat-ignorar-servico',
    ),
    path(
        'v1/chat/atualizar-localizacao/',
        ChatAtualizarLocalizacaoAPIView.as_view(),
        name='chat-atualizar-localizacao',
    ),
    path(
        'v1/chat/marcar-demanda/',
        ChatMarcarDemandaRascunhoAPIView.as_view(),
        name='chat-marcar-demanda',
    ),
    path(
        'v1/chat/confirmar-servico/',
        ChatConfirmarServicoAPIView.as_view(),
        name='chat-confirmar-servico',
    ),
    path(
        'v1/corpus-legado/top-trends/',
        CorpusLegadoTopTrendsAPIView.as_view(),
        name='corpus-legado-top-trends',
    ),
    path(
        'v1/corpus-legado/top-setores/',
        CorpusLegadoTopSetoresAPIView.as_view(),
        name='corpus-legado-top-setores',
    ),
    path(
        'v1/corpus-legado/atalhos-copiloto/',
        CorpusLegadoAtalhosCopilotoAPIView.as_view(),
        name='corpus-legado-atalhos-copiloto',
    ),
    path(
        'v1/corpus-legado/atalho-detalhe/',
        CorpusLegadoAtalhoDetalheAPIView.as_view(),
        name='corpus-legado-atalho-detalhe',
    ),
    path(
        'v1/corpus-legado/sugerir/',
        CorpusLegadoSugerirAPIView.as_view(),
        name='corpus-legado-sugerir',
    ),
    path(
        'v1/chat/revisar-etapa/',
        ChatRevisarEtapaAPIView.as_view(),
        name='chat-revisar-etapa',
    ),
    path(
        'v1/chat/editar-pedido/',
        ChatEditarPedidoAPIView.as_view(),
        name='chat-editar-pedido',
    ),
    path(
        'v1/chat/editar-local/',
        ChatEditarLocalAPIView.as_view(),
        name='chat-editar-local',
    ),
    path(
        'v1/chat/remover-anexo-sessao/',
        ChatRemoverAnexoSessaoAPIView.as_view(),
        name='chat-remover-anexo-sessao',
    ),
    path(
        'v1/chat/atualizar-indicacao/',
        ChatAtualizarIndicacaoCopilotoAPIView.as_view(),
        name='chat-atualizar-indicacao',
    ),
    path(
        'v1/chat/confirmar-tendencia/',
        ChatConfirmarTendenciaAPIView.as_view(),
        name='chat-confirmar-tendencia',
    ),
    path(
        'v1/validar-assinatura/<str:codigo>/',
        ValidarAssinaturaAPIView.as_view(),
        name='validar-assinatura',
    ),
    path(
        'assinaturas-validacao/pendentes/',
        AssinaturasValidacaoPendentesAPIView.as_view(),
        name='assinaturas-validacao-pendentes',
    ),
    path(
        'assinaturas-validacao/<int:validacao_id>/preview/',
        PreviewValidacaoGestorAPIView.as_view(),
        name='assinaturas-validacao-preview',
    ),
    path(
        'assinaturas-validacao/<int:validacao_id>/validar/',
        ValidarAssinaturaGestorAPIView.as_view(),
        name='assinaturas-validacao-validar',
    ),
    path('v1/geocoding/cep/', GeocodingCepAPIView.as_view(), name='geocoding-cep'),
    path(
        'v1/tramitacao/otimizar-texto/',
        OtimizarTextoTramitacaoAPIView.as_view(),
        name='tramitacao-otimizar-texto',
    ),
    path(
        'v1/tramitacao/otimizar-texto/',
        OtimizarTextoTramitacaoAPIView.as_view(),
        name='tramitacao-otimizar-texto',
    ),
    path('v1/geocoding/logradouros/', GeocodingLogradourosAPIView.as_view(), name='geocoding-logradouros'),
    path('v1/geocoding/resolver/', GeocodingResolverAPIView.as_view(), name='geocoding-resolver'),
    path('v1/geocoding/reverse/', GeocodingReverseAPIView.as_view(), name='geocoding-reverse'),
    path(
        'v1/copiloto-faq/sugestoes-llm/',
        CopilotoFaqSugestoesLlmAPIView.as_view(),
        name='copiloto-faq-sugestoes-llm',
    ),
    path(
        'v1/copiloto-faq/enriquecer-llm/',
        CopilotoFaqAprovarLlmAPIView.as_view(),
        name='copiloto-faq-enriquecer-llm-v1',
    ),
    path('users/me/', UserProfileView.as_view(), name='user-profile'),
    path('users/me/change-password/', ChangePasswordView.as_view(), name='user-change-password'),
    path('password-reset/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password-reset-confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('dashboard/stats/', DashboardStatsAPIView.as_view(), name='dashboard-stats'),
    path('copiloto/recusas/', CopilotoRecusasListAPIView.as_view(), name='copiloto-recusas'),
    path('demandas/locations/', DemandaLocationsAPIView.as_view(), name='demanda-locations'),
    path('demandas/mapa/agregacao/', DemandaMapAgregacaoAPIView.as_view(), name='demanda-mapa-agregacao'),
    path(
        'configuracao-oficio/',
        ConfiguracaoOficioAPIView.as_view(),
        name='configuracao-oficio',
    ),
    path(
        'configuracao-oficio/preview-pdf/',
        ConfiguracaoOficioPreviewPDFAPIView.as_view(),
        name='configuracao-oficio-preview-pdf',
    ),
    path(
        'configuracao-carta/',
        ConfiguracaoCartaAPIView.as_view(),
        name='configuracao-carta',
    ),
    path('consulta/hub/', ConsultaHubAPIView.as_view(), name='consulta-hub'),
    path('consulta/busca/', ConsultaHubBuscaAPIView.as_view(), name='consulta-busca'),
    path(
        'indicacoes/numeracao/',
        NumeracaoIndicacaoCamaraAPIView.as_view(),
        name='indicacoes-numeracao',
    ),
    path(
        'demandas/<int:demanda_pk>/operacional/estado/',
        DemandaOperacionalEstadoAPIView.as_view(),
        name='demanda-operacional-estado',
    ),
    path(
        'demandas/<int:demanda_pk>/operacional/historico-tecnico/',
        DemandaOperacionalHistoricoTecnicoAPIView.as_view(),
        name='demanda-operacional-historico',
    ),
    path(
        'demandas/<int:demanda_pk>/operacional/vincular-servico/',
        DemandaOperacionalVincularServicoAPIView.as_view(),
        name='demanda-operacional-vincular-servico',
    ),
    path(
        'demandas/<int:demanda_pk>/operacional/recusa-protocolo/',
        DemandaOperacionalRecusaProtocoloAPIView.as_view(),
        name='demanda-operacional-recusa',
    ),
    path(
        'demandas/<int:demanda_pk>/operacional/conclusao-parcial/',
        DemandaOperacionalConclusaoParcialAPIView.as_view(),
        name='demanda-operacional-conclusao-parcial',
    ),
    path(
        'demandas/<int:demanda_pk>/operacional/iniciar-execucao/',
        DemandaOperacionalIniciarExecucaoAPIView.as_view(),
        name='demanda-operacional-iniciar-execucao',
    ),
    path(
        'demandas/<int:demanda_pk>/operacional/abrir-pernas-transversal/',
        DemandaOperacionalAbrirPernasTransversalAPIView.as_view(),
        name='demanda-operacional-abrir-pernas-transversal',
    ),
    path(
        'demandas/<int:demanda_pk>/operacional/conclusao-tecnica/',
        DemandaOperacionalConclusaoTecnicaAPIView.as_view(),
        name='demanda-operacional-conclusao-tecnica',
    ),
    path(
        'demandas/<int:demanda_pk>/operacional/devolver-protocolo/',
        DemandaOperacionalDevolverProtocoloAPIView.as_view(),
        name='demanda-operacional-devolver',
    ),
    path(
        'demandas/<int:demanda_pk>/operacional/preview-conclusao-final/',
        DemandaOperacionalPreviewConclusaoFinalAPIView.as_view(),
        name='demanda-operacional-preview-conclusao-final',
    ),
    path(
        'demandas/<int:demanda_pk>/operacional/scatter-gather/',
        DemandaOperacionalScatterGatherAPIView.as_view(),
        name='demanda-operacional-scatter-gather',
    ),
    path(
        'demandas/<int:demanda_pk>/operacional/nos-unificados/',
        DemandaOperacionalNosUnificadosAPIView.as_view(),
        name='demanda-operacional-nos-unificados',
    ),
    path(
        'demandas/<int:demanda_pk>/operacional/conclusao-final/',
        DemandaOperacionalConclusaoFinalAPIView.as_view(),
        name='demanda-operacional-conclusao-final',
    ),
    path(
        'estudos-viabilidade/',
        EstudoViabilidadeListAPIView.as_view(),
        name='estudos-viabilidade-list',
    ),
    path('', include(router.urls)),
]