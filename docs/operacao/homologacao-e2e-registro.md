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

## Pendente — validação visual (UI manual)

Checklist §5.2–5.6 em [homologacao-go-live.md](homologacao-go-live.md) — marcar após rodada no browser:

- [ ] Copiloto → rascunho com serviço + endereço (5.2.1–5.2.3)
- [ ] Preview PDF no dialog «Enviar oficialmente» (5.2.3)
- [ ] Filas Protocolo: protocolados / operacionais / devolutivas (5.3.1)
- [ ] Super OS / cluster (5.5.2–5.5.4)
- [ ] Relatórios gestor + exportação (5.6.2)
- [ ] Reconciliação Sinapse UI (5.6.3)

---

## Comandos de repetição

```bash
# Ciclo legislativo completo (serviços)
python manage.py validar_e2e_homologacao --corrigir-vinculo-secretaria --manter-demanda

# Testes automatizados relacionados
DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test \
  core.tests.test_devolutiva_protocolo \
  core.tests.test_encerramento_legislativo \
  core.tests.test_assinatura_eletronica \
  core.tests.test_atraso_demanda_service \
  --keepdb
```

---

**Próximo passo:** rodada visual com operadores (Protocolo + Secretaria) usando demanda 2966 como referência de encerramento bem-sucedido.
