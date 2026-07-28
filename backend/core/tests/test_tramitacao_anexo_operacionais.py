"""Anexos operacionais reutilizáveis na conclusão final do Protocolo."""

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import AnexoTramitacao, ClusterExecucao, Demanda, Tramitacao
from core.models_operacional import FluxoRoteamento, OrquestradorConclusao
from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional
from core.services.operacional_estado_service import OperacionalEstadoService
from core.services.perna_operacional_service import PernaOperacionalService
from core.services.tramitacao_anexo_service import (
    listar_anexos_operacionais_demanda,
    vincular_anexos_existentes,
)

User = get_user_model()

SINAPSE_ORGAO_A = 9001
SINAPSE_ORGAO_B = 9002


class AnexosOperacionaisClusterTests(TestCase):
    def setUp(self):
        self.vereador = User.objects.create_user(
            username="ver_anexos_op", password="x", perfil="VEREADOR"
        )
        self.protocolo = User.objects.create_user(
            username="prot_anexos_op", password="x", perfil="PROTOCOLO"
        )
        self.sec_a = User.objects.create_user(
            username="sec_a_anexos",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        self.cluster = ClusterExecucao.objects.create(
            titulo="Super OS anexos",
            protocolo_super_os="SUPER-2026-ANX",
        )
        self.lider = Demanda.objects.create(
            titulo="Líder",
            descricao="x",
            autor=self.vereador,
            status="AGUARDANDO_DEVOLUTIVA_PROTOCOLO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            sinapse_orgao_lider_id=SINAPSE_ORGAO_A,
            fluxo_roteamento=FluxoRoteamento.FLUXO_TRANSVERSAL,
            orquestrador_conclusao=OrquestradorConclusao.SECRETARIA_LIDER,
            cluster=self.cluster,
        )
        self.irma = Demanda.objects.create(
            titulo="Irmã",
            descricao="x",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_orgao_id=SINAPSE_ORGAO_B,
            cluster=self.cluster,
        )
        tram_irma = Tramitacao.objects.create(
            demanda=self.irma,
            responsavel=self.sec_a,
            tipo="COMENTARIO",
            descricao="Andamento com anexo",
        )
        self.anexo_irma = AnexoTramitacao.objects.create(
            tramitacao=tram_irma,
            arquivo=SimpleUploadedFile("parecer_b.pdf", b"pdf-b"),
        )

    def test_listar_anexos_agrega_demandas_do_cluster(self):
        items = listar_anexos_operacionais_demanda(self.lider)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], self.anexo_irma.pk)
        self.assertEqual(items[0]["nome"], "parecer_b.pdf")

    def test_vincular_anexos_aceita_origem_no_cluster(self):
        tram_dev = Tramitacao.objects.create(
            demanda=self.lider,
            responsavel=self.protocolo,
            tipo="CONCLUSAO_FINAL",
            descricao="Devolutiva",
        )
        criados = vincular_anexos_existentes(
            tram_dev,
            [self.anexo_irma.pk],
            demanda_id=self.lider.pk,
        )
        self.assertEqual(len(criados), 1)
        self.assertEqual(criados[0].tramitacao_id, tram_dev.pk)


