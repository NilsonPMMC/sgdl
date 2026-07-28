# Roadmap consolidado — SGDL

Painel único de **status e prioridades**. O detalhamento por fase de produto está em [ROADMAP_PRODUTO.md](ROADMAP_PRODUTO.md).

**Atualizado:** 2026-06-18 · **Gate piloto:** **GO condicional** (Onda B em andamento) · Meta piloto: **2ª quinzena jun/2026**

> **Roadmap limpo de ajustes (jun/2026):** [ROADMAP-AJUSTES-HOMOLOGACAO-JUN2026.md](ROADMAP-AJUSTES-HOMOLOGACAO-JUN2026.md) — consolida entregas dev, revalidações P0 e ondas C/D/E para validação.

---

## Marco imediato

| Data / marco | Objetivo |
|--------------|----------|
| **Reunião de trabalho (2026-06-11)** | Realizada — 5 apontamentos · ver [operacao/reuniao-trabalho-jun2026.md](operacao/reuniao-trabalho-jun2026.md) |
| **Semana pós-reunião** | Ajustes A1–A5 + testes remotos em homologação — **concluído 2026-06-10** |
| **2ª quinzena jun/2026** | Piloto: 2 gabinetes + Protocolo + Gestão (+ possível Zeladoria/Serviços Urbanos) |
| **Onda B (pós-GO)** | B1–B9 — apontamentos Vereador + Protocolo (2026-06-13) |

**Gate piloto:** **GO condicional** — A1–A5 OK (2026-06-10); **Onda B** priorizada antes/durante piloto. Registro: [homologacao-e2e-registro.md](operacao/homologacao-e2e-registro.md) · [piloto-apontamentos-jun2026.md](operacao/piloto-apontamentos-jun2026.md).

---

## Resumo executivo

| Trilha | Status | Observação |
|--------|--------|------------|
| **Infra + Sinapse (Sprints 1–7)** | Concluída | Abr/2026 — sync, reconciliação, `SinapseReconciliacaoView` |
| **Carta otimizada (RAG)** | Concluída | Mai/2026 — `ServicoOtimizado`, triagem otimizada |
| **Copiloto** | **OK** | FAQ calibrada (A1); multi-pedido, painel Contexto, competência |
| **Relatórios gerenciais** | **OK** | SLA, process mining, funil, CSV, paginação server-side (Gestor) |
| **Mapa operacional** | **~ homologação** | Heatmap, agregação, filtros por perfil |
| **Layout / navegação** | **OK** | Menu por seções, sidebar recolhida, atalhos topbar |
| **Ciclo legislativo ponta a ponta** | **Concluído** | Assinatura → protocolo → operação → devolutiva → cidadão |
| **Protocolo + tramitação** | **~ homologação** | Painéis, fluxo AUTO, setores, Super OS, devolutiva entregues |
| **Assinatura envio oficial** | **Concluído** | Preview PDF (disco) + assinatura eletrônica + 1 anexo final |
| **Revisão assessor (P2)** | **Removido** | Rascunho pós-Copiloto substitui etapa formal (migração `0056`) |
| **Onda 2 (P1–P14)** | **Concluída** | Polimento UX e regras operacionais |
| **Cluster / Super OS v2** | **~ homologação** | Mesmo serviço + 300 m + coorte AUTO + UX por perfil |
| **Stand-by estudo/viabilidade** | **Fase 1 OK** | Registro na conclusão secretaria; fila executivo — ver [estudo-viabilidade-stand-by.md](especificacoes/estudo-viabilidade-stand-by.md) |

> Tramitação **100% no SGDL** — integração SEI/1Doc removida (migração `0049`).

---

## Status por fase de produto

Legenda: **OK** concluído · **~** parcial · **—** pendente

