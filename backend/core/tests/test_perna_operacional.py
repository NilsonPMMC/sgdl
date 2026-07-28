"""Testes do serviço PernaOperacional (P3)."""

import importlib.util

from django.test import TestCase

from core.models import Demanda, Usuario
from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional
from core.services.demanda_despacho_service import DemandaDespachoService
from core.services.perna_operacional_service import PernaOperacionalService

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_ORGAO_B = _legacy.SINAPSE_ORGAO_B
SINAPSE_SERVICO_ID = _legacy.SINAPSE_SERVICO_ID
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class PernaOperacionalServiceTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.svc = PernaOperacionalService()
        self.vereador = Usuario.objects.create_user(
            username="ver_perna", password="x", perfil="VEREADOR"
        )
        self.protocolo = Usuario.objects.create_user(
            username="prot_perna", password="x", perfil="PROTOCOLO"
        )

    def _demanda(self):
        return Demanda.objects.create(
            titulo="Teste perna",
            descricao="x",
            autor=self.vereador,
            status="AGUARDANDO_PROTOCOLO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            protocolo_legislativo="PL-PERNA-001",
        )

    def test_despacho_cria_pernas_sem_clones(self):
        demanda = self._demanda()
        resultado = DemandaDespachoService().despachar_multiplo(
            demanda,
            [
                {"secretaria_id": SINAPSE_ORGAO_A},
                {"secretaria_id": SINAPSE_ORGAO_B},
            ],
            usuario=self.protocolo,
            texto_despacho="Despacho de teste para pernas operacionais.",
        )
        principal = resultado["demanda"]
        self.assertEqual(len(resultado["demandas_desdobradas"]), 0)
        self.assertEqual(resultado["total_pernas"], 2)
        pernas = PernaOperacional.objects.filter(demanda=principal)
        self.assertEqual(pernas.count(), 2)

    def test_despacho_transversal_conta_pernas(self):
        demanda = self._demanda()
        resultado = DemandaDespachoService().despachar_multiplo(
            demanda,
            [{"secretaria_id": SINAPSE_ORGAO_A}, {"secretaria_id": SINAPSE_ORGAO_B}],
            usuario=self.protocolo,
        )
        self.assertEqual(resultado["total_pernas"], 2)
        self.assertEqual(resultado["total_destinos"], 2)

    def test_visibilidade_secretaria_integrada(self):
        demanda = self._demanda()
        DemandaDespachoService().despachar_multiplo(
            demanda,
            [{"secretaria_id": SINAPSE_ORGAO_A}, {"secretaria_id": SINAPSE_ORGAO_B}],
            usuario=self.protocolo,
        )
        ids = self.svc.demanda_ids_visiveis_por_orgao(SINAPSE_ORGAO_B)
        self.assertEqual(len(ids), 1)

    def test_iniciar_execucao_ativa_pernas(self):
        demanda = self._demanda()
        DemandaDespachoService().despachar_multiplo(
            demanda,
            [{"secretaria_id": SINAPSE_ORGAO_A}],
            usuario=self.protocolo,
        )
        demanda.refresh_from_db()
        self.svc.iniciar_execucao_pernas(demanda)
        self.assertFalse(
            PernaOperacional.objects.filter(
                demanda=demanda, status=StatusPernaOperacional.PENDENTE
            ).exists()
        )
