"""Testes de assinatura eletrônica no envio oficial."""

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Demanda, Tramitacao
from core.models_assinatura_eletronica import AssinaturaEletronica
from core.services.assinatura_eletronica_service import (
    DECLARACAO_ENVIO,
    AssinaturaEletronicaService,
)

import importlib.util

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_SERVICO_ID = _legacy.SINAPSE_SERVICO_ID
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class AssinaturaEletronicaServiceTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.vereador = _legacy.Usuario.objects.create_user(
            username="ver_assin", password="x", perfil="VEREADOR"
        )
        self.demanda = Demanda.objects.create(
            titulo="Ofício teste",
            descricao="<p>Solicito reparo.</p>",
            autor=self.vereador,
            status="RASCUNHO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )

    def test_registrar_assinatura_exige_declaracao(self):
        svc = AssinaturaEletronicaService()
        with self.assertRaises(ValueError):
            svc.registrar_assinatura(
                self.demanda,
                self.vereador,
                hash_documento_informado="",
                declaracao="sim",
            )

    def test_preview_nao_cria_anexo(self):
        preview = AssinaturaEletronicaService().preparar_preview_envio(self.demanda)
        self.assertTrue(preview["preview_pdf_disponivel"])
        self.assertEqual(self.demanda.anexos.count(), 0)

    def test_registrar_assinatura_um_unico_anexo(self):
        preview = AssinaturaEletronicaService().preparar_preview_envio(self.demanda)
        AssinaturaEletronicaService().registrar_assinatura(
            self.demanda,
            self.vereador,
            hash_documento_informado=preview["hash_documento"],
            declaracao=DECLARACAO_ENVIO,
        )
        oficios = self.demanda.anexos.filter(
            descricao__icontains="Ofício assinado eletronicamente"
        )
        self.assertEqual(oficios.count(), 1)

    def test_registrar_assinatura_cria_registro(self):
        preview = AssinaturaEletronicaService().preparar_preview_envio(self.demanda)
        assinatura = AssinaturaEletronicaService().registrar_assinatura(
            self.demanda,
            self.vereador,
            hash_documento_informado=preview["hash_documento"],
            declaracao=DECLARACAO_ENVIO,
        )
        self.assertEqual(len(assinatura.hash_documento), 64)
        self.assertEqual(len(assinatura.codigo_validacao), 32)

    def test_validar_codigo(self):
        preview = AssinaturaEletronicaService().preparar_preview_envio(self.demanda)
        assinatura = AssinaturaEletronicaService().registrar_assinatura(
            self.demanda,
            self.vereador,
            hash_documento_informado=preview["hash_documento"],
            declaracao=DECLARACAO_ENVIO,
        )
        payload = AssinaturaEletronicaService().validar_codigo(assinatura.codigo_validacao)
        self.assertTrue(payload["valido"])
        self.assertEqual(payload["demanda_id"], self.demanda.pk)


class EnviarOficialAssinaturaAPITests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.vereador = _legacy.Usuario.objects.create_user(
            username="ver_env_ass", password="x", perfil="VEREADOR"
        )
        self.client.force_authenticate(self.vereador)
        self.demanda = Demanda.objects.create(
            titulo="Enviar assinado",
            descricao="<p>Texto do ofício.</p>",
            autor=self.vereador,
            status="RASCUNHO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )

    def test_enviar_sem_declaracao_falha(self):
        r = self.client.post(f"/api/demandas/{self.demanda.pk}/enviar/", {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_enviar_com_assinatura_protocola(self):
        preview = self.client.get(
            f"/api/demandas/{self.demanda.pk}/preview-envio-oficial/"
        )
        self.assertEqual(preview.status_code, status.HTTP_200_OK)
        r = self.client.post(
            f"/api/demandas/{self.demanda.pk}/enviar/",
            {
                "declaracao": DECLARACAO_ENVIO,
                "hash_documento": preview.data["hash_documento"],
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.demanda.refresh_from_db()
        self.assertEqual(self.demanda.status, "AGUARDANDO_PROTOCOLO")
        self.assertTrue(self.demanda.protocolo_legislativo)
        self.assertTrue(AssinaturaEletronica.objects.filter(demanda=self.demanda).exists())
        self.assertTrue(
            Tramitacao.objects.filter(demanda=self.demanda, tipo="ENVIO_OFICIAL").exists()
        )

    def test_validar_assinatura_publico(self):
        preview = AssinaturaEletronicaService().preparar_preview_envio(self.demanda)
        assinatura = AssinaturaEletronicaService().registrar_assinatura(
            self.demanda,
            self.vereador,
            hash_documento_informado=preview["hash_documento"],
            declaracao=DECLARACAO_ENVIO,
        )
        from rest_framework.test import APIClient

        public_client = APIClient()
        r = public_client.get(f"/api/v1/validar-assinatura/{assinatura.codigo_validacao}/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data["valido"])


class EnviarLoteAssinaturaAPITests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.vereador = _legacy.Usuario.objects.create_user(
            username="ver_lote", password="x", perfil="VEREADOR"
        )
        self.client.force_authenticate(self.vereador)
        self.d1 = Demanda.objects.create(
            titulo="Lote A",
            descricao="<p>A</p>",
            autor=self.vereador,
            status="RASCUNHO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        self.d2 = Demanda.objects.create(
            titulo="Lote B",
            descricao="<p>B</p>",
            autor=self.vereador,
            status="RASCUNHO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )

    def test_preview_envio_lote(self):
        r = self.client.post(
            "/api/demandas/preview-envio-lote/",
            {"demanda_ids": [self.d1.pk, self.d2.pk]},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["total"], 2)
        self.assertEqual(len(r.data["itens"]), 2)

    def test_enviar_lote_assina_todos(self):
        preview = self.client.post(
            "/api/demandas/preview-envio-lote/",
            {"demanda_ids": [self.d1.pk, self.d2.pk]},
            format="json",
        )
        hashes = [
            {"demanda_id": item["demanda_id"], "hash_documento": item["hash_documento"]}
            for item in preview.data["itens"]
        ]
        r = self.client.post(
            "/api/demandas/enviar-lote/",
            {
                "demanda_ids": [self.d1.pk, self.d2.pk],
                "declaracao": DECLARACAO_ENVIO,
                "hashes": hashes,
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["total"], 2)
        self.d1.refresh_from_db()
        self.d2.refresh_from_db()
        self.assertEqual(self.d1.status, "AGUARDANDO_PROTOCOLO")
        self.assertEqual(self.d2.status, "AGUARDANDO_PROTOCOLO")
        self.assertEqual(AssinaturaEletronica.objects.filter(demanda__in=[self.d1, self.d2]).count(), 2)