class ConclusaoParcialAnexosTests(TestCase):
    def setUp(self):
        self.svc = OperacionalEstadoService()
        self.perna_svc = PernaOperacionalService()
        self.vereador = User.objects.create_user(
            username="ver_cp_anx", password="x", perfil="VEREADOR"
        )
        self.sec_a = User.objects.create_user(
            username="sec_cp_anx",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        self.demanda = Demanda.objects.create(
            titulo="Conclusão parcial anexos",
            descricao="x",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            sinapse_orgao_lider_id=SINAPSE_ORGAO_A,
            fluxo_roteamento=FluxoRoteamento.FLUXO_DIRETO,
        )
        self.perna_svc.criar_pernas_no_despacho(
            self.demanda,
            [{"secretaria_id": SINAPSE_ORGAO_A}],
        )
        PernaOperacional.objects.filter(demanda=self.demanda).update(
            status=StatusPernaOperacional.EM_EXECUCAO
        )

    def test_conclusao_parcial_persiste_anexos_na_tramitacao(self):
        arquivo = SimpleUploadedFile("laudo.pdf", b"laudo")
        self.svc.aplicar_conclusao_parcial(
            self.demanda,
            self.sec_a,
            parecer="Serviço executado conforme vistoria.",
            arquivos_anexos=[arquivo],
        )
        tram = Tramitacao.objects.filter(
            demanda=self.demanda, tipo="CONCLUSAO_PARCIAL"
        ).first()
        self.assertIsNotNone(tram)
        self.assertEqual(tram.anexos.count(), 1)
        items = listar_anexos_operacionais_demanda(self.demanda)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["tipo_tramitacao"], "CONCLUSAO_PARCIAL")
        self.assertIn("origem_label", items[0])

    def test_timeline_vereador_inclui_anexos_da_conclusao(self):
        arquivo = SimpleUploadedFile("parecer.pdf", b"parecer")
        self.svc.aplicar_conclusao_parcial(
            self.demanda,
            self.sec_a,
            parecer="<p>Parecer com <strong>formatação</strong>.</p>",
            arquivos_anexos=[arquivo],
        )
        timeline = self.svc.montar_timeline_operacional(self.demanda, usuario=self.vereador)
        conclusoes = [ev for ev in timeline if ev["tipo"] == "CONCLUSAO_PARCIAL"]
        self.assertEqual(len(conclusoes), 1)
        self.assertEqual(len(conclusoes[0]["anexos"]), 1)
        self.assertEqual(conclusoes[0]["anexos"][0]["nome"], "parecer.pdf")

        historico = self.svc.compilar_historico_tecnico(self.demanda)
        eventos = historico.get("eventos_tecnicos") or []
        self.assertTrue(any(len(ev.get("anexos") or []) == 1 for ev in eventos))

    def test_origem_label_scatter_usa_setor(self):
        tram = Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.sec_a,
            tipo="OPERACAO_NO",
            descricao="Encerramento no setor",
            metadata={
                "acao_no": "ENCERRAR",
                "orgao_id": SINAPSE_ORGAO_A,
                "orgao_nome": "Secretaria A",
                "setor_id": 999,
                "setor_nome": "MCRUZ-SETOR-X",
            },
        )
        AnexoTramitacao.objects.create(
            tramitacao=tram,
            arquivo=SimpleUploadedFile("foto.jpg", b"jpg"),
        )
        items = listar_anexos_operacionais_demanda(self.demanda)
        anexo = next(i for i in items if i["nome"] == "foto.jpg")
        self.assertEqual(anexo["origem_label"], "Secretaria A › MCRUZ-SETOR-X")


class AnexosOperacionaisAPITests(APITestCase):
    def setUp(self):
        self.protocolo = User.objects.create_user(
            username="prot_api_anx", password="x", perfil="PROTOCOLO"
        )
        self.vereador = User.objects.create_user(
            username="ver_api_anx", password="x", perfil="VEREADOR"
        )
        self.demanda = Demanda.objects.create(
            titulo="API anexos",
            descricao="x",
            autor=self.vereador,
            status="AGUARDANDO_DEVOLUTIVA_PROTOCOLO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        tram = Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.protocolo,
            tipo="DESPACHO",
            descricao="Despacho inicial",
        )
        AnexoTramitacao.objects.create(
            tramitacao=tram,
            arquivo=SimpleUploadedFile("despacho.pdf", b"desp"),
        )

    def test_endpoint_anexos_operacionais_lista_anexos(self):
        self.client.force_authenticate(self.protocolo)
        resp = self.client.get(f"/api/demandas/{self.demanda.pk}/anexos-operacionais/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["nome"], "despacho.pdf")
