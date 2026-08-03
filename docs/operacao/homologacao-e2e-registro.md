# Registro E2E homologação — Gate A1 (H1/H2)

> **Formato H2:** `tela · perfil · esperado · obtido · severidade`  
> Índice: [homologacao-go-live.md](homologacao-go-live.md) · Roadmap: [ROADMAP.md](../ROADMAP.md)

---

## Validação remota A1–A5 (2026-06-10)

Testes executados por operadores em **homologação** (`https://sgdl.mogidascruzes.sp.gov.br`).

| ID | Entrega | Resultado | Observação |
|----|---------|-----------|------------|
| **A1** | Copiloto calibrado com FAQ | **OK** | Recusas alinhadas ao banco FAQ (energia, água, prisão/furto → orientação, sem tendência indevida) |
| **A2** | Visibilidade Vereador (P8) | **OK** | Timeline sem tramitações operacionais; marcos e conclusão visíveis |
| **A3** | Assinatura chefia UA na conclusão (Secretaria) | **OK** | Diálogo de assinatura na conclusão operacional |
| **A4** | Assinaturas despacho Protocolo (inicial + devolutiva + gestor) | **OK** | Cadeia operador + gestor nos despachos |
| **A5** | RBAC Secretaria (isolamento órgão/UA) | **OK** | Secretaria vê apenas processos do próprio órgão/setor |

**Gate piloto (2ª quinzena jun/2026):** **GO** (condicional — Onda B em andamento)

**Rodada pós-GO (2026-06-13):** 9 novos apontamentos (H2-09…H2-17) — ver [piloto-apontamentos-jun2026.md](piloto-apontamentos-jun2026.md).

**Próximos passos operacionais:**
1. Executar **Onda B** (B1–B9) — prioridade B4, B5, B7, B8
2. Smoke E2E ponta a ponta após entregas P0/P1
3. Treinamento dos 2 gabinetes parceiros + operadores Protocolo/Secretaria
4. Backup pré-piloto (tar + sha256) conforme [homologacao-go-live.md](homologacao-go-live.md)

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

### Rodada H3 — Gestão de usuários U5 (jun/2026)

| # | Registro | Status |
|---|----------|--------|
| **H3-14** | GestaoUsuariosView · senha alterada sem intenção ao editar · checkbox «Alterar senha» + backend | **OK** |
| **H3-15** | GestaoUsuariosView · busca «admin» após editar (autofill) · anti-autofill + restauração | **OK** |
| **U5-UX** | GestaoUsuariosView · vínculos UA invisíveis no form · resumo + MultiSelect com labels | **OK** |
| **H3-16/28** | Gestor **Geral** vs **Setorial** · especificado em [modulo-usuarios-perfis.md §2.4](../especificacoes/modulo-usuarios-perfis.md) · RBAC **U7 pendente** | backlog |

### Rodada pós-GO — 2026-06-13 (Vereador + Protocolo)

Detalhe completo: [piloto-apontamentos-jun2026.md](piloto-apontamentos-jun2026.md)

| # | Registro | Severidade | Backlog |
|---|----------|------------|---------|
| **H2-09** | CopilotoView / DemandaForm · **VEREADOR** · busca identifica logradouros de MC · usuário **não localiza** endereços · **incômodo** | incômodo | **B1** |
| **H2-10** | Preview ofício rascunho · **VEREADOR** · data uma vez no documento · data **repetida** início e fim · **incômodo** | incômodo | **B2** |
| **H2-11** | Upload anexos · **VEREADOR** · restringir mesmo nome · permite duplicata · **incômodo** | incômodo | **B3** |
| **H2-12** | Timeline · **VEREADOR** · marcos com **secretaria/setor** (P8 refinado) · tudo como «Prefeitura» · **incômodo** (refino A2) | incômodo | **B4** |
| **H2-13** | Despacho · **PROTOCOLO** · encaminhar a **N secretarias** simultaneamente · apenas um destino · **melhoria** (aplicar) | melhoria | **B5** |
| **H2-14** | Assinatura despacho · **PROTOCOLO** · exibir **cargo** (chefe seção, auxiliar…) · rótulo genérico gestor · **melhoria** | melhoria | **B6** |
| **H2-15** | Pós-despacho · **PROTOCOLO** · confirmar **despacho assinado** visível · difícil localizar status · **melhoria** | melhoria | **B7** |
| **H2-16** | Despacho/devolutiva · **PROTOCOLO** · **juntar anexos** · sem upload em despachos/respostas · **melhoria** | melhoria | **B8** |
| **H2-17** | Timeline · **PROTOCOLO/SECRETARIA** · textos formatados (parágrafos) · texto corrido · **cosmético** | cosmético | **B9** |

