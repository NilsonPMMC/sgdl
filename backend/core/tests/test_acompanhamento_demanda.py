"""Acompanhamento gerencial de processos (fixar/desfixar)."""

import importlib.util

from django.test import TestCase
from rest_framework.test import APIClient

from core.models import Demanda, Notificacao, Usuario
from core.models_acompanhamento import DemandaAcompanhamento
from core.models_no_operacional import NoOperacional, StatusNoOperacional
from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional
from core.services.acompanhamento_demanda_service import AcompanhamentoDemandaService

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_ORGAO_B = _legacy.SINAPSE_ORGAO_B
SINAPSE_SERVICO_ID = _legacy.SINAPSE_SERVICO_ID
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class AcompanhamentoDemandaTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.vereador = Usuario.objects.create_user(
            username="ver_acomp", password="x", perfil="VEREADOR"
        )
        self.sec_a = Usuario.objects.create_user(
            username="sec_acomp",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        self.gestor_geral = Usuario.objects.create_user(
            username="gestor_geral_acomp",
            password="x",
            perfil="GESTOR",
            is_staff=True,
        )
        self.demanda = Demanda.objects.create(
            titulo="Processo acompanhamento",
            descricao="x",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_orgao_id=SINAPSE_ORGAO_B,
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            protocolo_executivo="2026-ACOMP-01",
            nos_ativos=1,
        )
        PernaOperacional.objects.create(
            demanda=self.demanda,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            status=StatusPernaOperacional.CONCLUIDA,
        )
        NoOperacional.objects.create(
            demanda=self.demanda,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            status=StatusNoOperacional.CONCLUIDO,
        )

    def test_secretaria_pode_fixar_apos_participacao(self):
        svc = AcompanhamentoDemandaService()
        self.assertTrue(svc.pode_acompanhar(self.sec_a, self.demanda))
        registro = svc.acompanhar(self.sec_a, self.demanda, origem=DemandaAcompanhamento.ORIGEM_MANUAL)
        self.assertTrue(registro.ativo)

    def test_listagem_aba_acompanhando(self):
        AcompanhamentoDemandaService().acompanhar(self.sec_a, self.demanda)
        client = APIClient()
        client.force_authenticate(self.sec_a)
        r = client.get(
            "/api/demandas/",
            {"fila": "operacionais", "escopo_setor": "acompanhando"},
        )
        self.assertEqual(r.status_code, 200)
        ids = {row["id"] for row in r.data["results"]} if "results" in r.data else {row["id"] for row in r.data}
        self.assertIn(self.demanda.pk, ids)

    def test_desfixar_via_api(self):
        svc = AcompanhamentoDemandaService()
        svc.acompanhar(self.sec_a, self.demanda)
        client = APIClient()
        client.force_authenticate(self.sec_a)
        r = client.post(f"/api/demandas/{self.demanda.pk}/desacompanhar/")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data.get("acompanhando"))
        self.assertFalse(
            DemandaAcompanhamento.objects.filter(
                usuario=self.sec_a, demanda=self.demanda, ativo=True
            ).exists()
        )

    def test_finalizacao_encerra_acompanhamentos(self):
        svc = AcompanhamentoDemandaService()
        svc.acompanhar(self.sec_a, self.demanda)
        self.demanda.status = "FINALIZADO"
        self.demanda.save(update_fields=["status"])
        self.assertFalse(
            DemandaAcompanhamento.objects.filter(
                usuario=self.sec_a, demanda=self.demanda, ativo=True
            ).exists()
        )

    def test_gestor_geral_pode_fixar_processo_em_operacao(self):
        svc = AcompanhamentoDemandaService()
        self.assertTrue(svc.pode_acompanhar(self.gestor_geral, self.demanda))
        svc.acompanhar(self.gestor_geral, self.demanda)

    def test_fixado_nao_aparece_na_aba_encerrado(self):
        from core.services.demanda_visibilidade import demanda_ids_encerrado_setor

        svc = AcompanhamentoDemandaService()
        svc.acompanhar(self.sec_a, self.demanda)
        ids_encerrado = demanda_ids_encerrado_setor(self.sec_a)
        self.assertNotIn(self.demanda.pk, ids_encerrado)

        client = APIClient()
        client.force_authenticate(self.sec_a)
        r = client.get(
            "/api/demandas/",
            {"fila": "operacionais", "escopo_setor": "encerrado"},
        )
        self.assertEqual(r.status_code, 200)
        ids = {row["id"] for row in r.data["results"]} if "results" in r.data else {row["id"] for row in r.data}
        self.assertNotIn(self.demanda.pk, ids)

    def test_notificacao_marco_para_acompanhante(self):
        svc = AcompanhamentoDemandaService()
        svc.acompanhar(self.sec_a, self.demanda)
        from core.services.notificacao_service import NotificacaoService

        criadas = NotificacaoService().notificar_todos_nos_encerrados(self.demanda)
        self.assertGreater(criadas, 0)
        self.assertTrue(
            Notificacao.objects.filter(
                destinatario=self.sec_a,
                mensagem__contains="[Acompanhamento]",
            ).exists()
        )
