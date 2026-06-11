# 🚀 Roadmap de Otimização da Carta de Serviços

## Objetivo
Otimizar a qualidade dos dados da Carta de Serviços no Sinapse para alcançar ~100% de eficácia na busca semântica, estruturando informações essenciais para gestão operacional.

## Problemas Identificados

### 1. Qualidade dos Embeddings
- Campo `texto_limpo_rag` com dados mal estruturados
- HTML mal formatado misturado com texto útil
- Descrições genéricas que não capturam a essência do serviço

### 2. Informações Fragmentadas
- `descricao_html` misturado com formatação
- `prazo` em texto livre inconsistente
- Documentos necessários em texto corrido sem estrutura
- Tipo de processo não categorizado

### 3. Inconsistências Operacionais
- Serviços sem prazo definido ou desatualizados
- Dependências implícitas não mapeadas
- Informações de taxas/pagamentos dispersas

## Pilares de Informação

### 🎯 Para Busca Semântica (RAG)
- **Descrição Objetiva**: Linguagem clara, sem HTML/jargões
- **Intenção Real do Serviço**: "Para que serve este serviço?"
- **Problemas que Resolve**: Lista estruturada de situações atendidas
- **Texto RAG Otimizado**: Concatenação inteligente para embedding

### 📊 Para Gestão Operacional
- **Tipo de Processo**: Administrativo, Operacional, Equipamentos, Misto, Terceirizado
- **Prazo Estruturado**: Dias + observações + data de atualização
- **Dependências de Realização**: ["vistoria_tecnica", "aprovacao_superior"]
- **Dependências de Documentos**: Lista estruturada
- **Dependências de Pagamentos**: {tipo, valor, obrigatorio}

## Estratégia de Implementação

### Abordagem: LLM-First Analysis
1. **Extensão do Schema Atual** - novos campos sem quebrar o existente
2. **Análise com LLM** - deixar a IA identificar carências e estruturar dados
3. **Enriquecimento Paralelo** - dados limpos convivem com originais
4. **Switch Controlado** - migração quando qualidade atingir 90%+
5. **Rollback Seguro** - possibilidade de voltar ao sistema anterior

## 🚀 Roadmap de Execução

### **Fase 1: LLM Analysis & Schema Design (1 sprint)**
- **1.1** Desenvolver agente LLM para análise da base atual
- **1.2** LLM identifica padrões, carências e oportunidades
- **1.3** Schema otimizado baseado na análise do LLM
- **1.4** Casos de teste definidos pelo próprio agente

### **Fase 2: Enriquecimento Inteligente (2 sprints)**
- **2.1** Pipeline LLM para limpeza e estruturação automática
- **2.2** Prompts especializados por tipo de serviço
- **2.3** Validação humana assistida em interface web
- **2.4** Feedback loop para refinamento contínuo

### **Fase 3: Nova Base Otimizada (1 sprint)**
- **3.1** Modelo estendido com campos otimizados
- **3.2** Migração Django com dados enriquecidos
- **3.3** Regeneração completa de embeddings
- **3.4** A/B testing: busca atual vs otimizada

### **Fase 4: Gestão Operacional (2 sprints)**
- **4.1** Dashboard de qualidade da carta
- **4.2** Alertas para dados desatualizados
- **4.3** Pipeline de atualização contínua
- **4.4** Métricas de performance RAG

### **Fase 5: Monitoramento Contínuo (ongoing)**
- **5.1** Score de similaridade > 0.9 em casos de teste
- **5.2** 95% dos serviços com dados estruturados
- **5.3** Pipeline automatizado de qualidade
- **5.4** Auditoria mensal com LLM

## Critérios de Sucesso

### Para RAG (Busca Semântica)
- [ ] Score de similaridade > 0.9 em casos de teste
- [ ] 100% dos serviços com `texto_rag_otimizado`
- [ ] Redução > 80% em falsos negativos
- [ ] Tempo de resposta < 200ms

### Para Gestão Operacional
- [ ] 95% dos serviços com prazos estruturados
- [ ] 90% com tipo de processo definido
- [ ] 85% com dependências mapeadas
- [ ] Dashboard operacional funcional

## Arquitetura Técnica

