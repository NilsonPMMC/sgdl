"""Testes A3 — assinatura eletrônica na conclusão operacional (Secretaria)."""

import importlib.util

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Demanda, Usuario
from core.models_assinatura_eletronica import AssinaturaEletronica
from core.services.assinatura_eletronica_service import (
    DECLARACAO_CONCLUSAO,
    AssinaturaEletronicaService,
)

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_SERVICO_ID = _legacy.SINAPSE_SERVICO_ID
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin

PARECER = "Serviço concluído conforme vistoria técnica no local."


class AssinaturaConclusaoSecretariaTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.vereador = Usuario.objects.create_user(
            username="ver_a3", password="x", perfil="VEREADOR"
        )
        self.secretaria = Usuario.objects.create_user(
            username="sec_a3",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        self.demanda = Demanda.objects.create(
            titulo="Conclusão A3",
            descricao="Demanda em execução",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            protocolo_executivo="2026-0200",
        )

    def test_registrar_conclusao_exige_declaracao(self):
        svc = AssinaturaEletronicaService()
        preview = svc.preparar_assinatura_conclusao_secretaria(
            self.demanda, parecer_operacional=PARECER
        )
        with self.assertRaises(ValueError):
            svc.registrar_assinatura_conclusao_secretaria(
                self.demanda,
                self.secretaria,
                hash_documento=preview["hash_documento"],
                declaracao="declaração inválida",
            )

    def test_registrar_conclusao_cria_assinatura(self):
        svc = AssinaturaEletronicaService()
        preview = svc.preparar_assinatura_conclusao_secretaria(
            self.demanda, parecer_operacional=PARECER
        )
        assinatura = svc.registrar_assinatura_conclusao_secretaria(
            self.demanda,
            self.secretaria,
            hash_documento=preview["hash_documento"],
            declaracao=DECLARACAO_CONCLUSAO,
        )
        self.assertEqual(assinatura.etapa, AssinaturaEletronica.ETAPA_CONCLUSAO_SECRETARIA)
        self.assertEqual(assinatura.papel, AssinaturaEletronica.PAPEL_CHEFIA_SETOR)


class AssinaturaConclusaoSecretariaAPITests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.vereador = Usuario.objects.create_user(
            username="ver_a3_api", password="x", perfil="VEREADOR"
        )
        self.secretaria = Usuario.objects.create_user(
            username="sec_a3_api",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        self.demanda = Demanda.objects.create(
            titulo="API A3",
            descricao="Teste",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            protocolo_executivo="2026-0201",
        )

    def _preview_conclusao(self):
        self.client.force_authenticate(self.secretaria)
        return self.client.post(
            f"/api/demandas/{self.demanda.pk}/preview-conclusao-secretaria/",
            {"parecer_operacional": PARECER},
            format="json",
        )

    def test_preview_conclusao_secretaria(self):
        r = self._preview_conclusao()
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("hash_documento", r.data)
        self.assertEqual(r.data["declaracao_exigida"], DECLARACAO_CONCLUSAO)

    def test_solicitar_devolutiva_exige_assinatura(self):
        self.client.force_authenticate(self.secretaria)
        r = self.client.post(
            f"/api/demandas/{self.demanda.pk}/solicitar-devolutiva/",
            {"parecer_operacional": PARECER},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Prévia", r.data["detail"])

    def test_solicitar_devolutiva_com_assinatura(self):
        preview = self._preview_conclusao()
        self.client.force_authenticate(self.secretaria)
        r = self.client.post(
            f"/api/demandas/{self.demanda.pk}/solicitar-devolutiva/",
            {
                "parecer_operacional": PARECER,
                "hash_documento": preview.data["hash_documento"],
                "declaracao": DECLARACAO_CONCLUSAO,
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["status"], "EM_EXECUCAO")
        self.assertTrue(r.data.get("aguardando_validacao_gestor"))
        self.assertIn("assinatura_registrada", r.data)
        self.assertTrue(
            AssinaturaEletronica.objects.filter(
                demanda=self.demanda,
                etapa=AssinaturaEletronica.ETAPA_CONCLUSAO_SECRETARIA,
            ).exists()
        )
