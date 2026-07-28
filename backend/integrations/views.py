from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from integrations.services.sinapse_sync_service import SinapseSyncService
from integrations.sinapse_client import SinapseClientError
from core.services.gestor_escopo import gestor_pode_crud_admin


def _can_manage_reconciliation(user) -> bool:
    return gestor_pode_crud_admin(user)


class SinapseUnmatchedListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _can_manage_reconciliation(request.user):
            return Response({"detail": "Sem permissao para reconciliacao."}, status=status.HTTP_403_FORBIDDEN)

        limit = int(request.query_params.get("limit", 50))
        match_status = request.query_params.get("match_status", "UNMATCHED")
        search = request.query_params.get("search")
        min_confidence_raw = request.query_params.get("min_confidence")
        min_confidence = None
        if min_confidence_raw is not None and str(min_confidence_raw).strip():
            try:
                min_confidence = float(min_confidence_raw)
            except ValueError:
                return Response(
                    {"detail": "Parametro min_confidence invalido."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        service = SinapseSyncService()
        data = service.list_unmatched(
            limit=limit,
            match_status=match_status,
            search=search,
            min_confidence=min_confidence,
        )
        return Response(data, status=status.HTTP_200_OK)


class SinapseManualBindAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _can_manage_reconciliation(request.user):
            return Response({"detail": "Sem permissao para reconciliacao."}, status=status.HTTP_403_FORBIDDEN)

        sinapse_id = request.data.get("sinapse_service_id")
        servico_id = request.data.get("servico_local_id")
        if not sinapse_id or not servico_id:
            return Response(
                {"detail": "Informe sinapse_service_id e servico_local_id."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        actor = request.user.username if request.user and request.user.is_authenticated else "api"
        service = SinapseSyncService()
        try:
            result = service.bind_manual_mapping(
                sinapse_service_id=str(sinapse_id),
                servico_local_id=int(servico_id),
                actor=actor,
            )
        except SinapseClientError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(result, status=status.HTTP_200_OK)


class SinapseSyncHealthAPIView(APIView):
    """Resumo operacional da fila de reconciliação (contagens e alertas)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _can_manage_reconciliation(request.user):
            return Response({"detail": "Sem permissao para reconciliacao."}, status=status.HTTP_403_FORBIDDEN)
        service = SinapseSyncService()
        return Response(service.sync_health_report(), status=status.HTTP_200_OK)


class SinapseBulkManualBindAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _can_manage_reconciliation(request.user):
            return Response({"detail": "Sem permissao para reconciliacao."}, status=status.HTTP_403_FORBIDDEN)

        bindings = request.data.get("bindings")
        if not isinstance(bindings, list):
            return Response(
                {"detail": "Informe 'bindings' como lista."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        actor = request.user.username if request.user and request.user.is_authenticated else "api"
        service = SinapseSyncService()
        result = service.bulk_bind_manual(bindings=bindings, actor=actor)
        return Response(result, status=status.HTTP_200_OK)