### Novos Modelos
```python
class ServicoEnhanced:
    # RAG Otimizado
    titulo_claro = CharField(max_length=200)
    descricao_objetiva = TextField()
    intencao_servico = TextField()
    problemas_resolve = JSONField()
    texto_rag_otimizado = TextField()
    
    # Gestão Operacional
    tipo_processo = CharField(choices=TIPOS_PROCESSO)
    prazo_dias = PositiveIntegerField()
    prazo_observacoes = TextField(blank=True)
    prazo_atualizado_em = DateTimeField()
    dependencias_realizacao = JSONField()
    dependencias_documentos = JSONField()
    dependencias_pagamentos = JSONField()
```

### Pipeline LLM
1. **Input**: Dados brutos do Sinapse
2. **Processing**: Prompt especializado por categoria
3. **Output**: Dados estruturados + qualidade score
4. **Validation**: Interface humana para aprovação
5. **Storage**: Base otimizada + tracking de versões

## Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| LLM gera dados incorretos | Média | Alto | Validação humana + casos de teste |
| Performance degradada | Baixa | Médio | A/B testing + rollback |
| Resistência à mudança | Média | Baixo | Treinamento + demonstrações |
| Custo computacional LLM | Alta | Médio | Processamento em lotes + cache |

## Status Atual (2026-06-02)

| Fase | Status |
|------|--------|
| 1 – Schema e análise | Concluída |
| 2 – Enriquecimento | Parcial (templates v3; LLM servidor indisponível) |
| 3 – Base + embeddings | Concluída (547 serviços, pgvector) |
| 4 – Gestão operacional | Em andamento |
| 5 – Metas RAG (>0,9 casos-teste) | Em andamento |

### Critérios RAG — situação

- [x] 100% com `texto_rag_otimizado` e embedding
- [ ] Similaridade > 0,9 nos casos buraco/cratera/avenida
- [ ] `intencao_servico` e `problemas_resolve` preenchidos (Bloco 1 v3)
- [ ] Atendimento/sistema/link sincronizados do Sinapse (Bloco 3)

## Plano de Execução — 4 Blocos

### Bloco 1 — Excelência RAG + campos estruturados (prioridade)

- `carta_rag_builder.py` — templates por categoria (pavimentação, limpeza/varrição, iluminação, saneamento, animais, licenciamento, vegetação, saúde, transporte, tributo, genérico)
- **v3.1 em massa** — `otimizar_texto_inteligente --todos --versao-alvo 3.1` (job background, log `/tmp/sgdl_rag_v31.log`)
- Persistir `intencao_servico`, `problemas_resolve`, `palavras_chave`
- Regenerar embeddings a cada mudança de RAG

### Bloco 2 — Busca híbrida na triagem

- Expandir `SINONIMOS_SERVICOS` (buraco, reparo, acidente…)
- Score híbrido vetorial + lexical em `TriagemOtimizadaService`
- Suite `testar_triagem_otimizada` com casos do gabinete

### Bloco 3 — Sinapse → Admin

- `sincronizar_metadados_sinapse` → `tipos_atendimento`, `sistema_solicitacao`, `link_sistema`
- Fonte: `CatalogServico` (`id_tipo_atendimento`, `solicitacao_internet`, `solicitacao_perfil`)

### Bloco 4 — Homologação

- [x] `USAR_BASE_SERVICOS_OTIMIZADA=True` no `.env`
- [x] APIs `/carta-otimizada/` corrigidas (serializer + list paginado)
- [x] `CartaExplorerView` consumindo API real (`getCartaOtimizada*`)
- [ ] Reload Gunicorn em homologação/produção (confirmar após deploy)
- [ ] Teste manual no chatbot (3 frases buraco/cratera)
- [ ] `manage.py test` + `check --deploy` + build frontend em CI

---

**Última atualização**: 2026-06-02  
**Status**: Fase 3 concluída; reprocessamento **v3.1** em andamento (~547 serviços); triagem crítica OK (buraco/cratera ~0,99; sujeira na rua ~0,99)  
**Responsável**: Equipe SGDL + IA Assistiva

### Comandos operacionais (v3.1)

```bash
# Acompanhar progresso
python manage.py shell -c "from core.models_carta_otimizada import ServicoOtimizado; print(ServicoOtimizado.objects.filter(versao_otimizacao='3.1').count())"
tail -f /tmp/sgdl_rag_v31.log

# Após concluir o job
python manage.py sincronizar_metadados_sinapse
sudo systemctl reload gunicorn-sgdl.service
python manage.py testar_triagem_otimizada --casos-criticos
```