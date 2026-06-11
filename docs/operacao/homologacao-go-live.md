# Checklist Final de Go-Live (Homologacao)

Este checklist define o criterio minimo para liberar o sistema para testes operacionais (homologacao).

## 1) Segurança e ambiente

- [x] `ENVIRONMENT` suportado por configuracao (`development`, `homolog`, `production`).
- [x] `SECRET_KEY` configurada por variavel de ambiente (sem hardcode fixo para producao).
- [x] `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` configurados por ambiente.
- [x] `CORS_ALLOWED_ORIGINS` parametrizado por ambiente.
- [x] `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` definidos por politica de ambiente.
- [x] `manage.py check --deploy` sem alertas impeditivos.

## 2) Backend e endpoints

- [x] Testes automatizados de fluxo critico passando (`manage.py test` com settings de teste).
- [x] Smoke por perfil validado:
  - [x] Vereador: lista/enviar demanda.
  - [x] Protocolo: despachar demanda.
  - [x] Secretaria: solicitar transferencia.
  - [x] Gestor: consultar KPIs e dashboard.
- [x] Endpoints de autenticacao JWT funcionando (`token` e `token/refresh`).
- [x] Erros 500 sem exposicao de traceback no payload.

## 3) Frontend e UX

- [x] Build de producao executa sem erro (`npm run build`).
- [x] Lint dos arquivos criticos sem erro.
- [x] Fluxo visual minimo validado:
  - [x] Lista de demandas por perfil.
  - [x] Tela de notificacoes com leitura e redirecionamento.
  - [x] Tela de relatorios com filtros e cards KPI.

## 4) Operacao e rollback

- [x] Backup completo do projeto armazenado e checksum registrado.
- [x] Snapshot do estado Git salvo para auditoria.
- [x] Plano de rollback definido (restaurar tar + voltar env).
- [x] Log de deploy/homologacao registrado com data e responsavel.

## Evidencias recomendadas

- Saida de `manage.py test`
- Saida de `manage.py check --deploy`
- Saida de `npm run build`
- Registro do backup (`.tar.gz` + `.sha256`)

## Evidencias executadas na Sprint 1 (2026-04-28)

- `python manage.py check --deploy` -> OK.
- `DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test` -> 16 testes OK.
- `DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test core.tests.HomologacaoSmokePorPerfilTests core.tests.EndpointsContratoTests` -> 8 testes OK.
- `npm run build` -> OK.
- `npm run lint` -> OK (apos saneamento de imports/variaveis nao usadas).
- Integracao Sinapse:
  - `python manage.py sync_sinapse_services --test-connection` -> conexao OK.
  - `python manage.py sync_sinapse_services --list-candidate-tables` -> `public.catalog_servico`.
  - `python manage.py sync_sinapse_services --dry-run --table public.catalog_servico --limit 10` -> OK (`fetched=10`, `missing_service_name=0`).

## Evidencias operacionais Sprint 2 (2026-04-28)

- Backup gerado:
  - arquivo: `.backups/sgdl_backup_20260428_123559.tar.gz`
  - checksum SHA256: `5b5c388de9535c4bfe2f678c4397a384bb5e96e9b3e56c8f27aca1bf3be8bf6c`
  - arquivo de checksum: `.backups/sgdl_backup_20260428_123559.tar.gz.sha256`
- Teste de restore controlado:
  - destino: `/tmp/sgdl_restore_test_20260428_123559`
  - validacao: estrutura `backend/`, `frontend/`, `docs/` restaurada com sucesso.
- Snapshot Git para auditoria:
  - `.backups/git_snapshot_20260428_123559.txt`
  - branch: `main`
  - head: `8d4511e4480236d803d3a14437a5fc8bddd2e2c9`
- Plano objetivo de rollback (homolog):
  1. Parar servicos do SGDL.
  2. Restaurar artefato: `tar -xzf .backups/sgdl_backup_20260428_123559.tar.gz -C <destino_controlado>`.
  3. Validar integridade com `sha256sum -c .backups/sgdl_backup_20260428_123559.tar.gz.sha256`.
  4. Restaurar variaveis de ambiente homolog e reiniciar backend/frontend.
  5. Executar smoke rapido (`check --deploy`, testes por perfil) e liberar ambiente.
- Registro operacional:
  - data/hora: 2026-04-28 12:35:59
  - responsavel tecnico: Time SGDL (execucao assistida por agente).

## Evidencias funcionais Sprint 2 (2026-04-28)

- Validacao por perfil (backend/fluxo):
  - `DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test core.tests.HomologacaoSmokePorPerfilTests core.tests.EndpointsContratoTests` -> 8 testes OK.
- Validacao de contrato Sinapse:
  - `DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test core.tests.SinapseSyncContractTests` -> 5 testes OK.
