"""Testes de formatação de descrição na timeline (B9)."""

from django.test import SimpleTestCase

from core.services.scatter_gather_service import _resumo_texto
from core.services.tramitacao_texto import descricao_tramitacao_para_exibicao


class TramitacaoTextoTests(SimpleTestCase):
    def test_texto_plano_preserva_quebras(self):
        raw = "Linha 1\n\nLinha 2\nLinha 3"
        ctx = descricao_tramitacao_para_exibicao(raw)
        self.assertEqual(ctx["modo"], "texto")
        self.assertIn("\n\n", ctx["texto"])

    def test_html_rico_mantem_modo_html(self):
        raw = "<p>Parágrafo A</p><p>Parágrafo B</p>"
        ctx = descricao_tramitacao_para_exibicao(raw)
        self.assertEqual(ctx["modo"], "html")
        self.assertIn("Parágrafo A", ctx["html"])

    def test_vazio(self):
        self.assertEqual(descricao_tramitacao_para_exibicao(""), {"modo": "vazio"})


class ResumoTextoScatterTests(SimpleTestCase):
    def test_resumo_texto_curto(self):
        self.assertEqual(_resumo_texto("Despacho inicial"), "Despacho inicial")

    def test_resumo_texto_longo_nao_retorna_none(self):
        longo = "x" * 250
        resumo = _resumo_texto(longo)
        self.assertIsNotNone(resumo)
        self.assertLessEqual(len(resumo), 200)
        self.assertTrue(resumo.endswith("…"))