| Fase | Tema | Status | Destaques |
|------|------|--------|-----------|
| **1** | Infra vetorial (pgvector, embeddings) | **OK** | Migração 0028, Kernel mxbai-embed-large |
| **2** | Ingestão, Copiloto, Carta, Tendências | **OK** | Explorer, tendências, FAQ (A1) e KPIs trilha OK; SLA Celery pendente |
| **3** | Ofícios PDF e assinatura | **OK** | Envio oficial + assinaturas Protocolo/Secretaria (A3/A4) validadas |
| **4** | Clusters, Protocolo, setor, fluxo | **~** | Ciclo operacional + Super OS UX OK; RBAC Secretaria (A5) validado |
| **5** | Piloto 23 gabinetes / Gov.br | **—** | **Início previsto** 2ª quinzena jun/2026 (gate GO) |
| **6** | Encerramento legislativo | **OK** | Pacote devolutiva, ciência, ofício ao cidadão |

Checklist detalhado: [ROADMAP_PRODUTO.md](ROADMAP_PRODUTO.md).

---

## Prioridades — Onda 1 (homologação operacional, até sexta-feira)

Foco: **validação E2E por perfil** (gate A1) e consolidação de observações UX antes do piloto.

| # | Entrega | Status | Ref. |
|---|---------|--------|------|
| **H1** | Roteiro E2E completo (Vereador → Protocolo → Secretaria → encerramento) | **Reunião 2026-06-11** — achados registrados; ciclo backend OK (demanda 2966) |
| **H2** | Consolidar observações de teste (bloqueante / incômodo / cosmético) | **OK** — H2-04…H2-08 resolvidos (A1–A5); registro 2026-06-10 |
| **H3** | Ocultar «Cluster» quando demanda não elegível (≥2, antes do protocolo) | **OK** | 4.1b |
| **H4** | Fila operacional por setor + visão Super OS na secretaria | **OK** | 4.4 — `fila=operacionais`, `minha_unidade`, coluna setor, deep-link dashboard |
| **H5** | Mensagens de estado vazio e erros nas filas | **OK** | 4.0 — vazio contextual + retry + fila devolutivas |
| **H6** | Checklist go-live com fluxo legislativo completo | **OK** | `operacao/homologacao-go-live.md` — seções 5–8 (ciclo, deploy, go/no-go, registro) |

### Onda Ajustes — pós-reunião 2026-06-11 (+1 semana + testes remotos)

| # | Entrega | Severidade | Status |
|---|---------|------------|--------|
| **A5** | **RBAC Secretaria** — restringir listagens/API ao órgão/UA do usuário | **Crítico** | **OK** — validado homologação 2026-06-10 |
| **A2** | **Visibilidade Vereador (P8)** — ocultar tramitações operacionais | Bloqueante | **OK** — validado 2026-06-10 · refino **B4** pendente |
| **A4** | Assinatura eletrônica **despacho Protocolo** (inicial + final + gestor) | Bloqueante | **OK** — validado homologação 2026-06-10 |
| **A3** | Assinatura eletrônica **chefia setor** na conclusão (Órgão/Secretaria) | Bloqueante | **OK** — validado homologação 2026-06-10 |
| **A1** | **Copiloto calibrado** com FAQ | Incômodo | **OK** — validado homologação 2026-06-10 |

### Validação remota — 2026-06-10

| Item | Resultado |
|------|-----------|
| **A1** Copiloto × FAQ | **OK** — recusas alinhadas (energia, água, prisão/furto → FAQ) |
| **A2** Visibilidade Vereador (P8) | **OK** |
| **A3** Assinatura conclusão Secretaria | **OK** |
| **A4** Assinaturas despacho Protocolo | **OK** |
| **A5** RBAC Secretaria (isolamento órgão/UA) | **OK** |
| **Gate piloto** | **GO** |

Registro completo: [homologacao-e2e-registro.md](operacao/homologacao-e2e-registro.md).

### Onda B — pós-GO (rodada operadores 2026-06-13)

Apontamentos da segunda rodada de testes. Detalhe: [piloto-apontamentos-jun2026.md](operacao/piloto-apontamentos-jun2026.md).

