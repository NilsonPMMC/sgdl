"""Copiloto — indicações com classificação semântica alinhada a ofícios."""

import importlib.util
import uuid
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from core.models import ChatSession, Demanda, Usuario
from core.services.chatbot_service import ChatbotService
from core.services.indicacao_numeracao_service import IndicacaoNumeracaoService

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin
SINAPSE_SERVICO_ID = _legacy.SINAPSE_SERVICO_ID


class CopilotoIndicacaoVinculoTests(SimpleTestCase):
    def test_indicacao_sem_vinculo_nao_esta_resolvida(self):
        item = {"modo_indicacao": True, "titulo": "Manutenção viária"}
        self.assertFalse(ChatbotService._item_vinculo_catalogo_resolvido(item))

    def test_indicacao_entra_na_fila_sem_servico_confirmado(self):
        svc = ChatbotService()
        rascunho = [{"modo_indicacao": True, "titulo": "Indicação teste"}]
        self.assertEqual(svc._indices_demandas_sem_servico_confirmado(rascunho), [0])

    @override_settings(
        COPILOTO_TENDENCIAS_ENABLED=True,
        COPILOTO_CARTA_SCORE_MINIMO=0.6666,
        COPILOTO_CARTA_SCORE_DOMINIO=0.40,
    )
    def test_nivelamento_indicacao_classifica_carta_forte(self):
        texto = (
            "nivelamento e cascalhamento na Estrada Municipal Katsuji Kitaguchi, "
            "no bairro Cocuera"
        )
        item = {
            "modo_indicacao": True,
            "titulo": "Nivelamento e cascalhamento na Estrada Municipal Katsuji Kitaguchi",
            "descricao": texto,
            "texto_para_embedding": texto,
            "candidatos_sinapse": [
                {
                    "servico_id": 127,
                    "titulo": "Limpeza de Valetas e Córregos",
                    "score": 0.8955,
                },
                {
                    "servico_id": 86,
                    "titulo": "Nivelamento e Cascalhamento",
                    "score": 0.7375,
                },
            ],
        }
        svc = ChatbotService()
        filtrados = ChatbotService._filtrar_candidatos_para_ui(
            item["candidatos_sinapse"],
            texto_coerencia=svc._texto_coerencia_demanda(item),
        )
        self.assertEqual(len(filtrados), 1)
        self.assertEqual(filtrados[0]["servico_id"], 86)
        modo, _ = svc._classificar_modo_vinculo_servico(item)
        self.assertEqual(modo, "carta_forte")
        self.assertFalse(svc._item_sugere_trilha_tendencia(item))


class CopilotoIndicacaoMaterializacaoTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        suffix = uuid.uuid4().hex[:8]
        self.camara = Usuario.objects.create_user(
            username=f"cam_cop_{suffix}", password="x", perfil="CAMARA"
        )
        self.vereador = Usuario.objects.create_user(
            username=f"ver_cop_{suffix}",
            password="x",
            perfil="VEREADOR",
            first_name="Maria",
        )
        cfg = IndicacaoNumeracaoService().carregar_config()
        cfg.ultimo_numero = max(cfg.ultimo_numero, 100)
        cfg.save()

    @patch("core.services.carta_utilizacao_service.CartaUtilizacaoService.validar_protocolo")
    @patch("core.services.geocoding_service.GeocodingService")
    def test_materializar_indicacao_com_servico_carta(self, mock_geo_cls, mock_validar):
        mock_validar.return_value = None
        mock_geo_cls.return_value.geocode.return_value = None

        item = {
            "modo_indicacao": True,
            "titulo": "Nivelamento e cascalhamento",
            "descricao": "Solicita nivelamento e cascalhamento na via.",
            "numero_indicacao": 101,
            "vereadores_vinculados_ids": [self.vereador.pk],
            "autor_vereador_id": self.vereador.pk,
            "servico_confirmado_usuario": True,
            "sinapse_servico_id_sugerido": SINAPSE_SERVICO_ID,
            "servico_local_id": SINAPSE_SERVICO_ID,
            "origem_vinculo": Demanda.ORIGEM_VINCULO_CARTA,
        }
        session = ChatSession.objects.create(autor=self.camara, historico_mensagens=[])
        svc = ChatbotService()
        criada = svc._materializar_demanda_indicacao(
            self.camara,
            item,
            texto_sessao="nivelamento e cascalhamento",
            geocoder=mock_geo_cls.return_value,
            session=session,
            texto_item=item["descricao"],
        )
        self.assertIsNotNone(criada)
        d = criada["demanda"]
        self.assertEqual(d.tipo_legislativo, Demanda.TIPO_LEGISLATIVO_INDICACAO)
        self.assertEqual(d.sinapse_servico_id, SINAPSE_SERVICO_ID)
        self.assertEqual(d.origem_vinculo, Demanda.ORIGEM_VINCULO_CARTA)

    def test_materializar_indicacao_sem_vinculo_bloqueada(self):
        item = {
            "modo_indicacao": True,
            "titulo": "Pedido genérico",
            "descricao": "Solicitação ampla.",
            "numero_indicacao": 102,
            "vereadores_vinculados_ids": [self.vereador.pk],
        }
        svc = ChatbotService()
        with patch("core.services.geocoding_service.GeocodingService") as mock_geo_cls:
            mock_geo_cls.return_value.geocode.return_value = None
            criada = svc._materializar_demanda_indicacao(
                self.camara,
                item,
                texto_sessao="pedido",
                geocoder=mock_geo_cls.return_value,
                session=None,
                texto_item=item["descricao"],
            )
        self.assertIsNone(criada)