Itens **bloqueantes:** nenhum na rodada backend automatizada (2026-06-11).

---

## Reunião de trabalho — 2026-06-11 (operadores)

**Participação:** operadores (Vereador, Protocolo, Secretaria, Gestão).  
**Acordado:** **+1 semana** de ajustes + **testes remotos** na aplicação antes do piloto (2ª quinzena jun/2026).  
**Briefing:** [reuniao-trabalho-jun2026.md](reuniao-trabalho-jun2026.md)

### Achados H2 (reunião)

| # | Registro | Severidade | Backlog |
|---|----------|------------|---------|
| **H2-04** | CopilotoView · VEREADOR/GESTOR · respostas/orientações alinhadas à **FAQ Copiloto** cadastrada · respostas genéricas ou desalinhadas ao banco FAQ · **incômodo** (qualidade piloto) | incômodo | **A1 — OK (2026-06-10)** |
| **H2-05** | DemandaDetailView / timeline · **VEREADOR** · ver só marcos relevantes e conclusão (regra **P8** documentada) · vereador vê **todo o processo** operacional · **bloqueante** | bloqueante | **A2 — OK (2026-06-10)** |
| **H2-06** | Conclusão do processo · **SECRETARIA** (chefia órgão/setor) · assinatura eletrônica na **conclusão** / encaminhamento devolutiva · hoje só tramitação sem assinatura do responsável · **bloqueante** (piloto) | bloqueante | **A3 — OK (2026-06-10)** |
| **H2-07** | Despacho Protocolo · **PROTOCOLO** · assinatura eletrônica no **despacho inicial** (protocolar) e no **despacho final** (devolutiva ao vereador), com assinatura do **gestor do protocolo** (secretário do órgão) · hoje despacho sem cadeia de assinatura · **bloqueante** (piloto) | bloqueante | **A4 — OK (2026-06-10)** |
| **H2-08** | DemandasView / listagens · **SECRETARIA** · ver **apenas** processos do **próprio órgão/setor** (regra U3/RBAC) · usuários de uma secretaria vendo processos de **todas** as secretarias · **bloqueante** | bloqueante | **A5 — OK (2026-06-10)** |

**Resumo reunião:** 4 **bloqueantes** (H2-05, H2-06, H2-07, H2-08) + 1 **incômodo** (H2-04) — **todos resolvidos e validados em homologação (2026-06-10).**

**Gate piloto (2ª quinzena jun/2026):** **GO**

### Plano de trabalho (semana pós-reunião)

| Prioridade | Item | Ação |
|------------|------|------|
| **P0** | A5 — isolamento Secretaria | **OK (2026-06-10)** |
| **P0** | A2 — visibilidade Vereador | **OK (2026-06-10)** |
| **P1** | A4 — assinatura Protocolo | **OK (2026-06-10)** |
| **P1** | A3 — assinatura chefia setor (Órgão/Secretaria) | **OK (2026-06-10)** |
| **P2** | A1 — Copiloto × FAQ | **OK (2026-06-10)** |
| — | Piloto operacional | Iniciar 2ª quinzena jun/2026 — 2 gabinetes + Protocolo + Gestão |

### Encerramento dev — 2026-06-12

| Entrega | Resultado |
|---------|-----------|
| A5 RBAC Secretaria | Código em dev — pendente smoke com 2 secretarias |
| A2 visibilidade Vereador | Código em dev — pendente smoke demanda real |
| A4 assinaturas Protocolo | UI detalhe + lista; `AssinaturaPendingAcao` (mig. `0063`); fix serializer `assinaturas` |
| **A3 Secretaria** | **[~] Implementado em dev** — diálogo assinatura conclusão + testes API |
| A1 Copiloto × FAQ | Não iniciado |

