"""Testes P8 — tramitações visíveis ao vereador."""

import importlib.util

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Demanda, Tramitacao, Usuario
from core.services.tramitacao_visibilidade_service import (
    TIPOS_TRAMITACAO_VISIVEIS_VEREADOR,
    descricao_tramitacao_para_vereador,
    filtrar_tramitacoes_para_usuario,
    rotulo_institucional_tramitacao,
    serializar_tramitacao_para_vereador,
    status_permite_pacote_devolutiva_vereador,
    tramitacao_visivel_para_vereador,
)
from core.models_unidade_administrativa import UnidadeAdministrativa
from core.serializers import TramitacaoSerializer
from integrations import sinapse_catalog

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_SERVICO_ID = _legacy.SINAPSE_SERVICO_ID
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class TramitacaoVisibilidadeServiceTests(TestCase):
    def test_tipos_internos_ocultos(self):
        self.assertFalse(tramitacao_visivel_para_vereador("EXECUCAO"))
        self.assertFalse(tramitacao_visivel_para_vereador("DESPACHO"))
        self.assertFalse(tramitacao_visivel_para_vereador("SOLICITACAO_DEVOLUTIVA"))
        self.assertFalse(tramitacao_visivel_para_vereador("CIENCIA_VEREADOR"))

    def test_marcos_legislativos_visiveis(self):
        self.assertTrue(tramitacao_visivel_para_vereador("CONCLUSAO"))
        self.assertTrue(tramitacao_visivel_para_vereador("ENVIO_OFICIAL"))
        self.assertTrue(tramitacao_visivel_para_vereador("DEVOLUTIVA_PROTOCOLO"))

    def test_filtro_queryset_vereador(self):
        vereador = Usuario.objects.create_user(username="ver_vis", password="x", perfil="VEREADOR")
        demanda = Demanda.objects.create(
            titulo="Teste visibilidade",
            descricao="x",
            autor=vereador,
            status="FINALIZADO",
        )
        Tramitacao.objects.create(
            demanda=demanda, responsavel=vereador, tipo="ENVIO_OFICIAL", descricao="Envio"
        )
        Tramitacao.objects.create(
            demanda=demanda, responsavel=vereador, tipo="DESPACHO", descricao="Despacho interno"
        )
        Tramitacao.objects.create(
            demanda=demanda, responsavel=vereador, tipo="EXECUCAO", descricao="Andamento interno"
        )
        Tramitacao.objects.create(
            demanda=demanda, responsavel=vereador, tipo="CONCLUSAO", descricao="Concluído"
        )
        qs = filtrar_tramitacoes_para_usuario(demanda.tramitacoes.all(), vereador, demanda=demanda)
        tipos = set(qs.values_list("tipo", flat=True))
        self.assertEqual(tipos, {"ENVIO_OFICIAL", "CONCLUSAO"})
        self.assertEqual(len(TIPOS_TRAMITACAO_VISIVEIS_VEREADOR), 4)

    def test_em_execucao_só_envio_oficial(self):
        vereador = Usuario.objects.create_user(username="ver_exec", password="x", perfil="VEREADOR")
        demanda = Demanda.objects.create(
            titulo="Em execução",
            descricao="x",
            autor=vereador,
            status="EM_EXECUCAO",
        )
        Tramitacao.objects.create(
            demanda=demanda, responsavel=vereador, tipo="ENVIO_OFICIAL", descricao="Envio"
        )
        Tramitacao.objects.create(
            demanda=demanda, responsavel=vereador, tipo="DESPACHO", descricao="Despacho"
        )
        Tramitacao.objects.create(
            demanda=demanda,
            responsavel=vereador,
            tipo="SOLICITACAO_DEVOLUTIVA",
            descricao="Parecer operacional:\nDetalhe interno",
        )
        qs = filtrar_tramitacoes_para_usuario(demanda.tramitacoes.all(), vereador, demanda=demanda)
        tipos = set(qs.values_list("tipo", flat=True))
        self.assertEqual(tipos, {"ENVIO_OFICIAL"})

    def test_devolutiva_extrai_só_resposta(self):
        tram = Tramitacao(
            tipo="DEVOLUTIVA_PROTOCOLO",
            descricao="Protocolo despachou devolutiva.\nResposta:\nTexto ao gabinete.",
        )
        self.assertEqual(descricao_tramitacao_para_vereador(tram), "Texto ao gabinete.")

    def test_pacote_devolutiva_vereador_só_apos_protocolo(self):
        self.assertFalse(status_permite_pacote_devolutiva_vereador("AGUARDANDO_DEVOLUTIVA_PROTOCOLO"))
        self.assertTrue(status_permite_pacote_devolutiva_vereador("DEVOLVIDO_VEREADOR"))

    def test_rotulo_institucional_por_tipo(self):
        self.assertEqual(
            rotulo_institucional_tramitacao("ENVIO_OFICIAL"),
            "Gabinete Legislativo",
        )
        self.assertEqual(
            rotulo_institucional_tramitacao("DEVOLUTIVA_PROTOCOLO"),
            "Protocolo Legislativo",
        )

    def test_conclusao_identifica_secretaria_e_setor(self):
        setor = UnidadeAdministrativa.objects.create(
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            sigla="SGZ-01",
            nome="Setor Zeladoria Centro",
            ativo=True,
        )
        demanda = Demanda.objects.create(
            titulo="Conclusão com setor",
            descricao="x",
            autor=Usuario.objects.create_user(username="ver_conc", password="x", perfil="VEREADOR"),
            status="FINALIZADO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            unidade_administrativa=setor,
        )
        tram = Tramitacao.objects.create(
            demanda=demanda,
            responsavel=demanda.autor,
            tipo="CONCLUSAO",
            descricao="Concluído",
            unidade_origem=setor,
        )
        data = serializar_tramitacao_para_vereador(
            TramitacaoSerializer(tram).data,
            demanda=demanda,
            tramitacao_obj=tram,
        )
        self.assertNotIn("Prefeitura", data["rotulo_institucional"])
        self.assertIn("SGZ-01", data["rotulo_institucional"])
        self.assertEqual(data["orgao_nome"], sinapse_catalog.get_orgao_nome(SINAPSE_ORGAO_A))
        self.assertEqual(data["unidade_nome"], "SGZ-01")
        self.assertIn("SGZ-01", data["descricao"])


