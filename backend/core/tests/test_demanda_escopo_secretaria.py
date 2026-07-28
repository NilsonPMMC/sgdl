"""Testes de isolamento RBAC — perfil SECRETARIA (A5)."""

import importlib.util

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Demanda, Usuario
from core.services.demanda_visibilidade import (
    aplicar_escopo_demanda,
    usuario_pode_acessar_demanda,
)

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_ORGAO_B = _legacy.SINAPSE_ORGAO_B
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class DemandaEscopoSecretariaTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.vereador = Usuario.objects.create_user(
            username="ver_escopo", password="x", perfil="VEREADOR"
        )
        self.sec_a = Usuario.objects.create_user(
            username="sec_a",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        self.sec_b = Usuario.objects.create_user(
            username="sec_b",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_B,
        )
        self.gestor = Usuario.objects.create_user(
            username="gestor_escopo", password="x", perfil="GESTOR"
        )
        self.dem_a = Demanda.objects.create(
            titulo="Demanda org A",
            descricao="x",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        self.dem_b = Demanda.objects.create(
            titulo="Demanda org B",
            descricao="x",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_orgao_id=SINAPSE_ORGAO_B,
        )

    def test_secretaria_a_ve_apenas_org_a(self):
        qs = aplicar_escopo_demanda(Demanda.objects.all(), self.sec_a)
        ids = set(qs.values_list("pk", flat=True))
        self.assertEqual(ids, {self.dem_a.pk})

    def test_secretaria_b_ve_apenas_org_b(self):
        qs = aplicar_escopo_demanda(Demanda.objects.all(), self.sec_b)
        ids = set(qs.values_list("pk", flat=True))
        self.assertEqual(ids, {self.dem_b.pk})

    def test_gestor_ve_todas(self):
        qs = aplicar_escopo_demanda(Demanda.objects.all(), self.gestor)
        self.assertEqual(qs.count(), 2)

    def test_secretaria_sem_orgao_nao_ve_nada(self):
        sec = Usuario.objects.create_user(
            username="sec_sem_org",
            password="x",
            perfil="SECRETARIA",
        )
        qs = aplicar_escopo_demanda(Demanda.objects.all(), sec)
        self.assertEqual(qs.count(), 0)

    def test_usuario_pode_acessar_demanda(self):
        self.assertTrue(usuario_pode_acessar_demanda(self.sec_a, self.dem_a))
        self.assertFalse(usuario_pode_acessar_demanda(self.sec_a, self.dem_b))
        self.assertTrue(usuario_pode_acessar_demanda(self.gestor, self.dem_b))

    def test_secretaria_ve_demanda_com_no_operacional_aberto(self):
        from core.models_no_operacional import NoOperacional, StatusNoOperacional

        NoOperacional.objects.create(
            demanda=self.dem_a,
            sinapse_orgao_id=SINAPSE_ORGAO_B,
            status=StatusNoOperacional.ABERTO,
        )
        qs = aplicar_escopo_demanda(Demanda.objects.all(), self.sec_b)
        self.assertIn(self.dem_a.pk, set(qs.values_list("pk", flat=True)))
        self.assertTrue(usuario_pode_acessar_demanda(self.sec_b, self.dem_a))


class DemandaEscopoSecretariaAPITests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.vereador = Usuario.objects.create_user(
            username="ver_api_escopo", password="x", perfil="VEREADOR"
        )
        self.sec_a = Usuario.objects.create_user(
            username="sec_api_a",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        self.dem_a = Demanda.objects.create(
            titulo="Demanda A",
            descricao="x",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        self.dem_b = Demanda.objects.create(
            titulo="Demanda B",
            descricao="x",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_orgao_id=SINAPSE_ORGAO_B,
        )

    def test_listagem_api_isolada_por_orgao(self):
        self.client.force_authenticate(self.sec_a)
        r = self.client.get("/api/demandas/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = {item["id"] for item in r.data}
        self.assertEqual(ids, {self.dem_a.pk})

    def test_detalhe_outro_orgao_retorna_404(self):
        self.client.force_authenticate(self.sec_a)
        r = self.client.get(f"/api/demandas/{self.dem_b.pk}/")
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_detalhe_super_os_com_no_scatter_nao_filtra_lider_listagem(self):
        """Seguidora com nó scatter visível: retrieve OK mesmo oculta na listagem."""
        from core.models import ClusterExecucao
        from core.models_no_operacional import NoOperacional, StatusNoOperacional

        cluster = ClusterExecucao.objects.create(
            titulo="Super OS escopo",
            status="EM_ANDAMENTO",
            sinapse_servico_id=self.dem_a.sinapse_servico_id,
        )
        seguidora = Demanda.objects.create(
            titulo="Seguidora",
            descricao="x",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            protocolo_legislativo="OF-S",
            cluster=cluster,
        )
        lider = Demanda.objects.create(
            titulo="Líder protocolada",
            descricao="x",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            protocolo_legislativo="OF-L",
            protocolo_executivo="2026-0100",
            fluxo_roteamento="FLUXO_TRANSVERSAL",
            nos_ativos=1,
            cluster=cluster,
        )
        NoOperacional.objects.create(
            demanda=lider,
            sinapse_orgao_id=SINAPSE_ORGAO_B,
            status=StatusNoOperacional.ABERTO,
        )
        self.client.force_authenticate(self.sec_b)
        r_list = self.client.get("/api/demandas/")
        ids_list = {item["id"] for item in r_list.data}
        self.assertIn(lider.pk, ids_list)
        self.assertNotIn(seguidora.pk, ids_list)
        r_det = self.client.get(f"/api/demandas/{lider.pk}/")
        self.assertEqual(r_det.status_code, status.HTTP_200_OK)

    def test_dashboard_isolado_por_orgao(self):
        self.client.force_authenticate(self.sec_a)
        r = self.client.get("/api/dashboard/stats/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["kpis"]["total_demandas"], 1)