| # | Entrega | Perfil | Prioridade | Status |
|---|---------|--------|------------|--------|
| **B4** | **A2.1** — Timeline vereador: **secretaria + setor** (não só «Prefeitura») | VEREADOR | **P0** | **[~] Dev 2026-06-13** |
| **B5** | Despacho **multi-secretaria** (N órgãos + UAs simultâneos) | PROTOCOLO | **P1** | Pendente |
| **B7** | Indicador / painel **«despacho assinado»** | PROTOCOLO | **P1** | Pendente |
| **B8** | **Anexos** em despachos e devolutivas | PROTOCOLO | **P1** | Pendente |
| **B1** | **Geocoding** — busca de logradouros MC | VEREADOR | **P1** | Pendente |
| **B2** | Corrigir **data duplicada** no ofício rascunho | VEREADOR | **P2** | Pendente |
| **B3** | Restringir anexos com **mesmo nome** | VEREADOR | **P2** | Pendente |
| **B6** | **Cargo** na assinatura (estrutura prefeitura) | PROTOCOLO | **P2** | Pendente |
| **B9** | **Formatação** de textos na timeline | PROTOCOLO/SECRETARIA | **P3** | Pendente |

**Ordem sugerida:** B4 → B7 → B1 → B2/B3 → B5/B8 → B6 → B9.

**A2:** validação original **OK**; **B4** é refinamento de qualidade (P8+).

| Item | Resultado |
|------|-----------|
| **A5** | Implementado — aguarda validação com 2 secretarias distintas |
| **A2** | Implementado — aguarda validação timeline vereador |
| **A4** | Implementado Protocolo — migrate `0063`, UI lista + detalhe |
| **A3** | **Implementado em dev** — diálogo assinatura conclusão Secretaria; testes `test_assinatura_conclusao_secretaria` |
| **A1** | **Implementado em dev** — FAQ no prompt + regex + respostas calibradas |
| **Deploy** | migrate `0063` + build frontend + restart em homologação |

### Correções recentes (jun/2026 — homologação)

| Área | Entrega |
|------|---------|
| **Copiloto** | Painel Contexto humanizado (checklist assunto/serviço/local) |
| **Relatórios** | SLA, process mining setor, funil, comparativo vereador, export CSV, lazy table |
| **Mapa** | Heatmap, agregação espacial/sazonal, link desde relatórios |
| **Carta / Setores / Fluxo** | Explorer refatorado; TabView setores; filtros FluxoServicos |
| **Layout** | AppMenu por seções; sidebar recolhida; atalhos topbar por perfil |
| Ofício PDF | Preview em disco compartilhado (multi-worker); **1 anexo** na assinatura |
| Super OS | Coorte AUTO antes do despacho; par com demanda já protocolada; graça 20 min |
| Super OS UX | Secretaria vê só líder; protocolo com links nos vinculados; vereador só timeline |
| Tramitação | Tipo `EXECUCAO`; propagação de andamentos no líder → vinculados |
| Cluster | Mínimo 2 processos; `reconciliar_servico()`; Super OS retroativa |

### Onda 2 — Polimento legislativo e UX (**concluída**)

Especificação: [especificacoes/onda2-polimento-ux.md](especificacoes/onda2-polimento-ux.md)

| # | Entrega | Status |
|---|---------|--------|
| P1 | Preview PDF antes do envio | **OK** |
| P2 | Revisão assessor | **Removido** — rascunho pós-Copiloto |
| P3 | Docs AUTO/MANUAL + `SINAPSE_AUTOFILL_THRESHOLD` | **OK** |
| P4 | KPIs trilha Carta/Tendência/Recusa no dashboard | **OK** |
| P5 | Assinatura eletrônica em lote | **OK** |
| P6 | Painel formatação ofício → PDF | **OK** |
| **P7** | Numeração ofício por vereador + protocolo global | **OK** |
| **P8** | Timeline vereador: só marcos / conclusão | **OK** (A2) · refino secretaria/setor → **B4** |
| **P9** | Dashboard secretaria sem gráfico por secretaria | **OK** |
| **P10** | Voltar no editar rascunho | **OK** |
| **P13** | Tabelas scroll responsivas | **OK** |
| **P14** | Acesso: +carta secretaria; −fluxo/reconciliação/FAQ protocolo | **OK** |
| **P11** | Descrição estruturada no detalhe (protocolo/secretaria/gestor) | **OK** |
| **P12** | Despachar no detalhe da demanda (protocolo) | **OK** |

