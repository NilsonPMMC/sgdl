# Operação e homologação — SGDL

Procedimentos para ambiente de homologação/produção. Configuração sensível: `backend/.env` (modelo em `backend/.env.example`).

---

## Checklist go-live

Documento canônico com critérios de segurança, testes, UX, ciclo legislativo (H6), deploy e go/no-go:

**[homologacao-go-live.md](operacao/homologacao-go-live.md)** — seções 1–4 (gates técnicos), 5 (roteiro E2E por perfil), 6 (deploy), 7–8 (go/no-go e assinatura).

Gates mínimos antes de liberar homologação operacional:

```bash
cd backend
python manage.py test --settings=config.settings_test
python manage.py check --deploy

cd ../frontend
npm run build
```

---

## Sync Sinapse (carta de serviços)

Runbook completo:

**[runbook-sync-sinapse.md](operacao/runbook-sync-sinapse.md)**

| Rotina | Comando |
|--------|---------|
| Diário (alterações na carta) | `python manage.py sync_sinapse_services --incremental-sync` |
| Carga grande | `--full-sync` |
| Semanal (integridade) | `--reconcile` |
| Monitoramento | `--sync-health-report` |

Artefatos de agendamento: [operacao/ops/](operacao/ops/) (`sinapse-sync.cron.example`, `sinapse-sync.service.example`).

**Nota:** Copiloto e triagem leem `catalog_servico` **ao vivo**; o sync mantém espelho auditável (`SinapseServiceSync`, `SinapseServicoMap`) para reconciliação na UI.

---

## Fluxo AUTO/MANUAL (Protocolo)

Guia operacional — despacho automático por serviço, Copiloto e `SINAPSE_AUTOFILL_THRESHOLD`:

**[fluxo-auto-manual.md](operacao/fluxo-auto-manual.md)** · API: [apis/fluxo-protocolo.md](apis/fluxo-protocolo.md)

Tela Gestor: `/gestao-fluxo-servicos`.

---

## Unidades administrativas (RM271698)

Importação da planilha oficial de setores para `UnidadeAdministrativa` (entrega C6):

**[importacao-unidades-rm271698.md](operacao/importacao-unidades-rm271698.md)**

| Rotina | Comando |
|--------|---------|
| Simular import | `python manage.py importar_unidades_rm271698 --dry-run` |
| Import / re-sync | `python manage.py importar_unidades_rm271698` |
| Conferência duplicatas | `python manage.py gerar_relatorio_rm_duplicados` |

Tela: `/gestao-setores` (de-para RM ↔ Sinapse + botão importar).  
Conferência: [rm271698-ids-duplicados-conferencia.md](operacao/rm271698-ids-duplicados-conferencia.md) (1 191 linhas → 1 120 IDs únicos).

---

## Celery SGDL (SLA isolado)

Worker e beat **exclusivos** do SGDL (Redis DB **15**, fila `sgdl_default`) — não compartilham broker com SIGA/CIPTEA:

**[celery-sgdl.md](operacao/celery-sgdl.md)**

| Rotina | Comando / serviço |
|--------|-------------------|
| Worker | `systemctl status celery-sgdl.service` |
| Beat (07:00) | `systemctl status celery-sgdl-beat.service` |
| Manual | `python manage.py verificar_atrasos` |

---

- Backup restaurável antes de mudanças estruturais (checksum registrado).
- Plano de rollback: restaurar tarball + reverter `.env` — detalhes no checklist de homologação.
- Regra do projeto: ver `.cursor/rules/homologacao-readiness.mdc`.

---

## Serviços (referência)

| Serviço | Função |
|---------|--------|
| `gunicorn-sgdl` | API Django |
| Nginx | Proxy / TLS / estáticos frontend |
| PostgreSQL | SGDL + extensão pgvector |
| Kernel AI (`AI_KERNEL_BASE_URL`) | Embeddings |

Reload após deploy de código:

```bash
sudo systemctl reload gunicorn-sgdl.service
```

---

## Documentação relacionada

- [README.md](README.md) — índice mestre
- [PROJETO.md](PROJETO.md) — arquitetura e variáveis de IA
- [ROADMAP.md](ROADMAP.md) — prioridades de produto
