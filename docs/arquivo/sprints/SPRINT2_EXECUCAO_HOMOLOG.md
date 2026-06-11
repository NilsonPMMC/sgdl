# Sprint 2 - Plano de Execucao Tecnica (SGDL)

## Objetivo da Sprint

Transformar as bases da Sprint 1 em capacidade operacional de homologacao com:
- sincronizacao Sinapse persistente e auditavel;
- normalizacao de dados da Carta de Servicos para uso real no SGDL;
- validacao UX fim-a-fim por perfil;
- fechamento operacional de backup/rollback.

Duracao sugerida: 5 a 8 dias uteis.

---

## Escopo da Sprint 2

### 1) Sinapse produtivo (persistencia e rastreabilidade)

#### Arquivos-alvo
- `backend/integrations/sinapse_client.py`
- `backend/integrations/services/sinapse_sync_service.py`
- `backend/integrations/management/commands/sync_sinapse_services.py`
- `backend/core/models.py` (ou app dedicado para mapeamento)
- `backend/core/tests.py` (ou testes do app integrations)

#### Tarefas
- Evoluir sync de `dry-run` para modo persistente controlado.
- Criar estrutura de rastreabilidade de sincronizacao:
  - `sinapse_service_id`
  - `hash_payload`
  - `last_sync_at`
  - `status_sync`
  - `divergencia`
- Implementar estrategia de execucao:
  - `--full-sync`
  - `--incremental-sync` (baseado em `updated_at`)
  - `--reconcile` para inconsistencias.

#### Validacao
- Full sync executa sem erro com log de resumo.
- Incremental sync atualiza somente registros alterados.
- Reexecucao idempotente (sem duplicidade local).

---

### 2) Qualidade de dados Sinapse (contrato interno limpo)

#### Arquivos-alvo
- `backend/integrations/services/sinapse_sync_service.py`
- `backend/core/models.py` / serializers relacionados a `Servico`
- testes de mapeamento em `backend/core/tests.py` (ou arquivo dedicado)

#### Tarefas
- Normalizar campos ricos (HTML) para contrato interno:
  - `sla_days` (texto -> numero quando possivel),
  - `required_documents`,
  - `channels`.
- Definir regra para secretaria provedora (`provider_secretariat`) e fallback.
- Padronizar status ativo/inativo do catalogo interoperavel.

#### Validacao
- Amostra real do Sinapse mapeada sem campos criticos nulos indevidos.
- Testes cobrindo ao menos:
  - payload completo;
  - payload parcial;
  - payload inconsistente.

---

### 3) UX de homologacao (validacao funcional guiada)

#### Arquivos-alvo
- `frontend/src/views/DemandasView.vue`
- `frontend/src/views/NotificacoesView.vue`
- `frontend/src/views/RelatoriosView.vue`
- `docs/HOMOLOGACAO_GO_LIVE_CHECKLIST.md`

#### Tarefas
- Executar roteiro assistido de validacao por perfil:
  - Vereador, Protocolo, Secretaria, Gestor.
- Registrar evidencias visuais e funcionais dos fluxos minimos:
  - abertura/listagem de demanda,
  - notificacoes com leitura/redirecionamento,
  - relatorios com filtros/KPIs.
- Ajustar feedbacks de interface que bloqueiem entendimento do fluxo.

#### Validacao
- Fluxos minimos validados sem bloqueio funcional.
- Checklist de UX da homologacao marcado com evidencias.

---

### 4) Operacao: backup, restore e rollback

#### Arquivos-alvo
- `docs/HOMOLOGACAO_GO_LIVE_CHECKLIST.md`
- `docs/ROADMAP_SGDL_SERVIDOR_APIS_LLM.md`
- registro operacional (local acordado pelo time)

#### Tarefas
- Gerar backup tecnico do estado atual:
  - pacote `.tar.gz`;
  - hash `.sha256`.
- Executar teste de restauracao controlado.
- Documentar plano de rollback objetivo (passo a passo).
- Registrar data/responsavel da validacao operacional.

#### Validacao
- Evidencia de backup e checksum anexada.
- Restore validado com sucesso em ambiente controlado.

---

### 5) Gates e encerramento da sprint

#### Tarefas
- Consolidar evidencias tecnicas e operacionais.
- Atualizar checklist diario e roadmap com status da Sprint 2.
- Registrar riscos residuais para Sprint 3.

#### Validacao (gate de saida)
- Backend:
  - `DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test`
  - `python manage.py check --deploy`
- Frontend:
  - `npm run lint`
  - `npm run build`
- Integracao:
  - `python manage.py sync_sinapse_services --full-sync`
  - `python manage.py sync_sinapse_services --incremental-sync`

---

## Ordem de implementacao (sequencia recomendada)

1. Persistencia Sinapse (modelo + comando + idempotencia).
2. Normalizacao de payload e testes de mapeamento.
3. Validacao UX por perfil e ajustes pontuais.
4. Backup/restore/rollback com evidencia formal.
5. Gates finais e consolidacao documental.

---

## Riscos da Sprint 2 e mitigacao

- Risco: divergencia de schema da base Sinapse.
  - Mitigacao: introspeccao de tabela + parser resiliente + log de incompatibilidade.
- Risco: regressao em cadastro/lista de servicos locais.
  - Mitigacao: sync idempotente + testes de contrato + execucao incremental controlada.
- Risco: indisponibilidade do barramento durante sincronizacao.
  - Mitigacao: retry + retomada incremental + fallback para dados locais existentes.
- Risco: validacao UX incompleta por falta de janela operacional.
  - Mitigacao: roteiro curto por perfil + evidencias minimas obrigatorias.

---

## Definicao de pronto da Sprint 2

- Sinapse sincronizando com persistencia, rastreabilidade e idempotencia.
- Contrato da Carta de Servicos normalizado para consumo interno.
- Fluxos UX minimos validados por perfil em homologacao.
- Evidencias de backup/restore/rollback registradas.
- Gates tecnicos e integracao executados com sucesso.