### Onda 3 — Escala / piloto

| # | Entrega | Status |
|---|---------|--------|
| C1 | Prazo padrão carta + política SLA | **OK** |
| C2 | Carta → setor (despacho) | **OK** |
| C4 | Hub de consultas por perfil | **OK** |
| C5 | Assuntos temáticos + protocolável/informativo | **OK** |
| C6 | Import RM271698 (1 120 unidades) | **OK** — [runbook](operacao/importacao-unidades-rm271698.md) |
| U1 | Documentação perfis e vínculos usuário | **OK** — [spec](especificacoes/modulo-usuarios-perfis.md) |
| U2 | Vínculo Protocolo → órgão 12 + UA SGAC (754) | **OK** |
| U3 | Gestão Secretaria — órgão + setor(es) RM | **OK** |
| U4 | Gestor — **Geral** (admin pleno) vs **Setorial** (escopo vinculado) | **OK** cadastro · **U7** RBAC pendente |
| U5 | UI gestão usuários unificada + UX H3-14/15/vínculos | **OK** |
| U7 | RBAC Gestor Geral vs Setorial | — Onda C |
| C3 | Embedding ao promover tendência | — |
| E2 | Pipeline IA → Celery | [~] SLA via Celery isolado (Redis /15); IA síncrona mantida |
| E3 | Mapa + relatórios analíticos | [~] Mapa operacional + Relatórios lapidados OK |
| **O1** | Ouvidoria + Groq (denúncia/reclamação/sugestão/elogio) | — pós-piloto |
| **S1** | Paginação server-side (Demandas, Carta, etc.) | [~] Relatórios OK |
| **CO1** | Copiloto gestão operacional (workshop) | — discussão |

### Piloto operacional (meta)

| Marco | Escopo |
|-------|--------|
| **2ª quinzena jun/2026** | 2 gabinetes parceiros + Protocolo + Gestão |
| **A confirmar** | Secretaria Zeladoria e Serviços Urbanos (UAs já importadas) |

Detalhe: [operacao/reuniao-trabalho-jun2026.md](operacao/reuniao-trabalho-jun2026.md).

---

## Mapa rápido por perfil

### Vereador

| Item | Status |
|------|--------|
| Copiloto → rascunho de demanda/ofício | **OK** (A1) · busca endereço → **B1** |
| Preview ofício / data no PDF | **~** · data duplicada → **B2** |
| Anexos — nomes duplicados | — · restringir → **B3** |
| Editar rascunho e enviar oficialmente (sem etapa assessor) | OK |
| Assinatura visual no PDF (perfil) | OK |
| Enviar oficialmente + assinatura eletrônica | OK |
| Pacote devolutiva + ciência + ofício ao cidadão | OK |
| Super OS — acompanha andamentos na timeline (`[Super OS]`) | OK |
| Numeração ofício `OFICIO-AAAA-NNNN` por vereador | **OK** (P7) |
| Timeline: ocultar gestão operacional; ver conclusão | **OK** (A2) · refino **B4** |
| Botão «Voltar» em editar rascunho | **OK** (P10) |

### Protocolo

| Item | Status |
|------|--------|
| Gestão de tendências (`/gestao-tendencias`) | OK |
| Clusters + despacho Super OS (`/clusters`) | OK |
| Painéis protocolados / operacionais / devolutivas + temporizador | OK |
| Vínculo institucional órgão **12** + UA **SGAC (754)** | **OK** (U2 — signal + `aplicar_vinculo_protocolo`) |
| Card Super OS na demanda com links entre vinculados | OK |
| Ocultar cluster quando não elegível | OK |
| Fluxo por serviço / Reconciliação Sinapse / FAQ Copiloto | **Removido** (P14 — só GESTOR) |
| Despachar no detalhe da demanda | **OK** (P12) · multi-secretaria → **B5** |
| Confirmar despacho assinado / anexos despacho | — · **B7**, **B8** pendentes |

