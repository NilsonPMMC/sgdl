# Onda 2 — Polimento UX e regras operacionais

> **Documento de especificação** incorporado em jun/2026.  
> Índice: [README.md](../README.md) · Prioridades: [ROADMAP_PRODUTO.md](../ROADMAP_PRODUTO.md) · Resumo: [ROADMAP.md](../ROADMAP.md)

Este arquivo detalha requisitos de produto para a **Onda 2** (pós-homologação estável da Onda 1). Cada item traz estado atual, comportamento desejado, arquivos impactados e critérios de aceite.

---

## Resumo das entregas

| # | Entrega | Área | Status |
|---|---------|------|--------|
| **P1** | Pré-visualização PDF antes do envio | Ofício | **Concluído** |
| **P2** | Revisão de texto pelo assessor | Ofício / Governança | **Removido** (jun/2026) — rascunho pós-Copiloto |
| **P3** | Documentação AUTO/MANUAL + `SINAPSE_AUTOFILL_THRESHOLD` | Operação / Protocolo | **Concluído** |
| **P6** | Painel de formatação de ofício (frontend → layout PDF) | Ofício / PDF | **Concluído** |
| **P7** | Numeração: ofício por vereador + protocolo global | Backend / modelo | **Concluído** |
| **P8** | Tramitações: vereador vê só conclusão (ocultar gestão operacional) | Timeline / API | **Concluído** |
| **P9** | Dashboard secretaria: remover gráfico «Demandas por Secretaria» | Dashboard | **Concluído** |
| **P10** | Botão «Voltar» em «Editar rascunho do ofício» | DemandaForm | **Concluído** |
| **P11** | Descrição estruturada no detalhe (protocolo, secretaria, admin) | DemandaDetail | **Concluído** |
| **P12** | Botão «Enviar/Despachar» no detalhe da demanda (protocolo) | DemandaDetail | **Concluído** |
| **P13** | Tabelas responsivas com scroll horizontal | Frontend global | **Concluído** |
| **P14** | Acesso: carta para secretaria; remover fluxo/reconciliação/FAQ do protocolo | — | **Concluído** |
| **P4** | KPIs de trilha no dashboard Protocolo/Gestor (Carta / Tendência / Recusa) | Dashboard | **Concluído** |
| **P5** | Assinatura eletrônica em lote (N rascunhos) | Ofício / Copiloto | **Concluído** |

**Onda 2 encerrada (jun/2026)** — todos os itens P1–P14 concluídos. Próximo pacote: [Onda 3](carta-consulta-evolucao.md).

---

## P2 — Revisão pelo assessor (removido jun/2026)

> **Decisão de produto:** a etapa formal de revisão pelo assessor foi retirada do fluxo.  
> O status **`RASCUNHO`** após o Copiloto é a janela natural para revisar dados e enviar oficialmente.

Fluxo atual:

```
Copiloto → RASCUNHO → editar rascunho → preview PDF → assinar → AGUARDANDO_PROTOCOLO
```

Código removido: `RevisaoAssessorService`, `/revisao-assessor`, campos `revisao_assessor_*` (migração `0056`).

---

## P3 — Documentação AUTO/MANUAL e triagem Sinapse

### Objetivo

Documentar de forma operacional as regras de **despacho automático por serviço**, a **confirmação humana no Copiloto** e o papel de **`SINAPSE_AUTOFILL_THRESHOLD`**, evitando confusão com «AUTO» da reconciliação Sinapse.

### Entregáveis

| Documento | Conteúdo |
|-----------|----------|
| [operacao/fluxo-auto-manual.md](../operacao/fluxo-auto-manual.md) | Guia completo: fluxo Protocolo, Copiloto, autofill, matriz de decisão |
| [apis/fluxo-protocolo.md](../apis/fluxo-protocolo.md) | Contrato REST `/api/fluxo-servicos/` |

### Critérios de aceite

- [x] Gestor e Protocolo distinguem fluxo AUTO (despacho) de sync AUTO (reconciliação).
- [x] Limiares Copiloto e `SINAPSE_AUTOFILL_THRESHOLD` documentados com defaults e escopo.
- [x] Exclusões (tendência, sem embedding, sem órgão) descritas.

---

## P4 — KPIs de trilha no dashboard (Protocolo / Gestor)

### Objetivo

Exibir no dashboard volumes do **motor de ingresso**: demandas formalizadas por trilha **Carta** vs **Tendência**, mais **recusas** registradas no Copiloto (itens `fora_competencia` / `descartada` em `ChatSession.demandas_rascunho`), com amostra dos motivos mais frequentes.

