# SGDL — Sistema de Gestão de Demandas Legislativas

Monorepo do SGDL (backend Django + frontend Vue). Configuração sensível fica em `backend/.env` (não versionado); use `backend/.env.example` como referência.

**Documentação (fonte única):** [docs/README.md](docs/README.md) — projeto, roadmap, operação e APIs.

**Status (jun/2026):** ciclo legislativo ponta a ponta no SGDL (sem SEI); homologação operacional em andamento — ver [docs/ROADMAP.md](docs/ROADMAP.md).

## Arquitetura de IA (embeddings vs LLM)

O SGDL separa **busca semântica** (vetores) de **chat/extração** (LLM). Não use o endpoint de chat do Kernel/Ollama para o copiloto ou para otimização RAG em lote — esses fluxos usam a **Groq API**.

| Função | Serviço | Variável (`.env`) |
|--------|---------|-------------------|
| **Embeddings** (547 serviços, triagem vetorial, pgvector) | Kernel em `192.168.10.50:8004` | `AI_KERNEL_BASE_URL` |
| **LLM chat** (copiloto, extração JSON, otimização RAG em lote) | Groq API | `GROQ_API_KEY` |

### Variáveis relacionadas

**Kernel (embeddings)**

- `AI_KERNEL_BASE_URL` — base HTTP do Kernel (ex.: `http://192.168.10.50:8004`)
- `AI_KERNEL_EMBEDDING_MODEL` — modelo de embedding (ex.: `mxbai-embed-large`)

**Groq (LLM)**

- `GROQ_API_KEY` — chave em [console.groq.com](https://console.groq.com/keys)
- `GROQ_BASE_URL` — padrão: `https://api.groq.com/openai/v1/chat/completions`
- `GROQ_MODEL` — modelo de chat (ex.: `llama-3.1-8b-instant`)

**Carta otimizada / triagem**

- `USAR_BASE_SERVICOS_OTIMIZADA=True` — triagem via `ServicoOtimizado` local
- `COPILOTO_CARTA_SCORE_MINIMO` — limiar mínimo de similaridade para candidatos na UI (ex.: `0.6666`)

### Onde cada peça é usada no código

| Componente | Embeddings | LLM (Groq) |
|------------|------------|------------|
| Triagem / copiloto (`VectorService`, `TriagemOtimizadaService`) | Kernel | — |
| Chat do copiloto (`ChatbotService`) | Kernel | Groq |
| Otimização RAG em lote (`otimizar_texto_llm_real`) | Kernel (regenera vetor após texto) | Groq (gera texto RAG) |
| Templates RAG determinísticos (`otimizar_texto_inteligente`, `carta_rag_builder`) | Kernel | — |

### Comandos úteis

```bash
cd backend

# Templates por categoria + embedding (massa)
python manage.py otimizar_texto_inteligente --forcar-todos --versao-alvo 3.2

# Long tail genéricos via Groq + embedding Kernel
python manage.py otimizar_texto_llm_real --apenas-genericos --todos --force

# Validar retrieval (frases-teste → top-K)
python manage.py validar_triagem_carta --limite 50
python manage.py testar_triagem_otimizada --casos-criticos
```

Documentação complementar: [docs/PROJETO.md](docs/PROJETO.md), [docs/ROADMAP.md](docs/ROADMAP.md), [docs/OPERACAO.md](docs/OPERACAO.md).
