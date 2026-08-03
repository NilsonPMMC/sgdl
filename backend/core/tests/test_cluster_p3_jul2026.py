"""P3 homologação jul/2026 — H-JUL-15 … H-JUL-18."""

import importlib.util

from django.test import TestCase

from core.models import ClusterExecucao, Demanda, Notificacao, Tramitacao
from core.models_assinatura_eletronica import AssinaturaEletronica
from core.services.assinatura_eletronica_service import AssinaturaEletronicaService
from core.services.cluster_service import ClusterService
from core.services.notificacao_service import NotificacaoService

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_SERVICO_ID = _legacy.SINAPSE_SERVICO_ID
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class ClusterMetadataP3Tests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        from core.models import Usuario

        self.svc = ClusterService()
        self.ver_a = Usuario.objects.create_user(
            username="ver_p3_a", password="x", perfil="VEREADOR"
        )
        self.ver_b = Usuario.objects.create_user(
            username="ver_p3_b", password="x", perfil="VEREADOR"
        )
        self.cluster = ClusterExecucao.objects.create(
            titulo="Cluster P3",
            status="EM_ANDAMENTO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            descricao_resumo="<p>HTML da forma&ccedil;&atilde;o</p>",
            bairro_referencia="Bairro Formacao",
        )
        self.primeira = Demanda.objects.create(
            titulo="Primeira",
            descricao="<p>desc antiga</p>",
            autor=self.ver_a,
            status="EM_EXECUCAO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            bairro="Bairro Formacao",
            protocolo_legislativo="OF-1",
            cluster=self.cluster,
        )
        self.lider = Demanda.objects.create(
            titulo="Lider protocolada",
            descricao="<p>Descricao <strong>lider</strong> &ndash; ok</p>",
            autor=self.ver_b,
            status="EM_EXECUCAO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            bairro="Centro Historico",
            protocolo_legislativo="OF-2",
            protocolo_executivo="2026-0099",
            fluxo_roteamento="FLUXO_TRANSVERSAL",
            nos_ativos=2,
            cluster=self.cluster,
        )

    def test_metadata_cluster_usa_lider_e_remove_html_hjul15_16(self):
        meta = self.svc.metadata_cluster(self.cluster)
        self.assertEqual(meta["lider_demanda_id"], self.lider.pk)
        self.assertNotIn("<p>", meta["descricao_resumo"])
        self.assertIn("lider", meta["descricao_resumo"].lower())
        self.assertEqual(meta["bairro_referencia"], "Centro Historico")

    def test_criar_cluster_strip_html_hjul15(self):
        demanda = Demanda.objects.create(
            titulo="Nova",
            descricao="<p>Buraco &nbsp; na via</p>",
            autor=self.ver_a,
            status="AGUARDANDO_PROTOCOLO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
        )
        cluster = self.svc._criar_cluster(demanda, [0.1, 0.2])
        self.assertNotIn("<", cluster.descricao_resumo)
        self.assertIn("Buraco", cluster.descricao_resumo)


