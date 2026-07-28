"""H3-02 — visibilidade de clones multi-secretaria (B5)."""

import importlib.util

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import ClusterExecucao, Demanda, Usuario
from core.services.cluster_service import ClusterService
from core.services.demanda_despacho_service import DemandaDespachoService
from core.services.demanda_visibilidade import aplicar_escopo_demanda

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_ORGAO_B = _legacy.SINAPSE_ORGAO_B
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class ClusterMultiDestinoVisibilidadeTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.vereador = Usuario.objects.create_user(
            username="ver_multi_vis", password="x", perfil="VEREADOR"
        )
        self.sec_b = Usuario.objects.create_user(
            username="sec_multi_b",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_B,
        )
        self.svc = ClusterService()

    def _cluster_multi_destino(self):
        cluster = ClusterExecucao.objects.create(
            titulo="Multi-destino teste",
            status="EM_ANDAMENTO",
        )
        lider = Demanda.objects.create(
            titulo="Líder org A",
            descricao="x",
            autor=self.vereador,
            status="PROTOCOLADO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            cluster=cluster,
        )
        clone = Demanda.objects.create(
            titulo="Clone org B",
            descricao="x",
            autor=self.vereador,
            status="PROTOCOLADO",
            sinapse_orgao_id=SINAPSE_ORGAO_B,
            cluster=cluster,
        )
        return lider, clone

    def test_grupo_super_os_inativo_em_multi_destino(self):
        lider, clone = self._cluster_multi_destino()
        self.assertFalse(self.svc.grupo_super_os_ativo(lider))
        self.assertFalse(self.svc.grupo_super_os_ativo(clone))

    def test_info_super_os_lista_vinculados_em_multi_destino(self):
        lider, clone = self._cluster_multi_destino()
        cluster = lider.cluster
        cluster.protocolo_super_os = "SUPER-TEST-001"
        cluster.save(update_fields=["protocolo_super_os"])

        info = self.svc.info_operacional_super_os(clone)
        self.assertFalse(info["ativo"])
        self.assertEqual(info["tipo"], "MULTI_DESTINO")
        self.assertEqual(len(info["demandas_vinculadas"]), 2)
        self.assertEqual(info["lider_id"], lider.pk)
        self.assertFalse(info["eh_lider"])
        self.assertTrue(info["orgaos_envolvidos"])

    def test_filtrar_listagem_mantem_clone_multi_destino(self):
        lider, clone = self._cluster_multi_destino()
        qs = aplicar_escopo_demanda(Demanda.objects.all(), self.sec_b)
        ids = set(self.svc.filtrar_listagem_apenas_lideres(qs).values_list("pk", flat=True))
        self.assertEqual(ids, {clone.pk})
        self.assertNotIn(lider.pk, ids)

    def test_super_os_mesmo_orgao_continua_ocultando_nao_lider(self):
        cluster = ClusterExecucao.objects.create(titulo="Super OS", status="EM_ANDAMENTO")
        lider = Demanda.objects.create(
            titulo="Líder",
            descricao="x",
            autor=self.vereador,
            status="PROTOCOLADO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            cluster=cluster,
        )
        filho = Demanda.objects.create(
            titulo="Filho",
            descricao="x",
            autor=self.vereador,
            status="PROTOCOLADO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            cluster=cluster,
        )
        self.assertTrue(self.svc.grupo_super_os_ativo(lider))
        sec_a = Usuario.objects.create_user(
            username="sec_multi_a",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        qs = aplicar_escopo_demanda(Demanda.objects.all(), sec_a)
        ids = set(self.svc.filtrar_listagem_apenas_lideres(qs).values_list("pk", flat=True))
        self.assertEqual(ids, {lider.pk})
        self.assertNotIn(filho.pk, ids)


class DespachoMultiDestinoAPITests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.vereador = Usuario.objects.create_user(
            username="ver_multi_api", password="x", perfil="VEREADOR"
        )
        self.protocolo = Usuario.objects.create_user(
            username="prot_multi", password="x", perfil="PROTOCOLO"
        )
        self.sec_b = Usuario.objects.create_user(
            username="sec_api_b",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_B,
        )
        self.demanda = Demanda.objects.create(
            titulo="Demanda multi-destino",
            descricao="Teste H3-02",
            autor=self.vereador,
            status="AGUARDANDO_PROTOCOLO",
            sinapse_servico_id=80,
            protocolo_legislativo="PL-TEST-001",
        )

    def test_secretaria_b_ve_demanda_principal_apos_despacho_multiplo(self):
        resultado = DemandaDespachoService().despachar_multiplo(
            self.demanda,
            [
                {"secretaria_id": SINAPSE_ORGAO_A},
                {"secretaria_id": SINAPSE_ORGAO_B},
            ],
            usuario=self.protocolo,
            texto_despacho="Despacho formal para as secretarias responsáveis pelo serviço.",
        )
        principal = resultado["demanda"]
        self.assertEqual(len(resultado["demandas_desdobradas"]), 0)
        self.assertEqual(len(resultado["pernas_operacionais"]), 2)

        self.client.force_authenticate(self.sec_b)
        r_list = self.client.get("/api/demandas/")
        self.assertEqual(r_list.status_code, status.HTTP_200_OK)
        ids_lista = {item["id"] for item in r_list.data}
        self.assertIn(principal.pk, ids_lista)

        r_detail = self.client.get(f"/api/demandas/{principal.pk}/")
        self.assertEqual(r_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(r_detail.data["id"], principal.pk)
