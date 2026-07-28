"""Testes do ciclo de devolutiva via Protocolo."""

import importlib.util

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Demanda, Tramitacao, Usuario
from core.services.assinatura_eletronica_service import (
    DECLARACAO_CONCLUSAO,
    DECLARACAO_DEVOLUTIVA,
    DECLARACAO_GESTOR_PROTOCOLO,
    AssinaturaEletronicaService,
)
from core.services.devolutiva_protocolo_service import DevolutivaProtocoloService

PARECER_SECRETARIA = "Operação concluída com sucesso no local."
PARECER_PROTOCOLO = "Segue devolutiva da secretaria para conhecimento."
PROTOCOLO_ORGAO_ID = 12

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_SERVICO_ID = _legacy.SINAPSE_SERVICO_ID
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class DevolutivaProtocoloServiceTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.vereador = Usuario.objects.create_user(
            username="ver_dev", password="x", perfil="VEREADOR"
        )
        self.secretaria = Usuario.objects.create_user(
            username="sec_dev",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        self.protocolo = Usuario.objects.create_user(
            username="prot_dev", password="x", perfil="PROTOCOLO"
        )
        self.demanda = Demanda.objects.create(
            titulo="Conclusão operacional",
            descricao="Serviço executado",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            protocolo_executivo="2026-0099",
            protocolo_legislativo="LEG-0099",
        )

    def test_ciclo_completo_devolutiva(self):
        svc = DevolutivaProtocoloService()
        svc.solicitar_devolutiva(
            self.demanda,
            self.secretaria,
            parecer_operacional="Serviço concluído conforme vistoria técnica.",
        )
        self.demanda.refresh_from_db()
        self.assertEqual(self.demanda.status, "AGUARDANDO_DEVOLUTIVA_PROTOCOLO")

        svc.despachar_devolutiva(
            self.demanda,
            self.protocolo,
            parecer_resposta="Encaminhamos resposta da secretaria ao gabinete.",
        )
        self.demanda.refresh_from_db()
        self.assertEqual(self.demanda.status, "FINALIZADO")
        self.assertIsNotNone(self.demanda.data_finalizacao)
        self.assertEqual(
            Tramitacao.objects.filter(demanda=self.demanda, tipo="ENCERRAMENTO_DEVOLUTIVA").count(),
            1,
        )

    def test_encerrar_devolutiva_idempotente_quando_ja_finalizado(self):
        svc = DevolutivaProtocoloService()
        svc.solicitar_devolutiva(
            self.demanda,
            self.secretaria,
            parecer_operacional="Serviço concluído conforme vistoria técnica.",
        )
        svc.despachar_devolutiva(
            self.demanda,
            self.protocolo,
            parecer_resposta="Encaminhamos resposta da secretaria ao gabinete.",
        )
        self.demanda.refresh_from_db()
        self.assertEqual(self.demanda.status, "FINALIZADO")
        svc.encerrar_devolutiva(self.demanda, self.vereador)
        self.assertEqual(self.demanda.status, "FINALIZADO")

    def test_secretaria_nao_finaliza_direto(self):
        with self.assertRaises(ValueError):
            DevolutivaProtocoloService().encerrar_devolutiva(self.demanda, self.secretaria)

    def test_despachar_devolutiva_fluxo_direto_aguardando_sem_conclusao_tecnica(self):
        """Protocolo despacha quando status já é AGUARDANDO, mesmo sem evento operacional."""
        self.demanda.fluxo_roteamento = "FLUXO_DIRETO"
        self.demanda.status = "AGUARDANDO_DEVOLUTIVA_PROTOCOLO"
        self.demanda.save(update_fields=["fluxo_roteamento", "status"])

        svc = DevolutivaProtocoloService()
        demanda, _tram = svc.despachar_devolutiva(
            self.demanda,
            self.protocolo,
            parecer_resposta="Resposta do protocolo ao gabinete sobre o atendimento.",
        )
        demanda.refresh_from_db()
        self.assertEqual(demanda.status, "FINALIZADO")


class DevolutivaProtocoloAPITests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.vereador = Usuario.objects.create_user(
            username="ver_dev_api", password="x", perfil="VEREADOR"
        )
        self.secretaria = Usuario.objects.create_user(
            username="sec_dev_api",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        self.protocolo = Usuario.objects.create_user(
            username="prot_dev_api", password="x", perfil="PROTOCOLO"
        )
        self.demanda = Demanda.objects.create(
            titulo="API devolutiva",
            descricao="Teste",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            protocolo_executivo="2026-0100",
        )

    def test_api_solicitar_e_despachar_devolutiva(self):
        svc = AssinaturaEletronicaService()
        preview_sec = svc.preparar_assinatura_conclusao_secretaria(
            self.demanda, parecer_operacional=PARECER_SECRETARIA
        )
        self.client.force_authenticate(self.secretaria)
        r1 = self.client.post(
            f"/api/demandas/{self.demanda.pk}/solicitar-devolutiva/",
            {
                "parecer_operacional": PARECER_SECRETARIA,
                "hash_documento": preview_sec["hash_documento"],
                "declaracao": DECLARACAO_CONCLUSAO,
            },
            format="json",
        )
        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        self.assertEqual(r1.data["status"], "AGUARDANDO_DEVOLUTIVA_PROTOCOLO")

        gestor = Usuario.objects.create_user(
            username="gest_prot_dev_api",
            password="x",
            perfil="PROTOCOLO",
            sinapse_orgao_id=PROTOCOLO_ORGAO_ID,
        )
        preview_prot = svc.preparar_assinatura_despacho_devolutiva(
            self.demanda, parecer_resposta=PARECER_PROTOCOLO
        )
        self.client.force_authenticate(self.protocolo)
        r2 = self.client.post(
            f"/api/demandas/{self.demanda.pk}/despachar-devolutiva/",
            {
                "parecer_resposta": PARECER_PROTOCOLO,
                "hash_documento": preview_prot["hash_documento"],
                "declaracao": DECLARACAO_DEVOLUTIVA,
                "declaracao_gestor": DECLARACAO_GESTOR_PROTOCOLO,
                "gestor_protocolo_id": gestor.pk,
            },
            format="json",
        )
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(r2.data["status"], "FINALIZADO")

        self.client.force_authenticate(self.vereador)
        r3 = self.client.post(
            f"/api/demandas/{self.demanda.pk}/confirmar-ciencia/",
            {
                "texto_resposta_cidadao": "Informamos que a solicitação foi atendida pela secretaria.",
                "gerar_oficio": False,
                "encerrar": True,
            },
            format="json",
        )
        self.assertEqual(r3.status_code, status.HTTP_200_OK)
        self.assertEqual(r3.data["status"], "FINALIZADO")

    def test_atualizar_status_nao_aceita_finalizado(self):
        self.client.force_authenticate(self.secretaria)
        r = self.client.post(
            f"/api/demandas/{self.demanda.pk}/atualizar_status/",
            {"status": "FINALIZADO"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
