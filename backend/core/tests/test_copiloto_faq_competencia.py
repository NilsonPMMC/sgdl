"""Testes A1 — Copiloto calibrado com FAQ cadastrada."""

import importlib.util

from django.test import TestCase, override_settings

from core.models_copiloto_faq import CopilotoFaqOrientacao, CopilotoFaqPadraoRegex
from core.services.chatbot_service import ChatbotService
from core.services.copiloto_faq_service import (
    detectar_faq_por_texto,
    invalidar_cache_faq,
    montar_resposta_chat_fora_competencia,
)

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


@override_settings(COPILOTO_FAQ_ENABLED=True)
class CopilotoFaqCalibracaoTests(SinapseCatalogTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        invalidar_cache_faq()
        self.faq, _ = CopilotoFaqOrientacao.objects.update_or_create(
            categoria_orientacao="ENERGIA_CONCESSIONARIA",
            defaults={
                "slug": "energia-teste",
                "titulo": "Energia elétrica residencial",
                "mensagem": "Problemas de conta de luz devem ser tratados com a concessionária.",
                "orgao_hint": "CPFL Piratininga",
                "municipio_referencia": "Mogi das Cruzes",
                "ordem": 1,
                "ativo": True,
            },
        )
        CopilotoFaqPadraoRegex.objects.update_or_create(
            faq=self.faq,
            expressao=r"\bconta\s+de\s+luz\b",
            defaults={"ordem": 10, "ativo": True},
        )
        invalidar_cache_faq()

    def test_detectar_faq_conta_de_luz(self):
        faq = detectar_faq_por_texto("Minha conta de luz veio errada este mês")
        self.assertIsNotNone(faq)
        self.assertEqual(faq.categoria_orientacao, "ENERGIA_CONCESSIONARIA")

    def test_montar_resposta_chat_usa_mensagem_faq(self):
        rascunho = [
            {
                "titulo": "Conta de luz",
                "fora_competencia": True,
                "motivo_recusa": "Problemas de conta de luz devem ser tratados com a concessionária. Orientação: CPFL Piratininga.",
                "faq_orientacao": {
                    "titulo": "Energia elétrica residencial",
                    "mensagem": "Problemas de conta de luz devem ser tratados com a concessionária.",
                    "orgao_hint": "CPFL Piratininga",
                },
            }
        ]
        msg = montar_resposta_chat_fora_competencia(rascunho)
        self.assertIn("conta de luz", msg.lower())
        self.assertIn("CPFL", msg)

    def test_pre_classificar_faq_nas_demandas(self):
        parsed = {
            "demandas_extraidas": [
                {
                    "titulo": "Conta de luz",
                    "descricao": "Minha conta de luz veio errada",
                    "pedido_integral": "Minha conta de luz veio errada",
                }
            ]
        }
        ChatbotService._pre_classificar_faq_nas_demandas(
            parsed, texto_sessao="Minha conta de luz veio errada"
        )
        item = parsed["demandas_extraidas"][0]
        self.assertEqual(item["categoria_orientacao"], "ENERGIA_CONCESSIONARIA")
        self.assertEqual(item["competencia_municipal"], "nao")
        self.assertIn("faq_orientacao", item)

    def test_system_prompt_inclui_faq_completa(self):
        prompt = ChatbotService._system_prompt_copiloto()
        self.assertIn("ENERGIA_CONCESSIONARIA", prompt)
        self.assertIn("conta de luz", prompt.lower())
        self.assertIn("CPFL", prompt)

    def test_turno_faq_imediata_conta_de_luz(self):
        from core.models import ChatSession, Usuario

        user = Usuario.objects.create_user(username="ver_faq2", password="x", perfil="VEREADOR")
        session = ChatSession.objects.create(
            autor=user,
            estado_atual=ChatSession.ESTADO_COLETA_DADOS,
            historico_mensagens=[],
            demandas_rascunho=[],
        )
        svc = ChatbotService()
        parsed = svc._turno_resposta_faq_imediata(
            "Minha conta de luz veio errada", session
        )
        self.assertIsNotNone(parsed)
        self.assertFalse(parsed.get("acionar_triagem_sinapse"))
        self.assertTrue(parsed["demandas_extraidas"][0].get("fora_competencia"))
        self.assertIn("concessionária", parsed["resposta_agente"].lower())

    def test_municipal_nao_prevalece_sobre_faq_agua(self):
        faq_agua, _ = CopilotoFaqOrientacao.objects.update_or_create(
            categoria_orientacao="AGUA_SANEAMENTO",
            defaults={
                "slug": "agua-teste",
                "titulo": "Água domiciliar",
                "mensagem": "Conta de água domiciliar: SABESP.",
                "orgao_hint": "SABESP",
                "municipio_referencia": "Mogi das Cruzes",
                "ordem": 2,
                "ativo": True,
            },
        )
        CopilotoFaqPadraoRegex.objects.update_or_create(
            faq=faq_agua,
            expressao=r"\bconta\s+de\s+[aá]gua\b",
            defaults={"ordem": 10, "ativo": True},
        )
        invalidar_cache_faq()
        faq = detectar_faq_por_texto("Minha conta de água veio errada")
        self.assertIsNotNone(faq)
        self.assertFalse(
            ChatbotService._texto_parece_demanda_municipal("Minha conta de água veio errada")
        )

    def test_item_fora_competencia_com_faq(self):
        svc = ChatbotService()
        item = {
            "titulo": "Conta de luz",
            "descricao": "Minha conta de luz veio errada",
            "competencia_municipal": "nao",
            "categoria_orientacao": "ENERGIA_CONCESSIONARIA",
        }
        fc, motivo = svc._item_fora_competencia(item, texto_sessao="Minha conta de luz veio errada")
        self.assertTrue(fc)
        self.assertIn("concessionária", motivo.lower())
        self.assertEqual(item.get("faq_orientacao", {}).get("categoria_orientacao"), "ENERGIA_CONCESSIONARIA")

    def test_detectar_faq_prisao_furto_fallback(self):
        faq_prisao, _ = CopilotoFaqOrientacao.objects.update_or_create(
            categoria_orientacao="MADATO_DE_PRISAO",
            defaults={
                "slug": "mandato-prisao-teste",
                "titulo": "Mandato de prisão",
                "mensagem": "O mandato de prisão é processo judicial e não compete à Prefeitura.",
                "orgao_hint": "Justiça Estadual ou advogado",
                "municipio_referencia": "Mogi das Cruzes",
                "ordem": 50,
                "ativo": True,
            },
        )
        CopilotoFaqPadraoRegex.objects.update_or_create(
            faq=faq_prisao,
            expressao="madato de prisão",
            defaults={"ordem": 10, "ativo": True},
        )
        invalidar_cache_faq()
        texto = "solicito prisão de um cidadão por furto no bairro São João"
        faq = detectar_faq_por_texto(texto)
        self.assertIsNotNone(faq)
        self.assertEqual(faq.categoria_orientacao, "MADATO_DE_PRISAO")
        self.assertFalse(ChatbotService._texto_parece_demanda_municipal(texto))

    def test_turno_faq_imediata_prisao_furto(self):
        from core.models import ChatSession, Usuario

        faq, _ = CopilotoFaqOrientacao.objects.update_or_create(
            categoria_orientacao="MADATO_DE_PRISAO",
            defaults={
                "slug": "mandato-prisao-turno",
                "titulo": "Mandato de prisão",
                "mensagem": "O mandato de prisão é processo judicial e não compete à Prefeitura.",
                "orgao_hint": "Justiça Estadual ou advogado",
                "municipio_referencia": "Mogi das Cruzes",
                "ordem": 50,
                "ativo": True,
            },
        )
        CopilotoFaqPadraoRegex.objects.update_or_create(
            faq=faq,
            expressao="madato de prisão",
            defaults={"ordem": 10, "ativo": True},
        )
        invalidar_cache_faq()
        user = Usuario.objects.create_user(username="ver_prisao", password="x", perfil="VEREADOR")
        session = ChatSession.objects.create(
            autor=user,
            estado_atual=ChatSession.ESTADO_COLETA_DADOS,
            historico_mensagens=[],
            demandas_rascunho=[],
        )
        parsed = ChatbotService()._turno_resposta_faq_imediata(
            "solicito prisão de um cidadão por furto no bairro São João",
            session,
        )
        self.assertIsNotNone(parsed)
        self.assertTrue(parsed["demandas_extraidas"][0].get("fora_competencia"))
        self.assertEqual(
            parsed["demandas_extraidas"][0].get("categoria_orientacao"),
            "MADATO_DE_PRISAO",
        )
        self.assertFalse(parsed.get("acionar_triagem_sinapse"))
