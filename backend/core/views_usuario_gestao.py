"""API de gestão de usuários por perfil (U3 Secretaria, U4 Gestor, U5 unificado)."""

from django.db.models import Q

from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import Usuario
from core.pagination import OptInPageNumberPagination
from core.services.gestor_escopo import gestor_pode_crud_admin
from core.serializers import (
    UsuarioGestaoSerializer,
    UsuarioGestaoUnificadoSerializer,
    UsuarioGestorSerializer,
    UsuarioGestorWriteSerializer,
    UsuarioCamaraWriteSerializer,
    UsuarioProtocoloWriteSerializer,
    UsuarioSecretariaWriteSerializer,
    UsuarioVereadorWriteSerializer,
)

_PERFIS_GESTAO = frozenset({"GESTOR"})
_PERFIS_CRIAVEIS = frozenset({"VEREADOR", "CAMARA", "PROTOCOLO", "SECRETARIA", "GESTOR"})
_WRITE_BY_PERFIL = {
    "VEREADOR": UsuarioVereadorWriteSerializer,
    "CAMARA": UsuarioCamaraWriteSerializer,
    "PROTOCOLO": UsuarioProtocoloWriteSerializer,
    "SECRETARIA": UsuarioSecretariaWriteSerializer,
    "GESTOR": UsuarioGestorWriteSerializer,
}
_READ_BY_PERFIL = {
    "VEREADOR": UsuarioGestaoUnificadoSerializer,
    "CAMARA": UsuarioGestaoUnificadoSerializer,
    "PROTOCOLO": UsuarioGestaoUnificadoSerializer,
    "SECRETARIA": UsuarioGestaoSerializer,
    "GESTOR": UsuarioGestorSerializer,
}


def _pode_gerir_usuarios(user) -> bool:
    return gestor_pode_crud_admin(user)


def _pode_gerir_gestores(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and getattr(user, "perfil", None) == "GESTOR"
        and gestor_pode_crud_admin(user)
    )


class GestaoUsuarioSecretariaViewSet(viewsets.ModelViewSet):
    """CRUD de usuários SECRETARIA com órgão + setor(es) RM."""

    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = (
            Usuario.objects.filter(perfil="SECRETARIA")
            .prefetch_related("unidades_responsaveis__unidade")
            .order_by("first_name", "last_name", "username")
        )
        orgao_id = self.request.query_params.get("sinapse_orgao_id")
        if orgao_id:
            try:
                qs = qs.filter(sinapse_orgao_id=int(orgao_id))
            except (TypeError, ValueError):
                pass
        incompleto = self.request.query_params.get("incompleto")
        if incompleto in ("1", "true", "True"):
            from core.services.usuario_vinculo_service import UsuarioVinculoService

            service = UsuarioVinculoService()
            ids = [
                u.pk
                for u in qs
                if not service.status_vinculo_secretaria(u).get("completo")
            ]
            qs = qs.filter(pk__in=ids)
        return qs

    def get_serializer_class(self):
        if self.action in ("create", "partial_update", "update"):
            return UsuarioSecretariaWriteSerializer
        return UsuarioGestaoSerializer

    def list(self, request, *args, **kwargs):
        if not _pode_gerir_usuarios(request.user):
            return Response({"detail": "Acesso restrito."}, status=status.HTTP_403_FORBIDDEN)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        if not _pode_gerir_usuarios(request.user):
            return Response({"detail": "Acesso restrito."}, status=status.HTTP_403_FORBIDDEN)
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        if not _pode_gerir_usuarios(request.user):
            return Response({"detail": "Acesso restrito."}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = serializer.save()
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            UsuarioGestaoSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, *args, **kwargs):
        if not _pode_gerir_usuarios(request.user):
            return Response({"detail": "Acesso restrito."}, status=status.HTTP_403_FORBIDDEN)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            user = serializer.save()
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(UsuarioGestaoSerializer(user).data)


