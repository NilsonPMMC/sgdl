from unittest.mock import patch

from decimal import Decimal

from django.template.loader import render_to_string
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Usuario
from core.models_config import ConfiguracaoOficio


class ConfiguracaoOficioAPITests(APITestCase):
    def setUp(self):
        self.gestor = Usuario.objects.create_user(
            username="gestor_oficio",
            password="x",
            perfil="GESTOR",
        )
        self.vereador = Usuario.objects.create_user(
            username="ver_oficio",
            password="x",
            perfil="VEREADOR",
        )
        ConfiguracaoOficio.carregar()

    def test_gestor_pode_consultar(self):
        self.client.force_authenticate(self.gestor)
        r = self.client.get("/api/configuracao-oficio/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("pagina_formato", r.data)
        self.assertIn("margem_superior_cm", r.data)
        self.assertIn("instituicao_nome", r.data)
        self.assertNotIn("gabinete_nome", r.data)

    def test_vereador_nao_pode_consultar(self):
        self.client.force_authenticate(self.vereador)
        r = self.client.get("/api/configuracao-oficio/")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_gestor_pode_atualizar_margens(self):
        self.client.force_authenticate(self.gestor)
        r = self.client.patch(
            "/api/configuracao-oficio/",
            {
                "municipio": "",
                "uf": "",
                "titulo_instituicao": "CÂMARA MUNICIPAL DE TESTE",
                "brasao_largura_cm": "3.20",
                "margem_superior_cm": "3.00",
                "margem_esquerda_cm": "2.50",
                "rodape_protocolo_altura_cm": "2.80",
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["municipio"], "")
        self.assertEqual(r.data["titulo_instituicao"], "CÂMARA MUNICIPAL DE TESTE")
        cfg = ConfiguracaoOficio.carregar()
        self.assertEqual(cfg.municipio, "")

    @patch("core.services.oficio_service.HTML.write_pdf", return_value=b"%PDF-1.4 test")
    def test_preview_pdf_gestor_get(self, _mock_pdf):
        self.client.force_authenticate(self.gestor)
        r = self.client.get("/api/configuracao-oficio/preview-pdf/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertTrue(r.content.startswith(b"%PDF"))

    @patch("core.services.oficio_service.HTML.write_pdf", return_value=b"%PDF-1.4 test")
    def test_preview_pdf_post_com_layout_formulario(self, _mock_pdf):
        self.client.force_authenticate(self.gestor)
        r = self.client.post(
            "/api/configuracao-oficio/preview-pdf/",
            {
                "titulo_instituicao": "",
                "cabecalho_layout": "BRASAO_CENTRO",
                "brasao_largura_cm": "4.50",
                "margem_esquerda_cm": "4.00",
                "margem_direita_cm": "1.50",
                "pagina_formato": "A4",
                "pagina_orientacao": "portrait",
            },
            format="multipart",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.content.startswith(b"%PDF"))

    def test_preview_pdf_vereador_negado(self):
        self.client.force_authenticate(self.vereador)
        r = self.client.get("/api/configuracao-oficio/preview-pdf/")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)


class ConfiguracaoOficioSingletonTests(TestCase):
    def test_carregar_cria_registro_unico(self):
        cfg = ConfiguracaoOficio.carregar()
        self.assertEqual(cfg.pk_fixo, 1)
        self.assertEqual(ConfiguracaoOficio.objects.count(), 1)

    def test_instituicao_nome_camara(self):
        cfg = ConfiguracaoOficio.carregar()
        cfg.titulo_instituicao = "CÂMARA MUNICIPAL DE MOGI DAS CRUZES"
        cfg.municipio = ""
        self.assertEqual(cfg.instituicao_nome, "CÂMARA MUNICIPAL DE MOGI DAS CRUZES")
        cfg.titulo_instituicao = ""
        cfg.municipio = "Mogi das Cruzes"
        self.assertEqual(cfg.instituicao_nome, "Câmara Municipal de Mogi das Cruzes")

    def test_contexto_layout_pdf_usa_ponto_decimal_para_css(self):
        cfg = ConfiguracaoOficio.carregar()
        cfg.brasao_largura_cm = Decimal("2.50")
        cfg.margem_superior_cm = Decimal("3.00")
        ctx = cfg.contexto_layout_pdf()
        self.assertEqual(ctx["brasao_largura"], "2.50")
        self.assertEqual(ctx["margem_superior"], "3.00")
        self.assertIn("margin: 3.00cm", ctx["oficio_css_dinamico"])
        self.assertIn("--oficio-brasao-largura: 2.50cm", ctx["oficio_css_dinamico"])
        self.assertNotIn("3,00cm", ctx["oficio_css_dinamico"])
        html = render_to_string("oficio/_oficio_estilos_pagina.html", ctx)
        self.assertIn("margin: 3.00cm", html)
        self.assertIn("var(--oficio-brasao-largura)", html)
        self.assertNotIn('type="text/django"', html)
        self.assertNotIn("3,00cm", html)
        html_brasao = render_to_string("oficio/_cabecalho_brasao.html", ctx)
        self.assertIn('class="cabecalho-brasao"', html_brasao)
        self.assertNotIn("2,50cm", html_brasao)

    def test_cabecalho_layout_texto_centro_sem_brasao(self):
        cfg = ConfiguracaoOficio.carregar()
        cfg.cabecalho_layout = "TEXTO_CENTRO"
        cfg.titulo_instituicao = "TITULO CENTRAL"
        ctx = cfg.contexto_layout_pdf()
        ctx["config"] = cfg
        ctx["cabecalho_imagem_url"] = "file:///tmp/brasao.png"
        html = render_to_string("oficio/_cabecalho_camara.html", ctx)
        self.assertIn("cabecalho-layout-texto_centro", html)
        self.assertIn("cabecalho-centro", html)
        self.assertNotIn("cabecalho-tabela", html)
        self.assertNotIn("cabecalho-brasao", html)

    def test_cabecalho_layout_texto_esquerda_inverte_colunas(self):
        cfg = ConfiguracaoOficio.carregar()
        cfg.cabecalho_layout = "TEXTO_ESQUERDA_BRASAO"
        cfg.titulo_instituicao = "TITULO"
        ctx = cfg.contexto_layout_pdf()
        ctx["config"] = cfg
        ctx["cabecalho_imagem_url"] = "file:///tmp/brasao.png"
        html = render_to_string("oficio/_cabecalho_camara.html", ctx)
        idx_texto = html.find("cabecalho-celula-texto")
        idx_brasao = html.find("cabecalho-celula-brasao")
        self.assertGreater(idx_texto, 0)
        self.assertGreater(idx_brasao, 0)
        self.assertLess(idx_texto, idx_brasao)
