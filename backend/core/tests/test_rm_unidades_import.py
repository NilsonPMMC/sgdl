"""Testes C6 — importação RM271698 e de-para."""

import importlib.util
from pathlib import Path

from django.test import TestCase

from core.models_depara_rm import DeParaRmSinapse
from core.models_unidade_administrativa import UnidadeAdministrativa
from core.services.rm_unidades_import_service import (
    RmUnidadesImportService,
    extrair_cod_rm,
    extrair_sigla_curta,
)

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A


class RmUnidadesImportServiceTests(TestCase):
    def test_extrair_cod_rm_e_sigla(self):
        sigla = "MCRUZ-SMSBE-SACPG"
        self.assertEqual(extrair_cod_rm(sigla), "SMSBE")
        self.assertEqual(extrair_sigla_curta(sigla), "SACPG")

    def test_importar_dry_run_respeita_depara(self):
        DeParaRmSinapse.objects.create(
            cod_rm="SMSBE",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            ativo=True,
        )
        DeParaRmSinapse.objects.create(cod_rm="SEMAE", sinapse_orgao_id=None, ativo=False)
        xlsx = Path(__file__).resolve().parents[3] / "docs" / "RM271698 - UNIDADES (1).xlsx"
        if not xlsx.is_file():
            self.skipTest("Planilha RM271698 ausente.")
        resultado = RmUnidadesImportService().importar(
            xlsx_path=xlsx,
            dry_run=True,
            carregar_csv=False,
        )
        self.assertEqual(resultado.total_linhas, 1191)
        self.assertGreater(resultado.importadas + resultado.atualizadas, 0)
        self.assertEqual(resultado.orfaos_por_cod.get("SEMAE"), 53)

    def test_importar_grava_unidade(self):
        DeParaRmSinapse.objects.create(
            cod_rm="SMGOV",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            ativo=True,
        )
        xlsx = Path(__file__).resolve().parents[3] / "docs" / "RM271698 - UNIDADES (1).xlsx"
        if not xlsx.is_file():
            self.skipTest("Planilha RM271698 ausente.")
        resultado = RmUnidadesImportService().importar(
            xlsx_path=xlsx,
            dry_run=False,
            carregar_csv=False,
        )
        self.assertGreater(resultado.importadas + resultado.atualizadas, 0)
        self.assertTrue(
            UnidadeAdministrativa.objects.filter(cod_rm_orgao="SMGOV").exists()
        )
