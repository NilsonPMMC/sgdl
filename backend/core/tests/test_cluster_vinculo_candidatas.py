"""Testes de vinculação manual e candidatas Super OS."""

import importlib.util

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import ClusterExecucao, Demanda
from core.services.cluster_service import ClusterService

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)

ClusterServiceTests = _legacy.ClusterServiceTests
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A

User = get_user_model()


class ClusterVinculoCandidatasTests(ClusterServiceTests, APITestCase):
    def setUp(self):
        super().setUp()
        self.protocolo = User.objects.create_user(
            username="prot_vinc_cand",
            password="x",
            perfil="PROTOCOLO",
        )
        self.client.force_authenticate(self.protocolo)
        self.cluster = ClusterExecucao.objects.create(
            titulo="Grupo teste vinculo",
            status="ABERTO",
            sinapse_servico_id=self.SINAPSE_SERVICO_TAPA,
            bairro_referencia="Centro",
            centroide=self.vetor,
        )
        Demanda.objects.create(
            titulo="Líder",
            descricao="Líder",
            autor=self.autor,
            status="AGUARDANDO_PROTOCOLO",
            cluster=self.cluster,
            embedding=self.vetor,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            sinapse_servico_id=self.SINAPSE_SERVICO_TAPA,
            latitude=-23.52,
            longitude=-46.19,
            bairro="Centro",
        )
        self.solta = Demanda.objects.create(
            titulo="Solta compatível",
            descricao="Solta",
            autor=self.autor,
            status="AGUARDANDO_PROTOCOLO",
            embedding=self.vetor,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            sinapse_servico_id=self.SINAPSE_SERVICO_TAPA,
            latitude=-23.52001,
            longitude=-46.19001,
            bairro="Centro",
        )

    def test_listar_demandas_candidatas_sugeridas(self):
        url = f"/api/clusters/{self.cluster.pk}/demandas-candidatas/"
        r = self.client.get(url)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in r.data["results"]]
        self.assertIn(self.solta.pk, ids)
        item = next(x for x in r.data["results"] if x["id"] == self.solta.pk)
        self.assertTrue(item["compativel"])

    def test_avaliar_compatibilidade_mesmo_cluster(self):
        svc = ClusterService()
        aval = svc.avaliar_compatibilidade_vinculo(self.solta, self.cluster)
        self.assertTrue(aval["compativel"])

    def test_gestor_pode_vincular(self):
        gestor = User.objects.create_user(
            username="gestor_vinc",
            password="x",
            perfil="GESTOR",
        )
        self.client.force_authenticate(gestor)
        url = f"/api/clusters/{self.cluster.pk}/vincular/"
        r = self.client.post(url, {"demanda_id": self.solta.pk}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
