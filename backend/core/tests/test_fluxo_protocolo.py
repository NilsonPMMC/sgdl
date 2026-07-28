from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Demanda, Notificacao, Usuario
from core.models_fluxo_protocolo import ServicoFluxoProtocolo
from core.services.fluxo_protocolo_service import FluxoProtocoloService

import importlib.util

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_ORGAO_A = _legacy.SINAPSE_ORGAO_A
SINAPSE_SERVICO_ID = _legacy.SINAPSE_SERVICO_ID
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


class FluxoProtocoloServiceTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.vereador = Usuario.objects.create_user(
            username="ver_fluxo", password="x", perfil="VEREADOR"
        )

    def _demanda_aguardando(self, **kwargs):
        defaults = {
            "titulo": "Tapa buraco",
            "descricao": "Buraco na rua",
            "autor": self.vereador,
            "status": "AGUARDANDO_PROTOCOLO",
            "sinapse_servico_id": SINAPSE_SERVICO_ID,
            "sinapse_orgao_id": SINAPSE_ORGAO_A,
            "protocolo_legislativo": "OFICIO-2026-0001",
            "embedding": [1.0] + [0.0] * 1023,
        }
        defaults.update(kwargs)
        return Demanda.objects.create(**defaults)

    def test_nao_despacha_sem_config_automatico(self):
        d = self._demanda_aguardando()
        ok = FluxoProtocoloService().tentar_despacho_automatico_pk(d.pk)
        self.assertFalse(ok)
        d.refresh_from_db()
        self.assertEqual(d.status, "AGUARDANDO_PROTOCOLO")

    def test_despacha_automatico_quando_configurado(self):
        ServicoFluxoProtocolo.objects.create(
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            modo=ServicoFluxoProtocolo.MODO_AUTOMATICO,
            ativo=True,
        )
        d = self._demanda_aguardando()
        ok = FluxoProtocoloService().tentar_despacho_automatico_pk(d.pk)
        self.assertTrue(ok)
        d.refresh_from_db()
        self.assertEqual(d.status, "PROTOCOLADO")
        self.assertTrue(d.protocolo_executivo)
        self.assertEqual(d.sinapse_orgao_id, SINAPSE_ORGAO_A)

    def test_despacho_automatico_registra_assinatura_sistema(self):
        from core.models_assinatura_eletronica import AssinaturaEletronica
        from core.services.assinatura_eletronica_service import (
            AssinaturaEletronicaService,
            DECLARACAO_DESPACHO_AUTOMATICO,
        )

        ServicoFluxoProtocolo.objects.create(
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            modo=ServicoFluxoProtocolo.MODO_AUTOMATICO,
            ativo=True,
        )
        d = self._demanda_aguardando()
        FluxoProtocoloService().tentar_despacho_automatico_pk(d.pk)
        d.refresh_from_db()
        assinatura = AssinaturaEletronica.objects.filter(
            demanda=d,
            etapa=AssinaturaEletronica.ETAPA_DESPACHO_INICIAL,
            papel=AssinaturaEletronica.PAPEL_OPERADOR,
        ).first()
        self.assertIsNotNone(assinatura)
        self.assertEqual(assinatura.declaracao, DECLARACAO_DESPACHO_AUTOMATICO)
        self.assertEqual(
            assinatura.usuario.username,
            AssinaturaEletronicaService.USUARIO_SISTEMA_USERNAME,
        )

    def test_tendencia_nunca_despacha_automatico(self):
        ServicoFluxoProtocolo.objects.create(
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            modo=ServicoFluxoProtocolo.MODO_AUTOMATICO,
        )
        d = self._demanda_aguardando(
            origem_vinculo=Demanda.ORIGEM_VINCULO_TENDENCIA,
        )
        self.assertFalse(FluxoProtocoloService().despacho_automatico_habilitado(d))

    def test_auto_protocola_demanda_nova_em_super_os_existente(self):
        from core.models import ClusterExecucao

        ServicoFluxoProtocolo.objects.create(
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            modo=ServicoFluxoProtocolo.MODO_AUTOMATICO,
            ativo=True,
        )
        cluster = ClusterExecucao.objects.create(
            titulo="Super OS teste",
            status="EM_ANDAMENTO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            protocolo_super_os="SUPER-2026-TEST",
        )
        d1 = self._demanda_aguardando(
            protocolo_legislativo="OFICIO-2026-0101",
            cluster=cluster,
        )
        d1.status = "PROTOCOLADO"
        d1.protocolo_executivo = "2026-9001"
        d1.save(update_fields=["status", "protocolo_executivo"])

        d2 = self._demanda_aguardando(protocolo_legislativo="OFICIO-2026-0102", cluster=cluster)
        d3 = self._demanda_aguardando(protocolo_legislativo="OFICIO-2026-0103", cluster=cluster)
        d3.status = "PROTOCOLADO"
        d3.protocolo_executivo = "2026-9002"
        d3.save(update_fields=["status", "protocolo_executivo"])

        n = FluxoProtocoloService().processar_cohorte_servico(SINAPSE_SERVICO_ID)
        self.assertGreaterEqual(n, 1)
        d2.refresh_from_db()
        self.assertEqual(d2.status, "PROTOCOLADO")
        self.assertTrue(d2.protocolo_executivo)
        self.assertEqual(d2.sinapse_orgao_id, SINAPSE_ORGAO_A)


class FluxoProtocoloAPITests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.gestor = Usuario.objects.create_user(
            username="gest_fluxo", password="x", perfil="GESTOR"
        )
        self.protocolo = Usuario.objects.create_user(
            username="prot_fluxo", password="x", perfil="PROTOCOLO"
        )
        self.client.force_authenticate(self.gestor)

    def test_upsert_fluxo_servico(self):
        r = self.client.post(
            "/api/fluxo-servicos/upsert/",
            {
                "sinapse_servico_id": SINAPSE_SERVICO_ID,
                "modo": ServicoFluxoProtocolo.MODO_AUTOMATICO,
                "ativo": True,
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["modo"], ServicoFluxoProtocolo.MODO_AUTOMATICO)
        self.assertTrue(r.data["despacho_automatico"])

    def test_protocolo_sem_acesso_upsert_fluxo(self):
        self.client.force_authenticate(self.protocolo)
        r = self.client.post(
            "/api/fluxo-servicos/upsert/",
            {
                "sinapse_servico_id": SINAPSE_SERVICO_ID,
                "modo": ServicoFluxoProtocolo.MODO_AUTOMATICO,
                "ativo": True,
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_nao_notifica_protocolo_quando_automatico(self):
        ServicoFluxoProtocolo.objects.create(
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            modo=ServicoFluxoProtocolo.MODO_AUTOMATICO,
        )
        Usuario.objects.create_user(username="prot2", password="x", perfil="PROTOCOLO")
        vereador = Usuario.objects.create_user(
            username="ver_not", password="x", perfil="VEREADOR"
        )
        d = Demanda.objects.create(
            titulo="Sem notif",
            descricao="x",
            autor=vereador,
            status="RASCUNHO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
        )
        antes = Notificacao.objects.count()
        d.status = "AGUARDANDO_PROTOCOLO"
        d.protocolo_legislativo = "OFICIO-2026-0100"
        d.save()
        self.assertEqual(Notificacao.objects.count(), antes)
