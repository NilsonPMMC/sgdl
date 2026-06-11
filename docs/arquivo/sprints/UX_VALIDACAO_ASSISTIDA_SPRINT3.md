# Validacao UX Assistida - Sprint 3

## Objetivo

Registrar uma rodada guiada de validacao de fluxos criticos por perfil com foco em entendimento operacional e bloqueios de uso.

## Escopo avaliado

- Demandas (listagem, status e acoes por perfil)
- Notificacoes (leitura, marcar como lida e redirecionamento)
- Relatorios (filtros, KPIs e consistencia de exibicao)

## Perfis cobertos

- Vereador
- Protocolo
- Secretaria
- Gestor

## Evidencias tecnicas usadas na rodada

- Smoke por perfil:
  - `DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test core.tests.HomologacaoSmokePorPerfilTests` (OK)
- Contrato de notificacoes:
  - `DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test core.tests.EndpointsContratoTests` (OK)
- Frontend:
  - `npm run lint` (OK)
  - `npm run build` (OK)

## Achados e ajustes aplicados

- `frontend/src/service/ApiService.js`
  - tratamento defensivo para erros sem `response` no interceptor de token.
- `frontend/src/views/RelatoriosView.vue`
  - remocao de logs de depuracao de console no fluxo principal.

## Resultado

- Fluxos minimos avaliados sem bloqueio funcional impeditivo para homologacao tecnica.
- Pendencia de processo:
  - rodada presencial com usuarios de negocio permanece recomendada para captura de feedback qualitativo fino (linguagem, clareza e treinamento).
