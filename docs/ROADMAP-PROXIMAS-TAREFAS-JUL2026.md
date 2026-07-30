# Próximas tarefas — SGDL (jul/2026)

> Backlog acordado após conclusão da **geocodificação MC (fases 1–3)**.  
> Referência geocodificação: [especificacoes/geocodificacao-endereco-mogi.md](especificacoes/geocodificacao-endereco-mogi.md)

**Atualizado:** 2026-07-30

---

## Status geral

| # | Tarefa | Status | Prioridade |
|---|--------|--------|------------|
| 1 | Delay pós despacho — janela CRUD (60 s) | **Concluída** | Alta |
| 2 | Módulo de gestão de textos padrão de despachos | Pendente | Alta |
| 3 | Gestão Cluster — Super OS manual (UI secretaria/gestor) | **Próxima** | Média |
| 4 | Análise base legada de serviços × carta Sinapse (prioridades Copiloto) | Pendente | Média |
| 5 | Copiloto Indicações — classificação semântica × carta Sinapse | Pendente | Alta |

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

## 2. Módulo de textos padrão de despachos

**Objetivo:** CRUD administrativo de modelos de texto (despacho inicial, devolutiva, conclusão, scatter) com placeholders (órgão, protocolo, prazo).

**Entregáveis previstos:**
- Modelo `TextoPadraoDespacho` (categoria, perfil, corpo, ativo)
- Tela de gestão (Protocolo / admin)
- Integração nos formulários (`FormularioTramitacao`, despacho Protocolo)

**Critério de pronto:** operador escolhe modelo, edita e assina; trilha de auditoria.

**Status:** não iniciado — priorizar após Tarefa 3 se necessário para piloto operacional.

---

## 3. Gestão Cluster — Super OS manual ⏭

**Objetivo:** Interface para usuários operacionais (Secretaria, Gestor) **criar manualmente** Super OS / agrupar demandas, além do fluxo automático (~300 m).

**Entregáveis previstos:**
- Tela ou extensão de `/clusters` com «Nova Super OS»
- Seleção de demandas elegíveis + confirmação
- Regras de visibilidade por perfil (RBAC)

**Critério de pronto:** Super OS manual criada, despachada e visível nas filas corretas.

---

## 4. Análise base legada × carta Sinapse

**Objetivo:** Importar/comparar base histórica de serviços (gestão anterior) com `CatalogServico` Sinapse; definir **prioridades e sinônimos** no Copiloto/triagem.

**Entregáveis previstos:**
- Inventário da base legada (CSV/API)
- Relatório de cobertura (% carta, gaps, duplicatas)
- Proposta de mapeamento + seed de hints Copiloto

**Critério de pronto:** documento de priorização validado + amostra de 20 serviços mapeados.

---

## 5. Copiloto Indicações — classificação semântica × carta

**Objetivo:** Indicações legislativas devem se comportar como **Ofícios** na triagem semântica do Copiloto: se a descrição reconhecer um serviço presente na carta Sinapse, **classificar e vincular**; se não estiver na carta, registrar como **tendência** — com exceções para pedidos de estudo, ações, implantações ou revitalizações em larga escala.

**Contexto (piloto jul/2026):** teste com indicação solicitando *«Manutenção com nivelamento e cascalhamento»* (serviço existente na carta) — esperado: Copiloto sugere/vincula o serviço; comportamento atual diverge do fluxo de Ofícios.

**Regras de negócio:**
| Situação | Comportamento esperado |
|----------|------------------------|
| Serviço reconhecido **na carta** | Classificar e propor vínculo (`sinapse_servico_id`) como Ofício |
| Serviço **fora da carta** | Entrada como **tendência** (sem forçar serviço inexistente) |
| Pedido de estudo, ação, implantação ou revitalização **em larga escala** | **Não** forçar vínculo carta; manter como tendência / encaminhamento amplo |

**Entregáveis previstos:**
- Reuso/alinhamento do pipeline semântico Ofício → Indicação (`copiloto_faq`, competência, LLM assistivo)
- Ajuste em `CopilotoView` / serviços de indicação e triagem
- Testes com amostra incluindo «Manutenção com nivelamento e cascalhamento»
- Documentação operacional para perfil Câmara

**Critério de pronto:** indicação com serviço carta classificada corretamente; indicação fora da carta vira tendência; exceções de larga escala respeitadas; validação humana antes de protocolar.

---

## Referências

| Documento | Uso |
|-----------|-----|
| [ROADMAP.md](ROADMAP.md) | Status consolidado |
| [ROADMAP_PRODUTO.md](ROADMAP_PRODUTO.md) | Fases produto |
| [fluxo-auto-manual.md](operacao/fluxo-auto-manual.md) | Despacho AUTO × manual |

**Configuração janela de correção:** `DESPACHO_JANELA_EDICAO_SEGUNDOS` (default 60) em `settings.py` / `.env`.
