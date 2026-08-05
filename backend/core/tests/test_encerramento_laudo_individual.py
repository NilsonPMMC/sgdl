"""Laudo do pacote devolutiva — Super OS conclusão individual por ofício."""

import importlib.util

from django.test import TestCase

from core.models import ClusterExecucao, Demanda, Tramitacao, Usuario
from core.models_operacional import EventoOperacional, FluxoRoteamento
from core.services.encerramento_legislativo_service import EncerramentoLegislativoService

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_SERVICO_ID = _legacy.SINAPSE_SERVICO_ID


class EncerramentoLaudoIndividualTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.ver_a = Usuario.objects.create_user(
            username="ver_laudo_a", password="x", perfil="VEREADOR", first_name="Priscila"
        )
        self.ver_b = Usuario.objects.create_user(
            username="ver_laudo_b", password="x", perfil="VEREADOR", first_name="Eduardo"
        )
        self.protocolo = Usuario.objects.create_user(
            username="prot_laudo", password="x", perfil="PROTOCOLO"
        )
        self.cluster = ClusterExecucao.objects.create(
            titulo="Super OS laudo",
            status="EM_ANDAMENTO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            protocolo_super_os="SUPER-LAUDO",
        )
        self.lider = Demanda.objects.create(
            titulo="Limpeza",
            descricao="x",
            autor=self.ver_a,
            protocolo_legislativo="2026-0004",
            status="FINALIZADO",
            fluxo_roteamento=FluxoRoteamento.FLUXO_DIRETO,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            protocolo_executivo="2026-0200",
            cluster=self.cluster,
        )
        self.seguidora = Demanda.objects.create(
            titulo="Limpeza",
            descricao="x",
            autor=self.ver_b,
            protocolo_legislativo="2026-0003",
            status="FINALIZADO",
            fluxo_roteamento=FluxoRoteamento.FLUXO_DIRETO,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            cluster=self.cluster,
        )
        Tramitacao.objects.create(
            demanda=self.lider,
            responsavel=self.protocolo,
            tipo=EventoOperacional.CONCLUSAO_FINAL,
            descricao="Conclusão final do Protocolo.\nParecer:\nPrezado(a) Priscila, processo 2026-0004.",
            metadata={
                "parecer": "Prezado(a) Priscila, processo 2026-0004.",
                "modo_conclusao": "individual",
            },
        )
        Tramitacao.objects.create(
            demanda=self.seguidora,
            responsavel=self.protocolo,
            tipo=EventoOperacional.CONCLUSAO_FINAL,
            descricao="Conclusão final da Super OS (ofício nº 2026-0003).\nParecer:\nPrezado(a) Eduardo, processo 2026-0003.",
            metadata={
                "parecer": "Prezado(a) Eduardo, processo 2026-0003.",
                "super_os_conclusao_individual": True,
                "modo_conclusao": "individual",
            },
        )
        self.svc = EncerramentoLegislativoService()

    def test_laudo_final_usa_parecer_da_demanda_vinculada(self):
        pacote_lider = self.svc.montar_pacote_devolutiva(self.lider)
        pacote_seg = self.svc.montar_pacote_devolutiva(self.seguidora)

        self.assertIn("Priscila", pacote_lider["laudo_final"])
        self.assertIn("2026-0004", pacote_lider["laudo_final"])
        self.assertNotIn("Eduardo", pacote_lider["laudo_final"])

        self.assertIn("Eduardo", pacote_seg["laudo_final"])
        self.assertIn("2026-0003", pacote_seg["laudo_final"])
        self.assertNotIn("Priscila", pacote_seg["laudo_final"])
