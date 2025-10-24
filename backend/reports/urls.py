# Em backend/reports/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path(
        'por-status/', 
        views.DemandasPorStatusView.as_view(), 
        name='report-por-status'
    ),
    path(
        'por-secretaria/', 
        views.DemandasPorSecretariaView.as_view(), 
        name='report-por-secretaria'
    ),
    path(
        'por-vereador/', 
        views.DemandasPorVereadorView.as_view(), 
        name='report-por-vereador'
    ),
    path(
        'heatmap/', 
        views.HeatmapView.as_view(), 
        name='report-heatmap'
    ),
    path(
        'demandas-filtradas/', 
        views.DemandasFiltradasView.as_view(), 
        name='report-demandas-filtradas'
    ),
]