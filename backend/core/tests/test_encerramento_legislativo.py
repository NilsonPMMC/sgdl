"""Testes Fase 6 — encerramento legislativo e resposta ao cidadão."""

import importlib.util

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Demanda, Tramitacao, Usuario
from core.models_encerramento_legislativo import EncerramentoLegislativo
from core.services.devolutiva_protocolo_service import DevolutivaProtocoloService
from core.services.encerramento_legislativo_service import EncerramentoLegislativoService

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class EncerramentoLegislativoServiceTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.vereador = Usuario.objects.create_user(
            username="ver_enc", password="x", perfil="VEREADOR"
        )
        self.secretaria = Usuario.objects.create_user(
            username="sec_enc",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        self.protocolo = Usuario.objects.create_user(
            username="prot_enc", password="x", perfil="PROTOCOLO"
        )
        self.demanda = Demanda.objects.create(
            titulo="Iluminação pública",
            descricao="Poste apagado na rua X",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            protocolo_executivo="2026-0200",
            protocolo_legislativo="LEG-0200",
        )

    def _ate_devolvido_vereador(self):
        DevolutivaProtocoloService().solicitar_devolutiva(
            self.demanda,
            self.secretaria,
            parecer_operacional="Lâmpada substituída conforme vistoria.",
        )
        DevolutivaProtocoloService().despachar_devolutiva(
            self.demanda,
            self.protocolo,
            parecer_resposta="Secretaria concluiu o serviço. Encaminhamos ao gabinete.",
        )
        self.demanda.refresh_from_db()

    def test_pacote_devolutiva_monta_pareceres(self):
        self._ate_devolvido_vereador()
        pacote = EncerramentoLegislativoService().montar_pacote_devolutiva(self.demanda)
        self.assertIn("Lâmpada substituída", pacote["parecer_operacional"])
        self.assertIn("Secretaria concluiu", pacote["resposta_protocolo"])

    def test_confirmar_ciencia_encerra_e_gera_pdf(self):
        self._ate_devolvido_vereador()
        EncerramentoLegislativoService().confirmar_ciencia(
            self.demanda,
            self.vereador,
            texto_resposta_cidadao="Informamos que o poste foi reparado.",
            gerar_oficio=True,
            encerrar=True,
        )
        self.demanda.refresh_from_db()
        self.assertEqual(self.demanda.status, "FINALIZADO")
        enc = EncerramentoLegislativo.objects.get(demanda=self.demanda)
        self.assertIsNotNone(enc.ciencia_em)
        self.assertTrue(
            Tramitacao.objects.filter(demanda=self.demanda, tipo="CIENCIA_VEREADOR").exists()
        )
        self.assertTrue(self.demanda.anexos.filter(descricao__icontains="Resposta ao cidadão").exists())


class EncerramentoLegislativoAPITests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.vereador = Usuario.objects.create_user(
            username="ver_enc_api", password="x", perfil="VEREADOR"
        )
        self.secretaria = Usuario.objects.create_user(
            username="sec_enc_api",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        self.protocolo = Usuario.objects.create_user(
            username="prot_enc_api", password="x", perfil="PROTOCOLO"
        )
        self.demanda = Demanda.objects.create(
            titulo="Buraco",
            descricao="Via danificada",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            protocolo_executivo="2026-0201",
        )
        DevolutivaProtocoloService().solicitar_devolutiva(
            self.demanda,
            self.secretaria,
            parecer_operacional="Buraco tapado pela secretaria de obras.",
        )
        DevolutivaProtocoloService().despachar_devolutiva(
            self.demanda,
            self.protocolo,
            parecer_resposta="Serviço concluído. Devolutiva ao vereador.",
        )

    def test_get_pacote_devolutiva(self):
        self.client.force_authenticate(self.vereador)
        r = self.client.get(f"/api/demandas/{self.demanda.pk}/pacote-devolutiva/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("parecer_operacional", r.data)

    def test_confirmar_ciencia_api(self):
        self.client.force_authenticate(self.vereador)
        r = self.client.post(
            f"/api/demandas/{self.demanda.pk}/confirmar-ciencia/",
            {
                "texto_resposta_cidadao": "A via foi recuperada conforme solicitado.",
                "gerar_oficio": False,
                "encerrar": True,
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["status"], "FINALIZADO")