- Validacao frontend:
  - `npm run lint` -> OK.
  - `npm run build` -> OK.
- Observacao de escopo:
  - evidencias visuais desta sprint estao ancoradas em validacao funcional/tecnica;
  - rodada assistida com usuarios finais permanece recomendada como reforco da Sprint 3.

## Evidencias Sprint 3 (2026-04-28)

- Governanca de sincronizacao:
  - `python manage.py sync_sinapse_services --sync-health-report` -> `ALERT` operacional por `UNMATCHED` acima do limiar (monitoramento ativo).
  - runbook consolidado: `docs/operacao/runbook-sync-sinapse.md`.
- Reconciliacao de mapeamento:
  - `python manage.py sync_sinapse_services --list-unmatched --limit 3` -> fila retornada.
  - `python manage.py sync_sinapse_services --bind-manual --sinapse-id 1066 --servico-id 250 --actor sprint3-dia2` -> vinculacao manual auditada.
- Qualidade:
  - `DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test core.tests.SinapseSyncContractTests` -> 7 testes OK.
  - `python manage.py check --deploy` -> OK.
  - `npm run lint` -> OK.
  - `npm run build` -> OK.

## Evidencias Sprint 4 (2026-04-28)

- Governanca e alerta:
  - `python manage.py sync_sinapse_services --sync-health-report` validado com nivel `ALERT/OK`.
  - limiares configuraveis por ambiente:
    - `SINAPSE_ALERT_UNMATCHED_THRESHOLD`
    - `SINAPSE_ALERT_DIVERGENT_THRESHOLD`
- Reconciliacao operacional:
  - `python manage.py sync_sinapse_services --list-unmatched --limit 3` -> fila operacional retornada.
  - `python manage.py sync_sinapse_services --bind-manual --sinapse-id 1066 --servico-id 250 --actor sprint3-dia2` -> vinculacao manual auditada.
- UX e feedback:
  - melhorias de mensageria em notificacoes (`frontend/src/views/NotificacoesView.vue`) com validacao de lint/build.
- Qualidade:
  - `DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test core.tests.SinapseSyncContractTests` -> suite ampliada e verde.
  - `python manage.py check` e `python manage.py check --deploy` -> OK.

## Evidencias Sprint 5 (2026-04-28)

- Automacao operacional:
  - `python manage.py sync_sinapse_services --generate-scheduler-artifacts` -> templates gerados em `docs/operacao/ops/`.
  - artefatos: `docs/operacao/ops/sinapse-sync.cron.example` e `docs/operacao/ops/sinapse-sync.service.example`.
- Alerta institucional:
  - `python manage.py sync_sinapse_services --sync-health-report --notify-alert-email` -> envio condicional quando nivel `ALERT`.
  - destinatarios por ambiente: `SINAPSE_ALERT_EMAIL_RECIPIENTS`.
- Reconciliacao em escala:
  - endpoint autenticado de fila `UNMATCHED`: `/api/integrations/sinapse/unmatched/`.
  - endpoint autenticado de vinculo manual: `/api/integrations/sinapse/bind-manual/`.
- Qualidade:
  - `DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test core.tests.SinapseSprint5ContractTests` -> OK.
  - `python manage.py check --deploy` -> OK.
  - `npm run lint` e `npm run build` -> OK.

## Evidencias Sprint 6 (2026-04-28)

- Alerta institucional multi-canal:
  - `python manage.py sync_sinapse_services --sync-health-report --notify-alert-email --notify-alert-webhook` -> envio condicional para e-mail e webhook em `ALERT`.
  - variaveis adicionadas: `SINAPSE_ALERT_WEBHOOK_URL`, `SINAPSE_ALERT_WEBHOOK_TIMEOUT`.
- Reconciliacao em escala (API):
  - `GET /api/integrations/sinapse/unmatched/?match_status=UNMATCHED&search=<termo>&min_confidence=0`
  - `POST /api/integrations/sinapse/bind-manual-bulk/`
- Qualidade:
  - `DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test core.tests.SinapseSprint5ContractTests` -> suite ampliada (filtros, lote, webhook) e verde.
  - `python manage.py check --deploy` -> OK.
  - `npm run lint` e `npm run build` -> OK.

## Evidencias Sprint 7 (2026-04-28)

- Frontend operacional de reconciliacao:
  - nova tela: `/integracoes/sinapse/reconciliacao`
  - filtros operacionais: `match_status`, `search`, `min_confidence`, `limit`
  - acao em lote: `POST /api/integrations/sinapse/bind-manual-bulk/`
- Controle de acesso por perfil:
  - frontend: rota/menu restritos para `GESTOR` e `PROTOCOLO`
  - backend: endpoints retornam `403` para perfis nao autorizados
