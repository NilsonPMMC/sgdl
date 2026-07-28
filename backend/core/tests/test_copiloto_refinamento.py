"""Refinamento Copiloto — FAQ desligada, relato integral, expansão composta, tendências."""

import importlib.util
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from core.models import ChatSessaoAnexo, ChatSession, Usuario
from core.services.chatbot_service import ChatbotService, _ENDERECO_VAZIO

_spec = importlib.util.spec_from_file_location("core_tests_legacy", "core/tests.py")
_legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_legacy)
SinapseCatalogTestMixin = _legacy.SinapseCatalogTestMixin


@override_settings(COPILOTO_FAQ_ENABLED=False, COPILOTO_TENDENCIAS_ENABLED=True)
class CopilotoRefinamentoTests(SinapseCatalogTestMixin, TestCase):
    def test_faq_desligada_nao_bloqueia_conta_de_luz(self):
        svc = ChatbotService()
        item = {
            "titulo": "Conta de luz",
            "descricao": "Minha conta de luz veio errada em maio",
            "competencia_municipal": "nao",
            "categoria_orientacao": "ENERGIA_CONCESSIONARIA",
        }
        fc, motivo = svc._item_fora_competencia(item, texto_sessao="Minha conta de luz veio errada")
        self.assertFalse(fc)
        self.assertIsNone(motivo)
        self.assertNotIn("fora_competencia", item)

    def test_expandir_composto_preserva_relato_integral(self):
        parsed = {
            "demandas_extraidas": [
                {
                    "titulo": "Buraco e lombada",
                    "descricao": "buraco e lombada na Rua A",
                    "pedido_integral": (
                        "buraco profundo e lombada ausente na Rua A, evento dia 15 de agosto"
                    ),
                    "endereco": {
                        "logradouro": "Rua A",
                        "numero": 100,
                        "bairro": "Centro",
                        "cep": None,
                        "complemento": None,
                    },
                }
            ]
        }
        ok = ChatbotService._expandir_demandas_compostas(
            parsed,
            "buraco profundo e lombada ausente na Rua A, evento dia 15 de agosto",
        )
        self.assertTrue(ok)
        dems = parsed["demandas_extraidas"]
        self.assertEqual(len(dems), 2)
        relato_esperado = (
            "buraco profundo e lombada ausente na Rua A, evento dia 15 de agosto"
        )
        for item in dems:
            self.assertEqual(item["pedido_integral"], relato_esperado)
            self.assertIn("agosto", item["descricao"].lower())
            self.assertNotIn("anexos_indices", item)

    def test_extrair_detalhes_complementares_data_evento(self):
        relato = "Via interditada desde segunda. Evento dia 20 de setembro no parque."
        det = ChatbotService._extrair_detalhes_complementares_relato(relato)
        self.assertIn("interditada", det.lower())
        self.assertIn("setembro", det.lower())

    def test_tendencias_habilitadas_por_padrao(self):
        from core.services.copiloto_config import copiloto_tendencias_habilitadas

        self.assertTrue(copiloto_tendencias_habilitadas())

    def test_item_sugere_trilha_tendencia_sem_carta(self):
        svc = ChatbotService()
        item = {
            "titulo": "Serviço inédito",
            "descricao": "Pedido de serviço que não existe na carta municipal",
            "candidatos_sinapse": [],
        }
        self.assertTrue(svc._item_sugere_trilha_tendencia(item))

    def test_expandir_buraco_e_poda_em_duas_demandas(self):
        texto = (
            "solicito tapa buraco e poda de arvore, R. João Ribeiro, 114 - Vila Suissa"
        )
        parsed = {
            "demandas_extraidas": [
                {
                    "titulo": "Tapa buraco e poda",
                    "descricao": texto,
                    "pedido_integral": texto,
                    "endereco": {
                        "logradouro": "R. João Ribeiro",
                        "numero": 114,
                        "bairro": "Vila Suissa",
                        "cep": "08810-220",
                        "complemento": None,
                    },
                }
            ]
        }
        ok = ChatbotService._expandir_demandas_compostas(parsed, texto)
        self.assertTrue(ok)
        dems = parsed["demandas_extraidas"]
        self.assertEqual(len(dems), 2)
        eixos = {d.get("_eixo_pedido") for d in dems}
        self.assertIn("pavimentacao_buraco", eixos)
        self.assertIn("meio_ambiente_poda", eixos)

    def test_materializacao_exige_servico_confirmado(self):
        svc = ChatbotService()
        item = {
            "titulo": "Poda",
            "descricao": "poda de arvore",
            "sinapse_servico_id_sugerido": 999001,
            "servico_local_id": 999001,
        }
        self.assertIsNone(svc._resolver_sinapse_id_confirmado(item))
        item["servico_confirmado_usuario"] = True
        sid = svc._resolver_sinapse_id_confirmado(item)
        self.assertEqual(sid, 999001)

    def test_mapa_anexos_prioriza_indice_demanda_explicito(self):
        from unittest.mock import MagicMock

        anexos = [
            MagicMock(indice_demanda=0),
            MagicMock(indice_demanda=1),
        ]
        rascunho = [
            {"anexos_indices": [0, 1]},
            {"anexos_indices": [0, 1]},
        ]
        mapa = ChatbotService._mapa_anexos_por_demanda(anexos, rascunho, [None, None])
        self.assertEqual(mapa[0], {0})
        self.assertEqual(mapa[1], {1})

    def test_revisar_servico_limpa_local_e_anexos(self):
        user = Usuario.objects.create_user(username="rev_svc", password="x", perfil="VEREADOR")
        session = ChatSession.objects.create(
            autor=user,
            estado_atual=ChatSession.ESTADO_VALIDACAO_FINAL,
            demandas_rascunho=[
                {
                    "titulo": "Buraco",
                    "servico_confirmado_usuario": True,
                    "sinapse_servico_id_sugerido": 999001,
                    "endereco": {"logradouro": "Rua A", "bairro": "Centro"},
                    "latitude": -23.5,
                    "anexos_indices": [0],
                }
            ],
        )
        ChatSessaoAnexo.objects.create(
            session=session,
            descricao="foto.jpg",
            indice_demanda=0,
            arquivo=SimpleUploadedFile("foto.jpg", b"conteudo"),
        )
        svc = ChatbotService()
        with patch(
            "core.services.chatbot_service.sinapse_catalog.servico_existe",
            return_value=True,
        ):
            payload = svc.revisar_etapa_copiloto(
                usuario=user,
                session_id=str(session.id),
                indice_demanda=0,
                etapa="servico",
            )
        session.refresh_from_db()
        item = session.demandas_rascunho[0]
        self.assertNotIn("servico_confirmado_usuario", item)
        self.assertNotIn("latitude", item)
        self.assertEqual(item.get("anexos_indices"), [])
        self.assertEqual(session.anexos_sessao.count(), 0)
        self.assertEqual(payload["revisao_etapa"], "servico")

    def test_editar_local_nao_afeta_servico(self):
        user = Usuario.objects.create_user(username="rev_loc", password="x", perfil="VEREADOR")
        session = ChatSession.objects.create(
            autor=user,
            estado_atual=ChatSession.ESTADO_VALIDACAO_FINAL,
            demandas_rascunho=[
                {
                    "titulo": "Poda",
                    "servico_confirmado_usuario": True,
                    "sinapse_servico_id_sugerido": 999002,
                    "endereco": {"logradouro": "Rua Antiga", "bairro": "Centro"},
                }
            ],
        )
        svc = ChatbotService()
        with patch.object(
            ChatbotService,
            "_resolver_coordenadas_item",
            return_value=(-23.55, -46.63, "logradouro"),
        ):
            with patch(
                "core.services.chatbot_service.sinapse_catalog.servico_existe",
                return_value=True,
            ):
                svc.editar_local_demanda(
                    usuario=user,
                    session_id=str(session.id),
                    indice_demanda=0,
                    endereco={"logradouro": "Rua Nova", "bairro": "Jardim", "numero": "10"},
                )
        session.refresh_from_db()
        item = session.demandas_rascunho[0]
        self.assertTrue(item.get("servico_confirmado_usuario"))
        self.assertEqual(item["endereco"]["logradouro"], "Rua Nova")

    def test_deve_adiar_anexos_multiplos_servicos(self):
        texto = "tapa buraco e poda de arvore na Rua A"
        self.assertTrue(
            ChatbotService._deve_adiar_anexos_multiplos_servicos([], texto)
        )
        rascunho_pendente = [{"titulo": "Buraco"}, {"titulo": "Poda"}]
        self.assertTrue(
            ChatbotService._deve_adiar_anexos_multiplos_servicos(rascunho_pendente, "")
        )
        rascunho_confirmado = [
            {
                "titulo": "Buraco",
                "servico_confirmado_usuario": True,
                "sinapse_servico_id_sugerido": 999001,
            },
            {
                "titulo": "Poda",
                "servico_confirmado_usuario": True,
                "sinapse_servico_id_sugerido": 999002,
            },
        ]
        with patch(
            "core.services.chatbot_service.sinapse_catalog.servico_existe",
            return_value=True,
        ):
            self.assertFalse(
                ChatbotService._deve_adiar_anexos_multiplos_servicos(
                    rascunho_confirmado, ""
                )
            )

    def test_indices_sem_servico_ignora_tendencia_confirmada(self):
        svc = ChatbotService()
        from core.models import Demanda

        rascunho = [
            {"titulo": "A", "origem_vinculo": Demanda.ORIGEM_VINCULO_TENDENCIA, "tendencia_id": 99},
            {"titulo": "B"},
        ]
        self.assertEqual(svc._indices_demandas_sem_servico_confirmado(rascunho), [1])

    @override_settings(GROQ_API_KEY="test-key")
    def test_confirmar_local_aceita_endereco_inferido_do_pedido(self):
        user = Usuario.objects.create_user(username="conf_loc", password="x", perfil="VEREADOR")
        session = ChatSession.objects.create(
            autor=user,
            estado_atual=ChatSession.ESTADO_COLETA_ENDERECO,
            demandas_rascunho=[
                {
                    "titulo": "Tapa buraco",
                    "servico_confirmado_usuario": True,
                    "sinapse_servico_id_sugerido": 999001,
                    "endereco": {
                        "logradouro": "Rua João Ribeiro",
                        "numero": "114",
                        "bairro": "Vila Suissa",
                    },
                    "latitude": -23.5123,
                    "longitude": -46.6234,
                }
            ],
        )
        svc = ChatbotService()
        with patch(
            "core.services.chatbot_service.sinapse_catalog.servico_existe",
            return_value=True,
        ):
            out = svc.interagir(
                usuario=user,
                session_id=str(session.id),
                mensagem="confirmar local",
            )
        session.refresh_from_db()
        item = session.demandas_rascunho[0]
        self.assertTrue(item.get("endereco_informado_usuario"))
        self.assertNotEqual(out["estado_atual"], ChatSession.ESTADO_COLETA_ENDERECO)

    @override_settings(GROQ_API_KEY="test-key")
    def test_revisao_pedido_mudanca_assunto_reabre_carta(self):
        user = Usuario.objects.create_user(username="rev_ped", password="x", perfil="VEREADOR")
        session = ChatSession.objects.create(
            autor=user,
            estado_atual=ChatSession.ESTADO_VALIDACAO_FINAL,
            demandas_rascunho=[
                {
                    "titulo": "Poda de Árvore",
                    "descricao": "Poda na Rua João Ribeiro",
                    "servico_confirmado_usuario": True,
                    "sinapse_servico_id_sugerido": 999002,
                    "_revisao_etapa": "pedido",
                    "_titulo_anterior_revisao": "Poda de Árvore",
                }
            ],
        )
        svc = ChatbotService()
        with patch(
            "core.services.chatbot_service.sinapse_catalog.servico_existe",
            return_value=True,
        ):
            with patch.object(
                ChatbotService,
                "_buscar_candidatos_sinapse_item",
                return_value=[{"servico_id": 999003, "titulo": "Limpeza de rua"}],
            ):
                out = svc.interagir(
                    usuario=user,
                    session_id=str(session.id),
                    mensagem="limpeza de rua",
                )
        session.refresh_from_db()
        item = session.demandas_rascunho[0]
        self.assertEqual(item.get("titulo"), "limpeza de rua")
        self.assertNotIn("servico_confirmado_usuario", item)
        self.assertNotIn("_revisao_etapa", item)
        self.assertTrue(out.get("revisao_encerrada"))
        self.assertIn("carta", (out.get("resposta_agente") or "").lower())

    @override_settings(GROQ_API_KEY="test-key")
    def test_local_geocodificado_exige_confirmacao_explicita(self):
        user = Usuario.objects.create_user(username="loc_pend", password="x", perfil="VEREADOR")
        session = ChatSession.objects.create(
            autor=user,
            estado_atual=ChatSession.ESTADO_COLETA_ENDERECO,
            demandas_rascunho=[
                {
                    "titulo": "Tapa buraco",
                    "descricao": "Buraco na Rua João Ribeiro, 114, Vila Suissa",
                    "servico_confirmado_usuario": True,
                    "sinapse_servico_id_sugerido": 999001,
                    "latitude": -23.5123,
                    "longitude": -46.6234,
                }
            ],
        )
        svc = ChatbotService()
        with patch(
            "core.services.chatbot_service.sinapse_catalog.servico_existe",
            return_value=True,
        ):
            out = svc._montar_resposta_http(
                session,
                {
                    "resposta_agente": "Informe o local.",
                    "estado_atual": ChatSession.ESTADO_COLETA_ENDERECO,
                    "demandas_extraidas": session.demandas_rascunho,
                },
                criadas=[],
            )
        self.assertTrue(out["demandas_extraidas"][0].get("local_pendente_confirmacao"))
        self.assertFalse(session.demandas_rascunho[0].get("local_confirmado_usuario"))
        with patch(
            "core.services.chatbot_service.sinapse_catalog.servico_existe",
            return_value=True,
        ):
            conf = svc.interagir(
                usuario=user,
                session_id=str(session.id),
                mensagem="confirmar local",
            )
        session.refresh_from_db()
        self.assertTrue(session.demandas_rascunho[0].get("local_confirmado_usuario"))
        self.assertNotEqual(conf["estado_atual"], ChatSession.ESTADO_COLETA_ENDERECO)

    def test_titulo_materializacao_respeita_revisao_pedido(self):
        item = {
            "titulo": "limpeza de rua",
            "descricao": "limpeza de rua",
            "pedido_integral": "limpeza de rua",
            "_eixo_pedido": "meio_ambiente_poda",
            "servico_confirmado_usuario": True,
            "sinapse_servico_id_sugerido": 999003,
        }
        titulo = ChatbotService._titulo_demanda_item(
            item,
            "limpeza de rua na Rua João Ribeiro",
            servico_nome="Limpeza urbana",
        )
        self.assertEqual(titulo, "limpeza de rua")

    @override_settings(GROQ_API_KEY="test-key")
    def test_revisao_pedido_limpa_eixo_antigo(self):
        user = Usuario.objects.create_user(username="rev_eixo", password="x", perfil="VEREADOR")
        session = ChatSession.objects.create(
            autor=user,
            estado_atual=ChatSession.ESTADO_VALIDACAO_FINAL,
            demandas_rascunho=[
                {
                    "titulo": "Poda de Árvore",
                    "descricao": "Poda na rua",
                    "_eixo_pedido": "meio_ambiente_poda",
                    "servico_confirmado_usuario": True,
                    "sinapse_servico_id_sugerido": 999002,
                    "_revisao_etapa": "pedido",
                    "_titulo_anterior_revisao": "Poda de Árvore",
                }
            ],
        )
        svc = ChatbotService()
        with patch(
            "core.services.chatbot_service.sinapse_catalog.servico_existe",
            return_value=True,
        ):
            with patch.object(
                ChatbotService,
                "_buscar_candidatos_sinapse_item",
                return_value=[{"servico_id": 999003, "titulo": "Limpeza urbana"}],
            ):
                out = svc.interagir(
                    usuario=user,
                    session_id=str(session.id),
                    mensagem="limpeza de rua",
                )
        session.refresh_from_db()
        item = session.demandas_rascunho[0]
        self.assertEqual(item.get("titulo"), "limpeza de rua")
        self.assertNotEqual(item.get("_eixo_pedido"), "meio_ambiente_poda")

    @override_settings(GROQ_API_KEY="test-key")
    def test_local_reaproveita_endereco_sessao_apos_reset_servico(self):
        user = Usuario.objects.create_user(username="reuso_loc", password="x", perfil="VEREADOR")
        session = ChatSession.objects.create(
            autor=user,
            estado_atual=ChatSession.ESTADO_COLETA_ENDERECO,
            historico_mensagens=[
                {
                    "role": "user",
                    "content": "poda de arvore na Rua João Ribeiro, Vila Suissa",
                },
            ],
            demandas_rascunho=[
                {
                    "titulo": "poda de arvore",
                    "descricao": "poda de arvore",
                    "servico_confirmado_usuario": True,
                    "sinapse_servico_id_sugerido": 999001,
                    "endereco": {
                        "cep": None,
                        "logradouro": None,
                        "numero": None,
                        "bairro": None,
                        "complemento": None,
                    },
                }
            ],
        )
        svc = ChatbotService()
        with patch.object(
            ChatbotService,
            "_resolver_coordenadas_item",
            return_value=(-23.5123, -46.6234, "logradouro"),
        ):
            with patch(
                "core.services.chatbot_service.sinapse_catalog.servico_existe",
                return_value=True,
            ):
                out = svc._montar_resposta_http(
                    session,
                    {
                        "resposta_agente": "Informe o local.",
                        "estado_atual": ChatSession.ESTADO_COLETA_ENDERECO,
                        "demandas_extraidas": session.demandas_rascunho,
                    },
                    criadas=[],
                )
        row = out["demandas_extraidas"][0]
        self.assertTrue(row.get("local_pendente_confirmacao"))
        self.assertEqual(row["endereco"].get("logradouro"), "Rua João Ribeiro")
        self.assertIsNotNone(row.get("latitude"))
        self.assertIsNotNone(row.get("longitude"))

    @override_settings(GROQ_API_KEY="test-key")
    def test_local_reaproveita_endereco_com_numero_inteiro(self):
        user = Usuario.objects.create_user(username="reuso_int", password="x", perfil="VEREADOR")
        session = ChatSession.objects.create(
            autor=user,
            estado_atual=ChatSession.ESTADO_COLETA_ENDERECO,
            historico_mensagens=[
                {"role": "user", "content": "limpeza de rua na Rua João Ribeiro"},
            ],
            demandas_rascunho=[
                {
                    "titulo": "poda de arvore",
                    "descricao": "poda de arvore",
                    "servico_confirmado_usuario": True,
                    "sinapse_servico_id_sugerido": 999001,
                    "endereco": dict(_ENDERECO_VAZIO),
                },
                {
                    "titulo": "Tapa Buraco",
                    "servico_confirmado_usuario": True,
                    "sinapse_servico_id_sugerido": 999002,
                    "endereco": {
                        "cep": "08810-220",
                        "logradouro": "Rua João Ribeiro",
                        "numero": 114,
                        "bairro": "Vila Suissa",
                    },
                    "latitude": -23.5123,
                    "longitude": -46.6234,
                    "local_confirmado_usuario": True,
                },
            ],
        )
        svc = ChatbotService()
        with patch.object(
            ChatbotService,
            "_resolver_coordenadas_item",
            return_value=(-23.5123, -46.6234, "logradouro"),
        ):
            with patch(
                "core.services.chatbot_service.sinapse_catalog.servico_existe",
                return_value=True,
            ):
                out = svc._montar_resposta_http(
                    session,
                    {
                        "resposta_agente": "Informe o local.",
                        "estado_atual": ChatSession.ESTADO_COLETA_ENDERECO,
                        "demandas_extraidas": session.demandas_rascunho,
                    },
                    criadas=[],
                )
        row = out["demandas_extraidas"][0]
        self.assertTrue(row.get("local_pendente_confirmacao"))
        self.assertIn("João Ribeiro", row["endereco"].get("logradouro") or "")
        self.assertEqual(row["endereco"].get("numero"), 114)

    @override_settings(GROQ_API_KEY="test-key")
    def test_revisao_pedido_mudanca_assunto_nao_quebra_com_numero_inteiro(self):
        user = Usuario.objects.create_user(username="rev_int", password="x", perfil="VEREADOR")
        session = ChatSession.objects.create(
            autor=user,
            estado_atual=ChatSession.ESTADO_VALIDACAO_FINAL,
            historico_mensagens=[
                {"role": "user", "content": "limpeza de rua e tapa buraco na Rua João Ribeiro 114"},
            ],
            demandas_rascunho=[
                {
                    "titulo": "Limpeza de Rua",
                    "descricao": "limpeza de rua na Rua João Ribeiro",
                    "servico_confirmado_usuario": True,
                    "sinapse_servico_id_sugerido": 999003,
                    "_revisao_etapa": "pedido",
                    "_titulo_anterior_revisao": "Limpeza de Rua",
                },
                {
                    "titulo": "Tapa Buraco",
                    "servico_confirmado_usuario": True,
                    "sinapse_servico_id_sugerido": 999001,
                    "endereco": {
                        "cep": "08810-220",
                        "logradouro": "Rua João Ribeiro",
                        "numero": 114,
                        "bairro": "Vila Suissa",
                    },
                    "latitude": -23.5123,
                    "longitude": -46.6234,
                    "local_confirmado_usuario": True,
                },
            ],
        )
        svc = ChatbotService()
        with patch.object(
            ChatbotService,
            "_buscar_candidatos_sinapse_item",
            return_value=[{"servico_id": 999002, "titulo": "Poda de árvore", "score": 0.9}],
        ):
            with patch(
                "core.services.chatbot_service.sinapse_catalog.servico_existe",
                return_value=True,
            ):
                out = svc.interagir(
                    usuario=user,
                    session_id=str(session.id),
                    mensagem="poda de arvore",
                )
        self.assertIn("assunto mudou", (out.get("resposta_agente") or "").lower())
        self.assertTrue(out.get("demandas_extraidas"))

    @override_settings(GROQ_API_KEY="test-key")
    def test_revisao_poda_preserva_assunto_apos_confirmar_servico(self):
        user = Usuario.objects.create_user(username="rev_poda", password="x", perfil="VEREADOR")
        session = ChatSession.objects.create(
            autor=user,
            estado_atual=ChatSession.ESTADO_COLETA_DADOS,
            historico_mensagens=[
                {"role": "user", "content": "limpeza de rua e tapa buraco"},
            ],
            demandas_rascunho=[
                {
                    "titulo": "poda de arvore",
                    "descricao": "poda de arvore",
                    "pedido_integral": "poda de arvore",
                    "texto_para_embedding": "poda de arvore",
                    "_eixo_pedido": "meio_ambiente_poda",
                    "candidatos_sinapse": [
                        {"servico_id": 999001, "titulo": "Tapa Buraco", "score": 0.99},
                        {"servico_id": 999002, "titulo": "Poda de árvore", "score": 0.95},
                    ],
                },
                {
                    "titulo": "Tapa Buraco",
                    "servico_confirmado_usuario": True,
                    "sinapse_servico_id_sugerido": 999001,
                },
            ],
        )
        svc = ChatbotService()
        with patch(
            "core.services.chatbot_service.sinapse_catalog.servico_existe",
            return_value=True,
        ):
            with patch(
                "core.services.chatbot_service.sinapse_catalog.get_servico",
            ) as mock_svc:
                mock_svc.return_value = type(
                    "S",
                    (),
                    {"titulo": "Solicitação de poda de árvores em área pública"},
                )()
                with patch(
                    "core.services.chatbot_service.sinapse_catalog.get_orgao_id_for_servico",
                    return_value=1,
                ):
                    with patch(
                        "core.services.chatbot_service.gestao_operacional_para_copiloto",
                        return_value=None,
                    ):
                        out = svc.confirmar_servico_demanda(
                            usuario=user,
                            session_id=str(session.id),
                            indice_demanda=0,
                            sinapse_servico_id=999002,
                        )
        session.refresh_from_db()
        item = session.demandas_rascunho[0]
        row = out["demandas_extraidas"][0]
        self.assertEqual(item.get("titulo"), "poda de arvore")
        self.assertEqual(row.get("titulo"), "poda de arvore")
        self.assertEqual(item.get("_eixo_pedido"), "meio_ambiente_poda")
        self.assertEqual(
            row.get("servico", {}).get("nome"),
            "Solicitação de poda de árvores em área pública",
        )

    @override_settings(GROQ_API_KEY="test-key")
    def test_confirmar_local_revisao_persiste_endereco_e_coords(self):
        user = Usuario.objects.create_user(username="rev_loc3", password="x", perfil="VEREADOR")
        session = ChatSession.objects.create(
            autor=user,
            estado_atual=ChatSession.ESTADO_COLETA_ENDERECO,
            historico_mensagens=[
                {
                    "role": "user",
                    "content": "solicito limpeza de rua e tapa buraco na Rua João Ribeiro, 114, Vila Suissa",
                },
            ],
            demandas_rascunho=[
                {
                    "titulo": "Limpeza de Rua",
                    "descricao": "Solicitação de limpeza de rua na Rua João Ribeiro, 114, Vila Suissa.",
                    "pedido_integral": "solicito limpeza de rua e tapa buraco na Rua João Ribeiro, 114, Vila Suissa",
                    "servico_confirmado_usuario": True,
                    "sinapse_servico_id_sugerido": 127,
                    "endereco": dict(_ENDERECO_VAZIO),
                    "_revisao_etapa": "local",
                },
                {
                    "titulo": "Tapa Buraco",
                    "servico_confirmado_usuario": True,
                    "sinapse_servico_id_sugerido": 80,
                    "endereco": {
                        "cep": "08810-220",
                        "logradouro": "Rua João Ribeiro",
                        "numero": 114,
                        "bairro": "Vila Suissa",
                    },
                    "latitude": -23.494491,
                    "longitude": -46.147018,
                    "coordenadas_fonte": "viacep_logradouro",
                    "local_confirmado_usuario": True,
                    "endereco_informado_usuario": True,
                },
            ],
        )
        svc = ChatbotService()
        with patch(
            "core.services.chatbot_service.sinapse_catalog.servico_existe",
            return_value=True,
        ):
            out = svc.interagir(
                usuario=user,
                session_id=str(session.id),
                mensagem="confirmar local solicitação 1",
            )
        session.refresh_from_db()
        item0 = session.demandas_rascunho[0]
        row0 = out["demandas_extraidas"][0]
        self.assertTrue(item0.get("local_confirmado_usuario"))
        self.assertEqual(item0["endereco"].get("logradouro"), "Rua João Ribeiro")
        self.assertEqual(item0["endereco"].get("bairro"), "Vila Suissa")
        self.assertIsNotNone(item0.get("latitude"))
        self.assertEqual(row0["endereco"].get("logradouro"), "Rua João Ribeiro")
        self.assertIsNotNone(row0.get("latitude"))
        self.assertTrue(out.get("revisao_encerrada"))
