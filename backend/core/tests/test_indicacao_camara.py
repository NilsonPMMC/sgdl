"""Testes — indicações legislativas (perfil CAMARA)."""

import uuid

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Demanda, DemandaVereadorVinculo, Notificacao
from core.services.indicacao_numeracao_service import IndicacaoNumeracaoService
from core.services.indicacao_service import (
    agregar_demandas_por_vereador,
    sincronizar_vinculos_vereador,
)
from core.services.notificacao_service import NotificacaoService
from core.models import Usuario

import importlib.util

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A


class IndicacaoNumeracaoServiceTests(TestCase):
    def test_formatar_e_proximo_numero(self):
        svc = IndicacaoNumeracaoService()
        cfg = svc.carregar_config()
        cfg.ultimo_numero = 122
        cfg.mascara = "IND nº {numero}/{ano}"
        cfg.save()
        sugerido = svc.proximo_numero_sugerido()
        self.assertEqual(sugerido["numero"], 123)
        self.assertIn("123", sugerido["protocolo_sugerido"])


class IndicacaoVinculoTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        suffix = uuid.uuid4().hex[:8]
        self.camara = Usuario.objects.create_user(
            username=f"cam_{suffix}", password="x", perfil="CAMARA"
        )
        self.vereador = Usuario.objects.create_user(
            username=f"ver_{suffix}", password="x", perfil="VEREADOR", first_name="João"
        )
        self.demanda = Demanda.objects.create(
            titulo="Indicação teste",
            descricao="Descrição",
            autor=self.camara,
            tipo_legislativo=Demanda.TIPO_LEGISLATIVO_INDICACAO,
            status="RASCUNHO",
        )

    def test_sincronizar_vereadores(self):
        sincronizar_vinculos_vereador(
            self.demanda,
            [self.vereador.pk],
            autor_vereador_id=self.vereador.pk,
        )
        self.assertEqual(self.demanda.vinculos_vereador.count(), 1)
        v = self.demanda.vinculos_vereador.first()
        self.assertEqual(v.papel, DemandaVereadorVinculo.PAPEL_AUTOR)


