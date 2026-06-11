# Roadmap: Fusão SGDL + MOVA (Portal do Vereador Intelligence)

> **Documento canônico de produto.** Índice geral: [README.md](README.md) · Status resumido: [ROADMAP.md](ROADMAP.md)

Este documento detalha as fases de implementação para transformar o SGDL no piloto de inovação tecnológica da prefeitura, integrando o motor de IA do projeto MOVA.

> **Legenda de status**
>
> - `[x]` **CONCLUÍDO** — entregue e validado (com evidência: arquivo, migração, teste ou smoke).
> - `[~]` **PARCIAL** — base implementada, falta funcionalidade complementar.
> - `[ ]` **PENDENTE** — não iniciado.

## Resumo executivo

| Fase | Tema | CONCLUÍDO | PARCIAL | PENDENTE |
|------|------|:---------:|:-------:|:--------:|
| 1 | Infraestrutura e Base Vetorial | 4 | 1 | 0 |
| 2 | Ingestão, Triagem e Produto Operacional | 12 | 3 | 4 |
| 3 | Governança Digital e Assinatura | 8 | 2 | 3 |
| 4 | Execução, Protocolo e Tramitação | 24 | 3 | 2 |
| 5 | Rollout Piloto e Integração Gov.br | 0 | 0 | 4 |
| 6 | Ciclo de Fechamento Legislativo | 4 | 0 | 0 |

---

## Motor de decisão (visão produto)

Três trilhas na ingestão (Copiloto) e dois caminhos estratégicos pós-ingestão:

| Trilha / Caminho | Quando | Destino |
|------------------|--------|---------|
| **A — Fast-Track Carta** | Match Sinapse confirmado | Serviço + órgão definidos → ofício → protocolo |
| **B — Malha fina (Tendências)** | Municipal, fora da carta | `Tendencia` + gestão Protocolo → promover à carta |
| **Recusa** | Fora de competência municipal | FAQ + encerramento sem ofício |

A IA deixa de ser só chat quando houver: Explorer da Carta, KPIs de trilha, clusterização e SLA operacional (ver fases 2.4–2.6 e 4.x).

---

## Fase 1: Infraestrutura e Base Vetorial
*Foco: Preparar o ecossistema Django para suportar inteligência de dados.*

### 1.1 Refatoração do Banco de Dados

- [x] **Instalação da extensão `pgvector` no PostgreSQL.**
  Servidor PG 18.2 com `vector 0.8.1` instalada. Aplicada idempotentemente via `VectorExtension()` em `backend/core/migrations/0028_clusterexecucao_demanda_embedding_and_more.py`.
- [x] **Migração do modelo `Demanda` com campo `embedding` (VectorField, 1024d).**
  Campo `embedding vector(1024)` + `ia_categoria`, `ia_sentimento`, `ia_processado`, `cluster_id` adicionados (`backend/core/models.py`; migração 0028).
- [x] **Criação da tabela `ClusterExecucao` para suporte à deduplicação.**
  Model criado com campos `titulo`, `descricao_resumo`, `status` (ABERTO/EM_ANDAMENTO/RESOLVIDO), `secretaria_responsavel`, `bairro_referencia`, `centroide vector(1024)`, `criado_em`, `atualizado_em` (`backend/core/models.py`; migração 0028).

### 1.2 Padronização de Embeddings

- [x] **Configuração do serviço `mxbai-embed-large` via Kernel AI.**
  `VectorService` em `backend/core/services/vector_service.py` consumindo `AI_KERNEL_BASE_URL`. Validado em smoke (retorno 1024d).
- [~] **Scripts para vetorização do legado (demandas pré-existentes)** — *stand-by*.
  Não há confirmação de volume legado a reprocessar. Manter no roadmap; implementar `manage.py backfill_embeddings` só se homologação exigir (`--batch-size`, `--dry-run`). Demandas novas já passam pelo pipeline em `signals.py`.

