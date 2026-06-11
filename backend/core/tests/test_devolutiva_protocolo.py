"""Testes do ciclo de devolutiva via Protocolo."""

import importlib.util

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Demanda, Tramitacao, Usuario
from core.services.devolutiva_protocolo_service import DevolutivaProtocoloService

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
        self.assertEqual(self.demanda.status, "DEVOLVIDO_VEREADOR")

        svc.encerrar_devolutiva(self.demanda, self.vereador)
        self.demanda.refresh_from_db()
        self.assertEqual(self.demanda.status, "FINALIZADO")
        self.assertIsNotNone(self.demanda.data_finalizacao)
        self.assertEqual(
            Tramitacao.objects.filter(demanda=self.demanda, tipo="ENCERRAMENTO_DEVOLUTIVA").count(),
            1,
        )

    def test_secretaria_nao_finaliza_direto(self):
        with self.assertRaises(ValueError):
            DevolutivaProtocoloService().encerrar_devolutiva(self.demanda, self.secretaria)


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
        self.client.force_authenticate(self.secretaria)
        r1 = self.client.post(
            f"/api/demandas/{self.demanda.pk}/solicitar-devolutiva/",
            {"parecer_operacional": "Operação concluída com sucesso no local."},
            format="json",
        )
        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        self.assertEqual(r1.data["status"], "AGUARDANDO_DEVOLUTIVA_PROTOCOLO")

        self.client.force_authenticate(self.protocolo)
        r2 = self.client.post(
            f"/api/demandas/{self.demanda.pk}/despachar-devolutiva/",
            {"parecer_resposta": "Segue devolutiva da secretaria para conhecimento."},
            format="json",
        )
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(r2.data["status"], "DEVOLVIDO_VEREADOR")

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
