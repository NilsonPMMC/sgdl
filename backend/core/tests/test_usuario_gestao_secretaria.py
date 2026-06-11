from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Usuario
from core.models_unidade_administrativa import (
    UnidadeAdministrativa,
    UnidadeAdministrativaResponsavel,
)
from core.services.usuario_vinculo_service import UsuarioVinculoService

import importlib.util

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_ORGAO_B = _legacy.SINAPSE_ORGAO_B
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class UsuarioVinculoSecretariaTests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.ua_a = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            nome="Setor A",
            sigla="SET-A",
        )
        self.ua_b = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_B,
            nome="Setor B",
            sigla="SET-B",
        )
        self.service = UsuarioVinculoService()

    def test_sincronizar_secretaria_vincula_orgao_e_setores(self):
        user = Usuario.objects.create_user(
            username="sec_u3",
            password="x",
            perfil="SECRETARIA",
        )
        info = self.service.sincronizar_secretaria(
            user,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            unidade_ids=[self.ua_a.pk],
        )
        user.refresh_from_db()
        self.assertTrue(info["completo"])
        self.assertEqual(user.sinapse_orgao_id, SINAPSE_ORGAO_A)
        self.assertTrue(
            UnidadeAdministrativaResponsavel.objects.filter(
                usuario=user, unidade=self.ua_a, ativo=True
            ).exists()
        )

    def test_rejeita_setor_de_outro_orgao(self):
        user = Usuario.objects.create_user(
            username="sec_u3_err",
            password="x",
            perfil="SECRETARIA",
        )
        with self.assertRaises(ValueError):
            self.service.sincronizar_secretaria(
                user,
                sinapse_orgao_id=SINAPSE_ORGAO_A,
                unidade_ids=[self.ua_b.pk],
            )

    def test_status_incompleto_sem_orgao_e_setor(self):
        user = Usuario.objects.create_user(
            username="sec_u3_inc",
            password="x",
            perfil="SECRETARIA",
        )
        status_info = self.service.status_vinculo_secretaria(user)
        self.assertFalse(status_info["completo"])
        self.assertTrue(status_info["falta_orgao"])
        self.assertTrue(status_info["falta_setores"])


class GestaoUsuarioSecretariaAPITests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.gestor = Usuario.objects.create_user(
            username="gest_u3",
            password="x",
            perfil="GESTOR",
        )
        self.ua = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            nome="Setor API",
            sigla="SET-API",
        )
        self.url = reverse("gestao-usuario-secretaria-list")

    def test_gestor_cria_usuario_secretaria_com_setores(self):
        self.client.force_authenticate(user=self.gestor)
        payload = {
            "username": "nova_sec",
            "password": "senha123",
            "first_name": "Nova",
            "last_name": "Secretaria",
            "sinapse_orgao_id": SINAPSE_ORGAO_A,
            "unidade_ids": [self.ua.pk],
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["vinculo_secretaria"]["completo"])
        user = Usuario.objects.get(username="nova_sec")
        self.assertEqual(user.perfil, "SECRETARIA")
        self.assertEqual(user.sinapse_orgao_id, SINAPSE_ORGAO_A)

    def test_secretaria_nao_acessa_gestao(self):
        sec = Usuario.objects.create_user(
            username="sec_block",
            password="x",
            perfil="SECRETARIA",
        )
        self.client.force_authenticate(user=sec)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_profile_expoe_vinculo_secretaria(self):
        user = Usuario.objects.create_user(
            username="sec_prof",
            password="x",
            perfil="SECRETARIA",
        )
        UsuarioVinculoService().sincronizar_secretaria(
            user,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            unidade_ids=[self.ua.pk],
        )
        self.client.force_authenticate(user=user)
        response = self.client.get(reverse("user-profile"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["vinculo_secretaria"]["completo"])
