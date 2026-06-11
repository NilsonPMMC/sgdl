"""Validação pública de assinatura eletrônica."""

from django.http import HttpResponse
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.services.assinatura_eletronica_service import AssinaturaEletronicaService


class ValidarAssinaturaAPIView(APIView):
    """GET /api/v1/validar-assinatura/<codigo>/ — consulta pública."""

    permission_classes = [AllowAny]

    def get(self, request, codigo=None):
        payload = AssinaturaEletronicaService().validar_codigo(codigo or "")
        if payload is None:
            return Response(
                {"valido": False, "detail": "Assinatura não encontrada ou código inválido."},
                status=404,
            )
        if request.query_params.get("format") == "qr":
            png = AssinaturaEletronicaService().gerar_qr_png_bytes(payload["codigo_validacao"])
            return HttpResponse(png, content_type="image/png")
        return Response(payload)