---

## Fase 2: Ingestão Inteligente e Triagem (NLP)
*Foco: Automatizar a entrada de dados e o cálculo de prazos.*

### 2.1 Motor de Extração (LLM) e Carta Sinapse

- [x] **Parser via Groq (Llama 3.3) → JSON estruturado.** (`LLMService`)
- [x] **Mapeamento automático com a Carta de Serviços.**
  Multi-DB Sinapse, `TriagemService.buscar_servico_sinapse`, modo assistivo em `signals.py`. Smoke: *Tapa Buraco* score 0.73 em ~32 ms.

### 2.2 Competência municipal e recusa no Copiloto

- [x] Bloqueio determinístico `fora_competencia` + heurística de score.
- [x] Classificador LLM (`competencia_municipal`, `motivo_recusa`, FAQ).
- [x] FAQ banco + Admin + API + `enriquecer_faq_llm`.
- [ ] Agendar enriquecimento FAQ em cron/Celery + revisão humana em massa.

### 2.3 Automação de SLA

- [x] **Cronômetro** ao status `PROTOCOLADO` (`data_inicio_prazo` em signals).
- [~] **Alertas de vencimento** — `verificar_atrasos` via cron; resolução C1 (carta → Sinapse → metadados → padrão); falta Celery beat e cobrança ativa.
- [ ] **Cobrança ativa** — alertas por e-mail e ofício de cobrança quando o prazo operacional vencer.

### 2.4 Carta de Serviços — Explorer e prova de triagem

- [x] **Módulo visual Vue** — `CartaExplorerView.vue` (`/carta-servicos`): busca, ficha (órgão, **prazo**, documentos, requisitos).
- [x] **Sandbox de simulação** — `POST /api/integrations/carta/simular-triagem/` (embedding Kernel + `TriagemService`, latências ms).
- [x] **API** — `GET .../carta/servicos/`, `GET .../carta/servicos/<id>/` (`CartaExplorerService`, `sinapse_catalog.servico_detalhe_dict`).
- [~] **Reconciliação de sync** — `SinapseReconciliacaoView` (mapeamento AUTO/MANUAL/UNMATCHED); complementar ao Explorer.
- [ ] Explicação Groq opcional do “por que este serviço” (evolução).
- **Evidência:** `manage.py test integrations.tests_carta_explorer --settings=config.settings_test`.

### 2.5 Gestão de Tendências (malha fina)

- [x] **Backend** — `Tendencia`, API, Copiloto (`confirmar-tendencia`), `docs/apis/tendencias.md`.
- [~] **Copiloto Vue** — fluxo tendência no chat (parcial; bloco pode estar oculto por flag).
- [x] **Módulo Vue Protocolo/Gestor** — `TendenciasGestaoView.vue` (`/gestao-tendencias`): lista, detalhe, editar (status/órgão/resumo), promover à carta, ocorrências → demanda.
- **Evidência:** `manage.py test core.tests.TendenciaAPITests --settings=config.settings_test` + `npm run build`.

### 2.6 KPIs do motor de trilhas

- [x] **Dashboard Protocolo/Gestor** — volume Carta / Tendência / Recusa, amostra `motivo_recusa` (`DashboardTrilhaService`, P4).
- [ ] Campo persistido `ia_sugestoes_sinapse` (ou equivalente) para auditoria pré-protocolo.
- **Evidência:** `manage.py test core.tests.test_dashboard_trilhas --settings=config.settings_test`.

---

## Fase 3: Governança Digital e Assinatura
*Foco: Formalização do processo e segurança jurídica.*

### 3.1 Geração de Ofícios (PDF)

- [x] **`OficioService` + WeasyPrint** — templates `demanda_oficio.html` / `oficio_lote.html`; Copiloto **não** gera PDF na materialização (evita anexos duplicados).
- [~] **Revisão de texto pelo assessor** — *removido jun/2026*; o status `RASCUNHO` após o Copiloto é a janela de revisão antes do envio oficial.
- [ ] **Templates dinâmicos com LLM** — redação institucional opcional via Groq (evolução).

