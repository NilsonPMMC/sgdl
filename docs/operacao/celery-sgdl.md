# Celery SGDL — worker isolado

> Runbook operacional · Índice: [OPERACAO.md](../OPERACAO.md)

O SGDL usa **broker e fila exclusivos** para não interferir em outros Celery do servidor (SIGA Gabinete, CIPTEA, etc.).

## Isolamento

| App | Redis DB | Fila padrão | systemd |
|-----|----------|-------------|---------|
| SIGA Gabinete | 0 | `siga_default` | `celery.service` |
| CIPTEA | 1 | (padrão CIPTEA) | `celery-ciptea.service` |
| **SGDL** | **15** | **`sgdl_default`** | **`celery-sgdl.service`** |

Prefixo de tasks: `sgdl.*` (ex.: `sgdl.verificar_atrasos`).

## Variáveis (`.env`)

```env
CELERY_ENABLED=true
CELERY_BROKER_URL=redis://127.0.0.1:6379/15
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/15
CELERY_TASK_DEFAULT_QUEUE=sgdl_default
```

Com `CELERY_ENABLED=false`, o Django opera normalmente; o comando `manage.py verificar_atrasos` continua disponível para cron manual.

## Instalação (homologação/produção)

```bash
sudo cp /var/www/sgdl/docs/operacao/ops/celery-sgdl.service.example /etc/systemd/system/celery-sgdl.service
sudo cp /var/www/sgdl/docs/operacao/ops/celery-sgdl-beat.service.example /etc/systemd/system/celery-sgdl-beat.service
sudo systemctl daemon-reload
sudo systemctl enable --now celery-sgdl.service celery-sgdl-beat.service
sudo systemctl status celery-sgdl.service
```

## Agendamento SLA

Beat dispara `sgdl.verificar_atrasos` **diariamente às 07:00** (America/Sao_Paulo) — notificações in-app para Protocolo, Gestor e Secretaria do órgão.

## Smoke

```bash
cd /var/www/sgdl/backend
../venv/bin/celery -A config inspect ping -d sgdl@$(hostname)
../venv/bin/python manage.py verificar_atrasos
```

Disparo manual assíncrono:

```bash
../venv/bin/python -c "
import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django; django.setup()
from core.tasks import verificar_atrasos_task
print(verificar_atrasos_task.delay().id)
"
```

## Rollback

```bash
sudo systemctl stop celery-sgdl-beat.service celery-sgdl.service
sudo systemctl disable celery-sgdl-beat.service celery-sgdl.service
# Reativar cron legado se necessário:
# 0 7 * * * cd /var/www/sgdl/backend && /var/www/sgdl/venv/bin/python manage.py verificar_atrasos
```
