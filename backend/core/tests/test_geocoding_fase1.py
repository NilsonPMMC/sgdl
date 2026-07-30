"""Fase 1 — normalização de endereço e gate de geocodificação para cluster."""

from unittest.mock import patch

from django.test import TestCase

from core.services.chatbot_service import ChatbotService
from core.services.endereco_normalizacao import (
    bairros_equivalentes,
    chave_endereco_canonica,
    coordenadas_elegiveis_cluster,
    endereco_resumo_humano,
    filtrar_coordenadas_para_persistencia,
    montar_alerta_geocode,
    normalizar_logradouro,
    variantes_tipo_via_logradouro,
)
from core.services.geocoding_service import GeocodingService


class EnderecoNormalizacaoTests(TestCase):
    def test_av_avenida_mesma_chave_canonica(self):
        a = chave_endereco_canonica(
            "Av. Francisco Ruiz", "Vila da Prata", None
        )
        b = chave_endereco_canonica(
            "Avenida Francisco Ruiz", "Vila da Prata", None
        )
        self.assertEqual(a, b)

    def test_normalizar_logradouro_expande_abreviacao(self):
        self.assertEqual(
            normalizar_logradouro("av. francisco ruiz"),
            "Avenida francisco ruiz",
        )

    def test_variantes_incluem_av_e_avenida(self):
        variantes = variantes_tipo_via_logradouro("Av. Francisco Ruiz")
        texto = " ".join(variantes).lower()
        self.assertIn("avenida", texto)
        self.assertIn("av.", texto)

    def test_bairros_equivalentes_vila(self):
        self.assertTrue(bairros_equivalentes("Vila da Prata", "Vl. da Prata"))

    def test_endereco_resumo_humano(self):
        resumo = endereco_resumo_humano(
            {"logradouro": "Av. Francisco Ruiz", "bairro": "Vila da Prata", "cep": "08717-180"}
        )
        self.assertIn("Avenida Francisco Ruiz", resumo)
        self.assertIn("Vila da Prata", resumo)
        self.assertIn("08717-180", resumo)

    def test_alerta_geocode_sem_lat_quando_endereco_informado(self):
        alerta = montar_alerta_geocode(
            logradouro="Avenida Francisco Ruiz",
            bairro="Vila da Prata",
            cep=None,
            latitude=None,
            longitude=None,
            endereco_informado=True,
        )
        self.assertIn("coordenadas precisas", alerta.lower())

    def test_alerta_geocode_ausente_com_coords(self):
        self.assertIsNone(
            montar_alerta_geocode(
                logradouro="Avenida X",
                bairro="Centro",
                cep=None,
                latitude=-23.57,
                longitude=-46.18,
                endereco_informado=True,
            )
        )

    def test_gate_rejeita_cep_aproximado_sem_bairro(self):
        lat, lng, fonte = filtrar_coordenadas_para_persistencia(
            -23.57, -46.18, "cep", "Avenida X", None
        )
        self.assertIsNone(lat)
        self.assertIsNone(lng)

    def test_gate_aceita_logradouro_e_bairro(self):
        lat, lng, fonte = filtrar_coordenadas_para_persistencia(
            -23.57,
            -46.18,
            "logradouro",
            "Avenida Francisco Ruiz",
            "Vila da Prata",
        )
        self.assertAlmostEqual(lat, -23.57, places=2)
        self.assertEqual(fonte, "logradouro")
        self.assertTrue(
            coordenadas_elegiveis_cluster(
                lat,
                lng,
                fonte,
                "Avenida Francisco Ruiz",
                "Vila da Prata",
            )
        )


class ExtrairEnderecoLivreFase1Tests(TestCase):
    def test_bairro_por_virgula_av_francisco_ruiz(self):
        ext = ChatbotService._extrair_endereco_livre(
            "Av. Francisco Ruiz, Vila da Prata"
        )
        self.assertEqual(ext.get("logradouro"), "Avenida Francisco Ruiz")
        self.assertEqual(ext.get("bairro"), "Vila da Prata")

    def test_bairro_por_virgula_avenida_completa(self):
        ext = ChatbotService._extrair_endereco_livre(
            "Avenida Francisco Ruiz, Vila da Prata"
        )
        self.assertEqual(ext.get("logradouro"), "Avenida Francisco Ruiz")
        self.assertEqual(ext.get("bairro"), "Vila da Prata")


class GeocodingServiceFase1Tests(TestCase):
    def setUp(self):
        from core.services import geocoding_service as geo_mod

        with geo_mod._nominatim_lock:
            geo_mod._geo_result_cache.clear()
            geo_mod._viacep_cache.clear()
            geo_mod._nominatim_backoff_until = 0.0

    @patch.object(GeocodingService, "_consultar_nominatim")
    def test_cache_compartilhado_av_avenida(self, mock_nominatim):
        mock_nominatim.return_value = (-23.572229, -46.185545)
        svc = GeocodingService()

        lat1, lng1, _ = svc.buscar_coordenadas(
            "Av. Francisco Ruiz", "Vila da Prata", None
        )
        lat2, lng2, _ = svc.buscar_coordenadas(
            "Avenida Francisco Ruiz", "Vila da Prata", None
        )

        self.assertAlmostEqual(lat1, lat2, places=6)
        self.assertAlmostEqual(lng1, lng2, places=6)
        self.assertEqual(mock_nominatim.call_count, 1)

    @patch.object(GeocodingService, "buscar_endereco_por_coordenadas")
    @patch.object(GeocodingService, "buscar_coordenadas_com_fonte")
    def test_resolver_endereco_geocode_enriquece_e_filtra(
        self, mock_buscar, mock_reverse
    ):
        mock_buscar.return_value = (-23.572229, -46.185545, "logradouro")
        mock_reverse.return_value = None
        svc = GeocodingService()
        res = svc.resolver_endereco_geocode(
            "Av. Francisco Ruiz", "Vila da Prata", None
        )
        self.assertEqual(res["logradouro"], "Avenida Francisco Ruiz")
        self.assertEqual(res["bairro"], "Vila da Prata")
        self.assertIsNotNone(res["latitude"])
        self.assertEqual(res["fonte"], "logradouro")

    @patch.object(GeocodingService, "buscar_coordenadas_com_fonte")
    def test_resolver_descarta_fonte_cep_aproximada(self, mock_buscar):
        mock_buscar.return_value = (-23.531866, -46.192145, "cep")
        svc = GeocodingService()
        res = svc.resolver_endereco_geocode("Rua X", "Centro", "08717-180")
        self.assertIsNone(res["latitude"])
        self.assertIsNone(res["longitude"])
