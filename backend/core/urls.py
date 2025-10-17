# /var/www/sgdl/backend/core/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DemandaViewSet, ServicoViewSet, AnexoViewSet, SecretariaViewSet, TramitacaoViewSet, DashboardStatsAPIView, DemandaLocationsAPIView, CurrentUserAPIView

router = DefaultRouter()
router.register(r'demandas', DemandaViewSet, basename='demanda')
router.register(r'servicos', ServicoViewSet, basename='servico')
router.register(r'anexos', AnexoViewSet, basename='anexo')
router.register(r'secretarias', SecretariaViewSet, basename='secretaria')
router.register(r'tramitacoes', TramitacaoViewSet, basename='tramitacao')

urlpatterns = [
    path('users/me/', CurrentUserAPIView.as_view(), name='current-user'),
    path('dashboard/stats/', DashboardStatsAPIView.as_view(), name='dashboard-stats'),
    path('demandas/locations/', DemandaLocationsAPIView.as_view(), name='demanda-locations'),
    path('', include(router.urls)),
]