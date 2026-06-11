# Roadmap SGDL - Servidor, APIs e LLM (com Kernel compartilhado)

## Objetivo

Conduzir a evolucao do SGDL, apos homologacao operacional, para um patamar de estabilidade e escalabilidade com:
- infraestrutura de servidor previsivel;
- integracoes API interoperaveis (Sinapse/Carta de Servicos);
- camada de IA assistiva orientada a negocio;
- uso padronizado do Kernel compartilhado em `/opt/shared_ai_service/shared_ai_service`.

## Status atual (Sprint 1)

- Sprint 1 (hardening + bases de integracao) concluida em 2026-04-28.
- Entregas concluídas na Sprint 1:
  - seguranca/configuracao por ambiente;
  - padronizacao de logs e erros sem traceback em payload;
  - cliente AI Kernel com timeout/retry/fallback e testes de contrato;
  - integracao Sinapse inicial (cliente + sync dry-run + descoberta de tabela real);
  - gates tecnicos verdes (testes backend, `check --deploy`, lint, build frontend).
- Pendencias deliberadas para Sprint 2:
  - sincronizacao persistente full/incremental com tabela de rastreabilidade;
  - normalizacao de payload Sinapse (ex.: `prazo` HTML -> formato interno);
  - validacao UX fim-a-fim em homologacao com usuarios.

## Status atual (Sprint 2)

- Sprint 2 (Sinapse produtivo + qualidade de dados + operacao) concluida em 2026-04-28.
- Entregas concluídas na Sprint 2:
  - sincronizacao Sinapse com persistencia (`--full-sync`), incremental (`--incremental-sync`) e reconciliacao (`--reconcile`);
  - rastreabilidade de sync com `sinapse_service_id`, `version`, `hash_payload`, `status_sync`, `divergencia`, `last_sync_at`;
  - normalizacao de contrato (SLA em dias, documentos e canais em lista, secretaria com fallback);
  - suite de contrato Sinapse cobrindo payload completo/parcial/inconsistente, idempotencia e erro de conectividade;
  - validacao operacional com backup, checksum, restore controlado e plano de rollback registrado.
- Riscos residuais para o proximo ciclo:
  - vinculo entre catalogo Sinapse e entidade `Servico` local ainda sem reconciliacao de dominio;
  - evidencias de UX ainda baseadas em fluxo funcional/testes, faltando rodada assistida com usuarios de negocio;
  - automacao de rotina de backup/restore ainda manual.

## Status atual (Sprint 3)

- Sprint 3 concluida em 2026-04-28.
- Entregas concluídas na Sprint 3:
  - mapeamento de dominio Sinapse <-> `Servico` local (`SinapseServicoMap`);
  - fila operacional de reconciliacao (`--list-unmatched`) e vinculacao manual segura (`--bind-manual`);
  - auditoria de vinculacao manual (`last_manual_actor`, `last_manual_at`, historico em `notes`);
  - governanca de monitoramento com `--sync-health-report` e limiares configuraveis;
  - runbook operacional de sincronizacao (`docs/RUNBOOK_SYNC_SINAPSE.md`);
  - reforco de qualidade com ampliacao de testes de contrato Sinapse.
- Riscos residuais para o proximo ciclo:
  - automatizacao agendada (cron/systemd) ainda nao implantada no servidor de homolog;
  - alto volume de `UNMATCHED` demanda rotina continua de conciliacao manual;
  - ajustes finos de UX ainda dependem de rodada presencial com usuarios de negocio.

## Status atual (Sprint 4)

- Sprint 4 concluida em 2026-04-28.
- Entregas concluídas na Sprint 4:
  - consolidacao operacional dos comandos de sync para rotina diaria;
  - monitoramento ativo com `sync-health-report` e limiares por ambiente;
  - reforco de reconciliacao manual com trilha de auditoria;
  - documentacao de runbook e evidencias de homologacao atualizadas;
  - ampliacao de testes de contrato e validacao de gates tecnicos.
- Riscos residuais para o proximo ciclo:
  - automacao server-side (cron/systemd + notificacao externa) ainda depende de implantacao em ambiente alvo;
  - fila `UNMATCHED` requer processo recorrente de tratativa com priorizacao de negocio;
  - necessidade de painel administrativo dedicado para reconciliacao em escala.

## Status atual (Sprint 5)

