"""Trilha A′ — Ouvidoria (O1)."""

from django.test import SimpleTestCase, override_settings

from core.services.copiloto_ouvidoria import (
    FONTE_AGENTE,
    FONTE_COMBINADA,
    FONTE_LEITURA_AUTOMATICA,
    SUBTIPO_DENUNCIA,
    SUBTIPO_ELOGIO,
    SUBTIPO_RECLAMACAO,
    SUBTIPO_SUGESTAO,
    detectar_teoria_ouvidoria,
    orientacao_ouvidoria,
)


class CopilotoOuvidoriaTests(SimpleTestCase):
    def test_elogio_detectado(self):
        texto = "Gostaria de registrar um elogio ao atendimento da Secretaria de Obras."
        det = detectar_teoria_ouvidoria(texto)
        self.assertIsNotNone(det)
        self.assertEqual(det["subtipo"], SUBTIPO_ELOGIO)

    def test_elogio_bem_atendido(self):
        texto = "Fui bem atendido no PAC e estou satisfeito com o serviço prestado."
        det = detectar_teoria_ouvidoria(texto)
        self.assertIsNotNone(det)
        self.assertEqual(det["subtipo"], SUBTIPO_ELOGIO)

    def test_reclamacao_atendimento(self):
        texto = "Quero fazer uma reclamação sobre a demora no atendimento da ouvidoria."
        det = detectar_teoria_ouvidoria(texto)
        self.assertIsNotNone(det)
        self.assertEqual(det["subtipo"], SUBTIPO_RECLAMACAO)

    def test_reclamacao_omissao(self):
        texto = "Quero demonstrar minha insatisfação com a omissão da prefeitura no retorno."
        det = detectar_teoria_ouvidoria(texto)
        self.assertIsNotNone(det)
        self.assertEqual(det["subtipo"], SUBTIPO_RECLAMACAO)

    def test_denuncia_irregularidade(self):
        texto = "Quero comunicar a ocorrência de um ato ilícito na secretaria."
        det = detectar_teoria_ouvidoria(texto)
        self.assertIsNotNone(det)
        self.assertEqual(det["subtipo"], SUBTIPO_DENUNCIA)

    def test_sugestao_totem_pac_mesmo_com_instalar(self):
        texto = (
            "registro uma sugestão para atendimentos no PAC, "
            "para que instale um toten de auto atendimento"
        )
        det = detectar_teoria_ouvidoria(texto, llm_teoria=False)
        self.assertIsNotNone(det)
        self.assertEqual(det["subtipo"], SUBTIPO_SUGESTAO)

    def test_sugestao_melhoria_servicos(self):
        texto = "Tenho uma proposta de melhoria dos serviços públicos no posto de atendimento."
        det = detectar_teoria_ouvidoria(texto)
        self.assertIsNotNone(det)
        self.assertEqual(det["subtipo"], SUBTIPO_SUGESTAO)

    def test_buraco_nao_e_ouvidoria(self):
        texto = "Solicito reparo de buraco na Rua das Flores, bairro Centro."
        self.assertIsNone(detectar_teoria_ouvidoria(texto))

    def test_lombada_nao_e_ouvidoria(self):
        texto = "Solicito instalação de lombada na Av. Principal, 100."
        self.assertIsNone(detectar_teoria_ouvidoria(texto))

    def test_llm_teoria_true_forca_trilha(self):
        texto = "Registro formal de manifestação sobre processo administrativo."
        det = detectar_teoria_ouvidoria(texto, llm_teoria=True, llm_subtipo="sugestao")
        self.assertIsNotNone(det)
        self.assertEqual(det["subtipo"], "sugestao")

    def test_llm_teoria_false_nao_bloqueia_sugestao_explicita(self):
        texto = "Registro uma sugestão para melhorar o atendimento no PAC."
        det = detectar_teoria_ouvidoria(texto, llm_teoria=False)
        self.assertIsNotNone(det)
        self.assertEqual(det["subtipo"], SUBTIPO_SUGESTAO)

    @override_settings(COPILOTO_OUVIDORIA_SINAPSE_SERVICO_ID=13)
    def test_servico_padrao_13(self):
        det = detectar_teoria_ouvidoria("Quero registrar um elogio à prefeitura.")
        self.assertEqual(det["servico_sinapse_id"], 13)

    def test_orientacao_por_subtipo(self):
        self.assertIn("elogio", orientacao_ouvidoria(SUBTIPO_ELOGIO).lower())
        self.assertIn("reclamação", orientacao_ouvidoria(SUBTIPO_RECLAMACAO).lower())
        self.assertIn("sugestão", orientacao_ouvidoria(SUBTIPO_SUGESTAO).lower())
        self.assertIn("denúncia", orientacao_ouvidoria(SUBTIPO_DENUNCIA).lower())

    def test_fonte_agente_quando_llm_define_subtipo(self):
        det = detectar_teoria_ouvidoria(
            "Registro formal de manifestação.",
            llm_teoria=True,
            llm_subtipo="sugestao",
        )
        self.assertEqual(det["fonte_classificacao"], FONTE_AGENTE)
        self.assertIn("Agente", det["detalhe_fonte"])

    def test_fonte_combinada_quando_agente_negou_e_leitura_corrigiu(self):
        texto = "Registro uma sugestão para melhorar o atendimento no PAC."
        det = detectar_teoria_ouvidoria(texto, llm_teoria=False)
        self.assertEqual(det["fonte_classificacao"], FONTE_COMBINADA)
        self.assertIn("Agente", det["detalhe_fonte"])
        self.assertIn("leitura automática", det["detalhe_fonte"])

    def test_fonte_leitura_automatica_sem_agente(self):
        det = detectar_teoria_ouvidoria("Gostaria de registrar um elogio ao atendimento.")
        self.assertEqual(det["fonte_classificacao"], FONTE_LEITURA_AUTOMATICA)
        self.assertIsNone(det["agente_subtipo"])

    def test_mensagens_sem_termos_tecnicos(self):
        det = detectar_teoria_ouvidoria(
            "Registro uma sugestão para melhorar o atendimento no PAC.",
            llm_teoria=False,
        )
        blob = f"{det['detalhe_fonte']} {det['motivo']}".lower()
        self.assertNotIn("groq", blob)
        self.assertNotIn("regex", blob)
        self.assertNotIn("backend", blob)
