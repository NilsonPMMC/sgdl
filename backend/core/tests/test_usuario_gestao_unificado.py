from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Usuario

import importlib.util

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_ORGAO_B = _legacy.SINAPSE_ORGAO_B


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

    def test_edicao_sem_senha_preserva_login(self):
        alvo = Usuario.objects.get(username="ver_u5")
        self.assertTrue(alvo.check_password("x"))
        self.client.force_authenticate(user=self.gestor)
        detail = reverse("gestao-usuario-detail", args=[alvo.pk])
        response = self.client.patch(
            detail,
            {"first_name": "Editado", "password": "   "},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        alvo.refresh_from_db()
        self.assertEqual(alvo.first_name, "Editado")
        self.assertTrue(alvo.check_password("x"))

    def test_atualizar_usuario_b_nao_remove_setores_de_usuario_a(self):
        from core.models_unidade_administrativa import (
            UnidadeAdministrativa,
            UnidadeAdministrativaResponsavel,
        )
        from core.services.usuario_vinculo_service import UsuarioVinculoService

        ua_a = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            nome="Setor A",
            sigla="SET-A",
        )
        ua_b = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_B,
            nome="Setor B",
            sigla="SET-B",
        )
        orgao_a = SINAPSE_ORGAO_A
        orgao_b = SINAPSE_ORGAO_B

        user_a = Usuario.objects.create_user(
            username="sec_a",
            password="x",
            perfil="SECRETARIA",
        )
        user_b = Usuario.objects.create_user(
            username="sec_b",
            password="x",
            perfil="SECRETARIA",
        )
        svc = UsuarioVinculoService()
        svc.sincronizar_secretaria(user_a, sinapse_orgao_id=orgao_a, unidade_ids=[ua_a.pk])
        svc.sincronizar_secretaria(user_b, sinapse_orgao_id=orgao_b, unidade_ids=[ua_b.pk])

        self.client.force_authenticate(user=self.gestor)
        detail_a = reverse("gestao-usuario-detail", args=[user_a.pk])
        detail_b = reverse("gestao-usuario-detail", args=[user_b.pk])

        r1 = self.client.patch(
            detail_a,
            {
                "sinapse_orgao_id": orgao_a,
                "unidade_ids": [ua_a.pk],
                "first_name": "Atualizado A",
            },
            format="json",
        )
        self.assertEqual(r1.status_code, status.HTTP_200_OK)

        r2 = self.client.patch(
            detail_b,
            {
                "sinapse_orgao_id": orgao_b,
                "unidade_ids": [ua_b.pk],
                "first_name": "Atualizado B",
            },
            format="json",
        )
        self.assertEqual(r2.status_code, status.HTTP_200_OK)

        self.assertTrue(
            UnidadeAdministrativaResponsavel.objects.filter(
                usuario=user_a, unidade=ua_a, ativo=True
            ).exists()
        )
        self.assertTrue(
            UnidadeAdministrativaResponsavel.objects.filter(
                usuario=user_b, unidade=ua_b, ativo=True
            ).exists()
        )
