"""API da configuração de SLA da carta (C1 — prazo padrão e política)."""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models_config import ConfiguracaoCarta
from core.serializers import ConfiguracaoCartaSerializer
from core.services.gestor_escopo import gestor_pode_crud_admin


def _pode_gestao_carta(user) -> bool:
    return gestor_pode_crud_admin(user)


class ConfiguracaoCartaAPIView(APIView):
    """Singleton GET/PATCH — prazo padrão e política de SLA."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _pode_gestao_carta(request.user):
            return Response(
                {"detail": "Sem permissão para consultar a configuração da carta."},
                status=status.HTTP_403_FORBIDDEN,
            )
        cfg = ConfiguracaoCarta.carregar()
        return Response(ConfiguracaoCartaSerializer(cfg).data)

    def patch(self, request):
        if not _pode_gestao_carta(request.user):
            return Response(
                {"detail": "Sem permissão para alterar a configuração da carta."},
                status=status.HTTP_403_FORBIDDEN,
            )
        cfg = ConfiguracaoCarta.carregar()
        serializer = ConfiguracaoCartaSerializer(cfg, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
