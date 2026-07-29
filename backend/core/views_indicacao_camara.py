"""API de numeração e configuração de indicações (Câmara)."""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models_config import NumeracaoIndicacaoCamara
from core.services.indicacao_numeracao_service import IndicacaoNumeracaoService


def _pode_configurar_indicacao(user) -> bool:
    perfil = getattr(user, "perfil", None)
    return perfil in ("CAMARA", "GESTOR")


class NumeracaoIndicacaoCamaraAPIView(APIView):
    """GET/PATCH — último número usado e máscara de formatação."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _pode_configurar_indicacao(request.user):
            return Response({"detail": "Sem permissão."}, status=status.HTTP_403_FORBIDDEN)
        svc = IndicacaoNumeracaoService()
        cfg = svc.carregar_config()
        sugerido = svc.proximo_numero_sugerido()
        return Response(
            {
                "ano": cfg.ano,
                "ultimo_numero": cfg.ultimo_numero,
                "mascara": cfg.mascara,
                "proximo_numero": sugerido["numero"],
                "protocolo_sugerido": sugerido["protocolo_sugerido"],
            }
        )

    def patch(self, request):
        if not _pode_configurar_indicacao(request.user):
            return Response({"detail": "Sem permissão."}, status=status.HTTP_403_FORBIDDEN)
        ultimo = request.data.get("ultimo_numero")
        if ultimo is None:
            return Response(
                {"detail": "Informe ultimo_numero."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            ultimo_int = int(ultimo)
        except (TypeError, ValueError):
            return Response(
                {"detail": "ultimo_numero inválido."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ano = request.data.get("ano")
        mascara = request.data.get("mascara")
        try:
            if getattr(request.user, "perfil", None) == "GESTOR":
                data = IndicacaoNumeracaoService().atualizar_ultimo_informado(
                    ultimo_int, ano=ano, mascara=mascara
                )
            else:
                data = IndicacaoNumeracaoService().atualizar_ultimo_informado(ultimo_int)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        cfg = NumeracaoIndicacaoCamara.carregar()
        return Response(
            {
                "ano": cfg.ano,
                "ultimo_numero": cfg.ultimo_numero,
                "mascara": cfg.mascara,
                "proximo_numero": data["numero"],
                "protocolo_sugerido": data["protocolo_sugerido"],
            }
        )