### 3.1b Assinatura do Vereador no Ofício (perfil → PDF)

- [x] **Perfil → PDF** — `Usuario.assinatura_imagem` (migração `0037`); `ProfileView` (upload PNG/JPG + gerador canvas); `contexto_assinatura_pdf` + `_bloco_assinatura.html` em `demanda_oficio` / `oficio_lote`.
- [~] **Texto complementar** — `Usuario.assinatura` (Editor) usado no PDF quando não há imagem ou como legenda.
- [ ] **Pré-visualização do ofício** no perfil ou Copiloto antes de materializar.
- **Evidência:** `manage.py test core.tests.OficioAssinaturaPdfTests --settings=config.settings_test`.

### 3.2 Assinatura Eletrônica Nativa (criptográfica)

- [x] **Hash SHA-256** — model `AssinaturaEletronica` (migração `0045`): `hash_documento`, `hash_assinatura`, IP, user-agent.
- [x] **Validação pública** — `GET /api/v1/validar-assinatura/<codigo>/` + QR (`?format=qr`) + página `/validar-assinatura/:codigo`.
- [x] **Assinatura em lote no Vue** — seleção de N rascunhos + `POST /api/demandas/enviar-lote/`; envio unitário mantido.

### 3.3 Envio oficial do ofício assinado (perfil Vereador)

- [x] **Fluxo «Enviar oficialmente»** — pré-visualização PDF + declaração «ASSINO E ENVIO» + registro de assinatura antes do protocolo.
- [x] Sequência: preview → assinatura eletrônica → `AGUARDANDO_PROTOCOLO` (+ fluxo automático se configurado).
- [x] UX: dialog com checkbox explícito e trilha de auditoria (IP, user-agent, hashes).
- [~] **Assinatura visual no PDF** (3.1b) — complementa; validação eletrônica é obrigatória no envio.
- [ ] Gov.br (Fase 5.2) como evolução institucional — **piloto usa assinatura nativa (D3)**.

### 3.4 Pré-visualização e revisão antes do envio

- [x] **Pré-visualização do ofício** — `GET /demandas/{id}/preview-envio-oficial/` + stream PDF autenticado; preview em disco compartilhado (multi-worker Gunicorn); **sem anexo** até a assinatura.
- [x] **Um único PDF oficial** por envio — limpeza de previews/copiloto/legado na assinatura; arquivo `oficio_demanda_{id}_assinado.pdf`.
- [~] Revisão formal pelo assessor (P2) — *removida*; rascunho pós-Copiloto substitui essa etapa (migração `0056`).

---

## Fase 4: Inteligência de Execução e Protocolo
*Foco: Otimização para secretarias, agrupamento e tramitação ponta a ponta no SGDL.*

### 4.0 Orquestração de Protocolo e gestão de fluxo

- [ ] **Roteamento automático vs manual** — serviços mapeados com alta confiança dispensam triagem humana; casos complexos ficam na fila Protocolo.
- [x] **Módulo de gestão de fluxo** — `FluxoServicosView` + API `/fluxo-servicos/` (modo MANUAL | AUTOMATICO por serviço Sinapse).
- [x] **Despacho automático** — ao entrar em `AGUARDANDO_PROTOCOLO`, serviços configurados protocolam direto no órgão da carta (`FluxoProtocoloService` + signal).
- [x] Regras documentadas alinhadas a `SINAPSE_AUTOFILL_THRESHOLD`, confirmação humana no Copiloto e cadastro de fluxo por serviço → [operacao/fluxo-auto-manual.md](operacao/fluxo-auto-manual.md).
- [x] **Tendência na tabela de demandas** — ação «Gerir tendência» com atalho para `TendenciasGestaoView` (`?id=` / `?demanda=`).
- [x] **Ações contextuais na tabela** (`DemandasView`, perfil Protocolo): **Cluster** · **Enviar** · **Gerir tendência** · **Ver**.
- [x] **Dois painéis de trabalho** na página de demandas (Protocolo/Gestor): `fila=protocolados` | `operacionais`, FIFO por `data_entrada_etapa`.
- [x] **Temporizador de parada** — coluna «Parado há» + `tempo_parado_segundos` na API (migração `0043`).

