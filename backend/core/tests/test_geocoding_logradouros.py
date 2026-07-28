"""Testes do autocomplete de logradouros (B1)."""

from unittest.mock import patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Usuario
from core.services.geocoding_service import GeocodingService


class GeocodingLogradouroServiceTests(TestCase):
    def test_parse_sugestao_nominatim_mogi(self):
        item = {
            "lat": "-23.522",
            "lon": "-46.185",
            "address": {
                "road": "Rua Barão de Jaceguai",
                "suburb": "Centro",
                "postcode": "08710000",
                "city": "Mogi das Cruzes",
            },
        }
        parsed = GeocodingService._parse_sugestao_nominatim(item)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["logradouro"], "Rua Barão de Jaceguai")
        self.assertEqual(parsed["bairro"], "Centro")
        self.assertIn("Mogi das Cruzes", parsed["label"])

    def test_parse_rejeita_outra_cidade(self):
        item = {
            "lat": "-23.5",
            "lon": "-46.6",
            "address": {
                "road": "Av. Paulista",
                "city": "São Paulo",
            },
        }
        self.assertIsNone(GeocodingService._parse_sugestao_nominatim(item))

    @patch.object(GeocodingService, "_consultar_nominatim_lista")
    def test_buscar_sugestoes_deduplica(self, mock_lista):
        mock_lista.return_value = [
            {
                "lat": "-23.522",
                "lon": "-46.185",
                "address": {
                    "road": "Rua A",
                    "suburb": "Centro",
                    "city": "Mogi das Cruzes",
                },
            },
            {
                "lat": "-23.522",
                "lon": "-46.185",
                "address": {
                    "road": "Rua A",
                    "suburb": "Centro",
                    "city": "Mogi das Cruzes",
                },
            },
        ]
        svc = GeocodingService()
        resultados = svc.buscar_sugestoes_logradouro("Rua A")
        self.assertEqual(len(resultados), 1)


class GeocodingLogradourosAPITests(APITestCase):
    def setUp(self):
        self.user = Usuario.objects.create_user(username="geo_user", password="x", perfil="VEREADOR")
        self.client.force_authenticate(self.user)

    def test_requer_minimo_tres_caracteres(self):
        resp = self.client.get("/api/v1/geocoding/logradouros/", {"q": "ru"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch.object(GeocodingService, "buscar_sugestoes_logradouro")
    def test_lista_sugestoes(self, mock_buscar):
        mock_buscar.return_value = [
            {
                "label": "Rua Teste, Centro, Mogi das Cruzes",
                "logradouro": "Rua Teste",
                "bairro": "Centro",
                "cep": "08710-000",
                "latitude": -23.52,
                "longitude": -46.18,
            }
        ]
        resp = self.client.get("/api/v1/geocoding/logradouros/", {"q": "Rua Teste"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["total"], 1)
        self.assertEqual(resp.data["resultados"][0]["logradouro"], "Rua Teste")
        mock_buscar.assert_called_once()
