"""API de vínculo carta otimizada ↔ setor (C2)."""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.services.carta_setor_service import CartaSetorService
from core.services.fluxo_protocolo_service import FluxoProtocoloService

_PERFIS = frozenset({"GESTOR", "PROTOCOLO"})


def _pode_gerir_carta_setor(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and (getattr(user, "perfil", None) in _PERFIS or user.is_staff)
    )


class CartaSetorViewSet(viewsets.ViewSet):
    """Gestão do vínculo serviço da carta → unidade administrativa."""

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"], url_path="carta")
    def carta(self, request):
        if not _pode_gerir_carta_setor(request.user):
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
        svc = CartaSetorService()
        payload["results"] = [
            svc.enriquecer_item_carta(item) for item in (payload.get("results") or [])
        ]
        return Response(payload)

    @action(detail=False, methods=["post"], url_path="upsert")
    def upsert(self, request):
        if not _pode_gerir_carta_setor(request.user):
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
        unidade_raw = request.data.get("unidade_administrativa_id")
        unidade_id = None
        if unidade_raw not in (None, "", "null"):
            try:
                unidade_id = int(unidade_raw)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "unidade_administrativa_id inválido."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        try:
            svc_obj = CartaSetorService().vincular(int(sid), unidade_id)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        item = {
            "sinapse_servico_id": int(sid),
            "titulo": svc_obj.titulo_otimizado,
            "orgao_id": None,
        }
        return Response(CartaSetorService().enriquecer_item_carta(item))