- Sprint 5 concluida em 2026-04-28.
- Entregas concluídas na Sprint 5:
  - comando de sync com envio opcional de alerta por e-mail em `ALERT` (`--notify-alert-email`);
  - geracao automatizada de artefatos operacionais (`--generate-scheduler-artifacts`) em `docs/ops/`;
  - endpoints autenticados para reconciliacao em escala (`/api/integrations/sinapse/unmatched/` e `/api/integrations/sinapse/bind-manual/`);
  - cobertura de testes para endpoints da Sprint 5 e envio de alerta institucional.
- Riscos residuais para o proximo ciclo:
  - implante efetivo dos artefatos de agendamento no servidor depende de janela operacional da infraestrutura;
  - conciliacao em massa ainda sem interface frontend dedicada (somente API/operacao);
  - recomendada integracao adicional de alerta em canal de chat corporativo.

## Status atual (Sprint 6)

- Sprint 6 concluida em 2026-04-28.
- Entregas concluídas na Sprint 6:
  - alerta institucional por webhook no `sync-health-report` (`--notify-alert-webhook`);
  - endpoint de reconciliacao com filtros operacionais (`match_status`, `search`, `min_confidence`);
  - endpoint de vinculacao manual em lote (`/api/integrations/sinapse/bind-manual-bulk/`);
  - ampliacao de contratos para filtros, lote e webhook.
- Riscos residuais para o proximo ciclo:
  - ainda sem interface frontend dedicada para operacao massiva (API pronta, UX administrativa pendente);
  - webhook depende de endpoint institucional com politica de retry/fila externa;
  - recomendada segregacao por perfil/permissao especifica para operacao de reconciliacao.

## Status atual (Sprint 7)

- Sprint 7 concluida em 2026-04-28.
- Entregas concluídas na Sprint 7:
  - tela frontend de reconciliacao Sinapse com filtros operacionais e acao em lote;
  - integracao completa dos endpoints de reconciliacao (`unmatched`, `bind-manual`, `bind-manual-bulk`);
  - enforcement de acesso por perfil no frontend (rota/menu) e backend (403 para nao autorizados);
  - ampliacao de testes de contrato para autorizacao de perfis.
- Riscos residuais para o proximo ciclo:
  - necessario evoluir UX de lote para suportar mapeamento 1:N com selecao de servicos distintos por item;
  - recomendada pagina de auditoria historica dedicada para decisoes manuais;
  - manter observabilidade de latencia para fila de reconciliacao quando volume crescer.

---

## Principios de execucao

- Priorizar confiabilidade e observabilidade antes de novas features.
- IA em modo assistivo (sugere, nao decide sozinha).
- Integracoes externas com fallback e cache.
- Entregas pequenas, testaveis e com rollback simples.

---

## Fase 0 - Baseline de ambiente (D+0 a D+3)

### Entregaveis
- Perfil de ambiente formalizado: `development`, `homolog`, `production`.
- Inventario de variaveis de ambiente por ambiente.
- Padrao de segredo e rotacao (sem hardcode em codigo).

### Checklist tecnico
- Definir `ENVIRONMENT`, `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`.
- Validar `manage.py check --deploy` em homolog.
- Definir padrao de logs (JSON ou texto estruturado) para backend e integracoes.

### Criterio de aceite
- Ambiente de homologacao sobe com configuracao deterministica e sem warning critico de seguranca.

---

## Fase 1 - Servidor e operacao (D+3 a D+8)

### Entregaveis
- Runtime do SGDL em topologia padrao (Nginx + Gunicorn/Uvicorn + Postgres + Redis).
- Rotina de backup e restauracao testada.
- Monitoramento minimo com alertas operacionais.

### Acoes recomendadas
- Backend:
  - health endpoint de app e DB;
  - timeout e retry em chamadas externas;
  - limite de upload e protecao basica de abuso.
- Infra:
  - proxy reverso com TLS;
  - rotacao de logs;
  - rotina de backup de banco + arquivos (`media`) com teste de restore mensal.

### Criterio de aceite
- RTO e RPO acordados para homologacao operacional.
- Simulacao de restore concluida com sucesso.

---

## Fase 2 - Integracoes API (Sinapse + contratos internos) (D+8 a D+15)

### Entregaveis
- Cliente de integracao com Sinapse (Carta de Servicos).
- Sincronizacao full + incremental com rastreabilidade.
- Mapeamento entre servicos SGDL e IDs oficiais da carta.

