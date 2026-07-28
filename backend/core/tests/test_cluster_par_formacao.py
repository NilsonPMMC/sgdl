"""Testes de formação de par cluster (inclui protocolado + aguardando)."""

import importlib.util

from django.test import TestCase, override_settings

from core.models import Demanda
from core.models import ClusterExecucao
from core.services.cluster_service import CLUSTER_MIN_DEMANDAS, ClusterService

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


@override_settings(
    CLUSTER_ENABLED=True,
    CLUSTER_SEMANTIC_THRESHOLD=0.7,
    CLUSTER_RADIUS_METERS=300,
    CLUSTER_FORMACAO_GRACE_MINUTES=20,
)
class ClusterParFormacaoTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.vereador = _legacy.Usuario.objects.create_user(
            username="ver_cluster_par", password="x", perfil="VEREADOR"
        )
        self.svc = ClusterService()
        self.vetor_base = [1.0] + [0.0] * 1023
        self.vetor_similar = [0.99] + [0.01] * 1023

    def _demanda(self, *, titulo, status, vetor):
        return Demanda.objects.create(
            titulo=titulo,
            descricao=titulo,
            autor=self.vereador,
            status=status,
            sinapse_servico_id=80,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            latitude=-23.536553,
            longitude=-46.209722,
            bairro="Vila Lavinia",
            embedding=vetor,
        )

    def test_par_com_demanda_ja_protocolada(self):
        """Segunda demanda na fila deve agrupar com par já protocolado (caso 2774/2775)."""
        d_protocolada = self._demanda(
            titulo="Buraco A", status="PROTOCOLADO", vetor=self.vetor_base
        )
        d_fila = self._demanda(
            titulo="Buraco B",
            status="AGUARDANDO_PROTOCOLO",
            vetor=self.vetor_similar,
        )

        cluster = self.svc.atribuir_demanda(d_fila)
        self.assertIsNotNone(cluster)
        d_protocolada.refresh_from_db()
        d_fila.refresh_from_db()
        self.assertEqual(d_protocolada.cluster_id, d_fila.cluster_id)
        self.assertGreaterEqual(
            Demanda.objects.filter(cluster_id=cluster.pk).count(),
            CLUSTER_MIN_DEMANDAS,
        )

    def test_deve_aguardar_rascunho_do_mesmo_servico(self):
        self._demanda(
            titulo="Rascunho par", status="RASCUNHO", vetor=self.vetor_base
        )
        aguardando = self._demanda(
            titulo="Na fila",
            status="AGUARDANDO_PROTOCOLO",
            vetor=self.vetor_similar,
        )
        self.assertTrue(self.svc.deve_aguardar_par_para_demanda(aguardando))

    def test_rascunho_com_embedding_nao_recebe_cluster(self):
        rascunho = self._demanda(
            titulo="Só rascunho", status="RASCUNHO", vetor=self.vetor_base
        )
        self.assertIsNone(self.svc.atribuir_demanda(rascunho))
        rascunho.refresh_from_db()
        self.assertIsNone(rascunho.cluster_id)

    def test_rascunho_nao_entra_como_par_na_formacao(self):
        self._demanda(
            titulo="Rascunho par", status="RASCUNHO", vetor=self.vetor_base
        )
        aguardando = self._demanda(
            titulo="Na fila",
            status="AGUARDANDO_PROTOCOLO",
            vetor=self.vetor_similar,
        )
        self.assertIsNone(self.svc.atribuir_demanda(aguardando))
        aguardando.refresh_from_db()
        self.assertIsNone(aguardando.cluster_id)

    def test_rascunho_perde_vinculo_cluster_ao_salvar(self):
        cluster = ClusterExecucao.objects.create(
            titulo="Cluster teste", status="ABERTO"
        )
        rascunho = self._demanda(
            titulo="Rascunho vinculado",
            status="AGUARDANDO_PROTOCOLO",
            vetor=self.vetor_base,
        )
        rascunho.cluster = cluster
        rascunho.save(update_fields=["cluster"])
        rascunho.status = "RASCUNHO"
        rascunho.save(update_fields=["status"])
        rascunho.refresh_from_db()
        self.assertIsNone(rascunho.cluster_id)
