"""Líder operacional do cluster — prioriza demanda protocolada."""

import importlib.util

from django.test import TestCase

from core.models import ClusterExecucao, Demanda
from core.services.cluster_service import ClusterService

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_SERVICO_ID = _legacy.SINAPSE_SERVICO_ID
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class ClusterLiderOperacionalTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        from core.models import Usuario

        self.svc = ClusterService()
        self.ver_a = Usuario.objects.create_user(
            username="ver_lider_a", password="x", perfil="VEREADOR"
        )
        self.ver_b = Usuario.objects.create_user(
            username="ver_lider_b", password="x", perfil="VEREADOR"
        )
        self.cluster = ClusterExecucao.objects.create(
            titulo="Cluster líder operacional",
            status="EM_ANDAMENTO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
        )
        self.primeira = Demanda.objects.create(
            titulo="Primeira no cluster",
            descricao="x",
            autor=self.ver_a,
            status="EM_EXECUCAO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            protocolo_legislativo="OF-1",
            cluster=self.cluster,
        )
        self.protocolada = Demanda.objects.create(
            titulo="Protocolada depois",
            descricao="x",
            autor=self.ver_b,
            status="EM_EXECUCAO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            protocolo_legislativo="OF-2",
            protocolo_executivo="2026-0099",
            fluxo_roteamento="FLUXO_TRANSVERSAL",
            nos_ativos=2,
            cluster=self.cluster,
        )

    def test_lider_prioriza_demanda_com_protocolo_executivo(self):
        self.assertEqual(
            self.svc.lider_cluster_pk(int(self.cluster.pk)),
            int(self.protocolada.pk),
        )
        info = self.svc.info_operacional_super_os(self.protocolada)
        self.assertTrue(info["eh_lider"])
        info_seg = self.svc.info_operacional_super_os(self.primeira)
        self.assertFalse(info_seg["eh_lider"])
        self.assertEqual(info_seg["lider_id"], self.protocolada.pk)
