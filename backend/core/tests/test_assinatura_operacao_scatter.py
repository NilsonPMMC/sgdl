"""Assinatura eletrônica em operações scatter-gather."""

import importlib.util

from django.test import TestCase

from core.models import Demanda, Tramitacao
from core.models_assinatura_eletronica import AssinaturaEletronica
from core.models_no_operacional import AcaoNoOperacional
from core.models_operacional import FluxoRoteamento
from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional
from core.services.assinatura_eletronica_service import (
    DECLARACAO_DESPACHO,
    DECLARACAO_ENCERRAMENTO_OPERACIONAL,
    AssinaturaEletronicaService,
)
from core.services.perna_operacional_service import PernaOperacionalService
from core.services.scatter_gather_service import NoOperacionalService

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_ORGAO_B = _legacy.SINAPSE_ORGAO_B
SINAPSE_ORGAO_C = 2003
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class AssinaturaOperacaoScatterTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.sg = NoOperacionalService()
        self.perna_svc = PernaOperacionalService()
        from core.models import Usuario

        self.vereador = Usuario.objects.create_user(
            username="ver_assin_sg", password="x", perfil="VEREADOR"
        )
        self.sec_a = Usuario.objects.create_user(
            username="sec_a_assin_sg",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        self.demanda = Demanda.objects.create(
            titulo="Scatter assinatura",
            descricao="x",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            sinapse_orgao_lider_id=SINAPSE_ORGAO_A,
            fluxo_roteamento=FluxoRoteamento.FLUXO_TRANSVERSAL,
        )
        self.perna_svc.criar_pernas_no_despacho(
            self.demanda,
            [
                {"secretaria_id": SINAPSE_ORGAO_A},
                {"secretaria_id": SINAPSE_ORGAO_B},
            ],
        )
        PernaOperacional.objects.filter(demanda=self.demanda).update(
            status=StatusPernaOperacional.EM_EXECUCAO
        )
        nos = self.sg.bootstrap_nos_iniciais(self.demanda, self.sec_a)
        self.no_a = next(n for n in nos if n.sinapse_orgao_id == SINAPSE_ORGAO_A)

    def test_despachar_opcional_registra_assinatura_quando_solicitada(self):
        ctx = {
            "assinar": True,
            "declaracao": DECLARACAO_DESPACHO,
            "acao": AcaoNoOperacional.DESPACHAR,
            "obrigatoria": False,
        }
        resultado = self.sg.aplicar_despachar(
            self.demanda,
            self.no_a.pk,
            self.sec_a,
            destino_orgao_id=SINAPSE_ORGAO_C,
            observacao="Despacho com assinatura eletrônica opcional.",
            assinatura_ctx=ctx,
        )
        tram_id = resultado["tramitacao_id"]
        assinatura = AssinaturaEletronica.objects.get(tramitacao_id=tram_id)
        self.assertEqual(assinatura.etapa, AssinaturaEletronica.ETAPA_OPERACAO_SCATTER)
        self.assertEqual(assinatura.declaracao, DECLARACAO_DESPACHO)
        self.assertEqual(assinatura.usuario_id, self.sec_a.pk)

    def test_despachar_sem_assinatura_nao_cria_registro(self):
        self.sg.aplicar_despachar(
            self.demanda,
            self.no_a.pk,
            self.sec_a,
            destino_orgao_id=SINAPSE_ORGAO_C,
            observacao="Despacho sem assinatura eletrônica.",
            assinatura_ctx={"assinar": False, "declaracao": "", "acao": "DESPACHAR"},
        )
        self.assertFalse(
            AssinaturaEletronica.objects.filter(
                demanda=self.demanda, etapa=AssinaturaEletronica.ETAPA_OPERACAO_SCATTER
            ).exists()
        )

    def test_encerrar_registra_assinatura_obrigatoria(self):
        ctx = {
            "assinar": True,
            "declaracao": DECLARACAO_ENCERRAMENTO_OPERACIONAL,
            "acao": AcaoNoOperacional.ENCERRAR,
            "obrigatoria": True,
        }
        resultado = self.sg.aplicar_encerrar(
            self.demanda,
            self.no_a.pk,
            self.sec_a,
            observacao="Encerramento com assinatura obrigatória.",
            assinatura_ctx=ctx,
        )
        assinatura = AssinaturaEletronica.objects.get(tramitacao_id=resultado["tramitacao_id"])
        self.assertEqual(assinatura.declaracao, DECLARACAO_ENCERRAMENTO_OPERACIONAL)
        self.no_a.refresh_from_db()
        self.assertEqual(self.no_a.status, "ABERTO")
        from core.models_assinatura_eletronica import AssinaturaValidacaoGestor

        self.assertTrue(
            AssinaturaValidacaoGestor.objects.filter(
                demanda=self.demanda,
                status=AssinaturaValidacaoGestor.STATUS_PENDENTE,
            ).exists()
        )
        resumo = AssinaturaEletronicaService().resumo_assinaturas_demanda(self.demanda)
        self.assertTrue(resumo["operacao_scatter_pendente_gestor"])
        self.assertFalse(resumo["operacao_scatter_assinada"])

    def test_validar_contexto_exige_assinatura_em_encerrar(self):
        svc = AssinaturaEletronicaService()
        ctx = svc.parse_assinatura_scatter_request({}, AcaoNoOperacional.ENCERRAR)
        ctx["assinar"] = False
        with self.assertRaises(ValueError):
            svc.validar_assinatura_scatter_contexto(ctx)

    def test_parse_assinatura_aceita_valores_multipart_como_lista(self):
        svc = AssinaturaEletronicaService()
        ctx = svc.parse_assinatura_scatter_request(
            {
                "assinar_eletronicamente": ["true"],
                "declaracao": ["ASSINO O DESPACHO"],
            },
            AcaoNoOperacional.DESPACHAR,
        )
        self.assertTrue(ctx["assinar"])
        self.assertEqual(ctx["declaracao"], "ASSINO O DESPACHO")

    def test_serializar_inclui_tramitacao_id(self):
        ctx = {
            "assinar": True,
            "declaracao": DECLARACAO_DESPACHO,
            "acao": AcaoNoOperacional.DESPACHAR,
            "obrigatoria": False,
        }
        self.sg.aplicar_despachar(
            self.demanda,
            self.no_a.pk,
            self.sec_a,
            destino_orgao_id=SINAPSE_ORGAO_B,
            observacao="Serialização scatter assinatura.",
            assinatura_ctx=ctx,
        )
        tram = Tramitacao.objects.filter(
            demanda=self.demanda,
            tipo="OPERACAO_NO",
            metadata__acao_no=AcaoNoOperacional.DESPACHAR,
        ).latest("pk")
        payload = AssinaturaEletronicaService().serializar_assinaturas_demanda(self.demanda)
        scatter = [a for a in payload if a.get("tramitacao_id") == tram.pk]
        self.assertEqual(len(scatter), 1)
        self.assertEqual(scatter[0]["etapa"], "OPERACAO_SCATTER")