### 4.1 Clustering e Super Ordem de Serviço

> **Evolução necessária (jun/2026):** a clusterização atual agrupa por similaridade semântica ampla; a regra de negócio correta é **mesmo serviço** + proximidade geográfica quando o serviço exige local.

- [x] **`ClusterService` v1** — semântica (cosseno ≥ `CLUSTER_SEMANTIC_THRESHOLD`, default 0.7) + geo (Haversine ≤ `CLUSTER_RADIUS_METERS`, default 300 m) ou mesmo bairro.
- [x] **Orquestração pós-save** — após embedding (`signals._aplicar_embedding_demanda_async`) e ao mudar status elegível (`demanda_cluster_pos_save`).
- [x] **Centroide** — média dos embeddings das demandas do cluster; recálculo a cada inclusão.
- [x] **Fechamento** — cluster `RESOLVIDO` quando todas as demandas `FINALIZADO`/`CANCELADO`; `EM_ANDAMENTO` se houver execução.
- [x] **Super OS** — múltiplos `autor` no mesmo cluster (contagem `autores_distintos` na API).
- [x] **API** — `GET /api/clusters/`, detalhe, `.../demandas/`, `.../resumo-operacional/` (Protocolo/Gestor).
- [x] **UI Vue** — `ClustersView.vue` (`/clusters`) + resumo no `DashboardView` (Protocolo/Gestor).
- [x] **Despacho manual Super OS** — `POST /api/clusters/{id}/despachar/` (`ClusterDespachoService`), protocolo `SUPER-AAAA-NNNN`; coluna e diálogo em `DemandasView.vue`.
- [x] **Janela de agregação** — `CLUSTER_JANELA_AGREGACAO_DIAS` (default 90): ofício novo similar só entra em cluster aberto atualizado dentro do prazo; fora disso, novo cluster.
- **Config:** `CLUSTER_ENABLED`, `CLUSTER_SEMANTIC_THRESHOLD`, `CLUSTER_RADIUS_METERS`, `CLUSTER_JANELA_AGREGACAO_DIAS` em `settings.py`.
- **Evidência:** `manage.py test core.tests.ClusterServiceTests core.tests.ClusterAPITests core.tests.ClusterDespachoTests core.tests.ClusterDespachoAPITests --settings=config.settings_test`.

### 4.1b Refinamento da inteligência de cluster (v2)

