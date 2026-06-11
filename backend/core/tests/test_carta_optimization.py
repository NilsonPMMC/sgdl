# /var/www/sgdl/backend/core/tests/test_carta_optimization.py

"""
Testes específicos para casos problemáticos identificados na análise da carta de serviços.
Valida as melhorias implementadas no sistema de otimização.
"""

import unittest
from django.test import TestCase
from unittest.mock import Mock, patch

from core.services import CartaOptimizerService, TextOptimizationResult, PrazoInfo
from core.services.embedding_service import EmbeddingOptimizationService


class TestCartaOptimizerService(TestCase):
    """Testes para o serviço de otimização da carta."""
    
    def setUp(self):
        self.optimizer = CartaOptimizerService()
    
    def test_limpeza_html_residual(self):
        """Testa limpeza de HTML residual identificado como problema crítico."""
        
        # Caso real problemático: HTML mal formatado
        texto_com_html = """
        <p><br></p>
        <p>Serviço para solicitação de &nbsp;licença&amp;gt;</p>
        <p></p><br><br>
        <p>Documentos necessários:</p>
        """
        
        texto_limpo, problemas = self.optimizer.limpar_html_residual(texto_com_html)
        
        # Verificar se limpou corretamente
        self.assertNotIn('<p>', texto_limpo)
        self.assertNotIn('<br>', texto_limpo)
        self.assertNotIn('&nbsp;', texto_limpo)
        self.assertNotIn('&amp;', texto_limpo)
        
        # Verificar se identificou problemas
        self.assertIn("HTML residual detectado", problemas)
        self.assertIn("Entidades HTML não convertidas", problemas)
        
        # Verificar conteúdo preservado
        self.assertIn("Serviço para solicitação", texto_limpo)
        self.assertIn("licença", texto_limpo)
        self.assertIn("Documentos necessários", texto_limpo)
    
    def test_extracao_prazo_estruturado(self):
        """Testa estruturação de prazos que estavam em texto livre."""
        
        casos_teste = [
            # (texto_prazo, categoria_esperada, dias_esperados)
            ("imediato", "IMEDIATO", 0),
            ("até 30 dias", "NORMAL", 30), 
            ("30 dias úteis", "NORMAL", 30),
            ("5 a 10 dias", "NORMAL", 10),  # Deve usar o máximo
            ("conforme demanda", "INDEFINIDO", None),
            ("conforme análise técnica", "LONGO", 30),
            ("rápido processamento", "RAPIDO", 5),
            ("prazo indefinido", "INDEFINIDO", None),
        ]
        
        for texto_prazo, categoria_esperada, dias_esperados in casos_teste:
            with self.subTest(texto_prazo=texto_prazo):
                prazo_info = self.optimizer.extrair_prazo_estruturado(texto_prazo)
                
                self.assertEqual(prazo_info.categoria, categoria_esperada)
                self.assertEqual(prazo_info.dias_numericos, dias_esperados)
                self.assertEqual(prazo_info.texto_original, texto_prazo)
    
    def test_extracao_palavras_chave(self):
        """Testa extração de palavras-chave para enriquecer embeddings."""
        
        titulo = "Licença de Funcionamento para Estabelecimentos"
        descricao = """
        Autorização para funcionamento de estabelecimentos comerciais, 
        industriais e de serviços no município. Necessária para empresários 
        que desejam abrir ou transferir seu negócio.
        """
        
        palavras_chave = self.optimizer.extrair_palavras_chave_contexto(titulo, descricao)
        
        # Verificar palavras importantes extraídas
        self.assertIn("licença", palavras_chave)
        self.assertIn("funcionamento", palavras_chave)
        self.assertIn("estabelecimentos", palavras_chave)
        self.assertIn("comerciais", palavras_chave)
        
        # Verificar sinônimos adicionados
        self.assertTrue(
            any(sinonimo in palavras_chave for sinonimo in ["autorização", "permissão", "alvará"])
        )
    
    def test_estruturacao_texto_rag_casos_problematicos(self):
        """Testa casos específicos que falhavam na busca (receita de bolo → recolhimento animais)."""
        
        # Caso 1: Serviço que deveria ser sobre recolhimento de animais
        servico_recolhimento = {
            'titulo': 'Requerimento para Recolhimento de Animais em Via Pública',
            'descricao_html': '<p>Serviço destinado ao recolhimento de animais abandonados ou perdidos nas vias públicas do município.</p>',
            'requisitos_html': '<p>Solicitação do munícipe ou verificação da fiscalização</p>',
            'prazo_estruturado': PrazoInfo(2, 'RAPIDO', 'até 2 dias', 'Conforme disponibilidade da equipe'),
            'palavras_chave': ['recolhimento', 'animais', 'via', 'pública', 'abandonados', 'perdidos', 'fiscalização']
        }
        
        texto_otimizado = self.optimizer.estruturar_texto_rag(servico_recolhimento)
        
        # Verificar estrutura PROBLEMA/SOLUÇÃO/CONTEXTO
        self.assertIn("PROBLEMA:", texto_otimizado)
        self.assertIn("SOLUÇÃO:", texto_otimizado)
        self.assertIn("CONTEXTO:", texto_otimizado)
        self.assertIn("PRAZO:", texto_otimizado)
        
        # Verificar conteúdo específico sobre animais
        self.assertIn("animais", texto_otimizado.lower())
        self.assertIn("recolhimento", texto_otimizado.lower())
        self.assertIn("via pública", texto_otimizado.lower())
        
        # Não deve conter nada sobre receita ou bolo
        self.assertNotIn("receita", texto_otimizado.lower())
        self.assertNotIn("bolo", texto_otimizado.lower())
    
    def test_inferencia_problema_cidadao(self):
        """Testa inferência de problemas que o cidadão está tentando resolver."""
        
        casos_teste = [
            (
                "Licença de Funcionamento Comercial",
                "descrição sobre estabelecimento",
                "autorização oficial para abrir"
            ),
            (
                "Certidão de Tempo de Serviço", 
                "certifica período trabalhado",
                "comprovar uma situação"
            ),
            (
                "Segunda Via de Alvará",
                "nova via de documento perdido", 
                "Perdi um documento oficial"
            ),
            (
                "Vistoria Técnica Sanitária",
                "verificação das condições", 
                "verificação técnica oficial"
            ),
        ]
        
        for titulo, descricao, problema_esperado_parte in casos_teste:
            with self.subTest(titulo=titulo):
                problema = self.optimizer._inferir_problema_cidadao(titulo, descricao)
                
                self.assertTrue(len(problema) > 0, f"Deveria inferir problema para: {titulo}")
                self.assertIn(problema_esperado_parte.lower(), problema.lower())
    
    def test_otimizacao_servico_completa(self):
        """Testa otimização completa de um serviço com múltiplos problemas."""
        
        # Serviço com todos os problemas identificados
        servico_problematico = {
            'titulo': 'Requerimento de Licença de Funcionamento',  # Título técnico
            'descricao_html': '<p><br></p><p>Licença para &nbsp;estabelecimentos</p><p></p>',  # HTML mal formatado
            'requisitos_html': '<p>Documentos&amp;gt; RG, CPF</p>',  # HTML + entidades
            'prazo': 'conforme demanda',  # Prazo não estruturado
            'texto_limpo_rag': 'Requerimento licença funcionamento estabelecimentos documentos',  # Texto pobre
            'departamento': 'Secretaria de Desenvolvimento',
            'orgao': 'Prefeitura Municipal',
            'categoria': 'Licenças e Alvarás'
        }
        
        resultado = self.optimizer.otimizar_servico(servico_problematico)
        
        # Verificar tipo do resultado
        self.assertIsInstance(resultado, TextOptimizationResult)
        
        # Verificar identificação de problemas
        self.assertTrue(len(resultado.problemas_encontrados) > 0)
        self.assertIn("Prazo não estruturado", resultado.problemas_encontrados)
        
        # Verificar melhorias aplicadas
        self.assertTrue(len(resultado.melhorias_aplicadas) > 0)
        self.assertTrue(any("palavras-chave" in m for m in resultado.melhorias_aplicadas))
        
        # Verificar enriquecimento do texto
        self.assertGreater(len(resultado.texto_otimizado), len(servico_problematico['texto_limpo_rag']))
        
        # Verificar estrutura do texto otimizado
        self.assertIn("PROBLEMA:", resultado.texto_otimizado)
        self.assertIn("SOLUÇÃO:", resultado.texto_otimizado)
        self.assertIn("CONTEXTO:", resultado.texto_otimizado)
        
        # Verificar metadados extraídos
        self.assertIn('prazo_estruturado', resultado.metadados_extraidos)
        self.assertIn('palavras_chave', resultado.metadados_extraidos)
        self.assertIn('publico_alvo_inferido', resultado.metadados_extraidos)
        self.assertIn('tipo_processo_inferido', resultado.metadados_extraidos)
        
        # Score deve ser calculado
        self.assertGreaterEqual(resultado.score_qualidade, 1)
        self.assertLessEqual(resultado.score_qualidade, 10)


