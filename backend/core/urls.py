# /var/www/sgdl/backend/core/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DemandaViewSet, ServicoViewSet, AnexoViewSet, SecretariaViewSet, 
    TramitacaoViewSet, DashboardStatsAPIView, CopilotoRecusasListAPIView, DemandaLocationsAPIView, 
    UsuarioViewSet, UserProfileView, ChangePasswordView, NotificacaoViewSet,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    ChatInteragirAPIView,
    ChatConfirmarServicoAPIView,
    ChatRetriagemCartaAPIView,
    ChatIgnorarServicoAPIView,
    ChatAtualizarLocalizacaoAPIView,
    ChatMarcarDemandaRascunhoAPIView,
)
from .views_geocoding import GeocodingCepAPIView, GeocodingResolverAPIView
from .views_cluster import ClusterExecucaoViewSet
from .views_fluxo_protocolo import ServicoFluxoProtocoloViewSet
from .views_unidade_administrativa import UnidadeAdministrativaViewSet
from .views_assinatura import ValidarAssinaturaAPIView
from .views_tendencia import ChatConfirmarTendenciaAPIView, TendenciaViewSet
from .views_copiloto_faq import (
    CopilotoFaqAprovarLlmAPIView,
    CopilotoFaqOrientacaoViewSet,
    CopilotoFaqPadraoRegexViewSet,
    CopilotoFaqSugestoesLlmAPIView,
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
from .views_carta_setor import CartaSetorViewSet
from .views_consulta_hub import ConsultaHubAPIView, ConsultaHubBuscaAPIView
from .views_depara_rm import DeParaRmSinapseViewSet
from .views_assunto_carta import AssuntoCartaViewSet, CartaAssuntoViewSet
from .views_usuario_gestao import (
    GestaoUsuarioGestorViewSet,
    GestaoUsuarioSecretariaViewSet,
    GestaoUsuarioViewSet,
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
        'v1/chat/confirmar-tendencia/',
        ChatConfirmarTendenciaAPIView.as_view(),
        name='chat-confirmar-tendencia',
    ),
    path(
        'v1/validar-assinatura/<str:codigo>/',
        ValidarAssinaturaAPIView.as_view(),
        name='validar-assinatura',
    ),
    path('v1/geocoding/cep/', GeocodingCepAPIView.as_view(), name='geocoding-cep'),
    path('v1/geocoding/resolver/', GeocodingResolverAPIView.as_view(), name='geocoding-resolver'),
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
    path('', include(router.urls)),
]