- [x] **Regra principal** — agrupar **apenas o mesmo serviço** (`sinapse_servico_id` / carta), não serviços semanticamente parecidos mas distintos (`CLUSTER_REQUER_MESMO_SERVICO`, migração `0042`).
- [x] **Geolocalização** — quando o serviço exige local (`servico_requer_localizacao`): raio **≤ 300 m** (Haversine); sem coordenadas, fallback mesmo bairro.
- [x] **Elegibilidade** — API `GET /demandas/{id}/cluster-elegibilidade/`; ação «Cluster» oculta quando &lt;2 processos ou após protocolo (`DemandasView`).
- [x] **Mínimo 2 demandas** — `CLUSTER_MIN_DEMANDAS = 2`; não forma cluster unitário; `purgar_clusters_unitarios()`.
- [x] **Gestão manual do cluster** — `POST /clusters/{id}/vincular/` e `desvincular/` + UI em `ClustersView.vue`; trilha em `Tramitacao`.
- [x] **Sincronização de status do grupo** — `propagar_status_no_cluster` no signal pós-save; ao finalizar, demais demandas e Super OS acompanham.
- [x] **Propagação de andamentos** — `propagar_tramitacao_no_cluster` no líder; tramitação bloqueada em filhos.
- [x] **UX Super OS por perfil** — secretaria: lista só líder + card vinculados; protocolo: links entre processos; vereador: timeline `[Super OS]`.
- [x] **Fluxo AUTO em coorte** — `processar_cohorte_servico()` + `CLUSTER_FORMACAO_GRACE_MINUTES` (20 min).
- [x] **Par retroativo** — `DEMANDA_STATUS_PAR_FORMACAO`; `reconciliar_servico()`; Super OS retroativa.
- [x] Embedding restrito a desempate dentro do **mesmo** serviço (união exige `sinapse_servico_id` igual).
- **Evidência:** `test_cluster_par_formacao`; pares (Tapa Buraco + Lombada) **não** clusterizados; caso 2774/2775 reconciliado.

### 4.2 Indicadores e mapa (não confundir com Tendencia operacional)

- [ ] **Análise espacial/sazonal** — agregação `bairro × categoria × mês` (`MapaCalorView` evolui).
- [ ] **Dashboard IA** — cobertura embedding, clusters abertos, baixa confiança Sinapse.

### 4.4 Unidade administrativa (setor) e tramitação transversal

> **Impacto alto** — base para despacho operacional real dentro e entre órgãos.

- [x] **Modelo `UnidadeAdministrativa` (setor)** — vinculada ao órgão (`sinapse_orgao_id`); nome, sigla, ativo (migração `0046`).
- [x] **Responsáveis por setor** — N usuários por unidade; API vincular/desvincular.
- [x] **Tramitação operacional** — despacho Protocolo com `unidade_administrativa_id`; histórico em `Tramitacao` (`unidade_origem` / `unidade_destino`).
- [x] **Tramitação transversal** — `POST /demandas/{id}/encaminhar-setor/` (mesmo órgão ou outro, auditável).
- [x] **Painel operacional** (4.0) — filtro `minha_unidade` / `unidade_administrativa` na fila operacionais; coluna setor na UI; estados vazios e retry por fila; deep-link `?fila=`; tipos `EXECUCAO` (`0050`).
- [x] **Cadastro** — `SetoresView.vue` + API `/unidades-administrativas/` (Gestor/Protocolo; Secretaria consulta).
- [x] **Import RM271698** — 1 120 unidades (C6); de-para RM ↔ Sinapse.
- [x] **U2 — Vínculo Protocolo** — `sinapse_orgao_id=12` + responsável UA SGAC na criação (`post_save`) e comando `aplicar_vinculo_protocolo`.
- [x] **U3 — Gestão Secretaria** — API + UI criar/editar usuário com órgão + setor(es); aviso global e bloqueio fila «Meu setor».
- [x] **U4 — Gestor** — `is_staff`/`is_superuser` automático; API/UI gestão gestores; referência org/UA opcional.
- [x] **U5 — Gestão de usuários** — hub `/gestao-usuarios` (todos os perfis; Protocolo sem gestores).
- **Dependências:** 4.0 (painéis e fluxo); influencia 4.1b (cluster por serviço+local) e Fase 6 (devolutiva).

### 4.5 Ciclo de devolutiva via Protocolo

- [x] **Regra de fechamento** — secretaria conclui em `EM_EXECUCAO` → `AGUARDANDO_DEVOLUTIVA_PROTOCOLO` (sem `FINALIZADO` direto).
- [x] Protocolo **despacha devolutiva** ao vereador (`despachar-devolutiva`) com parecer e notificação.
- [x] Estados: `EM_EXECUCAO` → `AGUARDANDO_DEVOLUTIVA_PROTOCOLO` → `DEVOLVIDO_VEREADOR` → `FINALIZADO`.
- [x] Integração Fase 6 — ofício resposta ao cidadão via `confirmar-ciencia` + PDF anexo.
- [x] Painel Protocolo: fila **Devolutivas** + ações inline e tela de detalhe.

