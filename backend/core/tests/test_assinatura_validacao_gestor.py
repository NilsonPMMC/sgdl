"""Testes — validação assíncrona de assinaturas pelo gestor."""

import importlib.util

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Demanda, Usuario
from core.models_assinatura_eletronica import (
    AssinaturaEletronica,
    AssinaturaValidacaoGestor,
)
from core.models_unidade_administrativa import UnidadeAdministrativaResponsavel
from core.services.assinatura_eletronica_service import (
    DECLARACAO_DESPACHO,
    DECLARACAO_GESTOR_PROTOCOLO,
    AssinaturaEletronicaService,
)
from core.services.tramitacao_janela_edicao_service import TramitacaoJanelaEdicaoService
from core.services.usuario_vinculo_service import PROTOCOLO_UNIDADE_PK

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_SERVICO_ID = _legacy.SINAPSE_SERVICO_ID
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class AssinaturaValidacaoGestorServiceTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.vereador = Usuario.objects.create_user(
            username="ver_val", password="x", perfil="VEREADOR"
        )
        self.operador = Usuario.objects.create_user(
            username="op_val", password="x", perfil="PROTOCOLO", cargo="Operador"
        )
        self.gestor = Usuario.objects.create_user(
            username="gest_val",
            password="x",
            perfil="GESTOR",
            cargo="Gestor SGAC",
        )
        UnidadeAdministrativaResponsavel.objects.create(
            unidade_id=PROTOCOLO_UNIDADE_PK,
            usuario=self.gestor,
            ativo=True,
        )
        self.demanda = Demanda.objects.create(
            titulo="Validação gestor",
            descricao="Teste",
            autor=self.vereador,
            status="AGUARDANDO_PROTOCOLO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )

    def test_despacho_inicial_cria_validacao_pendente(self):
        svc = AssinaturaEletronicaService()
        preview = svc.preparar_assinatura_despacho_inicial(
            self.demanda,
            secretaria_id=SINAPSE_ORGAO_A,
            unidade_administrativa_id=None,
            protocolo_executivo="2026/0301",
        )
        svc.registrar_assinaturas_despacho_inicial(
            self.demanda,
            self.operador,
            hash_documento=preview["hash_documento"],
            declaracao_operador=DECLARACAO_DESPACHO,
            contexto_operacao={
                "destinos": [{"secretaria_id": SINAPSE_ORGAO_A, "unidade_administrativa_id": None}],
                "texto_despacho": "Despacho inicial aguardando gestor.",
            },
        )
        self.demanda.refresh_from_db()
        self.assertEqual(self.demanda.status, "AGUARDANDO_PROTOCOLO")
        resumo = svc.resumo_assinaturas_demanda(self.demanda)
        self.assertFalse(resumo["despacho_inicial_assinado"])
        self.assertTrue(resumo["despacho_inicial_pendente_gestor"])
        self.assertTrue(
            AssinaturaValidacaoGestor.objects.filter(
                demanda=self.demanda,
                etapa=AssinaturaEletronica.ETAPA_DESPACHO_INICIAL,
                status=AssinaturaValidacaoGestor.STATUS_PENDENTE,
            ).exists()
        )
        tram = self.demanda.tramitacoes.filter(tipo="DESPACHO").first()
        self.assertIsNotNone(tram)
        self.assertTrue(
            (tram.metadata or {}).get("aguardando_validacao_gestor"),
            "Despacho deve aparecer na timeline enquanto aguarda gestor",
        )
        self.assertIsNotNone(tram.editavel_ate)
        self.assertGreater(
            TramitacaoJanelaEdicaoService.segundos_restantes(tram),
            0,
        )

    def test_gestor_valida_despacho_inicial(self):
        svc = AssinaturaEletronicaService()
        preview = svc.preparar_assinatura_despacho_inicial(
            self.demanda,
            secretaria_id=SINAPSE_ORGAO_A,
            unidade_administrativa_id=None,
            protocolo_executivo="2026/0302",
        )
        svc.registrar_assinaturas_despacho_inicial(
            self.demanda,
            self.operador,
            hash_documento=preview["hash_documento"],
            declaracao_operador=DECLARACAO_DESPACHO,
            contexto_operacao={
                "destinos": [{"secretaria_id": SINAPSE_ORGAO_A, "unidade_administrativa_id": None}],
                "texto_despacho": "Despacho após gestor.",
            },
        )
        validacao = AssinaturaValidacaoGestor.objects.get(
            demanda=self.demanda,
            etapa=AssinaturaEletronica.ETAPA_DESPACHO_INICIAL,
        )
        self.assertEqual(self.demanda.status, "AGUARDANDO_PROTOCOLO")
        svc.registrar_validacao_gestor(
            validacao,
            self.gestor,
            hash_documento=preview["hash_documento"],
            declaracao_gestor=DECLARACAO_GESTOR_PROTOCOLO,
        )
        self.demanda.refresh_from_db()
        self.assertNotEqual(self.demanda.status, "AGUARDANDO_PROTOCOLO")
        tram = self.demanda.tramitacoes.filter(tipo="DESPACHO").order_by("-timestamp").first()
        self.assertIsNotNone(tram)
        self.assertFalse((tram.metadata or {}).get("aguardando_validacao_gestor"))
        self.assertIsNotNone(tram.editavel_ate)
        resumo = svc.resumo_assinaturas_demanda(self.demanda)
        self.assertTrue(resumo["despacho_inicial_assinado"])
        self.assertFalse(resumo["despacho_inicial_pendente_gestor"])


class AssinaturaValidacaoGestorAPITests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.vereador = Usuario.objects.create_user(
            username="ver_val_api", password="x", perfil="VEREADOR"
        )
        self.operador = Usuario.objects.create_user(
            username="op_val_api", password="x", perfil="PROTOCOLO"
        )
        self.gestor = Usuario.objects.create_user(
            username="gest_val_api", password="x", perfil="GESTOR"
        )
        UnidadeAdministrativaResponsavel.objects.create(
            unidade_id=PROTOCOLO_UNIDADE_PK,
            usuario=self.gestor,
            ativo=True,
        )
        self.demanda = Demanda.objects.create(
            titulo="API validação",
            descricao="Teste",
            autor=self.vereador,
            status="AGUARDANDO_PROTOCOLO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            protocolo_executivo="2026/0303",
        )
        svc = AssinaturaEletronicaService()
        preview = svc.preparar_assinatura_despacho_inicial(
            self.demanda,
            secretaria_id=SINAPSE_ORGAO_A,
            unidade_administrativa_id=None,
            protocolo_executivo="2026/0303",
        )
        svc.registrar_assinaturas_despacho_inicial(
            self.demanda,
            self.operador,
            hash_documento=preview["hash_documento"],
            declaracao_operador=DECLARACAO_DESPACHO,
            contexto_operacao={
                "destinos": [{"secretaria_id": SINAPSE_ORGAO_A, "unidade_administrativa_id": None}],
                "texto_despacho": "Despacho API validação.",
            },
        )
        self.validacao = AssinaturaValidacaoGestor.objects.get(demanda=self.demanda)
        self.hash_doc = preview["hash_documento"]

    def test_listar_pendentes_gestor(self):
        self.client.force_authenticate(self.gestor)
        r = self.client.get("/api/assinaturas-validacao/pendentes/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["total"], 1)

    def test_validar_assinatura_gestor(self):
        self.client.force_authenticate(self.gestor)
        preview = self.client.post(
            f"/api/assinaturas-validacao/{self.validacao.pk}/preview/",
            {},
            format="json",
        )
        self.assertEqual(preview.status_code, status.HTTP_200_OK)
        r = self.client.post(
            f"/api/assinaturas-validacao/{self.validacao.pk}/validar/",
            {
                "hash_documento": self.hash_doc,
                "declaracao_gestor": DECLARACAO_GESTOR_PROTOCOLO,
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.validacao.refresh_from_db()
        self.assertEqual(self.validacao.status, AssinaturaValidacaoGestor.STATUS_CONCLUIDA)
