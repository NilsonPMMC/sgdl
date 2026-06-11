# Sprint 7 - Checklist Diario (Execucao)

Periodo de execucao: 2026-04-28  
Objetivo: entregar camada frontend para reconciliacao operacional em escala, com controle de acesso por perfil e fluxo de vinculacao em lote.

## Dia 1 - Estrutura de tela administrativa
- [x] Criar view de reconciliacao Sinapse no frontend.
- [x] Exibir fila de mapeamentos com tabela paginada.
- [x] Adicionar filtros operacionais (status, busca, confianca minima, limite).

## Dia 2 - Acao operacional em lote
- [x] Integrar selecao multipla de itens da fila.
- [x] Integrar vinculacao manual em lote para servico local unico.
- [x] Exibir resumo de processamento (sucesso/erros) via toast.

## Dia 3 - Acao individual assistida
- [x] Integrar vinculacao manual por linha (item individual).
- [x] Exibir metadados de auditoria para triagem.
- [x] Garantir refresh de fila apos operacao.

## Dia 4 - Navegacao e UX
- [x] Registrar rota protegida para reconciliacao.
- [x] Incluir item de menu visivel apenas para perfis operacionais.
- [x] Ajustar guard de rota para enforcement de `meta.perfis`.

## Dia 5 - Seguranca de acesso no backend
- [x] Restringir endpoints de reconciliacao para `GESTOR` e `PROTOCOLO`.
- [x] Retornar `403` padrao para perfis sem permissao.
- [x] Preservar mensagens sem exposicao de traceback.

## Dia 6 - Qualidade e testes
- [x] Ampliar testes de contrato para autorizacao de perfis.
- [x] Executar:
  - `python manage.py check --deploy`
  - `DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test core.tests.SinapseSprint5ContractTests`
  - `npm run lint`
  - `npm run build`

## Dia 7 - Fechamento e governanca
- [x] Atualizar roadmap com status Sprint 7 e riscos residuais.
- [x] Atualizar checklist de homologacao com evidencias da sprint.
- [x] Encerrar sprint formalmente como concluida.
