"""H3-20 — recusa «Não» na validação final do Copiloto."""

import importlib.util

from django.test import TestCase, override_settings

from core.models import ChatSession, Demanda, Usuario
from core.services.chatbot_service import ChatbotService

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SINAPSE_SERVICO_ID = _legacy.SINAPSE_SERVICO_ID
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


@override_settings(GROQ_API_KEY="test-key")
class CopilotoRecusaValidacaoTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.vereador = Usuario.objects.create_user(
            username="ver_recusa", password="x", perfil="VEREADOR"
        )
        self.svc = ChatbotService()
        self.rascunho = [
            {
                "titulo": "Tapa buraco",
                "descricao": "Buraco na rua",
                "sinapse_servico_id_sugerido": SINAPSE_SERVICO_ID,
                "sinapse_servico_id": SINAPSE_SERVICO_ID,
                "servico_confirmado": True,
                "endereco": {"logradouro": "Rua A", "bairro": "Centro"},
            }
        ]

    def _sessao_validacao(self):
        return ChatSession.objects.create(
            autor=self.vereador,
            estado_atual=ChatSession.ESTADO_VALIDACAO_FINAL,
            demandas_rascunho=list(self.rascunho),
        )

    def test_nao_na_validacao_final_retorna_ao_fluxo(self):
        session = self._sessao_validacao()
        out = self.svc.interagir(
            usuario=self.vereador,
            session_id=str(session.id),
            mensagem="não",
        )
        self.assertTrue(out.get("recusou_geracao_rascunhos"))
        self.assertEqual(out["estado_atual"], ChatSession.ESTADO_COLETA_DADOS)
        self.assertNotIn("demandas_criadas", out)
        session.refresh_from_db()
        self.assertEqual(session.estado_atual, ChatSession.ESTADO_COLETA_DADOS)
        self.assertEqual(Demanda.objects.filter(autor=self.vereador).count(), 0)

    def test_sim_na_validacao_final_ainda_tenta_materializar(self):
        session = self._sessao_validacao()
        out = self.svc.interagir(
            usuario=self.vereador,
            session_id=str(session.id),
            mensagem="sim",
        )
        self.assertFalse(out.get("recusou_geracao_rascunhos"))
        self.assertNotEqual(out.get("estado_atual"), ChatSession.ESTADO_VALIDACAO_FINAL)