class IndicacaoNumeracaoAPITests(APITestCase):
    def setUp(self):
        suffix = uuid.uuid4().hex[:8]
        self.camara = Usuario.objects.create_user(
            username=f"cam_api_{suffix}", password="x", perfil="CAMARA"
        )
        self.gestor = Usuario.objects.create_user(
            username=f"ges_api_{suffix}", password="x", perfil="GESTOR"
        )

    def test_camara_acessa_numeracao(self):
        self.client.force_authenticate(self.camara)
        r = self.client.get("/api/indicacoes/numeracao/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("protocolo_sugerido", r.data)

    def test_vereador_nao_acessa_numeracao(self):
        vereador = Usuario.objects.create_user(
            username=f"ver_num_{uuid.uuid4().hex[:6]}",
            password="x",
            perfil="VEREADOR",
        )
        self.client.force_authenticate(vereador)
        r = self.client.get("/api/indicacoes/numeracao/")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_gestor_atualiza_ultimo_numero(self):
        self.client.force_authenticate(self.gestor)
        r = self.client.patch(
            "/api/indicacoes/numeracao/",
            {"ultimo_numero": 50},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["ultimo_numero"], 50)
        self.assertEqual(r.data["proximo_numero"], 51)


class IndicacaoMetricasNotificacaoTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        suffix = uuid.uuid4().hex[:8]
        self.camara = Usuario.objects.create_user(
            username=f"cam_not_{suffix}", password="x", perfil="CAMARA"
        )
        self.vereador = Usuario.objects.create_user(
            username=f"ver_not_{suffix}",
            password="x",
            perfil="VEREADOR",
            first_name="Maria",
        )
        self.demanda = Demanda.objects.create(
            titulo="Indicação métricas",
            descricao="x",
            autor=self.camara,
            tipo_legislativo=Demanda.TIPO_LEGISLATIVO_INDICACAO,
            status="PROTOCOLADO",
            protocolo_legislativo="45/2026",
            protocolo_executivo="2026-0001",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        sincronizar_vinculos_vereador(
            self.demanda,
            [self.vereador.pk],
            autor_vereador_id=self.vereador.pk,
        )

    def test_agregar_por_vereador_conta_vinculo_indicacao(self):
        status_aberto = ["PROTOCOLADO", "EM_EXECUCAO"]
        rows = agregar_demandas_por_vereador(Demanda.objects.all(), status_aberto)
        maria = next(
            (
                r
                for r in rows
                if (r.get("autor__first_name") or "").startswith("Maria")
            ),
            None,
        )
        self.assertIsNotNone(maria)
        self.assertGreaterEqual(maria["total"], 1)

    def test_notificacao_despacho_inicial_para_camara(self):
        svc = NotificacaoService()
        criadas = svc.notificar_despacho_inicial(self.demanda, orgao_nome="Secretaria X")
        self.assertGreaterEqual(criadas, 1)
        self.assertTrue(
            Notificacao.objects.filter(
                destinatario=self.camara, tipo="DESPACHO"
            ).exists()
        )


class IndicacaoVereadorVisibilidadeTests(SinapseCatalogTestMixin, APITestCase):
    """H-JUL-07 — vereador vinculado enxerga indicação em lista, dashboard e mapa."""

    def setUp(self):
        super().setUp()
        suffix = uuid.uuid4().hex[:8]
        self.camara = Usuario.objects.create_user(
            username=f"cam_vis_{suffix}", password="x", perfil="CAMARA"
        )
        self.vereador = Usuario.objects.create_user(
            username=f"ver_vis_{suffix}",
            password="x",
            perfil="VEREADOR",
            first_name="Ana",
        )
        self.demanda = Demanda.objects.create(
            titulo="Indicação vinculada",
            descricao="Endereço teste",
            autor=self.camara,
            tipo_legislativo=Demanda.TIPO_LEGISLATIVO_INDICACAO,
            status="PROTOCOLADO",
            protocolo_legislativo="88/2026",
            protocolo_executivo="2026-0088",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            logradouro="Rua Teste",
            bairro="Centro",
            latitude=-23.523,
            longitude=-46.18,
        )
        sincronizar_vinculos_vereador(
            self.demanda,
            [self.vereador.pk],
            autor_vereador_id=self.vereador.pk,
        )
        self.client.force_authenticate(self.vereador)

    def test_listagem_demandas_com_filtro_autor_inclui_indicacao_vinculada_hjul07(self):
        r = self.client.get("/api/demandas/", {"autor": self.vereador.pk})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        data = r.data
        rows = data.get("results", data) if isinstance(data, dict) else list(data)
        ids = [d["id"] for d in rows]
        self.assertIn(self.demanda.pk, ids)

    def test_dashboard_stats_conta_indicacao_vinculada_hjul07(self):
        r = self.client.get("/api/dashboard/stats/", {"autor": self.vereador.pk})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(r.data["kpis"]["total_demandas"], 1)

    def test_mapa_locations_inclui_indicacao_vinculada_hjul07(self):
        r = self.client.get("/api/demandas/locations/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        payload = r.data if isinstance(r.data, dict) else {}
        locations = payload.get("results", payload)
        ids = [loc["id"] for loc in locations]
        self.assertIn(self.demanda.pk, ids)


class IndicacaoConsultaHubAPITests(APITestCase):
    def setUp(self):
        suffix = uuid.uuid4().hex[:8]
        self.camara = Usuario.objects.create_user(
            username=f"cam_hub_{suffix}", password="x", perfil="CAMARA"
        )

    def test_camara_acessa_hub_consulta(self):
        self.client.force_authenticate(self.camara)
        r = self.client.get("/api/consulta/hub/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["perfil"], "CAMARA")
        ids = {a["id"] for a in r.data["atalhos"]}
        self.assertIn("nova", ids)
        self.assertIn("rascunhos", ids)
