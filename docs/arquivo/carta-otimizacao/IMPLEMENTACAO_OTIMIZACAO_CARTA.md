# 📋 Implementação: Otimização da Carta de Serviços SGDL

## 🎯 Visão Geral

Esta implementação resolve os **problemas críticos identificados** na análise da carta de serviços, fornecendo melhorias práticas que podem ser executadas via Cursor Agent **sem dependência de LLM externo**.

## 🚨 Problemas Resolvidos

### 1. HTML Residual e Ruído no `texto_limpo_rag`
- ✅ **Solução**: Limpeza inteligente com padrões regex específicos
- ✅ **Local**: `CartaOptimizerService.limpar_html_residual()`
- ✅ **Resultado**: Remove `<p><br></p>`, entidades HTML, tags vazias

### 2. Títulos Técnicos Não Alinhados ao Cidadão  
- ✅ **Solução**: Inferência automática de problemas que o cidadão resolve
- ✅ **Local**: `CartaOptimizerService._inferir_problema_cidadao()`
- ✅ **Resultado**: Converte "Requerimento de X" → "Preciso de X para Y"

### 3. Embeddings Desalinhados (Score 0.73-0.75 para Irrelevantes)
- ✅ **Solução**: Texto RAG estruturado no formato PROBLEMA/SOLUÇÃO/CONTEXTO
- ✅ **Local**: `CartaOptimizerService.estruturar_texto_rag()`
- ✅ **Resultado**: Embeddings mais precisos e contextualizados

### 4. Prazos Não Estruturados
- ✅ **Solução**: Extração automática com categorização
- ✅ **Local**: `CartaOptimizerService.extrair_prazo_estruturado()`
- ✅ **Resultado**: IMEDIATO/RÁPIDO/NORMAL/LONGO + dias numéricos

### 5. Metadados Ricos Ignorados no Índice Vetorial
- ✅ **Solução**: Enriquecimento com palavras-chave, sinônimos e contexto
- ✅ **Local**: `CartaOptimizerService.extrair_palavras_chave_contexto()`
- ✅ **Resultado**: Até 20 palavras-chave expandidas por serviço

## 📁 Arquivos Implementados

### Core Services
```
backend/core/services/
├── __init__.py                 # Exports dos serviços
├── carta_optimizer.py          # Serviço principal de otimização
└── embedding_service.py        # Serviço de embeddings otimizados
```

### Management Commands
```
backend/core/management/commands/
├── otimizar_carta_servicos.py    # Comando principal de otimização
└── gerar_estatisticas_carta.py   # Comando para estatísticas
```

### Models e Estruturas
```
backend/core/
├── models_carta_metadata.py     # Modelos para metadados ricos
└── tests/test_carta_optimization.py  # Testes específicos
```

## 🔧 Funcionalidades Principais

### 1. Limpeza Inteligente de HTML
```python
# Remove HTML residual identificado como problema crítico
texto_limpo, problemas = optimizer.limpar_html_residual(texto_html)
# - Remove <p><br></p> vazios
# - Converte entidades HTML (&nbsp;, &amp;)  
# - Limpa tags malformadas
# - Preserva conteúdo relevante
```

### 2. Estruturação de Texto RAG
```python  
# Formato otimizado: PROBLEMA/SOLUÇÃO/CONTEXTO/PRAZO/PALAVRAS-CHAVE
texto_otimizado = optimizer.estruturar_texto_rag(servico_data)
# Exemplo de saída:
# "PROBLEMA: Preciso de autorização oficial para abrir meu negócio | 
#  SOLUÇÃO: Licença que autoriza funcionamento de estabelecimento comercial |
#  CONTEXTO: Para empresários que vão abrir novos negócios |
#  PRAZO: Até 30 dias | 
#  RELACIONADO: licença, autorização, alvará, estabelecimento"
```

### 3. Extração de Prazos Estruturados
```python
prazo_info = optimizer.extrair_prazo_estruturado("até 30 dias úteis")
# Resultado:
# PrazoInfo(
#   dias_numericos=30,
#   categoria='NORMAL', 
#   texto_original='até 30 dias úteis',
#   observacoes='Prazo padrão para análise'
# )
```

### 4. Enriquecimento com Sinônimos
```python
palavras_chave = optimizer.extrair_palavras_chave_contexto(titulo, descricao)
# Para "Licença de Funcionamento":
# ['licença', 'funcionamento', 'autorização', 'permissão', 'alvará']
```

## 🎮 Como Usar

### Comando Principal: Otimização
```bash
# 1. Preview das otimizações (sem aplicar)
python manage.py otimizar_carta_servicos --preview --limite 10

# 2. Aplicar otimizações com critério de qualidade
python manage.py otimizar_carta_servicos --aplicar --score-minimo 7

# 3. Focar nos serviços mais problemáticos
python manage.py otimizar_carta_servicos --problematicos --limite 20 --aplicar

# 4. Otimizar serviço específico
python manage.py otimizar_carta_servicos --servico-id 123 --aplicar --verbose

# 5. Validar qualidade após otimizações
python manage.py otimizar_carta_servicos --aplicar --validar --exportar relatorio.json
```

### Comando Auxiliar: Estatísticas
```bash
# Gerar estatísticas consolidadas
python manage.py gerar_estatisticas_carta

# Estatísticas de data específica  
python manage.py gerar_estatisticas_carta --data 2026-05-22
```

## 🧪 Casos de Teste Implementados

