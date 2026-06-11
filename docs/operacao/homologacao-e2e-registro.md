# Registro E2E homologação — Gate A1 (H1/H2)

> **Formato H2:** `tela · perfil · esperado · obtido · severidade`  
> Índice: [homologacao-go-live.md](homologacao-go-live.md) · Roadmap: [ROADMAP.md](../ROADMAP.md)

---

## Execução automatizada (2026-06-11)

Comando:

```bash
cd /var/www/sgdl/backend
python manage.py validar_e2e_homologacao --corrigir-vinculo-secretaria --manter-demanda
```

| Passo | Perfil | Resultado | Evidência |
|-------|--------|-----------|-----------|
| 5.2.4–5.2.5 | VEREADOR | **OK** | Envio oficial → `AGUARDANDO_PROTOCOLO`, 1 anexo PDF |
| 5.3.2 | PROTOCOLO | **OK** | Despacho → `PROTOCOLADO` (`2026-0021`) |
| 5.4.5 | SECRETARIA | **OK** | `EM_EXECUCAO` |
| 5.4.7 | SECRETARIA | **OK** | `AGUARDANDO_DEVOLUTIVA_PROTOCOLO` |
| 5.3.5 | PROTOCOLO | **OK** | `DEVOLVIDO_VEREADOR` |
| 5.2.6–5.2.7 | VEREADOR | **OK** | `FINALIZADO` + pacote devolutiva |
| 5.6.1 | GESTOR | **OK** | Dashboard `/api/dashboard/stats/` → 200 |

**Demanda evidência:** id **2966** · tag `3c1817db` · status `FINALIZADO`

**Gate A1 (backend/serviços):** **GO**

**Gate A1 (UI/API assistida — 2026-06-10):** **GO** — sem bloqueantes; ver seção abaixo.

Usuários de teste:

| Perfil | Username | Observação |
|--------|----------|------------|
| Vereador | `vereador_0_martinsnicole` | seed, senha `123` |
| Protocolo | `protocolo_0` | órgão 12 + UA SGAC (U2) |
| Secretaria | `sec_serviços_0` | órgão 17; vínculo setor corrigido na rodada (UA 890) |
| Gestor | `admin` | staff/super |

---

## Observações H2 (achados)

| # | Registro | Severidade |
|---|----------|------------|
| H2-01 | Gestão usuários · SECRETARIA · `sec_serviços_0` com atuação incompleta (sem setor UA) · corrigido via `--corrigir-vinculo-secretaria` · **incômodo** — revisar demais logins secretaria em `/gestao-usuarios` | incômodo |
| H2-02 | validar_e2e_homologacao · VEREADOR · envio exige `sinapse_servico_id` · falha sem `--servico 80` · documentado no comando · **cosmético** | cosmético |
| H2-03 | DemandasView · SECRETARIA · fila `minha_unidade` indisponível sem setor · esperado bloqueio · confirmado regra U3 · **ok** | — |

Itens **bloqueantes:** nenhum na rodada backend.

---

## Execução UI/API assistida (2026-06-10)

Browser MCP indisponível nesta sessão; rodada conduzida via **proxy API** (local `APIClient` + smoke HTTP em produção).

Comando local:

```bash
cd /var/www/sgdl/backend
python manage.py validar_e2e_ui_api --demanda-id 2966
```

| Tela / endpoint | Perfil | Resultado | Evidência |
|-----------------|--------|-----------|-----------|
| `/api/consulta/hub/` | VEREADOR | **OK** | 200 local + prod |
| `/api/demandas/?status=RASCUNHO` | VEREADOR | **OK** | 200 prod |
| `/api/demandas/2966/` | VEREADOR | **OK** | status `FINALIZADO` prod |
| Filas `protocolados` / `operacionais` / `devolutivas` | PROTOCOLO | **OK** | 200 local + prod |
| `/api/clusters/` | PROTOCOLO | **OK** | 200 local + prod |
| `/api/dashboard/stats/` | PROTOCOLO | **OK** | 200 local + prod |
| `/api/tendencias/` | PROTOCOLO | **OK** | 200 local |
| Reconciliação Sinapse | PROTOCOLO | **OK** | 403 (bloqueio esperado) |
| Fila `operacionais` + `minha_unidade=1` | SECRETARIA | **OK** | 200 prod; `atuacao_sgdl.completa=True` |
| `/api/dashboard/stats/` + `/api/reports/kpis/` | GESTOR | **OK** | 200 local (`admin` force_auth) |
| `/api/gestao-usuarios/` + `/api/fluxo-servicos/` | GESTOR | **OK** | 200 local |
| `/api/integrations/sinapse/unmatched/` | GESTOR | **OK** | 200 local |
| `/api/users/me/` + `atuacao_sgdl` | todos | **OK** | prod: órgão › setor preenchido (Protocolo + Secretaria) |

**Produção** (`https://sgdl.mogidascruzes.sp.gov.br`): login SPA 200; JWT seed OK para Vereador, Protocolo e Secretaria (senha `123`). Login `admin` retorna **401** — credencial de gestor em prod difere do seed local; endpoints gestor validados apenas no ambiente local.

**Resumo:** 24 checks locais OK, 0 bloqueantes. 12 checks HTTP prod OK (3 perfis).

---

## Pendente — validação visual pura (browser manual)

Checklist §5.2–5.6 em [homologacao-go-live.md](homologacao-go-live.md) — marcar após rodada no browser:

- [ ] Copiloto → rascunho com serviço + endereço (5.2.1–5.2.3) — *API chat não exercitada nesta rodada*
- [ ] Preview PDF no dialog «Enviar oficialmente» (5.2.3)
- [x] Filas Protocolo: protocolados / operacionais / devolutivas (5.3.1) — *validado via API prod 2026-06-10*
- [ ] Super OS / cluster (5.5.2–5.5.4)
- [ ] Relatórios gestor + exportação (5.6.2) — *KPIs API OK local; UI + login gestor prod pendente*
- [ ] Reconciliação Sinapse UI (5.6.3) — *API OK local; UI prod pendente*

---

## Comandos de repetição

```bash
# Ciclo legislativo completo (serviços)
python manage.py validar_e2e_homologacao --corrigir-vinculo-secretaria --manter-demanda

# Proxy UI/API por perfil (H1 assistido)
python manage.py validar_e2e_ui_api --demanda-id 2966

# Testes automatizados relacionados
DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test \
  core.tests.test_devolutiva_protocolo \
  core.tests.test_encerramento_legislativo \
  core.tests.test_assinatura_eletronica \
  core.tests.test_atraso_demanda_service \
  --keepdb
```

---

**Próximo passo:** rodada visual no browser com operadores — roteiro passo a passo: [roteiro-e2e-browser-operadores.md](roteiro-e2e-browser-operadores.md). Referência de encerramento: demanda **2966**.
