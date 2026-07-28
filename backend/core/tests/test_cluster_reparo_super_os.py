"""Testes do reparo operacional de Super OS."""

import importlib.util

from django.test import TestCase

from core.models import ClusterExecucao, Demanda, Tramitacao
from core.models_no_operacional import NoOperacional, StatusNoOperacional
from core.services.cluster_aderencia_service import demanda_integrada_ao_lider
from core.services.cluster_reparo_service import (
    clusters_candidatos_reparo,
    diagnosticar_cluster,
    reparar_cluster_super_os,
)
from core.services.cluster_service import ClusterService
from core.services.demanda_despacho_service import DemandaDespachoService

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_ORGAO_B = _legacy.SINAPSE_ORGAO_B
SINAPSE_SERVICO_ID = _legacy.SINAPSE_SERVICO_ID
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class ClusterReparoSuperOsTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        from core.models import Usuario

        self.protocolo = Usuario.objects.create_user(
            username="prot_reparo", password="x", perfil="PROTOCOLO"
        )
        self.ver_a = Usuario.objects.create_user(
            username="ver_reparo_a", password="x", perfil="VEREADOR"
        )
        self.ver_b = Usuario.objects.create_user(
            username="ver_reparo_b", password="x", perfil="VEREADOR"
        )
        self.cluster = ClusterExecucao.objects.create(
            titulo="Cluster reparo",
            status="EM_ANDAMENTO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
        )
        self.primeira = Demanda.objects.create(
            titulo="Primeira",
            descricao="x",
            autor=self.ver_a,
            status="EM_EXECUCAO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            protocolo_legislativo="OF-R-1",
            cluster=self.cluster,
        )
        self.protocolada = Demanda.objects.create(
            titulo="Protocolada",
            descricao="x",
            autor=self.ver_b,
            status="AGUARDANDO_PROTOCOLO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            protocolo_legislativo="OF-R-2",
            cluster=self.cluster,
        )
        for d in (self.primeira, self.protocolada):
            Tramitacao.objects.create(
                demanda=d,
                responsavel=d.autor,
                tipo="ENVIO_OFICIAL",
                descricao="Envio",
            )
        self.protocolada.protocolo_executivo = "2026-REPARO-TEST"
        self.protocolada.status = "EM_EXECUCAO"
        self.protocolada.fluxo_roteamento = "FLUXO_TRANSVERSAL"
        self.protocolada.save(
            update_fields=["protocolo_executivo", "status", "fluxo_roteamento"]
        )

    def test_diagnostico_detecta_seguidora_orfa(self):
        diag = diagnosticar_cluster(int(self.cluster.pk))
        self.assertTrue(diag["reparavel"])
        self.assertEqual(diag["lider_operacional_id"], self.protocolada.pk)
        self.assertIn(self.primeira.pk, diag["seguidoras_pendentes"])

    def test_diagnostico_protocolo_fora_primeira_com_nos_scatter(self):
        """Cenário Super OS: protocolo na 2ª demanda, nós na protocolada."""
        NoOperacional.objects.create(
            demanda=self.protocolada,
            sinapse_orgao_id=SINAPSE_ORGAO_B,
            status=StatusNoOperacional.ABERTO,
        )
        self.protocolada.nos_ativos = 1
        self.protocolada.save(update_fields=["nos_ativos"])
        diag = diagnosticar_cluster(int(self.cluster.pk))
        self.assertTrue(diag["reparavel"])
        self.assertTrue(diag["protocolo_fora_primeira"])
        self.assertTrue(diag["nos_fora_lider_legado"])
        self.assertEqual(diag["lider_operacional_id"], self.protocolada.pk)

    def test_despacho_segunda_demanda_integra_primeira_em_execucao(self):
        """Despacho na 2ª demanda integra a 1ª mesmo se já estiver EM_EXECUCAO."""
        from core.services.cluster_aderencia_service import integrar_cluster_apos_protocolo
        from core.services.demanda_despacho_service import DemandaDespachoService

        self.primeira.status = "EM_EXECUCAO"
        self.primeira.save(update_fields=["status"])
        self.protocolada.status = "AGUARDANDO_PROTOCOLO"
        self.protocolada.save(update_fields=["status"])

        DemandaDespachoService().despachar_multiplo(
            self.protocolada,
            [{"secretaria_id": SINAPSE_ORGAO_A}],
            usuario=self.protocolo,
            texto_despacho="Despacho inicial para integração de cluster em teste.",
        )
        self.protocolada.refresh_from_db()
        integradas = integrar_cluster_apos_protocolo(self.protocolada, usuario=self.protocolo)
        self.assertIn(self.primeira.pk, integradas)
        self.primeira.refresh_from_db()
        self.assertTrue(demanda_integrada_ao_lider(self.primeira))
        self.assertEqual(self.primeira.fluxo_roteamento, self.protocolada.fluxo_roteamento)
        estado = __import__(
            "core.services.operacional_estado_service", fromlist=["OperacionalEstadoService"]
        ).OperacionalEstadoService().montar_estado_operacional(
            self.primeira, self.ver_a
        )
        self.assertGreater(len(estado.get("timeline") or []), 0)

    def test_reparo_integra_seguidora_ao_lider_protocolado(self):
        DemandaDespachoService().despachar_multiplo(
            self.protocolada,
            [
                {"secretaria_id": SINAPSE_ORGAO_A},
                {"secretaria_id": SINAPSE_ORGAO_B},
            ],
            usuario=self.protocolo,
        )
        self.protocolada.refresh_from_db()
        self.protocolada.status = "EM_EXECUCAO"
        self.protocolada.inicio_execucao_automatico = True
        self.protocolada.save(
            update_fields=["status", "inicio_execucao_automatico"]
        )
        no = NoOperacional.objects.create(
            demanda=self.protocolada,
            sinapse_orgao_id=SINAPSE_ORGAO_B,
            status=StatusNoOperacional.ABERTO,
        )
        tram = Tramitacao.objects.create(
            demanda=self.protocolada,
            responsavel=self.protocolo,
            tipo="OPERACAO_NO",
            descricao="Abertura nó",
            metadata={
                "scatter_gather": True,
                "no_id": no.pk,
                "orgao_id": SINAPSE_ORGAO_B,
            },
        )
        no.abertura_tramitacao = tram
        no.save(update_fields=["abertura_tramitacao"])

        resultado = reparar_cluster_super_os(
            int(self.cluster.pk), usuario=self.protocolo
        )
        self.assertIn(self.primeira.pk, resultado["integradas"])
        self.primeira.refresh_from_db()
        self.assertTrue(demanda_integrada_ao_lider(self.primeira))
        self.assertEqual(
            ClusterService().lider_cluster_pk(int(self.cluster.pk)),
            self.protocolada.pk,
        )
        self.assertNotIn(int(self.cluster.pk), clusters_candidatos_reparo())