- Qualidade:
  - `DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test core.tests.SinapseSprint5ContractTests` -> suite ampliada (inclui autorizacao por perfil) e verde.
  - `python manage.py check --deploy` -> OK.
  - `npm run lint` e `npm run build` -> OK.

## 5) Ciclo legislativo ponta a ponta (H6)

Tramitação **100% interna** no SGDL (sem SEI/1Doc). Fluxo de referência:

```
RASCUNHO → assinatura eletrônica → AGUARDANDO_PROTOCOLO → PROTOCOLADO → EM_EXECUCAO
→ AGUARDANDO_DEVOLUTIVA_PROTOCOLO → DEVOLVIDO_VEREADOR → confirmar-ciência → FINALIZADO
```

Super OS (≥2 demandas do mesmo serviço + proximidade geográfica): protocolo `SUPER-AAAA-NNNN`.

### 5.1 Pré-requisitos técnicos

- [x] Migrações `0043`–`0050` aplicadas (`showmigrations core` sem pendências).
- [x] Campos e integrações SEI/1Doc removidos (`0049`).
- [x] Tipo de tramitação `EXECUCAO` disponível (`0050`).
- [x] Preview de ofício em disco compartilhado (multi-worker Gunicorn).
- [x] Assinatura gera **1** anexo PDF (`_assinado.pdf`).
- [x] Cluster: `CLUSTER_MIN_DEMANDAS=2`, `CLUSTER_FORMACAO_GRACE_MINUTES=20`.
- [x] Propagação de andamentos do líder para vinculados na Super OS.

### 5.2 Roteiro E2E — Vereador (H1)

> Backend/serviços validado em 2026-06-11 — demanda **2966** · [registro](homologacao-e2e-registro.md)

- [ ] Copiloto: criar rascunho com serviço Sinapse e endereço geocodificado.
- [ ] Revisar rascunho (texto, serviço, endereço) em «Editar rascunho do ofício».
- [ ] Pré-visualizar ofício (PDF via blob autenticado) antes do envio.
- [x] Assinar eletronicamente e enviar oficialmente → status `AGUARDANDO_PROTOCOLO`.
- [x] Confirmar **1** PDF anexo na demanda (sem duplicatas de preview).
- [x] Receber devolutiva (`DEVOLVIDO_VEREADOR`), registrar ciência e encerrar → `FINALIZADO`.
- [x] Ofício ao cidadão disponível no encerramento.

### 5.3 Roteiro E2E — Protocolo (H1)

- [ ] Listar fila de protocolados / aguardando despacho.
- [x] Despachar demanda individual → `PROTOCOLADO`.
- [ ] Despachar lote Super OS → protocolo `SUPER-*` e cluster visível em `/clusters`.
- [ ] Links entre processos vinculados na tela de detalhe (líder ↔ vinculados).
- [x] Despachar devolutiva ao vereador → `DEVOLVIDO_VEREADOR`.

### 5.4 Roteiro E2E — Secretaria (H1 + H4)

- [x] Fila operacional: `fila=operacionais` + `minha_unidade=1` (deep-link no dashboard).
- [x] Alternância «Meu setor» / «Toda secretaria» + filtro por setor.
- [x] Coluna **Setor**, **Parado há** e tag **N vinculados** na listagem.
- [x] Super OS: listagem e detalhe mostram só a **demanda líder** (protocolo na coluna).
- [x] Iniciar execução na demanda líder → `EM_EXECUCAO` (serviços — comando E2E; UI/API pendente validação visual).
- [ ] Registrar andamento tipo `EXECUCAO` no líder → replica nos vinculados.
- [x] Solicitar devolutiva → `AGUARDANDO_DEVOLUTIVA_PROTOCOLO` (serviços — comando E2E).

### 5.5 Roteiro E2E — Super OS e cluster (H3)

- [x] Ação «Cluster» oculta quando demanda não elegível (<2 ou já protocolada).
- [ ] Par retroativo: segunda demanda do mesmo serviço clusteriza com a já protocolada.
- [ ] Coorte AUTO: lote despachado forma Super OS antes do protocolo individual.
- [ ] Graça de formação (`CLUSTER_FORMACAO_GRACE_MINUTES`) respeitada no fluxo automático.
- [ ] `reconciliar_servico()` disponível para casos fora da janela de graça.

### 5.6 Roteiro E2E — Gestor

- [x] Dashboard com KPIs e resumo operacional (API 200 — registro E2E).
- [ ] Relatórios com filtros e exportação.
- [ ] Reconciliação Sinapse (`/integracoes/sinapse/reconciliacao`) — perfil autorizado.

### 5.7 UX — estados vazios e erros (H5)