class GestaoUsuarioGestorViewSet(viewsets.ModelViewSet):
    """CRUD de usuários GESTOR com privilégios admin e referência institucional opcional."""

    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return (
            Usuario.objects.filter(perfil="GESTOR")
            .prefetch_related("unidades_responsaveis__unidade")
            .order_by("first_name", "last_name", "username")
        )

    def get_serializer_class(self):
        if self.action in ("create", "partial_update", "update"):
            return UsuarioGestorWriteSerializer
        return UsuarioGestorSerializer

    def list(self, request, *args, **kwargs):
        if not _pode_gerir_gestores(request.user):
            return Response({"detail": "Acesso restrito a gestores administradores."}, status=status.HTTP_403_FORBIDDEN)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        if not _pode_gerir_gestores(request.user):
            return Response({"detail": "Acesso restrito a gestores administradores."}, status=status.HTTP_403_FORBIDDEN)
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        if not _pode_gerir_gestores(request.user):
            return Response({"detail": "Acesso restrito a gestores administradores."}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = serializer.save()
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(UsuarioGestorSerializer(user).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        if not _pode_gerir_gestores(request.user):
            return Response({"detail": "Acesso restrito a gestores administradores."}, status=status.HTTP_403_FORBIDDEN)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            user = serializer.save()
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(UsuarioGestorSerializer(user).data)


class GestaoUsuarioViewSet(viewsets.ModelViewSet):
    """Hub unificado U5 — listagem e CRUD por perfil operacional."""

    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "head", "options"]
    serializer_class = UsuarioGestaoUnificadoSerializer
    pagination_class = OptInPageNumberPagination

    def get_queryset(self):
        qs = (
            Usuario.objects.exclude(perfil="ASSESSOR")
            .prefetch_related("unidades_responsaveis__unidade")
            .order_by("perfil", "first_name", "last_name", "username")
        )
        if getattr(self.request.user, "perfil", None) == "PROTOCOLO":
            qs = qs.exclude(perfil="GESTOR")

        perfil = (self.request.query_params.get("perfil") or "").strip().upper()
        if perfil:
            qs = qs.filter(perfil=perfil)

        busca = (self.request.query_params.get("q") or "").strip()
        if busca:
            qs = qs.filter(
                Q(username__icontains=busca)
                | Q(first_name__icontains=busca)
                | Q(last_name__icontains=busca)
                | Q(email__icontains=busca)
            )

        incompleto = self.request.query_params.get("incompleto")
        if incompleto in ("1", "true", "True"):
            from core.services.usuario_vinculo_service import UsuarioVinculoService

            service = UsuarioVinculoService()
            ids = []
            for u in qs:
                if u.perfil == "SECRETARIA" and not service.status_vinculo_secretaria(u).get("completo"):
                    ids.append(u.pk)
                elif u.perfil == "PROTOCOLO" and not service.status_vinculo_protocolo(u).get("completo"):
                    ids.append(u.pk)
                elif u.perfil == "GESTOR":
                    vg = service.status_vinculo_gestor(u)
                    if vg.get("tipo_gestor") == "GERAL" and not vg.get("admin_pleno"):
                        ids.append(u.pk)
            qs = qs.filter(pk__in=ids)
        return qs

    def _read_serializer(self, user: Usuario):
        cls = _READ_BY_PERFIL.get(user.perfil, UsuarioGestaoUnificadoSerializer)
        return cls(user)

    def _pode_acessar_instancia(self, user: Usuario, target: Usuario) -> bool:
        if target.perfil == "GESTOR":
            return _pode_gerir_gestores(user)
        return _pode_gerir_usuarios(user)

    def _pode_criar_perfil(self, user, perfil: str) -> bool:
        if perfil == "GESTOR":
            return _pode_gerir_gestores(user)
        return _pode_gerir_usuarios(user) and perfil in _PERFIS_CRIAVEIS

    def list(self, request, *args, **kwargs):
        if not _pode_gerir_usuarios(request.user):
            return Response({"detail": "Acesso restrito."}, status=status.HTTP_403_FORBIDDEN)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        if not _pode_gerir_usuarios(request.user):
            return Response({"detail": "Acesso restrito."}, status=status.HTTP_403_FORBIDDEN)
        instance = self.get_object()
        if not self._pode_acessar_instancia(request.user, instance):
            return Response({"detail": "Acesso restrito."}, status=status.HTTP_403_FORBIDDEN)
        return Response(self._read_serializer(instance).data)

    def create(self, request, *args, **kwargs):
        perfil = (request.data.get("perfil") or "").strip().upper()
        if perfil not in _WRITE_BY_PERFIL:
            return Response(
                {"detail": "Perfil inválido ou não permitido (use VEREADOR, PROTOCOLO, SECRETARIA ou GESTOR)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not self._pode_criar_perfil(request.user, perfil):
            return Response({"detail": "Sem permissão para criar este perfil."}, status=status.HTTP_403_FORBIDDEN)

        serializer_class = _WRITE_BY_PERFIL[perfil]
        serializer = serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = serializer.save()
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self._read_serializer(user).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        if not self._pode_acessar_instancia(request.user, instance):
            return Response({"detail": "Acesso restrito."}, status=status.HTTP_403_FORBIDDEN)

        serializer_class = _WRITE_BY_PERFIL.get(instance.perfil)
        if not serializer_class:
            return Response({"detail": "Perfil não editável."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = serializer_class(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            user = serializer.save()
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self._read_serializer(user).data)