class TramitacaoVisibilidadeAPITests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.vereador = Usuario.objects.create_user(
            username="ver_api_vis", password="x", perfil="VEREADOR"
        )
        self.protocolo = Usuario.objects.create_user(
            username="prot_api_vis", password="x", perfil="PROTOCOLO"
        )
        self.demanda = Demanda.objects.create(
            titulo="Demanda timeline",
            descricao="Texto",
            autor=self.vereador,
            status="FINALIZADO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            protocolo_executivo="2026-0200",
            protocolo_legislativo="OFICIO-2026-0200",
        )
        Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.protocolo,
            tipo="ENVIO_OFICIAL",
            descricao="Envio oficial",
        )
        Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.protocolo,
            tipo="DESPACHO",
            descricao="Encaminhado à secretaria",
        )
        Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.protocolo,
            tipo="EXECUCAO",
            descricao="Vistoria técnica realizada",
        )
        Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.protocolo,
            tipo="DEVOLUTIVA_PROTOCOLO",
            descricao="Protocolo despachou devolutiva.\nResposta:\nResposta ao gabinete.",
        )
        Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.vereador,
            tipo="ENCERRAMENTO_DEVOLUTIVA",
            descricao="Encerrada",
        )

    def test_vereador_nao_ve_tramitacoes_internas_na_api(self):
        self.client.force_authenticate(self.vereador)
        r = self.client.get(f"/api/demandas/{self.demanda.id}/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        tipos = {t["tipo"] for t in r.data["tramitacoes"]}
        self.assertEqual(tipos, {"ENVIO_OFICIAL", "DEVOLUTIVA_PROTOCOLO", "ENCERRAMENTO_DEVOLUTIVA"})
        dev = next(t for t in r.data["tramitacoes"] if t["tipo"] == "DEVOLUTIVA_PROTOCOLO")
        self.assertEqual(dev["descricao"], "Resposta ao gabinete.")
        self.assertEqual(dev["rotulo_institucional"], "Protocolo Legislativo")
        self.assertNotEqual(dev.get("responsavel", {}).get("username"), "Prefeitura")
        self.assertEqual(dev["orgao_nome"], sinapse_catalog.get_orgao_nome(SINAPSE_ORGAO_A))
        self.assertNotIn("Encaminhado", str(r.data["tramitacoes"]))

    def test_protocolo_ve_timeline_completa(self):
        self.client.force_authenticate(self.protocolo)
        r = self.client.get(f"/api/demandas/{self.demanda.id}/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        tipos = {t["tipo"] for t in r.data["tramitacoes"]}
        self.assertEqual(tipos, {"ENVIO_OFICIAL", "DESPACHO", "EXECUCAO", "DEVOLUTIVA_PROTOCOLO", "ENCERRAMENTO_DEVOLUTIVA"})

    def test_vereador_nao_acessa_pacote_antes_devolutiva_protocolo(self):
        self.demanda.status = "AGUARDANDO_DEVOLUTIVA_PROTOCOLO"
        self.demanda.save(update_fields=["status"])
        Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.protocolo,
            tipo="SOLICITACAO_DEVOLUTIVA",
            descricao="Parecer operacional:\nConteúdo sigiloso",
        )
        self.client.force_authenticate(self.vereador)
        r = self.client.get(f"/api/demandas/{self.demanda.id}/pacote-devolutiva/")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        r2 = self.client.get(f"/api/demandas/{self.demanda.id}/")
        self.assertIsNone(r2.data.get("pacote_devolutiva"))


class TramitacaoVisibilidadeDemanda2966Tests(TestCase):
    """Regressão com dados reais da homologação (E2E)."""

    def test_ciclo_finalizado_mostra_tres_marcos(self):
        demanda = Demanda.objects.filter(pk=2966).first()
        if demanda is None:
            self.skipTest("Demanda 2966 ausente neste ambiente")
        vereador = demanda.autor
        qs = filtrar_tramitacoes_para_usuario(
            demanda.tramitacoes.all(), vereador, demanda=demanda
        )
        tipos = list(qs.order_by("timestamp").values_list("tipo", flat=True))
        self.assertEqual(
            tipos,
            ["ENVIO_OFICIAL", "DEVOLUTIVA_PROTOCOLO", "ENCERRAMENTO_DEVOLUTIVA"],
        )
        dev = qs.filter(tipo="DEVOLUTIVA_PROTOCOLO").first()
        data = serializar_tramitacao_para_vereador(
            TramitacaoSerializer(dev).data,
            demanda=demanda,
            tramitacao_obj=dev,
        )
        self.assertIn("[E2E]", data["descricao"])
        self.assertNotIn("Protocolo despachou", data["descricao"])
