"""Testes de hints do corpus legado no Copiloto (pós-triagem, score baixo)."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from core.models import Demanda
from core.services.chatbot_service import ChatbotService


class CopilotoCorpusHintsTests(SimpleTestCase):
    @override_settings(
        CORPUS_LEGADO_ENABLED=True,
        CORPUS_LEGADO_HINTS_COPILOTO_ENABLED=True,
        COPILOTO_CARTA_SCORE_MINIMO=0.6666,
    )
    def test_demanda_fora_carta_elegivel_hint(self):
        svc = ChatbotService()
        dem = {
            "titulo": "Oficina de artesanato",
            "fora_carta": True,
            "candidatos_sinapse": [
                {"servico_id": 82, "titulo": "Bueiros", "score": 0.50}
            ],
        }
        self.assertTrue(svc._demanda_elegivel_hint_corpus(dem))

    @override_settings(COPILOTO_CARTA_SCORE_MINIMO=0.6666)
    def test_demanda_carta_forte_nao_elegivel_hint(self):
        svc = ChatbotService()
        dem = {
            "titulo": "Tapa buraco",
            "fora_carta": False,
            "candidatos_sinapse": [
                {"servico_id": 80, "titulo": "Tapa Buraco", "score": 0.91}
            ],
        }
        self.assertFalse(svc._demanda_elegivel_hint_corpus(dem))

    def test_demanda_tendencia_confirmada_nao_elegivel(self):
        svc = ChatbotService()
        dem = {
            "titulo": "Pedido",
            "fora_carta": True,
            "tendencia_id": 5,
            "origem_vinculo": Demanda.ORIGEM_VINCULO_TENDENCIA,
        }
        self.assertFalse(svc._demanda_elegivel_hint_corpus(dem))

    def test_demanda_fora_competencia_nao_elegivel(self):
        svc = ChatbotService()
        dem = {"fora_competencia": True, "fora_carta": True}
        self.assertFalse(svc._demanda_elegivel_hint_corpus(dem))

    def test_rodada_llm_corpus_hibrido_pula_triagem_sinapse(self):
        from core.models import ChatSession

        svc = ChatbotService()
        historico = [{"role": "user", "content": "Solicito tapa buraco na via."}]
        parsed_llm = {
            "demandas_extraidas": [
                {
                    "titulo": "Tapa buraco",
                    "descricao": "buraco na rua principal",
                    "pedido_integral": "buraco na rua principal",
                }
            ],
            "acionar_triagem_sinapse": True,
            "estado_atual": ChatSession.ESTADO_COLETA_DADOS,
            "resposta_agente": "Entendi o pedido.",
        }
        with patch.object(svc, "_chamar_groq_json", return_value=parsed_llm):
            with patch.object(svc, "_aplicar_triagem_sinapse_local") as mock_triagem:
                parsed, _ = svc._rodada_llm_com_triagem(
                    historico,
                    corpus_servico_id=80,
                )
        self.assertFalse(parsed.get("acionar_triagem_sinapse"))
        mock_triagem.assert_not_called()

    @patch.object(ChatbotService, "_enriquecer_candidatos_utilizacao", side_effect=lambda c: c)
    @patch("integrations.sinapse_catalog.get_orgao_nome", return_value="Secretaria Teste")
    @patch(
        "integrations.sinapse_catalog.get_servico",
        return_value=SimpleNamespace(titulo="Tapa Buraco", id_orgao_id=1),
    )
    def test_turno_corpus_atalho_direto_sem_triagem(
        self, _mock_serv, _mock_orgao, _mock_enr
    ):
        from core.models import ChatSession

        session = ChatSession(estado_atual=ChatSession.ESTADO_COLETA_DADOS)
        session.demandas_rascunho = []
        svc = ChatbotService()
        parsed = svc._turno_corpus_atalho_direto(
            session,
            "Solicito tapa buraco na via.",
            80,
            "vias_buracos",
        )
        dems = parsed.get("demandas_extraidas") or []
        self.assertEqual(len(dems), 1)
        self.assertTrue(dems[0].get("servico_confirmado_usuario"))
        self.assertEqual(dems[0].get("sinapse_servico_id_sugerido"), 80)
        self.assertEqual(parsed.get("estado_atual"), ChatSession.ESTADO_COLETA_ENDERECO)
        self.assertIn("local", (parsed.get("resposta_agente") or "").lower())

    @patch.object(ChatbotService, "_enriquecer_candidatos_utilizacao", side_effect=lambda c: c)
    @patch("integrations.sinapse_catalog.get_orgao_nome", return_value="Secretaria Teste")
    @patch(
        "integrations.sinapse_catalog.get_servico",
        return_value=SimpleNamespace(titulo="Iluminação Pública: Troca de Lâmpadas", id_orgao_id=1),
    )
    def test_preselecao_corpus_confirma_no_rascunho_merged(self, _mock_serv, _mock_orgao, _mock_enr):
        svc = ChatbotService()
        merged = [{"titulo": "Iluminação pública", "fora_competencia": False}]
        parsed: dict = {"demandas_extraidas": [{"titulo": "outro pedido do llm"}]}
        svc._aplicar_preselecao_corpus_atalho(
            merged,
            14,
            parsed,
            eixo_id="iluminacao",
        )
        self.assertTrue(merged[0].get("servico_confirmado_usuario"))
        self.assertEqual(merged[0].get("sinapse_servico_id_sugerido"), 14)
        self.assertTrue(merged[0].get("corpus_aguarda_complemento"))
        self.assertEqual(merged[0].get("origem_vinculo"), Demanda.ORIGEM_VINCULO_CARTA)
        self.assertIn("Registrei", parsed.get("resposta_agente", ""))
        self.assertEqual(merged[0].get("titulo"), "Iluminação pública")

    def test_titulo_iluminacao_nao_vira_poda(self):
        item = {
            "titulo": "Iluminação pública",
            "descricao": "Solicito iluminação pública.",
            "corpus_atalho_eixo_id": "iluminacao",
            "servico_confirmado_usuario": True,
            "candidatos_sinapse": [
                {
                    "servico_id": 982,
                    "titulo": "retirada de galhos caídos de árvores em área pública",
                    "score": 0.76,
                }
            ],
        }
        titulo = ChatbotService._titulo_demanda_item(
            item,
            "Solicito iluminação pública.",
            servico_nome="Iluminação Pública: Troca de Lâmpadas Queimadas, Quebradas e com Defeitos",
        )
        self.assertEqual(titulo, "Iluminação pública")

    def test_titulo_eh_generico_prefixo_carta(self):
        self.assertFalse(
            ChatbotService._titulo_eh_generico(
                "Iluminação pública",
                servico_nome="Iluminação Pública: Troca de Lâmpadas Queimadas",
            )
        )

    def test_finalizar_nao_bloqueia_carta_explicita(self):
        svc = ChatbotService()
        rascunho = [
            {
                "titulo": "Limpeza e roçada de via",
                "descricao": "Solicito limpeza e roçagem de via.",
                "servico_confirmado_usuario": True,
                "sinapse_servico_id_sugerido": 176,
                "servico_local_id": 176,
                "origem_vinculo": Demanda.ORIGEM_VINCULO_CARTA,
                "corpus_atalho_eixo_id": "limpeza_rocada",
            }
        ]
        self.assertEqual(svc._indices_servico_incoerente(rascunho), [])

    def test_coerencia_limpeza_varricao(self):
        ok = ChatbotService._coerencia_texto_servico(
            "Limpeza e roçada de via\nSolicito limpeza e roçagem de via.",
            "Varrição de Ruas",
        )
        self.assertTrue(ok)

    def test_requer_localizacao_ronda_gcm(self):
        item = {
            "titulo": "Ronda da GCM",
            "corpus_atalho_eixo_id": "seguranca",
            "servico": {"nome": "Ronda nas Praças e Patrimônios Públicos"},
        }
        self.assertTrue(ChatbotService._item_requer_localizacao(item))

    def test_requer_localizacao_manutencao_estrada(self):
        item = {"titulo": "Manutenção de estrada", "descricao": "Solicito manutenção de estrada."}
        self.assertTrue(ChatbotService._item_requer_localizacao(item))

    def test_extrair_endereco_av_completo(self):
        ext = ChatbotService._extrair_endereco_livre(
            "Av. Antônio de Almeida, 391-199 - Jardim Marica, Mogi das Cruzes - SP, 08775-420"
        )
        self.assertEqual(ext.get("cep"), "08775-420")
        self.assertTrue((ext.get("logradouro") or "").startswith("Av."))
        self.assertTrue(ext.get("bairro") or ext.get("cep"))