class TestEmbeddingOptimizationService(TestCase):
    """Testes para o serviço de otimização de embeddings."""
    
    def setUp(self):
        self.service = EmbeddingOptimizationService()
    
    @patch('integrations.models_sinapse.CatalogServico.objects')
    def test_busca_servicos_problematicos(self, mock_objects):
        """Testa identificação automática de serviços problemáticos."""
        
        # Mock de serviços com diferentes tipos de problemas
        mock_servicos = [
            {
                'id': 1,
                'titulo': 'Requerimento de Licença',  # Título técnico = +1
                'texto_limpo_rag': '<p>HTML residual</p>',  # HTML = +3
                'prazo': 'conforme demanda',  # Prazo não estruturado = +2
                'descricao_html': '<div><p><span>HTML complexo</span></p></div>'  # HTML complexo = +1
                # Total: 7 pontos
            },
            {
                'id': 2, 
                'titulo': 'Solicitar Certidão',  # Título OK
                'texto_limpo_rag': 'Texto muito curto',  # Texto curto = +2
                'prazo': 'imediato',  # Prazo OK
                'descricao_html': 'Descrição simples'
                # Total: 2 pontos
            },
            {
                'id': 3,
                'titulo': 'Serviço Normal',  # Título OK
                'texto_limpo_rag': 'Texto adequado com conteúdo suficiente para análise',  # Texto OK
                'prazo': '30 dias',  # Prazo OK
                'descricao_html': 'Descrição normal'
                # Total: 0 pontos
            }
        ]
        
        # Configurar mock
        mock_objects.using.return_value.filter.return_value.values.return_value.__getitem__ = lambda _, slice_obj: mock_servicos[slice_obj]
        
        # Executar busca
        ids_problematicos = self.service.buscar_servicos_problematicos(limite=10)
        
        # Verificar ordenação por prioridade (maior score primeiro)
        self.assertEqual(len(ids_problematicos), 2)  # Apenas os com problemas
        self.assertEqual(ids_problematicos[0], 1)  # Serviço com mais problemas primeiro
        self.assertEqual(ids_problematicos[1], 2)  # Segundo mais problemático
    
    def test_simulacao_embedding_deterministica(self):
        """Testa que a simulação de embedding é determinística."""
        
        texto_teste = "Licença de funcionamento para estabelecimentos comerciais"
        
        # Gerar embedding duas vezes
        embedding1 = self.service._simular_embedding_otimizado(texto_teste)
        embedding2 = self.service._simular_embedding_otimizado(texto_teste)
        
        # Devem ser idênticos (determinístico)
        import numpy as np
        np.testing.assert_array_equal(embedding1, embedding2)
        
        # Verificar dimensões
        self.assertEqual(len(embedding1), 1024)
        
        # Verificar normalização
        norm = np.linalg.norm(embedding1)
        self.assertAlmostEqual(norm, 1.0, places=5)
    
    def test_calculo_similaridade(self):
        """Testa cálculo de similaridade entre embeddings."""
        
        # Embeddings similares (mesmo texto)
        texto1 = "licença de funcionamento"
        embedding1 = self.service._simular_embedding_otimizado(texto1)
        embedding2 = self.service._simular_embedding_otimizado(texto1)
        
        similaridade_identica = self.service._calcular_similaridade(embedding1, embedding2)
        self.assertAlmostEqual(similaridade_identica, 1.0, places=5)
        
        # Embeddings diferentes
        texto2 = "recolhimento de animais"
        embedding3 = self.service._simular_embedding_otimizado(texto2)
        
        similaridade_diferente = self.service._calcular_similaridade(embedding1, embedding3)
        self.assertLess(similaridade_diferente, 1.0)
        self.assertGreater(similaridade_diferente, -1.0)
    
    def test_validacao_relevancia_servicos(self):
        """Testa validação de relevância entre queries e serviços."""
        
        # Mock de serviço sobre licença
        servico_licenca = Mock()
        servico_licenca.titulo = "Licença de Funcionamento para Estabelecimentos"
        servico_licenca.descricao_html = "Autorização para funcionamento de estabelecimentos comerciais"
        
        # Queries relevantes
        self.assertTrue(self.service._e_relevante_para_servico("licença para empresa", servico_licenca))
        self.assertTrue(self.service._e_relevante_para_servico("alvará de funcionamento", servico_licenca))
        
        # Queries irrelevantes  
        self.assertFalse(self.service._e_relevante_para_servico("receita de bolo", servico_licenca))
        self.assertFalse(self.service._e_relevante_para_servico("recolhimento animais", servico_licenca))
    
    def test_casos_problematicos_especificos(self):
        """Testa os casos específicos que falhavam (receita de bolo → recolhimento animais)."""
        
        # Simular serviço de recolhimento de animais
        servico_animais = Mock()
        servico_animais.titulo = "Recolhimento de Animais em Via Pública"
        servico_animais.descricao_html = "Serviço para recolher animais abandonados ou perdidos nas ruas"
        
        # Query irrelevante não deve ter alta similaridade
        self.assertFalse(self.service._e_relevante_para_servico("receita de bolo", servico_animais))
        
        # Queries relevantes devem ter alta similaridade
        self.assertTrue(self.service._e_relevante_para_servico("recolhimento animais", servico_animais))
        self.assertTrue(self.service._e_relevante_para_servico("animal perdido", servico_animais))
        
        # Simular diferença nos embeddings
        embedding_receita = self.service._simular_embedding_otimizado("receita de bolo")
        embedding_animais = self.service._simular_embedding_otimizado("recolhimento de animais na via pública")
        
        similaridade = self.service._calcular_similaridade(embedding_receita, embedding_animais)
        
        # Deve ser baixa similaridade (< 0.7, que era o problema identificado)
        self.assertLess(similaridade, 0.7, "Receita de bolo não deveria ter alta similaridade com recolhimento de animais")


