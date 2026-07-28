"""Notificações operacionais — matriz por perfil."""

import importlib.util

from django.test import TestCase

from core.models import Demanda, Notificacao
from core.models_no_operacional import AcaoNoOperacional
from core.models_operacional import FluxoRoteamento
from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional
from core.models_unidade_administrativa import (
    UnidadeAdministrativa,
    UnidadeAdministrativaResponsavel,
)
from core.services.notificacao_service import NotificacaoService
from core.services.perna_operacional_service import PernaOperacionalService
from core.services.scatter_gather_service import NoOperacionalService

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_ORGAO_B = _legacy.SINAPSE_ORGAO_B
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class NotificacaoServiceTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        from core.models import ClusterExecucao, Usuario

        self.svc = NotificacaoService()
        self.ver_a = Usuario.objects.create_user(
            username="ver_not_a", password="x", perfil="VEREADOR"
        )
        self.ver_b = Usuario.objects.create_user(
            username="ver_not_b", password="x", perfil="VEREADOR"
        )
        self.protocolo = Usuario.objects.create_user(
            username="prot_not", password="x", perfil="PROTOCOLO"
        )
        self.gestor_geral = Usuario.objects.create_user(
            username="gest_geral_not", password="x", perfil="GESTOR"
        )
        self.gestor_setorial = Usuario.objects.create_user(
            username="gest_set_not",
            password="x",
            perfil="GESTOR",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        self.sec_a = Usuario.objects.create_user(
            username="sec_not_a",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        self.ua_a = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            nome="Setor A",
            sigla="STA",
            ativo=True,
        )
        UnidadeAdministrativaResponsavel.objects.create(
            unidade=self.ua_a,
            usuario=self.sec_a,
            ativo=True,
            pode_tramitar=True,
        )
        self.cluster = ClusterExecucao.objects.create(status="ABERTO")
        self.demanda_a = Demanda.objects.create(
            titulo="Demanda A",
            descricao="x",
            autor=self.ver_a,
            status="AGUARDANDO_PROTOCOLO",
            cluster=self.cluster,
            protocolo_legislativo="OF-A",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            unidade_administrativa=self.ua_a,
        )
        self.demanda_b = Demanda.objects.create(
            titulo="Demanda B",
            descricao="x",
            autor=self.ver_b,
            status="AGUARDANDO_PROTOCOLO",
            cluster=self.cluster,
            protocolo_legislativo="OF-B",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )

    def test_vereadores_interessados_cluster(self):
        vereadores = self.svc.vereadores_interessados(self.demanda_a)
        ids = {u.pk for u in vereadores}
        self.assertIn(self.ver_a.pk, ids)
        self.assertIn(self.ver_b.pk, ids)

    def test_notificar_despacho_inicial_super_os(self):
        self.cluster.protocolo_super_os = "SUPER-2026-0001"
        total = self.svc.notificar_despacho_inicial_super_os(
            self.cluster,
            [self.demanda_a, self.demanda_b],
            orgao_nome="Secretaria Teste",
        )
        self.assertEqual(total, 2)
        self.assertTrue(
            Notificacao.objects.filter(destinatario=self.ver_a, tipo="DESPACHO").exists()
        )

    def test_notificar_conclusao_final_apenas_vereador(self):
        self.demanda_a.status = "FINALIZADO"
        self.demanda_a.protocolo_executivo = "2026-0099"
        self.svc.notificar_conclusao_final(self.demanda_a)
        self.assertTrue(
            Notificacao.objects.filter(destinatario=self.ver_a, tipo="CONCLUSAO").exists()
        )
        self.assertTrue(
            Notificacao.objects.filter(destinatario=self.ver_b, tipo="CONCLUSAO").exists()
        )
        self.assertFalse(
            Notificacao.objects.filter(destinatario=self.protocolo, tipo="CONCLUSAO").exists()
        )

    def test_notificar_despacho_inicial_setores_respeita_vinculo(self):
        self.svc.notificar_despacho_inicial_setores(self.demanda_a)
        self.assertTrue(
            Notificacao.objects.filter(destinatario=self.sec_a, tipo="DESPACHO").exists()
        )

    def test_notificar_cluster_detectado_protocolo(self):
        self.svc.notificar_cluster_detectado(self.cluster, self.demanda_a)
        self.assertTrue(
            Notificacao.objects.filter(destinatario=self.protocolo, tipo="CLUSTER").exists()
        )

    def test_notificar_sla_atraso_matriz_perfis(self):
        self.demanda_a.status = "EM_EXECUCAO"
        self.demanda_a.save(update_fields=["status"])
        self.svc.notificar_sla_atraso(self.demanda_a)
        self.assertTrue(
            Notificacao.objects.filter(destinatario=self.protocolo, tipo="ATRASO").exists()
        )
        self.assertTrue(
            Notificacao.objects.filter(destinatario=self.sec_a, tipo="ATRASO").exists()
        )
        self.assertTrue(
            Notificacao.objects.filter(destinatario=self.gestor_geral, tipo="ATRASO").exists()
        )


class NotificacaoEncerramentoScatterTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        from core.models import Usuario

        self.sg = NoOperacionalService()
        self.perna_svc = PernaOperacionalService()
        self.vereador = Usuario.objects.create_user(
            username="ver_sg_not", password="x", perfil="VEREADOR"
        )
        self.protocolo = Usuario.objects.create_user(
            username="prot_sg_not", password="x", perfil="PROTOCOLO"
        )
        self.sec_a = Usuario.objects.create_user(
            username="sec_sg_not",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        self.gestor = Usuario.objects.create_user(
            username="gest_sg_not",
            password="x",
            perfil="GESTOR",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        self.ua = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            nome="Setor scatter",
            sigla="SSC",
            ativo=True,
        )
        UnidadeAdministrativaResponsavel.objects.create(
            unidade=self.ua,
            usuario=self.sec_a,
            ativo=True,
            pode_tramitar=True,
        )
        self.demanda = Demanda.objects.create(
            titulo="Scatter notificação",
            descricao="x",
            autor=self.vereador,
            status="EM_EXECUCAO",
            protocolo_executivo="2026-0100",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            sinapse_orgao_lider_id=SINAPSE_ORGAO_A,
            fluxo_roteamento=FluxoRoteamento.FLUXO_TRANSVERSAL,
            unidade_administrativa=self.ua,
        )
        self.perna_svc.criar_pernas_no_despacho(
            self.demanda,
            [{"secretaria_id": SINAPSE_ORGAO_A}],
        )
        PernaOperacional.objects.filter(demanda=self.demanda).update(
            status=StatusPernaOperacional.EM_EXECUCAO
        )
        nos = self.sg.bootstrap_nos_iniciais(self.demanda, self.sec_a)
        self.no_a = nos[0]

    def test_encerrar_no_notifica_secretaria_gestor_nao_vereador(self):
        antes_vereador = Notificacao.objects.filter(destinatario=self.vereador).count()
        antes_protocolo = Notificacao.objects.filter(destinatario=self.protocolo).count()
        self.sg.aplicar_encerrar(
            self.demanda,
            self.no_a.pk,
            self.sec_a,
            observacao="Encerramento operacional com notificação.",
            assinatura_ctx={
                "assinar": True,
                "declaracao": "ASSINO O ENCERRAMENTO OPERACIONAL",
                "acao": AcaoNoOperacional.ENCERRAR,
                "obrigatoria": True,
            },
        )
        depois_vereador = Notificacao.objects.filter(destinatario=self.vereador).count()
        self.assertEqual(depois_vereador, antes_vereador)
        self.assertTrue(
            Notificacao.objects.filter(destinatario=self.sec_a, tipo="ATUALIZACAO").exists()
        )
        # Único nó encerrado → gather notifica protocolo (testado também em test_gather_*)
        self.assertGreater(
            Notificacao.objects.filter(destinatario=self.protocolo).count(),
            antes_protocolo,
        )

    def test_gather_notifica_protocolo_todos_nos_encerrados(self):
        self.sg.aplicar_encerrar(
            self.demanda,
            self.no_a.pk,
            self.sec_a,
            observacao="Encerramento final do único nó operacional.",
            assinatura_ctx={
                "assinar": True,
                "declaracao": "ASSINO O ENCERRAMENTO OPERACIONAL",
                "acao": AcaoNoOperacional.ENCERRAR,
                "obrigatoria": True,
            },
        )
        self.assertTrue(
            Notificacao.objects.filter(
                destinatario=self.protocolo,
                tipo="ATUALIZACAO",
                mensagem__icontains="Todos os nós operacionais",
            ).exists()
        )
