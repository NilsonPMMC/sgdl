from django.test import SimpleTestCase

from core.services.carta_sinapse_sync import (
    aplicar_bloco_gestao_no_rag,
    extrair_lista_html,
    inferir_prazo_categoria,
    montar_bloco_gestao_operacional,
    RAG_GESTAO_MARKER,
)


class CartaSinapseSyncTests(SimpleTestCase):
    def test_extrair_lista_html_li(self):
        html = "<ul><li>RG</li><li>CPF</li></ul>"
        self.assertEqual(extrair_lista_html(html), ["RG", "CPF"])

    def test_inferir_prazo_categoria(self):
        self.assertEqual(inferir_prazo_categoria(30, ""), "NORMAL")
        self.assertEqual(inferir_prazo_categoria(5, ""), "RAPIDO")
        self.assertEqual(inferir_prazo_categoria(None, "Prazo imediato"), "IMEDIATO")

    def test_bloco_rag_substituicao(self):
        bloco = montar_bloco_gestao_operacional(
            prazo_dias=30,
            prazo_categoria="NORMAL",
            prazo_observacoes="30 dias",
            dependencias_documentos=["Contrato social"],
            dependencias_pagamentos=["Taxa de R$ 50,00"],
        )
        self.assertIn(RAG_GESTAO_MARKER, bloco)
        base = "Texto base do serviço."
        merged = aplicar_bloco_gestao_no_rag(base, bloco)
        merged2 = aplicar_bloco_gestao_no_rag(
            merged,
            montar_bloco_gestao_operacional(
                prazo_dias=15,
                prazo_categoria="NORMAL",
                prazo_observacoes="15 dias",
                dependencias_documentos=["RG"],
                dependencias_pagamentos=[],
            ),
        )
        self.assertEqual(merged2.count(RAG_GESTAO_MARKER), 1)
        self.assertIn("15 dias", merged2)
