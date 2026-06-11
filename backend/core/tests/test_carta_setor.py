"""Testes C2 — vínculo carta otimizada → unidade administrativa."""

import importlib.util
import uuid
from unittest.mock import patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Demanda, Usuario
from core.models_carta_otimizada import ServicoOtimizado
from core.models_unidade_administrativa import UnidadeAdministrativa
from core.services.carta_setor_service import CartaSetorService
from core.services.demanda_despacho_service import DemandaDespachoService

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_ORGAO_B = _legacy.SINAPSE_ORGAO_B
SINAPSE_SERVICO_ID = _legacy.SINAPSE_SERVICO_ID
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class CartaSetorServiceTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.suffix = uuid.uuid4().hex[:8]
        self.setor_a = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            nome="Obras",
            sigla="OBR",
        )
        self.setor_b = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_B,
            nome="Outro orgao",
            sigla="OUT",
        )
        ServicoOtimizado.objects.filter(sinapse_servico_id=SINAPSE_SERVICO_ID).delete()
        self.svc_otim = ServicoOtimizado.objects.create(
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            titulo_otimizado="Tapa buraco",
            descricao_objetiva="Reparo",
            texto_rag_otimizado="tapa buraco",
            ativo=True,
        )
        self.vereador = Usuario.objects.create_user(
            username=f"ver_setor_{self.suffix}",
            password="x",
            perfil="VEREADOR",
        )
        self.svc = CartaSetorService()

    def test_vincular_setor_valido(self):
        obj = self.svc.vincular(SINAPSE_SERVICO_ID, self.setor_a.pk)
        self.assertEqual(obj.unidade_administrativa_id, self.setor_a.pk)

    def test_rejeita_setor_de_outro_orgao(self):
        with self.assertRaises(ValueError) as ctx:
            self.svc.vincular(SINAPSE_SERVICO_ID, self.setor_b.pk)
        self.assertIn("não pertence", str(ctx.exception))

    def test_resolver_prioriza_vinculo_carta(self):
        self.svc_otim.unidade_administrativa = self.setor_a
        self.svc_otim.save()
        resolvida = self.svc.resolver_unidade(SINAPSE_SERVICO_ID)
        self.assertEqual(resolvida.pk, self.setor_a.pk)

    def test_resolver_fallback_primeira_unidade_orgao(self):
        resolvida = self.svc.resolver_unidade(SINAPSE_SERVICO_ID)
        self.assertEqual(resolvida.pk, self.setor_a.pk)

    def test_despacho_automatico_aplica_setor(self):
        self.svc_otim.unidade_administrativa = self.setor_a
        self.svc_otim.save()
        demanda = Demanda.objects.create(
            titulo="Buraco",
            descricao="x",
            autor=self.vereador,
            status="AGUARDANDO_PROTOCOLO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            protocolo_legislativo=f"OF-{self.suffix}",
        )
        DemandaDespachoService().despachar(
            demanda,
            secretaria_id=SINAPSE_ORGAO_A,
            automatico=True,
        )
        demanda.refresh_from_db()
        self.assertEqual(demanda.unidade_administrativa_id, self.setor_a.pk)
        self.assertEqual(demanda.status, "PROTOCOLADO")

    def test_sem_vinculo_mantem_fallback_orgao(self):
        demanda = Demanda.objects.create(
            titulo="Sem vinculo explicito",
            descricao="x",
            autor=self.vereador,
            status="AGUARDANDO_PROTOCOLO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            protocolo_legislativo=f"OF3-{self.suffix}",
        )
        DemandaDespachoService().despachar(
            demanda,
            secretaria_id=SINAPSE_ORGAO_A,
            automatico=True,
        )
        demanda.refresh_from_db()
        self.assertEqual(demanda.unidade_administrativa_id, self.setor_a.pk)


class CartaSetorAPITests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.suffix = uuid.uuid4().hex[:8]
        self.gestor = Usuario.objects.create_user(
            username=f"ges_setor_{self.suffix}", password="x", perfil="GESTOR"
        )
        self.setor = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            nome="Obras",
            sigla="OBR",
        )
        ServicoOtimizado.objects.filter(sinapse_servico_id=SINAPSE_SERVICO_ID).delete()
        ServicoOtimizado.objects.create(
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            titulo_otimizado="Tapa buraco",
            descricao_objetiva="Reparo",
            texto_rag_otimizado="tapa buraco",
            ativo=True,
        )

    def test_gestor_vincula_setor(self):
        self.client.force_authenticate(self.gestor)
        r = self.client.post(
            "/api/carta-setores/upsert/",
            {
                "sinapse_servico_id": SINAPSE_SERVICO_ID,
                "unidade_administrativa_id": self.setor.pk,
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["unidade_administrativa_id"], self.setor.pk)

    def test_api_rejeita_setor_orgao_errado(self):
        outro = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_B,
            nome="Remoto",
            sigla="REM",
        )
        self.client.force_authenticate(self.gestor)
        r = self.client.post(
            "/api/carta-setores/upsert/",
            {
                "sinapse_servico_id": SINAPSE_SERVICO_ID,
                "unidade_administrativa_id": outro.pk,
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("não pertence", r.data["detail"])
