from django.template.loader import render_to_string
from django.test import SimpleTestCase

from core.services.oficio_corpo_pdf import (
    parece_html_rico,
    preparar_corpo_pdf,
    sanitizar_html_oficio,
)


class OficioCorpoPdfTests(SimpleTestCase):
    def test_texto_plano_nao_e_richtext(self):
        texto = "Prezados,\n\nSolicitamos o serviço."
        ctx = preparar_corpo_pdf(texto)
        self.assertFalse(ctx["corpo_richtext"])
        self.assertEqual(ctx["corpo_texto"], texto)

    def test_html_quill_sanitizado_e_marcado_richtext(self):
        html = '<p class="ql-align-center">Texto centralizado</p><p>Segundo parágrafo</p>'
        self.assertTrue(parece_html_rico(html))
        ctx = preparar_corpo_pdf(html)
        self.assertTrue(ctx["corpo_richtext"])
        self.assertIn("ql-align-center", ctx["corpo_texto"])
        self.assertNotIn("<script", ctx["corpo_texto"].lower())

    def test_remove_script_malicioso(self):
        html = '<p>Ok</p><script>alert(1)</script>'
        limpo = sanitizar_html_oficio(html)
        self.assertNotIn("script", limpo.lower())
        self.assertIn("Ok", limpo)

    def test_template_renderiza_html_sem_exibir_tags(self):
        html = '<p class="ql-align-right">Alinhado à direita</p>'
        ctx = preparar_corpo_pdf(html)
        rendered = render_to_string("oficio/_corpo_oficio.html", ctx)
        self.assertIn('class="corpo corpo-richtext"', rendered)
        self.assertIn("Alinhado à direita", rendered)
        self.assertNotIn("&lt;p", rendered)

    def test_normaliza_nbsp_para_quebra_na_margem(self):
        html = "<p>Venho,&nbsp;respeitosamente,&nbsp;solicitar.</p>"
        limpo = sanitizar_html_oficio(html)
        self.assertNotIn("&nbsp;", limpo)
        self.assertIn("Venho, respeitosamente, solicitar.", limpo)

    def test_paragrafo_vazio_vira_quebra_visual(self):
        html = "<p>Linha 1</p><p></p><p>Linha 2</p>"
        limpo = sanitizar_html_oficio(html)
        self.assertIn("<p><br></p>", limpo)

    def test_div_quill_convertido_para_paragrafo(self):
        html = '<div class="ql-align-right">Data</div><div>Corpo</div>'
        limpo = sanitizar_html_oficio(html)
        self.assertIn('<p class="ql-align-right">Data</p>', limpo)
        self.assertIn("<p>Corpo</p>", limpo)
