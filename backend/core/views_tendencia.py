"""API de tendências (solicitações fora da carta Sinapse)."""

from __future__ import annotations

import logging

from django.conf import settings
from django.db.models import Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Tendencia
from .serializers import (
    ChatConfirmarTendenciaSerializer,
    TendenciaBuscarSimilaresSerializer,
    TendenciaOcorrenciaSerializer,
    TendenciaPromoverCartaSerializer,
    TendenciaSerializer,
    TendenciaUpdateSerializer,
)
from .services.chatbot_service import ChatbotService
from .services.tendencia_service import TendenciaService

logger = logging.getLogger(__name__)

PERFIS_GESTAO_TENDENCIA = frozenset({"PROTOCOLO", "GESTOR"})


def _usuario_pode_gestao_tendencia(user) -> bool:
    return getattr(user, "perfil", None) in PERFIS_GESTAO_TENDENCIA


class TendenciaViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    GET/PATCH /api/tendencias/ — gestão interna (Protocolo / Gestor).

    POST /api/tendencias/buscar-similares/ — preview semântico (copiloto).
    POST /api/tendencias/{id}/promover-carta/ — vincula serviço Sinapse.
  """

    permission_classes = [IsAuthenticated]
    queryset = Tendencia.objects.all()
    serializer_class = TendenciaSerializer
    filterset_fields = ["status"]
    search_fields = ["titulo", "slug", "descricao_resumo"]
    ordering_fields = ["volume_total", "ultima_ocorrencia", "titulo"]
    ordering = ["-volume_total", "-ultima_ocorrencia"]

    def get_queryset(self):
        qs = super().get_queryset()
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        q = (self.request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(titulo__icontains=q) | Q(slug__icontains=q) | Q(descricao_resumo__icontains=q))
        return qs

    def get_serializer_class(self):
        if self.action in ("partial_update", "update"):
            return TendenciaUpdateSerializer
        return TendenciaSerializer

    def list(self, request, *args, **kwargs):
        if not _usuario_pode_gestao_tendencia(request.user):
            return Response(
                {"detail": "Acesso restrito a Protocolo ou Gestor."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        if not _usuario_pode_gestao_tendencia(request.user):
            return Response(
                {"detail": "Acesso restrito a Protocolo ou Gestor."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().retrieve(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if not _usuario_pode_gestao_tendencia(request.user):
            return Response(
                {"detail": "Acesso restrito a Protocolo ou Gestor."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().partial_update(request, *args, **kwargs)

    @action(detail=False, methods=["post"], url_path="buscar-similares")
    def buscar_similares(self, request):
        """POST body: { texto, limite? } — tendências ativas próximas (embedding 1024d)."""
        ser = TendenciaBuscarSimilaresSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        texto = ser.validated_data["texto"]
        limite = ser.validated_data.get("limite", 5)
        svc = TendenciaService()
        resultados = svc.buscar_similares(texto, limite=limite)
        return Response(
            {
                "texto": texto[:200],
                "limite": limite,
                "threshold": getattr(settings, "TENDENCIA_SIMILARITY_THRESHOLD", 0.85),
                "resultados": resultados,
            }
        )

    @action(detail=True, methods=["post"], url_path="promover-carta")
    def promover_carta(self, request, pk=None):
        if not _usuario_pode_gestao_tendencia(request.user):
            return Response(
                {"detail": "Acesso restrito a Protocolo ou Gestor."},
                status=status.HTTP_403_FORBIDDEN,
            )
        tendencia = self.get_object()
        ser = TendenciaPromoverCartaSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            tendencia = TendenciaService().promover_para_carta(
                tendencia,
                sinapse_servico_id=ser.validated_data["sinapse_servico_id"],
                usuario=request.user,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TendenciaSerializer(tendencia).data)

    @action(detail=True, methods=["get"], url_path="ocorrencias")
    def ocorrencias(self, request, pk=None):
        if not _usuario_pode_gestao_tendencia(request.user):
            return Response(
                {"detail": "Acesso restrito a Protocolo ou Gestor."},
                status=status.HTTP_403_FORBIDDEN,
            )
        tendencia = self.get_object()
        qs = tendencia.ocorrencias.select_related("demanda").order_by("-criado_em")[:100]
        return Response(TendenciaOcorrenciaSerializer(qs, many=True).data)


class ChatConfirmarTendenciaAPIView(APIView):
    """POST /api/v1/chat/confirmar-tendencia/ — rascunho fora da carta (braço tendências)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not getattr(settings, "COPILOTO_TENDENCIAS_ENABLED", False):
            return Response(
                {"detail": "Módulo de tendências desabilitado neste ambiente."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        ser = ChatConfirmarTendenciaSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        try:
            payload = ChatbotService().confirmar_tendencia_demanda(
                usuario=request.user,
                session_id=str(data["session_id"]),
                indice_demanda=int(data["indice_demanda"]),
                titulo=(data.get("titulo") or "").strip(),
                descricao_resumo=(data.get("descricao_resumo") or "").strip(),
                sinapse_orgao_id=data.get("sinapse_orgao_id"),
                tendencia_id=data.get("tendencia_id"),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError:
            return Response(
                {"detail": "Sessão inexistente ou não pertence ao usuário."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(payload, status=status.HTTP_200_OK)
