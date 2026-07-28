"""API de gestão de fluxo Protocolo por serviço da carta."""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models_fluxo_protocolo import ServicoFluxoProtocolo
from core.serializers import ServicoFluxoProtocoloSerializer
from core.services.fluxo_protocolo_service import FluxoProtocoloService
from core.services.gestor_escopo import gestor_pode_crud_admin

_PERFIS = frozenset({"GESTOR", "PROTOCOLO"})


def _pode_gerir_fluxo(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and (
            getattr(user, "perfil", None) == "PROTOCOLO"
            or gestor_pode_crud_admin(user)
        )
    )


class ServicoFluxoProtocoloViewSet(viewsets.ModelViewSet):
    """CRUD de regras de despacho automático por serviço Sinapse."""

    permission_classes = [IsAuthenticated]
    serializer_class = ServicoFluxoProtocoloSerializer
    queryset = ServicoFluxoProtocolo.objects.all().order_by("sinapse_servico_id")
    http_method_names = ["get", "post", "patch", "head", "options"]

    def list(self, request, *args, **kwargs):
        if not _pode_gerir_fluxo(request.user):
            return Response(
                {"detail": "Acesso restrito a Protocolo ou Gestor."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        if not _pode_gerir_fluxo(request.user):
            return Response(
                {"detail": "Acesso restrito a Protocolo ou Gestor."},
                status=status.HTTP_403_FORBIDDEN,
            )
        sid = request.data.get("sinapse_servico_id")
        modo = request.data.get("modo", ServicoFluxoProtocolo.MODO_MANUAL)
        if not sid:
            return Response(
                {"detail": "sinapse_servico_id é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            obj = FluxoProtocoloService().upsert_config(
                sinapse_servico_id=int(sid),
                modo=str(modo),
                ativo=bool(request.data.get("ativo", True)),
                observacoes=str(request.data.get("observacoes") or ""),
                usuario=request.user,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            ServicoFluxoProtocoloSerializer(obj).data,
            status=status.HTTP_200_OK,
        )

    def partial_update(self, request, *args, **kwargs):
        if not _pode_gerir_fluxo(request.user):
            return Response(
                {"detail": "Acesso restrito a Protocolo ou Gestor."},
                status=status.HTTP_403_FORBIDDEN,
            )
        obj = self.get_object()
        modo = request.data.get("modo", obj.modo)
        try:
            atualizado = FluxoProtocoloService().upsert_config(
                sinapse_servico_id=int(obj.sinapse_servico_id),
                modo=str(modo),
                ativo=bool(request.data.get("ativo", obj.ativo)),
                observacoes=str(request.data.get("observacoes", obj.observacoes)),
                usuario=request.user,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ServicoFluxoProtocoloSerializer(atualizado).data)

    @action(detail=False, methods=["get"], url_path="carta")
    def carta(self, request):
        if not _pode_gerir_fluxo(request.user):
            return Response(
                {"detail": "Acesso restrito a Protocolo ou Gestor."},
                status=status.HTTP_403_FORBIDDEN,
            )
        q = (request.query_params.get("q") or "").strip()
        orgao_id = request.query_params.get("orgao_id")
        page_param = request.query_params.get("page")
        page_size_param = request.query_params.get("page_size")
        if page_param is not None or page_size_param is not None:
            try:
                page_size = min(int(page_size_param or 25), 100)
                page = max(int(page_param or 1), 1)
            except (TypeError, ValueError):
                page_size, page = 25, 1
            offset = (page - 1) * page_size
            limit = page_size
        else:
            try:
                limit = min(int(request.query_params.get("limit", 200)), 500)
            except (TypeError, ValueError):
                limit = 200
            try:
                offset = max(int(request.query_params.get("offset", 0)), 0)
            except (TypeError, ValueError):
                offset = 0
        orgao_int = None
        if orgao_id:
            try:
                orgao_int = int(orgao_id)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "orgao_id inválido."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        payload = FluxoProtocoloService().listar_carta_com_fluxo(
            q=q,
            orgao_id=orgao_int,
            limit=limit,
            offset=offset,
        )
        from core.services.carta_setor_service import CartaSetorService

        svc = CartaSetorService()
        payload["results"] = [
            svc.enriquecer_item_carta(item) for item in (payload.get("results") or [])
        ]
        total = int(payload.get("total") or len(payload.get("results") or []))
        payload["count"] = total
        return Response(payload)

    @action(detail=False, methods=["post"], url_path="upsert")
    def upsert(self, request):
        if not _pode_gerir_fluxo(request.user):
            return Response(
                {"detail": "Acesso restrito a Protocolo ou Gestor."},
                status=status.HTTP_403_FORBIDDEN,
            )
        sid = request.data.get("sinapse_servico_id")
        if not sid:
            return Response(
                {"detail": "sinapse_servico_id é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            obj = FluxoProtocoloService().upsert_config(
                sinapse_servico_id=int(sid),
                modo=str(
                    request.data.get("modo", ServicoFluxoProtocolo.MODO_MANUAL)
                ),
                ativo=bool(request.data.get("ativo", True)),
                observacoes=str(request.data.get("observacoes") or ""),
                usuario=request.user,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ServicoFluxoProtocoloSerializer(obj).data)
