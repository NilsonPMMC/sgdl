"""Triagem Copiloto — placa/sinalização vs lombada."""

from django.test import SimpleTestCase

from core.services.chatbot_service import ChatbotService


class CopilotoSinalizacaoTests(SimpleTestCase):
    def _candidatos_lombada_sinalizacao(self):
        return [
            {
                "servico_id": 132,
                "titulo": "Trânsito: Implantação de Lombada",
                "orgao": "Secretaria de Mobilidade e Trânsito",
                "score": 0.99,
            },
            {
                "servico_id": 133,
                "titulo": "Trânsito: Implantação ou Alteração de Sinalização",
                "orgao": "Secretaria de Mobilidade e Trânsito",
                "score": 0.99,
            },
        ]

    def test_placa_sinalizacao_sugere_servico_133(self):
        item = {
            "titulo": "Placa de sinalização de lombada",
            "descricao": (
                "Solicito placa de sinalização de lombada na Av. José Benedito Braga, "
                "próximo ao número 401, na Vila Mogilar."
            ),
            "texto_para_embedding": (
                "instalação de lombada e placa de sinalização na Av. José Benedito Braga"
            ),
            "candidatos_sinapse": self._candidatos_lombada_sinalizacao(),
        }
        melhor = ChatbotService._escolher_melhor_candidato_sinapse(
            item["candidatos_sinapse"], item
        )
        self.assertIsNotNone(melhor)
        self.assertEqual(melhor["servico_id"], 133)

    def test_instalacao_lombada_mantem_servico_132(self):
        item = {
            "titulo": "Instalação de lombada",
            "descricao": "Solicito instalação de lombada na Av. José Benedito Braga, 401.",
            "texto_para_embedding": "instalação lombada Av. José Benedito Braga",
            "candidatos_sinapse": self._candidatos_lombada_sinalizacao(),
        }
        melhor = ChatbotService._escolher_melhor_candidato_sinapse(
            item["candidatos_sinapse"], item
        )
        self.assertEqual(melhor["servico_id"], 132)

    def test_titulo_indica_sinalizacao(self):
        self.assertTrue(
            ChatbotService._titulo_indica_sinalizacao(
                {"titulo": "Placa de sinalização de lombada"}
            )
        )
        self.assertFalse(
            ChatbotService._titulo_indica_sinalizacao({"titulo": "Instalação de lombada"})
        )

    def test_normalizar_eixo_sinalizacao(self):
        item = {
            "titulo": "Placa de sinalização de lombada",
            "descricao": "Solicito placa de sinalização.",
            "_eixo_pedido": "mobilidade_lombada",
        }
        ChatbotService._normalizar_item_pedido_composto(item)
        self.assertEqual(item["_eixo_pedido"], "mobilidade_sinalizacao")
