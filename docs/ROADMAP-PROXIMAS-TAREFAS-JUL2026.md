# Próximas tarefas — SGDL (jul/2026)

> Backlog acordado após conclusão da **geocodificação MC (fases 1–3)**.  
> Referência geocodificação: [especificacoes/geocodificacao-endereco-mogi.md](especificacoes/geocodificacao-endereco-mogi.md)

**Atualizado:** 2026-07-30 (Fase 3 concluída)

---

## Status geral

| # | Tarefa | Status | Prioridade |
|---|--------|--------|------------|
| 1 | Delay pós despacho — janela CRUD (60 s) | **Concluída** | Alta |
| 2 | Módulo de gestão de textos padrão de despachos | **Concluída** | Alta |
| 3 | Gestão Cluster — vinculação manual a Super OS existente | **Concluída** | Média |
| 4 | Análise base legada de serviços × carta Sinapse (prioridades Copiloto) | Adiada | Média |
| 5 | Copiloto Indicações — classificação semântica × carta Sinapse | **Concluída** | Alta |

---

## 1. Delay pós despacho — janela CRUD (60 s) ✅

**Objetivo:** Após registrar um despacho/andamento (Protocolo, Secretaria, Gestor), permitir **corrigir ou desfazer** o texto por **60 segundos** (configurável), antes de consolidar na timeline.

**Escopo implementado (homologação jul/2026):**

- Campo `editavel_ate` em `Tramitacao` + migration `0076_tramitacao_editavel_ate`
- Setting `DESPACHO_JANELA_EDICAO_SEGUNDOS` (default **60**) em `settings.py` / `.env`
- Serviço `tramitacao_janela_edicao_service.py`: elegibilidade, janela, PATCH/DELETE, reversão scatter/protocolo
- API `PATCH` / `DELETE` em `/api/tramitacoes/{id}/` dentro da janela
- Signal `post_save` abre janela automaticamente ao criar tramitação elegível
- UI `TramitacaoJanelaCorrecao.vue`: contador regressivo (60s…59s…), pausa na edição/confirmação, editor rico maximizável
- Integração em `OperacionalTimeline` e `DemandaDetailView` (Protocolo, Secretaria, Gestor)
- **Protocolo — despacho inicial e conclusão final:**
  - Tramitação preview visível na timeline **enquanto aguarda validação do gestor** (`aguardando_validacao_gestor`)
  - Contador de 60s inicia na assinatura do operador; reinicia ao salvar correção
  - Após validação do gestor: executa despacho/conclusão na tramitação existente + nova janela de 60s
  - Desfazer pendente cancela validação e libera novo ciclo de assinatura
- **Refresh imediato na timeline** após PATCH (`sincronizarTramitacoesNaTimeline` + reload completo)
- Desfazer: limpa assinaturas (evita `IntegrityError`), reverte nós scatter/filhos órfãos, status da demanda quando aplicável
- Testes: `test_tramitacao_janela_edicao.py` (14+ casos), `test_assinatura_validacao_gestor`, `test_views_operacional`

**Configuração:** `DESPACHO_JANELA_EDICAO_SEGUNDOS` em `settings.py` / `.env`

**Evidências de execução:** `manage.py test core.tests.test_tramitacao_janela_edicao` · `npm run build`

---

## 2. Módulo de textos padrão de despachos ✅

**Objetivo:** CRUD de modelos de texto com formatação rica (Editor/Quill) e placeholders (`{{protocolo_executivo}}`, `{{autor_nome}}`, etc.), reutilizáveis nos formulários de despacho/andamento/devolutiva.

**Escopo implementado (jul/2026):**

- Modelo `TextoPadraoDespacho` + migrations `0077`–`0079` (M2M setores; categorias simplificadas)
- **Duas famílias de categoria** (sem matriz por tipo de formulário):
  - **PROTOCOLO** — despacho inicial e final (protocolo → secretaria/vereador/câmara)
  - **OPERACIONAL** — tramitações secretaria ↔ setores
- Picker e CRUD filtram **só a categoria do perfil logado** (gestor geral vê ambas)
- Escopo automático por perfil: Protocolo → setor protocolo; Secretaria → órgão/setor; Gestor setorial → setores vinculados; Gestor geral → uso geral
- Seleção explícita de setor(es) quando o usuário tem múltiplas UAs
- Serviço `texto_padrao_despacho_service.py`: visibilidade, placeholders, `contexto_demanda` (`protocolo_executivo_efetivo`, autor, prazo)
- API `/api/textos-padrao-despacho/` (CRUD + `aplicar/` + `meta-criacao/`)
- Tela **Operação → Textos padrão** (`TextosPadraoDespachoView.vue`) com biblioteca de placeholders clicáveis
- Integração via `DescricaoTramitacaoEditor` + `PlaceholdersTextoPadraoChips` nos formulários de tramitação
- Correção placeholders: `demanda-id` + contexto completo ao abrir despacho/devolutiva pela lista
- Testes: `test_texto_padrao_despacho.py`

**Fora de escopo (futuro):** textos automáticos de envio vereador/câmara → protocolo (matriz gestor geral).

**Critério de pronto:** operador escolhe modelo ou cria na hora, placeholders preenchidos na aplicação, edita no Editor e assina.

