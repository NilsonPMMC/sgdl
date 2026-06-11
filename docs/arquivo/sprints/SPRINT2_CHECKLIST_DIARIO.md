# Sprint 2 - Checklist Operacional Diario

## Como usar

- Marcar cada item ao final do dia.
- Registrar bloqueios e decisoes no campo "Observacoes".
- So considerar dia concluido quando os criterios de saida forem atendidos.

---

## Dia 1 - Sinapse persistente (modelo e comando base)

### Tarefas
- [x] Definir/implementar estrutura de rastreabilidade de sync.
- [x] Evoluir comando `sync_sinapse_services` para modo persistente.
- [x] Garantir execucao idempotente no reprocessamento.

### Criterio de saida
- [x] `--full-sync` executa e persiste sem duplicidade.

### Observacoes
- Concluido em 2026-04-28.
- Estrutura de rastreabilidade criada em `integrations/models.py`:
  - `sinapse_service_id`, `version`, `hash_payload`, `payload`, `status_sync`, `divergencia`, `last_sync_at`.
- Migration criada/aplicada:
  - `integrations/migrations/0001_initial.py`
  - `python manage.py migrate integrations` (OK)
- Comando evoluido:
  - `sync_sinapse_services --full-sync` habilitado para persistencia.
- Validacao real com tabela Sinapse `public.catalog_servico`:
  - 1a execucao: `processed=557`, `created=557`, `updated=0`, `unchanged=0`.
  - 2a execucao: `processed=557`, `created=0`, `updated=0`, `unchanged=557` (idempotencia comprovada).

---

## Dia 2 - Sinapse incremental e reconciliacao

### Tarefas
- [x] Implementar `--incremental-sync` com base em `updated_at`.
- [x] Implementar modo de reconciliacao de divergencias.
- [x] Registrar logs de resumo (novos, atualizados, divergentes).

### Criterio de saida
- [x] Incremental processa somente alteracoes e gera resumo confiavel.

### Observacoes
- Concluido em 2026-04-28.
- Comando de sync atualizado com novos modos:
  - `--incremental-sync`
  - `--reconcile`
- Protecao adicionada para evitar uso simultaneo de modos (`--dry-run`, `--full-sync`, `--incremental-sync`, `--reconcile`).
- Incremental baseado em `updated_at`:
  - quando `updated_at` de origem <= `version` armazenada, registro e pulado sem reprocessar payload.
- Reconciliacao:
  - marca como `DIVERGENT` registros sem `service_name`;
  - marca como `DIVERGENT` registros locais nao encontrados na leitura atual da mesma tabela de origem.
- Validacao real em `public.catalog_servico`:
  - `--incremental-sync`: `processed=557`, `skipped_by_updated_at=557`, `created=0`, `updated=0`.
  - `--reconcile`: `processed=557`, `divergentes=0`.

---

## Dia 3 - Normalizacao da Carta de Servicos

### Tarefas
- [x] Normalizar `sla_days` para contrato interno utilizavel.
- [x] Normalizar `required_documents` e `channels`.
- [x] Definir regra de secretaria responsavel com fallback.

### Criterio de saida
- [x] Mapeamento minimo com qualidade suficiente em amostra real.

### Observacoes
- Concluido em 2026-04-28.
- Normalizacoes implementadas em `integrations/services/sinapse_sync_service.py`:
  - `sla_days`: parse de texto/HTML para inteiro (dias), com conversao aproximada de meses (`meses * 30`).
  - `required_documents`: normalizado para lista de strings (suporta JSON string/lista e texto livre).
  - `channels`: normalizado para lista de strings com fallback para telefone/canais.
- Regra de secretaria responsavel com fallback:
  - `provider_secretariat` -> `secretaria` -> `orgao` -> `departamento` -> `orgao_responsavel`.
- Validacao real:
  - `--dry-run --table public.catalog_servico --limit 5` com amostra mostrando:
    - `sla_days` normalizado (ex.: `15`, `30`, `120`);
    - `provider_secretariat` preenchido por `departamento` quando necessario.
  - `--full-sync --table public.catalog_servico --limit 200` para persistir normalizacao:
    - `processed=557`, `updated=557`.

---

## Dia 4 - Testes de contrato Sinapse

### Tarefas
- [x] Criar testes para payload completo, parcial e inconsistente.
- [x] Validar idempotencia do sync persistente.
- [x] Validar tratamento de erro de conectividade/timeout.

### Criterio de saida
- [x] Suite de testes do modulo Sinapse verde.

### Observacoes
- Concluido em 2026-04-28.
- Adicionada suite `SinapseSyncContractTests` em `backend/core/tests.py` cobrindo:
  - payload completo (normalizacao de `sla_days`, `required_documents`, `channels`);
  - payload parcial;
  - payload inconsistente;
  - idempotencia de `full_sync` (duas execucoes sem duplicidade);
  - erro de conectividade (propagacao de `SinapseClientError`).
- Validacao executada:
  - `DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test core.tests.SinapseSyncContractTests` (5 testes OK).