class TestIntegracaoCompleta(TestCase):
    """Testes de integração entre os serviços."""
    
    def setUp(self):
        self.optimizer_service = CartaOptimizerService()
        self.embedding_service = EmbeddingOptimizationService()
    
    def test_fluxo_otimizacao_completo(self):
        """Testa fluxo completo de otimização de um serviço."""
        
        # Dados de entrada com problemas típicos
        servico_data = {
            'id': 999,
            'titulo': 'Requerimento para Licença de Funcionamento',
            'descricao_html': '<p><br></p><p>Licença necessária para &nbsp;estabelecimentos</p>',
            'requisitos_html': '<p>Documentos: RG, CPF, comprovante</p>',
            'prazo': 'conforme análise',
            'texto_limpo_rag': 'requerimento licença funcionamento estabelecimentos',
            'departamento': 'Secretaria de Desenvolvimento',
            'orgao': 'Prefeitura',
            'categoria': 'Licenças'
        }
        
        # Executar otimização
        resultado = self.optimizer_service.otimizar_servico(servico_data)
        
        # Verificar melhorias foram aplicadas
        self.assertIsInstance(resultado, TextOptimizationResult)
        self.assertTrue(len(resultado.melhorias_aplicadas) > 0)
        self.assertGreater(len(resultado.texto_otimizado), len(servico_data['texto_limpo_rag']))
        
        # Verificar estruturação do texto
        texto_otimizado = resultado.texto_otimizado
        self.assertIn("PROBLEMA:", texto_otimizado)
        self.assertIn("SOLUÇÃO:", texto_otimizado)
        
        # Verificar que problema específico foi inferido corretamente
        self.assertIn("autorização", texto_otimizado.lower())
        self.assertIn("estabelecimento", texto_otimizado.lower())
        
        # Verificar metadados estruturados
        metadados = resultado.metadados_extraidos
        self.assertIn('prazo_estruturado', metadados)
        self.assertEqual(metadados['prazo_estruturado']['categoria'], 'LONGO')  # "conforme análise" → LONGO
        
        # Verificar público-alvo inferido
        self.assertIn('publico_alvo_inferido', metadados)
        self.assertIn('empresários', metadados['publico_alvo_inferido'])
        
        # Verificar tipo de processo
        self.assertIn('tipo_processo_inferido', metadados)
        self.assertEqual(metadados['tipo_processo_inferido'], 'administrativo_licenca')
    
    def test_prevencao_casos_problematicos(self):
        """Testa se as otimizações previnem os casos problemáticos identificados."""
        
        casos_teste = [
            {
                'nome': 'Recolhimento de Animais',
                'servico': {
                    'titulo': 'Recolhimento de Animais Abandonados',
                    'descricao_html': 'Serviço municipal para recolher animais perdidos ou abandonados',
                    'palavras_esperadas': ['animal', 'recolhimento', 'abandono'],
                    'palavras_proibidas': ['receita', 'bolo', 'culinária']
                }
            },
            {
                'nome': 'Licença Comercial', 
                'servico': {
                    'titulo': 'Licença de Funcionamento Comercial',
                    'descricao_html': 'Autorização para abertura de estabelecimento comercial',
                    'palavras_esperadas': ['licença', 'comercial', 'estabelecimento'],
                    'palavras_proibidas': ['animal', 'recolhimento']
                }
            }
        ]
        
        for caso in casos_teste:
            with self.subTest(caso=caso['nome']):
                servico_data = {
                    **caso['servico'],
                    'requisitos_html': '',
                    'prazo': 'até 30 dias',
                    'texto_limpo_rag': '',
                    'departamento': '',
                    'orgao': '',
                    'categoria': ''
                }
                
                # Otimizar serviço
                resultado = self.optimizer_service.otimizar_servico(servico_data)
                texto_otimizado = resultado.texto_otimizado.lower()
                
                # Verificar palavras esperadas estão presentes
                for palavra in caso['servico']['palavras_esperadas']:
                    self.assertIn(palavra, texto_otimizado, 
                                f"Palavra '{palavra}' deve estar no texto otimizado de {caso['nome']}")
                
                # Verificar palavras proibidas não estão presentes
                for palavra in caso['servico']['palavras_proibidas']:
                    self.assertNotIn(palavra, texto_otimizado,
                                   f"Palavra '{palavra}' NÃO deve estar no texto otimizado de {caso['nome']}")


if __name__ == '__main__':
    unittest.main()