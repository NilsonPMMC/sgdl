"""Paginação server-side da listagem de demandas."""

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Demanda, Usuario
import importlib.util

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


def _rows(response):
    data = response.data
    if isinstance(data, dict):
        return data.get("results", [])
    return list(data)


class DemandaListPaginationTests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.protocolo = Usuario.objects.create_user(
            username="prot_pag", password="x", perfil="PROTOCOLO"
        )
        self.vereador = Usuario.objects.create_user(
            username="ver_pag", password="x", perfil="VEREADOR"
        )
        self.client.force_authenticate(self.protocolo)
        agora = timezone.now()
        for i in range(3):
            Demanda.objects.create(
                titulo=f"Aguardando {i}",
                descricao="x",
                autor=self.vereador,
                status="AGUARDANDO_PROTOCOLO",
                sinapse_orgao_id=SINAPSE_ORGAO_A,
                data_entrada_etapa=agora,
            )

    def test_sem_page_retorna_lista_plana(self):
        r = self.client.get("/api/demandas/", {"fila": "protocolados"})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIsInstance(r.data, list)
        self.assertEqual(len(r.data), 3)

    def test_com_page_retorna_paginado(self):
        r = self.client.get(
            "/api/demandas/",
            {"fila": "protocolados", "page": 1, "page_size": 2},
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("results", r.data)
        self.assertEqual(r.data["count"], 3)
        self.assertEqual(len(r.data["results"]), 2)

    def test_resumo_filas(self):
        r = self.client.get("/api/demandas/resumo-filas/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["protocolados"], 3)
        self.assertEqual(r.data["abertos"], 3)

    def test_listagem_com_resumo_embutido(self):
        r = self.client.get(
            "/api/demandas/",
            {"fila": "protocolados", "page": 1, "page_size": 10, "include_resumo": "1"},
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("resumo_filas", r.data)
        self.assertEqual(r.data["resumo_filas"]["protocolados"], 3)

    def test_consulta_atrasadas(self):
        Demanda.objects.filter(status="AGUARDANDO_PROTOCOLO").update(
            status="PROTOCOLADO",
            data_inicio_prazo=timezone.now() - timezone.timedelta(days=30),
            prazo_efetivo_dias=5,
        )
        r = self.client.get(
            "/api/demandas/",
            {"fila": "operacionais", "consulta": "atrasadas", "page": 1, "page_size": 10},
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["count"], 3)

    def test_fila_finalizados_usa_serializer_enxuto(self):
        inicio = timezone.now() - timezone.timedelta(days=5)
        fim = timezone.now()
        Demanda.objects.filter(status="AGUARDANDO_PROTOCOLO").update(
            status="FINALIZADO",
            data_inicio_prazo=inicio,
            data_finalizacao=fim,
        )
        r = self.client.get(
            "/api/demandas/",
            {"fila": "finalizados", "page": 1, "page_size": 10},
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        row = r.data["results"][0]
        self.assertIn("titulo", row)
        self.assertNotIn("tramitacoes", row)
        self.assertNotIn("anexos", row)
        self.assertIn("data_finalizacao", row)
        self.assertIn("tempo_execucao_segundos", row)
        self.assertGreaterEqual(row["tempo_execucao_segundos"], 5 * 86400 - 60)
