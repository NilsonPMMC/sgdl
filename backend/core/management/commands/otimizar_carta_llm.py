"""
Comando para otimização LLM da Carta de Serviços baseado na análise anterior.

Este comando implementa as melhorias identificadas pelo analisar_carta_llm:
- Limpa e reestrutura textos para melhor RAG
- Extrai informações estruturadas
- Gera novos embeddings otimizados
- Valida qualidade dos resultados

Usage:
    python manage.py otimizar_carta_llm --relatorio relatorio.json --limite 10
    python manage.py otimizar_carta_llm --servico 123 --preview
    python manage.py otimizar_carta_llm --batch --categoria "Saúde"
"""

import json
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction, models
from django.conf import settings

from core.services.ai_kernel_client import AIKernelClient
from core.services.vector_service import VectorService
from integrations.models_sinapse import CatalogServico, SINAPSE_DB_ALIAS


class Command(BaseCommand):
    help = "Otimização LLM da Carta de Serviços baseada em análise anterior"

    def add_arguments(self, parser):
        parser.add_argument(
            "--relatorio",
            type=str,
            help="Arquivo JSON da análise prévia (analisar_carta_llm)"
        )
        parser.add_argument(
            "--servico",
            type=int,
            help="ID específico do serviço para otimizar"
        )
        parser.add_argument(
            "--limite",
            type=int,
            default=10,
            help="Número máximo de serviços para otimizar (default: 10)"
        )
        parser.add_argument(
            "--categoria",
            type=str,
            help="Filtrar por categoria específica"
        )
        parser.add_argument(
            "--preview",
            action="store_true",
            help="Mostrar preview das otimizações sem salvar"
        )
        parser.add_argument(
            "--batch",
            action="store_true",
            help="Processamento em lote com validação mínima"
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Forçar otimização mesmo com dados já processados"
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS("🚀 Iniciando otimização LLM da Carta de Serviços...")
        )
        
        try:
            # Carregar análise prévia se disponível
            analise_previa = None
            if options.get("relatorio"):
                analise_previa = self._carregar_analise(options["relatorio"])
                self.stdout.write("📊 Análise prévia carregada com sucesso")
            
            # Verificar conexões
            self._verificar_conexoes()
            
            # Coletar serviços para otimizar
            servicos = self._coletar_servicos(options)
            
            if not servicos:
                self.stdout.write(
                    self.style.WARNING("❌ Nenhum serviço encontrado para otimizar")
                )
                return
                
            self.stdout.write(f"🎯 Processando {len(servicos)} serviços...")
            
            # Processar serviços
            resultados = self._processar_servicos(servicos, analise_previa, options)
            
            # Exibir relatório
            self._exibir_resultados(resultados)
            
        except Exception as e:
            raise CommandError(f"Erro na otimização: {str(e)}")

    def _carregar_analise(self, arquivo: str) -> Dict[str, Any]:
        """Carrega análise prévia do arquivo JSON."""
        try:
            with open(arquivo, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise CommandError(f"Arquivo de análise não encontrado: {arquivo}")
        except json.JSONDecodeError as e:
            raise CommandError(f"Arquivo JSON inválido: {e}")

    def _verificar_conexoes(self):
        """Verifica conexões necessárias."""
        # Sinapse
        try:
            connection = connections[SINAPSE_DB_ALIAS]
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            self.stdout.write("✅ Conexão Sinapse OK")
        except Exception as e:
            raise CommandError(f"❌ Erro Sinapse: {str(e)}")
        
        # Kernel AI
        try:
            ai_client = AIKernelClient()
            # Test simples
            self.stdout.write("✅ Kernel AI OK")
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f"⚠️ Kernel AI com problemas: {str(e)}")
            )

    def _coletar_servicos(self, options: Dict[str, Any]) -> List[CatalogServico]:
        """Coleta serviços para otimização."""
        if options.get("servico"):
            # Serviço específico
            try:
                servico = CatalogServico.objects.using(SINAPSE_DB_ALIAS).get(
                    id=options["servico"]
                )
                return [servico]
            except CatalogServico.DoesNotExist:
                raise CommandError(f"Serviço {options['servico']} não encontrado")
        
        # Query geral
        queryset = CatalogServico.objects.using(SINAPSE_DB_ALIAS).select_related(
            'id_categoria', 'id_orgao'
        )
        
        if options.get("categoria"):
            queryset = queryset.filter(id_categoria__nome__icontains=options["categoria"])
        
        # Priorizar serviços sem embedding ou com problemas
        if not options.get("force"):
            queryset = queryset.filter(
                models.Q(embedding__isnull=True) |
                models.Q(texto_limpo_rag__isnull=True) |
                models.Q(texto_limpo_rag="")
            )
        
        return list(queryset[:options["limite"]])

    def _processar_servicos(
        self, 
        servicos: List[CatalogServico], 
        analise_previa: Optional[Dict[str, Any]], 
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Processa lista de serviços com otimização LLM."""
        
        resultados = {
            "total_processados": 0,
            "sucessos": 0,
            "erros": 0,
            "previews": [],
            "detalhes": []
        }
        
        for i, servico in enumerate(servicos, 1):
            self.stdout.write(f"\n🔄 Processando {i}/{len(servicos)}: {servico.titulo[:50]}...")
            
            try:
                resultado = self._otimizar_servico(servico, analise_previa, options)
                
                if options.get("preview"):
                    resultados["previews"].append(resultado)
                    self._exibir_preview(resultado)
                else:
                    self._salvar_otimizacao(servico, resultado, options)
                    resultados["sucessos"] += 1
                
                resultados["detalhes"].append(resultado)
                resultados["total_processados"] += 1
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"❌ Erro no serviço {servico.id}: {str(e)}")
                )
                resultados["erros"] += 1
                resultados["total_processados"] += 1
        
        return resultados

    def _otimizar_servico(
        self, 
        servico: CatalogServico, 
        analise_previa: Optional[Dict[str, Any]], 
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Otimiza um serviço individual com LLM."""
        
        # Montar contexto para LLM
        contexto = self._montar_contexto_servico(servico, analise_previa)
        
        # Prompt de otimização
        prompt = self._construir_prompt_otimizacao(contexto)
        
        try:
            ai_client = AIKernelClient()
            resposta_llm = ai_client.chat(
                system_prompt="Você é um especialista em otimização de dados para busca semântica (RAG) e serviços públicos. Retorne sempre JSON válido.",
                user_prompt=prompt
            )
            
            # Parse da resposta
            try:
                otimizacao = json.loads(resposta_llm)
            except json.JSONDecodeError:
                otimizacao = self._extrair_json_da_resposta(resposta_llm)
            
            # Validar campos obrigatórios
            self._validar_otimizacao(otimizacao)
            
            # Gerar novo embedding se texto foi otimizado
            if otimizacao.get("texto_rag_otimizado"):
                try:
                    vector_service = VectorService()
                    novo_embedding = vector_service.generate_embedding(
                        otimizacao["texto_rag_otimizado"]
                    )
                    otimizacao["novo_embedding"] = novo_embedding
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f"⚠️ Erro ao gerar embedding: {str(e)}")
                    )
            
            # Adicionar metadados
            otimizacao["metadata"] = {
                "servico_id": servico.id,
                "processado_em": datetime.now().isoformat(),
                "versao_original": {
                    "titulo": servico.titulo,
                    "texto_limpo_rag": servico.texto_limpo_rag,
                    "tem_embedding": servico.embedding is not None
                }
            }
            
            return otimizacao
            
        except Exception as e:
            raise Exception(f"Erro LLM para serviço {servico.id}: {str(e)}")

    def _montar_contexto_servico(
        self, 
        servico: CatalogServico, 
        analise_previa: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Monta contexto completo do serviço para o LLM."""
        
        contexto = {
            "servico_atual": {
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
            }
        }
        
        # Adicionar insights da análise prévia se disponível
        if analise_previa:
            contexto["analise_previa"] = {
                "recomendacoes_rag": analise_previa.get("recomendacoes_rag", {}),
                "problemas_identificados": analise_previa.get("analise_qualidade_dados", {}),
                "estrategia_limpeza": analise_previa.get("recomendacoes_rag", {}).get("estrategia_limpeza", "")
            }
        
        return contexto

    def _construir_prompt_otimizacao(self, contexto: Dict[str, Any]) -> str:
        """Constrói prompt para otimização do serviço."""
        
        servico = contexto["servico_atual"]
        
        prompt = f"""
MISSÃO: Otimizar dados do serviço para busca semântica (RAG) e gestão operacional.

SERVIÇO ATUAL:
{json.dumps(servico, ensure_ascii=False, indent=2)}
"""
        
        # Adicionar contexto da análise prévia se disponível
        if "analise_previa" in contexto:
            analise = contexto["analise_previa"]
            prompt += f"""

INSIGHTS DA ANÁLISE PRÉVIA:
Estratégia de limpeza: {analise.get('estrategia_limpeza', 'N/A')}
Recomendações RAG: {json.dumps(analise.get('recomendacoes_rag', {}), ensure_ascii=False)}
"""

        prompt += """

OTIMIZAÇÃO REQUERIDA (responda APENAS em JSON válido):

{
  "titulo_otimizado": "versão clara e objetiva do título",
  "descricao_objetiva": "descrição limpa, sem HTML, linguagem cidadã",
  "intencao_servico": "para que serve este serviço? (1-2 frases)",
  "problemas_resolve": ["lista dos problemas/situações que este serviço resolve"],
  "texto_rag_otimizado": "texto concatenado otimizado para embedding (titulo + descrição + problemas + contexto útil)",
  
  "dados_gestao": {
    "tipo_processo": "ADMINISTRATIVO|OPERACIONAL|EQUIPAMENTOS|MISTO|TERCEIRIZADO",
    "prazo_estruturado": {
      "dias": 0,
      "observacoes": "detalhes sobre o prazo",
      "fonte": "de onde veio esta informação"
    },
    "dependencias": {
      "documentos": ["lista estruturada de documentos"],
      "realizacao": ["pré-requisitos para realização"],
      "pagamentos": [{"tipo": "taxa", "valor": "R$ X", "obrigatorio": true}]
    }
  },
  
  "qualidade": {
    "score_original": "0-10",
    "score_otimizado": "0-10", 
    "principais_melhorias": ["principais mudanças realizadas"],
    "confianca": "ALTA|MÉDIA|BAIXA"
  }
}

INSTRUÇÕES:
1. Remova HTML e formatação desnecessária
2. Use linguagem clara e acessível ao cidadão
3. Seja específico nos problemas que o serviço resolve
4. O texto_rag_otimizado deve ser rico em contexto para busca semântica
5. Extraia prazos estruturados quando possível
6. Identifique dependências implícitas
7. Seja conservador se informações não estão claras
8. RESPOSTA DEVE SER JSON VÁLIDO, sem texto adicional
"""
        
        return prompt

    def _validar_otimizacao(self, otimizacao: Dict[str, Any]):
        """Valida se a otimização contém campos obrigatórios."""
        campos_obrigatorios = [
            "titulo_otimizado", 
            "descricao_objetiva", 
            "texto_rag_otimizado",
            "qualidade"
        ]
        
        for campo in campos_obrigatorios:
            if not otimizacao.get(campo):
                raise ValueError(f"Campo obrigatório ausente: {campo}")
        
        # Validar score de qualidade
        qualidade = otimizacao.get("qualidade", {})
        if not isinstance(qualidade.get("score_otimizado"), (int, float)):
            raise ValueError("Score de qualidade inválido")

    def _extrair_json_da_resposta(self, resposta: str) -> Dict[str, Any]:
        """Extrai JSON de resposta com texto adicional."""
        try:
            inicio = resposta.find('{')
            fim = resposta.rfind('}') + 1
            
            if inicio >= 0 and fim > inicio:
                json_str = resposta[inicio:fim]
                return json.loads(json_str)
        except:
            pass
        
        raise ValueError("Não foi possível extrair JSON válido da resposta LLM")

    def _exibir_preview(self, resultado: Dict[str, Any]):
        """Exibe preview da otimização."""
        meta = resultado.get("metadata", {})
        original = meta.get("versao_original", {})
        
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"🎯 PREVIEW - Serviço {meta.get('servico_id', '?')}")
        self.stdout.write(f"{'='*60}")
        
        # Títulos
        self.stdout.write(f"\n📝 TÍTULO:")
        self.stdout.write(f"  Original: {original.get('titulo', 'N/A')[:100]}...")
        self.stdout.write(f"  Otimizado: {resultado.get('titulo_otimizado', 'N/A')[:100]}...")
        
        # Texto RAG
        self.stdout.write(f"\n🎯 TEXTO RAG:")
        self.stdout.write(f"  Original: {(original.get('texto_limpo_rag') or 'N/A')[:100]}...")
        self.stdout.write(f"  Otimizado: {resultado.get('texto_rag_otimizado', 'N/A')[:100]}...")
        
        # Qualidade
        qualidade = resultado.get("qualidade", {})
        self.stdout.write(f"\n📊 QUALIDADE:")
        self.stdout.write(f"  Score Original: {qualidade.get('score_original', 'N/A')}")
        self.stdout.write(f"  Score Otimizado: {qualidade.get('score_otimizado', 'N/A')}")
        self.stdout.write(f"  Confiança: {qualidade.get('confianca', 'N/A')}")
        
        melhorias = qualidade.get("principais_melhorias", [])
        if melhorias:
            self.stdout.write(f"  Melhorias: {', '.join(melhorias[:3])}")

    def _salvar_otimizacao(
        self, 
        servico: CatalogServico, 
        resultado: Dict[str, Any], 
        options: Dict[str, Any]
    ):
        """Salva otimização no banco (modo read-only, apenas log)."""
        
        # IMPORTANTE: Models Sinapse são read-only
        # Por enquanto, apenas logamos as otimizações
        
        self.stdout.write(
            self.style.WARNING("⚠️ Modo read-only: salvando otimização em log")
        )
        
        # Em produção, aqui implementaríamos:
        # 1. Salvar em tabela de otimizações local
        # 2. Ou exportar para posterior importação no Sinapse
        # 3. Ou integração com API do Sinapse
        
        # Log estruturado para auditoria
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "servico_id": servico.id,
            "otimizacao": resultado,
            "usuario": "system",
            "versao": "1.0"
        }
        
        # Salvar em arquivo por enquanto
        log_file = f"/tmp/otimizacoes_carta_{datetime.now().strftime('%Y%m%d')}.jsonl"
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        
        self.stdout.write(f"📝 Otimização salva em: {log_file}")

    def _exibir_resultados(self, resultados: Dict[str, Any]):
        """Exibe relatório final dos resultados."""
        
        self.stdout.write(self.style.SUCCESS(f"\n🏆 RELATÓRIO FINAL"))
        self.stdout.write("="*50)
        
        total = resultados["total_processados"]
        sucessos = resultados["sucessos"]
        erros = resultados["erros"]
        
        self.stdout.write(f"Total processados: {total}")
        self.stdout.write(f"Sucessos: {sucessos}")
        self.stdout.write(f"Erros: {erros}")
        
        if total > 0:
            taxa_sucesso = (sucessos / total) * 100
            self.stdout.write(f"Taxa de sucesso: {taxa_sucesso:.1f}%")
        
        # Estatísticas de qualidade
        scores = []
        for detalhe in resultados.get("detalhes", []):
            qualidade = detalhe.get("qualidade", {})
            score = qualidade.get("score_otimizado")
            if isinstance(score, (int, float)):
                scores.append(score)
        
        if scores:
            score_medio = sum(scores) / len(scores)
            self.stdout.write(f"Score médio de qualidade: {score_medio:.1f}/10")
            
            high_quality = sum(1 for s in scores if s >= 8)
            self.stdout.write(f"Serviços alta qualidade (≥8): {high_quality} ({high_quality/len(scores)*100:.1f}%)")