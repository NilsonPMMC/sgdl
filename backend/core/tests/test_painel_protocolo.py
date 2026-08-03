from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import ClusterExecucao, Demanda, Usuario
import importlib.util

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


def _rows(response):
    data = response.data
    if isinstance(data, dict):
        return data.get("results", [])
    return list(data)


class PainelProtocoloFilterTests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.protocolo = Usuario.objects.create_user(
            username="prot_painel", password="x", perfil="PROTOCOLO"
        )
        self.vereador = Usuario.objects.create_user(
            username="ver_painel", password="x", perfil="VEREADOR"
        )
        self.client.force_authenticate(self.protocolo)
        agora = timezone.now()

        self.aguardando = Demanda.objects.create(
            titulo="Aguardando",
            descricao="x",
            autor=self.vereador,
            status="AGUARDANDO_PROTOCOLO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            data_entrada_etapa=agora - timezone.timedelta(hours=5),
        )
        self.protocolada = Demanda.objects.create(
            titulo="Protocolada",
            descricao="x",
            autor=self.vereador,
            status="PROTOCOLADO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            data_entrada_etapa=agora - timezone.timedelta(hours=1),
        )
        self.em_exec = Demanda.objects.create(
            titulo="Execução",
            descricao="x",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            data_entrada_etapa=agora - timezone.timedelta(hours=2),
        )

    def test_fila_protocolados(self):
        r = self.client.get("/api/demandas/", {"fila": "protocolados"})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = [d["id"] for d in _rows(r)]
        self.assertEqual(ids, [self.aguardando.id])

    def test_fila_operacionais_fifo(self):
        r = self.client.get("/api/demandas/", {"fila": "operacionais"})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = [d["id"] for d in _rows(r)]
        self.assertEqual(ids, [self.protocolada.id, self.em_exec.id])

    def test_resposta_inclui_temporizador(self):
        r = self.client.get("/api/demandas/", {"fila": "protocolados"})
        row = _rows(r)[0]
        self.assertIn("tempo_parado_segundos", row)
        self.assertGreaterEqual(row["tempo_parado_segundos"], 0)
        self.assertIn("data_entrada_etapa", row)
        self.assertIsNotNone(row["data_entrada_etapa"])


class PainelProtocoloSuperOsTests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.protocolo = Usuario.objects.create_user(
            username="prot_super_os", password="x", perfil="PROTOCOLO"
        )
        self.vereador = Usuario.objects.create_user(
            username="ver_super_os", password="x", perfil="VEREADOR"
        )
        self.client.force_authenticate(self.protocolo)
        self.cluster = ClusterExecucao.objects.create(
            titulo="Super OS teste",
            status="EM_ANDAMENTO",
        )
        self.lider = Demanda.objects.create(
            titulo="Líder Super OS",
            descricao="x",
            autor=self.vereador,
            status="AGUARDANDO_PROTOCOLO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            cluster=self.cluster,
        )
        self.seguidora = Demanda.objects.create(
            titulo="Seguidora Super OS",
            descricao="x",
            autor=self.vereador,
            status="AGUARDANDO_PROTOCOLO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            cluster=self.cluster,
        )

    def test_fila_protocolados_lista_apenas_lider_super_os_hjul05(self):
        r = self.client.get("/api/demandas/", {"fila": "protocolados"})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = [d["id"] for d in _rows(r)]
        self.assertEqual(ids, [self.lider.id])

    def test_resumo_hub_protocolados_conta_apenas_lider(self):
        from core.services.consulta_hub_service import ConsultaHubService

        resumo = ConsultaHubService().resumo_painel_protocolo(self.protocolo)
        self.assertEqual(resumo["protocolados"], 1)


class PainelProtocoloSuperOsDespachoTimelineTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.protocolo = Usuario.objects.create_user(
            username="prot_super_tl", password="x", perfil="PROTOCOLO"
        )
        self.vereador = Usuario.objects.create_user(
            username="ver_super_tl", password="x", perfil="VEREADOR"
        )
        self.vetor = [1.0] + [0.0] * 1023
        self.cluster = ClusterExecucao.objects.create(
            titulo="Super OS timeline",
            status="ABERTO",
            centroide=self.vetor,
        )
        self.lider = Demanda.objects.create(
            titulo="Líder timeline",
            descricao="x",
            autor=self.vereador,
            status="AGUARDANDO_PROTOCOLO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            cluster=self.cluster,
            embedding=self.vetor,
        )
        self.seguidora = Demanda.objects.create(
            titulo="Seguidora timeline",
            descricao="x",
            autor=self.vereador,
            status="AGUARDANDO_PROTOCOLO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            cluster=self.cluster,
            embedding=self.vetor,
        )

    def test_timeline_seguidora_um_despacho_inicial_apos_super_os_hjul06(self):
        from core.services.cluster_despacho_service import ClusterDespachoService
        from core.services.operacional_estado_service import OperacionalEstadoService

        ClusterDespachoService().despachar_super_os(
            self.cluster,
            secretaria_id=SINAPSE_ORGAO_A,
            usuario=self.protocolo,
        )
        svc = OperacionalEstadoService()
        tl_lider = svc.montar_timeline_operacional(self.lider, usuario=self.protocolo)
        tl_seg = svc.montar_timeline_operacional(self.seguidora, usuario=self.protocolo)
        despachos_lider = [t for t in tl_lider if t["tipo"] == "DESPACHO"]
        despachos_seg = [t for t in tl_seg if t["tipo"] == "DESPACHO"]
        self.assertEqual(len(despachos_lider), 1)
        self.assertEqual(len(despachos_seg), 1)
        self.assertEqual(despachos_lider[0]["id"], despachos_seg[0]["id"])


class DataEntradaEtapaSignalTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.vereador = Usuario.objects.create_user(
            username="ver_etapa", password="x", perfil="VEREADOR"
        )

    def test_atualiza_data_entrada_etapa_ao_mudar_status(self):
        d = Demanda.objects.create(
            titulo="Fluxo",
            descricao="x",
            autor=self.vereador,
            status="AGUARDANDO_PROTOCOLO",
        )
        primeira = d.data_entrada_etapa
        d.status = "PROTOCOLADO"
        d.save(update_fields=["status"])
        d.refresh_from_db()
        self.assertIsNotNone(d.data_entrada_etapa)
        if primeira:
            self.assertGreaterEqual(d.data_entrada_etapa, primeira)