### Implementação

| Camada | Arquivo / endpoint |
|--------|-------------------|
| Serviço | `backend/core/services/dashboard_trilha_service.py` — `DashboardTrilhaService.calcular()` e `mensal_por_trilha()` |
| API | `GET /api/dashboard/stats/` — chaves `trilhas` e `trilhas_mensal` (apenas perfis **GESTOR** e **PROTOCOLO**) |
| Filtro listagem | `origem_vinculo` em `DemandaFilter` + query `?origem_vinculo=CARTA|TENDENCIA` na listagem |
| Frontend | `DashboardView.vue` — cards, gráfico doughnut, série mensal carta×tendência, lista de motivos de recusa |
| Testes | `backend/core/tests/test_dashboard_trilhas.py` |

### Critérios de aceite

- [x] Gestor e Protocolo veem totais Carta, Tendência e Recusa (Copiloto) no dashboard.
- [x] Percentuais sobre demandas formalizadas e sobre o motor de ingresso.
- [x] Amostra top 8 de `motivo_recusa` agregada.
- [x] Atalhos para listagem filtrada por trilha (`origem_vinculo`).

---

## P5 — Assinatura eletrônica em lote

### Objetivo

Permitir que o vereador (ou gestor) **assine e envie N rascunhos** numa única declaração, após materialização no Copiloto — evitando repetir o fluxo unitário ofício a ofício.

### Implementação

| Camada | Detalhe |
|--------|---------|
| Serviço | `backend/core/services/envio_oficial_service.py` — `preparar_preview_lote()`, `enviar_lote()` |
| API | `POST /api/demandas/preview-envio-lote/` · `POST /api/demandas/enviar-lote/` |
| Frontend | `DemandasView.vue` — seleção múltipla em rascunhos + dialog; `CopilotoView.vue` — atalho «Assinar e enviar todos» |
| Assinatura | Um registro `AssinaturaEletronica` + PDF por demanda; transação atômica (tudo ou nada) |

### Critérios de aceite

- [x] Preview com hash por ofício antes do envio.
- [x] Declaração única `ASSINO E ENVIO` para todo o lote.
- [x] Cada demanda vai a `AGUARDANDO_PROTOCOLO` com protocolo legislativo próprio.
- [x] Limite de 50 ofícios por requisição.

---

## P6 — Painel de formatação de ofício

### Objetivo

Disponibilizar no **frontend** um painel de configuração visual/institucional do ofício, cujas alterações **refletem diretamente** no layout do PDF gerado (preview, assinatura e anexo final).

### Estado atual

| Aspecto | Implementação |
|---------|---------------|
| Configuração | Singleton `ConfiguracaoOficio`; API `GET`/`PATCH` + painel **GESTOR** (`ConfiguracaoOficioView.vue`); Admin mantido como fallback |
| PDF | Templates WeasyPrint em `backend/core/templates/oficio/`; contexto montado por `OficioService` (`backend/core/services/oficio_service.py`) |
| Campos | Brasão/arte de cabeçalho, formato/orientação de página, margens (cm), destinatário padrão (Prefeitura) |
| Frontend | Tela `/admin/configuracao-oficio` (Tailwind) — modelo **Câmara Municipal**; corpo e assinatura vêm da demanda/vereador |

### Comportamento desejado

1. Nova tela ou seção administrativa (perfis **GESTOR** e, conforme política, **PROTOCOLO** ou assessor) para editar parâmetros de `ConfiguracaoOficio`.
2. Campos do painel mapeiam 1:1 para o contexto do template PDF (cabeçalho, destinatário, rodapé, textos padrão).
3. **Pré-visualização em tempo real** (opcional na v1): botão «Ver amostra PDF» com dados fictícios ou demanda de teste.
4. Alterações persistidas via API REST (`GET`/`PATCH` configuracao-oficio) com auditoria (`atualizado_em`, usuário).
5. PDF de envio oficial, preview e resposta ao cidadão usam a mesma configuração.

### Escopo técnico sugerido

| Camada | Ação |
|--------|------|
| Backend | `ConfiguracaoOficioSerializer` + `ConfiguracaoOficioViewSet` (somente leitura para não-gestor) |
| Frontend | `ConfiguracaoOficioView.vue` ou aba em gestão; formulário + preview PDF |
| Templates | Manter `demanda_oficio.html`; garantir que todos os campos do painel existam no contexto |
| Permissão | `GESTOR` (mínimo); avaliar assessor legislativo como perfil futuro |

