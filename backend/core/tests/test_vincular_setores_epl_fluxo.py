"""Testes do comando vincular_setores_epl_fluxo."""

import importlib.util
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from core.models_carta_otimizada import ServicoOtimizado
from core.models_unidade_administrativa import UnidadeAdministrativa
from core.management.commands.vincular_setores_epl_fluxo import (
    REGRAS_EPL_PADRAO,
    iter_servicos_sinapse_orgao,
    resolver_unidade_epl,
)

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_SERVICO_ID = _legacy.SINAPSE_SERVICO_ID
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class VincularSetoresEplFluxoTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.orgao_id = 18
        self.servico_ref = 293
        self.sigla_epl = "MCRUZ-SMMT-DIVGG-EPL"
        self.ua, _ = UnidadeAdministrativa.objects.get_or_create(
            sinapse_orgao_id=self.orgao_id,
            sigla=self.sigla_epl,
            defaults={"nome": "EPL Mobilidade", "ativo": True},
        )
        ServicoOtimizado.objects.filter(sinapse_servico_id=SINAPSE_SERVICO_ID).delete()
        self.svc = ServicoOtimizado.objects.create(
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            titulo_otimizado="Serviço teste EPL",
            descricao_objetiva="Teste",
            texto_rag_otimizado="teste",
            ativo=True,
        )

    def test_resolver_unidade_epl_por_sigla(self):
        regra = next(r for r in REGRAS_EPL_PADRAO if r.sinapse_orgao_id == self.orgao_id)
        ua = resolver_unidade_epl(regra)
        self.assertEqual(ua.pk, self.ua.pk)

    def test_filtrar_por_servico_referencia(self):
        from core.management.commands.vincular_setores_epl_fluxo import filtrar_regras

        regras = filtrar_regras(293)
        self.assertEqual(len(regras), 1)
        self.assertEqual(regras[0].sinapse_orgao_id, 18)

    def test_filtrar_por_orgao_catalogo(self):
        from core.management.commands.vincular_setores_epl_fluxo import filtrar_regras

        regras = filtrar_regras(18)
        self.assertEqual(len(regras), 1)
        self.assertEqual(regras[0].sigla_ua, self.sigla_epl)

    @patch("integrations.sinapse_catalog.get_orgao_id_for_servico")
    @patch("integrations.sinapse_catalog.buscar_servicos_catalogo")
    def test_comando_vincula_servicos_do_orgao(self, mock_busca, mock_orgao_servico):
        mock_orgao_servico.return_value = self.orgao_id
        mock_busca.return_value = {
            "total": 1,
            "results": [{"id": SINAPSE_SERVICO_ID}],
            "catalogo_disponivel": True,
        }

        with patch(
            "core.management.commands.vincular_setores_epl_fluxo.sinapse_catalog.catalog_disponivel",
            return_value=True,
        ):
            out = StringIO()
            call_command(
                "vincular_setores_epl_fluxo",
                orgao_id=self.orgao_id,
                stdout=out,
            )

        self.svc.refresh_from_db()
        self.assertEqual(self.svc.unidade_administrativa_id, self.ua.pk)
        self.assertIn("vinculado(s)/atualizado(s)", out.getvalue())
        self.assertNotIn("[dry-run]", out.getvalue())

    @patch("integrations.sinapse_catalog.buscar_servicos_catalogo")
    def test_dry_run_nao_altera_banco(self, mock_busca):
        mock_busca.return_value = {
            "total": 1,
            "results": [{"id": SINAPSE_SERVICO_ID}],
            "catalogo_disponivel": True,
        }

        with patch(
            "core.management.commands.vincular_setores_epl_fluxo.sinapse_catalog.catalog_disponivel",
            return_value=True,
        ):
            call_command(
                "vincular_setores_epl_fluxo",
                orgao_id=self.orgao_id,
                dry_run=True,
            )

        self.svc.refresh_from_db()
        self.assertIsNone(self.svc.unidade_administrativa_id)

    def test_iter_servicos_pagina_catalogo(self):
        paginas = [
            {"total": 3, "results": [{"id": 1}, {"id": 2}]},
            {"total": 3, "results": [{"id": 3}]},
            {"total": 3, "results": []},
        ]

        with patch(
            "core.management.commands.vincular_setores_epl_fluxo.sinapse_catalog.buscar_servicos_catalogo",
            side_effect=paginas,
        ):
            ids = list(iter_servicos_sinapse_orgao(self.orgao_id, limit=2))

        self.assertEqual(ids, [1, 2, 3])
