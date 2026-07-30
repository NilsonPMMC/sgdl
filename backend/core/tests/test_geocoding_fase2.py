"""Fase 2 — autocomplete Copiloto, reverse geocode e confirmação explícita."""

from unittest.mock import patch

from django.test import TestCase

from core.models import ChatSession, Usuario
from core.services.chatbot_service import ChatbotService
from core.services.geocoding_service import GeocodingService


class GeocodingReverseFase2Tests(TestCase):
    @patch.object(GeocodingService, "buscar_endereco_por_coordenadas")
    @patch.object(GeocodingService, "buscar_coordenadas_com_fonte")
    def test_resolver_enriquece_bairro_via_reverse(self, mock_buscar, mock_reverse):
        mock_buscar.return_value = (-23.572229, -46.185545, "logradouro")
        mock_reverse.return_value = {
            "logradouro": "Avenida Francisco Ruiz",
            "bairro": "Vila da Prata",
            "cep": "08717-180",
        }
        svc = GeocodingService()
        res = svc.resolver_endereco_geocode("Av. Francisco Ruiz", None, None)
        self.assertEqual(res["bairro"], "Vila da Prata")
        self.assertIsNotNone(res["latitude"])
        mock_reverse.assert_called_once()


class CopilotoEditarLocalFase2Tests(TestCase):
    def test_editar_local_nao_confirma_automaticamente(self):
        user = Usuario.objects.create_user(username="f2_loc", password="x", perfil="VEREADOR")
        session = ChatSession.objects.create(
            autor=user,
            estado_atual=ChatSession.ESTADO_COLETA_ENDERECO,
            demandas_rascunho=[
                {
                    "titulo": "Buraco",
                    "servico_confirmado_usuario": True,
                    "sinapse_servico_id_sugerido": 999002,
                    "endereco": {"logradouro": "Rua Antiga", "bairro": "Centro"},
                }
            ],
        )
        svc = ChatbotService()
        with patch.object(
            ChatbotService,
            "_resolver_coordenadas_item",
            return_value=(-23.55, -46.63, "logradouro"),
        ):
            with patch(
                "core.services.chatbot_service.sinapse_catalog.servico_existe",
                return_value=True,
            ):
                svc.editar_local_demanda(
                    usuario=user,
                    session_id=str(session.id),
                    indice_demanda=0,
                    endereco={"logradouro": "Av. Francisco Ruiz", "bairro": "Vila da Prata"},
                )
        session.refresh_from_db()
        item = session.demandas_rascunho[0]
        self.assertFalse(item.get("local_confirmado_usuario"))
        self.assertFalse(item.get("endereco_informado_usuario"))
        self.assertTrue(ChatbotService._item_tem_local_inferido_pendente(item))


class CopilotoColetaEnderecoFase2Tests(TestCase):
    def test_endereco_por_virgula_nao_e_apagado_antes_da_confirmacao(self):
        user = Usuario.objects.create_user(username="f2_av", password="x", perfil="VEREADOR")
        session = ChatSession.objects.create(
            autor=user,
            estado_atual=ChatSession.ESTADO_COLETA_ENDERECO,
            demandas_rascunho=[
                {
                    "titulo": "Tapa buraco na via",
                    "descricao": "buraco na rua",
                    "servico_confirmado_usuario": True,
                    "sinapse_servico_id_sugerido": 999002,
                    "endereco": {
                        "cep": None,
                        "logradouro": None,
                        "numero": None,
                        "bairro": None,
                        "complemento": None,
                    },
                }
            ],
        )
        svc = ChatbotService()
        rascunho = list(session.demandas_rascunho)
        with patch.object(
            ChatbotService,
            "_resolver_coordenadas_item",
            return_value=(-23.572229, -46.185545, "logradouro"),
        ):
            with patch(
                "core.services.chatbot_service.sinapse_catalog.servico_existe",
                return_value=True,
            ):
                ok = svc._processar_coleta_endereco_usuario(
                    rascunho, "av francisco ruiz, vila da prata"
                )
        self.assertTrue(ok)
        item = rascunho[0]
        end = item.get("endereco") or {}
        self.assertIn("francisco ruiz", (end.get("logradouro") or "").lower())
        self.assertIn("vila da prata", (end.get("bairro") or "").lower())
        self.assertIsNotNone(item.get("latitude"))
        self.assertFalse(item.get("local_confirmado_usuario"))
        self.assertFalse(item.get("endereco_informado_usuario"))
        msg = svc._mensagem_revisar_local_inferido(rascunho)
        self.assertIn("francisco ruiz", msg.lower())
        self.assertIn("confirmar local", msg.lower())