### Arquitetura proposta
- `backend/integrations/sinapse_client.py`
- `backend/integrations/services/sinapse_sync_service.py`
- `backend/integrations/management/commands/sync_sinapse_services.py`
- Tabela de controle:
  - `sinapse_service_id`
  - `version`
  - `hash_payload`
  - `last_sync_at`
  - `status_sync`
  - `divergencia`

### Regras de resiliencia
- retry exponencial para timeout 5xx;
- circuit breaker simples para indisponibilidade;
- cache local de leitura para continuidade operacional;
- fila de reconciliacao para divergencias.

### Criterio de aceite
- Carta de Servicos sincronizada e auditavel.
- Fallback local funcional quando Sinapse estiver fora.

---

## Fase 3 - LLM e Kernel compartilhado (D+12 a D+22)

### Objetivo
Padronizar uso de IA no SGDL usando o Kernel compartilhado em:
- `/opt/shared_ai_service/shared_ai_service`

### Estado do Kernel (observado)
- Stack: FastAPI.
- Endpoints:
  - `GET /` (health)
  - `POST /v1/embeddings`
  - `POST /v1/similarity`
  - `POST /v1/chat`
- Embeddings: `mixedbread-ai/mxbai-embed-large-v1` (1024 dimensoes).
- Chat via Ollama com modelo padrao configuravel.

### Integracao SGDL recomendada
- Criar cliente unico no SGDL:
  - `backend/core/services/ai_kernel_client.py`
- Encapsular chamadas de:
  - embeddings (deduplicacao e busca semantica);
  - chat (pre-analise de texto para triagem assistiva).
- Definir contrato interno:
  - timeout curto (ex: 5-10s para embeddings, 20-30s para chat);
  - retries para erro transiente;
  - logs com `request_id` e latencia.

### Casos de uso iniciais (assistivos)
- Sugestao de categoria/urgencia na abertura.
- Resumo de demanda para protocolo.
- Sinalizacao de potencial duplicidade.

### Governanca de IA
- sem decisao automatica irreversivel;
- toda sugestao com confirmacao humana;
- auditoria: `prompt`, `resposta`, `modelo`, `tempo`, `aceite`.

### Criterio de aceite
- Integracao com Kernel estavel em homologacao, com fallback sem bloquear operacao.

---

## Fase 4 - UX e fluxo (D+18 a D+28)

### Entregaveis
- Fluxo guiado de abertura (inspirado no MOVA), sem quebrar painel admin atual.
- Etapa de confirmacao de entendimento antes de protocolar.
- Mensagens de erro/feedback padronizadas.

### Escopo minimo
- Entrada: descricao + localizacao + anexos.
- Pre-analise assistiva com possibilidade de correcao pelo usuario.
- Saida: protocolo, prazos e proximo passo claros.

### Criterio de aceite
- Taxa de conclusao maior que fluxo atual em teste controlado de homologacao.

---

## Fase 5 - Qualidade, seguranca e go-live tecnico (D+25 a D+35)

### Entregaveis
- Testes de contrato para APIs criticas.
- Smoke por perfil automatizado no pipeline.
- Checklist de go-live/homologacao atualizado com evidencias.

### Gates obrigatorios
- Backend:
  - `manage.py test`
  - `manage.py check --deploy`
- Frontend:
  - lint de arquivos alterados
  - build de producao
- Integracoes:
  - teste de conectividade Sinapse
  - teste de conectividade Kernel AI

### Criterio de aceite
- Todos os gates verdes e checklist de homologacao 100% concluido.

---

## Dependencias externas

- Sinapse:
  - endpoint e autenticacao oficiais da Carta de Servicos;
  - politica de limite de chamadas.
- Kernel:
  - disponibilidade do host/porta;
  - capacidade de CPU/RAM para embeddings;
  - disponibilidade do Ollama/modelo para chat.

---

## Riscos principais e mitigacao

- Indisponibilidade de integracao externa:
  - cache + fallback + retry + alertas.
- Variacao de qualidade LLM:
  - prompt versionado + validacao humana + metricas de aceite.
- Crescimento de latencia:
  - timeout por endpoint + monitoramento de p95/p99 + fila assíncrona para tarefas pesadas.

---

## Plano de implementacao sugerido (PRs)

