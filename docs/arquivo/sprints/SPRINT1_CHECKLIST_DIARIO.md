# Sprint 1 - Checklist Operacional Diario

## Como usar

- Marcar cada item ao final do dia.
- Registrar bloqueios e decisoes no campo "Observacoes".
- So considerar dia concluido quando os criterios de saida forem atendidos.

---

## Dia 1 - Ambiente e seguranca (base)

### Tarefas
- [x] Revisar variaveis de ambiente por perfil (`development`, `homolog`, `production`).
- [x] Ajustar `backend/config/settings.py` para comportamento seguro por ambiente.
- [x] Validar segredos (sem hardcode sensivel em codigo versionado).

### Criterio de saida
- [x] `python manage.py check --deploy` executa sem issue critica.

### Observacoes
- Concluido em 2026-04-28.
- Criado `backend/.env.example` com baseline por ambiente.
- `settings.py` atualizado com parser seguro de listas de env (`env_list` com trim).
- Validacao executada: `manage.py check --deploy` (OK).

---

## Dia 2 - Logs e tratamento de erro

### Tarefas
- [x] Remover `print` e debug residual de producao no backend.
- [x] Padronizar logs com `logger` por contexto (acao/endpoint).
- [x] Garantir payload de erro sem traceback para o cliente.

### Criterio de saida
- [x] Fluxos criticos respondem erro padrao sem exposicao interna.

### Observacoes
- Concluido em 2026-04-28.
- `backend/core/views.py` atualizado:
  - logs padronizados com `logger.warning/exception` com contexto de demanda/usuario;
  - removido `print` no fluxo de reset de senha;
  - limpeza de comentarios de depuracao.
- Validacoes executadas:
  - `manage.py check --deploy` (OK)
  - `DJANGO_SETTINGS_MODULE=config.settings_test manage.py test core.tests` (11 testes OK)
- Observacao: `print` remanescente apenas em migration historica (`core/migrations/0023...`), sem impacto operacional.

---

## Dia 3 - Cliente Kernel AI (fundacao)

### Tarefas
- [x] Criar `backend/core/services/ai_kernel_client.py`.
- [x] Implementar chamadas para:
  - [x] `POST /v1/embeddings`
  - [x] `POST /v1/similarity`
  - [x] `POST /v1/chat`
- [x] Definir timeout/retry por endpoint.

### Criterio de saida
- [x] Teste de conectividade com Kernel em `/opt/shared_ai_service/shared_ai_service` validado.

### Observacoes
- Concluido em 2026-04-28.
- Cliente criado em `backend/core/services/ai_kernel_client.py` com:
  - health check;
  - embeddings/similarity/chat;
  - retry com backoff + timeout por endpoint;
  - excecao customizada (`AIKernelClientError`) e logging de latencia.
- Configuracao adicionada em `backend/config/settings.py`:
  - `AI_KERNEL_BASE_URL`
  - `AI_KERNEL_TIMEOUT_EMBEDDINGS`
  - `AI_KERNEL_TIMEOUT_SIMILARITY`
  - `AI_KERNEL_TIMEOUT_CHAT`
  - `AI_KERNEL_MAX_RETRIES`
  - `AI_KERNEL_RETRY_BACKOFF_SECONDS`
- `backend/.env.example` atualizado com variaveis do Kernel.
- Testes adicionados em `core/tests.py` (contrato com mock).
- Dependencia adicionada: `requests==2.33.1` em `backend/requirements.txt`.
- Validacoes:
  - `manage.py test` (11 testes OK, incluindo contrato Kernel);
  - Conectividade real ao Kernel: `GET http://localhost:8004/` -> `200`.

---

## Dia 4 - Testes de contrato do Kernel

### Tarefas
- [x] Criar testes com mock para sucesso, timeout e erro 5xx.
- [x] Garantir logs de latencia e status das chamadas.
- [x] Revisar fallback quando Kernel indisponivel.

### Criterio de saida
- [x] Suite de testes de contrato do cliente AI verde.

### Observacoes
- Concluido em 2026-04-28.
- `AIKernelClient` atualizado:
  - log de falha com latencia (`tempo=%sms`) por tentativa;
  - fallback explicito com metodos seguros:
    - `embeddings_safe()`
    - `similarity_safe()`
    - `chat_safe()`
- Testes de contrato ampliados em `core/tests.py`:
  - sucesso;
  - timeout;
  - erro 5xx;
  - fallback seguro em indisponibilidade.
- Validacoes executadas:
  - `manage.py test core.tests.AIKernelClientContractTests` (5 testes OK)
  - `manage.py test core.tests.EndpointsContratoTests core.tests.HomologacaoSmokePorPerfilTests` com `settings_test` (8 testes OK)

---

## Dia 5 - Sinapse (esqueleto de integracao)

### Tarefas
- [x] Criar cliente `integrations/sinapse_client.py`.
- [x] Criar servico de sincronizacao `sinapse_sync_service.py`.
- [x] Criar comando `sync_sinapse_services.py` com modo dry-run.
- [x] Definir contrato minimo da Carta de Servicos.

