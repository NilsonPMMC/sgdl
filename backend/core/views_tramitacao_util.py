"""Endpoints auxiliares de tramitação (H3-17)."""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.services.tramitacao_texto_service import otimizar_texto_tramitacao


class OtimizarTextoTramitacaoAPIView(APIView):
    """Sugere revisão institucional do texto antes de registrar andamento/despacho."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        texto = request.data.get("texto") or request.data.get("descricao") or ""
        contexto = request.data.get("contexto") or request.data.get("tipo") or "andamento"
        try:
            otimizado = otimizar_texto_tramitacao(str(texto), contexto=str(contexto))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "texto_original": texto,
                "texto_otimizado": otimizado,
            }
        )