### Critérios de aceite

- [x] Gestor altera destinatário no painel → próximo PDF de preview reflete o novo nome.
- [x] Vereador não acessa o painel (403 ou menu oculto).
- [x] `manage.py test` cobre leitura/escrita da API de configuração (`test_configuracao_oficio.py`).
- [x] Documentado em `docs/apis/` quando a API existir → [apis/fluxo-protocolo.md](../apis/fluxo-protocolo.md) (fluxo serviços); config ofício pendente doc API dedicada.

### Riscos

- Conflito com edição simultânea no Django Admin → descontinuar Admin ou sincronizar única fonte (frontend).
- WeasyPrint exige CSS estável; mudanças de layout precisam de snapshot visual na homologação.

---

## P7 — Numeração de ofícios e protocolo

### Objetivo

Padronizar identificadores do sistema com regras explícitas e sequências corretas por escopo.

### Regras desejadas

| Identificador | Formato | Escopo da sequência | Momento de atribuição |
|---------------|---------|---------------------|------------------------|
| **Ofício (legislativo)** | `OFICIO-AAAA-0001` | **Por vereador** (autor da demanda), reinício anual | Envio oficial (`enviar`) |
| **Protocolo (executivo)** | `AAAA-0001` | **Global** (todos os ofícios), reinício anual | Despacho protocolo (`despachar`) |
| **Super OS** | `SUPER-AAAA-0001` | Global por ano (mantido) | Formação/despacho de cluster |

Exemplo: Vereador A envia 1º ofício de 2026 → `OFICIO-2026-0001`; Vereador B envia 1º ofício de 2026 → `OFICIO-2026-0001` (sequência independente). Protocolo do primeiro despacho de 2026 → `2026-0001` para qualquer vereador.

### Estado atual

| Campo | Formato atual | Sequência atual | Arquivo |
|-------|---------------|-----------------|---------|
| `protocolo_legislativo` | `OFICIO-AAAA-NNNN` | **Global por ano** (último de todos os vereadores) | `backend/core/views.py` (~L604–627) |
| `protocolo_executivo` | `AAAA-NNNN` | Global por ano | `backend/core/services/demanda_despacho_service.py` (`proximo_protocolo_executivo`) |
| `protocolo_super_os` | `SUPER-AAAA-NNNN` | Global por ano | `backend/core/services/cluster_despacho_service.py` |

O formato de **protocolo executivo** já atende `AAAA-0001`. A mudança principal é **ofício por vereador**.

### Implementação sugerida

1. Em `enviar`, filtrar último `protocolo_legislativo` por `demanda.autor_id` (ou `criado_por`) **e** ano.
2. Índice ou constraint de unicidade: `(autor, ano, sequência)` implícito no formato da string.
3. Migração de dados: ofícios legados mantêm numeração global; novos envios seguem regra por vereador (documentar corte de data).
4. UI: exibir `protocolo_legislativo` como «Nº do ofício» e `protocolo_executivo` como «Protocolo» nas telas de detalhe e listagem.
5. Testes: dois autores distintos recebem `OFICIO-2026-0001` cada; protocolo executivo continua monotônico global.

### Critérios de aceite

- [ ] Dois vereadores diferentes obtêm `OFICIO-2026-0001` no primeiro envio do ano.
- [ ] Mesmo vereador: segundo envio → `OFICIO-2026-0002`.
- [ ] Despachos sequenciais geram `2026-0001`, `2026-0002` independente do vereador.
- [ ] PDF e notificações exibem os números corretos.

---

## P8 — Tramitações: visibilidade para vereador

### Objetivo

No perfil **VEREADOR**, ocultar tramitações de **gestão operacional interna** durante a execução; exibir ao cidadão/vereador apenas marcos relevantes e, na etapa operacional, **predominantemente a conclusão**.

### Estado atual

- Timeline em `DemandaDetailView.vue` mostra **todas** as tramitações para todos os perfis (`timelineOrdenada`, `v-html` na descrição).
- Tipos disponíveis em `Tramitacao.TIPO_CHOICES` (`backend/core/models.py`): `EXECUCAO`, `ANALISE_TECNICA`, `COMENTARIO`, `TRANSFERENCIA`, `ENCAMINHAMENTO_SETOR`, `PROGRAMACAO`, `ATRASO`, `CONCLUSAO`, etc.

### Comportamento desejado

