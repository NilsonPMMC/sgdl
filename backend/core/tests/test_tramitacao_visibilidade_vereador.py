"""Testes P8 — tramitações visíveis ao vereador."""

import importlib.util

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Demanda, Tramitacao, Usuario
from core.services.tramitacao_visibilidade_service import (
    TIPOS_TRAMITACAO_VISIVEIS_VEREADOR,
    filtrar_tramitacoes_para_usuario,
    tramitacao_visivel_para_vereador,
)

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_SERVICO_ID = _legacy.SINAPSE_SERVICO_ID
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class TramitacaoVisibilidadeServiceTests(TestCase):
    def test_tipos_operacionais_ocultos(self):
        self.assertFalse(tramitacao_visivel_para_vereador("EXECUCAO"))
        self.assertFalse(tramitacao_visivel_para_vereador("TRANSFERENCIA"))
        self.assertFalse(tramitacao_visivel_para_vereador("COMENTARIO"))

    def test_marcos_legislativos_visiveis(self):
        self.assertTrue(tramitacao_visivel_para_vereador("CONCLUSAO"))
        self.assertTrue(tramitacao_visivel_para_vereador("DESPACHO"))
        self.assertTrue(tramitacao_visivel_para_vereador("ENVIO_OFICIAL"))

    def test_filtro_queryset_vereador(self):
        vereador = Usuario.objects.create_user(username="ver_vis", password="x", perfil="VEREADOR")
        demanda = Demanda.objects.create(
            titulo="Teste visibilidade",
            descricao="x",
            autor=vereador,
            status="EM_EXECUCAO",
        )
        Tramitacao.objects.create(
            demanda=demanda, responsavel=vereador, tipo="DESPACHO", descricao="Despacho"
        )
        Tramitacao.objects.create(
            demanda=demanda, responsavel=vereador, tipo="EXECUCAO", descricao="Andamento interno"
        )
        Tramitacao.objects.create(
            demanda=demanda, responsavel=vereador, tipo="CONCLUSAO", descricao="Concluído"
        )
        qs = filtrar_tramitacoes_para_usuario(demanda.tramitacoes.all(), vereador)
        tipos = set(qs.values_list("tipo", flat=True))
        self.assertEqual(tipos, {"DESPACHO", "CONCLUSAO"})
        self.assertEqual(len(TIPOS_TRAMITACAO_VISIVEIS_VEREADOR), 7)


class TramitacaoVisibilidadeAPITests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.vereador = Usuario.objects.create_user(
            username="ver_api_vis", password="x", perfil="VEREADOR"
        )
        self.protocolo = Usuario.objects.create_user(
            username="prot_api_vis", password="x", perfil="PROTOCOLO"
        )
        self.demanda = Demanda.objects.create(
            titulo="Demanda timeline",
            descricao="Texto",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            protocolo_executivo="2026-0200",
            protocolo_legislativo="OFICIO-2026-0200",
        )
        Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.protocolo,
            tipo="DESPACHO",
            descricao="Encaminhado à secretaria",
        )
        Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.protocolo,
            tipo="EXECUCAO",
            descricao="Vistoria técnica realizada",
        )
        Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.protocolo,
            tipo="CONCLUSAO",
            descricao="Serviço executado",
        )

    def test_vereador_nao_ve_tramitacoes_operacionais_na_api(self):
        self.client.force_authenticate(self.vereador)
        r = self.client.get(f"/api/demandas/{self.demanda.id}/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        tipos = {t["tipo"] for t in r.data["tramitacoes"]}
        self.assertEqual(tipos, {"DESPACHO", "CONCLUSAO"})
        self.assertNotIn("EXECUCAO", tipos)

    def test_protocolo_ve_timeline_completa(self):
        self.client.force_authenticate(self.protocolo)
        r = self.client.get(f"/api/demandas/{self.demanda.id}/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        tipos = {t["tipo"] for t in r.data["tramitacoes"]}
        self.assertEqual(tipos, {"DESPACHO", "EXECUCAO", "CONCLUSAO"})