1. PR-1: hardening de ambiente + observabilidade base.
2. PR-2: integracao Sinapse (cliente + sync + mapeamento).
3. PR-3: cliente Kernel AI + embeddings no SGDL.
4. PR-4: pre-analise assistiva (endpoint + UX minima).
5. PR-5: smoke por perfil + contrato de APIs + checklist final.

---

## Evidencias obrigatorias por fase

- comandos executados e saida resumida;
- endpoints validados e payload de exemplo;
- riscos encontrados e acao tomada;
- rollback testado quando aplicavel.

## Plano detalhado da Sprint 1

- Ver: `docs/SPRINT1_EXECUCAO_HOMOLOG.md`

## Plano detalhado da Sprint 2

- Ver: `docs/SPRINT2_EXECUCAO_HOMOLOG.md`
- Acompanhamento diario: `docs/SPRINT2_CHECKLIST_DIARIO.md`

## Plano objetivo da Sprint 2 (proximo ciclo)

1. Sinapse produtivo:
   - persistencia de sincronizacao (full + incremental);
   - tabela de vinculo entre catalogo Sinapse e servicos SGDL;
   - politicas de reconciliacao e auditoria de divergencia.
2. Qualidade de dados:
   - parser de campos ricos (HTML) para contrato interno limpo;
   - regra de priorizacao para secretaria responsavel e SLA.
3. UX de homologacao:
   - roteiro de validacao visual por perfil em ambiente homolog;
   - ajustes de feedback de tela e mensagens de fluxo.
4. Operacao:
   - finalizar evidencias de backup/rollback;
   - consolidar log operacional de homologacao com responsavel e data.

## Plano objetivo da Sprint 3 (proximo ciclo)

1. Vinculo de dominio Sinapse x SGDL:
   - implementar tabela de mapeamento `Servico` local <-> `sinapse_service_id`;
   - tratar divergencias com fila de reconciliacao e status operacional.
2. Governanca de sincronizacao:
   - job agendado (full semanal + incremental diario);
   - alerta operacional para erro e divergencia acima de limiar.
3. UX homolog assistida:
   - rodada guiada com usuarios por perfil (evidencia manual/ata curta);
   - ajustes de mensagens e estados de erro orientados a usabilidade.
4. Qualidade e entrega:
   - ampliar testes de contrato para comandos de gerenciamento;
   - consolidar checklist final de homologacao com evidencias da Sprint 3.

## Plano detalhado da Sprint 3

- Acompanhamento diario: `docs/SPRINT3_CHECKLIST_DIARIO.md`

## Plano detalhado da Sprint 5

- Acompanhamento diario: `docs/SPRINT5_CHECKLIST_DIARIO.md`

## Plano detalhado da Sprint 6

- Acompanhamento diario: `docs/SPRINT6_CHECKLIST_DIARIO.md`

## Plano detalhado da Sprint 7

- Acompanhamento diario: `docs/SPRINT7_CHECKLIST_DIARIO.md`

## Plano objetivo da Sprint 4 (proximo ciclo)

1. Automacao operacional:
   - implantar agendamento real no servidor (incremental diario + full semanal + health report);
   - integrar notificacao de alerta (e-mail/chat interno) para `ALERT`.
2. Reconciliacao assistida:
   - criar visao administrativa para fila `UNMATCHED` e vinculacao manual com busca de `Servico`;
   - priorizar top pendencias por impacto operacional.
3. UX com usuarios de negocio:
   - rodada presencial estruturada por perfil com ata curta de feedback;
   - refinamento de mensagens e microinteracoes de erro/sucesso.
4. Qualidade continua:
   - ampliar cobertura de testes para comando `sync_sinapse_services` (health/report modes);
   - manter gates tecnicos obrigatorios em toda entrega.

## Plano objetivo da Sprint 5 (proximo ciclo)

1. Implantacao operacional no servidor:
   - agendar `incremental`, `full` e `sync-health-report` em cron/systemd;
   - integrar alerta `ALERT` com canal institucional (e-mail/chat interno).
2. Reconciliacao em escala:
   - criar endpoint/painel administrativo para fila `UNMATCHED`;
   - suportar filtros, bulk actions e historico de decisoes.
3. UX com usuarios de negocio:
   - rodada presencial estruturada e backlog priorizado por impacto.
4. Qualidade e governanca:
   - adicionar testes de integracao para comandos e fluxos de mapeamento;
   - manter checklist de homologacao com evidencias por sprint.
