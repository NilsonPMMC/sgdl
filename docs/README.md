# Documentação SGDL — índice mestre

**Fonte única de gestão** do projeto SGDL (Sistema de Gestão de Demandas Legislativas).  
Use este arquivo como ponto de entrada; documentos históricos ficam em [`arquivo/`](arquivo/README.md).

**Última reorganização:** 2026-06-10 · **Roadmap operacional:** Onda 3 C1–C6 concluídos; homologação H1/H2

---

## Comece aqui

| Documento | Para quê |
|-----------|----------|
| [**PROJETO.md**](PROJETO.md) | O que é o SGDL, arquitetura, IA (Kernel vs Groq), monorepo, comandos úteis |
| [**ROADMAP.md**](ROADMAP.md) | Status consolidado, prioridades atuais, links para trilhas de evolução |
| [**OPERACAO.md**](OPERACAO.md) | Homologação, deploy, sync Sinapse, evidências de go-live |

---

## Roadmap e evolução

| Documento | Escopo |
|-----------|--------|
| [**ROADMAP_PRODUTO.md**](ROADMAP_PRODUTO.md) | **Canônico** — fases 1–6 (Copiloto, Carta, Tendências, Clusters, Gov.br) com checklist `[x]`/`[~]`/`[ ]` |
| [**especificacoes/onda2-polimento-ux.md**](especificacoes/onda2-polimento-ux.md) | **Onda 2** — painel ofício, numeração, tramitações vereador, UX dashboard/demanda, acessos (P6–P14) |
| [**especificacoes/carta-consulta-evolucao.md**](especificacoes/carta-consulta-evolucao.md) | **Onda 3** — prazo padrão carta, vínculo setor, embedding + tendências, hub de consulta por perfil (C1–C4) |
| [**especificacoes/modulo-usuarios-perfis.md**](especificacoes/modulo-usuarios-perfis.md) | **U1–U5** — perfis, vínculos e hub `/gestao-usuarios` |
| [**especificacoes/carta-assuntos-utilizacao-unidades.md**](especificacoes/carta-assuntos-utilizacao-unidades.md) | **Onda 3 C5–C6** — assuntos temáticos, modo protocolável/informativo, importação RM271698 |
| [arquivo/infra/ROADMAP_SGDL_SERVIDOR_APIS_LLM.md](arquivo/infra/ROADMAP_SGDL_SERVIDOR_APIS_LLM.md) | Trilha infra/API/LLM (Sprints 1–7 concluídas em abr/2026) — referência histórica |
| [arquivo/infra/EVOLUCAO_SINAPSE_MOVA.md](arquivo/infra/EVOLUCAO_SINAPSE_MOVA.md) | Análise comparativa SGDL × MOVA (contexto de UX e IA) |
| [arquivo/carta-otimizacao/](arquivo/carta-otimizacao/) | Roadmap e relatórios da otimização RAG da carta (concluído mai/2026) |

---

## APIs e contratos

| Documento | Escopo |
|-----------|--------|
| [apis/tendencias.md](apis/tendencias.md) | API de tendências (malha fina fora da carta) |
| [apis/copiloto-faq.md](apis/copiloto-faq.md) | FAQ de competência municipal no Copiloto |
| [apis/fluxo-protocolo.md](apis/fluxo-protocolo.md) | API fluxo AUTO/MANUAL por serviço (`/fluxo-servicos/`) |

Código de referência: `backend/core/urls.py`, `backend/integrations/urls.py`.

---

## Operação e homologação

| Documento | Escopo |
|-----------|--------|
| [operacao/importacao-unidades-rm271698.md](operacao/importacao-unidades-rm271698.md) | **C6** — import RM271698, de-para, comandos |
| [operacao/rm271698-ids-duplicados-conferencia.md](operacao/rm271698-ids-duplicados-conferencia.md) | Conferência: 45 IDs duplicados na planilha (1 191 linhas → 1 120 únicos) |
| [operacao/runbook-sync-sinapse.md](operacao/runbook-sync-sinapse.md) | Rotina de sincronização Sinapse |
| [operacao/fluxo-auto-manual.md](operacao/fluxo-auto-manual.md) | **Onda 2 P3** — fluxo Protocolo AUTO/MANUAL, Copiloto, `SINAPSE_AUTOFILL_THRESHOLD` |
| [operacao/ops/](operacao/ops/) | Exemplos cron/systemd para sync |

Regras do agente Cursor (homologação e evolução Sinapse): `.cursor/rules/`.

---

## Arquivo histórico

| Pasta | Conteúdo |
|-------|----------|
| [arquivo/sprints/](arquivo/sprints/) | Checklists diários e execução Sprints 1–7 (abr/2026) |
| [arquivo/carta-otimizacao/](arquivo/carta-otimizacao/) | Relatórios de execução da base otimizada |
| [arquivo/correcoes-frontend/](arquivo/correcoes-frontend/) | Notas de correção Carta Explorer |

Detalhes: [arquivo/README.md](arquivo/README.md).

---

## Mapa rápido do repositório

```
sgdl/
├── backend/          # Django — API, Copiloto, triagem, integrações
├── frontend/         # Vue 3 + PrimeVue
├── docs/             # ← você está aqui
│   ├── README.md     # índice mestre
│   ├── PROJETO.md
│   ├── ROADMAP.md
│   ├── ROADMAP_PRODUTO.md
│   ├── apis/
│   ├── operacao/
│   └── arquivo/
└── README.md         # atalho técnico (IA, .env, comandos)
```

---

## Como manter esta documentação

1. **Status de produto** → atualizar `ROADMAP.md` (resumo) e `ROADMAP_PRODUTO.md` (detalhe por fase).
2. **Nova API** → adicionar em `docs/apis/` e linkar neste índice.
3. **Procedimento operacional** → `docs/operacao/`.
4. **Sprint/checklist encerrado** → mover para `docs/arquivo/` em vez de duplicar na raiz.
5. **Não criar** novos `ROADMAP_*.md` soltos na raiz — estender os documentos canônicos acima.
