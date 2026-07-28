"""Testes de visibilidade scatter-gather na timeline/API."""

import importlib.util

from django.test import TestCase

from core.models import Demanda, Tramitacao
from core.services.scatter_gather_visibilidade import (
    queryset_excluir_scatter_sistema,
    tramitacao_operacional_visivel,
    tramitacao_scatter_sistema,
)

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class ScatterGatherVisibilidadeTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        from core.models import Usuario

        self.vereador = Usuario.objects.create_user(
            username="ver_vis", password="x", perfil="VEREADOR"
        )
        self.demanda = Demanda.objects.create(
            titulo="Vis scatter",
            descricao="x",
            autor=self.vereador,
            status="EM_EXECUCAO",
        )

    def test_bootstrap_e_inicio_sao_sistema(self):
        bootstrap = Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.vereador,
            tipo="OPERACAO_NO",
            descricao="Nó operacional raiz aberto.",
            metadata={"acao_no": "BOOTSTRAP", "scatter_gather": True},
        )
        inicio = Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.vereador,
            tipo="STATUS_UPDATE",
            descricao="Início da etapa operacional (scatter-gather).",
            metadata={"scatter_gather": True, "automatico": True},
        )
        usuario = Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.vereador,
            tipo="OPERACAO_NO",
            descricao="Vistoria técnica solicitada.",
            metadata={"acao_no": "DESPACHAR", "scatter_gather": True},
        )
        self.assertTrue(tramitacao_scatter_sistema(bootstrap))
        self.assertTrue(tramitacao_scatter_sistema(inicio))
        self.assertFalse(tramitacao_scatter_sistema(usuario))
        self.assertFalse(tramitacao_operacional_visivel(bootstrap))
        self.assertFalse(tramitacao_operacional_visivel(inicio))
        self.assertTrue(tramitacao_operacional_visivel(usuario))

    def test_abertura_e_encaminhamento_ocultos_na_timeline(self):
        abertura = Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.vereador,
            tipo="OPERACAO_NO",
            descricao="Abertura via protocolo.",
            metadata={"acao_no": "ABERTURA_NO", "scatter_gather": True},
        )
        encaminhamento = Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.vereador,
            tipo="OPERACAO_NO",
            descricao="Encaminhamento para SEMAE.",
            metadata={"acao_no": "ENCAMINHAMENTO_NO", "scatter_gather": True},
        )
        self.assertFalse(tramitacao_operacional_visivel(abertura))
        self.assertFalse(tramitacao_operacional_visivel(encaminhamento))

    def test_queryset_exclui_eventos_sistema(self):
        Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.vereador,
            tipo="OPERACAO_NO",
            descricao="bootstrap",
            metadata={"acao_no": "BOOTSTRAP"},
        )
        Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.vereador,
            tipo="OPERACAO_NO",
            descricao="Despacho real",
            metadata={"acao_no": "DESPACHAR"},
        )
        qs = queryset_excluir_scatter_sistema(self.demanda.tramitacoes.all())
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().descricao, "Despacho real")
