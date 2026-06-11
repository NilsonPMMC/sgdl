"""Testes de unidades administrativas (setores) e tramitação."""

import importlib.util

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Demanda, Tramitacao, Usuario
from core.models_unidade_administrativa import UnidadeAdministrativa
from core.services.demanda_despacho_service import DemandaDespachoService
from core.services.tramitacao_setor_service import TramitacaoSetorService

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_ORGAO_B = _legacy.SINAPSE_ORGAO_B
SINAPSE_SERVICO_ID = _legacy.SINAPSE_SERVICO_ID
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class UnidadeAdministrativaServiceTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.gestor = Usuario.objects.create_user(
            username="gestor_setor", password="x", perfil="GESTOR"
        )
        self.setor_a = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            nome="Obras Viárias",
            sigla="OBV",
        )
        self.setor_b = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_B,
            nome="Iluminação",
            sigla="ILU",
        )

    def test_despacho_com_setor(self):
        vereador = Usuario.objects.create_user(username="ver_set", password="x", perfil="VEREADOR")
        protocolo = Usuario.objects.create_user(username="prot_set", password="x", perfil="PROTOCOLO")
        demanda = Demanda.objects.create(
            titulo="Buraco",
            descricao="Reparo",
            autor=vereador,
            status="AGUARDANDO_PROTOCOLO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
        )
        DemandaDespachoService().despachar(
            demanda,
            secretaria_id=SINAPSE_ORGAO_A,
            usuario=protocolo,
            unidade_administrativa_id=self.setor_a.pk,
        )
        demanda.refresh_from_db()
        self.assertEqual(demanda.unidade_administrativa_id, self.setor_a.pk)
        self.assertTrue(
            Tramitacao.objects.filter(demanda=demanda, unidade_destino=self.setor_a).exists()
        )

    def test_encaminhamento_transversal(self):
        gestor = self.gestor
        vereador = Usuario.objects.create_user(username="ver_tr", password="x", perfil="VEREADOR")
        demanda = Demanda.objects.create(
            titulo="Lâmpada",
            descricao="Troca",
            autor=vereador,
            status="PROTOCOLADO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            unidade_administrativa=self.setor_a,
        )
        TramitacaoSetorService().encaminhar(
            demanda,
            unidade_destino_id=self.setor_b.pk,
            usuario=gestor,
        )
        demanda.refresh_from_db()
        self.assertEqual(demanda.unidade_administrativa_id, self.setor_b.pk)
        self.assertEqual(demanda.sinapse_orgao_id, SINAPSE_ORGAO_B)
        tram = Tramitacao.objects.filter(demanda=demanda, tipo="ENCAMINHAMENTO_SETOR").first()
        self.assertIsNotNone(tram)
        self.assertEqual(tram.unidade_origem_id, self.setor_a.pk)
        self.assertEqual(tram.unidade_destino_id, self.setor_b.pk)


class UnidadeAdministrativaAPITests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.gestor = Usuario.objects.create_user(
            username="gestor_api_set", password="x", perfil="GESTOR"
        )
        self.client.force_authenticate(self.gestor)

    def test_criar_setor(self):
        r = self.client.post(
            "/api/unidades-administrativas/",
            {
                "sinapse_orgao_id": SINAPSE_ORGAO_A,
                "nome": "Manutenção Urbana",
                "sigla": "MAN",
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data["sigla"], "MAN")

    def test_vincular_responsavel(self):
        unidade = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            nome="Zeladoria",
            sigla="ZEL",
        )
        secretaria = Usuario.objects.create_user(
            username="sec_zel",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        r = self.client.post(
            f"/api/unidades-administrativas/{unidade.pk}/responsaveis/",
            {"usuario_id": secretaria.pk},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["usuario_id"], secretaria.pk)
