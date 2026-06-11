"""Testes C4 — hub de consultas."""

import importlib.util
import uuid

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Demanda, Usuario
from core.models_unidade_administrativa import UnidadeAdministrativa
from core.services.consulta_hub_service import ConsultaHubService

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class ConsultaHubServiceTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.suffix = uuid.uuid4().hex[:8]
        self.vereador = Usuario.objects.create_user(
            username=f"ver_hub_{self.suffix}", password="x", perfil="VEREADOR"
        )
        self.svc = ConsultaHubService()

    def test_atalhos_vereador_incluem_rascunhos(self):
        Demanda.objects.create(
            titulo="Rasc",
            descricao="x",
            autor=self.vereador,
            status="RASCUNHO",
        )
        atalhos = self.svc.atalhos(self.vereador)
        ids = {a["id"] for a in atalhos}
        self.assertIn("rascunhos", ids)
        rasc = next(a for a in atalhos if a["id"] == "rascunhos")
        self.assertGreaterEqual(rasc["contagem"], 1)
        self.assertEqual(rasc["rota"], "/demandas")

    def test_gestor_tem_atalhos_administrativos(self):
        gestor = Usuario.objects.create_user(
            username=f"ges_hub_{self.suffix}", password="x", perfil="GESTOR"
        )
        ids = {a["id"] for a in self.svc.atalhos(gestor)}
        self.assertIn("explorer", ids)
        self.assertIn("sla", ids)


class ConsultaHubAPITests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.suffix = uuid.uuid4().hex[:8]
        self.vereador = Usuario.objects.create_user(
            username=f"ver_api_{self.suffix}", password="x", perfil="VEREADOR"
        )
        self.gestor = Usuario.objects.create_user(
            username=f"ges_api_{self.suffix}", password="x", perfil="GESTOR"
        )

    def test_vereador_acessa_hub(self):
        self.client.force_authenticate(self.vereador)
        r = self.client.get("/api/consulta/hub/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["perfil"], "VEREADOR")
        self.assertTrue(len(r.data["atalhos"]) >= 3)

    def test_busca_curta_retorna_vazio(self):
        self.client.force_authenticate(self.gestor)
        r = self.client.get("/api/consulta/busca/", {"q": "a"})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["demandas"], [])

    def test_perfil_sem_acesso_recebe_403(self):
        assessor = Usuario.objects.create_user(
            username=f"ass_hub_{self.suffix}", password="x", perfil="ASSESSOR"
        )
        self.client.force_authenticate(assessor)
        r = self.client.get("/api/consulta/hub/")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
