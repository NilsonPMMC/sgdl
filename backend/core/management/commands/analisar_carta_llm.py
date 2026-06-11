"""
Comando para análise LLM da qualidade da Carta de Serviços.

O agente LLM analisa os dados atuais e identifica:
- Carências na estrutura de dados
- Oportunidades de otimização para RAG
- Padrões de qualidade por categoria
- Recomendações específicas para cada serviço

Usage:
    python manage.py analisar_carta_llm --limite 50 --categoria "Saúde"
    python manage.py analisar_carta_llm --detalhado --exportar relatorio.json
"""

import json
import sys
from datetime import datetime
from typing import Any, Dict, List

from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from core.services.ai_kernel_client import AIKernelClient
from integrations.models_sinapse import CatalogServico, CatalogCategoria, SINAPSE_DB_ALIAS


class Command(BaseCommand):
    help = "Análise LLM da qualidade da Carta de Serviços para otimização RAG"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limite",
            type=int,
            default=20,
            help="Número máximo de serviços para analisar (default: 20)"
        )
        parser.add_argument(
            "--categoria",
            type=str,
            help="Filtrar por categoria específica"
        )
        parser.add_argument(
            "--detalhado",
            action="store_true",
            help="Análise detalhada por serviço individual"
        )
        parser.add_argument(
            "--exportar",
            type=str,
            help="Exportar relatório para arquivo JSON"
        )
        parser.add_argument(
            "--sem-embedding",
            action="store_true",
            help="Focar apenas em serviços sem embedding"
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS("🤖 Iniciando análise LLM da Carta de Serviços...")
        )
        
        try:
            # Verificar conexão com Sinapse
            self._verificar_conexao_sinapse()
            
            # Coletar dados para análise
            servicos = self._coletar_servicos(options)
            
            if not servicos:
                self.stdout.write(
                    self.style.WARNING("❌ Nenhum serviço encontrado com os critérios especificados")
                )
                return
                
            self.stdout.write(f"📊 Analisando {len(servicos)} serviços...")
            
            # Análise com LLM
            relatorio = self._analisar_com_llm(servicos, options)
            
            # Exibir resultados
            self._exibir_relatorio(relatorio)
            
            # Exportar se solicitado
            if options.get("exportar"):
                self._exportar_relatorio(relatorio, options["exportar"])
                
        except Exception as e:
            raise CommandError(f"Erro na análise: {str(e)}")

    def _verificar_conexao_sinapse(self):
        """Verifica se a conexão com Sinapse está funcionando."""
        try:
            connection = connections[SINAPSE_DB_ALIAS]
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            self.stdout.write("✅ Conexão com Sinapse OK")
        except Exception as e:
            raise CommandError(f"❌ Erro de conexão com Sinapse: {str(e)}")

    def _coletar_servicos(self, options: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Coleta serviços para análise baseado nos filtros."""
        queryset = CatalogServico.objects.using(SINAPSE_DB_ALIAS).select_related(
            'id_categoria', 'id_orgao'
        )
        
        # Aplicar filtros
        if options.get("categoria"):
            queryset = queryset.filter(id_categoria__nome__icontains=options["categoria"])
            
        if options.get("sem_embedding"):
            queryset = queryset.filter(embedding__isnull=True)
            
        # Limitar resultado
        queryset = queryset[:options["limite"]]
        
        servicos = []
        for servico in queryset:
            dados = {
                "id": servico.id,
                "titulo": servico.titulo,
                "descricao_html": servico.descricao_html,
                "texto_limpo_rag": servico.texto_limpo_rag,
                "departamento": servico.departamento,
                "prazo": servico.prazo,
                "documentos_necessarios": servico.documentos_necessarios,
                "requisitos_html": servico.requisitos_html,
                "fluxo_html": servico.fluxo_html,
                "observacoes_html": servico.observacoes_html,
                "categoria": servico.id_categoria.nome if servico.id_categoria else None,
                "orgao": servico.id_orgao.nome if servico.id_orgao else None,
                "tem_embedding": servico.embedding is not None,
                "status": servico.status,
            }
            servicos.append(dados)
            
        return servicos

    def _analisar_com_llm(self, servicos: List[Dict[str, Any]], options: Dict[str, Any]) -> Dict[str, Any]:
        """Executa análise com LLM dos serviços coletados."""
        
        # Prompt especializado para análise
        prompt_analise = self._construir_prompt_analise(servicos, options.get("detalhado", False))
        
        try:
            ai_client = AIKernelClient()
            resposta_llm = ai_client.chat(
                system_prompt="Você é um especialista em otimização de dados para busca semântica (RAG) e gestão de serviços públicos.",
                user_prompt=prompt_analise
            )
            
            # Parse da resposta JSON
            try:
                analise = json.loads(resposta_llm)
            except json.JSONDecodeError:
                # Fallback: extrair JSON do texto
                analise = self._extrair_json_da_resposta(resposta_llm)
                
            # Adicionar metadados
            analise["metadata"] = {
                "timestamp": datetime.now().isoformat(),
                "total_servicos_analisados": len(servicos),
                "criterios_filtro": {k: v for k, v in options.items() if v},
            }
            
            return analise
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Erro na análise LLM: {str(e)}")
            )
            # Retornar análise básica manual em caso de erro
            return self._analise_basica_manual(servicos)

    def _construir_prompt_analise(self, servicos: List[Dict[str, Any]], detalhado: bool) -> str:
        """Constrói o prompt especializado para análise LLM."""
        
        # Amostrar alguns serviços para o prompt
        amostra = servicos[:5] if len(servicos) > 5 else servicos
        
        prompt = f"""
MISSÃO: Analisar {len(servicos)} serviços da Carta de Serviços para otimização de busca semântica (RAG).

CONTEXTO: Sistema público que usa embeddings para busca semântica de serviços. Precisamos identificar carências nos dados que prejudicam a qualidade da busca e sugerir melhorias estruturadas.

DADOS AMOSTRA (primeiros {len(amostra)} serviços):
{json.dumps(amostra, ensure_ascii=False, indent=2)}

ANÁLISE REQUERIDA (responda APENAS em JSON válido):

{{
  "resumo_executivo": {{
    "problemas_criticos": ["lista dos 3 principais problemas identificados"],
    "potencial_melhoria_rag": "percentual estimado de melhoria na busca (ex: 40%)",
    "prioridade_acao": "ALTA|MÉDIA|BAIXA"
  }},
  
  "analise_qualidade_dados": {{
    "campos_problematicos": {{
      "titulo": {{ "problemas": [], "sugestoes": [] }},
      "descricao_html": {{ "problemas": [], "sugestoes": [] }},
      "texto_limpo_rag": {{ "problemas": [], "sugestoes": [] }},
      "prazo": {{ "problemas": [], "sugestoes": [] }},
      "documentos_necessarios": {{ "problemas": [], "sugestoes": [] }}
    }},
    "campos_faltantes_criticos": ["campos que deveriam existir para melhor RAG"],
    "inconsistencias_detectadas": ["padrões inconsistentes encontrados"]
  }},
  
  "recomendacoes_rag": {{
    "estrutura_texto_otimizada": "como deveria ser estruturado o texto para embedding",
    "informacoes_essenciais": ["dados críticos que devem estar sempre presentes"],
    "informacoes_prejudiciais": ["dados que atrapalham a busca semântica"],
    "estrategia_limpeza": "abordagem recomendada para limpeza dos dados"
  }},
  
  "gestao_operacional": {{
    "tipos_processo_detectados": ["categorias de processo identificadas nos dados"],
    "padroes_prazo": "análise dos prazos encontrados",
    "dependencias_implicitas": ["dependências não explícitas mas identificáveis"],
    "gaps_informacionais": ["informações faltantes para gestão"]
  }},
  
  "plano_acao_priorizado": [
    {{
      "acao": "descrição da ação",
      "impacto_rag": "ALTO|MÉDIO|BAIXO", 
      "esforco": "ALTO|MÉDIO|BAIXO",
      "prioridade": 1
    }}
  ]
}}

INSTRUÇÕES ESPECÍFICAS:
1. Foque na otimização para busca semântica
2. Identifique padrões nos dados, não apenas problemas isolados  
3. Seja específico nas sugestões de melhoria
4. Considere a gestão operacional dos serviços públicos
5. Priorize ações por impacto vs esforço
6. RESPOSTA DEVE SER JSON VÁLIDO, sem texto adicional
"""

        if detalhado:
            prompt += f"""

ANÁLISE DETALHADA POR SERVIÇO (adicionar ao JSON):
  "analise_individual": [
    {{
      "id": id_do_servico,
      "titulo": "título",
      "problemas_especificos": [],
      "score_qualidade": "0-10",
      "texto_rag_sugerido": "versão otimizada do texto para embedding"
    }}
  ]
"""
        
        return prompt

    def _extrair_json_da_resposta(self, resposta: str) -> Dict[str, Any]:
        """Tenta extrair JSON de uma resposta que pode conter texto adicional."""
        try:
            # Procurar por JSON entre marcadores
            inicio = resposta.find('{')
            fim = resposta.rfind('}') + 1
            
            if inicio >= 0 and fim > inicio:
                json_str = resposta[inicio:fim]
                return json.loads(json_str)
        except:
            pass
        
        # Fallback: resposta estruturada básica
        return {
            "erro": "Não foi possível extrair JSON da resposta LLM",
            "resposta_bruta": resposta
        }

    def _analise_basica_manual(self, servicos: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Análise manual básica em caso de erro no LLM."""
        
        total = len(servicos)
        sem_embedding = sum(1 for s in servicos if not s.get("tem_embedding"))
        sem_prazo = sum(1 for s in servicos if not s.get("prazo"))
        
        return {
            "resumo_executivo": {
                "problemas_criticos": [
                    f"{sem_embedding} serviços sem embedding ({sem_embedding/total*100:.1f}%)",
                    f"{sem_prazo} serviços sem prazo definido ({sem_prazo/total*100:.1f}%)",
                    "Análise LLM falhou - dados limitados"
                ],
                "potencial_melhoria_rag": "Indeterminado (erro LLM)",
                "prioridade_acao": "ALTA"
            },
            "erro_llm": True,
            "estatisticas_basicas": {
                "total_servicos": total,
                "sem_embedding": sem_embedding,
                "sem_prazo": sem_prazo,
                "categorias_unicas": len(set(s.get("categoria") for s in servicos if s.get("categoria")))
            }
        }

    def _exibir_relatorio(self, relatorio: Dict[str, Any]):
        """Exibe o relatório formatado no terminal."""
        
        self.stdout.write(self.style.SUCCESS("\n🎯 RELATÓRIO DE ANÁLISE LLM"))
        self.stdout.write("=" * 60)
        
        # Resumo Executivo
        resumo = relatorio.get("resumo_executivo", {})
        self.stdout.write(self.style.WARNING(f"\n📋 RESUMO EXECUTIVO"))
        self.stdout.write(f"Prioridade: {resumo.get('prioridade_acao', 'N/A')}")
        self.stdout.write(f"Melhoria RAG estimada: {resumo.get('potencial_melhoria_rag', 'N/A')}")
        
        problemas = resumo.get("problemas_criticos", [])
        if problemas:
            self.stdout.write(f"\n🚨 PROBLEMAS CRÍTICOS:")
            for i, problema in enumerate(problemas, 1):
                self.stdout.write(f"  {i}. {problema}")
        
        # Recomendações RAG
        if "recomendacoes_rag" in relatorio:
            rag = relatorio["recomendacoes_rag"]
            self.stdout.write(self.style.SUCCESS(f"\n🎯 RECOMENDAÇÕES PARA RAG"))
            self.stdout.write(f"Estrutura otimizada: {rag.get('estrutura_texto_otimizada', 'N/A')}")
            
            if rag.get('informacoes_essenciais'):
                self.stdout.write(f"\n✅ INFORMAÇÕES ESSENCIAIS:")
                for info in rag['informacoes_essenciais']:
                    self.stdout.write(f"  • {info}")
                    
            if rag.get('informacoes_prejudiciais'):
                self.stdout.write(f"\n❌ INFORMAÇÕES PREJUDICIAIS:")
                for info in rag['informacoes_prejudiciais']:
                    self.stdout.write(f"  • {info}")
        
        # Plano de Ação
        if "plano_acao_priorizado" in relatorio:
            self.stdout.write(self.style.SUCCESS(f"\n📈 PLANO DE AÇÃO PRIORIZADO"))
            plano = relatorio["plano_acao_priorizado"]
            for acao in plano[:5]:  # Top 5 ações
                impacto = acao.get('impacto_rag', 'N/A')
                esforco = acao.get('esforco', 'N/A') 
                prio = acao.get('prioridade', '?')
                desc = acao.get('acao', 'N/A')
                self.stdout.write(f"  {prio}. {desc} (Impacto: {impacto}, Esforço: {esforco})")
        
        # Estatísticas (se análise manual)
        if relatorio.get("erro_llm"):
            self.stdout.write(self.style.ERROR(f"\n⚠️  ANÁLISE MANUAL (LLM indisponível)"))
            stats = relatorio.get("estatisticas_basicas", {})
            for key, value in stats.items():
                self.stdout.write(f"  {key}: {value}")

    def _exportar_relatorio(self, relatorio: Dict[str, Any], arquivo: str):
        """Exporta o relatório para arquivo JSON."""
        try:
            with open(arquivo, 'w', encoding='utf-8') as f:
                json.dump(relatorio, f, ensure_ascii=False, indent=2)
            self.stdout.write(
                self.style.SUCCESS(f"✅ Relatório exportado para: {arquivo}")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Erro ao exportar: {str(e)}")
            )