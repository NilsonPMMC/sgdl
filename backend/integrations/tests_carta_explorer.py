"""Testes do Explorer da Carta Sinapse."""

from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


@override_settings(
    DATABASES={
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
)
class CartaExplorerAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="gestor_carta",
            password="test",
            perfil="GESTOR",
        )
        self.client.force_authenticate(user=self.user)

    @patch("integrations.views_carta_explorer.CartaExplorerService")
    def test_lista_servicos(self, mock_svc_cls):
        mock_svc_cls.return_value.buscar.return_value = {
            "total": 1,
            "results": [{"id": 10, "nome": "Tapa Buraco"}],
            "catalogo_disponivel": True,
        }
        response = self.client.get("/api/integrations/carta/servicos/", {"q": "buraco"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 1)
        mock_svc_cls.return_value.buscar.assert_called_once()

    @patch("integrations.views_carta_explorer.CartaExplorerService")
    def test_detalhe_servico(self, mock_svc_cls):
        mock_svc_cls.return_value.detalhe.return_value = {
            "id": 10,
            "titulo": "Tapa Buraco",
            "prazo_dias": 15,
            "documentos_necessarios": "Foto do local",
        }
        response = self.client.get("/api/integrations/carta/servicos/10/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["prazo_dias"], 15)

    @patch("integrations.views_carta_explorer.CartaExplorerService")
    def test_simular_triagem(self, mock_svc_cls):
        mock_svc_cls.return_value.simular_triagem.return_value = {
            "ok": True,
            "candidatos": [{"servico_id": 10, "score": 0.73, "titulo": "Tapa Buraco"}],
            "latencia_total_ms": 45.2,
        }
        response = self.client.post(
            "/api/integrations/carta/simular-triagem/",
            {"texto": "buraco na rua", "top_k": 3},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["ok"])

    def test_perfil_sem_acesso(self):
        vereador_ok = User.objects.create_user(
            username="vereador_carta",
            password="test",
            perfil="VEREADOR",
        )
        self.client.force_authenticate(user=vereador_ok)
        with patch("integrations.views_carta_explorer.CartaExplorerService") as mock_svc:
            mock_svc.return_value.buscar.return_value = {"total": 0, "results": []}
            self.assertEqual(
                self.client.get("/api/integrations/carta/servicos/").status_code,
                status.HTTP_200_OK,
            )

        secretaria = User.objects.create_user(
            username="sec_carta",
            password="test",
            perfil="SECRETARIA",
        )
        self.client.force_authenticate(user=secretaria)
        with patch("integrations.views_carta_explorer.CartaExplorerService") as mock_svc:
            mock_svc.return_value.buscar.return_value = {"total": 0, "results": []}
            response = self.client.get("/api/integrations/carta/servicos/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class CartaExplorerServiceTests(TestCase):
    @patch("integrations.services.carta_explorer_service.catalog_disponivel", return_value=True)
    @patch("integrations.sinapse_catalog.servico_detalhe_dict")
    @patch("core.services.triagem_service.TriagemService")
    @patch("core.services.vector_service.VectorService")
    def test_simular_triagem_enriquece_candidatos(
        self, mock_vector_cls, mock_triagem_cls, mock_detalhe, _disp
    ):
        mock_vector_cls.return_value.generate_embedding.return_value = [0.1] * 8
        mock_triagem_cls.return_value.buscar_servico_sinapse.return_value = [
            {
                "servico_id": 10,
                "titulo": "Tapa Buraco",
                "orgao": "Zeladoria",
                "score": 0.73,
                "distancia": 0.27,
            }
        ]
        mock_detalhe.return_value = {
            "prazo_dias": 10,
            "prazo_texto": "10 dias",
            "documentos_necessarios": "Foto",
        }

        from integrations.services.carta_explorer_service import CartaExplorerService

        out = CartaExplorerService().simular_triagem("buraco na rua", top_k=3)
        self.assertTrue(out["ok"])
        self.assertEqual(len(out["candidatos"]), 1)
        self.assertEqual(out["candidatos"][0]["prazo_dias"], 10)

    def test_simular_texto_curto(self):
        from integrations.services.carta_explorer_service import CartaExplorerService

        out = CartaExplorerService().simular_triagem("abc")
        self.assertFalse(out["ok"])