- [x] Mensagem contextual quando a lista está vazia (por fila e perfil).
- [x] Banner de erro com detalhe da API + botão «Tentar novamente».
- [x] Mensagens distintas para filas protocolados / operacionais / devolutivas.
- [x] Query `?fila=` sincronizada na URL (deep-link).

### 5.8 Registro de observações de teste (H2)

Formato: `tela · perfil · esperado · obtido · severidade`

**Gate A1:** nenhum item **bloqueante** no roteiro 5.2–5.6 antes de abrir piloto (Fase 5). Consolidar achados em `docs/ROADMAP.md` (Onda 1).

---

## 6) Procedimento de deploy (homologação)

Executar na ordem após backup restaurável (checksum em `.backups/`):

```bash
# 1. Backend — migrações e checagem
cd /var/www/sgdl/backend
python manage.py migrate
python manage.py check --deploy

# 2. Reiniciar workers (ajustar nome do serviço conforme ambiente)
sudo systemctl reload gunicorn-sgdl.service

# 3. Frontend — build de produção
cd /var/www/sgdl/frontend
npm run build

# 4. Smoke pós-deploy (opcional, recomendado)
cd /var/www/sgdl/backend
python manage.py test core.tests.HomologacaoSmokePorPerfilTests \
  core.tests.test_assinatura_eletronica \
  core.tests.test_cluster_par_formacao \
  core.tests.test_atraso_demanda_service \
  --settings=config.settings_test

# 5. Celery SGDL (se CELERY_ENABLED=true)
sudo systemctl restart celery-sgdl.service celery-sgdl-beat.service
sudo systemctl status celery-sgdl.service --no-pager
```

**Nota:** a suite completa em SQLite (`settings_test`) pode falhar em migrações pgvector; em homologação operacional preferir Postgres de teste ou rodar os módulos listados acima.

---

## 7) Critérios go / no-go

| Critério | Go | No-go |
|----------|----|-------|
| Segurança (seção 1) | Todos os itens marcados | Qualquer item crítico em aberto |
| `check --deploy` | 0 erros; warnings SSL aceitos em dev/homolog | Erros impeditivos |
| Build frontend | `npm run build` sem falha | Build quebrado |
| Fluxo legislativo (5.2–5.5) | Roteiro E2E validado por perfil (H1) | Bloqueante não resolvido |
| Super OS | Formação + propagação de andamentos OK | Cluster não forma ou não replica |
| PDF ofício | 1 anexo por demanda assinada | Múltiplos PDFs ou hash divergente no envio |
| Backup | Artefato + SHA256 registrados | Deploy sem backup restaurável |
| Observações H2 | Nenhum bloqueante aberto | Bloqueante sem mitigação |

**Decisão:** preencher a tabela de registro (seção 8) com **GO** ou **NO-GO** e responsável.

---

## 8) Registro de homologação (assinatura)

| Campo | Valor |
|-------|-------|
| Data | _preencher na rodada E2E_ |
| Ambiente | homologação operacional |
| Versão Git (HEAD) | _preencher_ |
| Backup + SHA256 | _referenciar `.backups/`_ |
| Responsável técnico | _nome_ |
| Responsável negócio | _nome_ |
| Resultado | ☐ GO &nbsp; ☐ NO-GO |
| Observações H2 pendentes | _listar ou «nenhuma bloqueante»_ |

---

## Evidências Onda 1 (jun/2026)

Comandos executados na consolidação do H6:

```bash
cd /var/www/sgdl/backend
python manage.py check --deploy          # OK (5 warnings SSL/DEBUG esperados em homolog)
python manage.py showmigrations core     # 0043–0050 aplicadas [X]

cd /var/www/sgdl/frontend
npm run build                            # OK (built em ~8s)
```

Suites de teste recomendadas (Postgres ou módulos isolados):

- `core.tests.test_assinatura_eletronica` — preview sem anexo + 1 PDF na assinatura.
- `core.tests.test_cluster_par_formacao` — par com demanda já protocolada.
- `core.tests.test_devolutiva_protocolo` + `test_encerramento_legislativo`.
- `core.tests.HomologacaoSmokePorPerfilTests` — smoke por perfil.

Configuração cluster validada: `CLUSTER_MIN_DEMANDAS=2`, `CLUSTER_FORMACAO_GRACE_MINUTES=20`.

---

## Proxima fase (apos homologacao)

- Roadmap: [ROADMAP.md](../ROADMAP.md) — Ondas 2 (polimento) e 3 (piloto).
- Especificacao Onda 2 (P6–P14): [especificacoes/onda2-polimento-ux.md](../especificacoes/onda2-polimento-ux.md) — painel oficio, numeracao, tramitacoes vereador, UX dashboard/demanda, acessos.
- Evolucao Sinapse/MOVA: `docs/arquivo/infra/EVOLUCAO_SINAPSE_MOVA.md`
