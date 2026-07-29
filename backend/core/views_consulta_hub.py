"""API do hub de consultas (C4)."""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.services.consulta_hub_service import ConsultaHubService

_PERFIS_HUB = frozenset({"VEREADOR", "PROTOCOLO", "SECRETARIA", "GESTOR", "CAMARA"})


class ConsultaHubAPIView(APIView):
    """GET — atalhos e contadores por perfil."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        perfil = getattr(request.user, "perfil", None)
        if perfil not in _PERFIS_HUB and not request.user.is_staff:
            return Response(
                {"detail": "Hub de consultas não disponível para este perfil."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(
            {
                "perfil": perfil,
                "atalhos": ConsultaHubService().atalhos(request.user),
            }
        )


class ConsultaHubBuscaAPIView(APIView):
    """GET ?q= — busca unificada (demandas + carta)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        perfil = getattr(request.user, "perfil", None)
        if perfil not in _PERFIS_HUB and not request.user.is_staff:
            return Response(
                {"detail": "Busca não disponível para este perfil."},
                status=status.HTTP_403_FORBIDDEN,
            )
        q = (request.query_params.get("q") or "").strip()
        try:
            limit = min(int(request.query_params.get("limit", 15)), 30)
        except (TypeError, ValueError):
            limit = 15
        return Response(ConsultaHubService().buscar(request.user, q, limit=limit))
