from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Usuario

import importlib.util

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class GestaoUsuarioUnificadoAPITests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.gestor = Usuario.objects.create_user(
            username="gest_u5",
            password="x",
            perfil="GESTOR",
            is_staff=True,
            is_superuser=True,
        )
        self.protocolo = Usuario.objects.create_user(
            username="prot_u5",
            password="x",
            perfil="PROTOCOLO",
        )
        Usuario.objects.create_user(username="ver_u5", password="x", perfil="VEREADOR")
        self.url = reverse("gestao-usuario-list")

    def test_lista_todos_perfis(self):
        self.client.force_authenticate(user=self.gestor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        perfis = {u["perfil"] for u in response.data}
        self.assertIn("VEREADOR", perfis)
        self.assertIn("GESTOR", perfis)

    def test_protocolo_nao_ve_gestores(self):
        self.client.force_authenticate(user=self.protocolo)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        perfis = {u["perfil"] for u in response.data}
        self.assertNotIn("GESTOR", perfis)

    def test_cria_vereador_sem_vinculo(self):
        self.client.force_authenticate(user=self.protocolo)
        response = self.client.post(
            self.url,
            {
                "perfil": "VEREADOR",
                "username": "novo_ver",
                "password": "senha123",
                "first_name": "Novo",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = Usuario.objects.get(username="novo_ver")
        self.assertEqual(user.perfil, "VEREADOR")
        self.assertIsNone(user.sinapse_orgao_id)
        self.assertEqual(response.data["vinculo_status"], "ok")

    def test_filtro_por_perfil(self):
        self.client.force_authenticate(user=self.gestor)
        response = self.client.get(self.url, {"perfil": "VEREADOR"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(all(u["perfil"] == "VEREADOR" for u in response.data))

    def test_protocolo_nao_cria_gestor(self):
        self.client.force_authenticate(user=self.protocolo)
        response = self.client.post(
            self.url,
            {"perfil": "GESTOR", "username": "x", "password": "y"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