---

## Fase 5: Rollout Piloto e Integração Gov.br

### 5.1 Lançamento nos 23 Gabinetes

- [ ] Treinamento ágil e feedbacks.
- [ ] Fine-tuning de prompts com logs produção.

### 5.2 Integração Federal

- [ ] Roadmap Gov.br substituindo assinatura nativa (3.2).
- [ ] Expansão MOVA para outros serviços.

---

## Fase 6: Encerramento e Devolutiva Legislativa

- [x] Recebimento da resposta final da Secretaria — integrado ao pacote de devolutiva (tramitações 4.5).
- [x] Encerramento sistêmico — Protocolo via `encerrar-devolutiva` ou vereador via `confirmar-ciencia`.
- [x] Devolutiva no painel do vereador — `GET pacote-devolutiva` + bloco na tela de detalhe (`DEVOLVIDO_VEREADOR`).
- [x] Ciência e ofício ao cidadão — `confirmar-ciencia` gera PDF «Resposta ao cidadão» e encerra (`FINALIZADO`).

---

## Próximos passos sugeridos (priorizados)

> Critério: maior valor com menor risco (`homologacao-readiness`).  
> **Posição atual (jun/2026):** ciclo legislativo e **Onda 2 (P1–P14) concluídos**. Foco imediato: **H1/H2** (E2E + observações UX) até **sexta-feira**; em seguida **Onda 3**.

### Entregas concluídas (base estável — não reabrir)

| Entrega | Fase |
|---------|------|
| Assinatura perfil → PDF do ofício | 3.1b |
| Explorer Carta + simulação triagem | 2.4 |
| Gestão de Tendências (`TendenciasGestaoView`) | 2.5 |
| Clusterização + Super OS + cluster v2 | 4.1 / 4.1b |
| Painéis Protocolo (protocolados / operacionais / devolutivas) + temporizador | 4.0 |
| Ações na tabela + gerir tendência in-line | 4.0 |
| «Enviar oficialmente» + assinatura eletrônica | 3.2 + 3.3 |
| Unidade administrativa (setor) + tramitação transversal | 4.4 |
| Gestão de fluxo automatizado por serviço | 4.0 |
| Devolutiva Protocolo → vereador → ofício ao cidadão | 4.5 + 6 |
| Tramitação ponta a ponta no SGDL (sem integração SEI) | — |
| Preview PDF + 1 anexo na assinatura (multi-worker) | 3.4 |
| Super OS UX por perfil + propagação de andamentos | 4.1b |
| Coorte AUTO + par retroativo + reconciliar serviço | 4.1 / 4.0 |

### Onda 1 — Homologação operacional (até sexta-feira, jun/2026)

| # | Entrega | Fase | Status |
|---|---------|------|--------|
| **H1** | **Testes E2E por perfil** — Vereador → Protocolo → Secretaria → encerramento | — | **Em andamento** |
| **H2** | Consolidar observações de UX (`tela · perfil · esperado · obtido · severidade`) | — | **Em andamento** |
| **H3** | Ocultar ação «Cluster» quando não elegível (≥2, antes do protocolo) | 4.1b | **Concluído** |
| **H4** | Fila operacional por setor + visão Super OS secretaria (líder, dashboard) | 4.4 | **Concluído** |
| **H5** | Estados vazios, mensagens de erro e deep-links nas filas | 4.0 | **Concluído** |
| **H6** | Checklist `homologacao-go-live.md` com fluxo legislativo completo | — | **Concluído** |

### Onda 2 — Polimento legislativo e UX operacional (**concluída**)

Especificação detalhada: **[especificacoes/onda2-polimento-ux.md](especificacoes/onda2-polimento-ux.md)**

