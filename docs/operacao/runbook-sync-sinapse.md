# Runbook operacional — Sync Sinapse (SGDL)

## Objetivo

Manter no PostgreSQL do SGDL um **espelho auditável** da carta de serviços lida na base Sinapse (`catalog_servico`), com status de mapeamento (`AUTO` / `UNMATCHED` / `MANUAL`) para a tela **Reconciliação Sinapse** (`/integracoes/sinapse/reconciliacao`).

## Quando rodar a rotina

| Evento | Comando recomendado |
|--------|---------------------|
| **Rotina diária** (alterações na carta) | `--incremental-sync` |
| **Após carga grande** na carta Sinapse (novos serviços, revisão em massa) | `--full-sync` (sem `--limit` baixo) |
| **Semanal** (integridade: o que sumiu da fonte) | `--reconcile` |
| **Após sync** (monitoramento) | `--sync-health-report` |
| **Alerta `UNMATCHED` alto** | `--list-unmatched` + tela web ou `--bind-manual` |

### O que o sync **não** substitui

- **Copiloto, formulários e triagem** leem o catálogo Sinapse **ao vivo** (`sinapse_catalog` → `catalog_servico`). Serviços novos na carta já entram na busca sem sync.
- O sync atualiza **`SinapseServiceSync`** e **`SinapseServicoMap`** no banco do SGDL (fila, saúde, auditoria).

Quando a base Sinapse for atualizada de forma relevante, rode sync no SGDL para alinhar espelho e métricas — não é obrigatório para cada edição de texto se o ID do serviço não mudou.

## Pré-requisitos

No `backend/.env`:

```env
SINAPSE_DB_NAME=...
SINAPSE_DB_USER=...
SINAPSE_DB_PASSWORD=...
SINAPSE_DB_HOST=...
SINAPSE_DB_PORT=5432
SINAPSE_SERVICE_TABLE=catalog_servico
```

Validação rápida:

```bash
cd /var/www/sgdl/backend
source venv/bin/activate   # se aplicável
python manage.py sync_sinapse_services --test-connection
python manage.py sync_sinapse_services --list-candidate-tables
# Deve listar public.catalog_servico (não carta_servicos)
python manage.py sync_sinapse_services --dry-run --limit 5
```

## Comandos operacionais

Use o venv do projeto e o diretório `backend`. Com `SINAPSE_SERVICE_TABLE` no `.env`, **não é obrigatório** repetir `--table` nos comandos.

### 1) Incremental diário

Processa registros com `updated_at` mais recente que o espelho local.

```bash
python manage.py sync_sinapse_services --incremental-sync
```

### 2) Full (após atualização relevante da carta)

Percorre toda a tabela. **Não use `--limit 200`** em produção se a carta tiver centenas de serviços (o limite corta o processamento).

```bash
python manage.py sync_sinapse_services --full-sync
```

Primeira carga ou homologação:

```bash
python manage.py sync_sinapse_services --full-sync
python manage.py shell -c "
from integrations.models import SinapseServicoMap
from django.db.models import Count
print('total:', SinapseServicoMap.objects.count())
print(list(SinapseServicoMap.objects.values('match_status').annotate(c=Count('id'))))
"
```

### 3) Reconciliação de integridade (semanal)

Marca como `DIVERGENT` registros que deixaram de existir na leitura atual da fonte.

```bash
python manage.py sync_sinapse_services --reconcile
```

### 4) Saúde e alerta

```bash
python manage.py sync_sinapse_services --sync-health-report
```

Com notificação (quando `alert_level` = `ALERT`):

```bash
python manage.py sync_sinapse_services --sync-health-report --notify-alert-email --notify-alert-webhook
```

API equivalente (Gestor/Protocolo): `GET /api/integrations/sinapse/sync-health/`

### 5) Fila de mapeamento pendente

```bash
python manage.py sync_sinapse_services --list-unmatched --limit 50
```

API: `GET /api/integrations/sinapse/unmatched/?match_status=UNMATCHED&limit=100`

### 6) Vinculação manual (CLI)

