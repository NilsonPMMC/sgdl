"""Paginação opt-in em listagens administrativas."""

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from core.models_unidade_administrativa import UnidadeAdministrativa
import importlib.util

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin

User = get_user_model()


class AdminListPaginationTests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.gestor = User.objects.create_user(
            username="gestor_pag",
            password="x",
            perfil="GESTOR",
        )
        self.client.force_authenticate(self.gestor)
        for i in range(3):
            UnidadeAdministrativa.objects.create(
                sinapse_orgao_id=SINAPSE_ORGAO_A,
                nome=f"Setor {i}",
                sigla=f"S{i}",
                ativo=True,
            )

    def test_unidades_sem_page_retorna_lista_plana(self):
        r = self.client.get("/api/unidades-administrativas/", {"incluir_inativos": "1"})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIsInstance(r.data, list)

    def test_unidades_com_page_retorna_paginado(self):
        r = self.client.get(
            "/api/unidades-administrativas/",
            {"incluir_inativos": "1", "page": 1, "page_size": 2},
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["count"], 3)
        self.assertEqual(len(r.data["results"]), 2)

    def test_gestao_usuarios_paginado(self):
        User.objects.create_user(username="ver_pag", password="x", perfil="VEREADOR")
        r = self.client.get("/api/gestao-usuarios/", {"page": 1, "page_size": 1})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("count", r.data)
        self.assertEqual(len(r.data["results"]), 1)
