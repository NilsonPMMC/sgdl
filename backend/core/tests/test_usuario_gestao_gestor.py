from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Usuario
from core.models_unidade_administrativa import UnidadeAdministrativa
from core.services.usuario_vinculo_service import UsuarioVinculoService

import importlib.util

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class UsuarioVinculoGestorTests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.ua = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            nome="SGAC ref",
            sigla="SGAC-REF",
        )
        self.service = UsuarioVinculoService()

    def test_sincronizar_gestor_aplica_staff_superuser(self):
        user = Usuario.objects.create_user(
            username="gest_u4",
            password="x",
            perfil="VEREADOR",
        )
        Usuario.objects.filter(pk=user.pk).update(
            perfil="GESTOR",
            is_staff=False,
            is_superuser=False,
        )
        user.refresh_from_db()
        info = self.service.sincronizar_gestor(user)
        user.refresh_from_db()
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(info["admin_pleno"])

    def test_referencia_institucional_opcional(self):
        user = Usuario.objects.create_user(
            username="gest_u4_ref",
            password="x",
            perfil="GESTOR",
        )
        info = self.service.sincronizar_gestor(
            user,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            unidade_ids=[self.ua.pk],
        )
        user.refresh_from_db()
        self.assertEqual(user.sinapse_orgao_id, SINAPSE_ORGAO_A)
        self.assertTrue(info["referencia_unidades"])

    def test_signal_gestor_aplica_privilegios(self):
        user = Usuario.objects.create_user(
            username="gest_u4_sig",
            password="x",
            perfil="VEREADOR",
        )
        user.perfil = "GESTOR"
        user.is_staff = False
        user.is_superuser = False
        user.save()
        user.refresh_from_db()
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)


class GestaoUsuarioGestorAPITests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.gestor = Usuario.objects.create_user(
            username="gest_admin_u4",
            password="x",
            perfil="GESTOR",
            is_staff=True,
            is_superuser=True,
        )
        self.protocolo = Usuario.objects.create_user(
            username="prot_u4",
            password="x",
            perfil="PROTOCOLO",
        )
        self.url = reverse("gestao-usuario-gestor-list")

    def test_gestor_cria_outro_gestor(self):
        self.client.force_authenticate(user=self.gestor)
        payload = {
            "username": "novo_gestor",
            "password": "senha123",
            "sinapse_orgao_id": SINAPSE_ORGAO_A,
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = Usuario.objects.get(username="novo_gestor")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_protocolo_nao_gerencia_gestores(self):
        self.client.force_authenticate(user=self.protocolo)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_profile_expoe_vinculo_gestor(self):
        self.client.force_authenticate(user=self.gestor)
        response = self.client.get(reverse("user-profile"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["vinculo_gestor"]["admin_pleno"])
        self.assertTrue(response.data["is_staff"])
