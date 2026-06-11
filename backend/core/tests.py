import json
from datetime import timedelta
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Demanda, Notificacao, Usuario

SINAPSE_SERVICO_ID = 1001
SINAPSE_ORGAO_A = 2001
SINAPSE_ORGAO_B = 2002


def payload_envio_oficial(demanda):
    from core.services.assinatura_eletronica_service import (
        DECLARACAO_ENVIO,
        AssinaturaEletronicaService,
    )

    preview = AssinaturaEletronicaService().preparar_preview_envio(demanda)
    return {
        "declaracao": DECLARACAO_ENVIO,
        "hash_documento": preview["hash_documento"],
    }


class SinapseCatalogTestMixin:
    """Mock do catálogo Sinapse para testes sem DB sinapse."""

    def setUp(self):
        self._catalog_patch = patch.multiple(
            "integrations.sinapse_catalog",
            servico_existe=lambda sid: True,
            orgao_existe=lambda oid: int(oid) in (SINAPSE_ORGAO_A, SINAPSE_ORGAO_B),
            get_orgao_id_for_servico=lambda sid: SINAPSE_ORGAO_A,
            prazo_dias=lambda sid: 10,
            get_orgao_nome=lambda oid: (
                {
                    SINAPSE_ORGAO_A: "Secretaria A",
                    SINAPSE_ORGAO_B: "Secretaria B",
                }.get(int(oid), f"Orgao {oid}")
                if oid is not None
                else None
            ),
            get_servico=lambda sid: type(
                "CatalogServicoFake",
                (),
                {"titulo": "Serviço Teste", "id_orgao_id": SINAPSE_ORGAO_A, "prazo": "10 dias"},
            )(),
            servico_to_dict=lambda s: {
                "id": SINAPSE_SERVICO_ID,
                "nome": "Serviço Teste",
                "tipo": "SERVIÇO",
                "prazo": 10,
                "secretaria_responsavel": {"id": SINAPSE_ORGAO_A, "nome": "Secretaria A"},
            }
            if s
            else None,
            orgao_to_dict=lambda o: {"id": o.id, "nome": o.nome} if o else None,
            get_orgao=lambda oid: type(
                "CatalogOrgaoFake",
                (),
                {
                    "id": int(oid),
                    "nome": {
                        SINAPSE_ORGAO_A: "Secretaria A",
                        SINAPSE_ORGAO_B: "Secretaria B",
                    }.get(int(oid), "Orgao"),
                },
            )()
            if oid
            else None,
            list_servicos_api=lambda **kwargs: [],
            list_orgaos_api=lambda **kwargs: [],
            resolver_servico_por_titulo=lambda titulo: SINAPSE_SERVICO_ID,
            servico_requer_localizacao=lambda sid: True,
        )
        self._catalog_patch.start()
        super().setUp()

    def tearDown(self):
        super().tearDown()
        self._catalog_patch.stop()
from core.services.ai_kernel_client import AIKernelClient, AIKernelClientError
from integrations.models import SinapseServiceSync, SinapseServicoMap
from integrations.services.sinapse_sync_service import SinapseSyncService
from integrations.sinapse_client import SinapseClientError


