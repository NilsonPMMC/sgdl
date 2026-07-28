# Estudo / viabilidade — base stand-by

> **Módulo:** demandas finalizadas sem execução material, registradas para gestão executiva.  
> **Status Fase 1:** **concluída** (jul/2026) · **Fases 2–3:** planejadas

---

## Problema

Demandas inviáveis ou não executáveis no curto prazo (ex.: «iluminação pública de todo o município») precisam **encerrar o ciclo legislativo** com resposta ao vereador, mas **registrar** que não houve execução material — formando uma **base stand-by** consultável pelo executivo (Protocolo, secretarias, gestores).

---

## Decisões de produto (válidas para todas as fases)

| # | Decisão |
|---|---------|
| 1 | **`FINALIZADO` permanece único** — não criar status paralelo. |
| 2 | Classificação na **conclusão operacional da Secretaria** (ou encerramento scatter-gather equivalente). |
| 3 | Só entra na base quem for **sinalizado** (`registrar_stand_by=true`). |
| 4 | Vereador pode repetir pedido; **executivo** vê referências stand-by (informativo, **não bloqueia** novo protocolo). |
| 5 | **Escopo geográfico obrigatório** ao registrar stand-by. |
| 6 | **Sem prazo definido na Fase 1** — gestão de prazos fica para Fase 2. |

---

## Fase 1 — Registro e consulta (concluída)

### Escopo entregue

**Backend**

- Modelo `RegistroEstudoViabilidade` + campos em `Demanda` (`resultado_operacional`, `motivo_nao_execucao`, `escopo_geografico`, `stand_by_estudo_viabilidade`).
- Migração `0071_estudo_viabilidade`.
- Serviço `EstudoViabilidadeService` — validação, persistência, referências geográficas.
- Integração nas conclusões: `conclusao-tecnica`, `solicitar-devolutiva`, `scatter-gather` / `nos-unificados` (quando `processo_avancou`).
- API `GET /api/estudos-viabilidade/`.
- Filtro de listagem `fila=stand_by` e `stand_by_estudo=true`.
- Serializer: `registro_estudo_viabilidade`, `referencias_stand_by` (somente executivo).
- Admin Django: `RegistroEstudoViabilidade`.

**Frontend**

- Formulário `FormularioResultadoOperacional` na conclusão operacional (dialog assinatura) e no encerramento scatter-gather.
- Badge **Stand-by (estudo)** no detalhe e na listagem (executivo).
- Aba **Stand-by (estudo)** em Demandas (Protocolo/Gestor).
- Filtro **Somente stand-by** para Secretaria (escopo Encerrado).

**Resultados operacionais**

| Valor | Uso |
|-------|-----|
| `EXECUTADO` | Padrão retrocompatível |
| `RESPONDIDO_SEM_EXECUCAO` | Exige motivo; permite stand-by |
| `ORIENTACAO` | Permite stand-by |
| `PARCIAL` | Sem stand-by na Fase 1 |

**Motivos de não execução:** estudo/viabilidade, investimento, licitação, norma, inviável técnico, informativo.

### Correções pós-homologação (jul/2026)

- **Bug scatter-gather:** encerramento via `executarEncerrarSelecionados` não enviava payload stand-by → corrigido no frontend.
- **Bug backend:** scatter sem payload gravava `EXECUTADO` por padrão → scatter só persiste quando há payload explícito.

### Evidências

- `manage.py test core.tests.test_estudo_viabilidade` (12 testes).
- `npm run build` (frontend).
- E2E homologação: demandas evidência #3879, #3882 (retroativa).

### Arquivos principais

| Área | Caminhos |
|------|----------|
| Modelo | `backend/core/models_estudo_viabilidade.py`, `models.py`, `0071_estudo_viabilidade.py` |
| Serviço | `backend/core/services/estudo_viabilidade_service.py` |
| API | `views_estudo_viabilidade.py`, `views_operacional.py`, `views.py`, `filters.py`, `serializers.py` |
| Frontend | `estudoViabilidade.js`, `FormularioResultadoOperacional.vue`, `DemandaDetailView.vue`, `FormularioScatterGather.vue`, `DemandasView.vue` |
| Testes | `backend/core/tests/test_estudo_viabilidade.py` |

### Critério de pronto (Fase 1) — atendido

- [x] Secretaria registra stand-by na conclusão com escopo e motivo.
- [x] Processo segue até `FINALIZADO` sem novo status.
- [x] Executivo consulta fila stand-by e vê referências em novas demandas similares.
- [x] Vereador não vê base stand-by; pode protocolar novamente.
- [x] Testes automatizados + build frontend.

---

## Fase 2 — Gestão executiva da base (planejada)

**Objetivo:** transformar a base stand-by de «registro passivo» em **ferramenta de gestão** para Protocolo, gestores e secretarias — sem alterar o ciclo legislativo do vereador.

### Escopo proposto

#### 2.1 Prazos e acompanhamento

- Campos opcionais no registro: **previsão de retomada**, **responsável pela análise**, **status de gestão** (ex.: em estudo, aguardando investimento, arquivado administrativamente).
- **Alertas internos** para executivo (notificação / dashboard) quando prazo se aproximar ou vencer — **sem** expor prazo ao vereador na Fase 2.
- Filtros avançados: por motivo, órgão, escopo textual, serviço Sinapse, bairro, «vencidas», «sem previsão».