**Perfil VEREADOR** — exibir na timeline:

| Tipo | Visível? | Notas |
|------|----------|-------|
| `ENVIO_OFICIAL` | Sim | Marco de envio |
| `DESPACHO` | Sim | Encaminhamento ao executivo |
| `CONCLUSAO` | Sim | Resultado / conclusão do serviço |
| `SOLICITACAO_DEVOLUTIVA` | Sim (resumo) | Pode mostrar texto institucional, não detalhes internos |
| `DEVOLUTIVA_PROTOCOLO` | Sim | Devolutiva ao gabinete |
| `CIENCIA_VEREADOR` | Sim | Ciência registrada |
| `ENCERRAMENTO_DEVOLUTIVA` | Sim | Encerramento |
| `EXECUCAO` | **Não** | Gestão operacional |
| `ANALISE_TECNICA` | **Não** | Gestão operacional |
| `COMENTARIO` | **Não** | Gestão operacional |
| `TRANSFERENCIA` | **Não** | Gestão operacional |
| `ENCAMINHAMENTO_SETOR` | **Não** | Gestão operacional |
| `PROGRAMACAO` | **Não** | Gestão operacional |
| `ATRASO` | **Não** | Gestão operacional |
| `STATUS_UPDATE` | **Não** | Gestão operacional |

**Regra de etapa:** enquanto `status === 'EM_EXECUCAO'`, o vereador não vê andamentos operacionais; quando houver `CONCLUSAO`, exibir como marco principal (mensagem amigável, ex.: «Serviço concluído pela Secretaria»).

**Demais perfis:** sem filtro (comportamento atual).

### Implementação sugerida

| Opção | Prós | Contras |
|-------|------|---------|
| **A — Filtro no frontend** | Rápido; sem mudança de API | Dados ainda trafegam na API |
| **B — Filtro no serializer** | Segurança; contrato claro por perfil | Requer parâmetro de contexto no serializer |

Recomendação: **opção B** em `TramitacaoSerializer` ou queryset aninhado em `DemandaDetailSerializer` quando `request.user.perfil == 'VEREADOR'`, com lista `TIPOS_VISIVEIS_VEREADOR` centralizada (backend).

### Critérios de aceite

- [ ] Vereador em `EM_EXECUCAO` não vê tramitações `EXECUCAO` / `TRANSFERENCIA` na timeline.
- [ ] Vereador vê `CONCLUSAO` quando registrada pela secretaria.
- [ ] Protocolo e secretaria continuam vendo timeline completa.
- [ ] Super OS: mensagem informativa mantida; andamentos replicados `[Super OS]` não expõem detalhe operacional ao vereador.

---

## P9 — Dashboard secretaria: remover gráfico

### Objetivo

Na dashboard de usuários **SECRETARIA**, remover o gráfico **«Demandas por Secretaria»**, que pouco agrega (secretaria já filtra pelo próprio órgão).

### Estado atual

- `DashboardView.vue` (~L303–307): gráfico exibido para todos exceto `VEREADOR`.
- Secretaria carrega stats com `secretaria_destino` fixo (~L53–57).
- Backend: `DashboardStatsAPIView` agrega por órgão Sinapse.

### Comportamento desejado

- `v-if` do gráfico: exibir para `GESTOR` e `PROTOCOLO` apenas (ou manter para gestor; ocultar para `SECRETARIA`).
- Manter cards/resumo operacional da secretaria (fila do setor, Super OS) já entregues na Onda 1.

### Arquivos

- `frontend/src/views/DashboardView.vue`

### Critérios de aceite

- [ ] Login SECRETARIA: dashboard sem gráfico de barras por secretaria.
- [ ] Login GESTOR/PROTOCOLO: gráfico permanece (se aplicável ao perfil).

---

## P10 — Botão «Voltar» em editar rascunho

### Objetivo

Na tela **«Editar rascunho do ofício»** (`/demandas/editar/:id`), incluir botão **«Voltar»** além do «Cancelar» existente.

### Estado atual

- `DemandaForm.vue`: botão **Cancelar** → `router.push('/demandas')` (~L724).
- Sem `router.back()` nem retorno contextual (ex.: viria do Copiloto ou da lista).

### Comportamento desejado

- Botão **«Voltar»** (secundário, ícone `pi-arrow-left`): `router.back()` com fallback para `/demandas` se não houver histórico.
- Manter **Cancelar** com comportamento atual ou unificar rótulos (definir na implementação: «Voltar» = navegação; «Cancelar» = descartar alterações não salvas — se houver dirty state).