class DemandasFluxoTests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.sinapse_orgao_id = SINAPSE_ORGAO_A
        self.vereador = Usuario.objects.create_user(
            username="vereador1",
            password="senhaforte123",
            perfil="VEREADOR",
        )
        self.protocolo = Usuario.objects.create_user(
            username="protocolo1",
            password="senhaforte123",
            perfil="PROTOCOLO",
        )
        self.demanda = Demanda.objects.create(
            titulo="Buraco na via principal",
            descricao="Solicitação de reparo urgente",
            autor=self.vereador,
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            status="RASCUNHO",
        )

    def test_enviar_demanda_gera_protocolo_legislativo(self):
        self.client.force_authenticate(user=self.vereador)
        url = reverse("demanda-enviar", kwargs={"pk": self.demanda.pk})

        response = self.client.post(url, payload_envio_oficial(self.demanda), format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.demanda.refresh_from_db()
        self.assertEqual(self.demanda.status, "AGUARDANDO_PROTOCOLO")
        self.assertIsNotNone(self.demanda.protocolo_legislativo)

    def test_enviar_demanda_trilha_tendencia_sem_servico_sinapse(self):
        from core.models import Tendencia

        tendencia = Tendencia.objects.create(
            slug="iluminacao-praca",
            titulo="Iluminação em praça pública",
            sinapse_orgao_id=self.sinapse_orgao_id,
        )
        demanda_tend = Demanda.objects.create(
            titulo="Praça sem luz",
            descricao="Solicitação fora da carta",
            autor=self.vereador,
            status="RASCUNHO",
            origem_vinculo=Demanda.ORIGEM_VINCULO_TENDENCIA,
            tendencia=tendencia,
            sinapse_servico_id=None,
        )

        self.client.force_authenticate(user=self.vereador)
        url = reverse("demanda-enviar", kwargs={"pk": demanda_tend.pk})
        response = self.client.post(url, payload_envio_oficial(demanda_tend), format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        demanda_tend.refresh_from_db()
        self.assertEqual(demanda_tend.status, "AGUARDANDO_PROTOCOLO")
        self.assertIsNotNone(demanda_tend.protocolo_legislativo)
        self.assertIsNone(demanda_tend.sinapse_servico_id)
        self.assertEqual(demanda_tend.tendencia_id, tendencia.id)
        self.assertEqual(demanda_tend.sinapse_orgao_id, self.sinapse_orgao_id)

    def test_despachar_demanda_define_data_inicio_prazo(self):
        self.demanda.status = "AGUARDANDO_PROTOCOLO"
        self.demanda.save(update_fields=["status"])

        self.client.force_authenticate(user=self.protocolo)
        url = reverse("demanda-despachar", kwargs={"pk": self.demanda.pk})
        payload = {
            "secretaria_id": self.sinapse_orgao_id,
        }

        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.demanda.refresh_from_db()
        self.assertEqual(self.demanda.status, "PROTOCOLADO")
        self.assertIsNotNone(self.demanda.protocolo_executivo)
        self.assertIsNotNone(self.demanda.data_inicio_prazo)
        self.assertEqual(self.demanda.sinapse_orgao_id, self.sinapse_orgao_id)


class RelatoriosKpiTests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.gestor = Usuario.objects.create_user(
            username="gestor1",
            password="senhaforte123",
            perfil="GESTOR",
        )
        vereador = Usuario.objects.create_user(
            username="vereador2",
            password="senhaforte123",
            perfil="VEREADOR",
        )

        demanda_atrasada = Demanda.objects.create(
            titulo="Demanda atrasada",
            descricao="Aguardando atendimento",
            autor=vereador,
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            status="PROTOCOLADO",
        )
        demanda_em_dia = Demanda.objects.create(
            titulo="Demanda em dia",
            descricao="Recente",
            autor=vereador,
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            status="PROTOCOLADO",
        )
        Demanda.objects.create(
            titulo="Demanda finalizada",
            descricao="Concluída",
            autor=vereador,
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            status="FINALIZADO",
            data_inicio_prazo=timezone.now() - timedelta(days=20),
        )
        Demanda.objects.filter(pk=demanda_atrasada.pk).update(data_inicio_prazo=timezone.now() - timedelta(days=10))
        Demanda.objects.filter(pk=demanda_em_dia.pk).update(data_inicio_prazo=timezone.now() - timedelta(days=1))

    def test_report_kpis_retorna_contagens_consistentes(self):
        self.client.force_authenticate(user=self.gestor)
        url = reverse("report-kpis")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_demandas"], 3)
        self.assertEqual(response.data["demandas_abertas"], 2)
        self.assertEqual(response.data["demandas_concluidas"], 1)
        self.assertEqual(response.data["demandas_atrasadas"], 1)


class EndpointsContratoTests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.sinapse_orgao_id = SINAPSE_ORGAO_A
        self.vereador = Usuario.objects.create_user(
            username="vereador_api",
            password="senhaforte123",
            perfil="VEREADOR",
        )
        self.protocolo = Usuario.objects.create_user(
            username="protocolo_api",
            password="senhaforte123",
            perfil="PROTOCOLO",
        )
        self.demanda = Demanda.objects.create(
            titulo="Demanda API",
            descricao="Fluxo de contrato de endpoint",
            autor=self.vereador,
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            status="RASCUNHO",
        )

    def test_token_endpoint_retorna_tokens(self):
        url = reverse("token_obtain_pair")
        response = self.client.post(
            url,
            {"username": "vereador_api", "password": "senhaforte123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_notificacoes_endpoint_exige_autenticacao(self):
        url = reverse("notificacao-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_notificacoes_do_usuario_logado(self):
        Notificacao.objects.create(
            destinatario=self.vereador,
            mensagem="Notificação do vereador",
            tipo="ATUALIZACAO",
        )
        Notificacao.objects.create(
            destinatario=self.protocolo,
            mensagem="Notificação do protocolo",
            tipo="ATUALIZACAO",
        )
        self.client.force_authenticate(user=self.vereador)
        url = reverse("notificacao-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        dados = response.data["results"] if isinstance(response.data, dict) else response.data
        self.assertEqual(len(dados), 1)
        self.assertEqual(dados[0]["mensagem"], "Notificação do vereador")

    def test_despachar_exige_perfil_protocolo(self):
        self.demanda.status = "AGUARDANDO_PROTOCOLO"
        self.demanda.save(update_fields=["status"])
        self.client.force_authenticate(user=self.vereador)
        url = reverse("demanda-despachar", kwargs={"pk": self.demanda.pk})
        response = self.client.post(url, {"secretaria_id": self.sinapse_orgao_id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class HomologacaoSmokePorPerfilTests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.sinapse_orgao_a = SINAPSE_ORGAO_A
        self.sinapse_orgao_b = SINAPSE_ORGAO_B
        self.vereador = Usuario.objects.create_user(
            username="vereador_smoke",
            password="senhaforte123",
            perfil="VEREADOR",
        )
        self.protocolo = Usuario.objects.create_user(
            username="protocolo_smoke",
            password="senhaforte123",
            perfil="PROTOCOLO",
        )
        self.gestor = Usuario.objects.create_user(
            username="gestor_smoke",
            password="senhaforte123",
            perfil="GESTOR",
        )
        self.secretaria_user = Usuario.objects.create_user(
            username="secretaria_smoke",
            password="senhaforte123",
            perfil="SECRETARIA",
            sinapse_orgao_id=self.sinapse_orgao_a,
        )
        self.demanda = Demanda.objects.create(
            titulo="Demanda Smoke",
            descricao="Validação por perfil",
            autor=self.vereador,
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            status="RASCUNHO",
        )

    def test_smoke_vereador_fluxo_basico(self):
        self.client.force_authenticate(user=self.vereador)
        demandas_url = reverse("demanda-list")
        list_response = self.client.get(demandas_url)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)

        enviar_url = reverse("demanda-enviar", kwargs={"pk": self.demanda.pk})
        enviar_response = self.client.post(
            enviar_url, payload_envio_oficial(self.demanda), format="json"
        )
        self.assertEqual(enviar_response.status_code, status.HTTP_200_OK)
        self.demanda.refresh_from_db()
        self.assertEqual(self.demanda.status, "AGUARDANDO_PROTOCOLO")

    def test_smoke_protocolo_despacho(self):
        self.demanda.status = "AGUARDANDO_PROTOCOLO"
        self.demanda.save(update_fields=["status"])
        self.client.force_authenticate(user=self.protocolo)
        url = reverse("demanda-despachar", kwargs={"pk": self.demanda.pk})
        response = self.client.post(
            url,
            {"secretaria_id": self.sinapse_orgao_a},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.demanda.refresh_from_db()
        self.assertEqual(self.demanda.status, "PROTOCOLADO")

    def test_smoke_secretaria_solicita_transferencia(self):
        self.demanda.status = "PROTOCOLADO"
        self.demanda.sinapse_orgao_id = self.sinapse_orgao_a
        self.demanda.data_inicio_prazo = timezone.now() - timedelta(days=1)
        self.demanda.save(update_fields=["status", "sinapse_orgao_id", "data_inicio_prazo"])
        self.client.force_authenticate(user=self.secretaria_user)
        url = reverse("demanda-solicitar-transferencia", kwargs={"pk": self.demanda.pk})
        response = self.client.post(url, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.demanda.refresh_from_db()
        self.assertEqual(self.demanda.status, "AGUARDANDO_TRANSFERENCIA")

    def test_smoke_gestor_consulta_kpis_e_dashboard(self):
        self.demanda.status = "PROTOCOLADO"
        self.demanda.sinapse_orgao_id = self.sinapse_orgao_a
        self.demanda.data_inicio_prazo = timezone.now() - timedelta(days=10)
        self.demanda.save(update_fields=["status", "sinapse_orgao_id", "data_inicio_prazo"])
        self.client.force_authenticate(user=self.gestor)

        kpis_response = self.client.get(reverse("report-kpis"))
        self.assertEqual(kpis_response.status_code, status.HTTP_200_OK)
        self.assertIn("total_demandas", kpis_response.data)

        dashboard_response = self.client.get(reverse("dashboard-stats"))
        self.assertEqual(dashboard_response.status_code, status.HTTP_200_OK)
        self.assertIn("kpis", dashboard_response.data)


class AIKernelClientContractTests(APITestCase):
    @patch("core.services.ai_kernel_client.requests.get")
    def test_health_success(self, mock_get):
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {"status": "online"}
        mock_get.return_value = mock_response

        client = AIKernelClient()
        data = client.health()
        self.assertEqual(data["status"], "online")

    @patch("core.services.ai_kernel_client.requests.post")
    def test_embeddings_success(self, mock_post):
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {"embeddings": [[0.1, 0.2]]}
        mock_post.return_value = mock_response

        client = AIKernelClient()
        embeddings = client.embeddings(["teste"])
        self.assertEqual(len(embeddings), 1)
        self.assertEqual(embeddings[0][0], 0.1)

    @patch("core.services.ai_kernel_client.requests.post")
    def test_timeout_error_raises_custom_exception(self, mock_post):
        import requests

        mock_post.side_effect = requests.Timeout("timeout")
        client = AIKernelClient()
        with self.assertRaises(AIKernelClientError):
            client.chat("sistema", "usuario")

    @patch("core.services.ai_kernel_client.requests.post")
    def test_http_500_raises_custom_exception(self, mock_post):
        mock_response = Mock(status_code=500, text="internal error")
        mock_post.return_value = mock_response
        client = AIKernelClient()
        with self.assertRaises(AIKernelClientError):
            client.embeddings(["texto"])

    @patch("core.services.ai_kernel_client.requests.post")
    def test_safe_fallback_returns_empty_values(self, mock_post):
        import requests

        mock_post.side_effect = requests.ConnectionError("offline")
        client = AIKernelClient()

        self.assertEqual(client.embeddings_safe(["x"]), [])
        self.assertEqual(client.similarity_safe("x", ["a", "b"]), [])
        self.assertEqual(client.chat_safe("sys", "usr"), "")


class SinapseSyncContractTests(APITestCase):
    @patch("integrations.services.sinapse_sync_service.SinapseClient")
    def test_map_service_record_payload_completo(self, _mock_client):
        raw = {
            "id": 101,
            "titulo": "Troca de lampadas",
            "departamento": "Iluminacao Publica",
            "prazo": "<p>15 dias.</p>",
            "documentos_necessarios": "<ul><li>RG</li><li>CPF</li></ul>",
            "telefone": '["156", "(11) 99999-0000"]',
            "updated_at": "2026-03-13T10:00:00-03:00",
            "ativo": True,
        }
        service = SinapseSyncService(table_name="public.catalog_servico")
        mapped = service.map_service_record(raw)

        self.assertEqual(mapped["service_id"], 101)
        self.assertEqual(mapped["service_name"], "Troca de lampadas")
        self.assertEqual(mapped["provider_secretariat"], "Iluminacao Publica")
        self.assertEqual(mapped["sla_days"], 15)
        self.assertEqual(mapped["required_documents"], ["RG CPF"])
        self.assertEqual(mapped["channels"], ["156", "(11) 99999-0000"])
        self.assertTrue(mapped["active"])

    @patch("integrations.services.sinapse_sync_service.SinapseClient")
    def test_map_service_record_payload_parcial(self, _mock_client):
        raw = {
            "codigo": "SVC-77",
            "nome": "Servico parcial",
            "orgao": "Secretaria Parcial",
            "prazo_dias": 8,
            "documentos": None,
            "canais": "",
            "data_atualizacao": "2026-04-01T12:00:00-03:00",
        }
        service = SinapseSyncService(table_name="public.catalog_servico")
        mapped = service.map_service_record(raw)

        self.assertEqual(mapped["service_id"], "SVC-77")
        self.assertEqual(mapped["service_name"], "Servico parcial")
        self.assertEqual(mapped["provider_secretariat"], "Secretaria Parcial")
        self.assertEqual(mapped["sla_days"], 8)
        self.assertEqual(mapped["required_documents"], [])
        self.assertEqual(mapped["channels"], [])

    @patch("integrations.services.sinapse_sync_service.SinapseClient")
    def test_map_service_record_payload_inconsistente(self, _mock_client):
        raw = {
            "id": 909,
            "titulo": "",
            "departamento": "",
            "prazo": "<p>sem prazo definido</p>",
            "documentos_necessarios": "  ",
            "telefone": None,
        }
        service = SinapseSyncService(table_name="public.catalog_servico")
        mapped = service.map_service_record(raw)

        self.assertEqual(mapped["service_id"], 909)
        self.assertEqual(mapped["service_name"], "")
        self.assertIsNone(mapped["provider_secretariat"])
        self.assertIsNone(mapped["sla_days"])
        self.assertEqual(mapped["required_documents"], [])
        self.assertEqual(mapped["channels"], [])

    @patch("integrations.sinapse_catalog.servico_existe", return_value=True)
    @patch("integrations.services.sinapse_sync_service.SinapseClient")
    def test_full_sync_idempotente(self, mock_client_cls, _mock_catalog):
        rows = [
            {
                "id": 1,
                "titulo": "Servico A",
                "departamento": "Secretaria A",
                "prazo": "10 dias",
                "updated_at": "2026-04-10T09:00:00-03:00",
            },
            {
                "id": 2,
                "titulo": "Servico B",
                "departamento": "Secretaria B",
                "prazo": "2 meses",
                "updated_at": "2026-04-10T09:01:00-03:00",
            },
        ]
        mock_client = Mock()
        mock_client.fetch_services.side_effect = [rows, []]
        mock_client_cls.return_value = mock_client

        service = SinapseSyncService(table_name="public.catalog_servico")
        first = service.full_sync(batch_size=100)
        self.assertEqual(first["created"], 2)
        self.assertEqual(first["updated"], 0)
        self.assertEqual(SinapseServiceSync.objects.count(), 2)

        mock_client.fetch_services.side_effect = [rows, []]
        second = service.full_sync(batch_size=100)
        self.assertEqual(second["created"], 0)
        self.assertEqual(second["updated"], 0)
        self.assertEqual(second["unchanged"], 2)
        self.assertEqual(SinapseServiceSync.objects.count(), 2)

    @patch("integrations.services.sinapse_sync_service.SinapseClient")
    def test_full_sync_erro_conectividade_propaga_excecao(self, mock_client_cls):
        mock_client = Mock()
        mock_client.fetch_services.side_effect = SinapseClientError("fonte indisponivel")
        mock_client_cls.return_value = mock_client

        service = SinapseSyncService(table_name="public.catalog_servico")
        with self.assertRaises(SinapseClientError):
            service.full_sync(batch_size=100)

    @patch("integrations.services.sinapse_sync_service.SinapseClient")
    def test_list_unmatched_retorna_pendencias(self, _mock_client):
        SinapseServiceSync.objects.create(
            sinapse_service_id="S-1",
            source_table="public.catalog_servico",
            version="2026-04-01T10:00:00-03:00",
            hash_payload="abc123",
            payload={"service_name": "Servico X", "provider_secretariat": "Secretaria X"},
            status_sync="SYNCED",
        )
        SinapseServicoMap.objects.create(
            sinapse_service_id="S-1",
            match_status="UNMATCHED",
            match_rule="none",
            confidence=0,
        )
        service = SinapseSyncService(table_name="public.catalog_servico")
        data = service.list_unmatched(limit=10)

        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["sinapse_service_id"], "S-1")
        self.assertEqual(data[0]["service_name"], "Servico X")
        self.assertEqual(data[0]["match_status"], "UNMATCHED")

    @patch("integrations.sinapse_catalog.servico_existe", return_value=True)
    @patch("integrations.services.sinapse_sync_service.SinapseClient")
    def test_bind_manual_mapping_registra_auditoria(self, _mock_client, _mock_catalog):
        SinapseServicoMap.objects.create(
            sinapse_service_id="S-2",
            match_status="UNMATCHED",
            confidence=0,
        )
        service = SinapseSyncService(table_name="public.catalog_servico")
        result = service.bind_manual_mapping(
            sinapse_service_id="S-2",
            servico_local_id=SINAPSE_SERVICO_ID,
            actor="teste-qa",
        )

        self.assertEqual(result["match_status"], "MANUAL")
        self.assertEqual(result["catalog_servico_id"], SINAPSE_SERVICO_ID)
        updated = SinapseServicoMap.objects.get(sinapse_service_id="S-2")
        self.assertEqual(updated.last_manual_actor, "teste-qa")
        self.assertIn("actor=teste-qa", updated.notes or "")

    @patch("integrations.services.sinapse_sync_service.SinapseClient")
    @override_settings(
        SINAPSE_ALERT_UNMATCHED_THRESHOLD=1,
        SINAPSE_ALERT_DIVERGENT_THRESHOLD=1,
    )
    def test_sync_health_report_gera_alerta_por_limiar(self, _mock_client):
        SinapseServiceSync.objects.create(
            sinapse_service_id="S-3",
            source_table="public.catalog_servico",
            version="2026-04-01T10:00:00-03:00",
            hash_payload="hash-s3",
            payload={"service_name": "Servico Y"},
            status_sync="DIVERGENT",
        )
        SinapseServicoMap.objects.create(
            sinapse_service_id="S-3",
            match_status="UNMATCHED",
            confidence=0,
        )
        service = SinapseSyncService(table_name="public.catalog_servico")
        report = service.sync_health_report()

        self.assertEqual(report["alert_level"], "ALERT")
        self.assertGreaterEqual(report["summary"]["unmatched_mappings"], 1)
        self.assertGreaterEqual(report["summary"]["divergent_sync_records"], 1)


class SinapseSprint5ContractTests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.user = Usuario.objects.create_user(
            username="gestor_sprint5",
            password="senhaforte123",
            perfil="GESTOR",
        )
        self.vereador = Usuario.objects.create_user(
            username="vereador_sprint5",
            password="senhaforte123",
            perfil="VEREADOR",
        )
        SinapseServiceSync.objects.create(
            sinapse_service_id="SP5-1",
            source_table="public.catalog_servico",
            version="2026-04-28T10:00:00-03:00",
            hash_payload="hash-sp5-1",
            payload={"service_name": "Servico Sprint5 Externo", "provider_secretariat": "Secretaria Sprint5"},
            status_sync="SYNCED",
        )
        SinapseServicoMap.objects.create(
            sinapse_service_id="SP5-1",
            match_status="UNMATCHED",
            confidence=0,
        )
        self.client.force_authenticate(user=self.user)

    def test_sync_health_endpoint_retorna_resumo(self):
        response = self.client.get("/api/integrations/sinapse/sync-health/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("alert_level", response.data)
        self.assertIn("summary", response.data)

    def test_unmatched_endpoint_retorna_fila(self):
        response = self.client.get("/api/integrations/sinapse/unmatched/?limit=10")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["sinapse_service_id"], "SP5-1")

    def test_unmatched_endpoint_aplica_filtro_search(self):
        response = self.client.get("/api/integrations/sinapse/unmatched/?search=sprint5")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["provider_secretariat"], "Secretaria Sprint5")

    @patch("integrations.sinapse_catalog.servico_existe", return_value=True)
    def test_bind_manual_endpoint_vincula_servico(self, _mock_catalog):
        response = self.client.post(
            "/api/integrations/sinapse/bind-manual/",
            {"sinapse_service_id": "SP5-1", "servico_local_id": SINAPSE_SERVICO_ID},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["match_status"], "MANUAL")
        updated = SinapseServicoMap.objects.get(sinapse_service_id="SP5-1")
        self.assertEqual(updated.match_status, "MANUAL")

    @patch("integrations.sinapse_catalog.servico_existe", return_value=True)
    def test_bind_manual_bulk_endpoint_vincula_em_lote(self, _mock_catalog):
        SinapseServiceSync.objects.create(
            sinapse_service_id="SP5-2",
            source_table="public.catalog_servico",
            version="2026-04-28T10:01:00-03:00",
            hash_payload="hash-sp5-2",
            payload={"service_name": "Servico Sprint5 Externo B", "provider_secretariat": "Secretaria Sprint5"},
            status_sync="SYNCED",
        )
        SinapseServicoMap.objects.create(
            sinapse_service_id="SP5-2",
            match_status="UNMATCHED",
            confidence=0,
        )

        response = self.client.post(
            "/api/integrations/sinapse/bind-manual-bulk/",
            {
                "bindings": [
                    {"sinapse_service_id": "SP5-1", "servico_local_id": SINAPSE_SERVICO_ID},
                    {"sinapse_service_id": "SP5-2", "servico_local_id": SINAPSE_SERVICO_ID},
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_bound"], 2)
        self.assertEqual(SinapseServicoMap.objects.filter(match_status="MANUAL").count(), 2)

    def test_unmatched_endpoint_bloqueia_perfil_nao_autorizado(self):
        self.client.force_authenticate(user=self.vereador)
        response = self.client.get("/api/integrations/sinapse/unmatched/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("integrations.management.commands.sync_sinapse_services.send_mail")
    @override_settings(SINAPSE_ALERT_EMAIL_RECIPIENTS=["ops@sgdl.local"])
    def test_sync_health_report_envia_email_em_alerta(self, mock_send_mail):
        SinapseServiceSync.objects.filter(sinapse_service_id="SP5-1").update(status_sync="DIVERGENT")
        with patch(
            "integrations.management.commands.sync_sinapse_services.SinapseSyncService.sync_health_report"
        ) as mock_report:
            mock_report.return_value = {
                "alert_level": "ALERT",
                "reasons": ["Teste alerta"],
                "summary": {"unmatched_mappings": 1, "divergent_sync_records": 1},
                "thresholds": {"unmatched_threshold": 1, "divergent_threshold": 1},
            }
            from django.core.management import call_command

            call_command("sync_sinapse_services", "--sync-health-report", "--notify-alert-email")

        self.assertTrue(mock_send_mail.called)

    @patch("integrations.management.commands.sync_sinapse_services.requests.post")
    @override_settings(SINAPSE_ALERT_WEBHOOK_URL="https://hooks.example.local/sgdl")
    def test_sync_health_report_envia_webhook_em_alerta(self, mock_post):
        mock_response = Mock(status_code=200)
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        with patch(
            "integrations.management.commands.sync_sinapse_services.SinapseSyncService.sync_health_report"
        ) as mock_report:
            mock_report.return_value = {
                "alert_level": "ALERT",
                "reasons": ["Teste webhook"],
                "summary": {"unmatched_mappings": 2, "divergent_sync_records": 1},
                "thresholds": {"unmatched_threshold": 1, "divergent_threshold": 1},
            }
            from django.core.management import call_command

            call_command("sync_sinapse_services", "--sync-health-report", "--notify-alert-webhook")

        self.assertTrue(mock_post.called)


class CopilotoAnexoOficioTests(SinapseCatalogTestMixin, APITestCase):
    """Vínculo de anexos e ofícios por demanda (sem replicar em lote)."""

    def setUp(self):
        super().setUp()
        from core.models import ChatSession, ChatSessaoAnexo
        from core.services.chatbot_service import ChatbotService

        self.ChatSession = ChatSession
        self.ChatSessaoAnexo = ChatSessaoAnexo
        self.ChatbotService = ChatbotService
        self.user = Usuario.objects.create_user(
            username="copiloto_test",
            password="x",
            perfil="ASSESSOR",
        )

    def test_mapa_anexos_nao_replica_em_todas_demandas(self):
        rascunho = [
            {"titulo": "Tapa buraco", "anexos_indices": [0]},
            {"titulo": "Poda", "anexos_indices": []},
        ]
        anexos_fake = [object(), object()]
        mapa = self.ChatbotService._mapa_anexos_por_demanda(
            anexos_fake,
            rascunho,
            [object(), object()],
        )
        self.assertEqual(mapa[0], {0})
        self.assertEqual(mapa[1], set())

    def test_inferencia_texto_segunda_solicitacao(self):
        rascunho = [{"titulo": "Tapa buraco"}, {"titulo": "Poda de árvore"}]
        idx = self.ChatbotService._inferir_indice_demanda_pelo_texto(
            "Segue foto da segunda solicitação", rascunho
        )
        self.assertEqual(idx, 1)

    def test_unica_demanda_recebe_todos_anexos_sem_indices(self):
        mapa = self.ChatbotService._mapa_anexos_por_demanda(
            [object(), object()],
            [{"titulo": "Única"}],
            [object()],
        )
        self.assertEqual(mapa[0], {0, 1})

    @patch("core.services.chatbot_service.GeocodingService")
    @patch("core.services.chatbot_service.sinapse_catalog")
    def test_enriquecer_demandas_para_ui(self, mock_catalog, mock_geo_cls):
        from core.models import ChatSession, ChatSessaoAnexo
        from django.core.files.uploadedfile import SimpleUploadedFile

        mock_catalog.get_servico.return_value = type(
            "S", (), {"titulo": "Tapa buraco", "id_orgao_id": 1}
        )()
        mock_catalog.get_orgao_id_for_servico.return_value = 1
        mock_catalog.get_orgao_nome.return_value = "Obras"
        mock_catalog.servico_existe.return_value = True
        mock_geo_cls.return_value.buscar_coordenadas_com_fonte.return_value = (
            -23.1,
            -46.2,
            "logradouro",
        )

        session = ChatSession.objects.create(
            autor=self.user,
            estado_atual=ChatSession.ESTADO_VALIDACAO_FINAL,
            demandas_rascunho=[
                {
                    "titulo": "Tapa Buraco",
                    "descricao": "Solicitação de tapa buraco",
                    "sinapse_servico_id_sugerido": SINAPSE_SERVICO_ID,
                    "anexos_indices": [0],
                    "endereco": {"bairro": "Centro", "logradouro": "Rua A"},
                }
            ],
        )
        ChatSessaoAnexo.objects.create(
            session=session,
            arquivo=SimpleUploadedFile("foto.jpg", b"x", content_type="image/jpeg"),
            descricao="foto.jpg",
            indice_demanda=0,
        )

        svc = self.ChatbotService()
        out = svc._enriquecer_demandas_para_ui(session, session.demandas_rascunho)
        self.assertEqual(len(out), 1)
        self.assertIsNotNone(out[0]["servico"])
        self.assertEqual(out[0]["servico"]["nome"], "Tapa buraco")
        self.assertTrue(out[0]["servico"]["confirmado"])
        self.assertEqual(out[0]["latitude"], -23.1)
        self.assertEqual(len(out[0]["anexos"]), 1)
        self.assertEqual(out[0]["anexos"][0]["nome"], "foto.jpg")


class GeocodingServiceTests(TestCase):
    """Geocodificação: ViaCEP, variantes de via e ordem de tentativas."""

    def setUp(self):
        from core.services import geocoding_service as geo_mod

        with geo_mod._nominatim_lock:
            geo_mod._geo_result_cache.clear()
            geo_mod._viacep_cache.clear()
            geo_mod._nominatim_backoff_until = 0.0

    @patch("core.services.geocoding_service.GeocodingService._consultar_nominatim")
    @patch("core.services.geocoding_service.GeocodingService._consultar_viacep")
    def test_cache_evita_segunda_chamada_nominatim(self, mock_viacep, mock_nominatim):
        from core.services.geocoding_service import GeocodingService

        mock_viacep.return_value = {
            "logradouro": "Rua Maestro Laurindo José Gonçalves",
            "bairro": "Parque Santana",
            "localidade": "Mogi das Cruzes",
            "uf": "SP",
        }
        mock_nominatim.return_value = (-23.532719, -46.195105)

        svc = GeocodingService()
        args = ("Rua X", "Parque Santana", "08717-180")
        svc.buscar_coordenadas(*args)
        svc.buscar_coordenadas(*args)
        self.assertEqual(mock_nominatim.call_count, 1)

    def test_variantes_logradouro_enxuga_nome_longo(self):
        from core.services.geocoding_service import GeocodingService

        svc = GeocodingService()
        variantes = svc._variantes_logradouro(
            "Rua Maestro Laurindo José Gonçalves"
        )
        self.assertIn("Rua Maestro Laurindo José Gonçalves", variantes)
        self.assertTrue(any("Maestro Laurindo" in v for v in variantes))

    @patch("core.services.geocoding_service.GeocodingService._consultar_nominatim")
    @patch("core.services.geocoding_service.GeocodingService._consultar_viacep")
    def test_buscar_prioriza_via_antes_de_cep_sozinho(self, mock_viacep, mock_nominatim):
        from core.services.geocoding_service import GeocodingService
        mock_viacep.return_value = {
            "logradouro": "Rua Maestro Laurindo José Gonçalves",
            "bairro": "Parque Santana",
            "localidade": "Mogi das Cruzes",
            "uf": "SP",
        }

        chamadas: list[str] = []

        def nominatim_side_effect(query: str):
            chamadas.append(query)
            if "Maestro Laurindo" in query and "08717-180" in query:
                return -23.532719, -46.195105
            if query.startswith("08717-180, Mogi"):
                return -23.531866, -46.192145
            return None, None

        mock_nominatim.side_effect = nominatim_side_effect

        svc = GeocodingService()
        lat, lng, fonte = svc.buscar_coordenadas(
            "ofício na rua suja",
            "Parque Santana",
            "08717-180",
        )
        self.assertAlmostEqual(lat, -23.532719, places=4)
        self.assertAlmostEqual(lng, -46.195105, places=4)
        self.assertEqual(fonte, "viacep_logradouro")
        self.assertTrue(chamadas)
        self.assertIn("Maestro Laurindo", chamadas[0])
        cep_sozinho = [q for q in chamadas if q.startswith("08717-180, Mogi")]
        if cep_sozinho:
            self.assertGreater(chamadas.index(cep_sozinho[0]), 0)

    @patch("core.services.geocoding_service.GeocodingService._consultar_viacep")
    def test_aplicar_endereco_canonico_preserva_cep_da_demanda(self, mock_viacep):
        from core.services.chatbot_service import ChatbotService

        mock_viacep.return_value = None
        item = {
            "titulo": "Tapa buraco",
            "descricao": "Na Rua Maestro Laurindo, Parque Santana, 08717-180",
            "endereco": {"cep": "08717-180"},
        }
        texto_sessao = "Outro pedido no CEP 08765-000 em outro bairro"
        ChatbotService._aplicar_endereco_canonico(
            item,
            ChatbotService._texto_contexto_demanda(item, texto_sessao),
        )
        self.assertEqual(item["endereco"]["cep"], "08717-180")

    def test_extrair_endereco_ignora_texto_de_anexo(self):
        from core.services.chatbot_service import ChatbotService

        ext = ChatbotService._extrair_endereco_canonico(
            "Segue(m) anexo(s) para análise da solicitação."
        )
        self.assertIsNone(ext.get("bairro"))
        self.assertIsNone(ext.get("logradouro"))

    def test_merge_endereco_preserva_bairro_valido(self):
        from core.services.chatbot_service import ChatbotService

        base = {"bairro": "Parque Santana", "cep": "08717-180"}
        update = {
            "bairro": "Segue(m) anexo(s) para análise da solicitação.",
            "logradouro": None,
        }
        merged = ChatbotService._merge_endereco_dicts(base, update)
        self.assertEqual(merged["bairro"], "Parque Santana")
        self.assertEqual(merged["cep"], "08717-180")

    def test_fallback_endereco_nao_polui_com_anexo(self):
        from core.services.chatbot_service import ChatbotService

        svc = ChatbotService()
        parsed = {
            "usuario_forneceu_endereco_real": True,
            "demandas_extraidas": [
                {
                    "titulo": "Tapa buraco",
                    "sinapse_servico_id_sugerido": SINAPSE_SERVICO_ID,
                    "endereco": {
                        "bairro": "Parque Santana",
                        "logradouro": "Rua Maestro Laurindo",
                        "cep": "08717-180",
                    },
                }
            ],
        }
        svc._fallback_endereco_e_resumo(
            parsed, "Segue(m) anexo(s) para análise da solicitação."
        )
        end = parsed["demandas_extraidas"][0]["endereco"]
        self.assertEqual(end.get("bairro"), "Parque Santana")


class CopilotoTriagemSemSegundaGroqTests(TestCase):
    """Triagem Sinapse no backend: uma única chamada Groq por turno."""

    def test_rodada_llm_aplica_triagem_local_sem_segunda_groq(self):
        from core.models import ChatSession
        from core.services.chatbot_service import ChatbotService, _SINAPSE_PREFIX

        svc = ChatbotService()
        historico = [{"role": "user", "content": "tapa buraco na rua X"}]
        parsed_inicial = {
            "usuario_forneceu_endereco_real": True,
            "resposta_agente": "Entendi o pedido de tapa-buraco.",
            "estado_atual": ChatSession.ESTADO_COLETA_DADOS,
            "demandas_extraidas": [
                {
                    "titulo": "Tapa buraco",
                    "descricao": "buraco na via",
                    "texto_para_embedding": "tapa buraco rua X",
                    "endereco": {"logradouro": "Rua X", "bairro": "Centro", "cep": None},
                }
            ],
            "acionar_triagem_sinapse": True,
            "confirmar_criacao_demandas": False,
        }
        marcador = (
            f"{_SINAPSE_PREFIX}: A busca vetorial retornou as opções abaixo. "
            "1) servico_id=80 — Tapa Buraco (Obras)"
        )
        blocos = [
            {
                "indice_demanda": 0,
                "candidatos_sinapse": [
                    {
                        "servico_id": 80,
                        "titulo": "Tapa Buraco",
                        "orgao": "Obras",
                        "score": 0.91,
                        "servico_local_id_mapeado": 80,
                    },
                    {
                        "servico_id": 15,
                        "titulo": "Iluminação",
                        "orgao": "Iluminação",
                        "score": 0.4,
                        "servico_local_id_mapeado": 15,
                    },
                ],
            }
        ]

        with patch.object(svc, "_chamar_groq_json", return_value=parsed_inicial) as mock_groq:
            with patch.object(
                svc,
                "_montar_injecao_sinapse",
                return_value=(marcador, blocos[0]["candidatos_sinapse"], blocos),
            ):
                parsed, historico_out = svc._rodada_llm_com_triagem(historico)

        self.assertEqual(mock_groq.call_count, 1)
        self.assertFalse(parsed.get("acionar_triagem_sinapse"))
        self.assertEqual(parsed.get("estado_atual"), ChatSession.ESTADO_COLETA_DADOS)
        cands = parsed["demandas_extraidas"][0].get("candidatos_sinapse")
        self.assertEqual(len(cands), 2)
        ra = (parsed.get("resposta_agente") or "").lower()
        self.assertIn("painel", ra)
        self.assertNotIn("similaridade", ra)
        system_msgs = [
            m["content"]
            for m in historico_out
            if isinstance(m, dict) and m.get("role") == "system"
        ]
        self.assertTrue(any(s.startswith(_SINAPSE_PREFIX) for s in system_msgs))


class CopilotoAnexoSemGroqTests(SinapseCatalogTestMixin, APITestCase):
    """Envio de anexos / continuar sem anexos não chama Groq."""

    def setUp(self):
        super().setUp()
        from core.models import ChatSession
        from core.services.chatbot_service import ChatbotService

        self.ChatSession = ChatSession
        self.svc = ChatbotService()
        self.user = Usuario.objects.create_user(
            username="copiloto_anexo_skip",
            password="x",
            perfil="ASSESSOR",
        )
        self.session = ChatSession.objects.create(
            autor=self.user,
            estado_atual=ChatSession.ESTADO_VALIDACAO_FINAL,
            demandas_rascunho=[
                {
                    "titulo": "Tapa buraco",
                    "sinapse_servico_id_sugerido": SINAPSE_SERVICO_ID,
                    "endereco": {"bairro": "Centro", "logradouro": "Rua A"},
                    "endereco_informado_usuario": True,
                }
            ],
            historico_mensagens=[],
        )

    @patch("core.services.chatbot_service.ChatbotService._rodada_llm_com_triagem")
    def test_interagir_com_anexo_nao_chama_groq(self, mock_rodada):
        from django.core.files.uploadedfile import SimpleUploadedFile

        f = SimpleUploadedFile("foto.jpg", b"jpeg", content_type="image/jpeg")
        with patch.object(self.svc, "api_key", "test-key"):
            out = self.svc.interagir(
                usuario=self.user,
                session_id=str(self.session.id),
                mensagem="",
                anexos_upload=[f],
                anexo_demanda_indices=[0],
            )
        mock_rodada.assert_not_called()
        self.assertIn("arquivo", (out.get("resposta_agente") or "").lower())
        self.assertEqual(out.get("estado_atual"), self.ChatSession.ESTADO_VALIDACAO_FINAL)

    @patch("core.services.chatbot_service.ChatbotService._rodada_llm_com_triagem")
    def test_interagir_continuar_sem_anexos_nao_chama_groq(self, mock_rodada):
        with patch.object(self.svc, "api_key", "test-key"):
            out = self.svc.interagir(
                usuario=self.user,
                session_id=str(self.session.id),
                mensagem="continuar sem anexos",
            )
        mock_rodada.assert_not_called()
        self.assertIn("anexo", (out.get("resposta_agente") or "").lower())

    def test_mensagem_ui_anexo_detectada(self):
        from core.services.chatbot_service import ChatbotService

        self.assertTrue(
            ChatbotService._mensagem_eh_somente_anexo("📎 2 anexos enviados")
        )
        self.assertTrue(
            ChatbotService._mensagem_eh_somente_anexo(
                "Segue(m) anexo(s) para análise da solicitação."
            )
        )
        self.assertTrue(
            ChatbotService()._turno_pula_llm_groq("continuar sem anexos", [])
        )
        self.assertTrue(
            ChatbotService()._turno_pula_llm_groq("continuar sem local", [])
        )


class CopilotoEnderecoSanitizacaoTests(TestCase):
    def test_logradouro_frase_pedido_invalido(self):
        from core.services.chatbot_service import ChatbotService

        frase = (
            "solicito uso de espaço no parque centenário para ações sociais "
            "no dia 10 de agosto de 2026"
        )
        self.assertFalse(
            ChatbotService._valor_campo_endereco_valido("logradouro", frase)
        )

    def test_extrair_parque_centenario(self):
        from core.services.chatbot_service import ChatbotService

        nome = ChatbotService._extrair_nome_parque(
            "reserva no Parque Centenário para evento no dia 10"
        )
        self.assertEqual(nome, "Parque Centenário")

    def test_endereco_real_rejeita_frase_como_logradouro(self):
        from core.services.chatbot_service import ChatbotService

        item = {
            "endereco": {
                "logradouro": (
                    "solicito uso de espaço no parque centenário para ações sociais"
                ),
                "bairro": None,
            }
        }
        self.assertFalse(ChatbotService._endereco_real_do_usuario(item))

    def test_bairro_trecho_descricao_invalido(self):
        from core.services.chatbot_service import ChatbotService

        self.assertFalse(
            ChatbotService._valor_campo_endereco_valido(
                "bairro", "Transporte para apresentação e competição"
            )
        )
        ext = ChatbotService._extrair_endereco_canonico(
            "Transporte para apresentação e competição, evento no centro"
        )
        self.assertIsNone(ext.get("bairro"))

    def test_bairro_explicito_valido(self):
        from core.services.chatbot_service import ChatbotService

        ext = ChatbotService._extrair_endereco_livre(
            "Rua das Flores, 100, bairro Centro, CEP 08717-180"
        )
        self.assertEqual(ext.get("bairro"), "Centro")

    def test_sanitizar_remove_bairro_sem_endereco_informado(self):
        from core.services.chatbot_service import ChatbotService

        item = {
            "titulo": "Transporte para apresentação",
            "descricao": "competição escolar",
            "endereco": {
                "bairro": "Transporte para apresentação e competição",
                "logradouro": None,
            },
        }
        ChatbotService._sanitizar_endereco_demanda(item)
        self.assertIsNone(item["endereco"]["bairro"])
        self.assertIsNone(item["endereco"]["logradouro"])

    def test_sanitizar_remove_logradouro_lixo(self):
        from core.services.chatbot_service import ChatbotService

        item = {
            "titulo": "Uso do Parque Centenário",
            "descricao": "ações sociais no parque centenário",
            "endereco": {
                "logradouro": (
                    "solicito uso de espaço no parque centenário para ações sociais"
                ),
            },
        }
        ChatbotService._sanitizar_endereco_demanda(item)
        self.assertIsNone(item["endereco"]["logradouro"])

    @patch("core.services.chatbot_service.sinapse_catalog.servico_existe", return_value=True)
    def test_planejar_pede_endereco_apos_servico_mesmo_com_parque_no_titulo(
        self, _mock_existe
    ):
        from types import SimpleNamespace

        from core.models import ChatSession
        from core.services.chatbot_service import ChatbotService

        rascunho = [
            {
                "titulo": "Uso do Parque Centenário",
                "descricao": "ações sociais",
                "sinapse_servico_id_sugerido": 1040,
                "servico_local_id": 1040,
                "endereco": {
                    "logradouro": (
                        "solicito uso de espaço no parque centenário para ações sociais"
                    ),
                },
            }
        ]
        session = SimpleNamespace(
            estado_atual=ChatSession.ESTADO_COLETA_DADOS,
            demandas_rascunho=rascunho,
            save=lambda *a, **k: None,
        )
        svc = ChatbotService()
        plano = svc._planejar_passo_fluxo(session, list(rascunho))
        self.assertEqual(plano["estado_atual"], ChatSession.ESTADO_COLETA_ENDERECO)
        self.assertIn("local", (plano.get("resposta_agente") or "").lower())

    def test_item_requer_localizacao_reserva_parque(self):
        from core.services.chatbot_service import ChatbotService

        self.assertTrue(
            ChatbotService._item_requer_localizacao(
                {
                    "titulo": "Uso do Parque Centenário",
                    "servico": {"nome": "Reserva de espaços e Eventos no Parque Centenário"},
                }
            )
        )

    def test_pos_triagem_nao_repete_lista_numerada_no_chat(self):
        from core.services.chatbot_service import ChatbotService

        parsed = {
            "resposta_agente": "Entendi: Transporte para apresentação.",
            "demandas_extraidas": [
                {
                    "titulo": "Transporte para apresentação",
                    "candidatos_sinapse": [
                        {"servico_id": 1, "titulo": "Linhas", "orgao": "Mobilidade", "score": 0.79},
                        {"servico_id": 2, "titulo": "Alteração", "orgao": "Mobilidade", "score": 0.78},
                    ],
                }
            ],
        }
        blocos = [
            {
                "indice_demanda": 0,
                "candidatos_sinapse": parsed["demandas_extraidas"][0]["candidatos_sinapse"],
            }
        ]
        ChatbotService()._montar_resposta_pos_triagem_sinapse(parsed, blocos, [])
        ra = (parsed.get("resposta_agente") or "").lower()
        self.assertNotIn("similaridade", ra)
        self.assertNotIn("1)", parsed["resposta_agente"])
        self.assertIn("painel", ra)

    def test_normalizar_comando_remove_aspas(self):
        from core.services.chatbot_service import ChatbotService

        self.assertEqual(
            ChatbotService._normalizar_comando_usuario('"continuar sem local"'),
            "continuar sem local",
        )

    @patch("core.services.chatbot_service.ChatbotService._rodada_llm_com_triagem")
    @patch("core.services.chatbot_service.sinapse_catalog.get_servico", return_value=None)
    @patch("core.services.chatbot_service.sinapse_catalog.servico_existe", return_value=True)
    def test_interagir_continuar_sem_local_avanca_para_anexos(
        self, _mock_existe, _mock_get, mock_rodada
    ):
        from core.models import ChatSession
        from core.services.chatbot_service import ChatbotService

        user = Usuario.objects.create_user(
            username="copiloto_sem_local",
            password="x",
            perfil="ASSESSOR",
        )
        session = ChatSession.objects.create(
            autor=user,
            estado_atual=ChatSession.ESTADO_COLETA_ENDERECO,
            demandas_rascunho=[
                {
                    "titulo": "Uso do Parque Centenário",
                    "sinapse_servico_id_sugerido": 1040,
                    "servico_local_id": 1040,
                }
            ],
            historico_mensagens=[],
        )
        svc = ChatbotService()
        with patch.object(svc, "api_key", "test-key"):
            out = svc.interagir(
                usuario=user,
                session_id=str(session.id),
                mensagem='"continuar sem local"',
            )
        mock_rodada.assert_not_called()
        self.assertEqual(out["estado_atual"], ChatSession.ESTADO_VALIDACAO_FINAL)
        self.assertIn("anexo", (out.get("resposta_agente") or "").lower())
        session.refresh_from_db()
        self.assertTrue(
            (session.demandas_rascunho or [{}])[0].get("endereco_opcional_dispensado")
        )


class CopilotoFaqEnriquecimentoLlmTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command

        call_command("seed_copiloto_faq")

    def test_parse_resposta_groq(self):
        from core.services.copiloto_faq_enriquecimento_llm import (
            CopilotoFaqEnriquecimentoLlmService,
        )

        data = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "observacoes": "ok",
                                "novas_entradas": [],
                                "atualizacoes": [],
                            }
                        )
                    }
                }
            ]
        }
        parsed = CopilotoFaqEnriquecimentoLlmService._parse_content(data)
        self.assertEqual(parsed.get("observacoes"), "ok")

    def test_aplicar_nova_entrada_mock_groq(self):
        from unittest.mock import patch

        from core.models_copiloto_faq import CopilotoFaqOrientacao
        from core.services.copiloto_faq_enriquecimento_llm import (
            CopilotoFaqEnriquecimentoLlmService,
        )

        resposta = {
            "observacoes": "teste",
            "novas_entradas": [
                {
                    "categoria_orientacao": "DETRAN_VEICULOS",
                    "titulo": "DETRAN e veículos",
                    "mensagem": "Licenciamento e CNH são do DETRAN, não da Prefeitura.",
                    "orgao_hint": "DETRAN-SP",
                    "padroes_regex": [r"\bdetran\b", r"\bcnh\b"],
                    "ordem": 55,
                }
            ],
            "atualizacoes": [
                {
                    "categoria_orientacao": "ENERGIA_CONCESSIONARIA",
                    "padroes_regex_novos": [r"\bqueda\s+de\s+luz\b"],
                    "notas_internas": "teste padrao extra",
                }
            ],
        }
        svc = CopilotoFaqEnriquecimentoLlmService()
        with patch.object(svc, "api_key", "test-key"):
            with patch.object(svc, "_chamar_groq", return_value=resposta):
                out = svc.executar(max_novas=3, dry_run=False)
        self.assertEqual(out.novas_aplicadas, 1)
        self.assertEqual(out.atualizacoes_aplicadas, 1)
        self.assertTrue(
            CopilotoFaqOrientacao.objects.filter(
                categoria_orientacao="DETRAN_VEICULOS"
            ).exists()
        )
        energia = CopilotoFaqOrientacao.objects.get(
            categoria_orientacao="ENERGIA_CONCESSIONARIA"
        )
        self.assertTrue(
            energia.padroes.filter(expressao=r"\bqueda\s+de\s+luz\b").exists()
        )


class GeocodingApiTests(APITestCase):
    def setUp(self):
        self.user = Usuario.objects.create_user(
            username="geo_api_user",
            password="x",
            perfil="VEREADOR",
        )
        self.client.force_authenticate(self.user)

    @patch(
        "core.views_geocoding.GeocodingService.buscar_endereco_por_cep",
        return_value={
            "logradouro": "Rua Teste",
            "bairro": "Centro",
            "localidade": "Mogi das Cruzes",
            "uf": "SP",
        },
    )
    def test_geocoding_cep_endpoint(self, _mock_cep):
        r = self.client.get("/api/v1/geocoding/cep/?cep=08717180")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["logradouro"], "Rua Teste")


class CopilotoFaqApiTests(SinapseCatalogTestMixin, APITestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command

        call_command("seed_copiloto_faq")
        cls.gestor = Usuario.objects.create_user(
            username="gestor_faq",
            password="x",
            perfil="GESTOR",
        )

    def test_catalogo_llm_requer_gestor(self):
        self.client.force_authenticate(self.gestor)
        r = self.client.get("/api/copiloto-faq/catalogo-llm/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("categorias", r.data)
        self.assertTrue(any(c["categoria_orientacao"] == "ENERGIA_CONCESSIONARIA" for c in r.data["categorias"]))

    def test_enriquecer_llm_cria_entrada(self):
        self.client.force_authenticate(self.gestor)
        payload = {
            "categoria_orientacao": "RODOVIA_ESTADUAL",
            "titulo": "Rodovias estaduais",
            "mensagem": "Assunto de rodovia estadual.",
            "orgao_hint": "DER-SP",
            "padroes_regex": [r"\brodovia\s+estadual\b"],
        }
        r = self.client.post("/api/copiloto-faq/enriquecer-llm/", payload, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        from core.models_copiloto_faq import CopilotoFaqOrientacao

        self.assertTrue(
            CopilotoFaqOrientacao.objects.filter(categoria_orientacao="RODOVIA_ESTADUAL").exists()
        )

    def test_sugestoes_llm_v1_dry_run(self):
        from unittest.mock import patch

        from core.services.copiloto_faq_enriquecimento_llm import (
            CopilotoFaqEnriquecimentoLlmService,
        )

        resposta_groq = {
            "observacoes": "foco detran",
            "novas_entradas": [
                {
                    "categoria_orientacao": "DETRAN_VEICULOS",
                    "titulo": "DETRAN",
                    "mensagem": "CNH no DETRAN.",
                    "orgao_hint": "DETRAN-SP",
                    "padroes_regex": [r"\bdetran\b"],
                }
            ],
            "atualizacoes": [],
        }
        self.client.force_authenticate(self.gestor)
        svc = CopilotoFaqEnriquecimentoLlmService()
        with patch.object(svc, "api_key", "test-key"):
            with patch.object(svc, "_chamar_groq", return_value=resposta_groq):
                with patch(
                    "core.views_copiloto_faq.CopilotoFaqEnriquecimentoLlmService",
                    return_value=svc,
                ):
                    r = self.client.get(
                        "/api/v1/copiloto-faq/sugestoes-llm/",
                        {"foco": "DETRAN"},
                    )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["observacoes"], "foco detran")
        self.assertEqual(len(r.data["sugestoes"]), 1)
        self.assertEqual(r.data["sugestoes"][0]["tipo"], "nova")
        from core.models_copiloto_faq import CopilotoFaqOrientacao

        self.assertFalse(
            CopilotoFaqOrientacao.objects.filter(categoria_orientacao="DETRAN_VEICULOS").exists()
        )

    def test_aprovar_v1_enriquecer_llm(self):
        self.client.force_authenticate(self.gestor)
        payload = {
            "categoria_orientacao": "PROCON_WEB",
            "titulo": "Procon online",
            "mensagem": "Reclamação no Procon estadual.",
            "orgao_hint": "Procon-SP",
            "padroes_regex": [r"\bprocon\b"],
        }
        r = self.client.post("/api/v1/copiloto-faq/enriquecer-llm/", payload, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        from core.models_copiloto_faq import CopilotoFaqOrientacao

        self.assertTrue(
            CopilotoFaqOrientacao.objects.filter(categoria_orientacao="PROCON_WEB").exists()
        )


class CopilotoFaqCompetenciaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command

        call_command("seed_copiloto_faq")

    def test_detectar_faq_energia(self):
        from core.services.copiloto_faq_competencia import detectar_faq_por_texto

        faq = detectar_faq_por_texto("falta de energia em casa conta de luz cpfl")
        self.assertIsNotNone(faq)
        self.assertEqual(faq.categoria_orientacao, "ENERGIA_CONCESSIONARIA")

    def test_iluminacao_publica_nao_dispara_faq_energia(self):
        from core.services.copiloto_faq_competencia import detectar_faq_por_texto

        faq = detectar_faq_por_texto("poste apagado iluminação pública na rua principal")
        self.assertIsNone(faq)


class ForaCompetenciaCopilotoTests(TestCase):
    """Pedidos sem relação com serviço municipal não devem seguir carta nem tendência."""

    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command

        call_command("seed_copiloto_faq")

    def test_receita_bolo_marcada_fora_competencia(self):
        from core.services.chatbot_service import ChatbotService

        item = {
            "titulo": "Receita de Bolo",
            "descricao": "Solicitação de receita de bolo",
            "texto_para_embedding": "Receita de Bolo Solicitação de receita de bolo",
            "candidatos_sinapse": [
                {
                    "servico_id": 323,
                    "titulo": "Recolhimento de animais de rua sem tutor e em situação de risco",
                    "orgao": "Meio Ambiente",
                    "score": 0.743,
                },
            ],
        }
        svc = ChatbotService()
        with override_settings(COPILOTO_CARTA_SCORE_MINIMO=0.70):
            fc, motivo = svc._item_fora_competencia(item)
        self.assertTrue(fc)
        self.assertIsNotNone(motivo)
        self.assertTrue(svc._item_sugere_trilha_tendencia(item))

    def test_llm_competencia_nao_receita_bolo(self):
        from core.services.chatbot_service import ChatbotService

        item = {
            "titulo": "Receita de Bolo",
            "descricao": "Solicitação de receita de bolo",
            "competencia_municipal": "nao",
            "motivo_recusa": "Não é serviço municipal.",
        }
        svc = ChatbotService()
        fc, motivo = svc._item_fora_competencia(item)
        self.assertTrue(fc)
        self.assertIn("municipal", (motivo or "").lower())

    @override_settings(COPILOTO_CARTA_SCORE_MINIMO=0.70)
    def test_faq_energia_fora_competencia_sem_triagem_carta(self):
        from core.services.chatbot_service import ChatbotService

        item = {
            "titulo": "Falta de energia",
            "descricao": "Conta de luz cpfl sem energia em casa",
            "texto_para_embedding": "falta energia conta luz cpfl casa",
            "competencia_municipal": "nao",
            "categoria_orientacao": "ENERGIA_CONCESSIONARIA",
            "candidatos_sinapse": [
                {
                    "servico_id": 323,
                    "titulo": "Recolhimento de animais",
                    "score": 0.75,
                }
            ],
        }
        svc = ChatbotService()
        fc, motivo = svc._item_fora_competencia(item)
        self.assertTrue(fc)
        self.assertIsNotNone(item.get("faq_orientacao"))
        self.assertEqual(
            item["faq_orientacao"]["categoria_orientacao"], "ENERGIA_CONCESSIONARIA"
        )
        self.assertIn("concession", (motivo or "").lower())

    @override_settings(COPILOTO_TENDENCIAS_ENABLED=True, COPILOTO_CARTA_SCORE_MINIMO=0.70)
    def test_fechamento_rua_nao_e_fora_competencia(self):
        from core.services.chatbot_service import ChatbotService

        item = {
            "titulo": "Fechamento de rua para evento particular",
            "descricao": "Rua Maestro Laurindo José Gonçalves, Parque Santana",
            "texto_para_embedding": "fechamento rua evento parque santana",
            "candidatos_sinapse": [
                {
                    "servico_id": 10,
                    "titulo": "Reserva de espaços e Eventos no Parque Centenário",
                    "score": 0.74,
                }
            ],
        }
        svc = ChatbotService()
        fc, _ = svc._item_fora_competencia(item)
        self.assertFalse(fc)
        self.assertTrue(svc._item_sugere_trilha_tendencia(item))

    def test_inscricao_taxista_nao_e_procon(self):
        from core.services.chatbot_service import ChatbotService

        item = {
            "titulo": "Inscrição de Taxista",
            "descricao": "Solicitação de inscrição de taxista",
            "texto_para_embedding": "inscrição de taxista",
            "competencia_municipal": "nao",
            "categoria_orientacao": "DEFESA_CONSUMIDOR",
        }
        svc = ChatbotService()
        fc, motivo = svc._item_fora_competencia(item)
        self.assertFalse(fc)
        self.assertEqual(item.get("competencia_municipal"), "sim")
        self.assertNotIn("faq_orientacao", item)
        self.assertIsNone(motivo)


class TendenciaCoerenciaTests(TestCase):
  @override_settings(COPILOTO_TENDENCIAS_ENABLED=True)
  def test_oficina_artesanato_nao_casa_com_bueiros(self):
      from core.services.chatbot_service import ChatbotService

      item = {
          "titulo": "Uso de espaço reservado no Parque Santana",
          "descricao": "Oficina de artesanato",
          "texto_para_embedding": "Parque Santana oficina de artesanato",
          "candidatos_sinapse": [
              {
                  "servico_id": 82,
                  "titulo": "Manutenção ou Limpeza de Bueiros, Bocas de Lobo e Galerias",
                  "orgao": "SSU",
                  "score": 0.739,
              }
          ],
      }
      svc = ChatbotService()
      self.assertTrue(svc._item_sugere_trilha_tendencia(item))
      self.assertFalse(
          svc._coerencia_texto_servico(
              svc._texto_coerencia_demanda(item),
              item["candidatos_sinapse"][0]["titulo"],
          )
      )

  @override_settings(COPILOTO_TENDENCIAS_ENABLED=True)
  def test_fechamento_rua_nao_casa_com_reserva_parque(self):
      from core.services.chatbot_service import ChatbotService

      item = {
          "titulo": "Fechamento de rua para evento particular",
          "descricao": "Rua Maestro Laurindo José Gonçalves, Parque Santana",
          "texto_para_embedding": "fechamento rua evento parque santana",
          "candidatos_sinapse": [
              {
                  "servico_id": 10,
                  "titulo": "Reserva de espaços e Eventos no Parque Centenário",
                  "score": 0.74,
              }
          ],
      }
      svc = ChatbotService()
      self.assertTrue(svc._item_sugere_trilha_tendencia(item))

  def test_variantes_triagem_incluem_local_parque(self):
      from core.services.chatbot_service import ChatbotService

      item = {
          "titulo": "Reserva de espaço para ação social",
          "descricao": "no Parque Centenário",
          "texto_para_embedding": "ação social no Parque Centenário",
      }
      variantes = ChatbotService._variantes_consulta_triagem_sinapse(item)
      joined = " ".join(variantes).lower()
      self.assertIn("parque centen", joined)
      self.assertIn("reserva", joined)

  @override_settings(COPILOTO_TENDENCIAS_ENABLED=True, COPILOTO_CARTA_SCORE_MINIMO=0.70)
  def test_reserva_parque_centenario_prioriza_carta(self):
      from core.services.chatbot_service import ChatbotService

      item = {
          "titulo": "Reserva de espaço para ação social",
          "descricao": "Parque Centenário",
          "texto_para_embedding": "ação social no Parque Centenário",
          "tendencia_id": 3,
          "origem_vinculo": "TENDENCIA",
          "candidatos_sinapse": [
              {
                  "servico_id": 1040,
                  "titulo": "Reserva de espaços e Eventos no Parque Centenário",
                  "score": 0.82,
              }
          ],
      }
      svc = ChatbotService()
      self.assertFalse(svc._item_sugere_trilha_tendencia(item))

  @override_settings(COPILOTO_TENDENCIAS_ENABLED=True)
  def test_tapa_buraco_casa_com_tapa_buraco(self):
      from core.services.chatbot_service import ChatbotService

      item = {
          "titulo": "Tapa buraco na Rua X",
          "descricao": "Buraco perigoso",
          "candidatos_sinapse": [
              {"servico_id": 1, "titulo": "Tapa Buraco", "score": 0.92},
          ],
      }
      svc = ChatbotService()
      self.assertFalse(svc._item_sugere_trilha_tendencia(item))


class TendenciaServiceTests(TestCase):
    def test_normalizar_slug(self):
        from core.services.tendencia_service import normalizar_slug

        self.assertEqual(normalizar_slug("Tapa Buraco — Via X"), "tapa-buraco-via-x")

    @patch("core.services.tendencia_service.VectorService.generate_embedding")
    def test_buscar_ou_criar_nova(self, mock_emb):
        from core.models import Tendencia
        from core.services.tendencia_service import TendenciaService

        mock_emb.return_value = []
        t = TendenciaService().buscar_ou_criar(
            titulo="Iluminação em praça não catalogada",
            texto_embedding="lampada apagada praca central",
        )
        self.assertEqual(Tendencia.objects.count(), 1)
        self.assertEqual(t.titulo, "Iluminação em praça não catalogada")
        self.assertTrue(t.slug)


class TendenciaAPITests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.protocolo = Usuario.objects.create_user(
            username="proto_tend",
            password="x",
            perfil="PROTOCOLO",
        )
        self.assessor = Usuario.objects.create_user(
            username="ass_tend",
            password="x",
            perfil="ASSESSOR",
        )

    def test_buscar_similares_requer_auth(self):
        url = "/api/tendencias/buscar-similares/"
        r = self.client.post(url, {"texto": "buraco rua"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("core.services.tendencia_service.VectorService.generate_embedding")
    def test_buscar_similares_autenticado(self, mock_emb):
        from core.models import Tendencia

        mock_emb.return_value = [0.1] * 1024
        Tendencia.objects.create(
            slug="buraco-via",
            titulo="Buraco em via",
            texto_canonico="buraco via",
            embedding=[0.1] * 1024,
        )
        self.client.force_authenticate(self.assessor)
        r = self.client.post(
            "/api/tendencias/buscar-similares/",
            {"texto": "buraco na rua", "limite": 3},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("resultados", r.data)

    def test_listar_tendencias_so_protocolo(self):
        from core.models import Tendencia

        Tendencia.objects.create(slug="t1", titulo="T1")
        self.client.force_authenticate(self.assessor)
        r = self.client.get("/api/tendencias/")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.protocolo)
        r2 = self.client.get("/api/tendencias/")
        self.assertEqual(r2.status_code, status.HTTP_200_OK)


@override_settings(COPILOTO_TENDENCIAS_ENABLED=True)
class CopilotoConfirmarTendenciaTests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        from core.models import ChatSession

        self.user = Usuario.objects.create_user(
            username="cop_tend",
            password="x",
            perfil="ASSESSOR",
        )
        self.session = ChatSession.objects.create(
            autor=self.user,
            estado_atual=ChatSession.ESTADO_VALIDACAO_FINAL,
            demandas_rascunho=[
                {
                    "titulo": "Problema não catalogado",
                    "descricao": "detalhe",
                    "texto_para_embedding": "problema especial xyz",
                    "candidatos_sinapse": [],
                }
            ],
        )

    @patch("core.services.tendencia_service.VectorService.generate_embedding")
    def test_confirmar_tendencia_rascunho(self, mock_emb):
        mock_emb.return_value = []
        self.client.force_authenticate(self.user)
        r = self.client.post(
            "/api/v1/chat/confirmar-tendencia/",
            {
                "session_id": str(self.session.id),
                "indice_demanda": 0,
                "titulo": "Problema não catalogado",
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.session.refresh_from_db()
        item = self.session.demandas_rascunho[0]
        self.assertEqual(item.get("origem_vinculo"), "TENDENCIA")
        self.assertIsNotNone(item.get("tendencia_id"))


@override_settings(COPILOTO_TENDENCIAS_ENABLED=True)
class CopilotoMaterializarTendenciaTests(SinapseCatalogTestMixin, TestCase):
    """Demanda em trilha tendência não deve receber serviço Sinapse da triagem automática."""

    def setUp(self):
        super().setUp()
        from core.models import Tendencia

        self.user = Usuario.objects.create_user(
            username="mat_tend",
            password="x",
            perfil="ASSESSOR",
        )
        self.tendencia = Tendencia.objects.create(
            slug="fechamento-rua-evento",
            titulo="Fechamento de rua para evento",
        )

    @patch("core.services.chatbot_service.GeocodingService")
    @patch("core.services.chatbot_service.ChatbotService._aplicar_triagem_sinapse_no_item")
    def test_materializar_tendencia_sem_triagem_carta(self, mock_triagem, mock_geo_cls):
        from core.services.chatbot_service import ChatbotService

        def _triagem_preenche_carta(item):
            item["sinapse_servico_id_sugerido"] = SINAPSE_SERVICO_ID
            item["servico_local_id"] = SINAPSE_SERVICO_ID
            return True

        mock_triagem.side_effect = _triagem_preenche_carta
        mock_geo_cls.return_value.buscar_coordenadas.return_value = (None, None, None)

        svc = ChatbotService()
        criadas = svc._materializar_demandas(
            self.user,
            [
                {
                    "titulo": "Fechamento de rua para evento",
                    "descricao": "Preciso fechar a rua no sábado",
                    "tendencia_id": self.tendencia.id,
                    "origem_vinculo": Demanda.ORIGEM_VINCULO_TENDENCIA,
                    "candidatos_sinapse": [
                        {"servico_id": SINAPSE_SERVICO_ID, "titulo": "Artesanato", "score": 0.73},
                    ],
                }
            ],
        )
        self.assertEqual(len(criadas), 1)
        demanda = Demanda.objects.get(pk=criadas[0]["id"])
        self.assertEqual(demanda.origem_vinculo, Demanda.ORIGEM_VINCULO_TENDENCIA)
        self.assertIsNone(demanda.sinapse_servico_id)
        self.assertEqual(demanda.tendencia_id, self.tendencia.id)
        mock_triagem.assert_not_called()


class OficioAssinaturaPdfTests(SinapseCatalogTestMixin, TestCase):
    """Assinatura do vereador no contexto/HTML do ofício (entrega 3.1b)."""

    def setUp(self):
        super().setUp()
        self.user = Usuario.objects.create_user(
            username="vereador_assinatura",
            password="test",
            first_name="João",
            last_name="Silva",
            cargo="Vereador",
            perfil="VEREADOR",
            assinatura="<p>João Silva</p><p>Vereador</p>",
        )

    def test_contexto_assinatura_texto_sem_imagem(self):
        from core.services.assinatura_pdf import contexto_assinatura_pdf

        ctx = contexto_assinatura_pdf(self.user)
        self.assertTrue(ctx["tem_assinatura"])
        self.assertIn("João Silva", ctx["assinatura_texto"])
        self.assertIsNone(ctx["assinatura_imagem_url"])

    def test_html_oficio_inclui_bloco_assinatura(self):
        from django.template.loader import render_to_string

        from core.services.assinatura_pdf import contexto_assinatura_pdf
        from core.services.oficio_service import OficioService

        demanda = Demanda.objects.create(
            titulo="Buraco na rua",
            descricao="Solicito tapa-buraco",
            autor=self.user,
            status="RASCUNHO",
            sinapse_servico_id=SINAPSE_SERVICO_ID,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )
        svc = OficioService()
        ctx = svc._contexto_pdf(
            autor=self.user,
            corpo_texto="Texto do ofício",
            titulo=demanda.titulo,
            protocolo_id=demanda.id,
        )
        html = render_to_string("oficio/demanda_oficio.html", ctx)
        self.assertIn("assinatura-texto", html)
        self.assertIn("João Silva", html)

    @override_settings(MEDIA_ROOT="/tmp/sgdl_test_media")
    def test_contexto_assinatura_com_imagem(self):
        import os
        import tempfile

        from django.core.files.uploadedfile import SimpleUploadedFile

        from core.services.assinatura_pdf import contexto_assinatura_pdf

        with tempfile.TemporaryDirectory() as tmp:
            with self.settings(MEDIA_ROOT=tmp):
                png = (
                    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
                    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
                    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
                    b"\x00\x00\x00\x00IEND\xaeB`\x82"
                )
                self.user.assinatura_imagem.save(
                    "sig.png",
                    SimpleUploadedFile("sig.png", png, content_type="image/png"),
                    save=True,
                )
                ctx = contexto_assinatura_pdf(self.user)
                self.assertTrue(ctx["tem_assinatura"])
                self.assertIsNotNone(ctx["assinatura_imagem_url"])
                self.assertTrue(ctx["assinatura_imagem_url"].startswith("file://"))


class ClusterServiceTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.autor_a = Usuario.objects.create_user(
            username="ver_a", password="x", perfil="VEREADOR"
        )
        self.autor_b = Usuario.objects.create_user(
            username="ver_b", password="x", perfil="VEREADOR"
        )
        self.vetor_base = [1.0] + [0.0] * 1023
        self.vetor_similar = [0.99] + [0.01] * 1023

    SINAPSE_SERVICO_TAPA = 80
    SINAPSE_SERVICO_LOMBADA = 86

    def _demanda(
        self,
        *,
        autor,
        titulo,
        embedding,
        lat=-23.52,
        lon=-46.19,
        bairro="Centro",
        status="AGUARDANDO_PROTOCOLO",
        sinapse_servico_id=None,
    ):
        return Demanda.objects.create(
            titulo=titulo,
            descricao=titulo,
            autor=autor,
            status=status,
            embedding=embedding,
            latitude=lat,
            longitude=lon,
            bairro=bairro,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            sinapse_servico_id=sinapse_servico_id or self.SINAPSE_SERVICO_TAPA,
        )

    @override_settings(
        CLUSTER_ENABLED=True,
        CLUSTER_SEMANTIC_THRESHOLD=0.7,
        CLUSTER_RADIUS_METERS=300,
    )
    def test_primeira_demanda_so_nao_cria_cluster(self):
        from core.models import ClusterExecucao
        from core.services.cluster_service import ClusterService

        d = self._demanda(autor=self.autor_a, titulo="Buraco rua A", embedding=self.vetor_base)
        cluster = ClusterService().atribuir_demanda(d)
        self.assertIsNone(cluster)
        d.refresh_from_db()
        self.assertIsNone(d.cluster_id)
        self.assertEqual(ClusterExecucao.objects.count(), 0)

    @override_settings(
        CLUSTER_ENABLED=True,
        CLUSTER_SEMANTIC_THRESHOLD=0.7,
        CLUSTER_RADIUS_METERS=500,
    )
    def test_agrupa_demandas_proximas_e_similares(self):
        from core.models import ClusterExecucao
        from core.services.cluster_service import ClusterService

        d1 = self._demanda(autor=self.autor_a, titulo="Buraco 1", embedding=self.vetor_base)
        c1 = ClusterService().atribuir_demanda(d1)
        d2 = self._demanda(
            autor=self.autor_b,
            titulo="Buraco 2",
            embedding=self.vetor_similar,
            lat=-23.52001,
            lon=-46.19001,
        )
        c2 = ClusterService().atribuir_demanda(d2)
        self.assertEqual(c1.id, c2.id)
        self.assertEqual(ClusterExecucao.objects.count(), 1)
        self.assertEqual(Demanda.objects.filter(cluster=c1).count(), 2)

    @override_settings(
        CLUSTER_ENABLED=True,
        CLUSTER_SEMANTIC_THRESHOLD=0.7,
        CLUSTER_RADIUS_METERS=50,
    )
    def test_nao_agrupa_se_geo_distante(self):
        from core.models import ClusterExecucao
        from core.services.cluster_service import ClusterService

        d1 = self._demanda(autor=self.autor_a, titulo="Buraco centro", embedding=self.vetor_base)
        ClusterService().atribuir_demanda(d1)
        d2 = self._demanda(
            autor=self.autor_b,
            titulo="Buraco longe",
            embedding=self.vetor_similar,
            lat=-23.60,
            lon=-46.30,
            bairro="Outro",
        )
        ClusterService().atribuir_demanda(d2)
        self.assertEqual(ClusterExecucao.objects.count(), 2)

    @override_settings(
        CLUSTER_ENABLED=True,
        CLUSTER_SEMANTIC_THRESHOLD=0.7,
        CLUSTER_RADIUS_METERS=500,
    )
    def test_nao_agrupa_servicos_diferentes_mesmo_geo(self):
        from core.models import ClusterExecucao
        from core.services.cluster_service import ClusterService

        d1 = self._demanda(
            autor=self.autor_a,
            titulo="Buraco 1",
            embedding=self.vetor_base,
            sinapse_servico_id=self.SINAPSE_SERVICO_TAPA,
        )
        ClusterService().atribuir_demanda(d1)
        d2 = self._demanda(
            autor=self.autor_b,
            titulo="Lombada 1",
            embedding=self.vetor_similar,
            lat=-23.52001,
            lon=-46.19001,
            sinapse_servico_id=self.SINAPSE_SERVICO_LOMBADA,
        )
        ClusterService().atribuir_demanda(d2)
        self.assertEqual(ClusterExecucao.objects.count(), 2)

    @override_settings(CLUSTER_ENABLED=True)
    def test_propaga_status_finalizado_no_grupo(self):
        from core.models import ClusterExecucao
        from core.services.cluster_service import ClusterService

        d1 = self._demanda(autor=self.autor_a, titulo="A", embedding=self.vetor_base)
        c1 = ClusterService().atribuir_demanda(d1)
        d2 = self._demanda(
            autor=self.autor_b,
            titulo="B",
            embedding=self.vetor_similar,
            lat=-23.52001,
            lon=-46.19001,
        )
        ClusterService().atribuir_demanda(d2)
        self.assertEqual(c1.id, d2.cluster_id)

        d1.status = "FINALIZADO"
        d1.save(update_fields=["status"])
        ClusterService().propagar_status_no_cluster(d1)

        d2.refresh_from_db()
        self.assertEqual(d2.status, "FINALIZADO")
        c1.refresh_from_db()
        self.assertEqual(c1.status, "RESOLVIDO")

    @override_settings(CLUSTER_ENABLED=True)
    def test_fecha_cluster_quando_todas_finalizadas(self):
        from core.models import ClusterExecucao
        from core.services.cluster_service import ClusterService

        d = self._demanda(
            autor=self.autor_a,
            titulo="Única",
            embedding=self.vetor_base,
            status="PROTOCOLADO",
        )
        cluster = ClusterService().atribuir_demanda(d)
        d.status = "FINALIZADO"
        d.save(update_fields=["status"])
        ClusterService().reavaliar_fechamento_cluster(cluster.id)
        cluster.refresh_from_db()
        self.assertEqual(cluster.status, "RESOLVIDO")


class ClusterEmbeddingPresenteTests(TestCase):
    def test_embedding_presente_com_lista(self):
        from core.services.cluster_service import embedding_presente

        self.assertFalse(embedding_presente(None))
        self.assertFalse(embedding_presente([]))
        self.assertTrue(embedding_presente([0.1, 0.2]))

    def test_signal_cluster_nao_explode_com_vetor_preenchido(self):
        from core.services.cluster_service import embedding_presente

        autor = Usuario.objects.create_user(username="sig_cl", password="x", perfil="VEREADOR")
        d = Demanda.objects.create(
            titulo="Teste envio",
            descricao="x",
            autor=autor,
            status="RASCUNHO",
            embedding=[0.5] + [0.0] * 1023,
        )
        d.status = "AGUARDANDO_PROTOCOLO"
        d.save(update_fields=["status"])
        self.assertTrue(embedding_presente(d.embedding))


class ClusterAPITests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.gestor = Usuario.objects.create_user(
            username="gestor_cl", password="x", perfil="GESTOR"
        )
        self.client.force_authenticate(self.gestor)

    def test_lista_clusters_gestor(self):
        from core.models import ClusterExecucao

        ClusterExecucao.objects.create(titulo="Grupo buracos", status="ABERTO")
        r = self.client.get("/api/clusters/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        payload = r.data if isinstance(r.data, list) else r.data.get("results", r.data)
        self.assertTrue(len(payload) >= 1)


class ClusterDespachoTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.protocolo = Usuario.objects.create_user(
            username="prot_desp", password="x", perfil="PROTOCOLO"
        )
        self.autor = Usuario.objects.create_user(
            username="ver_desp", password="x", perfil="VEREADOR"
        )
        self.vetor = [1.0] + [0.0] * 1023

    def _demanda_cluster(self, *, cluster, titulo="Ofício A"):
        return Demanda.objects.create(
            titulo=titulo,
            descricao=titulo,
            autor=self.autor,
            status="AGUARDANDO_PROTOCOLO",
            cluster=cluster,
            embedding=self.vetor,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )

    def test_despachar_super_os_protocola_pendentes(self):
        from core.models import ClusterExecucao
        from core.services.cluster_despacho_service import ClusterDespachoService

        cluster = ClusterExecucao.objects.create(
            titulo="Grupo lote",
            status="ABERTO",
            centroide=self.vetor,
        )
        d1 = self._demanda_cluster(cluster=cluster, titulo="A")
        d2 = self._demanda_cluster(cluster=cluster, titulo="B")

        resultado = ClusterDespachoService().despachar_super_os(
            cluster,
            secretaria_id=SINAPSE_ORGAO_A,
            usuario=self.protocolo,
        )
        self.assertEqual(resultado["total"], 2)
        cluster.refresh_from_db()
        self.assertTrue(cluster.protocolo_super_os.startswith("SUPER-"))
        for d in (d1, d2):
            d.refresh_from_db()
            self.assertEqual(d.status, "PROTOCOLADO")
            self.assertIsNotNone(d.protocolo_executivo)

    @override_settings(
        CLUSTER_ENABLED=True,
        CLUSTER_SEMANTIC_THRESHOLD=0.7,
        CLUSTER_RADIUS_METERS=500,
        CLUSTER_JANELA_AGREGACAO_DIAS=90,
    )
    def test_janela_agregacao_nao_reusa_cluster_antigo(self):
        from datetime import timedelta

        from core.models import ClusterExecucao
        from core.services.cluster_service import ClusterService

        d1 = Demanda.objects.create(
            titulo="Antiga",
            descricao="Antiga",
            autor=self.autor,
            status="AGUARDANDO_PROTOCOLO",
            embedding=self.vetor,
            latitude=-23.52,
            longitude=-46.19,
            bairro="Centro",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            sinapse_servico_id=ClusterServiceTests.SINAPSE_SERVICO_TAPA,
        )
        c1 = ClusterService().atribuir_demanda(d1)
        ClusterExecucao.objects.filter(pk=c1.pk).update(
            atualizado_em=timezone.now() - timedelta(days=120)
        )
        c1.refresh_from_db()

        vetor_similar = [0.99] + [0.01] * 1023
        d2 = Demanda.objects.create(
            titulo="Nova similar",
            descricao="Nova similar",
            autor=self.autor,
            status="AGUARDANDO_PROTOCOLO",
            embedding=vetor_similar,
            latitude=-23.52001,
            longitude=-46.19001,
            bairro="Centro",
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            sinapse_servico_id=ClusterServiceTests.SINAPSE_SERVICO_TAPA,
        )
        c2 = ClusterService().atribuir_demanda(d2)
        self.assertNotEqual(c1.id, c2.id)


class ClusterGestaoAPITests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        from core.models import ClusterExecucao

        super().setUp()
        self.protocolo = Usuario.objects.create_user(
            username="prot_gest", password="x", perfil="PROTOCOLO"
        )
        self.autor = Usuario.objects.create_user(
            username="ver_gest", password="x", perfil="VEREADOR"
        )
        self.client.force_authenticate(self.protocolo)
        self.vetor = [1.0] + [0.0] * 1023
        self.cluster = ClusterExecucao.objects.create(
            titulo="Grupo gestão",
            status="ABERTO",
            centroide=self.vetor,
            sinapse_servico_id=ClusterServiceTests.SINAPSE_SERVICO_TAPA,
        )
        Demanda.objects.create(
            titulo="No cluster",
            descricao="No cluster",
            autor=self.autor,
            status="AGUARDANDO_PROTOCOLO",
            cluster=self.cluster,
            embedding=self.vetor,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            sinapse_servico_id=ClusterServiceTests.SINAPSE_SERVICO_TAPA,
            latitude=-23.52,
            longitude=-46.19,
            bairro="Centro",
        )
        self.solta = Demanda.objects.create(
            titulo="Solta",
            descricao="Solta",
            autor=self.autor,
            status="AGUARDANDO_PROTOCOLO",
            embedding=[0.99] + [0.01] * 1023,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            sinapse_servico_id=ClusterServiceTests.SINAPSE_SERVICO_TAPA,
            latitude=-23.52001,
            longitude=-46.19001,
            bairro="Centro",
        )

    def test_vincular_demanda_ao_cluster(self):
        url = f"/api/clusters/{self.cluster.pk}/vincular/"
        r = self.client.post(url, {"demanda_id": self.solta.pk}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.solta.refresh_from_db()
        self.assertEqual(self.solta.cluster_id, self.cluster.pk)

    def test_desvincular_demanda_do_cluster(self):
        vinculada = Demanda.objects.create(
            titulo="Sair",
            descricao="Sair",
            autor=self.autor,
            status="AGUARDANDO_PROTOCOLO",
            cluster=self.cluster,
            embedding=self.vetor,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
            sinapse_servico_id=ClusterServiceTests.SINAPSE_SERVICO_TAPA,
            latitude=-23.52,
            longitude=-46.19,
            bairro="Centro",
        )
        url = f"/api/clusters/{self.cluster.pk}/desvincular/"
        r = self.client.post(url, {"demanda_id": vinculada.pk}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        vinculada.refresh_from_db()
        self.assertIsNone(vinculada.cluster_id)


class ClusterDespachoAPITests(SinapseCatalogTestMixin, APITestCase):
    def setUp(self):
        from core.models import ClusterExecucao

        super().setUp()
        self.protocolo = Usuario.objects.create_user(
            username="prot_api", password="x", perfil="PROTOCOLO"
        )
        self.client.force_authenticate(self.protocolo)
        self.cluster = ClusterExecucao.objects.create(
            titulo="API lote",
            status="ABERTO",
            centroide=[1.0] + [0.0] * 1023,
        )
        Demanda.objects.create(
            titulo="Pendente",
            descricao="Pendente",
            autor=Usuario.objects.create_user(username="v1", password="x", perfil="VEREADOR"),
            status="AGUARDANDO_PROTOCOLO",
            cluster=self.cluster,
            sinapse_orgao_id=SINAPSE_ORGAO_A,
        )

    def test_post_despachar_cluster(self):
        url = f"/api/clusters/{self.cluster.pk}/despachar/"
        r = self.client.post(
            url,
            {"secretaria_id": SINAPSE_ORGAO_A},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("protocolo_super_os", r.data)
        self.cluster.refresh_from_db()
        self.assertTrue(self.cluster.protocolo_super_os)
