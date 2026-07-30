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


class GeocodingLogradourosAPIView(APIView):
    """GET /api/v1/geocoding/logradouros/?q=...&bairro=... — autocomplete de vias (Mogi das Cruzes)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        termo = (request.query_params.get("q") or request.query_params.get("termo") or "").strip()
        bairro = (request.query_params.get("bairro") or "").strip() or None
        if len(termo) < 3:
            return Response(
                {"detail": "Informe ao menos 3 caracteres para buscar logradouros."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            limite = int(request.query_params.get("limit") or 8)
        except (TypeError, ValueError):
            limite = 8

        svc = GeocodingService()
        sugestoes = svc.buscar_sugestoes_logradouro(termo, bairro=bairro, limit=limite)
        return Response({"resultados": sugestoes, "total": len(sugestoes)})


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
        res = svc.resolver_endereco_geocode(logradouro, bairro, cep or None)
        if res.get("latitude") is None or res.get("longitude") is None:
            return Response(
                {
                    "latitude": res.get("latitude_bruta"),
                    "longitude": res.get("longitude_bruta"),
                    "fonte": res.get("fonte_bruta") or res.get("fonte") or "indisponivel",
                    "logradouro": res.get("logradouro"),
                    "bairro": res.get("bairro"),
                    "cep": res.get("cep"),
                    "persistivel": False,
                    "detail": (
                        "Endereço localizado de forma aproximada ou incompleta. "
                        "Informe logradouro e bairro para coordenadas utilizáveis no cluster."
                    ),
                },
                status=status.HTTP_200_OK,
            )
        return Response(
            {
                "latitude": round(float(res["latitude"]), 6),
                "longitude": round(float(res["longitude"]), 6),
                "fonte": res.get("fonte"),
                "logradouro": res.get("logradouro"),
                "bairro": res.get("bairro"),
                "cep": res.get("cep"),
                "persistivel": True,
            }
        )


class GeocodingReverseAPIView(APIView):
    """POST /api/v1/geocoding/reverse/ — endereço a partir de latitude/longitude."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            lat = round(float(request.data.get("latitude")), 6)
            lng = round(float(request.data.get("longitude")), 6)
        except (TypeError, ValueError):
            return Response(
                {"detail": "Informe latitude e longitude válidas."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        svc = GeocodingService()
        dados = svc.buscar_endereco_por_coordenadas(lat, lng)
        if not dados:
            return Response(
                {
                    "latitude": lat,
                    "longitude": lng,
                    "logradouro": None,
                    "bairro": None,
                    "cep": None,
                    "detail": "Não foi possível identificar o endereço neste ponto.",
                },
                status=status.HTTP_200_OK,
            )
        return Response(
            {
                "latitude": lat,
                "longitude": lng,
                "logradouro": dados.get("logradouro"),
                "bairro": dados.get("bairro"),
                "cep": dados.get("cep"),
            }
        )
