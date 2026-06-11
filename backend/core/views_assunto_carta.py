"""API de assuntos temáticos e política de utilização (C5)."""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models_assunto_carta import AssuntoCarta
from core.serializers import AssuntoCartaSerializer
from core.services.carta_utilizacao_service import CartaUtilizacaoService
from core.services.fluxo_protocolo_service import FluxoProtocoloService

_PERFIS_GESTOR = frozenset({"GESTOR"})
_PERFIS_CARTA = frozenset({"GESTOR", "PROTOCOLO"})


def _pode_gestor(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and (getattr(user, "perfil", None) in _PERFIS_GESTOR or user.is_staff)
    )


def _pode_gerir_carta(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and (getattr(user, "perfil", None) in _PERFIS_CARTA or user.is_staff)
    )


class AssuntoCartaViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = AssuntoCartaSerializer
    queryset = AssuntoCarta.objects.filter(ativo=True).order_by("ordem", "nome")
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        qs = AssuntoCarta.objects.all().order_by("ordem", "nome")
        if self.action == "list" and self.request.query_params.get("todos") != "1":
            qs = qs.filter(ativo=True)
        return qs

    def list(self, request, *args, **kwargs):
        if not _pode_gerir_carta(request.user):
            return Response(
                {"detail": "Acesso restrito a Protocolo ou Gestor."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().list(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if not _pode_gestor(request.user):
            return Response(
                {"detail": "Acesso restrito ao Gestor."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().partial_update(request, *args, **kwargs)


class CartaAssuntoViewSet(viewsets.ViewSet):
    """Vínculo serviço → assunto + modo de utilização."""

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"], url_path="carta")
    def carta(self, request):
        if not _pode_gerir_carta(request.user):
            return Response(
                {"detail": "Acesso restrito a Protocolo ou Gestor."},
                status=status.HTTP_403_FORBIDDEN,
            )
        q = (request.query_params.get("q") or "").strip()
        orgao_id = request.query_params.get("orgao_id")
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
        util_svc = CartaUtilizacaoService()
        payload["results"] = [
            util_svc.enriquecer_item_carta(item) for item in (payload.get("results") or [])
        ]
        return Response(payload)

    @action(detail=False, methods=["post"], url_path="upsert")
    def upsert(self, request):
        if not _pode_gestor(request.user):
            return Response(
                {"detail": "Acesso restrito ao Gestor."},
                status=status.HTTP_403_FORBIDDEN,
            )
        sid = request.data.get("sinapse_servico_id")
        if not sid:
            return Response(
                {"detail": "sinapse_servico_id é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        assunto_raw = request.data.get("assunto_id")
        assunto_id = assunto_raw if "assunto_id" in request.data else None
        modo = request.data.get("modo_utilizacao_sgdl") if "modo_utilizacao_sgdl" in request.data else None
        msg = (
            request.data.get("mensagem_orientacao")
            if "mensagem_orientacao" in request.data
            else None
        )
        try:
            svc_obj = CartaUtilizacaoService().vincular(
                int(sid),
                assunto_id=assunto_id,
                modo_utilizacao_sgdl=modo,
                mensagem_orientacao=msg,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        item = {
            "sinapse_servico_id": int(sid),
            "titulo": svc_obj.titulo_otimizado,
        }
        return Response(CartaUtilizacaoService().enriquecer_item_carta(item))
