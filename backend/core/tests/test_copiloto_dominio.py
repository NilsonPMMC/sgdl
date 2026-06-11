from django.test import SimpleTestCase, override_settings

from core.services.chatbot_service import ChatbotService
from core.services.copiloto_dominio import detectar_dominio_operacional


class CopilotoDominioTests(SimpleTestCase):
    def test_detectar_mobilidade_redutor(self):
        texto = (
            "solicitando a manutenção e revitalização do redutor de velocidade, "
            "na Av. Shozo Sakai, em frente ao n° 810"
        )
        dom = detectar_dominio_operacional(texto)
        self.assertIsNotNone(dom)
        self.assertEqual(dom["id"], "mobilidade_transito")

    @override_settings(
        COPILOTO_TENDENCIAS_ENABLED=True,
        COPILOTO_CARTA_SCORE_MINIMO=0.6666,
        COPILOTO_CARTA_SCORE_DOMINIO=0.40,
    )
    def test_redutor_modo_carta_dominio_nao_forca_tendencia(self):
        texto = (
            "solicitando a manutenção e revitalização do redutor de velocidade, "
            "na Av. Shozo Sakai"
        )
        item = {
            "titulo": "Manutenção de redutor na Av. Shozo Sakai",
            "descricao": texto,
            "texto_para_embedding": texto,
            "candidatos_sinapse": [
                {
                    "servico_id": 200,
                    "titulo": "Iluminação pública",
                    "orgao": "Iluminação",
                    "score": 0.55,
                },
                {
                    "servico_id": 301,
                    "titulo": "Implantação de Lombada",
                    "orgao": "Secretaria de Mobilidade e Trânsito",
                    "score": 0.48,
                },
                {
                    "servico_id": 302,
                    "titulo": "Manutenção de sinalização de trânsito",
                    "orgao": "Mobilidade",
                    "score": 0.42,
                },
            ],
        }
        svc = ChatbotService()
        modo, dominio = svc._classificar_modo_vinculo_servico(item)
        self.assertEqual(modo, "carta_dominio")
        self.assertEqual(dominio["id"], "mobilidade_transito")
        self.assertFalse(svc._item_sugere_trilha_tendencia(item))

    @override_settings(
        COPILOTO_TENDENCIAS_ENABLED=True,
        COPILOTO_CARTA_SCORE_MINIMO=0.6666,
    )
    def test_sem_dominio_nem_carta_forte_vai_tendencia(self):
        item = {
            "titulo": "Oficina de artesanato",
            "descricao": "Oficina no parque",
            "candidatos_sinapse": [
                {
                    "servico_id": 82,
                    "titulo": "Manutenção de Bueiros",
                    "score": 0.50,
                }
            ],
        }
        svc = ChatbotService()
        self.assertTrue(svc._item_sugere_trilha_tendencia(item))

    def test_campo_endereco_str_aceita_numero_inteiro(self):
        self.assertEqual(ChatbotService._campo_endereco_str(810), "810")
        self.assertEqual(ChatbotService._campo_endereco_str(None), "")
        self.assertEqual(ChatbotService._campo_endereco_str(" 42 "), "42")

    def test_nivelamento_prioriza_servico_coerente_na_ui(self):
        texto = (
            "nivelamento e cascalhamento na Estrada Municipal Katsuji Kitaguchi, "
            "no bairro Cocuera"
        )
        item = {
            "titulo": "Nivelamento e cascalhamento na Estrada Municipal Katsuji Kitaguchi",
            "descricao": texto,
            "texto_para_embedding": texto,
            "candidatos_sinapse": [
                {
                    "servico_id": 127,
                    "titulo": "Limpeza de Valetas e Córregos",
                    "score": 0.8955,
                },
                {
                    "servico_id": 86,
                    "titulo": "Nivelamento e Cascalhamento",
                    "score": 0.7375,
                },
            ],
        }
        svc = ChatbotService()
        filtrados = ChatbotService._filtrar_candidatos_para_ui(
            item["candidatos_sinapse"],
            texto_coerencia=svc._texto_coerencia_demanda(item),
        )
        self.assertEqual(len(filtrados), 1)
        self.assertEqual(filtrados[0]["servico_id"], 86)
        modo, _ = svc._classificar_modo_vinculo_servico(item)
        self.assertEqual(modo, "carta_forte")
        self.assertFalse(svc._item_sugere_trilha_tendencia(item))

    def test_merge_preserva_relato_mais_longo(self):
        relato_longo = (
            "solicita estudos visando ao aumento da quantidade de veículos em operação "
            "na linha 209 do transporte coletivo municipal de Mogi das Cruzes"
        )
        old = [{"descricao": relato_longo, "pedido_integral": relato_longo}]
        new = [
            {
                "descricao": "Solicitação de transporte coletivo",
                "titulo": "Transporte Coletivo",
            }
        ]
        merged = ChatbotService._merge_demandas_rascunho(old, new)
        self.assertIn("linha 209", merged[0]["descricao"])

    def test_titulo_derivado_do_relato_linha_onibus(self):
        relato = (
            "solicita estudos visando ao aumento da quantidade de veículos em operação "
            "na linha 209 do transporte coletivo municipal"
        )
        item = {"titulo": "Transporte Coletivo", "descricao": relato}
        titulo = ChatbotService._titulo_demanda_item(
            item,
            relato,
            servico_nome="Transporte Coletivo: Alteração de Linhas de Ônibus",
        )
        self.assertIn("209", titulo)
        self.assertNotEqual(titulo.lower(), "transporte coletivo")

    def test_relato_integral_recupera_mensagem_longa(self):
        from core.models import ChatSession

        relato = (
            "solicita estudos visando ao aumento da quantidade de veículos em operação "
            "na linha 209 do transporte coletivo municipal"
        )
        session = ChatSession(
            historico_mensagens=[
                {"role": "user", "content": relato},
                {"role": "user", "content": "sim"},
            ]
        )
        item = {"titulo": "Transporte Coletivo", "descricao": "Solicitação de transporte coletivo"}
        integral = ChatbotService._relato_integral_item(item, session=session)
        self.assertIn("linha 209", integral)

    def test_normalizar_sinapse_id_remove_nome_texto(self):
        item = {
            "sinapse_servico_id_sugerido": "Transporte Coletivo",
            "servico_local_id": "Alteração de Linhas",
        }
        ChatbotService._normalizar_sinapse_id_rascunho(item)
        self.assertNotIn("sinapse_servico_id_sugerido", item)
        self.assertNotIn("servico_local_id", item)

    def test_transporte_coletivo_prioriza_alteracao_linhas(self):
        texto = (
            "solicita estudos visando ao aumento da quantidade de veículos em operação "
            "na linha 209 do transporte coletivo municipal de Mogi das Cruzes"
        )
        item = {
            "titulo": "Aumento de veículos na linha 209",
            "descricao": texto,
            "texto_para_embedding": texto,
            "candidatos_sinapse": [
                {
                    "servico_id": 98,
                    "titulo": "Transporte Escolar: Inscrição para vagas",
                    "score": 0.85,
                },
                {
                    "servico_id": 160,
                    "titulo": "Transporte Coletivo: Alteração de Linhas de Ônibus",
                    "score": 0.62,
                },
            ],
        }
        melhor = ChatbotService._escolher_melhor_candidato_sinapse(item["candidatos_sinapse"], item)
        self.assertEqual(melhor["servico_id"], 160)
        filtrados = ChatbotService._filtrar_candidatos_para_ui(
            item["candidatos_sinapse"],
            texto_coerencia=texto,
        )
        self.assertEqual(filtrados[0]["servico_id"], 160)

    def test_expandir_buraco_e_lombada_em_duas_demandas(self):
        texto = (
            "solicito serviço para reparo em buracos na via e instalação de lombada "
            "na rua ipiranga, próximo ao número 1001, centro"
        )
        parsed = {
            "demandas_extraidas": [
                {
                    "titulo": "Reparo em buracos na via",
                    "descricao": texto,
                    "endereco": {
                        "logradouro": "Rua Ipiranga",
                        "numero": 1001,
                        "bairro": "Centro",
                    },
                    "competencia_municipal": "sim",
                }
            ],
            "acionar_triagem_sinapse": False,
        }
        ok = ChatbotService._expandir_demandas_compostas(parsed, texto)
        self.assertTrue(ok)
        dems = parsed["demandas_extraidas"]
        self.assertEqual(len(dems), 2)
        titulos = {d["titulo"] for d in dems}
        self.assertIn("Reparo em buracos na via", titulos)
        self.assertIn("Instalação de lombada", titulos)
        self.assertTrue(parsed.get("acionar_triagem_sinapse"))
        for d in dems:
            self.assertEqual(d["endereco"]["logradouro"], "Rua Ipiranga")
        buraco = next(d for d in dems if "buraco" in d["titulo"].lower())
        lombada = next(d for d in dems if "lombada" in d["titulo"].lower())
        self.assertIn("buraco", buraco["texto_para_embedding"].lower())
        self.assertIn("lombad", lombada["texto_para_embedding"].lower())

    def test_item_expandido_mantem_titulo_especifico_do_eixo(self):
        item = {
            "titulo": "Reparo em buracos na via e instalação de lombada",
            "descricao": "Solicito reparo em buracos na via na Rua Ipiranga.",
            "pedido_integral": (
                "reparo em buracos na via e instalação de lombada na rua ipiranga"
            ),
            "_eixo_pedido": "pavimentacao_buraco",
        }
        ChatbotService._normalizar_item_pedido_composto(item)
        self.assertEqual(item["titulo"], "Reparo em buracos na via")
        self.assertNotIn("lombada", item["pedido_integral"].lower())
        relato = ChatbotService._relato_integral_item(item)
        self.assertIn("buraco", relato.lower())
        self.assertNotIn("lombada", relato.lower())

    def test_normalizar_lista_llm_dois_itens_titulo_composto(self):
        items = [
            {
                "titulo": "Reparo em buracos na via e instalação de lombada",
                "descricao": (
                    "Solicito reparo em buracos na via e instalação de lombada "
                    "na Rua Ipiranga, próximo ao número 1001, no Centro."
                ),
                "endereco": {
                    "logradouro": "Rua Ipiranga",
                    "numero": 1001,
                    "bairro": "Centro",
                },
                "candidatos_sinapse": [
                    {"servico_id": 80, "titulo": "Tapa Buraco", "score": 0.99}
                ],
            },
            {
                "titulo": "Instalação de lombada",
                "descricao": (
                    "Solicito instalação de lombada na Rua Ipiranga, próximo ao número 1001, no Centro."
                ),
                "endereco": {
                    "logradouro": "Rua Ipiranga",
                    "numero": 1001,
                    "bairro": "Centro",
                },
                "candidatos_sinapse": [
                    {"servico_id": 301, "titulo": "Implantação de Lombada", "score": 0.88}
                ],
            },
        ]
        ChatbotService._normalizar_lista_demandas_compostas(items)
        self.assertEqual(items[0]["titulo"], "Reparo em buracos na via")
        self.assertNotIn("lombada", items[0]["descricao"].lower())
        self.assertEqual(items[1]["titulo"], "Instalação de lombada")
        self.assertNotIn("buraco", items[1]["descricao"].lower())

    def test_preservar_relato_nao_quebra_com_eixo_pedido(self):
        svc = ChatbotService()
        items = [
            {
                "titulo": "Reparo em buracos na via e instalação de lombada",
                "descricao": "Solicito reparo em buracos na via.",
                "_eixo_pedido": "pavimentacao_buraco",
            }
        ]
        out = svc._preservar_relato_rascunho(None, items)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["titulo"], "Reparo em buracos na via")

    def test_demandas_pendentes_ignora_descartada(self):
        svc = ChatbotService()
        so_descartada = [
            {
                "titulo": "Instalação de lombada",
                "descricao": "Solicito lombada",
                "descartada": True,
            },
        ]
        self.assertFalse(svc._demandas_pendentes_vinculo_carta(so_descartada))