### Arquivos

- `frontend/src/views/DemandaForm.vue`

### Critérios de aceite

- [ ] Usuário abre rascunho a partir da lista → «Voltar» retorna à lista.
- [ ] Usuário abre a partir do Copiloto → «Voltar» retorna ao Copiloto (via histórico).

---

## P11 — Descrição estruturada no detalhe da demanda

### Objetivo

Na tela **Demanda** (detalhe), perfis **PROTOCOLO**, **SECRETARIA** e **ADMIN/GESTOR** devem ver o campo **Descrição** com a mesma **formatação estruturada** que o vereador vê na edição (parágrafos HTML, quebras de linha).

### Estado atual

- Detalhe: `v-html="demanda.descricao"` para **todos** os perfis (`DemandaDetailView.vue` ~L726–728).
- Edição: `descricaoParaHtml()` em `DemandaForm.vue` converte texto plano → `<p>`/`<br>` no Editor.
- Se a descrição foi salva como texto plano (legado), protocolo/secretaria podem ver bloco sem parágrafos; vereador no editor vê formatado.

### Comportamento desejado

1. Função compartilhada `descricaoParaHtml` (extrair para `frontend/src/utils/oficioTexto.js` ou similar).
2. No detalhe, para `PROTOCOLO`, `SECRETARIA`, `GESTOR`: aplicar `descricaoParaHtml(demanda.descricao)` antes do `v-html` (idempotente se já for HTML).
3. Vereador: manter visualização atual (já é HTML na maioria dos casos).
4. Opcional backend: normalizar descrição no `save` do rascunho para HTML consistente.

### Critérios de aceite

- [ ] Descrição com parágrafos separados por linha em branco renderiza igual para vereador e protocolo no detalhe.
- [ ] Sem regressão XSS: conteúdo continua originado do sistema (rascunho do autor).

---

## P12 — Despachar no detalhe da demanda (protocolo)

### Objetivo

Na tela **Demanda** (detalhe), perfil **PROTOCOLO** deve ter botão **«Enviar / Despachar»** para demandas em `AGUARDANDO_PROTOCOLO`, sem obrigar retorno à lista.

### Estado atual

- Despacho apenas em `DemandasView.vue` (botão na tabela e painel protocolo, diálogo `despachoDialog`).
- `DemandaDetailView.vue`: não há ação de despacho para `AGUARDANDO_PROTOCOLO`.
- Backend: `POST /api/demandas/{id}/despachar/` restrito a `perfil == 'PROTOCOLO'` (`views.py` ~L683–720).

### Comportamento desejado

1. Botão visível quando `isProtocolo && demanda.status === 'AGUARDANDO_PROTOCOLO'`.
2. Reutilizar lógica/diálogo de despacho de `DemandasView` (extrair componente `DespachoDemandaDialog.vue`) ou navegação mínima com confirmação de secretaria/setor.
3. Após sucesso: recarregar demanda e toast; status → `PROTOCOLADO`.
4. **GESTOR:** não despacha no backend — botão só para PROTOCOLO (alinhar com contrato atual).

### Critérios de aceite

- [ ] Protocolo despacha do detalhe; lista e detalhe ficam consistentes.
- [ ] Demanda não elegível (outro status) não exibe o botão.
- [ ] Fluxo Super OS / coorte AUTO não quebrado (despacho unitário continua válido).

---

## P13 — Tabelas responsivas (scroll horizontal)

### Objetivo

Padronizar **todas** as tabelas do frontend com comportamento responsivo em telas estreitas (scroll horizontal).

### Estado atual

| Tela | `responsiveLayout="scroll"` |
|------|----------------------------|
| `DemandasView.vue` | Sim |
| `SinapseReconciliacaoView.vue` | Sim |
| `AdminFaqView.vue` | Sim |
| `RelatoriosView.vue` | Sim |
| `FluxoServicosView.vue` | **Não** |
| `SetoresView.vue` | **Não** |
| `ClustersView.vue` | **Não** |
| `TendenciasGestaoView.vue` | **Não** |
| `CartaExplorerView.vue` | **Não** |
| `NotificacoesView.vue` | Verificar |
| `RecentSalesWidget.vue` | Sim |

### Comportamento desejado

