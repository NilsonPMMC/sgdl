"""Testes de formatação de descrição na timeline (B9)."""

from django.test import SimpleTestCase

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