#### 2.2 Painel stand-by

- Tela dedicada ou extensão de Relatórios: volume por motivo, por secretaria, por serviço, mapa por bairro/escopo.
- Export CSV (similar ao admin Serviços Otimizados) para reuniões de gestão.
- Ações em lote leves: marcar «em análise», atribuir responsável (sem reabrir demanda).

#### 2.3 Retomada operacional (conceitual)

- Flag `pode_retomar` já existe no modelo — evoluir para fluxo guiado:
  - «Retomar estudo» → cria **nova demanda** vinculada ao registro stand-by (auditoria), **ou**
  - reabertura controlada apenas para executivo (decisão de produto a validar).
- Histórico: registro stand-by permanece imutável; retomada gera trilha nova.

#### 2.4 Refinos de UX

- Stand-by visível na conclusão **Protocolo** (somente leitura do registro da secretaria).
- Resumo stand-by no **Consulta Hub** / dashboard gestor.
- Mensagens de empty-state e tooltips alinhados ao vocabulário institucional.

### Fora de escopo (Fase 2)

- Novo status de demanda.
- Bloqueio automático de protocolo pelo Copiloto (Fase 3).
- Integração financeira / licitação externa.

### Dependências técnicas

- Estabilidade Fase 1 em homologação (scatter + fluxo direto).
- Definição institucional de ** quem define prazo** e ** quem recebe alerta**.

### Critério de pronto (Fase 2)

- [ ] Gestor/Protocolo filtra e exporta base stand-by com prazos.
- [ ] Secretaria vê demandas stand-by do órgão com status de gestão.
- [ ] Alertas configuráveis (mínimo: vencimento de previsão).
- [ ] Fluxo de retomada documentado e testado (1 cenário E2E).
- [ ] Testes backend + build frontend.

### Estimativa de esforço (ordem de grandeza)

| Entrega | Complexidade |
|---------|----------------|
| 2.1 Prazos + status gestão | Média |
| 2.2 Painel + CSV | Média |
| 2.3 Retomada vinculada | Alta |
| 2.4 UX refinements | Baixa |

---

## Fase 3 — Inteligência assistiva e interoperabilidade (planejada)

**Objetivo:** usar a base stand-by no **Copiloto** e na **evolução Sinapse/MOVA**, em modo **assistivo** (sugestão + validação humana + auditoria).

### Escopo proposto

#### 3.1 Copiloto — materialização

- Na triagem / confirmação de rascunho: se existir stand-by **compatível** (mesmo serviço + proximidade geográfica), exibir **alerta informativo** ao vereador/assessor:
  - «Já existe demanda finalizada sobre tema similar em stand-by — o executivo foi orientado; você pode protocolar normalmente.»
- Para **executivo** no Copiloto (se aplicável): link direto ao registro stand-by.
- **Não bloquear** protocolo (decisão Fase 1 mantida).

#### 3.2 Copiloto — sugestão de stand-by na conclusão

- Modo assistivo na conclusão secretaria: sugerir motivo/escopo a partir do parecer (LLM local/Groq), **sempre** com confirmação explícita antes de gravar.

#### 3.3 Tendências e clusters

- Correlacionar registros stand-by com **tendências** e **clusters** (volume por tema/bairro).
- Indicador no mapa de calor: «demandas não executadas registradas» vs «executadas».

#### 3.4 Interoperabilidade (Sinapse / MOVA)

- Sincronização auditável de registros stand-by relevantes para planejamento (API isolada, mapeamento, sem acoplamento direto ao núcleo).
- Alinhamento ao pilar **UX guiado + IA assistiva** ([evolucao-sinapse-mova](../.cursor/rules/evolucao-sinapse-mova.mdc)).

#### 3.5 Governança e auditoria

- Relatório periódico stand-by → investimento/licitação (export enriquecido).
- Log de alterações em `RegistroEstudoViabilidade` (quem alterou previsão/status na Fase 2+).

### Riscos e mitigações

| Risco | Mitigação |
|-------|-----------|
| Falso positivo na duplicidade stand-by | Mesmo raio 300 m + serviço; mensagem informativa; não bloquear |
| LLM sugere stand-by indevido | Sugestão desligável; confirmação humana obrigatória |
| Sobrecarga de alertas | Preferências por perfil; digest diário na Fase 3 |

### Critério de pronto (Fase 3)

- [ ] Alerta Copiloto stand-by em homologação (≥3 casos de teste documentados).
- [ ] Sugestão assistiva de conclusão (feature flag).
- [ ] Integração tendências/clusters mínima (contagem por serviço).
- [ ] Documentação operacional + testes regressão Copiloto.

---

## Referências cruzadas

- [gestao-operacional-portal-vereadores.md](gestao-operacional-portal-vereadores.md) — conclusão operacional e scatter-gather.
- [homologacao-e2e-registro.md](../operacao/homologacao-e2e-registro.md) — usuários seed homologação.
- [ROADMAP.md](../ROADMAP.md) — trilha consolidada.

---

## Histórico

| Data | Evento |
|------|--------|
| 2026-07 | Fase 1 implementada; homologação demandas #3879, #3882; correção scatter-gather |
| — | Fase 2–3 documentadas para planejamento futuro |
