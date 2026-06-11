from django.urls import path

from integrations.views import (
    SinapseBulkManualBindAPIView,
    SinapseManualBindAPIView,
    SinapseSyncHealthAPIView,
    SinapseUnmatchedListAPIView,
)
from integrations.views_carta_explorer import (
    CartaServicoDetailAPIView,
    CartaServicoListAPIView,
    CartaSimularTriagemAPIView,
)


urlpatterns = [
    path("sinapse/sync-health/", SinapseSyncHealthAPIView.as_view(), name="sinapse-sync-health"),
    path("sinapse/unmatched/", SinapseUnmatchedListAPIView.as_view(), name="sinapse-unmatched-list"),
    path("sinapse/bind-manual/", SinapseManualBindAPIView.as_view(), name="sinapse-bind-manual"),
    path("sinapse/bind-manual-bulk/", SinapseBulkManualBindAPIView.as_view(), name="sinapse-bind-manual-bulk"),
    path("carta/servicos/", CartaServicoListAPIView.as_view(), name="carta-servicos-list"),
    path(
        "carta/servicos/<int:servico_id>/",
        CartaServicoDetailAPIView.as_view(),
        name="carta-servico-detail",
    ),
    path(
        "carta/simular-triagem/",
        CartaSimularTriagemAPIView.as_view(),
        name="carta-simular-triagem",
    ),
]
