# Sprint 1 - Plano de Execucao Tecnica (SGDL)

## Objetivo da Sprint

Entregar a base tecnica para evolucao com foco em:
- configuracao robusta de ambiente/servidor;
- base de observabilidade e seguranca;
- preparacao para integracoes (Sinapse e Kernel AI);
- validacao operacional com gates tecnicos.

Duracao sugerida: 5 a 8 dias uteis.

---

## Escopo da Sprint 1

### 1) Configuracao de ambiente e seguranca baseline

#### Arquivos-alvo
- `backend/config/settings.py`
- `backend/.env` (somente para homolog; sem commit de segredo real)
- `backend/config/urls.py` (health endpoint, se necessario)

#### Tarefas
- Padronizar variaveis por ambiente:
  - `ENVIRONMENT`, `DEBUG`, `SECRET_KEY`,
  - `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`,
  - flags de seguranca (`SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS`).
- Garantir comportamento seguro para homolog/producao.
- Validar ausencia de hardcode sensivel.

#### Validacao
- `python manage.py check --deploy` sem issues criticos.
- Smoke de login/autenticacao sem regressao.

---

### 2) Observabilidade minima e higiene de erro

#### Arquivos-alvo
- `backend/core/views.py`
- `backend/reports/views.py`
- `backend/core/signals.py`
- `backend/core/serializers.py`

#### Tarefas
- Remover prints/debug residuais de producao.
- Padronizar logs com `logger` (nivel info/warning/error).
- Garantir que respostas 500 nao exponham traceback para cliente.
- Incluir contexto minimo em logs de erro (acao, id da demanda/protocolo quando houver).

#### Validacao
- Testes de fluxos criticos sem erro.
- Revisao manual de payload de erro (sem detalhe interno sensivel).

---

### 3) Base para integracao com Sinapse (sem consumo definitivo ainda)

#### Arquivos-alvo (novos)
- `backend/integrations/` (app ou modulo dedicado)
- `backend/integrations/sinapse_client.py`
- `backend/integrations/services/sinapse_sync_service.py`
- `backend/integrations/management/commands/sync_sinapse_services.py`

#### Tarefas
- Criar esqueleto de cliente HTTP Sinapse (autenticacao, timeout, retries).
- Definir contrato minimo de payload da Carta de Servicos.
- Criar comando de sincronizacao dry-run para homolog.
- Registrar log de execucao e erros de integracao.

#### Validacao
- Execucao do comando de sync em modo dry-run.
- Log claro de sucesso/falha e tempo de resposta.

---

### 4) Base para integracao com Kernel AI (embeddings/chat)

#### Arquivos-alvo
- `backend/core/services/` (novo cliente dedicado)
- `backend/core/services/ai_kernel_client.py` (novo)
- `backend/config/settings.py` (variaveis do Kernel)
- `backend/core/tests.py` (testes de contrato com mocks)

#### Tarefas
- Criar cliente unico para chamadas ao Kernel:
  - `/v1/embeddings`
  - `/v1/similarity`
  - `/v1/chat`
- Definir timeout/retry por endpoint.
- Normalizar tratamento de erro de conectividade.
- Adicionar testes com mock de respostas do Kernel.

#### Validacao
- Testes de contrato do cliente (sucesso + timeout + erro 5xx).
- Log de latencia e status de chamada.

---

### 5) Qualidade e gates da sprint

#### Arquivos-alvo
- `backend/core/tests.py`
- `docs/HOMOLOGACAO_GO_LIVE_CHECKLIST.md`
- `docs/ROADMAP_SGDL_SERVIDOR_APIS_LLM.md`

#### Tarefas
- Expandir testes de smoke por perfil para cobrir regressao dos fluxos alterados.
- Atualizar checklist com evidencias da sprint.
- Consolidar checklist de saida da Sprint 1.

#### Validacao (gate de saida)
- Backend:
  - `DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test`
  - `python manage.py check --deploy`
- Frontend:
  - `npm run build`
  - lint dos arquivos alterados.

---

## Ordem de implementacao (sequencia recomendada)

1. `settings.py` + variaveis de ambiente (seguranca/base).
2. Higiene de logs/erros em views/signals/serializers.
3. Cliente Kernel AI + testes de contrato.
4. Esqueleto Sinapse + comando dry-run.
5. Reforco de testes de smoke e fechamento de evidencias.

---

## Riscos da Sprint 1 e mitigacao

- Risco: quebra por variavel de ambiente faltante.
  - Mitigacao: defaults seguros em dev/teste e checklist de env por ambiente.
- Risco: dependencia externa indisponivel (Sinapse/Kernel).
  - Mitigacao: mock + dry-run + fallback local sem bloquear fluxo principal.
- Risco: regressao em fluxos de demanda.
  - Mitigacao: smoke por perfil + testes de integracao existentes.

---

## Definicao de pronto da Sprint 1

- Ambiente de homologacao com configuracao segura e validada.
- Logs e erros padronizados sem vazamento sensivel.
- Cliente Kernel AI pronto e testado.
- Base de integracao Sinapse criada (dry-run funcional).
- Gates tecnicos verdes e evidencias registradas em docs.
