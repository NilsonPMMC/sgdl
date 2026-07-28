"""Testes de exportação CSV de Serviços Otimizados no Django Admin."""

import csv
import io

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.admin.servico_otimizado_export import servico_otimizado_csv_response
from core.models_carta_otimizada import ServicoOtimizado

Usuario = get_user_model()


class ServicoOtimizadoExportTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_superuser(
            username="admin_csv",
            email="admin@example.com",
            password="x",
        )
        self.client.force_login(self.admin)
        ServicoOtimizado.objects.all().delete()
        self.svc_a = ServicoOtimizado.objects.create(
            sinapse_servico_id=801,
            titulo_otimizado="Tapa buraco na via",
            descricao_objetiva="Reparo de buracos em vias públicas.",
            intencao_servico="Corrigir buracos que prejudicam o trânsito.",
            texto_rag_otimizado="tapa buraco via pública",
            problemas_resolve=["buraco", "asfalto"],
            palavras_chave=["buraco", "via"],
            prazo_dias=15,
            prazo_categoria="NORMAL",
            tipo_processo="OPERACIONAL",
            score_qualidade_original=3,
            score_qualidade_otimizado=8,
            versao_otimizacao="3.1",
            ativo=True,
        )
        self.svc_b = ServicoOtimizado.objects.create(
            sinapse_servico_id=802,
            titulo_otimizado="Iluminação pública",
            descricao_objetiva="Troca de lâmpadas queimadas.",
            intencao_servico="Restaurar iluminação em logradouros.",
            texto_rag_otimizado="iluminação pública lâmpada",
            problemas_resolve=["lâmpada queimada"],
            palavras_chave=["luz", "poste"],
            prazo_dias=7,
            prazo_categoria="RAPIDO",
            tipo_processo="OPERACIONAL",
            score_qualidade_original=4,
            score_qualidade_otimizado=9,
            versao_otimizacao="3.1",
            ativo=False,
        )

    def _parse_csv(self, response) -> list[list[str]]:
        content = response.content.decode("utf-8-sig")
        return list(csv.reader(io.StringIO(content), delimiter=";"))

    def test_resposta_csv_contem_colunas_e_dados(self):
        response = servico_otimizado_csv_response(
            ServicoOtimizado.objects.filter(pk=self.svc_a.pk)
        )
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("attachment", response["Content-Disposition"])

        rows = self._parse_csv(response)
        self.assertGreaterEqual(len(rows), 2)
        header = rows[0]
        self.assertIn("titulo_otimizado", header)
        self.assertNotIn("sinapse_servico_id", header)
        self.assertNotIn("tem_embedding", header)
        self.assertNotIn("ativo", header)

        data = dict(zip(header, rows[1], strict=False))
        self.assertEqual(data["id"], str(self.svc_a.pk))
        self.assertEqual(data["titulo_otimizado"], "Tapa buraco na via")
        self.assertEqual(data["prazo_dias"], "15")

    def test_admin_export_csv_respeita_filtro_ativo(self):
        url = reverse("admin:core_servicootimizado_export_csv")
        response = self.client.get(url, {"ativo__exact": "1"})
        self.assertEqual(response.status_code, 200)

        rows = self._parse_csv(response)
        header = rows[0]
        titulos = {
            dict(zip(header, row, strict=False))["titulo_otimizado"] for row in rows[1:]
        }
        self.assertEqual(titulos, {"Tapa buraco na via"})

    def test_admin_export_csv_todos(self):
        url = reverse("admin:core_servicootimizado_export_csv")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        rows = self._parse_csv(response)
        self.assertEqual(len(rows), 3)

    def test_admin_action_exporta_selecionados(self):
        url = reverse("admin:core_servicootimizado_changelist")
        response = self.client.post(
            url,
            {
                "action": "exportar_csv_selecionados",
                "_selected_action": [str(self.svc_b.pk)],
            },
        )
        self.assertEqual(response.status_code, 200)
        rows = self._parse_csv(response)
        self.assertEqual(len(rows), 2)
        data = dict(zip(rows[0], rows[1], strict=False))
        self.assertEqual(data["titulo_otimizado"], "Iluminação pública")
