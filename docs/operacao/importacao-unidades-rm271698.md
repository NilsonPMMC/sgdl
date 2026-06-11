# Importação de unidades administrativas — RM271698

> **Entrega C6** · Planilha: [`../RM271698 - UNIDADES (1).xlsx`](../RM271698%20-%20UNIDADES%20(1).xlsx)  
> Spec: [carta-assuntos-utilizacao-unidades.md](../especificacoes/carta-assuntos-utilizacao-unidades.md)

---

## Resumo operacional (jun/2026)

| Métrica | Valor |
|---------|-------|
| Linhas na planilha | **1 191** |
| IDs únicos (`ID_UNIDADE`) | **1 120** |
| Linhas duplicadas (mesmo ID) | **71** |
| Unidades gravadas no banco | **1 120** |
| Órgãos RM mapeados (de-para) | **30** códigos em `docs/de-para-rm-sinapse.csv` |

**Por que 1 191 ≠ 1 120?** A planilha repete **45 IDs** em **71 linhas extras** (mesmo `ID_UNIDADE`, sigla e nome iguais na maioria dos casos). O SGDL importa **1 registro por ID**, não 1 por linha.

Relatório para conferência com a RM: **[rm271698-ids-duplicados-conferencia.md](rm271698-ids-duplicados-conferencia.md)**.

---

## De-para RM → Sinapse

Arquivo versionado: [`../de-para-rm-sinapse.csv`](../de-para-rm-sinapse.csv)

| COD_RM | sinapse_orgao_id | Órgão Sinapse |
|--------|------------------|---------------|
| SEMAE | 5 | Serviço Municipal de Águas e Esgotos |
| SMSBE | 3 | Secretaria de Saúde e Bem-Estar |
| SMAS | 2 | Secretaria de Assistência Social |
| … | … | (demais linhas no CSV) |

Gestão na UI: **Setores (UA)** → seção «De-para RM ↔ Sinapse».

API: `GET/PATCH /api/depara-rm-sinapse/`, `POST /api/depara-rm-sinapse/carregar-csv/`.

---

## Comandos

```bash
cd /var/www/sgdl/backend

# Simular (sem gravar)
python manage.py importar_unidades_rm271698 --dry-run

# Importação / re-sync (carrega CSV de-para antes)
python manage.py importar_unidades_rm271698

# Regenerar relatório de IDs duplicados
python manage.py gerar_relatorio_rm_duplicados
```

Via API (Gestor/Protocolo): `POST /api/unidades-administrativas/importar-rm/`  
Body: `{ "dry_run": false, "carregar_csv": true }`

---

## Regras de importação

1. **Chave:** `sinapse_unidade_id` = coluna `ID_UNIDADE` da planilha.
2. **Órgão Sinapse:** 2.º segmento da sigla (`MCRUZ-SMSBE-…` → `SMSBE`) → tabela `DeParaRmSinapse`.
3. **Sigla:** sigla RM completa (até 32 chars); se colidir no mesmo órgão, sufixo com ID.
4. **Merge:** unidades já existentes com o mesmo `sinapse_unidade_id` são **atualizadas**.
5. **Órfãos:** COD_RM sem mapeamento ativo **não importam** (dry-run lista pendências).

---

## Evidências

| Item | Comando / artefato |
|------|-------------------|
| Testes import | `manage.py test core.tests.test_rm_unidades_import --settings=config.settings_test` |
| Contagem banco | 1 120 registros com `sinapse_unidade_id` preenchido |
| Conferência duplicatas | `gerar_relatorio_rm_duplicados` → `rm271698-ids-duplicados-conferencia.md` |

---

**Última importação:** jun/2026 · **Próxima ação sugerida:** validar com RM os 45 IDs duplicados (prioridade: linhas com e-mail institucional vs. `sei_naoresponder@sp.gov.br`).
