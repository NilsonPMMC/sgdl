# SGDL — visão do projeto

**SGDL** (Sistema de Gestão de Demandas Legislativas) é o sistema do gabinete legislativo de Mogi das Cruzes para registrar, triar, protocolar e acompanhar demandas de zeladoria e serviços municipais, com apoio de IA assistiva e integração à **Carta de Serviços Sinapse**.

---

## Pilares atuais

| Pilar | Descrição |
|-------|-----------|
| **Operação legislativa** | Demandas, ofícios, perfis ([vereador, protocolo, secretaria, gestor](especificacoes/modulo-usuarios-perfis.md)), notificações, relatórios |
| **Carta Sinapse** | Catálogo oficial de serviços, triagem vetorial, reconciliação de sync |
| **Copiloto** | Chat conversacional: extração de pedido, escolha na carta, tendência, ofício em rascunho |
| **Inteligência** | Embeddings (Kernel), LLM (Groq), clusters geográficos/semânticos, mapa de calor |

Referência de evolução de produto: [ROADMAP_PRODUTO.md](ROADMAP_PRODUTO.md).

---

## Arquitetura técnica

Monorepo:

| Parte | Stack | Caminho |
|-------|-------|---------|
| Backend | Django + DRF + PostgreSQL (+ pgvector) | `backend/` |
| Frontend | Vue 3 + Vite + PrimeVue | `frontend/` |
| Config sensível | `.env` (não versionado) | `backend/.env.example` |

Bancos:

- **SGDL** — demandas, usuários, sessões do copiloto, tendências, clusters, carta otimizada local
- **Sinapse** (leitura) — `catalog_servico` e metadados da carta oficial

---

## IA: embeddings vs LLM

O SGDL **separa** busca semântica (vetores) de chat/extração (LLM).

| Função | Serviço | Variável (`.env`) |
|--------|---------|-------------------|
| **Embeddings** (triagem, pgvector, RAG) | Kernel (`AI_KERNEL_BASE_URL`) | `AI_KERNEL_EMBEDDING_MODEL` |
| **LLM** (copiloto JSON, otimização RAG em lote) | Groq API | `GROQ_API_KEY`, `GROQ_MODEL` |

**Não** usar endpoint de chat do Kernel/Ollama para o copiloto — o fluxo de chat usa Groq.

### Onde cada peça é usada

| Componente | Embeddings | LLM (Groq) |
|------------|------------|------------|
| `VectorService`, `TriagemOtimizadaService` | Kernel | — |
| `ChatbotService` (copiloto) | Kernel | Groq |
| `otimizar_texto_llm_real` | Kernel (após texto) | Groq |
| `otimizar_texto_inteligente`, templates RAG | Kernel | — |

### Variáveis relevantes (carta / copiloto)

- `USAR_BASE_SERVICOS_OTIMIZADA` — triagem via `ServicoOtimizado` local
- `COPILOTO_CARTA_SCORE_MINIMO` — limiar UI carta forte (ex.: `0.6666`)
- `COPILOTO_CARTA_SCORE_DOMINIO` — limiar modo domínio (ex.: `0.40`)
- `COPILOTO_TENDENCIAS_ENABLED` — trilha tendência no copiloto

---

## Motor de decisão no Copiloto

| Trilha | Quando | Destino |
|--------|--------|---------|
| **Carta** | Match Sinapse ≥ limiar | Serviço + órgão → ofício |
| **Domínio** | Mesmo eixo (mobilidade, pavimentação…) sem match forte | Lista ampliada na carta ou tendência |
| **Tendência** | Fora da carta com confiança baixa | `Tendencia` + gestão Protocolo |
| **Recusa** | Fora de competência municipal | FAQ + encerramento sem ofício |

Código principal: `backend/core/services/chatbot_service.py`, `copiloto_dominio.py`, `triagem_otimizada_service.py`.  
UI: `frontend/src/views/CopilotoView.vue`.

O rascunho (`RASCUNHO`) após materialização no Copiloto é a **janela de revisão** — o vereador ajusta texto, serviço e endereço em `DemandaForm.vue` antes de «Enviar oficialmente».

---

## Comandos úteis (desenvolvimento)

```bash
cd backend

# Testes
python manage.py test --settings=config.settings_test
python manage.py check --deploy

# Carta otimizada / RAG
python manage.py otimizar_texto_inteligente --forcar-todos --versao-alvo 3.2
python manage.py otimizar_texto_llm_real --apenas-genericos --todos --force
python manage.py validar_triagem_carta --limite 50
python manage.py testar_triagem_otimizada --casos-criticos

# Sync Sinapse (ver runbook)
python manage.py sync_sinapse_services --incremental-sync
python manage.py sync_sinapse_services --sync-health-report
```

```bash
cd frontend
npm run build
```

---

## Documentação relacionada

- [ROADMAP.md](ROADMAP.md) — status e prioridades
- [OPERACAO.md](OPERACAO.md) — homologação e sync
- [apis/](apis/) — contratos HTTP
- [README.md](README.md) — índice completo
