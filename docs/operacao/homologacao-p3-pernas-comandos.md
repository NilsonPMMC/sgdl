# Homologação P3 — pernas operacionais

Roteiro de comandos para deploy, migração legado e validação.  
Execute na ordem indicada (copie/cole no servidor).

---

## 1. Pré-requisitos

```bash
cd /var/www/sgdl
source venv/bin/activate
cd backend
```

---

## 2. Backup (recomendado antes de migrar legado)

```bash
# Ajuste usuário/host/banco conforme seu .env
pg_dump -Fc -h localhost -U sgdl_user sgdl_db > /var/www/sgdl/.backups/sgdl_pre_p3_$(date +%Y%m%d_%H%M).backup
sha256sum /var/www/sgdl/.backups/sgdl_pre_p3_*.backup | tail -1
```

---

## 3. Migration e check

```bash
cd /var/www/sgdl/backend
/var/www/sgdl/venv/bin/python manage.py migrate core --noinput
/var/www/sgdl/venv/bin/python manage.py check
/var/www/sgdl/venv/bin/python manage.py check --deploy
```

Migrations esperadas até **0067_perna_operacional**.

---

## 4. Testes (ambiente de teste)

```bash
cd /var/www/sgdl/backend
DJANGO_SETTINGS_MODULE=config.settings_test \
  /var/www/sgdl/venv/bin/python manage.py test \
    core.tests.test_perna_operacional \
    core.tests.test_despacho_destinos \
    core.tests.test_despacho_multi_visibilidade \
    --keepdb -v 1
```

---

## 5. Build frontend

```bash
cd /var/www/sgdl/frontend
npm run build
```

Após deploy: **hard refresh** no browser (Ctrl+Shift+R) ou aba anônima.

---

## 6. Reload backend (gunicorn homologação porta 8006)

```bash
# Ver processo
pgrep -af 'gunicorn.*8006'

# Reload graceful
kill -HUP $(pgrep -f 'gunicorn.*8006' | head -1)

# Confirmar que subiu
sleep 2 && curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8006/api/
```

---

## 7. Migração legado B5 → pernas (clones -D2)

**Somente** clusters multi-órgão **mesmo vereador** (não Super OS).

### 7.1 Simular (obrigatório primeiro)

```bash
cd /var/www/sgdl/backend
/var/www/sgdl/venv/bin/python manage.py migrar_clones_para_pernas --dry-run
```

### 7.2 Um cluster específico (piloto)

```bash
# Troque CLUSTER_ID pelo id do cluster multi-destino
/var/www/sgdl/venv/bin/python manage.py migrar_clones_para_pernas --dry-run --cluster-id CLUSTER_ID
/var/www/sgdl/venv/bin/python manage.py migrar_clones_para_pernas --cluster-id CLUSTER_ID
```

### 7.3 Uma demanda (líder ou clone)

```bash
# Ex.: demanda 3157
/var/www/sgdl/venv/bin/python manage.py migrar_clones_para_pernas --dry-run --demanda-id 3157
/var/www/sgdl/venv/bin/python manage.py migrar_clones_para_pernas --demanda-id 3157
```

### 7.4 Migrar todos elegíveis

```bash
/var/www/sgdl/venv/bin/python manage.py migrar_clones_para_pernas --dry-run
/var/www/sgdl/venv/bin/python manage.py migrar_clones_para_pernas
```

> **Nota:** clones legados **não são apagados** — permanecem no banco para auditoria.  
> A operação passa a usar as **pernas na demanda líder**. Clones antigos podem ser arquivados manualmente depois da validação.

---

## 8. Verificações pós-deploy (shell Django)

```bash
cd /var/www/sgdl/backend
/var/www/sgdl/venv/bin/python manage.py shell
```

```python
from core.models import Demanda
from core.models_perna_operacional import PernaOperacional

# Demanda específica
d = Demanda.objects.get(pk=SUBSTITUA_ID)
print("status:", d.status, "fluxo:", d.fluxo_roteamento)
for p in d.pernas_operacionais.all():
    print(f"  perna #{p.pk} org={p.sinapse_orgao_id} status={p.status} ua={p.unidade_administrativa_id}")

# Contagem global
print("Demandas com pernas:", Demanda.objects.filter(pernas_operacionais__isnull=False).distinct().count())
print("Pernas ativas:", PernaOperacional.objects.exclude(status="CANCELADA").count())
```

---

## 9. Smoke API (substitua TOKEN e DEMANDA_ID)

```bash
TOKEN="SEU_JWT"
DEMANDA_ID=123

curl -s -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8006/api/demandas/${DEMANDA_ID}/operacional/estado/" | python3 -m json.tool
```

Campos esperados: `usa_pernas_operacionais`, `pernas_operacionais`, `participantes_transversal`.

---

## 10. Roteiro browser (resumo)

| Passo | Perfil | Ação |
|-------|--------|------|
| 1 | Protocolo | Despacho multi-órgão → confirmar **1 demanda**, `total_pernas > 1`, sem `-D2` |
| 2 | Secretaria B | Demanda aparece na fila (visibilidade por perna) |
| 3 | Secretaria líder | Iniciar execução (C2) ou automático (C3) |
| 4 | Cada secretaria | Conclusão parcial (`perna_id` se multi-setor no mesmo órgão) |
| 5 | Protocolo | Conclusão final após gate fechar |

---

## 11. Rollback (se necessário)

```bash
# Restaurar backup
pg_restore -c -h localhost -U sgdl_user -d sgdl_db /var/www/sgdl/.backups/sgdl_pre_p3_XXXXXX.backup

# Reverter código
cd /var/www/sgdl && git checkout main -- backend/core frontend/src

# Reload
kill -HUP $(pgrep -f 'gunicorn.*8006' | head -1)
```

---

Índice: [fluxo-tramitacoes-cenarios.md](../especificacoes/fluxo-tramitacoes-cenarios.md)
