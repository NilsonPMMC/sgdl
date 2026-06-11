# Sprint 6 - Checklist Diario (Execucao)

Periodo de execucao: 2026-04-28  
Objetivo: evoluir operacao assistida para escala com webhook institucional, filtros operacionais e vinculacao manual em lote.

## Dia 1 - Alerta institucional multi-canal
- [x] Adicionar notificacao via webhook no `sync-health-report` (`--notify-alert-webhook`).
- [x] Parametrizar URL e timeout em ambiente:
  - `SINAPSE_ALERT_WEBHOOK_URL`
  - `SINAPSE_ALERT_WEBHOOK_TIMEOUT`
- [x] Atualizar template de cron para disparo combinado (e-mail + webhook).

## Dia 2 - Reconciliacao escalavel (consulta)
- [x] Evoluir endpoint `UNMATCHED` com filtros operacionais:
  - `match_status`
  - `search`
  - `min_confidence`
- [x] Retornar metadados para triagem (`servico_local`, `audit`, `notes`).

## Dia 3 - Reconciliacao escalavel (acao em lote)
- [x] Implementar servico de vinculacao manual em lote (`bulk_bind_manual`).
- [x] Expor endpoint autenticado de lote:
  - `POST /api/integrations/sinapse/bind-manual-bulk/`
- [x] Manter trilha de auditoria em cada item.

## Dia 4 - Contratos e confiabilidade
- [x] Adicionar testes para filtros do endpoint `UNMATCHED`.
- [x] Adicionar testes para bind manual em lote.
- [x] Adicionar testes para alerta por webhook.

## Dia 5 - Configuracao e operacao
- [x] Atualizar `backend/.env.example` com variaveis de webhook.
- [x] Atualizar evidencias da homologacao com novos comandos da sprint.
- [x] Atualizar roadmap com status da Sprint 6.

## Dia 6 - Gates tecnicos
- [x] `python manage.py check --deploy`
- [x] `DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test core.tests.SinapseSprint5ContractTests`
- [x] `npm run lint`
- [x] `npm run build`

## Dia 7 - Fechamento
- [x] Consolidar risco residual de escala para painel frontend dedicado.
- [x] Registrar encerramento formal da Sprint 6.
