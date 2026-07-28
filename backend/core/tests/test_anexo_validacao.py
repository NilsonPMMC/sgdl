"""Testes de validação de anexos com mesmo nome (B3)."""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Anexo, Demanda
from core.services.anexo_validacao_service import (
    normalizar_nome_arquivo,
    validar_lote_nomes_arquivo,
    validar_nome_arquivo_novo,
)

import importlib.util

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class AnexoValidacaoServiceTests(SimpleTestCase):
    def test_normalizar_nome_case_insensitive(self):
        self.assertEqual(normalizar_nome_arquivo("Foto.PDF"), "foto.pdf")
        self.assertEqual(normalizar_nome_arquivo("/tmp/docs/Relatorio.pdf"), "relatorio.pdf")

    def test_rejeita_nome_duplicado(self):
        existentes = {"foto.jpg"}
        with self.assertRaises(ValueError) as ctx:
            validar_nome_arquivo_novo(existentes, "FOTO.JPG")
        self.assertIn("foto.jpg", str(ctx.exception).lower())

    def test_lote_rejeita_duplicata_interna(self):
        with self.assertRaises(ValueError):
            validar_lote_nomes_arquivo(set(), ["a.pdf", "A.PDF"])


class AnexoAPITests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.vereador = _legacy.Usuario.objects.create_user(
            username="ver_anexo", password="x", perfil="VEREADOR"
        )
        self.client.force_authenticate(self.vereador)
        self.demanda = Demanda.objects.create(
            titulo="Demanda anexo",
            descricao="x",
            autor=self.vereador,
            status="RASCUNHO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        Anexo.objects.create(
            demanda=self.demanda,
            arquivo=SimpleUploadedFile("documento.pdf", b"pdf"),
            descricao="documento.pdf",
        )

    def test_rejeita_anexo_mesmo_nome(self):
        resp = self.client.post(
            "/api/anexos/",
            {
                "demanda": self.demanda.pk,
                "arquivo": SimpleUploadedFile("Documento.PDF", b"outro"),
            },
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("documento.pdf", resp.data["arquivo"][0].lower())
