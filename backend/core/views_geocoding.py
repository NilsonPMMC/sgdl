"""API de geocodificação (ViaCEP + Nominatim) para formulários do SGDL."""

from __future__ import annotations

import re

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .services.geocoding_service import GeocodingService


def _cep_limpo(cep: str | None) -> str:
    return re.sub(r"\D", "", cep or "")


class GeocodingCepAPIView(APIView):
    """GET /api/v1/geocoding/cep/?cep=08717180"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        cep = _cep_limpo(request.query_params.get("cep"))
        if len(cep) != 8:
            return Response(
                {"detail": "Informe um CEP com 8 dígitos."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        svc = GeocodingService()
        dados = svc.buscar_endereco_por_cep(cep)
        if not dados:
            return Response(
                {"detail": "CEP não encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"cep": cep, **dados})


class GeocodingResolverAPIView(APIView):
    """POST /api/v1/geocoding/resolver/ — coordenadas via GeocodingService."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        logradouro = (request.data.get("logradouro") or "").strip()
        bairro = (request.data.get("bairro") or "").strip()
        cep = _cep_limpo(request.data.get("cep"))

        if not logradouro and not bairro and len(cep) < 8:
            return Response(
                {"detail": "Informe CEP ou logradouro com bairro."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        svc = GeocodingService()
        lat, lng, fonte = svc.buscar_coordenadas_com_fonte(logradouro, bairro, cep or None)
        if lat is None or lng is None:
            return Response(
                {
                    "latitude": None,
                    "longitude": None,
                    "fonte": "indisponivel",
                    "detail": "Não foi possível localizar o endereço em Mogi das Cruzes.",
                },
                status=status.HTTP_200_OK,
            )
        return Response(
            {
                "latitude": round(float(lat), 6),
                "longitude": round(float(lng), 6),
                "fonte": fonte,
            }
        )
