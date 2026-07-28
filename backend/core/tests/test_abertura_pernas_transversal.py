"""Abertura de pernas transversais pela secretaria líder (C1/C2)."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Demanda, Tramitacao
from core.models_operacional import FluxoRoteamento, OrquestradorConclusao
from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional
from core.services.operacional_estado_service import (
    OperacionalEstadoService,
    OperacionalPermissaoError,
)
from core.services.perna_operacional_service import PernaOperacionalService

User = get_user_model()

SINAPSE_ORGAO_A = 9001
SINAPSE_ORGAO_B = 9002
SINAPSE_ORGAO_C = 9003


class AberturaPernasTransversalTests(TestCase):
    def setUp(self):
        self.svc = OperacionalEstadoService()
        self.perna_svc = PernaOperacionalService()
        self.vereador = User.objects.create_user(
            username="vereador_abertura",
            password="x",
            perfil="VEREADOR",
        )
        self.sec_a = User.objects.create_user(
            username="sec_a_abertura",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        self.sec_b = User.objects.create_user(
            username="sec_b_abertura",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_B,
        )

    def _demanda_em_execucao(self, **kwargs):
        defaults = dict(
            titulo="Teste abertura pernas",
            descricao="x",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            sinapse_orgao_lider_id=SINAPSE_ORGAO_A,
            fluxo_roteamento=FluxoRoteamento.FLUXO_TRANSVERSAL,
            orquestrador_conclusao=OrquestradorConclusao.SECRETARIA_LIDER,
        )
        defaults.update(kwargs)
        return Demanda.objects.create(**defaults)

    def test_secretaria_lider_abre_perna_integrada(self):
        demanda = self._demanda_em_execucao()
        self.perna_svc.criar_pernas_no_despacho(
            demanda,
            [{"secretaria_id": SINAPSE_ORGAO_A}],
        )
        PernaOperacional.objects.filter(demanda=demanda).update(
            status=StatusPernaOperacional.EM_EXECUCAO
        )

        resultado = self.svc.aplicar_abertura_pernas_transversal(
            demanda,
            self.sec_a,
            destinos_raw={
                "destinos": [
                    {"secretaria_id": SINAPSE_ORGAO_A},
                    {"secretaria_id": SINAPSE_ORGAO_B},
                ]
            },
            observacao="Encaminhar à secretaria integrada.",
        )

        pernas = PernaOperacional.objects.filter(demanda=demanda).order_by("ordem")
        self.assertEqual(pernas.count(), 2)
        self.assertEqual(int(pernas.last().sinapse_orgao_id), SINAPSE_ORGAO_B)
        self.assertEqual(resultado["total_pernas"], 2)
        self.assertTrue(
            Tramitacao.objects.filter(
                demanda=demanda, tipo="EXECUCAO"
            ).exists()
        )

    def test_secretaria_integrada_pode_abrir_sub_pernas(self):
        demanda = self._demanda_em_execucao()
        self.perna_svc.criar_pernas_no_despacho(
            demanda,
            [
                {"secretaria_id": SINAPSE_ORGAO_A},
                {"secretaria_id": SINAPSE_ORGAO_B},
            ],
        )
        PernaOperacional.objects.filter(demanda=demanda).update(
            status=StatusPernaOperacional.EM_EXECUCAO
        )

        resultado = self.svc.aplicar_abertura_pernas_transversal(
            demanda,
            self.sec_b,
            destinos_raw={"destinos": [{"secretaria_id": SINAPSE_ORGAO_C}]},
            observacao="SEMAE abre SEC OBRAS.",
        )

        self.assertEqual(resultado["pernas_novas"], 1)
        perna_c = PernaOperacional.objects.get(demanda=demanda, sinapse_orgao_id=SINAPSE_ORGAO_C)
        self.assertEqual(
            int((perna_c.metadata or {}).get("orgao_lider_imediato_id")),
            SINAPSE_ORGAO_B,
        )

    def test_secretaria_sem_perna_nao_pode_abrir_pernas(self):
        demanda = self._demanda_em_execucao()
        with self.assertRaises(OperacionalPermissaoError):
            self.svc.aplicar_abertura_pernas_transversal(
                demanda,
                self.sec_b,
                destinos_raw={"destinos": [{"secretaria_id": SINAPSE_ORGAO_C}]},
            )

    def test_lider_conclui_parcial_propria_com_integradas_abertas(self):
        """C1: líder conclui setor próprio sem esperar secretarias integradas."""
        PARECER = "Serviço concluído no setor da secretaria responsável."
        demanda = self._demanda_em_execucao()
        self.perna_svc.criar_pernas_no_despacho(
            demanda,
            [{"secretaria_id": SINAPSE_ORGAO_A}],
        )
        PernaOperacional.objects.filter(demanda=demanda).update(
            status=StatusPernaOperacional.EM_EXECUCAO
        )
        self.svc.aplicar_abertura_pernas_transversal(
            demanda,
            self.sec_a,
            destinos_raw={
                "destinos": [
                    {"secretaria_id": SINAPSE_ORGAO_B},
                ]
            },
            observacao="Integrar mobilidade.",
        )
        perna_lider = PernaOperacional.objects.get(
            demanda=demanda, sinapse_orgao_id=SINAPSE_ORGAO_A
        )

        resultado = self.svc.aplicar_conclusao_parcial(
            demanda, self.sec_a, parecer=PARECER, perna_id=perna_lider.pk
        )

        demanda.refresh_from_db()
        perna_lider.refresh_from_db()
        self.assertEqual(perna_lider.status, StatusPernaOperacional.CONCLUIDA)
        self.assertEqual(demanda.status, "EM_EXECUCAO")
        self.assertFalse(resultado["processo_avancou"])
        self.assertEqual(len(resultado["pendencias_parciais"]), 1)
        self.assertEqual(
            int(resultado["pendencias_parciais"][0]["sinapse_orgao_id"]),
            SINAPSE_ORGAO_B,
        )

    def test_lider_ultima_conclusao_parcial_consolida_processo(self):
        """C1: quando a líder é a última, consolida para conclusão final do Protocolo."""
        PARECER = "Conclusão final da secretaria responsável."
        demanda = self._demanda_em_execucao()
        perna_lider = PernaOperacional.objects.create(
            demanda=demanda,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            ordem=1,
            status=StatusPernaOperacional.EM_EXECUCAO,
        )
        PernaOperacional.objects.create(
            demanda=demanda,
            sinapse_orgao_id=SINAPSE_ORGAO_B,
            ordem=2,
            status=StatusPernaOperacional.CONCLUIDA,
        )
        self.svc.aplicar_conclusao_parcial(
            demanda, self.sec_a, parecer=PARECER, perna_id=perna_lider.pk
        )
        demanda.refresh_from_db()
        self.assertEqual(demanda.status, "AGUARDANDO_DEVOLUTIVA_PROTOCOLO")
        self.assertTrue(
            demanda.tramitacoes.filter(
                tipo="CONCLUSAO_TECNICA",
                metadata__consolidacao_transversal=True,
            ).exists()
        )

    def test_resolver_fluxo_cluster_super_os_com_um_destino(self):
        demanda = Demanda.objects.create(
            titulo="Cluster",
            descricao="x",
            autor=self.vereador,
            status="AGUARDANDO_PROTOCOLO",
            cluster_id=99999,
        )
        from unittest.mock import patch

        with patch.object(
            OperacionalEstadoService,
            "resolver_modo_entrada_processo",
            return_value="CLUSTER_SUPER_OS",
        ):
            fluxo = self.svc.resolver_fluxo_roteamento(
                total_destinos=1, demanda=demanda
            )
        self.assertEqual(fluxo, FluxoRoteamento.FLUXO_TRANSVERSAL)
