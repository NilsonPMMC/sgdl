"""Testes — aderência de demanda seguidora ao processo líder do cluster."""

import importlib.util

from django.test import TestCase

from core.models import ClusterExecucao, Demanda, Tramitacao
from core.models_no_operacional import NoOperacional, StatusNoOperacional
from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional
from core.services.cluster_aderencia_service import ClusterAderenciaService
from core.services.cluster_service import ClusterService
from core.services.demanda_despacho_service import DemandaDespachoService

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_ORGAO_B = _legacy.SINAPSE_ORGAO_B
SINAPSE_SERVICO_ID = _legacy.SINAPSE_SERVICO_ID
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class ClusterAderenciaServiceTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        from core.models import Usuario

        self.svc = ClusterAderenciaService()
        self.protocolo = Usuario.objects.create_user(
            username="prot_ader", password="x", perfil="PROTOCOLO"
        )
        self.ver_a = Usuario.objects.create_user(
            username="ver_a", password="x", perfil="VEREADOR"
        )
        self.ver_b = Usuario.objects.create_user(
            username="ver_b", password="x", perfil="VEREADOR"
        )
        self.cluster = ClusterExecucao.objects.create(
            titulo="Cluster aderência",
            status="EM_ANDAMENTO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
        )
        self.lider = Demanda.objects.create(
            titulo="Líder",
            descricao="x",
            autor=self.ver_a,
            status="AGUARDANDO_PROTOCOLO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            protocolo_legislativo="OFICIO-A-001",
            cluster=self.cluster,
            embedding=[0.1] * 1024,
        )
        self.seguidora = Demanda.objects.create(
            titulo="Seguidora",
            descricao="x",
            autor=self.ver_b,
            status="AGUARDANDO_PROTOCOLO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            protocolo_legislativo="OFICIO-B-001",
            cluster=self.cluster,
            embedding=[0.1] * 1024,
        )
        Tramitacao.objects.create(
            demanda=self.lider,
            responsavel=self.ver_a,
            tipo="ENVIO_OFICIAL",
            descricao="Envio líder",
        )
        Tramitacao.objects.create(
            demanda=self.seguidora,
            responsavel=self.ver_b,
            tipo="ENVIO_OFICIAL",
            descricao="Envio seguidora",
        )

    def test_situacao_exibe_decisao_quando_lider_despachado(self):
        DemandaDespachoService().despachar_multiplo(
            self.lider,
            [
                {"secretaria_id": SINAPSE_ORGAO_A},
                {"secretaria_id": SINAPSE_ORGAO_B},
            ],
            usuario=self.protocolo,
            texto_despacho="Despacho inicial do processo líder para secretarias.",
        )
        self.lider.refresh_from_db()
        self.assertEqual(self.lider.status, "EM_EXECUCAO")

        sit = self.svc.situacao_aderencia(self.seguidora)
        self.assertTrue(sit["exibir_decisao"])
        self.assertTrue(sit["aderir_lider"])
        self.assertTrue(sit["desvincular_despacho"])
        self.assertEqual(sit["lider"]["id"], self.lider.pk)

    def test_aderir_espelha_protocolo_executivo_e_tramitacoes(self):
        DemandaDespachoService().despachar_multiplo(
            self.lider,
            [{"secretaria_id": SINAPSE_ORGAO_A}, {"secretaria_id": SINAPSE_ORGAO_B}],
            usuario=self.protocolo,
            texto_despacho="Despacho líder com duas secretarias integradas.",
        )
        self.lider.refresh_from_db()
        exec_lider = self.lider.protocolo_executivo

        resultado = self.svc.aderir_ao_processo_lider(self.seguidora, usuario=self.protocolo)
        self.seguidora.refresh_from_db()

        self.assertEqual(resultado.pk, self.seguidora.pk)
        self.assertEqual(self.seguidora.status, self.lider.status)
        self.assertIsNone(self.seguidora.protocolo_executivo)
        from core.services.cluster_aderencia_service import protocolo_executivo_efetivo

        self.assertEqual(protocolo_executivo_efetivo(self.seguidora), exec_lider)
        self.assertEqual(
            self.seguidora.tramitacoes.filter(tipo="ENVIO_OFICIAL").count(),
            1,
        )
        self.assertTrue(
            self.seguidora.tramitacoes.filter(tipo="DESPACHO").exists()
        )
        self.assertEqual(
            self.lider.tramitacoes.exclude(tipo="ENVIO_OFICIAL").count(),
            self.seguidora.tramitacoes.exclude(tipo="ENVIO_OFICIAL").count() - 1,
        )
        self.assertEqual(
            PernaOperacional.objects.filter(demanda=self.seguidora).count(),
            PernaOperacional.objects.filter(demanda=self.lider).count(),
        )

    def test_aderir_espelha_nos_operacionais(self):
        DemandaDespachoService().despachar_multiplo(
            self.lider,
            [{"secretaria_id": SINAPSE_ORGAO_A}],
            usuario=self.protocolo,
            texto_despacho="Despacho líder para bootstrap de nós operacionais.",
        )
        self.lider.refresh_from_db()
        self.assertGreater(NoOperacional.objects.filter(demanda=self.lider).count(), 0)

        self.svc.aderir_ao_processo_lider(self.seguidora, usuario=self.protocolo)
        self.seguidora.refresh_from_db()

        nos_lider = NoOperacional.objects.filter(demanda=self.lider).count()
        nos_seg = NoOperacional.objects.filter(demanda=self.seguidora).count()
        self.assertEqual(nos_lider, nos_seg)
        self.assertEqual(self.seguidora.nos_ativos, self.lider.nos_ativos)

    def test_seguidora_ressincroniza_quando_lider_avanca_devolutiva(self):
        from core.models_operacional import ESTADO_AGUARDANDO_CONCLUSAO_FINAL

        DemandaDespachoService().despachar_multiplo(
            self.lider,
            [{"secretaria_id": SINAPSE_ORGAO_A}],
            usuario=self.protocolo,
            texto_despacho="Despacho líder para operação scatter-gather.",
        )
        self.lider.refresh_from_db()
        self.svc.aderir_ao_processo_lider(self.seguidora, usuario=self.protocolo)
        self.seguidora.refresh_from_db()
        self.assertEqual(self.seguidora.status, "EM_EXECUCAO")

        self.lider.status = ESTADO_AGUARDANDO_CONCLUSAO_FINAL
        self.lider.nos_ativos = 0
        self.lider.save(update_fields=["status", "nos_ativos"])

        self.svc.ressincronizar_com_lider(self.seguidora, lider=self.lider)
        self.seguidora.refresh_from_db()
        self.assertEqual(self.seguidora.status, ESTADO_AGUARDANDO_CONCLUSAO_FINAL)
        self.assertEqual(self.seguidora.nos_ativos, 0)