**Evidências:** `manage.py check` · `npm run build` · migrations `0077`–`0079`

---

## 3. Gestão Cluster — vinculação manual a Super OS existente ✅

**Status:** concluída (jul/2026).

**Objetivo:** Permitir que operadores (**Protocolo, Gestor, Secretaria**) integrem manualmente ofícios que o agrupamento automático (~300 m / mesmo serviço) não reconheceu a um **grupo Super OS já ativo** — sem criar Super OS do zero.

**Escopo implementado:**

- **`/clusters`**: botão «Vincular ofício» com busca por ofício, vereador, bairro ou logradouro (substitui digitação de ID)
- API `GET /api/clusters/{id}/demandas-candidatas/` — candidatos com flag «Pode vincular» e motivo de bloqueio
- **`DemandaDetailView`**: atalho «Vincular a Super OS» para ofícios aguardando protocolo, sem cluster
- API `GET /api/demandas/{id}/clusters-vinculo/` — grupos compatíveis com o ofício aberto
- RBAC: vincular/desvincular → Protocolo, Gestor, Secretaria; despacho em lote Super OS → somente Protocolo
- Escopo Secretaria/Gestor setorial por órgão na listagem de clusters

**Fora de escopo (deliberado):** botão «Nova Super OS» — grupos nascem do fluxo automático; a ferramenta apenas **completa/corrige** o agrupamento.

**Critério de pronto:** operador localiza grupo → busca ofício → vincula com feedback claro → grupo atualizado na tela e no detalhe da demanda.

**Evidências:** `npm run build` · commit `8217755` e complementos · testes `test_cluster_vinculo_candidatas.py`

---

## 4. Análise base legada × carta Sinapse ⏸

**Status:** adiada.

**Objetivo:** Importar/comparar base histórica de serviços (gestão anterior) com `CatalogServico` Sinapse; definir **prioridades e sinônimos** no Copiloto/triagem.

**Entregáveis previstos:**
- Inventário da base legada (CSV/API)
- Relatório de cobertura (% carta, gaps, duplicatas)
- Proposta de mapeamento + seed de hints Copiloto

**Critério de pronto:** documento de priorização validado + amostra de 20 serviços mapeados.

---

## 5. Copiloto Indicações — classificação semântica × carta ✅

**Objetivo:** Indicações legislativas devem se comportar como **Ofícios** na triagem semântica do Copiloto: se a descrição reconhecer um serviço presente na carta Sinapse, **classificar e vincular**; se não estiver na carta, registrar como **tendência** — com exceções para pedidos de estudo, ações, implantações ou revitalizações em larga escala.

**Escopo implementado (jul/2026):**

- Indicações (perfil **CAMARA**) passam pelo **mesmo pipeline semântico** de ofícios: LLM → triagem Sinapse → painel «Serviço na carta» ou tendência → endereço (opcional) → PDF → vereadores/número → rascunho
- Removidos bypasses de triagem/vínculo (`acionar_triagem_sinapse`, `_item_vinculo_catalogo_resolvido`, `_forcar_regras_estado_rigidas`, `_indices_demandas_sem_servico_confirmado`)
- Materialização propaga `sinapse_servico_id` + `origem_vinculo=CARTA` ou `tendencia` + `origem_vinculo=TENDENCIA`
- Frontend `CopilotoView`: painel de serviço visível; exige vínculo carta/tendência antes de finalizar
- `CopilotoIndicacaoCampos`: persistência explícita de vereadores/número na sessão antes de gerar rascunho; card «Gerar rascunho da indicação»
- Correções homologação: `NameError` de `session` na triagem; metadados não salvos ao digitar «finalizar»
- Testes: `test_copiloto_indicacao_carta.py` (vínculo, nivelamento/cascalhamento, materialização com serviço carta)
- Commits: `a91e2d5`, `97930d3`, `19edf5d`

**Regras de negócio (atendidas):**

| Situação | Comportamento |
|----------|---------------|
| Serviço reconhecido **na carta** | Triagem + confirmação humana → `sinapse_servico_id` |
| Serviço **fora da carta** | Opção «Nenhuma das opções» → tendência |
| Pedido amplo (estudo/revitalização) | Heurística existente `_item_sugere_trilha_tendencia` / escolha humana |

**Fora de escopo (futuro):** documentação operacional dedicada perfil Câmara; refinamento heurística «larga escala» dedicada.

**Critério de pronto:** indicação com serviço carta classificada e confirmada; fora da carta vira tendência; validação humana antes de protocolar.

**Evidências:** `manage.py check` · `npm run build` · homologação caso «nivelamento e cascalhamento» (Estrada da Mineração)

---

## Referências

| Documento | Uso |
|-----------|-----|
| [ROADMAP.md](ROADMAP.md) | Status consolidado |
| [ROADMAP_PRODUTO.md](ROADMAP_PRODUTO.md) | Fases produto |
| [fluxo-auto-manual.md](operacao/fluxo-auto-manual.md) | Despacho AUTO × manual |

**Configuração janela de correção:** `DESPACHO_JANELA_EDICAO_SEGUNDOS` (default 60) em `settings.py` / `.env`.
