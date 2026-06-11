# Roadmap consolidado — SGDL

Painel único de **status e prioridades**. O detalhamento por fase de produto está em [ROADMAP_PRODUTO.md](ROADMAP_PRODUTO.md).

**Atualizado:** 2026-06-10 · **Onda 3:** C1–C6 concluídos

---

## Resumo executivo

| Trilha | Status | Observação |
|--------|--------|------------|
| **Infra + Sinapse (Sprints 1–7)** | Concluída | Abr/2026 — sync, reconciliação, `SinapseReconciliacaoView` |
| **Carta otimizada (RAG)** | Concluída | Mai/2026 — `ServicoOtimizado`, triagem otimizada |
| **Copiloto** | Em homologação | Multi-pedido, competência, FAQ; tendência no chat parcial |
| **Ciclo legislativo ponta a ponta** | **Concluído** | Assinatura → protocolo → operação → devolutiva → cidadão |
| **Protocolo + tramitação** | **~ homologação** | Painéis, fluxo AUTO, setores, Super OS, devolutiva entregues |
| **Assinatura envio oficial** | **Concluído** | Preview PDF (disco) + assinatura eletrônica + 1 anexo final |
| **Revisão assessor (P2)** | **Removido** | Rascunho pós-Copiloto substitui etapa formal (migração `0056`) |
| **Onda 2 (P1–P14)** | **Concluída** | Polimento UX e regras operacionais |
| **Cluster / Super OS v2** | **~ homologação** | Mesmo serviço + 300 m + coorte AUTO + UX por perfil |

> Tramitação **100% no SGDL** — integração SEI/1Doc removida (migração `0049`).

---

## Status por fase de produto

Legenda: **OK** concluído · **~** parcial · **—** pendente

| Fase | Tema | Status | Destaques |
|------|------|--------|-----------|
| **1** | Infra vetorial (pgvector, embeddings) | **OK** | Migração 0028, Kernel mxbai-embed-large |
| **2** | Ingestão, Copiloto, Carta, Tendências | **~** | Explorer, tendências, FAQ e KPIs trilha OK; SLA Celery pendente |
| **3** | Ofícios PDF e assinatura | **OK** | Envio oficial + assinatura + preview; rascunho = janela de revisão |
| **4** | Clusters, Protocolo, setor, fluxo | **~** | Ciclo operacional + Super OS UX OK; analítica e polish pendentes |
| **5** | Piloto 23 gabinetes / Gov.br | **—** | Não iniciado |
| **6** | Encerramento legislativo | **OK** | Pacote devolutiva, ciência, ofício ao cidadão |

Checklist detalhado: [ROADMAP_PRODUTO.md](ROADMAP_PRODUTO.md).

---

## Prioridades — Onda 1 (homologação operacional, até sexta-feira)

Foco: **validação E2E por perfil** (gate A1) e consolidação de observações UX antes do piloto.

| # | Entrega | Status | Ref. |
|---|---------|--------|------|
| **H1** | Roteiro E2E completo (Vereador → Protocolo → Secretaria → encerramento) | **Em andamento** — backend **GO** ([registro](operacao/homologacao-e2e-registro.md)); UI manual pendente |
| **H2** | Consolidar observações de teste (bloqueante / incômodo / cosmético) | **Em andamento** | formato: `tela · perfil · esperado · obtido · severidade` |
| **H3** | Ocultar «Cluster» quando demanda não elegível (≥2, antes do protocolo) | **OK** | 4.1b |
| **H4** | Fila operacional por setor + visão Super OS na secretaria | **OK** | 4.4 — `fila=operacionais`, `minha_unidade`, coluna setor, deep-link dashboard |
| **H5** | Mensagens de estado vazio e erros nas filas | **OK** | 4.0 — vazio contextual + retry + fila devolutivas |
| **H6** | Checklist go-live com fluxo legislativo completo | **OK** | `operacao/homologacao-go-live.md` — seções 5–8 (ciclo, deploy, go/no-go, registro) |

### Correções recentes (jun/2026 — homologação)

| Área | Entrega |
|------|---------|
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
| **P8** | Timeline vereador: só marcos / conclusão | **OK** |
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
| U4 | Gestor — admin pleno + referência institucional | **OK** |
| U5 | UI gestão usuários unificada | **OK** |
| C3 | Embedding ao promover tendência | — |
| E2 | Pipeline IA → Celery | [~] SLA via Celery isolado (Redis /15); IA síncrona mantida |

---

## Mapa rápido por perfil

### Vereador

| Item | Status |
|------|--------|
| Copiloto → rascunho de demanda/ofício | ~ homologação |
| Editar rascunho e enviar oficialmente (sem etapa assessor) | OK |
| Assinatura visual no PDF (perfil) | OK |
| Enviar oficialmente + assinatura eletrônica | OK |
| Pacote devolutiva + ciência + ofício ao cidadão | OK |
| Super OS — acompanha andamentos na timeline (`[Super OS]`) | OK |
| Numeração ofício `OFICIO-AAAA-NNNN` por vereador | **OK** (P7) |
| Timeline: ocultar gestão operacional; ver conclusão | **OK** (P8) |
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
| Despachar no detalhe da demanda | **OK** (P12) |

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
| Vínculo órgão Sinapse + setor(es) RM (responsável UA) | **OK** (U3 — `/gestao-usuarios`) |
| Consulta Carta de Serviços | **OK** (P14) |
| Dashboard sem gráfico «Demandas por Secretaria» | **OK** (P9) |

### Gestor

| Item | Status |
|------|--------|
| Dashboard + relatórios KPI | OK |
| Mapa de calor (básico) | OK |
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
