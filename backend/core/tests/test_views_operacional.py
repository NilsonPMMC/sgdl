"""Testes API — Gestão Operacional (Portal dos Vereadores)."""

import importlib.util

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import ClusterExecucao, Demanda, Tramitacao, Usuario
from core.models_assinatura_eletronica import AssinaturaValidacaoGestor
from core.models_operacional import FluxoRoteamento
from core.models_unidade_administrativa import UnidadeAdministrativaResponsavel
from core.services.assinatura_eletronica_service import (
    DECLARACAO_CONCLUSAO,
    DECLARACAO_CONCLUSAO_FINAL,
    DECLARACAO_GESTOR_PROTOCOLO,
    AssinaturaEletronicaService,
)
from core.services.demanda_despacho_service import DemandaDespachoService
from core.services.usuario_vinculo_service import PROTOCOLO_UNIDADE_PK

PARECER = "Parecer operacional com conteúdo suficiente para validação."
RESPOSTA_PROTOCOLO = "Resposta consolidada do protocolo ao vereador."

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_ORGAO_B = _legacy.SINAPSE_ORGAO_B
SINAPSE_SERVICO_ID = _legacy.SINAPSE_SERVICO_ID
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class OperacionalEstadoAPITests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.vereador = Usuario.objects.create_user(
            username="ver_op_api", password="x", perfil="VEREADOR"
        )
        self.protocolo = Usuario.objects.create_user(
            username="prot_op_api", password="x", perfil="PROTOCOLO"
        )
        self.gestor_proto = Usuario.objects.create_user(
            username="gest_op_api",
            password="x",
            perfil="GESTOR",
            sinapse_orgao_id=12,
        )
        UnidadeAdministrativaResponsavel.objects.create(
            unidade_id=PROTOCOLO_UNIDADE_PK,
            usuario=self.gestor_proto,
            ativo=True,
        )
        self.sec_a = Usuario.objects.create_user(
            username="sec_op_api_a",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        self.sec_b = Usuario.objects.create_user(
            username="sec_op_api_b",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_B,
        )
        self.demanda = Demanda.objects.create(
            titulo="API operacional",
            descricao="Teste",
            autor=self.vereador,
            status="AGUARDANDO_PROTOCOLO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            origem_vinculo=Demanda.ORIGEM_VINCULO_TENDENCIA,
            protocolo_legislativo="OP-API-001",
        )

    def _url(self, nome: str, pk: int | None = None) -> str:
        return reverse(nome, kwargs={"demanda_pk": pk or self.demanda.pk})

    def test_estado_operacional_retorna_acoes_protocolo(self):
        self.client.force_authenticate(user=self.protocolo)
        resp = self.client.get(self._url("demanda-operacional-estado"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("triagem_despacho", resp.data["acoes_disponiveis"])
        self.assertIn("vincular_servico", resp.data["acoes_disponiveis"])

    def test_vincular_servico_tendencia(self):
        self.client.force_authenticate(user=self.protocolo)
        resp = self.client.post(
            self._url("demanda-operacional-vincular-servico"),
            {"sinapse_servico_id": SINAPSE_SERVICO_ID},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.demanda.refresh_from_db()
        self.assertEqual(self.demanda.sinapse_servico_id, SINAPSE_SERVICO_ID)
        self.assertEqual(self.demanda.origem_vinculo, Demanda.ORIGEM_VINCULO_CARTA)

    def test_recusa_protocolo_tendencia(self):
        self.client.force_authenticate(user=self.protocolo)
        resp = self.client.post(
            self._url("demanda-operacional-recusa"),
            {"parecer": "Demanda fora da competência municipal."},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.demanda.refresh_from_db()
        self.assertEqual(self.demanda.status, "DEVOLVIDO_VEREADOR")

    def test_conclusao_parcial_transversal(self):
        DemandaDespachoService().despachar_multiplo(
            self.demanda,
            [{"secretaria_id": SINAPSE_ORGAO_A}, {"secretaria_id": SINAPSE_ORGAO_B}],
            usuario=self.protocolo,
            texto_despacho="Despacho transversal para teste de conclusão parcial.",
        )
        self.demanda.refresh_from_db()
        clone = Demanda.objects.filter(cluster=self.demanda.cluster).exclude(pk=self.demanda.pk).first()
        for d in (self.demanda, clone):
            d.status = "EM_EXECUCAO"
            d.save(update_fields=["status"])

        self.client.force_authenticate(user=self.sec_b)
        resp_b = self.client.post(
            reverse("demanda-operacional-conclusao-parcial", kwargs={"demanda_pk": clone.pk}),
            {"parecer_operacional": PARECER},
            format="json",
        )
        self.assertEqual(resp_b.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(user=self.sec_a)
        resp_a = self.client.post(
            self._url("demanda-operacional-conclusao-parcial"),
            {"parecer_operacional": PARECER},
            format="json",
        )
        self.assertEqual(resp_a.status_code, status.HTTP_200_OK)
        self.assertTrue(resp_a.data["operacional"]["processo_avancou"])
        self.demanda.refresh_from_db()
        self.assertEqual(self.demanda.status, "AGUARDANDO_DEVOLUTIVA_PROTOCOLO")

    def test_conclusao_final_com_assinatura(self):
        self.demanda.status = "AGUARDANDO_DEVOLUTIVA_PROTOCOLO"
        self.demanda.fluxo_roteamento = FluxoRoteamento.FLUXO_DIRETO
        self.demanda.sinapse_orgao_id = SINAPSE_ORGAO_A
        self.demanda.sinapse_orgao_lider_id = SINAPSE_ORGAO_A
        self.demanda.protocolo_executivo = "2026-0200"
        self.demanda.save()
        Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.sec_a,
            tipo="CONCLUSAO_TECNICA",
            descricao=f"Parecer:\n{PARECER}",
            metadata={"parecer": PARECER},
        )

        self.client.force_authenticate(user=self.protocolo)
        preview = self.client.post(
            self._url("demanda-operacional-preview-conclusao-final"),
            {"parecer_resposta": RESPOSTA_PROTOCOLO},
            format="json",
        )
        self.assertEqual(preview.status_code, status.HTTP_200_OK)

        resp = self.client.post(
            self._url("demanda-operacional-conclusao-final"),
            {
                "parecer_resposta": RESPOSTA_PROTOCOLO,
                "hash_documento": preview.data["hash_documento"],
                "declaracao_operador": DECLARACAO_CONCLUSAO_FINAL,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get("aguardando_validacao_gestor"))
        self.demanda.refresh_from_db()
        self.assertEqual(self.demanda.status, "AGUARDANDO_DEVOLUTIVA_PROTOCOLO")
        tram_pendente = self.demanda.tramitacoes.filter(tipo="CONCLUSAO_FINAL").first()
        self.assertIsNotNone(tram_pendente)
        self.assertTrue((tram_pendente.metadata or {}).get("aguardando_validacao_gestor"))

        validacao = AssinaturaValidacaoGestor.objects.get(demanda=self.demanda)
        self.client.force_authenticate(user=self.gestor_proto)
        validar = self.client.post(
            f"/api/assinaturas-validacao/{validacao.pk}/validar/",
            {
                "hash_documento": preview.data["hash_documento"],
                "declaracao_gestor": DECLARACAO_GESTOR_PROTOCOLO,
            },
            format="json",
        )
        self.assertEqual(validar.status_code, status.HTTP_200_OK)
        self.demanda.refresh_from_db()
        self.assertEqual(self.demanda.status, "FINALIZADO")
        tram_final = Tramitacao.objects.filter(demanda=self.demanda, tipo="CONCLUSAO_FINAL").first()
        self.assertIsNotNone(tram_final)
        self.assertFalse((tram_final.metadata or {}).get("aguardando_validacao_gestor"))
        self.assertIsNotNone(tram_final.editavel_ate)
        self.assertTrue(
            Tramitacao.objects.filter(demanda=self.demanda, tipo="CONCLUSAO_FINAL").exists()
        )
        self.assertTrue(
            Tramitacao.objects.filter(demanda=self.demanda, tipo="ENCERRAMENTO_DEVOLUTIVA").exists()
        )
        self.assertFalse(
            Tramitacao.objects.filter(demanda=self.demanda, tipo="DEVOLUTIVA_PROTOCOLO").exists()
        )

    def test_conclusao_final_gestor_protocolo_sem_declaracao_operador_hjul11(self):
        """Gestor SGAC conclui direto com declaracao_gestor — sem exigir operador."""
        self.demanda.status = "AGUARDANDO_DEVOLUTIVA_PROTOCOLO"
        self.demanda.fluxo_roteamento = FluxoRoteamento.FLUXO_DIRETO
        self.demanda.sinapse_orgao_id = SINAPSE_ORGAO_A
        self.demanda.sinapse_orgao_lider_id = SINAPSE_ORGAO_A
        self.demanda.protocolo_executivo = "2026-0201"
        self.demanda.save()
        Tramitacao.objects.create(
            demanda=self.demanda,
            responsavel=self.sec_a,
            tipo="CONCLUSAO_TECNICA",
            descricao=f"Parecer:\n{PARECER}",
            metadata={"parecer": PARECER},
        )

        self.client.force_authenticate(user=self.gestor_proto)
        preview = self.client.post(
            self._url("demanda-operacional-preview-conclusao-final"),
            {"parecer_resposta": RESPOSTA_PROTOCOLO},
            format="json",
        )
        self.assertEqual(preview.status_code, status.HTTP_200_OK)
        self.assertEqual(preview.data.get("modo_assinatura"), "gestor_apenas")

        resp = self.client.post(
            self._url("demanda-operacional-conclusao-final"),
            {
                "parecer_resposta": RESPOSTA_PROTOCOLO,
                "hash_documento": preview.data["hash_documento"],
                "declaracao_gestor": DECLARACAO_GESTOR_PROTOCOLO,
                "assinatura_apenas_gestor": True,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertFalse(resp.data.get("aguardando_validacao_gestor"))
        self.demanda.refresh_from_db()
        self.assertEqual(self.demanda.status, "FINALIZADO")
        tram = Tramitacao.objects.filter(
            demanda=self.demanda, tipo="CONCLUSAO_FINAL"
        ).first()
        self.assertIsNotNone(tram)
        self.assertFalse((tram.metadata or {}).get("aguardando_validacao_gestor"))
        self.assertFalse(
            AssinaturaValidacaoGestor.objects.filter(
                demanda=self.demanda,
                status=AssinaturaValidacaoGestor.STATUS_PENDENTE,
            ).exists()
        )

    def test_devolver_protocolo_secretaria(self):
        self.demanda.status = "PROTOCOLADO"
        self.demanda.fluxo_roteamento = FluxoRoteamento.FLUXO_DIRETO
        self.demanda.sinapse_orgao_id = SINAPSE_ORGAO_A
        self.demanda.sinapse_orgao_lider_id = SINAPSE_ORGAO_A
        self.demanda.save()
        self.client.force_authenticate(user=self.sec_a)
        resp = self.client.post(
            self._url("demanda-operacional-devolver"),
            {"justificativa": "Setor incorreto — necessário reencaminhamento."},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.demanda.refresh_from_db()
        self.assertEqual(self.demanda.status, "AGUARDANDO_PROTOCOLO")

    def test_devolver_protocolo_bloqueado_apos_iniciar_execucao(self):
        self.demanda.status = "EM_EXECUCAO"
        self.demanda.fluxo_roteamento = FluxoRoteamento.FLUXO_DIRETO
        self.demanda.sinapse_orgao_id = SINAPSE_ORGAO_A
        self.demanda.sinapse_orgao_lider_id = SINAPSE_ORGAO_A
        self.demanda.save()
        self.client.force_authenticate(user=self.sec_a)
        resp = self.client.post(
            self._url("demanda-operacional-devolver"),
            {"justificativa": "Tentativa após início da execução."},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_conclusao_tecnica_fluxo_direto(self):
        self.demanda.status = "EM_EXECUCAO"
        self.demanda.fluxo_roteamento = FluxoRoteamento.FLUXO_DIRETO
        self.demanda.sinapse_orgao_id = SINAPSE_ORGAO_A
        self.demanda.sinapse_orgao_lider_id = SINAPSE_ORGAO_A
        self.demanda.save()

        svc = AssinaturaEletronicaService()
        preview = svc.preparar_assinatura_conclusao_secretaria(
            self.demanda, parecer_operacional=PARECER
        )
        self.client.force_authenticate(user=self.sec_a)
        resp = self.client.post(
            self._url("demanda-operacional-conclusao-tecnica"),
            {
                "parecer_operacional": PARECER,
                "hash_documento": preview["hash_documento"],
                "declaracao": DECLARACAO_CONCLUSAO,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get("aguardando_validacao_gestor"))
        self.demanda.refresh_from_db()
        self.assertEqual(self.demanda.status, "EM_EXECUCAO")