1. Constante ou classe utilitária, ex.: `TABLE_RESPONSIVE_SCROLL` → `responsiveLayout="scroll"` + `class="sgdl-table-scroll"`.
2. CSS global (ex. `frontend/src/assets/styles.scss`): `.sgdl-table-scroll .p-datatable-wrapper { overflow-x: auto; }` e `min-width` em colunas críticas onde necessário.
3. Aplicar em **todas** as `DataTable` de views de produção.

### Critérios de aceite

- [ ] Viewport mobile (~375px): tabelas principais permitem scroll horizontal sem quebrar layout.
- [ ] `npm run build` sem erro.

---

## P14 — Regras de acesso (menu e rotas)

### Objetivo

Ajustar permissões de navegação conforme papel operacional de cada perfil.

### Mudanças desejadas

| Feature | Rota | Antes | Depois |
|---------|------|-------|--------|
| **Carta de Serviços** | `/carta-servicos` | VEREADOR, GESTOR, PROTOCOLO | + **SECRETARIA** |
| **Fluxo por serviço** | `/gestao-fluxo-servicos` | GESTOR, PROTOCOLO | **GESTOR** apenas |
| **Reconciliação Sinapse** | `/integracoes/sinapse/reconciliacao` | GESTOR, PROTOCOLO | **GESTOR** apenas |
| **FAQ Copiloto** | `/admin/faq-copiloto` | GESTOR, PROTOCOLO | **GESTOR** apenas |

### Arquivos a alterar

| Arquivo | Alteração |
|---------|-----------|
| `frontend/src/layout/AppMenu.vue` | `visible` por item |
| `frontend/src/router/index.js` | `meta.perfis` em cada rota |
| Backend (se houver guard) | Endpoints de fluxo/reconciliação/FAQ: validar `403` para PROTOCOLO |

### Estado atual (referência)

```javascript
// AppMenu.vue — trechos atuais
Carta: ['VEREADOR', 'GESTOR', 'PROTOCOLO']
Fluxo: ['GESTOR', 'PROTOCOLO']
Reconciliação: ['GESTOR', 'PROTOCOLO']
FAQ: ['GESTOR', 'PROTOCOLO']
```

### Critérios de aceite

- [ ] SECRETARIA acessa `/carta-servicos` (menu + rota).
- [ ] PROTOCOLO **não** vê menu nem acessa rotas de Fluxo, Reconciliação e FAQ (redirect `/auth/access` ou 403 na API).
- [ ] GESTOR mantém acesso integral às três telas administrativas.
- [ ] Documentar matriz de perfis em [ROADMAP.md](../ROADMAP.md) (mapa por perfil).

---

## Ordem de implementação sugerida

Prioridade por **valor + baixo risco** (homologação):

1. **P14** — Acesso (menu/rotas): mudança localizada, sem migração.
2. **P9** — Dashboard secretaria: uma linha de `v-if`.
3. **P10** — Voltar no rascunho: UX imediata.
4. **P13** — Tabelas scroll: polish transversal.
5. **P12** — Despachar no detalhe: reutilizar diálogo existente.
6. **P11** — Descrição estruturada: util compartilhado.
7. **P8** — Filtro tramitações vereador: regra de negócio + testes API.
8. **P7** — Numeração por vereador: migração lógica + testes.
9. **P6** — Painel formatação ofício: maior escopo (API + tela + PDF).

---

## Matriz de impacto por perfil (pós-P14)

| Tela / recurso | Vereador | Protocolo | Secretaria | Gestor |
|----------------|:--------:|:---------:|:----------:|:------:|
| Carta de Serviços | Sim | Sim | **Sim** (novo) | Sim |
| Fluxo por serviço | — | **—** (removido) | — | Sim |
| Reconciliação Sinapse | — | **—** (removido) | — | Sim |
| FAQ Copiloto | — | **—** (removido) | — | Sim |
| Painel formatação ofício (P6) | — | — | — | Sim |
| Timeline completa | Filtrada (P8) | Sim | Sim | Sim |
| Despachar no detalhe (P12) | — | Sim | — | — |
| Descrição estruturada (P11) | — | Sim | Sim | Sim |

---

## Evidências de pronto (Onda 2 — este pacote)

```bash
# Backend
cd backend
python manage.py test core.tests.test_protocolo_numeracao core.tests.test_tramitacao_visibilidade_vereador
python manage.py check --deploy

# Frontend
cd frontend
npm run build
npm run lint
```

Checklist manual: seção **Onda 2** em `operacao/homologacao-go-live.md` (a criar na implementação).

---

**Última atualização:** 2026-06-02  
**Autor:** especificação incorporada a partir de requisitos de produto (sessão jun/2026).
