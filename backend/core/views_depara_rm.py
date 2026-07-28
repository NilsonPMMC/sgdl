"""API de de-para COD_RM ↔ Sinapse (C6)."""

from rest_framework.decorators import action
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models_depara_rm import DeParaRmSinapse
from core.serializers import DeParaRmSinapseSerializer
from core.services.gestor_escopo import gestor_pode_crud_admin, pode_consultar_depara_rm


def _pode_gerir(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and (
            getattr(user, "perfil", None) == "PROTOCOLO"
            or gestor_pode_crud_admin(user)
        )
    )


class DeParaRmSinapseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = DeParaRmSinapseSerializer
    queryset = DeParaRmSinapse.objects.all().order_by("cod_rm")
    http_method_names = ["get", "post", "patch", "head", "options"]

    def list(self, request, *args, **kwargs):
        if not pode_consultar_depara_rm(request.user):
            return Response(
                {"detail": "Acesso restrito a Protocolo ou Gestor."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        if not pode_consultar_depara_rm(request.user):
            return Response(
                {"detail": "Acesso restrito a Protocolo ou Gestor."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        if not _pode_gerir(request.user):
            return Response(
                {"detail": "Acesso restrito a Protocolo ou Gestor administrador."},
                status=status.HTTP_403_FORBIDDEN,
            )
        data = dict(request.data)
        if data.get("cod_rm"):
            data["cod_rm"] = str(data["cod_rm"]).strip().upper()
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        if not _pode_gerir(request.user):
            return Response(
                {"detail": "Acesso restrito a Protocolo ou Gestor administrador."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().partial_update(request, *args, **kwargs)

    @action(detail=False, methods=["post"], url_path="carregar-csv")
    def carregar_csv(self, request):
        if not _pode_gerir(request.user):
            return Response(
                {"detail": "Acesso restrito a Protocolo ou Gestor administrador."},
                status=status.HTTP_403_FORBIDDEN,
            )
        from core.services.rm_unidades_import_service import RmUnidadesImportService

        n = RmUnidadesImportService().carregar_depara_csv()
        return Response({"carregados": n})
