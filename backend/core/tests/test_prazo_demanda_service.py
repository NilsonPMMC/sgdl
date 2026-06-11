"""Testes C1 — resolução de prazo (ServicoOtimizado / Sinapse / padrão)."""

import uuid
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APITestCase

from core.models import Demanda, Usuario
from core.models_config import ConfiguracaoCarta
from core.models_carta_otimizada import ServicoOtimizado
from core.services.prazo_demanda_service import PrazoDemandaService

SINAPSE_SERVICO_ID = 1001


class PrazoDemandaServiceTests(TestCase):
    def setUp(self):
        self._suffix = uuid.uuid4().hex[:8]
        self._patch_orgao = patch(
            "core.models.sinapse_catalog.get_orgao_id_for_servico",
            return_value=None,
        )
        self._patch_prazo_sinapse = patch(
            "core.services.prazo_demanda_service.sinapse_catalog.prazo_dias",
            return_value=None,
        )
        self._patch_orgao.start()
        self._patch_prazo_sinapse.start()

        cfg = ConfiguracaoCarta.carregar()
        cfg.prazo_padrao_dias = 30
        cfg.politica_prazo = ConfiguracaoCarta.POLITICA_SERVICO_COM_FALLBACK
        cfg.save()

        self.vereador = Usuario.objects.create_user(
            username=f"ver_prazo_{self._suffix}",
            password="x",
            perfil="VEREADOR",
        )
        ServicoOtimizado.objects.filter(sinapse_servico_id=SINAPSE_SERVICO_ID).delete()
        self.svc = PrazoDemandaService()

    def tearDown(self):
        self._patch_prazo_sinapse.stop()
        self._patch_orgao.stop()
        cfg = ConfiguracaoCarta.carregar()
        cfg.prazo_padrao_dias = 30
        cfg.politica_prazo = ConfiguracaoCarta.POLITICA_SERVICO_COM_FALLBACK
        cfg.save()

        self.vereador = Usuario.objects.create_user(
            username="ver_prazo", password="x", perfil="VEREADOR"
        )
        ServicoOtimizado.objects.filter(sinapse_servico_id=SINAPSE_SERVICO_ID).delete()
        self.svc = PrazoDemandaService()

    def test_fallback_padrao_sem_servico(self):
        demanda = Demanda.objects.create(
            titulo="Tendência sem carta",
            descricao="x",
            autor=self.vereador,
            status="PROTOCOLADO",
            sinapse_servico_id=None,
        )
        res = self.svc.resolver_demanda(demanda)
        self.assertEqual(res.dias, 30)
        self.assertEqual(res.origem, Demanda.PRAZO_ORIGEM_PADRAO)

    def test_servico_otimizado_prioridade(self):
        ServicoOtimizado.objects.create(
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            titulo_otimizado="Tapa buraco",
            descricao_objetiva="Reparo",
            texto_rag_otimizado="tapa buraco",
            prazo_dias=15,
            ativo=True,
        )
        demanda = Demanda.objects.create(
            titulo="Buraco",
            descricao="x",
            autor=self.vereador,
            status="RASCUNHO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
        )
        res = self.svc.resolver_demanda(demanda)
        self.assertEqual(res.dias, 15)
        self.assertEqual(res.origem, Demanda.PRAZO_ORIGEM_SERVICO)
        self.assertEqual(res.origem_detalhe, "CARTA")

    def test_politica_servico_sem_fallback(self):
        cfg = ConfiguracaoCarta.carregar()
        cfg.politica_prazo = ConfiguracaoCarta.POLITICA_SERVICO
        cfg.save()
        demanda = Demanda.objects.create(
            titulo="Sem prazo",
            descricao="x",
            autor=self.vereador,
            status="RASCUNHO",
            sinapse_servico_id=999999,
        )
        res = self.svc.resolver_demanda(demanda)
        self.assertIsNone(res.dias)
        self.assertEqual(res.origem, Demanda.PRAZO_ORIGEM_INDEFINIDO)

    def test_snapshot_protocolo(self):
        ServicoOtimizado.objects.create(
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            titulo_otimizado="Serv",
            descricao_objetiva="d",
            texto_rag_otimizado="rag",
            prazo_dias=20,
            ativo=True,
        )
        demanda = Demanda.objects.create(
            titulo="Snap",
            descricao="x",
            autor=self.vereador,
            status="AGUARDANDO_PROTOCOLO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
        )
        self.svc.aplicar_snapshot_protocolo(demanda)
        demanda.save(update_fields=["prazo_efetivo_dias", "prazo_origem"])
        demanda.refresh_from_db()
        self.assertEqual(demanda.prazo_efetivo_dias, 20)
        self.assertEqual(demanda.prazo_origem, Demanda.PRAZO_ORIGEM_SERVICO)
        self.assertEqual(demanda.prazo_dias(), 20)


class ConfiguracaoCartaAPITests(APITestCase):
    def setUp(self):
        suffix = uuid.uuid4().hex[:8]
        self.gestor = Usuario.objects.create_user(
            username=f"ges_carta_{suffix}", password="x", perfil="GESTOR"
        )
        self.vereador = Usuario.objects.create_user(
            username=f"ver_carta_{suffix}", password="x", perfil="VEREADOR"
        )

    def test_gestor_atualiza_config(self):
        self.client.force_authenticate(self.gestor)
        r = self.client.patch(
            "/api/configuracao-carta/",
            {"prazo_padrao_dias": 45, "politica_prazo": "PADRAO"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["prazo_padrao_dias"], 45)
        self.assertEqual(r.data["politica_prazo"], "PADRAO")

    def test_vereador_nao_acessa(self):
        self.client.force_authenticate(self.vereador)
        r = self.client.get("/api/configuracao-carta/")
        self.assertEqual(r.status_code, 403)
