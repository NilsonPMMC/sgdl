# Em backend/reports/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path(
        'por-status/',
        views.DemandasPorStatusView.as_view(),
        name='report-por-status',
    ),
    path(
        'por-secretaria/',
        views.DemandasPorSecretariaView.as_view(),
        name='report-por-secretaria',
    ),
    path(
        'por-vereador/',
        views.DemandasPorVereadorView.as_view(),
        name='report-por-vereador',
    ),
    path(
        'heatmap/',
        views.HeatmapView.as_view(),
        name='report-heatmap',
    ),
    path(
        'kpis/',
        views.ReportKPIsView.as_view(),
        name='report-kpis',
    ),
    path(
        'demandas-filtradas/',
        views.DemandasFiltradasView.as_view(),
        name='report-demandas-filtradas',
    ),
    path(
        'process-mining-setor/',
        views.ReportProcessMiningSetorView.as_view(),
        name='report-process-mining-setor',
    ),
    path(
        'funil-status/',
        views.ReportFunilStatusView.as_view(),
        name='report-funil-status',
    ),
    path(
        'comparativo-vereador/',
        views.ReportComparativoVereadorView.as_view(),
        name='report-comparativo-vereador',
    ),
    path(
        'export-csv/',
        views.ReportExportCSVView.as_view(),
        name='report-export-csv',
    ),
]
