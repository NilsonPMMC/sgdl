"""API REST do Explorer da Carta de Serviços Sinapse."""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from integrations.services.carta_explorer_service import CartaExplorerService

_PERFIS_EXPLORER = frozenset({"VEREADOR", "GESTOR", "PROTOCOLO", "SECRETARIA"})


def _can_explore_carta(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and (getattr(user, "perfil", None) in _PERFIS_EXPLORER or user.is_staff)
    )


class CartaServicoListAPIView(APIView):
    """GET — busca paginada na carta (q, orgao_id, limit, offset)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _can_explore_carta(request.user):
            return Response(
                {"detail": "Sem permissão para consultar a carta de serviços."},
                status=status.HTTP_403_FORBIDDEN,
            )

        q = request.query_params.get("q", "")
        orgao_raw = request.query_params.get("orgao_id") or request.query_params.get(
            "secretaria_id"
        )
        orgao_id = None
        if orgao_raw is not None and str(orgao_raw).strip():
            try:
                orgao_id = int(orgao_raw)
            except ValueError:
                return Response(
                    {"detail": "Parâmetro orgao_id inválido."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            limit = int(request.query_params.get("limit", 40))
            offset = int(request.query_params.get("offset", 0))
        except ValueError:
            return Response(
                {"detail": "Parâmetros limit/offset inválidos."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = CartaExplorerService().buscar(
            q=q, orgao_id=orgao_id, limit=limit, offset=offset
        )
        return Response(data, status=status.HTTP_200_OK)


class CartaServicoDetailAPIView(APIView):
    """GET — ficha do serviço (prazo, documentos, órgão)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, servico_id: int):
        if not _can_explore_carta(request.user):
            return Response(
                {"detail": "Sem permissão para consultar a carta de serviços."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            sid = int(servico_id)
        except (TypeError, ValueError):
            return Response(
                {"detail": "ID do serviço inválido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        detalhe = CartaExplorerService().detalhe(sid)
        if not detalhe:
            return Response(
                {"detail": "Serviço não encontrado na carta Sinapse."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(detalhe, status=status.HTTP_200_OK)


class CartaSimularTriagemAPIView(APIView):
    """POST — simulação de triagem vetorial (embedding + top-K Sinapse)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _can_explore_carta(request.user):
            return Response(
                {"detail": "Sem permissão para simular triagem."},
                status=status.HTTP_403_FORBIDDEN,
            )

        texto = request.data.get("texto") or request.data.get("q") or ""
        top_k_raw = request.data.get("top_k", 5)
        try:
            top_k = int(top_k_raw)
        except (TypeError, ValueError):
            return Response(
                {"detail": "Parâmetro top_k inválido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        resultado = CartaExplorerService().simular_triagem(texto, top_k=top_k)
        http_status = status.HTTP_200_OK if resultado.get("ok") else status.HTTP_400_BAD_REQUEST
        return Response(resultado, status=http_status)