### Casos Problemáticos Específicos
✅ **Receita de bolo → Recolhimento de animais**: Teste que falha no sistema atual
✅ **HTML mal formatado**: `<p><br></p>` e entidades não convertidas  
✅ **Prazos em texto livre**: "conforme demanda", "até análise"
✅ **Títulos técnicos**: "Requerimento para X" → problema cidadão
✅ **Embeddings desalinhados**: Validação de separação relevante/irrelevante

### Exemplo de Teste
```python
def test_casos_problematicos_especificos(self):
    # Serviço que deveria ser sobre recolhimento de animais
    servico_recolhimento = {
        'titulo': 'Recolhimento de Animais em Via Pública',
        'descricao_html': 'Serviço para recolher animais abandonados',
        # ...
    }
    
    texto_otimizado = optimizer.estruturar_texto_rag(servico_recolhimento)
    
    # Deve conter palavras sobre animais
    self.assertIn("animais", texto_otimizado.lower())
    self.assertIn("recolhimento", texto_otimizado.lower())
    
    # NÃO deve conter nada sobre receita
    self.assertNotIn("receita", texto_otimizado.lower())
    self.assertNotIn("bolo", texto_otimizado.lower())
```

## 📊 Metadados Ricos Estruturados

### Modelo `ServicoMetadataRico`
```python
class ServicoMetadataRico(models.Model):
    sinapse_servico_id = models.BigIntegerField(unique=True)
    
    # Processo
    tipo_processo = models.CharField(choices=TIPO_PROCESSO_CHOICES)
    publico_alvo = ArrayField(models.CharField(...))
    canal_preferencial = models.CharField(...)
    
    # Prazo estruturado  
    prazo_dias_numericos = models.PositiveIntegerField(null=True)
    prazo_categoria = models.CharField(choices=CATEGORIA_PRAZO_CHOICES)
    
    # RAG otimizado
    problemas_resolve = ArrayField(models.TextField())
    palavras_chave_expandidas = ArrayField(models.CharField(...))
    texto_rag_otimizado = models.TextField()
    
    # Qualidade
    score_qualidade_texto = models.PositiveSmallIntegerField(default=5)
    tem_problemas_html = models.BooleanField(default=False)
```

## 🎯 Resultados Esperados

### Melhorias Quantificáveis
- ✅ **Limpeza HTML**: 100% dos casos `<p><br></p>` removidos
- ✅ **Prazos estruturados**: 80%+ dos prazos categorizados automaticamente  
- ✅ **Enriquecimento semântico**: 5-20 palavras-chave por serviço
- ✅ **Score de qualidade**: Melhoria média de 2-3 pontos (escala 1-10)

### Casos Críticos Resolvidos
- ✅ **"receita de bolo" → "recolhimento animais"**: Separação clara por contexto
- ✅ **HTML residual degradando embeddings**: Limpeza automática
- ✅ **Títulos técnicos**: Conversão para linguagem cidadã
- ✅ **Prazos "conforme demanda"**: Categorização INDEFINIDO + observações

## 🔄 Workflow de Execução

### 1. Análise Inicial
```bash
# Identificar serviços problemáticos
python manage.py otimizar_carta_servicos --problematicos --preview --limite 20
```

### 2. Otimização Gradual
```bash
# Aplicar em lotes pequenos primeiro
python manage.py otimizar_carta_servicos --aplicar --limite 10 --score-minimo 8

# Expandir conforme confiança
python manage.py otimizar_carta_servicos --aplicar --limite 50 --score-minimo 7
```

### 3. Validação e Ajustes
```bash
# Validar qualidade das otimizações
python manage.py otimizar_carta_servicos --validar --exportar validacao.json

# Gerar estatísticas de progresso
python manage.py gerar_estatisticas_carta
```

### 4. Monitoramento
```bash  
# Acompanhar evolução diária
python manage.py gerar_estatisticas_carta --data $(date +%Y-%m-%d)
```

## 🧪 Testes de Homologação

### Executar Suite de Testes
```bash
# Testes específicos de otimização
python manage.py test core.tests.test_carta_optimization

# Testes de casos problemáticos
python manage.py test core.tests.test_carta_optimization.TestCartaOptimizerService.test_casos_problematicos_especificos
```

### Evidências Esperadas
- ✅ **Todos os testes passando**: 0 falhas na suite
- ✅ **HTML limpo**: Remoção de 100% das tags problemáticas
- ✅ **Prazos estruturados**: Categorização correta dos padrões conhecidos
- ✅ **Separação semântica**: Queries irrelevantes com similaridade < 0.7

## 📈 Monitoramento de Qualidade

### Métricas de Acompanhamento
- **Score médio de qualidade**: Meta > 7.0
- **Percentual otimizado**: Meta > 80%
- **Casos problemáticos resolvidos**: Meta > 95%
- **Tempo de processamento**: Meta < 2 min para 50 serviços

### Alertas de Qualidade  
- Score médio abaixo de 6.0
- Mais de 20% com "necessita_revisao=True"
- Crescimento de problemas HTML residual
- Degradação na separação semântica

## 🎉 Conclusão

Esta implementação resolve **todos os 5 problemas críticos identificados** na análise anterior:

1. ✅ **HTML residual**: Limpeza inteligente automática
2. ✅ **Títulos técnicos**: Inferência de problemas cidadão  
3. ✅ **Embeddings desalinhados**: Estruturação PROBLEMA/SOLUÇÃO/CONTEXTO
4. ✅ **Prazos não estruturados**: Extração e categorização automática
5. ✅ **Metadados ignorados**: Enriquecimento com 20+ palavras-chave

**Pronto para execução em homologação** com evidências de testes e monitoramento de qualidade implementados.