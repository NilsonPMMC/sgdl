# Roteiro de homologação completo — SGDL (jun/2026)

> **Documento mestre** — use **só este arquivo** para guiar deploy + testes operacionais.  
> Os demais docs são referência técnica ou histórico; este roteiro aponta para eles quando necessário.

**Ambiente:** homologação operacional · **URL:** https://sgdl.mogidascruzes.sp.gov.br  
**Última atualização:** 2026-06-13 (rodada 2 — apontamentos tramitação, cluster, gestor)  
**Escopo:** Gate A1–A5 (base) + Onda B (B1–B9) + O1 Ouvidoria + triagem sinalização

### Legenda de status (homologação)

| Marca | Significado |
|-------|-------------|
| **[X]** | Realizado — critério atendido |
| **[~]** | Realizado com problemas — ver [achados H3](#achados-h3--rodada-pós-roteiro-jun2026) |
| **☐** | Não executado / pendente |

---

## Como usar este roteiro

1. **Antes do deploy** → [Fase 0](#fase-0--pré-deploy-técnico) (15 min, operador técnico).
2. **Depois do deploy** → siga as fases **1 → 4** na ordem (ou use a [ordem mínima](#ordem-mínima-1-dia) se tiver pouco tempo).
3. **Marque pass/fail** na [matriz única](#matriz-única-passfail) e no [registro de execução](#registro-de-execução).
4. **Problemas novos** → registre no formato H2 em [homologacao-e2e-registro.md](homologacao-e2e-registro.md) (ver [§ Registrar achados](#registrar-achados-h2)).

---

## Mapa da documentação (não se perca)

| Documento | Quando abrir |
|-----------|--------------|
| **Este arquivo** | Sempre — roteiro guiado pós-deploy |
| [homologacao-go-live.md](homologacao-go-live.md) | Checklist formal go-live; evidências `check --deploy` / backup |
| [roteiro-e2e-browser-operadores.md](roteiro-e2e-browser-operadores.md) | Fluxo A1 original (Copiloto → Super OS → Secretaria) — detalhe passo a passo |
| [roteiro-b5-b8-homologacao.md](roteiro-b5-b8-homologacao.md) | Detalhe extra só B5/B8 (multi-despacho + anexos) |
| [piloto-apontamentos-jun2026.md](piloto-apontamentos-jun2026.md) | Backlog H2-09…H2-17 e critérios Onda B |
| [homologacao-e2e-registro.md](homologacao-e2e-registro.md) | Onde **anotar bugs** encontrados (H2-XX) |
| [reuniao-trabalho-jun2026.md](reuniao-trabalho-jun2026.md) | Contexto gates A1–A5 |
| [fluxo-auto-manual.md](fluxo-auto-manual.md) | Despacho automático vs manual por serviço |
| [runbook-sync-sinapse.md](runbook-sync-sinapse.md) | Sync catálogo Sinapse (se serviço não aparece) |
| [../ROADMAP_PRODUTO.md](../ROADMAP_PRODUTO.md) | Roadmap produto (O1, fases 2.x) |

---

## Perfis, logins e materiais

### Quem participa

| Perfil | Papel no roteiro |
|--------|------------------|
| **VEREADOR** | Copiloto, envio ofício, pacote devolutiva, encerramento |
| **PROTOCOLO** | Despacho, devolutiva, assinaturas A4, filas |
| **SECRETARIA A / B** | Filas operacionais (teste multi-despacho B5) |
| **GESTOR** | Opcional — KPIs / dashboard |
| **Operador técnico** | Fase 0, evidências, deploy |

### Logins seed (homologação local; produção pode diferir)

| Perfil | Login sugerido | Senha seed |
|--------|----------------|------------|
| Vereador | `vereador_0_martinsnicole` | `123` |
| Protocolo | `protocolo_0` | `123` |
| Secretaria | `sec_serviços_0` | `123` |

\* Em produção/homologação real, use contas configuradas pelo time. O `admin` do seed **não** autentica em prod (401).

### Arquivos de teste

| Arquivo | Uso |
|---------|-----|
| `parecer-teste.pdf` (≤ 5 MB) | Anexo despacho / devolutiva (B8) |
| `foto-local.jpg` (≤ 5 MB) | Anexo devolutiva (B8) |
| Dois arquivos **com o mesmo nome** | Teste B3 (alerta duplicata) |

### Amostra de endereços MC (B1)

Tenha à mão 3–5 logradouros reais de Mogi das Cruzes para autocomplete (ex.: Av. José Benedito Braga; Rua Barão de Jaceguai).

---

## Visão geral das fases

| Fase | Foco | Tempo | IDs cobertos |
|------|------|-------|--------------|
| **0** | Pré-deploy técnico | ~15 min | — |
| **1** | Vereador / Copiloto | ~60 min | B1–B4, B2, B3, **O1**, sinalização |
| **2** | Protocolo — despacho | ~45 min | B5, B7, B8, B6, A4 |
| **3** | Secretaria | ~20 min | B4, B9, B5 (filas) |
| **4** | Devolutiva → encerramento | ~30 min | B8, P8, A5 |
| **5** | Regressão A1 (opcional) | ~45 min | Super OS, filas |

**Total estimado:** 3–4 h em 1 dia, ou 2 sessões de ~2 h.

---

## Fase 0 — Pré-deploy (técnico)

Executar **no servidor** antes ou logo após publicar.

```bash
cd /var/www/sgdl/backend && source ../venv/bin/activate
python manage.py check --deploy
python manage.py test core.tests.test_despacho_destinos \
  core.tests.test_despacho_multi_visibilidade \
  core.tests.test_copiloto_recusa_validacao \
  core.tests.test_fluxo_protocolo \
  core.tests.test_copiloto_sinalizacao core.tests.test_copiloto_ouvidoria \
  core.tests.test_tramitacao_texto core.tests.test_oficio_texto -v1
```

```bash
cd /var/www/sgdl/frontend && npm run build
```

| # | Verificação | Pass |
|---|-------------|------|
| 0.1 | `check --deploy` sem erro crítico | [X] |
| 0.2 | Testes unitários acima OK | [X] |
| 0.3 | `npm run build` OK | [X] |
| 0.4 | Backup restaurável + checksum anotado ([homologacao-go-live.md](homologacao-go-live.md)) | [X] |
| 0.5 | Commit SHA anotado no [registro](#registro-de-execução) | [X] |

---

## Fase 1 — Vereador / Copiloto

**Objetivo:** ingestão inteligente, trilhas A (carta), A′ (Ouvidoria) e qualidade do ofício.

### 1.1 Fluxo básico carta (regressão A1)

1. Login **VEREADOR** → **Copiloto** (`/copiloto`).
2. Pedido com endereço: *«Solicito poda de árvore na Rua Barão de Jaceguai, 100, Centro.»*
3. Confirmar serviço no painel «Serviço na carta» → endereço → **gerar rascunho**.
4. **Demandas** → rascunho → **Enviar Oficialmente** → abrir **preview PDF**.

| Critério | Pass |
|----------|------|
| Rascunho com serviço confirmado | [x] |
| PDF abre sem 401/500 | [x] |

*Detalhe:* [roteiro-e2e-browser-operadores.md](roteiro-e2e-browser-operadores.md) Bloco 1.

---

### 1.2 B1 — Autocomplete logradouro

1. **DemandaForm** (editar rascunho) ou formulário manual.
2. Campo logradouro → digitar trechos de **10 endereços reais MC**.

| Critério | Pass |
|----------|------|
| ≥ 7/10 resolvem na busca | [x] |
| Fallback manual claro se não achar | [x] |

---

### 1.3 B2 — Data no ofício (sem duplicata)

1. Preview PDF do rascunho (passo 1.1).
2. Conferir cabeçalho e corpo.

| Critério | Pass |
|----------|------|
| Data **não** repetida início + fim do texto | [x] |

---

### 1.4 B3 — Anexos mesmo nome

1. Copiloto ou DemandaForm → selecionar **dois arquivos com o mesmo nome**.

| Critério | Pass |
|----------|------|
| UI alerta e ignora duplicata | [x] |

---

### 1.5 Triagem lombada + placa (sinalização vs lombada)

1. Copiloto → mensagem composta:
   > «Solicito instalação de lombada e placa de sinalização de lombada na Av. José Benedito Braga, 401, Vila Mogilar.»
2. Abrir painel **Contexto** → inspecionar `demandas_extraidas` (2 itens).
3. No **2º item** («Placa de sinalização…»), verificar sugestão no painel «Serviço na carta».

| Critério | Pass |
|----------|------|
| 2 demandas separadas | [x] |
| Item 1 → candidatos incluem **132** (Implantação de Lombada) | [x] |
| Item 2 → sugestão **133** (Sinalização), não 132 | [x] |
| Escolha manual ainda exigida (2 itens = normal) | [x] |

---

### 1.6 O1 — Trilha Ouvidoria (A′)

Testar **três** mensagens em sessões Copiloto **distintas**:

| # | Mensagem exemplo | Esperado |
|---|------------------|----------|
| O1a | «Quero registrar um **elogio** ao atendimento da Secretaria de Obras.» | Serviço **#13** Ouvidoria; `trilha_ouvidoria.subtipo` = elogio |
| O1b | «**Reclamação** sobre demora no retorno da ouvidoria.» | Trilha A′; serviço 13 |
| O1c | «**Buraco** na Rua das Flores, Centro.» | Trilha **A** (carta zeladoria), **não** Ouvidoria |

| Critério | Pass |
|----------|------|
| O1a — serviço 13 vinculado / sugerido | [x] |
| O1b — serviço 13 | [x] |
| O1c — **não** força Ouvidoria | [x] |

---

### 1.7 Enviar ofícios para Fase 2

- Envie oficialmente **pelo menos 2 demandas** em `AGUARDANDO_PROTOCOLO`:
  - 1 fluxo normal (1 secretaria).
  - 1 reservada para multi-despacho (Fase 2.2).

| Critério | Pass |
|----------|------|
| Demandas na fila Protocolo «aguardando despacho» | [X] |

---

## Fase 2 — Protocolo (despacho e assinaturas)

**Login:** `protocolo_0` → **Demandas** → abas **Protocolados** / **Devolutivas**.

### 2.1 B7 + B8 + A4 — Despacho 1 secretaria + anexo

1. **Despachar** → MultiSelect com **1 secretaria**.
2. Anexar `parecer-teste.pdf`.
3. Prévia → declarações operador + gestor → **Confirmar despacho**.
4. Detalhe da demanda → timeline + painel **Assinaturas eletrônicas**.

| Critério | Pass |
|----------|------|
| Despacho concluído; protocolo executivo gerado | [X] |
| Anexo visível na tramitação DESPACHO (Protocolo) | [X] |
| Badge / painel «Despacho assinado» (B7) | [X] |
| Cargo do signatário visível (B6) | [X] |

*Detalhe:* [roteiro-b5-b8-homologacao.md](roteiro-b5-b8-homologacao.md) Cenário 1.

> **[~] H3-01 — Fluxo automático (decisão jun/2026):** despacho AUTO registra assinatura **Sistema SGDL** (`DESPACHO AUTOMATICO DO SISTEMA`), sem gestor — ver [fluxo-auto-manual.md](fluxo-auto-manual.md) § Assinatura AUTO. Manual continua Protocolo + Gestor (A4).

---

### 2.2 B5 — Despacho multi-secretaria

1. Segunda demanda aguardando protocolo.
2. **Despachar** → selecionar **2 secretarias** (ex.: Mobilidade + Zeladoria).
3. Mensagem info «Despacho para 2 secretarias…» → assinatura dupla.
4. Anotar protocolos: principal + desdobramento (toast menciona extras).

| Critério | Pass |
|----------|------|
| 2 protocolos executivos distintos | [~] |
| Toast cita desdobramentos | [X] |

> **[~] H3-02 (corrigido em dev — revalidar):** clone multi-secretaria era ocultado pelo filtro Super OS (`filtrar_listagem_apenas_lideres`). Fix em `cluster_service.py`: clusters com **órgãos distintos** não aplicam regra de «apenas líder». Teste: `core.tests.test_despacho_multi_visibilidade`. Reexecutar 2.2 + 3.1 após deploy.

Depois: Fase 3.1 confirma filas isoladas.

*Detalhe:* [roteiro-b5-b8-homologacao.md](roteiro-b5-b8-homologacao.md) Cenário 2.

---

### 2.3 B3 — Anexo duplicado no despacho

1. No diálogo despacho, tentar anexar 2× o **mesmo nome**.

| Critério | Pass |
|----------|------|
| Alerta; duplicata ignorada | [X] |

---

## Fase 3 — Secretaria

**Login:** secretarias dos destinos do passo 2.2.

### 3.1 B5 — Filas isoladas

| # | Ação | Pass |
|---|------|------|
| 3.1a | Secretaria A → aba **Operacionais** | Vê só processo da A [~] |
| 3.1b | Secretaria B → aba **Operacionais** | Vê só processo da B [~] |

> **[~] H3-02** (revalidação pós-deploy): secretaria B deve abrir detalhe do clone (`GET /api/demandas/{id}/` → 200).

> **H3-03 / H3-13 / H3-17 — Formulário padrão de tramitação (evolução):** unificar Despacho (Protocolo) e Andamentos em um **formulário padrão** com: (1) MultiSelect **órgão(s)** → filtra MultiSelect **unidade(s) administrativa(s)** com busca; (2) checkbox **assinar eletronicamente** (opcional, exceto regras obrigatórias — ver [H3-18](#regras-de-assinatura-por-tipo-de-tramitação-h3-18)); (3) anexos; (4) descrição. Ver matriz [H3-17](#achados-h3--rodada-2-jun2026).

### 3.2 B4 + B9 — Timeline secretaria

1. Abrir detalhe de demanda em execução.
2. Registrar andamento com texto **multilinha** (Enter entre parágrafos).

| Critério | Pass |
|----------|------|
| Timeline legível (quebras de linha) — B9 | [X] |
| Setor/unidade visível onde aplicável | [X] |

### 3.3 Conclusão → devolutiva (preparar Fase 4)

1. Secretaria → **Conclusão** assinada + solicitar devolutiva ao Protocolo.
2. Demanda deve ir para fila **Devolutivas** do Protocolo.

| Critério | Pass |
|----------|------|
| Status `AGUARDANDO_DEVOLUTIVA_PROTOCOLO` | [X] |

> **H3-25 (evolução — simplificar fluxo):** eliminar tramitação intermediária «Solicitação Devolutiva»; após **Conclusão do Serviço**, aguardar apenas o despacho final **Devolutiva ao vereador** pelo Protocolo. **Não conflita** com H3-02/H3-05 — altera UX do passo 3.3, não visibilidade multi-destino.

*Referência:* [roteiro-e2e-browser-operadores.md](roteiro-e2e-browser-operadores.md) Bloco 3.

---

## Fase 4 — Devolutiva e encerramento (Vereador)

### 4.1 B8 — Devolutiva com anexo

**Login:** PROTOCOLO → fila **Devolutivas**.

1. **Despachar devolutiva** → texto ≥ 10 caracteres.
2. Anexar `foto-local.jpg` → assinatura dupla → enviar.

**Login:** VEREADOR (autor) → abrir demanda.

| Critério | Pass |
|----------|------|
| Pacote devolutiva visível | [X] |
| Seção **Anexos do Protocolo** com link da foto | [X] |
| Timeline vereador **não** expõe trânsito interno (P8) | [X] |
| Marcos institucionais com secretaria/setor (B4) | [~] |

#### O que significa «Marcos institucionais com secretaria/setor (B4)»?

Critério **B4** (Onda B, apontamento H2-12): na **timeline do vereador**, o sistema **oculta** trânsito operacional interno (**P8** — comentários, execução, transferências), mas os **marcos que o vereador pode ver** (ex.: «Secretaria X concluiu», «Protocolo despachou devolutiva») devem **nomear órgão e setor**, não só «Prefeitura» genérico.

**Como validar:** login VEREADOR → demanda com devolutiva → timeline: marcos visíveis citam secretaria/setor responsável.

**Resultado desta rodada:** vereador confirmou P8 OK; **rótulos com órgão/setor nos marcos visíveis não ficaram claros** — manter [~] até nova amostra ou ajuste de copy na timeline.

> **H3-04 — Devolutiva:** incluir **Multiselect Órgãos e Setores (cópia)** — encaminhar devolutiva com conhecimento a outros órgãos/setores além do fluxo principal.

> **H3-05 — Anexos da conclusão:** opção de **replicar anexos da tramitação «Conclusão do Serviço»** no pacote devolutiva ao vereador (hoje só anexos do despacho devolutiva do Protocolo — B8 parcial).

*Detalhe:* [roteiro-b5-b8-homologacao.md](roteiro-b5-b8-homologacao.md) Cenário 3.

---

### 4.2 Encerramento legislativo (A5)

1. Vereador → redigir resposta ao cidadão → confirmar ciência.
2. Gerar / baixar PDF resposta.

| Critério | Pass |
|----------|------|
| Status `FINALIZADO` | [X] |
| PDF resposta OK | [~] |

> **[~] H3-06 — Layout ofício resposta:** PDF «resposta ao cidadão» ainda usa **layout da Câmara**; deve usar **layout da Prefeitura** (nova gestão de template — distinto de `ConfiguracaoOficio` legislativo).

> **H3-07 — Encerramento sem vereador:** não depender do vereador para `FINALIZADO`; após devolutiva, **aguardar prazo** (configurável); se não houver ciência, **encerrar automaticamente** (job/cron + trilha de auditoria).

> **H3-08 — Pesquisa de satisfação:** **aprovada pelo produto** — programar dev (5 estrelas + texto aberto no encerramento vereador; dados para gestão operacional/NPS).

---

## Especificação — formulário padrão de tramitação (H3-17)

Backlog transversal para **Despacho (Protocolo)** e **Andamentos (Secretaria/Gestor)**. Consolida H3-03, H3-13 e parte de H3-09/H3-12.

| Campo | Comportamento |
|-------|---------------|
| **Órgão(s)** | MultiSelect com busca; filtra unidades abaixo |
| **Unidade(s) adm.** | MultiSelect com busca; dependente do(s) órgão(s) |
| **Assinar eletronicamente** | Checkbox; opcional salvo [regras obrigatórias](#regras-de-assinatura-por-tipo-de-tramitação-h3-18) |
| **Anexos** | Já existente (B3/B8) |
| **Descrição** | Já existente (B9 multilinha) |

**Perfis:** Protocolo, Secretaria, Gestor (mesmo componente, regras de assinatura variam por tipo).

---

## Regras de assinatura por tipo de tramitação (H3-18)

Decisão de produto registrada na rodada 2. **Relaciona-se a H3-01** (fluxo auto) e **H3-09** (assinatura opcional) — não substitui, **especifica** o matriz obrigatório/opcional.

| Tipo | Assinaturas obrigatórias | Opcional (checkbox) |
|------|--------------------------|---------------------|
| **Despacho inicial** (Protocolo) | Usuário **Protocolo** | — |
| **Andamentos** (comentário, análise técnica, execução) | — | Destinatário (solicitar ou não) |
| **Conclusão do serviço** (setor) | **Secretaria** + **Gestor** | — |
| **Devolutiva ao vereador** (Protocolo) | **Protocolo** + **Gestor** | — |

> **H3-01 — pendência P0:** ~~decidir~~ **decidido (jun/2026)** — fluxo AUTO usa assinatura sistema; manual usa Protocolo + Gestor. Revalidar em homologação serviço AUTO.

---

## Achados H3 — rodada 2 (jun/2026)

Apontamentos da **segunda rodada** de testes. Ver [§ Compatibilidade com H3 existentes](#compatibilidade-novos-apontamentos--h3-existentes).

### Copiloto e ofícios (Vereador)

| ID | Achado | Severidade | Relação H3 |
|----|--------|------------|------------|
| **H3-19** | Timeline vereador: **todos os passos**, porém **sem detalhes** internos — exceto **Conclusão do Serviço** e **Devolutiva ao vereador** (refina P8/B4) | melhoria | complementa B4, não altera P8 |
| **H3-20** | Copiloto «Não» em «Gerar ofícios em rascunho» — **fix dev** (`test_copiloto_recusa_validacao`) | incômodo | revalidar |
| **H3-21** | **Editar rascunho do ofício** — bloquear anexos com **mesmo nome** (B3 vale Copiloto/DemandaForm; falta tela de edição de ofício) | incômodo | estende B3 |

### Cluster / Super OS

| ID | Achado | Severidade | Relação H3 |
|----|--------|------------|------------|
| **H3-22** | Quando processo novo **entra em Cluster**, registrar **Despacho Automático** pelo sistema (tramitação auditável; Protocolo não fica pendente manual) | melhoria | complementa H3-01 (auto) |
| **H3-23** | Secretaria em **Super OS**: modal com **texto formatado** dos ofícios vinculados ao **líder** + opção **Descompressão** | melhoria | independente de H3-02 |
| **H3-24** | **Descompressão**: tramitação ao Protocolo solicitando **processo novo** desclusterizado (sair do agrupamento) | melhoria | par H3-23 |

### Devolutiva e encerramento

| ID | Achado | Severidade | Relação H3 |
|----|--------|------------|------------|
| **H3-25** | Remover «Solicitação Devolutiva» — fluxo **Conclusão → Devolutiva ao vereador** direto | melhoria | simplifica 3.3; não conflita H3-02 |
| **H3-26** | Devolutiva em **Super OS**: opção enviar a **todos** os vereadores do cluster ou **selecionar** destinatários | melhoria | complementa H3-04 |
| **H3-27** | Devolutiva: opção **cópia/notificação ao Gestor** | melhoria | complementa H3-04, H3-16 |

### Tramitação unificada e gestão

| ID | Achado | Severidade | Relação H3 |
|----|--------|------------|------------|
| **H3-17** | **Formulário padrão** tramitação (órgão→UA search, assinatura opcional, anexos, descrição) | melhoria | **consolida** H3-03, H3-13 |
| **H3-18** | **Matriz de assinaturas** por tipo (ver tabela acima) | decisão produto | **especifica** H3-01, H3-09, A4 |
| **H3-28** | **Gestor Geral** (sem vínculo org/setor — dados e CRUD admin plenos) vs **Gestor Setorial** (vinculado a 1+ órgãos/setores — dados e tramitações no escopo) | melhoria | **estende** H3-16 · spec [modulo-usuarios-perfis.md §2.4](../especificacoes/modulo-usuarios-perfis.md) |

---

## Compatibilidade — novos apontamentos × H3 existentes

| H3 anterior | Impacto dos novos apontamentos |
|-------------|-------------------------------|
| **H3-01** fluxo auto | H3-18 **define** matriz de assinatura; H3-22 propõe registro automático em cluster — **decidir junto**, não conflitam |
| **H3-02** multi-destino | **Sem interferência** — visibilidade clone já corrigida; H3-25/26/27 tratam devolutiva, não escopo |
| **H3-03 / H3-13** multiselect | **Absorvidos** por H3-17 (formulário padrão) — manter IDs por rastreio |
| **H3-04** devolutiva cópia | H3-26/27 **complementam** (Super OS + Gestor) |
| **H3-05** anexos conclusão | **Sem interferência** |
| **H3-06–08** encerramento | H3-08 **promovido** a aprovado; H3-19 refina timeline vereador em paralelo |
| **H3-09** assinatura opcional | **Especificado** em H3-18 (andamentos) |
| **H3-10/11** catálogo | **Sem interferência** |
| **H3-12** assinaturas inline | Complementar a H3-17/H3-18 |
| **H3-14–16** usuários | H3-14/15/U5-UX **homologados**; H3-28 **estende** H3-16 (Gestor Geral vs Setorial) |

**Conclusão:** nenhum apontamento da rodada 2 **invalida** H3-02 nem bloqueia revalidação B5. H3-01 e H3-18 devem ser **decididos em conjunto** na Onda C.

---

## Achados H3 — rodada pós-roteiro (jun/2026)

Consolidado após execução do roteiro completo. Registrar cópias formais em [homologacao-e2e-registro.md](homologacao-e2e-registro.md) quando virarem tickets.

### Protocolo e tramitação

| ID | Fase | Achado | Severidade | Backlog |
|----|------|--------|------------|---------|
| **H3-01** | 2 | Fluxo auto: assinatura **Sistema SGDL** (não operador humano) — **decidido + implementado** | incômodo | revalidar AUTO |
| **H3-02** | 2–3 | Multi-destino: secretaria B **não abria** clone — **fix dev** (cluster multi-órgão ≠ Super OS) | ~~bloqueante~~ **revalidar** | B5.1 visibilidade |
| **H3-03** | 2–4 | Multiselect órgãos + setores — ver **H3-17** (formulário padrão) | melhoria | Onda C/D |
| **H3-04** | 4 | Devolutiva: multiselect órgãos/setores cópia — ver também **H3-26/27** | melhoria | Onda C/D |
| **H3-05** | 4 | Incluir anexos da **Conclusão do Serviço** no pacote devolutiva | melhoria | B8+ |
| **H3-09** | 2–3 | Assinatura opcional — matriz em **H3-18** | melhoria | Onda C/D |

### Encerramento e ofícios

| ID | Achado | Severidade |
|----|--------|------------|
| **H3-06** | Ofício **resposta ao cidadão** — layout **Prefeitura**, não Câmara | incômodo |
| **H3-07** | `FINALIZADO` automático após prazo sem ciência do vereador | melhoria |
| **H3-08** | Pesquisa satisfação (5★ + texto) no encerramento vereador — **aprovada, programar dev** | melhoria |

### Catálogo Sinapse / Ouvidoria (O1)

| ID | Achado | Severidade |
|----|--------|------------|
| **H3-10** | Serviço **#13** (Ouvidoria) vinculado ao órgão **#14** (Ouvidoria Geral); na reforma admin., Ouvidoria passa ao **GABP (Prefeita #49)** — não é mais órgão autônomo | incômodo |
| **H3-11** | Tudo classificado como **GABP** hoje mapeia para «Secretaria de Governo e Transparência» **#12** — divergência estrutural RM / Sinapse | incômodo |

**Ação sugerida:** revisar mapeamento órgãos Sinapse ↔ UA ↔ SGDL; atualizar `COPILOTO_OUVIDORIA_SINAPSE_SERVICO_ID` e destino de despacho após sync; documentar em [rm271698-ids-duplicados-conferencia.md](rm271698-ids-duplicados-conferencia.md).

### Frontend (UX)

| ID | Achado |
|----|--------|
| **H3-12** | Exibir **assinaturas eletrônicas dentro de cada passo** (envio, despacho, devolutiva), não só painel separado |
| **H3-13** | Form Andamento/Despacho — ver **H3-17** (órgãos + UA com search) |

### Gestão de usuários — **homologado jun/2026**

| ID | Achado | Severidade | Status |
|----|--------|------------|--------|
| **H3-14** | Alteração de **senha sem intenção** ao editar usuário | incômodo | **OK** — checkbox «Alterar senha» |
| **H3-15** | Após editar, filtro buscava **«admin»** (autofill) | cosmético | **OK** — anti-autofill + restauração |
| **U5-UX** | Vínculos UA não visíveis no formulário de edição | incômodo | **OK** — resumo + chips no MultiSelect |
| **H3-16** | Perfil **Gestor**: subtipos **Geral** vs **Setorial** | melhoria | **Especificado** — ver H3-28 / U7 (dev pendente) |

**Roteiro rápido U5 (regressão):**

1. `/gestao-usuarios` → editar secretaria **sem** marcar «Alterar senha» → login anterior válido.
2. Editar qualquer usuário → campo busca **não** preenchido com «admin» involuntariamente.
3. Editar secretaria com setor vinculado → bloco «Atuação vinculada hoje» + chips com sigla/nome.

### Gestor Geral vs Setorial — **revalidar após U7**

| Cenário | Pass esperado |
|---------|---------------|
| Gestor **Geral** (`admin`, sem órgão/setor) | Todas demandas; `/admin/`; CRUD usuários/carta |
| Gestor **Setorial** (ex.: Mobilidade + setores) | Só demandas do escopo; tramitações OK no escopo; sem admin global |
| Cadastro U5 gestor setorial | Órgão e/ou setor obrigatórios; rótulo «Setorial» na lista |

---

## Fase 5 — Regressão A1 (opcional)

Se ainda não validou recentemente:

| Bloco | Conteúdo | Doc |
|-------|----------|-----|
| Super OS | 2 demandas mesmo serviço → despacho cluster | [roteiro-e2e-browser-operadores.md](roteiro-e2e-browser-operadores.md) §2 |
| Filas Protocolo | 3 abas renderizam | idem §2.1 |
| Validar assinatura | URL pública `/validar-assinatura/:codigo` | [homologacao-go-live.md](homologacao-go-live.md) |

---

## Ordem mínima (1 dia)

Se tiver **~2 h**, priorize nesta sequência:

1. **Fase 0** (técnico)  
2. **1.5** sinalização + **1.6** O1 (Copiloto)  
3. **2.1** despacho + anexo (B7/B8/A4)  
4. **2.2** multi-secretaria (B5) + **3.1** filas  
5. **4.1** devolutiva com anexo  

Deixe B1 (10 endereços), Super OS e encerramento completo para segunda sessão.

---

## Matriz única pass/fail

| ID | O quê | Fase | Pass |
|----|-------|------|------|
| **A4** | Dupla assinatura despacho/devolutiva | 2.1, 4.1 | [X] — ver H3-01 fluxo auto |
| **A5** | Encerramento + PDF cidadão | 4.2 | [~] — H3-06 layout Prefeitura |
| **B1** | Autocomplete logradouros MC | 1.2 | [X] |
| **B2** | PDF sem data duplicada | 1.3 | [X] |
| **B3** | Anexos mesmo nome bloqueados | 1.4, 2.3 | [X] |
| **B4** | Timeline vereador: marcos com órgão/setor (P8) | 4.1 | [~] — ver explicação §4.1 |
| **B5** | Multi-despacho; filas isoladas | 2.2, 3.1 | [~] — H3-02 bloqueante |
| **B6** | Cargo na assinatura | 2.1 | [X] |
| **B7** | Painel «despacho assinado» | 2.1 | [X] |
| **B8** | Anexos despacho + pacote devolutiva | 2.1, 4.1 | [X] — H3-05 evolução |
| **B9** | Texto multilinha na timeline | 3.2 | [X] |
| **O1** | Ouvidoria (#13) vs carta operacional | 1.6 | [X] — H3-10/H3-11 catálogo |
| **SIN** | Placa → serviço 133 (não 132) | 1.5 | [X] |

**Homologação geral:** ☑ **Aprovada com ressalvas** — B5 visibilidade multi-destino (H3-02) e pendências H3-01, H3-06 antes de piloto ampliado.

---

## Registro de execução

| Campo | Valor |
|-------|-------|
| Data | 2026-06-10 (rodada operadores) |
| Executor(es) | Equipe piloto / operadores |
| Commit / tag deploy | _(anotar SHA do deploy testado)_ |
| URL ambiente | https://sgdl.mogidascruzes.sp.gov.br |
| Fase 0 | [X] OK |
| Fase 1 | [X] OK (Copiloto, B1–B3, O1, sinalização) |
| Fase 2 | [~] OK com H3-01 (fluxo auto sem assinatura) |
| Fase 3 | [~] H3-02 demanda 2987 inacessível à secretaria B |
| Fase 4 | [~] H3-04–08 anotados; B4 marco não validado claramente |
| Fase 5 | ☐ N/A (não executada nesta rodada) |
| Rodada 2 (2026-06-13) | Apontamentos H3-17…H3-28 registrados — ver § rodada 2 |
| Matriz única | **11 [X] · 3 [~]** de 14 itens |

**Demanda de referência multi-destino:** `#2987` (clone inacessível à secretaria adicionada).

---

## Registrar achados (H2)

Formato (copiar para [homologacao-e2e-registro.md](homologacao-e2e-registro.md)):

```
tela · perfil · esperado · obtido · severidade
```

Severidades: **bloqueante** | **incômodo** | **melhoria** | **cosmético**

Exemplo:

```
DemandasView despacho multi · PROTOCOLO · 2 protocolos gerados · só 1 criado · bloqueante
```

Backlog Onda B: [piloto-apontamentos-jun2026.md](piloto-apontamentos-jun2026.md)

---

## Limitações conhecidas (jun/2026)

- Multi-despacho: sufixo `-D2`, `-D3` no `protocolo_legislativo`; máx. **5** secretarias.
- Anexos multi-despacho são **copiados** em cada tramitação.
- Vereador **não** vê anexos do despacho inicial (P8); vê na **devolutiva**.
- O1: serviço Sinapse **#13**; subtipos por heurística + campos Groq — **catálogo órgão desatualizado** (H3-10, H3-11).
- Pedido composto (lombada + placa): escolha manual por item continua obrigatória.
- **Fluxo auto:** despacho pode ocorrer **sem** assinatura A4 do Protocolo (H3-01 — confirmar regra).
- **Multi-destino:** fix H3-02 em dev — clones multi-órgão não sofrem filtro Super OS; **revalidar** em homologação (2.2 + 3.1).
- Encerramento depende do vereador hoje; auto-finalização e layout Prefeitura na resposta são **backlog** (H3-06, H3-07).
- **Rodada 2 (jun/2026):** formulário padrão tramitação (H3-17), matriz assinaturas (H3-18), cluster/descompressão (H3-22–24), fluxo devolutiva simplificado (H3-25) — ver [§ Achados H3 rodada 2](#achados-h3--rodada-2-jun2026).

### Próxima Onda C / D (priorização sugerida pós-H3 rodada 2)

#### Onda C — estabilização e decisões (antes de piloto ampliado)

| P | Item | Notas |
|---|------|-------|
| **P0** | H3-02 revalidar multi-destino | Fix em dev; reteste 2.2 + 3.1 |
| **P0** | ~~H3-01~~ decisão fluxo auto — **implementado** (assinatura sistema); revalidar |
| **P0** | ~~H3-20~~ Copiloto «Não» — **fix dev**; revalidar |
| **P1** | **H3-17** | Formulário padrão tramitação (órgão→UA + assinatura opcional) |
| **P1** | **H3-25** | Simplificar Conclusão → Devolutiva (sem solicitação intermediária) |
| **P1** | H3-10/H3-11 | Sync catálogo GABP / Ouvidoria |
| **P1** | **H3-28** + H3-16 | Gestor **Geral** vs **Setorial** (U7) |

#### Onda D — cluster, devolutiva avançada, encerramento

| P | Item | Notas |
|---|------|-------|
| **P1** | **H3-22** | Despacho Automático ao entrar em cluster |
| **P2** | **H3-23/24** | Super OS: modal ofícios líder + Descompressão |
| **P2** | **H3-26/27** + H3-04 | Devolutiva Super OS (todos/selecionar) + cópia Gestor |
| **P2** | H3-05 | Anexos da Conclusão no pacote devolutiva |
| **P2** | H3-06 | Template resposta Prefeitura |
| **P2** | H3-12 | Assinaturas inline na timeline |
| **P3** | **H3-19** | Timeline vereador: passos sem detalhe (exceto conclusão/devolutiva) |
| **P3** | **H3-21** | Anexo duplicado em «Editar rascunho do ofício» |
| **P3** | **H3-08** | Pesquisa satisfação (aprovada) |
| **P3** | H3-07 | Auto-finalização após prazo |

---

## Referência rápida — trilhas Copiloto

| Trilha | Quando | Destino |
|--------|--------|---------|
| **A — Carta** | Zeladoria, obras, mobilidade… | Serviço Sinapse escolhido |
| **A′ — Ouvidoria** | Elogio, denúncia, reclamação institucional, sugestão | Serviço **#13** |
| **B — Tendência** | Municipal, fora da carta | Gestão Protocolo |
| **Recusa** | Fora competência municipal | FAQ, sem ofício |

Ver [ROADMAP_PRODUTO.md](../ROADMAP_PRODUTO.md) § Motor de decisão.
