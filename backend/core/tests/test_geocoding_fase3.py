"""Fase 3 — cache local de vias, parsing LLM e fuzzy bairro."""

from unittest.mock import patch

from django.test import TestCase, override_settings

from core.models import ChatSession, Usuario
from core.models_via_referencia import ViaReferenciaMogi
from core.services.chatbot_service import ChatbotService
from core.services.endereco_normalizacao import bairros_equivalentes
from core.services.endereco_parsing_service import EnderecoParsingService
from core.services.geocoding_service import GeocodingService
from core.services.via_referencia_service import ViaReferenciaService


class BairroFuzzyFase3Tests(TestCase):
    def test_bairros_fuzzy_vila_prata(self):
        self.assertTrue(
            bairros_equivalentes("Vila da Prata", "Vila da Prata", fuzzy_threshold=90)
        )

    @override_settings(GEOCODING_BAIRRO_FUZZY_THRESHOLD=85)
    def test_bairros_fuzzy_typo_leve(self):
        self.assertTrue(bairros_equivalentes("Jardim Armênia", "Jardim Armenia"))


class ViaReferenciaFase3Tests(TestCase):
    def setUp(self):
        ViaReferenciaMogi.objects.create(
            logradouro="Avenida Francisco Ruiz",
            bairro="Vila da Prata",
            chave_canonica=GeocodingService.chave_endereco(
                "Avenida Francisco Ruiz", "Vila da Prata", None
            ),
            latitude=-23.572229,
            longitude=-46.185545,
            origem=ViaReferenciaMogi.ORIGEM_SEED,
            ativo=True,
        )

    @override_settings(GEOCODING_VIA_REFERENCIA_ENABLED=True)
    @patch.object(GeocodingService, "_consultar_nominatim")
    def test_buscar_coordenadas_usa_cache_local(self, mock_nominatim):
        mock_nominatim.return_value = (None, None)
        svc = GeocodingService()
        lat, lng, fonte = svc.buscar_coordenadas(
            "Av. Francisco Ruiz", "Vila da Prata", None
        )
        self.assertAlmostEqual(lat, -23.572229, places=5)
        self.assertEqual(fonte, "via_referencia_local")
        mock_nominatim.assert_not_called()


class EnderecoLlmParsingFase3Tests(TestCase):
    @override_settings(GEOCODING_LLM_PARSING_ENABLED=True, GROQ_API_KEY="test")
    def test_enriquecer_com_llm_preenche_bairro(self):
        base = {"logradouro": "Avenida Francisco Ruiz", "bairro": None, "cep": None}
        llm_out = {"logradouro": None, "bairro": "Vila da Prata", "cep": None}
        svc = EnderecoParsingService()
        with patch.object(svc, "_extrair_llm", return_value=llm_out):
            merged = svc.enriquecer_com_llm(base, "buraco na av francisco ruiz, vila da prata")
        self.assertEqual(merged.get("bairro"), "Vila da Prata")

    @override_settings(GEOCODING_LLM_PARSING_ENABLED=False)
    def test_llm_desligado_mantem_regex(self):
        ext = ChatbotService._extrair_endereco_livre(
            "Av. Francisco Ruiz, Vila da Prata"
        )
        self.assertEqual(ext.get("bairro"), "Vila da Prata")


class EnderecoLlmParsingIntegracaoTests(TestCase):
    @override_settings(GEOCODING_LLM_PARSING_ENABLED=True, GROQ_API_KEY="test")
    def test_extrair_endereco_livre_chama_llm_quando_incompleto(self):
        def _fake_enriquecer(self, base, texto):
            return {**base, "bairro": "Vila da Prata"}

        with patch.object(
            EnderecoParsingService,
            "enriquecer_com_llm",
            _fake_enriquecer,
        ):
            ext = ChatbotService._extrair_endereco_livre(
                "buraco na francisco ruiz proximo a padaria"
            )
        self.assertEqual(ext.get("bairro"), "Vila da Prata")


class EnderecoAbreviacaoCopilotoTests(TestCase):
    @override_settings(GEOCODING_LLM_PARSING_ENABLED=False)
    def test_r_e_inicial_jose_pq_santana(self):
        ext = ChatbotService._extrair_endereco_livre(
            "r maestro laurindo j gonçalves, pq santana"
        )
        self.assertIn("Rua", ext.get("logradouro") or "")
        self.assertIn("José", ext.get("logradouro") or "")
        self.assertIn("Parque", ext.get("bairro") or "")

    @override_settings(GEOCODING_LLM_PARSING_ENABLED=False)
    def test_coleta_endereco_nao_confirma_automaticamente(self):
        user = Usuario.objects.create_user(username="loc_abbr", password="x", perfil="VEREADOR")
        session = ChatSession.objects.create(
            autor=user,
            estado_atual=ChatSession.ESTADO_COLETA_ENDERECO,
            demandas_rascunho=[
                {
                    "titulo": "Buraco",
                    "servico_confirmado_usuario": True,
                    "sinapse_servico_id_sugerido": 999002,
                    "requer_localizacao": True,
                }
            ],
        )
        svc = ChatbotService()
        with patch.object(
            ChatbotService,
            "_resolver_coordenadas_item",
            return_value=(None, None, "indisponivel"),
        ):
            ok = svc._processar_coleta_endereco_usuario(
                session.demandas_rascunho,
                "r maestro laurindo j gonçalves, pq santana",
            )
        self.assertTrue(ok)
        item = session.demandas_rascunho[0]
        self.assertFalse(item.get("local_confirmado_usuario"))
        self.assertFalse(svc._rascunho_tem_endereco_suficiente(session.demandas_rascunho))
    def test_registrar_cria_chave_canonica(self):
        obj = ViaReferenciaService().registrar(
            logradouro="Av. Francisco Ruiz",
            bairro="Vl. da Prata",
            latitude=-23.572229,
            longitude=-46.185545,
            origem=ViaReferenciaMogi.ORIGEM_SEED,
        )
        self.assertIsNotNone(obj)
        self.assertEqual(obj.logradouro, "Avenida Francisco Ruiz")
        self.assertEqual(obj.bairro, "Vila da Prata")
