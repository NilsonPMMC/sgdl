"""Validação de portal no login JWT."""

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

Usuario = get_user_model()


class AuthPortalLoginTests(APITestCase):
    def setUp(self):
        self.vereador = Usuario.objects.create_user(
            username="ver_portal", password="secret123", perfil="VEREADOR"
        )
        self.protocolo = Usuario.objects.create_user(
            username="prot_portal", password="secret123", perfil="PROTOCOLO"
        )

    def _login(self, username, portal=None):
        payload = {"username": username, "password": "secret123"}
        if portal is not None:
            payload["portal"] = portal
        return self.client.post("/api/token/", payload, format="json")

    def test_vereador_no_portal_vereador(self):
        r = self._login("ver_portal", "vereador")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("access", r.data)

    def test_vereador_bloqueado_no_portal_prefeitura(self):
        r = self._login("ver_portal", "prefeitura")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(r.data.get("code"), "wrong_portal")
        self.assertEqual(r.data.get("portal_correto"), "vereador")

    def test_protocolo_no_portal_prefeitura(self):
        r = self._login("prot_portal", "prefeitura")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_protocolo_bloqueado_no_portal_vereador(self):
        r = self._login("prot_portal", "vereador")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(r.data.get("portal_correto"), "prefeitura")

    def test_sem_portal_mantem_compatibilidade(self):
        r = self._login("ver_portal")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