### Operação (setor / secretaria)

| Item | Status |
|------|--------|
| Tramitação por órgão + encaminhar-setor | OK |
| Unidade administrativa + responsáveis (`/gestao-setores`) | OK — **1 120 unidades RM271698** importadas |
| Solicitar devolutiva (sem finalizar direto) | OK |
| Lista filtrada — só demanda **líder** da Super OS | OK |
| Card Super OS + andamentos replicados nos vinculados | OK |
| Resumo Super OS no dashboard (sem gestor de clusters) | OK |
| Fila operacional `minha_unidade` + filtro setor | OK |
| Vínculo órgão Sinapse + setor(es) RM (responsável UA) | **OK** (U3 + A5) |
| Consulta Carta de Serviços | **OK** (P14) |
| Dashboard sem gráfico «Demandas por Secretaria» | **OK** (P9) |

### Gestor

| Item | Status |
|------|--------|
| Dashboard + relatórios KPI | OK |
| Mapa de calor (operacional + heatmap) | **~** homologação |
| Relatórios gerenciais (SLA, mining, CSV) | **OK** |
| Gestor de clusters + resumo Super OS | OK |
| KPIs de trilha Carta/Tendência/Recusa | **OK** (P4 — dashboard Protocolo/Gestor) |
| Assuntos da carta + utilização SGDL (`/admin/assuntos-carta`) | **OK** (C5) |
| SLA da carta (`/admin/configuracao-carta`) | **OK** (C1) |
| Admin Django + escopo sistema inteiro | **OK** — perfil GESTOR + `is_superuser` [U4](especificacoes/modulo-usuarios-perfis.md) |

---

## Fluxo canônico (SGDL ponta a ponta)

```
RASCUNHO → preview PDF → assinatura eletrônica → AGUARDANDO_PROTOCOLO
  → [clusterização + coorte AUTO] → PROTOCOLADO (ou Super OS SUPER-AAAA-NNNN)
  → EM_EXECUCAO → AGUARDANDO_DEVOLUTIVA_PROTOCOLO → DEVOLVIDO_VEREADOR
  → confirmar-ciência → FINALIZADO
```

Identificadores: `protocolo_legislativo` (`OFICIO-AAAA-NNNN`, sequência **por autor**), `protocolo_executivo` (`AAAA-NNNN`, global), `SUPER-AAAA-NNNN`.

Regras de cluster: **mesmo serviço Sinapse** + similaridade ≥ 0,7 + raio ≤ 300 m (quando o serviço exige local).

---

## Trilhas históricas (referência)

| Documento | Conteúdo |
|-----------|----------|
| [arquivo/infra/ROADMAP_SGDL_SERVIDOR_APIS_LLM.md](arquivo/infra/ROADMAP_SGDL_SERVIDOR_APIS_LLM.md) | Infra/APIs — Sprints 1–7 |
| [arquivo/carta-otimizacao/STATUS_EXECUCAO_ROADMAP.md](arquivo/carta-otimizacao/STATUS_EXECUCAO_ROADMAP.md) | Otimização carta (mai/2026) |
| [arquivo/sprints/](arquivo/sprints/) | Evidências abr/2026 |

---

## Evidências de homologação

```bash
cd backend && python manage.py test core.tests.test_assinatura_eletronica core.tests.test_cluster_par_formacao --settings=config.settings_test --keepdb
cd backend && python manage.py check --deploy
cd frontend && npm run build
```

Checklist: [operacao/homologacao-go-live.md](operacao/homologacao-go-live.md).

---

## Manutenção

- Novos requisitos de produto → [ROADMAP_PRODUTO.md](ROADMAP_PRODUTO.md) (detalhe) + este arquivo (prioridade resumida).
- Observações de teste → consolidar em **H2** (`tela · perfil · esperado · obtido · severidade`) e derivar H4–H5.
- Sprints encerradas → [arquivo/sprints/](arquivo/sprints/).
