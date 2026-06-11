from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
import importlib.util

from core.models import ChatSession, Demanda, Usuario

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class DashboardTrilhaServiceTests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        from core.services.dashboard_trilha_service import DashboardTrilhaService

        self.trilha_svc = DashboardTrilhaService()
        self.vereador = Usuario.objects.create_user(
            username="ver_trilha",
            password="x",
            perfil="VEREADOR",
        )
        self.gestor = Usuario.objects.create_user(
            username="gest_trilha",
            password="x",
            perfil="GESTOR",
        )

    def _demanda(self, **kwargs):
        defaults = {
            "titulo": "Teste trilha",
            "descricao": "Corpo",
            "autor": self.vereador,
            "status": "AGUARDANDO_PROTOCOLO",
        }
        defaults.update(kwargs)
        return Demanda.objects.create(**defaults)

    def test_conta_carta_e_tendencia(self):
        self._demanda(origem_vinculo=Demanda.ORIGEM_VINCULO_CARTA)
        self._demanda(origem_vinculo=Demanda.ORIGEM_VINCULO_TENDENCIA)

        dados = self.trilha_svc.calcular()
        self.assertEqual(dados["carta"]["total"], 1)
        self.assertEqual(dados["tendencia"]["total"], 1)
        self.assertEqual(dados["totais"]["demandas_formalizadas"], 2)

    def test_recusa_copiloto_na_amostra(self):
        ChatSession.objects.create(
            autor=self.vereador,
            demandas_rascunho=[
                {
                    "titulo": "Receita de bolo",
                    "fora_competencia": True,
                    "motivo_recusa": "Não é serviço público municipal.",
                }
            ],
        )
        dados = self.trilha_svc.calcular()
        self.assertEqual(dados["recusa"]["total"], 1)
        self.assertEqual(len(dados["amostra_motivo_recusa"]), 1)
        self.assertIn("serviço público", dados["amostra_motivo_recusa"][0]["motivo"])

    def test_api_dashboard_inclui_trilhas_para_gestor(self):
        self._demanda(origem_vinculo=Demanda.ORIGEM_VINCULO_CARTA)
        self.client.force_authenticate(self.gestor)
        r = self.client.get("/api/dashboard/stats/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("trilhas", r.data)
        self.assertEqual(r.data["trilhas"]["carta"]["total"], 1)
        self.assertIn("grafico_trilhas", r.data["trilhas"])

    def test_api_dashboard_sem_trilhas_para_vereador(self):
        self.client.force_authenticate(self.vereador)
        r = self.client.get("/api/dashboard/stats/", {"autor": self.vereador.pk})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertNotIn("trilhas", r.data)

    def test_mensal_por_trilha(self):
        agora = timezone.now()
        self._demanda(
            origem_vinculo=Demanda.ORIGEM_VINCULO_CARTA,
            data_criacao=agora,
        )
        qs = Demanda.objects.exclude(status="RASCUNHO")
        serie = self.trilha_svc.mensal_por_trilha(qs)
        self.assertTrue(serie)
        self.assertGreaterEqual(serie[-1]["carta"], 1)