---

## Dia 5 - UX de homologacao por perfil

### Tarefas
- [x] Executar roteiro funcional por perfil (Vereador, Protocolo, Secretaria, Gestor).
- [x] Registrar evidencias dos fluxos de Demandas, Notificacoes e Relatorios.
- [x] Corrigir bloqueios de UX que impactem operacao.

### Criterio de saida
- [x] Fluxos minimos validados sem bloqueio funcional.

### Observacoes
- Concluido em 2026-04-28.
- Ajustes de UX/robustez aplicados:
  - `frontend/src/service/ApiService.js`
    - protecao para erro sem `response` no interceptor;
    - remocao de `console.log/error` de depuracao no fluxo de refresh token.
  - `frontend/src/views/RelatoriosView.vue`
    - remocao de logs de depuracao durante busca de relatorios.
- Evidencias de validacao dos fluxos:
  - `Demandas`: coberto em smoke por perfil (`HomologacaoSmokePorPerfilTests`) com fluxos de vereador/protocolo/secretaria/gestor.
  - `Notificacoes`: coberto em `EndpointsContratoTests` (autenticacao e isolamento por usuario).
  - `Relatorios`: coberto em smoke do gestor + `npm run build`/`npm run lint` sem erro.
- Validacoes executadas:
  - `DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test core.tests.HomologacaoSmokePorPerfilTests core.tests.EndpointsContratoTests` (8 testes OK)
  - `npm run lint` (OK)
  - `npm run build` (OK)

---

## Dia 6 - Operacao (backup, restore e rollback)

### Tarefas
- [x] Gerar backup (`.tar.gz`) e checksum (`.sha256`).
- [x] Executar teste de restore em ambiente controlado.
- [x] Atualizar plano de rollback com passo a passo objetivo.

### Criterio de saida
- [x] Evidencias operacionais registradas e verificadas.

### Observacoes
- Concluido em 2026-04-28.
- Backup gerado:
  - `.backups/sgdl_backup_20260428_123559.tar.gz`
  - checksum: `.backups/sgdl_backup_20260428_123559.tar.gz.sha256`
  - SHA256: `5b5c388de9535c4bfe2f678c4397a384bb5e96e9b3e56c8f27aca1bf3be8bf6c`
- Restore controlado validado:
  - destino `/tmp/sgdl_restore_test_20260428_123559`
  - estrutura `backend/`, `frontend/`, `docs/` confirmada.
- Snapshot Git salvo para auditoria:
  - `.backups/git_snapshot_20260428_123559.txt`
  - branch `main`, head `8d4511e4480236d803d3a14437a5fc8bddd2e2c9`.
- Plano de rollback objetivo registrado em `docs/HOMOLOGACAO_GO_LIVE_CHECKLIST.md`.

---

## Dia 7 - Consolidacao e fechamento da Sprint 2

### Tarefas
- [x] Atualizar `docs/HOMOLOGACAO_GO_LIVE_CHECKLIST.md` com evidencias da Sprint 2.
- [x] Atualizar `docs/ROADMAP_SGDL_SERVIDOR_APIS_LLM.md` com status e proximos passos.
- [x] Consolidar riscos residuais e plano da Sprint 3.

### Criterio de saida
- [x] Sprint 2 formalmente encerrada com definicao de pronto atendida.

### Observacoes
- Concluido em 2026-04-28.
- Consolidacao final realizada:
  - `docs/HOMOLOGACAO_GO_LIVE_CHECKLIST.md` atualizado com evidencias funcionais e operacionais da Sprint 2.
  - `docs/ROADMAP_SGDL_SERVIDOR_APIS_LLM.md` atualizado com status da Sprint 2 e plano objetivo da Sprint 3.
- Riscos residuais consolidados:
  - mapeamento de dominio entre catalogo Sinapse e `Servico` local ainda nao implementado;
  - validacao UX ainda baseada em evidencias funcionais/tecnicas, recomendada rodada assistida com usuarios;
  - backup/restore ainda manual (sem automacao agendada).
- Plano da Sprint 3 consolidado:
  - mapeamento Sinapse <-> Servico local;
  - governanca operacional da sincronizacao (agendamento + alertas);
  - rodada UX assistida com usuarios;
  - ampliacao de testes de contrato e fechamento do checklist de homologacao.

---

## Resumo de status da Sprint 2

- Progresso geral: [ ] 0-25%  [ ] 26-50%  [ ] 51-75%  [x] 76-100%
- Bloqueios ativos:
  - Nenhum bloqueio tecnico impeditivo para encerramento da Sprint 2.
- Decisoes tecnicas relevantes:
  - Sincronizacao Sinapse consolidada com modos `full`, `incremental` e `reconcile`, com rastreabilidade local.
  - Normalizacao de contrato aplicada em tempo de sync para estabilizar consumo interno do catalogo.
  - Evidencia de homologacao reforcada com backup, checksum, restore e snapshot Git auditavel.
- Responsavel pelo fechamento:
  - Time SGDL (registro tecnico assistido por agente).
