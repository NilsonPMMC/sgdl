"""Testes C5 — assuntos temáticos e política de utilização."""

import importlib.util

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from core.models_assunto_carta import AssuntoCarta, ModoUtilizacaoSgdl
from core.models_carta_otimizada import ServicoOtimizado
from core.services.carta_utilizacao_service import CartaUtilizacaoService

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_SERVICO_ID = _legacy.SINAPSE_SERVICO_ID
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class CartaUtilizacaoServiceTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.assunto_info = AssuntoCarta.objects.create(
            nome="Alvará teste",
            slug="alvara-teste",
            ordem=99,
            modo_utilizacao_sgdl=ModoUtilizacaoSgdl.INFORMATIVO,
            mensagem_orientacao="Orientação do assunto.",
        )
        ServicoOtimizado.objects.filter(sinapse_servico_id=SINAPSE_SERVICO_ID).delete()
        self.svc = ServicoOtimizado.objects.create(
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            titulo_otimizado="Certidão teste",
            descricao_objetiva="Desc",
            intencao_servico="",
            texto_rag_otimizado="texto",
            assunto=self.assunto_info,
        )

    def test_herda_modo_do_assunto(self):
        info = CartaUtilizacaoService().resolver(SINAPSE_SERVICO_ID)
        self.assertEqual(info["modo_efetivo"], ModoUtilizacaoSgdl.INFORMATIVO)
        self.assertEqual(info["heranca"], "ASSUNTO")
        self.assertTrue(info["somente_orientacao"])

    def test_desvincular_assunto(self):
        CartaUtilizacaoService().vincular(
            SINAPSE_SERVICO_ID,
            assunto_id=None,
            atualizar_assunto=True,
        )
        self.svc.refresh_from_db()
        self.assertIsNone(self.svc.assunto_id)
        info = CartaUtilizacaoService().resolver(SINAPSE_SERVICO_ID)
        self.assertIsNone(info["assunto_id"])
        self.assertEqual(info["heranca"], "GLOBAL")

    def test_override_por_servico(self):
        self.svc.modo_utilizacao_sgdl = ModoUtilizacaoSgdl.PROTOCOLAVEL
        self.svc.save(update_fields=["modo_utilizacao_sgdl"])
        info = CartaUtilizacaoService().resolver(SINAPSE_SERVICO_ID)
        self.assertEqual(info["modo_efetivo"], ModoUtilizacaoSgdl.PROTOCOLAVEL)
        self.assertEqual(info["heranca"], "SERVICO")

    def test_validar_protocolo_bloqueia_informativo(self):
        with self.assertRaises(ValueError):
            CartaUtilizacaoService().validar_protocolo(SINAPSE_SERVICO_ID)


class AssuntoCartaAPITests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.gestor = _legacy.Usuario.objects.create_user(
            username="gestor_assunto", password="x", perfil="GESTOR"
        )
        self.assunto = AssuntoCarta.objects.create(
            nome="Zeladoria teste API",
            slug="zeladoria-api",
            ordem=100,
            modo_utilizacao_sgdl=ModoUtilizacaoSgdl.PROTOCOLAVEL,
        )
        self.client.force_authenticate(self.gestor)

    def test_listar_assuntos(self):
        r = self.client.get("/api/assuntos-carta/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        payload = r.data if isinstance(r.data, list) else r.data.get("results", [])
        self.assertGreaterEqual(len(payload), 1)

    def test_upsert_classificacao_servico(self):
        ServicoOtimizado.objects.filter(sinapse_servico_id=SINAPSE_SERVICO_ID).delete()
        ServicoOtimizado.objects.create(
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            titulo_otimizado="Serviço API",
            descricao_objetiva="Desc",
            intencao_servico="",
            texto_rag_otimizado="texto",
        )
        r = self.client.post(
            "/api/carta-assuntos/upsert/",
            {
                "sinapse_servico_id": SINAPSE_SERVICO_ID,
                "assunto_id": self.assunto.pk,
                "modo_utilizacao_sgdl": "",
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("utilizacao_sgdl", r.data)
        self.assertEqual(r.data["utilizacao_sgdl"]["assunto_id"], self.assunto.pk)

    def test_upsert_remove_assunto_com_null(self):
        ServicoOtimizado.objects.filter(sinapse_servico_id=SINAPSE_SERVICO_ID).delete()
        ServicoOtimizado.objects.create(
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            titulo_otimizado="Serviço API",
            descricao_objetiva="Desc",
            intencao_servico="",
            texto_rag_otimizado="texto",
            assunto=self.assunto,
        )
        r = self.client.post(
            "/api/carta-assuntos/upsert/",
            {"sinapse_servico_id": SINAPSE_SERVICO_ID, "assunto_id": None},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIsNone(r.data["utilizacao_sgdl"]["assunto_id"])