| # | Entrega | Fase | Status |
|---|---------|------|--------|
| **P1** | Pré-visualização do ofício antes de «Enviar oficialmente» | 3.4 | **Concluído** |
| **P2** | Revisão pelo assessor | 3.1 | **Removido** — rascunho pós-Copiloto é a janela de revisão |
| **P3** | Documentar regras AUTO/MANUAL + `SINAPSE_AUTOFILL_THRESHOLD` | 4.0 | **Concluído** |
| **P4** | KPIs de trilha no dashboard Protocolo (Carta / Tendência / Recusa) | 2.6 | **Concluído** |
| **P5** | Assinatura eletrônica em lote (N demandas) | 3.2 | **Concluído** |
| **P6** | Painel formatação de ofício no frontend → layout PDF | 3.1 | **Concluído** |
| **P7** | Numeração: `OFICIO-AAAA-NNNN` por vereador; protocolo `AAAA-NNNN` global | 4.0 | **Concluído** |
| **P8** | Vereador: ocultar tramitações operacionais; exibir conclusão | 4.5 | **Concluído** |
| **P9** | Dashboard secretaria: remover gráfico «Demandas por Secretaria» | 2.6 | **Concluído** |
| **P10** | Botão «Voltar» em «Editar rascunho do ofício» | 3.4 | **Concluído** |
| **P11** | Descrição estruturada no detalhe (protocolo, secretaria, gestor) | 4.0 | **Concluído** |
| **P12** | Botão «Enviar/Despachar» no detalhe da demanda (protocolo) | 4.0 | **Concluído** |
| **P13** | Tabelas responsivas com scroll horizontal (todas as DataTables) | — | **Concluído** |
| **P14** | Acesso: carta para secretaria; remover fluxo/reconciliação/FAQ do protocolo | — | **Concluído** |

### Onda 3 — Escala e analítica (piloto)

Especificação detalhada (Carta + consulta): **[especificacoes/carta-consulta-evolucao.md](especificacoes/carta-consulta-evolucao.md)**

| # | Entrega | Fase | Status |
|---|---------|------|--------|
| **E1** | SLA com prazo da carta Sinapse + alertas e cobrança ativa | 2.3 | [~] Parcial (C1: resolução + snapshot; falta cobrança ativa) |
| **E2** | Migrar pipeline IA → Celery | 2.3 | [~] SLA isolado (Redis DB 15); IA Copiloto permanece síncrona |
| **E3** | Mapa espacial/sazonal + dashboard IA | 4.2 | Pendente |
| **E4** | Treinamento piloto 23 gabinetes | 5.1 | Pendente |
| **E5** | Gov.br (evolução institucional da assinatura) | 5.2 | Pendente |
| **C1** | Prazo padrão + política «serviço ou padrão» (fallback natural) | 2.3 / Carta | **Concluído** |
| **C2** | Carta otimizada → vínculo unidade administrativa (setor) | 4.4 / Carta | **Concluído** |
| **C3** | Embedding enriquecido ao incorporar tendências à carta | 2.4 / 2.5 | Pendente |
| **C4** | Hub de consultas intuitivas (vereador, protocolo, secretaria) | UX | **Concluído** |
| **C5** | Assuntos temáticos + política protocolável / informativo (Copiloto) | Carta / IA | **Concluído** — [spec](especificacoes/carta-assuntos-utilizacao-unidades.md) |
| **C6** | Importação unidades RM271698 → `UnidadeAdministrativa` | Carta / Setores | **Concluído** — [runbook](operacao/importacao-unidades-rm271698.md) |
| **U1** | Documentação perfis e vínculos (usuário / órgão / UA) | Governança | **Concluído** — [spec](especificacoes/modulo-usuarios-perfis.md) |
| **U2** | Vínculo Protocolo → órgão 12 + UA SGAC (754) | Governança | **OK** |
| **U3** | Gestão Secretaria: órgão + setor(es) RM na criação do usuário | Governança | **OK** |
| **U4** | Gestor: vínculo institucional + admin pleno (Django + frontend) | Governança | **OK** |
| **U5** | UI gestão de usuários unificada (hub por perfil) | UX / Governança | **OK** |
| **U6** | Django Admin — Perfil + Órgão + inline Setor + «Onde atua» | Governança | **OK** |
| — | Backfill embeddings legado | 1.2 | **Stand-by** |