### Criterio de saida
- [x] Dry-run de sincronizacao executado com log de sucesso/falha.

### Observacoes
- Concluido em 2026-04-28.
- Implementado app `integrations` e adicionado ao `INSTALLED_APPS`.
- Novos artefatos:
  - `backend/integrations/sinapse_client.py`
  - `backend/integrations/services/sinapse_sync_service.py`
  - `backend/integrations/management/commands/sync_sinapse_services.py`
- Variaveis adicionadas em `backend/config/settings.py` e `backend/.env.example`:
  - `SINAPSE_DB_NAME`, `SINAPSE_DB_USER`, `SINAPSE_DB_PASSWORD`, `SINAPSE_DB_HOST`, `SINAPSE_DB_PORT`
  - `SINAPSE_SERVICE_TABLE`
- Contrato minimo definido no mapeamento (`map_service_record`):
  - `service_id`, `service_name`, `provider_secretariat`, `sla_days`, `required_documents`, `channels`, `active`, `updated_at`, `raw`.
- Validacoes executadas:
  - `python manage.py check` (OK)
  - `python manage.py sync_sinapse_services --test-connection` (Conexao Sinapse OK)
  - `python manage.py sync_sinapse_services --list-candidate-tables` (retornou `public.catalog_servico`)
  - `python manage.py sync_sinapse_services --dry-run --table public.catalog_servico --limit 10` (OK, `fetched=10`, `missing_service_name=0`).

---

## Dia 6 - Smoke, regressao e gates tecnicos

### Tarefas
- [x] Executar smoke por perfil (Vereador, Protocolo, Secretaria, Gestor).
- [x] Rodar testes backend.
- [x] Rodar lint dos arquivos alterados no frontend.
- [x] Rodar build frontend.

### Criterio de saida
- [x] Gates tecnicos verdes:
  - [x] `DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test`
  - [x] `python manage.py check --deploy`
  - [x] `npm run build`
  - [x] lint sem erro nos arquivos alterados

### Observacoes
- Concluido em 2026-04-28.
- Validacoes executadas:
  - `DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test` (16 testes OK)
  - `DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test core.tests.HomologacaoSmokePorPerfilTests core.tests.EndpointsContratoTests` (8 testes OK)
  - `python manage.py check --deploy` (OK)
  - `npm run build` (OK)
  - `npm run lint` (OK apos saneamento de imports/variaveis nao usadas)
- Ajustes de lint aplicados:
  - `frontend/src/components/FloatingConfigurator.vue`
  - `frontend/src/layout/AppMenu.vue`
  - `frontend/src/views/MapaCalorView.vue`
  - `frontend/vite.config.mjs`

---

## Dia 7 - Consolidacao e evidencias

### Tarefas
- [x] Atualizar `docs/HOMOLOGACAO_GO_LIVE_CHECKLIST.md` com evidencias.
- [x] Atualizar `docs/ROADMAP_SGDL_SERVIDOR_APIS_LLM.md` com status da Sprint 1.
- [x] Consolidar riscos residuais e plano da Sprint 2.

### Criterio de saida
- [x] Sprint 1 formalmente encerrada com definicao de pronto atendida.

### Observacoes
- Concluido em 2026-04-28.
- Documentacao atualizada:
  - `docs/HOMOLOGACAO_GO_LIVE_CHECKLIST.md` com evidencias tecnicas executadas na Sprint 1.
  - `docs/ROADMAP_SGDL_SERVIDOR_APIS_LLM.md` com status atual da Sprint 1 e plano objetivo da Sprint 2.
- Riscos residuais consolidados:
  - backup/rollback ainda depende de evidencia operacional formal (`.tar.gz`, `.sha256`, log de restauracao);
  - mapeamento Sinapse ainda em modo dry-run (sem persistencia incremental);
  - validacao visual funcional por perfil no frontend pendente de rodada assistida com usuarios.
- Plano imediato de Sprint 2 definido:
  - persistencia de sync Sinapse + auditoria;
  - normalizacao do payload da carta de servicos;
  - validacao UX fim-a-fim em homologacao;
  - fechamento operacional de backup/rollback.

---

## Resumo de status da Sprint 1

- Progresso geral: [ ] 0-25%  [ ] 26-50%  [ ] 51-75%  [x] 76-100%
- Bloqueios ativos:
  - Nenhum bloqueio tecnico impeditivo para encerramento da Sprint 1.
- Decisoes tecnicas relevantes:
  - Sinapse iniciou via conexao direta ao banco para aceleracao de homologacao, mantendo contrato interno desacoplado.
  - Integracao AI Kernel mantida como camada assistiva com fallback resiliente e sem decisao automatica irreversivel.
  - Execucao de testes backend padronizada com `DJANGO_SETTINGS_MODULE=config.settings_test` para ambiente local sem permissao de create database.
- Responsavel pelo fechamento:
  - Time SGDL (registro tecnico assistido por agente).