`--servico-id` é o **ID do serviço na carta Sinapse** (`catalog_servico.id`), não uma tabela legada do SGDL.

```bash
python manage.py sync_sinapse_services \
  --bind-manual \
  --sinapse-id 1066 \
  --servico-id 250 \
  --actor "operador_protocolo"
```

Na interface web: mesma operação em **Reconciliação Sinapse** → confirmar vínculo.

## Status de mapeamento

| Status | Significado |
|--------|-------------|
| `AUTO` | ID numérico existe em `catalog_servico` |
| `UNMATCHED` | ID visto na sync sem correspondência na carta |
| `MANUAL` | Confirmado por operador (web ou CLI) |

Com sync apenas em `catalog_servico` e IDs iguais ao catálogo, a fila tende a ficar toda `AUTO` até existir outra fonte de IDs externos.

## Política de alerta

`ALERT` quando:

- `unmatched_mappings >= SINAPSE_ALERT_UNMATCHED_THRESHOLD` (padrão 200)
- `divergent_sync_records >= SINAPSE_ALERT_DIVERGENT_THRESHOLD` (padrão 20)
- existir registro em `ERROR`

Variáveis: `SINAPSE_ALERT_EMAIL_RECIPIENTS`, `SINAPSE_ALERT_WEBHOOK_URL`.

## Ação em alerta

1. `GET /api/integrations/sinapse/sync-health/` ou `--sync-health-report`
2. `--list-unmatched` ou filtro `UNMATCHED` na tela
3. `--reconcile` se houver divergências de fonte
4. Vinculação manual (web/CLI) com `--actor` identificado
5. Reexecutar health report e registrar evidência

## Agendamento cron (futuro)

Arquivos de referência: `docs/operacao/ops/sinapse-sync.cron.example`, `docs/operacao/ops/sinapse-sync.service.example`.

Gerar/atualizar templates a partir do comando:

```bash
python manage.py sync_sinapse_services --generate-scheduler-artifacts
```

### Crontab sugerido (produção / homologação)

Ajuste usuário, caminho do Python (`venv`) e `DJANGO_SETTINGS_MODULE` conforme o servidor.

```cron
# Variáveis (exemplo)
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin

# Incremental diário — 08:00 (após manutenção usual da carta)
0 8 * * * cd /var/www/sgdl/backend && /var/www/sgdl/backend/venv/bin/python manage.py sync_sinapse_services --incremental-sync >> /var/log/sgdl/sinapse-sync.log 2>&1

# Full semanal — segunda 07:00 (carga completa do espelho)
0 7 * * 1 cd /var/www/sgdl/backend && /var/www/sgdl/backend/venv/bin/python manage.py sync_sinapse_services --full-sync >> /var/log/sgdl/sinapse-sync.log 2>&1

# Reconcile — domingo 06:30
30 6 * * 0 cd /var/www/sgdl/backend && /var/www/sgdl/backend/venv/bin/python manage.py sync_sinapse_services --reconcile >> /var/log/sgdl/sinapse-sync.log 2>&1

# Health report — 08:15 (após incremental)
15 8 * * * cd /var/www/sgdl/backend && /var/www/sgdl/backend/venv/bin/python manage.py sync_sinapse_services --sync-health-report --notify-alert-email --notify-alert-webhook >> /var/log/sgdl/sinapse-health.log 2>&1
```

### Checklist antes de ativar cron

- [ ] `.env` com `SINAPSE_SERVICE_TABLE=catalog_servico`
- [ ] `--test-connection` e `--dry-run` OK
- [ ] Um `--full-sync` manual executado com sucesso
- [ ] Diretório de log (`/var/log/sgdl/`) criado e permissões do usuário do cron
- [ ] Destinatários de e-mail/webhook configurados para alertas
- [ ] Evidência em homologação: `docs/operacao/homologacao-go-live.md`

## Documentação relacionada

- `docs/operacao/ops/sinapse-sync.cron.example`
- `docs/arquivo/infra/EVOLUCAO_SINAPSE_MOVA.md`
- `docs/operacao/homologacao-go-live.md` (evidências de sync)
