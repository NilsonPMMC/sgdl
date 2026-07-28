"""Testes — estudo/viabilidade e base stand-by."""

import importlib.util

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Demanda, Usuario
from core.models_estudo_viabilidade import (
    MotivoNaoExecucao,
    RegistroEstudoViabilidade,
    ResultadoOperacional,
)
from core.services.estudo_viabilidade_service import (
    EstudoViabilidadeError,
    EstudoViabilidadeService,
)

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_ORGAO_B = _legacy.SINAPSE_ORGAO_B
SINAPSE_SERVICO_ID = _legacy.SINAPSE_SERVICO_ID
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin

PARECER = "Demanda analisada: execução material inviável no escopo solicitado."


class EstudoViabilidadeServiceTests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.vereador = Usuario.objects.create_user(
            username="ver_estudo", password="x", perfil="VEREADOR"
        )
        self.secretaria = Usuario.objects.create_user(
            username="sec_estudo",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        self.protocolo = Usuario.objects.create_user(
            username="prot_estudo", password="x", perfil="PROTOCOLO"
        )
        self.demanda = Demanda.objects.create(
            titulo="Iluminação pública ampliada",
            descricao="Pedido abrangente",
            autor=self.vereador,
            status="EM_EXECUCAO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            bairro="Centro",
            protocolo_executivo="2026-0300",
        )

    def test_registrar_stand_by_cria_registro(self):
        svc = EstudoViabilidadeService()
        svc.registrar_conclusao_operacional(
            self.demanda,
            self.secretaria,
            parecer=PARECER,
            payload={
                "resultado_operacional": ResultadoOperacional.RESPONDIDO_SEM_EXECUCAO,
                "motivo_nao_execucao": MotivoNaoExecucao.ESTUDO_VIABILIDADE,
                "escopo_geografico": "Município inteiro",
                "registrar_stand_by": True,
            },
        )
        self.demanda.refresh_from_db()
        self.assertTrue(self.demanda.stand_by_estudo_viabilidade)
        self.assertEqual(
            self.demanda.resultado_operacional,
            ResultadoOperacional.RESPONDIDO_SEM_EXECUCAO,
        )
        registro = RegistroEstudoViabilidade.objects.get(demanda=self.demanda)
        self.assertEqual(registro.escopo_geografico, "Município inteiro")
        self.assertEqual(registro.registrado_por_id, self.secretaria.pk)

    def test_sem_payload_mantem_executado_sem_stand_by(self):
        svc = EstudoViabilidadeService()
        svc.registrar_conclusao_operacional(
            self.demanda,
            self.secretaria,
            parecer=PARECER,
            payload={"resultado_operacional": ResultadoOperacional.EXECUTADO},
        )
        self.demanda.refresh_from_db()
        self.assertFalse(self.demanda.stand_by_estudo_viabilidade)
        self.assertFalse(
            RegistroEstudoViabilidade.objects.filter(demanda=self.demanda).exists()
        )

    def test_stand_by_exige_escopo(self):
        svc = EstudoViabilidadeService()
        with self.assertRaises(EstudoViabilidadeError):
            svc.registrar_conclusao_operacional(
                self.demanda,
                self.secretaria,
                parecer=PARECER,
                payload={
                    "resultado_operacional": ResultadoOperacional.ORIENTACAO,
                    "registrar_stand_by": True,
                    "escopo_geografico": "ab",
                },
            )

    def test_scatter_sem_payload_nao_grava_executado(self):
        from unittest.mock import Mock

        from core.services.estudo_viabilidade_service import (
            registrar_resultado_operacional_se_processo_avancou,
        )

        request = Mock()
        request.data = {}
        registrar_resultado_operacional_se_processo_avancou(
            request,
            self.demanda,
            self.secretaria,
            parecer=PARECER,
            processo_avancou=True,
        )
        self.demanda.refresh_from_db()
        self.assertEqual(self.demanda.resultado_operacional, "")
        self.assertFalse(self.demanda.stand_by_estudo_viabilidade)

    def test_sem_execucao_exige_motivo(self):
        svc = EstudoViabilidadeService()
        with self.assertRaises(EstudoViabilidadeError):
            svc.registrar_conclusao_operacional(
                self.demanda,
                self.secretaria,
                parecer=PARECER,
                payload={
                    "resultado_operacional": ResultadoOperacional.RESPONDIDO_SEM_EXECUCAO,
                    "registrar_stand_by": False,
                },
            )

    def test_remover_stand_by_apaga_registro(self):
        svc = EstudoViabilidadeService()
        svc.registrar_conclusao_operacional(
            self.demanda,
            self.secretaria,
            parecer=PARECER,
            payload={
                "resultado_operacional": ResultadoOperacional.ORIENTACAO,
                "escopo_geografico": "Bairro X",
                "registrar_stand_by": True,
            },
        )
        svc.registrar_conclusao_operacional(
            self.demanda,
            self.secretaria,
            parecer=PARECER,
            payload={
                "resultado_operacional": ResultadoOperacional.EXECUTADO,
                "registrar_stand_by": False,
            },
        )
        self.demanda.refresh_from_db()
        self.assertFalse(self.demanda.stand_by_estudo_viabilidade)
        self.assertFalse(
            RegistroEstudoViabilidade.objects.filter(demanda=self.demanda).exists()
        )


class EstudoViabilidadeAPITests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.vereador = Usuario.objects.create_user(
            username="ver_estudo_api", password="x", perfil="VEREADOR"
        )
        self.protocolo = Usuario.objects.create_user(
            username="prot_estudo_api", password="x", perfil="PROTOCOLO"
        )
        self.sec_b = Usuario.objects.create_user(
            username="sec_estudo_b",
            password="x",
            perfil="SECRETARIA",
            sinapse_orgao_id=SINAPSE_ORGAO_B,
        )
        self.demanda = Demanda.objects.create(
            titulo="Stand-by API",
            descricao="Teste",
            autor=self.vereador,
            status="FINALIZADO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            bairro="Centro",
            stand_by_estudo_viabilidade=True,
            resultado_operacional=ResultadoOperacional.RESPONDIDO_SEM_EXECUCAO,
            motivo_nao_execucao=MotivoNaoExecucao.ESTUDO_VIABILIDADE,
            escopo_geografico="Município inteiro",
        )
        RegistroEstudoViabilidade.objects.create(
            demanda=self.demanda,
            resultado_operacional=ResultadoOperacional.RESPONDIDO_SEM_EXECUCAO,
            motivo_nao_execucao=MotivoNaoExecucao.ESTUDO_VIABILIDADE,
            escopo_geografico="Município inteiro",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            parecer_snapshot=PARECER,
        )
        self.nova = Demanda.objects.create(
            titulo="Nova demanda similar",
            descricao="Teste referência",
            autor=self.vereador,
            status="AGUARDANDO_PROTOCOLO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            bairro="Centro",
        )

    def test_listagem_stand_by_protocolo(self):
        self.client.force_authenticate(user=self.protocolo)
        resp = self.client.get(reverse("estudos-viabilidade-list"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resp.data["count"], 1)
        ids = [item["demanda_id"] for item in resp.data["results"]]
        self.assertIn(self.demanda.pk, ids)

    def test_listagem_stand_by_negada_vereador(self):
        self.client.force_authenticate(user=self.vereador)
        resp = self.client.get(reverse("estudos-viabilidade-list"))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_secretaria_ve_apenas_orgao_proprio(self):
        self.client.force_authenticate(user=self.sec_b)
        resp = self.client.get(reverse("estudos-viabilidade-list"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 0)

    def test_referencias_stand_by_visiveis_executivo(self):
        self.client.force_authenticate(user=self.protocolo)
        resp = self.client.get(
            reverse("demanda-detail", kwargs={"pk": self.nova.pk})
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        refs = resp.data.get("referencias_stand_by") or []
        self.assertTrue(any(r["demanda_id"] == self.demanda.pk for r in refs))

    def test_referencias_stand_by_ocultas_vereador(self):
        self.client.force_authenticate(user=self.vereador)
        resp = self.client.get(
            reverse("demanda-detail", kwargs={"pk": self.nova.pk})
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data.get("referencias_stand_by"), [])

    def test_fila_stand_by_listagem_demandas(self):
        self.client.force_authenticate(user=self.protocolo)
        resp = self.client.get("/api/demandas/", {"fila": "stand_by"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payload = resp.data
        if isinstance(payload, dict):
            items = payload.get("results", [])
        else:
            items = payload
        ids = [d["id"] for d in items]
        self.assertIn(self.demanda.pk, ids)