**Deploy homologação pendente:** `python manage.py migrate core 0063` · `npm run build` · restart Gunicorn.

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

## Rodada pós-deploy jul/2026 (31/jul tarde)

Deploy do pacote `e9638c1` em homologação. Rodadas R1–R5 executadas conforme roteiro sugerido.

**Resultado:** **NO-GO** para piloto contínuo.

**Documento completo:** [rodada-pos-deploy-jul2026.md](rodada-pos-deploy-jul2026.md)

### Resumo por severidade

| Severidade | Qtd | IDs |
|------------|-----|-----|
| **Bloqueante** | 7 | H-JUL-01, H-JUL-02, H-JUL-03, H-JUL-04, H-JUL-05, H-JUL-06, H-JUL-07 |
| **Incômodo** | 10 | H-JUL-08 … H-JUL-14, H-JUL-16, H-JUL-17, H-JUL-18 |
| **Melhoria** | 1 | H-JUL-19 |
| **Esclarecimento** | 1 | H-JUL-20 |

### Correções P0/P1 em dev (2026-08-03)

Pacote **H-JUL-01 … H-JUL-06** — CRUD 60s, desfazer despacho, devolutiva assíncrona, visibilidade gestor setorial, Super OS fila só líder, dedupe despacho inicial na seguidora.

| ID | Entrega | Evidência dev |
|----|---------|---------------|
| H-JUL-01 | CRUD cross-perfil bloqueado | `test_tramitacao_janela_edicao.py` |
| H-JUL-02 | Desfazer despacho inicial | `test_delete_reverte_nos_pernas_e_notificacoes_hjul02` |
| H-JUL-03 | Modal devolutiva operador-only | `test_devolutiva_protocolo`, `modo_assinatura_protocolo` |
| H-JUL-04 | Gestor setorial — queryset com validação pendente | `test_gestor_escopo.py` |
| H-JUL-05 | Fila protocolados só líder Super OS | `test_painel_protocolo.py` |
| H-JUL-06 | Timeline seguidora — 1 despacho inicial | `test_timeline_seguidora_um_despacho_inicial_apos_super_os_hjul06` |

| H-JUL-07 | Filtro autor inclui indicações vinculadas | `IndicacaoVereadorVisibilidadeTests` |
| H-JUL-08/09 | Placeholders resolvidos na publicação; editor Quill sincronizado | `test_despacho_publicado_sem_placeholders_hjul08` |

**Reteste homologação:** RT-SEC + RT-ASS + RT-SOS + RT-IND + RT-PLC em [rodada-pos-deploy-jul2026.md](rodada-pos-deploy-jul2026.md).

### Bloqueantes prioritários restantes (P0)

*Nenhum bloqueante P0 pendente de correção em dev (reteste homologação pendente).*

### Bloqueantes corrigidos em dev (aguardando reteste)

| ID | Registro resumido |
|----|-------------------|
| **H-JUL-01** | Protocolo vê e edita despacho da Secretaria na janela 60s (falha RBAC) |
| **H-JUL-02** | Desfazer despacho inicial não reverte nó; Secretaria notificada e acessa link |
| **H-JUL-03** | Modal devolutiva ainda permitia operador assinar como gestor |
| **H-JUL-04** | Gestor setorial — 404 ao abrir demanda após assinatura operador |
| **H-JUL-05** | Super OS — fila lista todas demandas, não só líder |
| **H-JUL-06** | Super OS — seguidora com despacho inicial duplicado |
| **H-JUL-07** | Indicações — vereador vinculado não vê lista/dashboard/mapa |

### Checklist reteste (marcar após correção)

Ver seções **RT-SEC**, **RT-ASS**, **RT-SOS**, **RT-IND**, **RT-GEO**, **RT-PLC** em [rodada-pos-deploy-jul2026.md](rodada-pos-deploy-jul2026.md).

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

**Próximo passo:** Deploy + reteste RT-SEC … RT-SOS (incl. H-JUL-15–18) após pacote H-JUL-01…18. Gate piloto: **NO-GO** até reteste em homologação.

**Última atualização:** 2026-08-03 — correções H-JUL-01…18 em dev; rodada browser pós-deploy `e9638c1` permanece NO-GO até reteste.