Itens concluídos recentemente (não repetir): remoção revisão assessor (`0056`, jun/2026), remoção SEI/1Doc (`0049`), encerramento (`0048`), devolutiva (`0047`), setores (`0046`), assinatura eletrônica (`0045`), tipo tramitação `EXECUCAO` (`0050`), cluster coorte/par retroativo (jun/2026).

### Formato para observações de teste (H2)

Registrar cada achado como uma linha:

```
tela · perfil · esperado · obtido · severidade
```

Exemplo: `DemandasView · SECRETARIA · coluna Super OS abre líder · abre /clusters · bloqueante` → encaixa em H4 (corrigido jun/2026).

---

## Trilha de evidências (homologação)

| Item | Evidência |
|------|-----------|
| Extensão pgvector | `vector 0.8.1` no Postgres |
| Migração 0028 | `manage.py showmigrations core` |
| Suite de testes | `manage.py test core --settings=config.settings_test` |
| Smoke TriagemService | top-1 *Tapa Buraco* ~32 ms |
| Assinatura no PDF (entrega 1) | `manage.py test core.tests.OficioAssinaturaPdfTests --settings=config.settings_test` |
| Explorer Carta (entrega 2) | `manage.py test integrations.tests_carta_explorer --settings=config.settings_test` |
| Gestão Tendências (entrega 3) | `TendenciasGestaoView.vue` + `core.tests.TendenciaAPITests` |
| Clusterização (4.1) | `core.tests.ClusterServiceTests` + `CLUSTER_*` em settings |
| Par cluster retroativo (4.1b) | `core.tests.test_cluster_par_formacao` |
| Assinatura eletrônica (3.2–3.3) | `core.tests.test_assinatura_eletronica` + `/validar-assinatura/:codigo` |
| Preview PDF sem anexo (3.4) | `preview-envio-oficial` + `preview-envio-oficial-pdf` |
| KPIs trilha (P4) | `core.tests.test_dashboard_trilhas` + `DashboardTrilhaService` |
| Devolutiva + encerramento (4.5 + 6) | `core.tests.test_devolutiva_protocolo` + `core.tests.test_encerramento_legislativo` |
| Tramitação ponta a ponta SGDL | Migrações `0043`–`0050`; sem campos SEI/1Doc |
| C1 SLA carta (prazo padrão + política) | `0057` + `core.tests.test_prazo_demanda_service` + `/admin/configuracao-carta` |
| C2 carta → setor (despacho) | `0058` + `core.tests.test_carta_setor` + coluna setor em `/gestao-fluxo-servicos` |
| C4 hub de consultas | `/consulta` + `core.tests.test_consulta_hub` + `npm run build` |
| C5 assuntos + utilização SGDL | `0060` + `core.tests.test_carta_utilizacao` + `/admin/assuntos-carta` |
| C6 import RM271698 | `0059` + `core.tests.test_rm_unidades_import` + [runbook](operacao/importacao-unidades-rm271698.md) |
| U1 perfis e vínculos | [modulo-usuarios-perfis.md](especificacoes/modulo-usuarios-perfis.md) |
| Build frontend | `npm run build` |

---

**Última atualização:** 2026-06-10.  
**Status:** **Onda 3 C1–C6 concluídos** (jun/2026). **U1–U5** (governança usuários completa). **Próximo foco:** H1/H2 homologação; **C3** + **E2** (Celery).