class ResumoAssinaturaSeguidoraP3Tests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        from core.models import Usuario

        self.svc = AssinaturaEletronicaService()
        self.ver_a = Usuario.objects.create_user(
            username="ver_p3_sig_a", password="x", perfil="VEREADOR"
        )
        self.ver_b = Usuario.objects.create_user(
            username="ver_p3_sig_b", password="x", perfil="VEREADOR"
        )
        self.cluster = ClusterExecucao.objects.create(
            titulo="Cluster assinatura",
            status="EM_ANDAMENTO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
        )
        self.lider = Demanda.objects.create(
            titulo="Lider",
            descricao="x",
            autor=self.ver_b,
            status="EM_EXECUCAO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            protocolo_executivo="2026-0100",
            fluxo_roteamento="FLUXO_TRANSVERSAL",
            nos_ativos=1,
            cluster=self.cluster,
        )
        self.seguidora = Demanda.objects.create(
            titulo="Seguidora",
            descricao="x",
            autor=self.ver_a,
            status="EM_EXECUCAO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            protocolo_legislativo="OF-S",
            cluster=self.cluster,
        )
        Tramitacao.objects.create(
            demanda=self.seguidora,
            responsavel=self.ver_a,
            tipo="COMENTARIO",
            descricao="Integrada",
            metadata={"acao": "ADERIR_LIDER", "lider_demanda_id": self.lider.pk},
        )
        AssinaturaEletronica.objects.create(
            demanda=self.lider,
            usuario=self.ver_b,
            etapa=AssinaturaEletronica.ETAPA_DESPACHO_DEVOLUTIVA,
            papel=AssinaturaEletronica.PAPEL_OPERADOR,
            hash_documento="a" * 64,
            declaracao="ASSINO",
        )
        AssinaturaEletronica.objects.create(
            demanda=self.lider,
            usuario=self.ver_b,
            etapa=AssinaturaEletronica.ETAPA_DESPACHO_DEVOLUTIVA,
            papel=AssinaturaEletronica.PAPEL_GESTOR_PROTOCOLO,
            hash_documento="b" * 64,
            declaracao="VALIDO",
        )
        AssinaturaEletronica.objects.create(
            demanda=self.seguidora,
            usuario=self.ver_a,
            etapa=AssinaturaEletronica.ETAPA_ENVIO_OFICIO,
            papel=AssinaturaEletronica.PAPEL_OPERADOR,
            hash_documento="c" * 64,
            declaracao="ASSINO",
        )

    def test_resumo_seguidora_espelha_lider_hjul17(self):
        resumo_lider = self.svc.resumo_assinaturas_demanda(self.lider)
        resumo_seg = self.svc.resumo_assinaturas_demanda(self.seguidora)
        self.assertTrue(resumo_lider["devolutiva_assinada"])
        self.assertTrue(resumo_seg["devolutiva_assinada"])
        self.assertFalse(resumo_seg["envio_oficio_assinado"])


class NotificacaoConclusaoSuperOsP3Tests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        from core.models import Usuario

        self.ver_a = Usuario.objects.create_user(
            username="ver_p3_not_a", password="x", perfil="VEREADOR"
        )
        self.ver_b = Usuario.objects.create_user(
            username="ver_p3_not_b", password="x", perfil="VEREADOR"
        )
        self.cluster = ClusterExecucao.objects.create(
            status="EM_ANDAMENTO",
            protocolo_super_os="SUPER-2026-0011",
        )
        self.lider = Demanda.objects.create(
            titulo="Lider Super OS",
            descricao="x",
            autor=self.ver_a,
            status="EM_EXECUCAO",
            cluster=self.cluster,
            protocolo_legislativo="OF-L",
            protocolo_executivo="2026-0111",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        self.seguidora = Demanda.objects.create(
            titulo="Seguidora Super OS",
            descricao="x",
            autor=self.ver_b,
            status="EM_EXECUCAO",
            cluster=self.cluster,
            protocolo_legislativo="OF-S",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )

    def test_conclusao_super_os_uma_notificacao_por_vereador_hjul18(self):
        Notificacao.objects.all().delete()
        self.lider.status = "FINALIZADO"
        with self.captureOnCommitCallbacks(execute=True):
            self.lider.save(update_fields=["status"])

        self.assertEqual(
            Notificacao.objects.filter(destinatario=self.ver_a, tipo="CONCLUSAO").count(),
            1,
        )
        self.assertEqual(
            Notificacao.objects.filter(destinatario=self.ver_b, tipo="CONCLUSAO").count(),
            1,
        )
        msg = Notificacao.objects.filter(destinatario=self.ver_a, tipo="CONCLUSAO").first()
        self.assertIn("SUPER-2026-0011", msg.mensagem)

    def test_notificar_conclusao_seguidora_super_os_nao_dispara_hjul18(self):
        Notificacao.objects.all().delete()
        criadas = NotificacaoService().notificar_conclusao_final(self.seguidora)
        self.assertEqual(criadas, 0)
