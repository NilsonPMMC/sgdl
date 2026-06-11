# Sprint 5 - Checklist Diario (Execucao)

Periodo de execucao: 2026-04-28  
Objetivo: implantar automacao operacional server-side, escalar reconciliacao e consolidar governanca para homologacao assistida.

## Dia 1 - Automacao operacional base
- [x] Implementar geracao de artefatos de agendamento (`cron`/`systemd`) via comando de gestao.
- [x] Definir template padrao para incremental diario, full semanal e health report.
- [x] Evidencia tecnica registrada.

## Dia 2 - Canal institucional de alerta
- [x] Integrar envio de e-mail quando `sync-health-report` retornar `ALERT`.
- [x] Parametrizar destinatarios por ambiente (`SINAPSE_ALERT_EMAIL_RECIPIENTS`).
- [x] Validar comportamento sem destinatario configurado (warning operacional).

## Dia 3 - Reconciliacao em escala (API)
- [x] Expor endpoint autenticado para fila `UNMATCHED`.
- [x] Expor endpoint autenticado para vinculacao manual.
- [x] Garantir retorno de erro de negocio sem traceback.

## Dia 4 - Qualidade de contrato
- [x] Ampliar testes de contrato para endpoints de reconciliacao.
- [x] Ampliar testes de contrato para envio de alerta por e-mail.
- [x] Executar suite dedicada da Sprint 5 com sucesso.

## Dia 5 - Operacao/documentacao
- [x] Registrar templates operacionais em `docs/ops/`.
- [x] Atualizar roadmap com status da Sprint 5 e riscos residuais.
- [x] Atualizar checklist de homologacao com evidencias da Sprint 5.

## Dia 6 - Gates tecnicos
- [x] `python manage.py check --deploy`
- [x] `DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test core.tests.SinapseSprint5ContractTests`
- [x] `npm run lint`
- [x] `npm run build`

## Dia 7 - Fechamento da sprint
- [x] Consolidar entregas tecnicas e operacionais.
- [x] Registrar riscos residuais para Sprint 6.
- [x] Encerrar sprint com status formal: concluida.
