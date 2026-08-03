# Apontamentos — reunião homologação (jul/2026)

> **Contexto:** reunião operacional de homologação (31/jul/2026) — correções priorizadas antes do piloto contínuo.  
> **Índice:** [ROADMAP-PROXIMAS-TAREFAS-JUL2026.md](../ROADMAP-PROXIMAS-TAREFAS-JUL2026.md) · [piloto-apontamentos-jun2026.md](piloto-apontamentos-jun2026.md)

**Data do registro:** 2026-07-31  
**Ambiente:** homologação operacional  
**Commit de referência:** `e9638c1` (push 31/jul/2026) · correções P0 **H-JUL-01/02/03** em dev (2026-08-03, commit pendente de tag após push)  
**Reteste pós-deploy:** [rodada-pos-deploy-jul2026.md](rodada-pos-deploy-jul2026.md) — **NO-GO** (31/jul tarde); reteste RT-SEC + RT-ASS pendente após deploy 2026-08-03

---

## Resumo executivo

| # | Tema | Status dev | Reteste 31/jul | Commit |
|---|------|------------|----------------|--------|
| 1 | Gestor setorial — visibilidade pós-assinatura (fechar nó) | Entregue | **Falhou** (404) — H-JUL-04 | `e9638c1` |
| 2 | Duplicidade tramitação no despacho final | Entregue | **Falhou** — H-JUL-12, H-JUL-18 | `e9638c1` |
| 3 | Placeholders nos formulários de tramitação | Entregue | **Falhou** — H-JUL-08, H-JUL-09 | `e9638c1` |
| 4 | Despacho Super OS — só líder + integração seguidoras | Entregue (fase 1) | **Falhou** — H-JUL-05, H-JUL-06 | `e9638c1` |
| 5 | Despacho inicial — sem validação gestor | Entregue | **Corrigido dev** — H-JUL-02 *(reteste)* | 2026-08-03 |
| 6 | Despacho final — operador assina; gestor valida depois | Entregue | **Corrigido dev** — H-JUL-03 *(reteste)*; H-JUL-10/11 pendentes | 2026-08-03 |
| 7 | Indicações — vereadores vinculados acompanham processo | Parcial | **Falhou** — só notificação OK (H-JUL-07) | `e9638c1` |
| 8 | Copiloto / mapa — CEP após ajuste de pin | Entregue | **Parcial** — intermitente + busca logradouro (H-JUL-13/14) | `e9638c1` |

**Extras no mesmo pacote:** mapa analítico alinhado aos pinos — **não retestado** nesta rodada.

**Bloqueante adicional (janela CRUD 60 s):** Protocolo edita/desfaz despacho de Secretaria — **H-JUL-01** — **corrigido dev 2026-08-03** *(reteste pendente)*.

---

## 1. Gestor setorial — visibilidade após notificação de assinatura ✅

| Campo | Valor |
|-------|-------|
| **Sintoma** | Gestor setorial recebia notificação para validar tramitação (fechar nó scatter), mas a demanda não aparecia na fila nem no detalhe |
| **Causa** | Assimetria entre quem recebe `ASSINATURA_PENDENTE` e regras de `usuario_pode_acessar_demanda` / fila operacional |
| **Correção** | `demanda_visibilidade.py`: grant explícito via `demanda_ids_com_validacao_gestor_pendente` (usa `usuario_pode_validar_assinatura_gestor`) |
| **Validar** | Gestor setorial: notificação → abrir demanda → validar em Assinaturas pendentes |
| **Reteste 31/jul** | **Falhou** — 404 após assinatura operador *(H-JUL-04)* |
| **Correção 2026-08-03** | `aplicar_escopo_perfil`: demandas com `AssinaturaValidacaoGestor` pendente entram no queryset do gestor setorial (alinha retrieve com `usuario_pode_acessar_demanda`) |
| **Reteste** | Pendente em homologação (RT-ASS) |

---

## 2. Duplicidade no despacho final (ex. demanda 2004) ✅

| Campo | Valor |
|-------|-------|
| **Sintoma** | Duas entradas na timeline após conclusão (origem Protocolo, ação automatizada) |
| **Causa** | `CONCLUSAO_FINAL` + `ENCERRAMENTO_DEVOLUTIVA` automático exibidos em sequência |
| **Correção** | `operacional_estado_service.montar_timeline_operacional`: ocultar `ENCERRAMENTO_DEVOLUTIVA` quando já existe `CONCLUSAO_FINAL` |
| **Validar** | Demanda com fluxo operacional finalizado — uma conclusão final visível na timeline |
| **Reteste 31/jul** | **Falhou** — scatter-gather duplicado; placeholders literais na timeline (H-JUL-12) |

---

## 3. Biblioteca de placeholders na tramitação ✅

| Campo | Valor |
|-------|-------|
| **Sintoma** | Chips de placeholder e modelos de texto não atualizavam o editor Quill |
| **Causa** | PrimeVue `Editor` não sincroniza `modelValue` programático |
| **Correção** | `DescricaoTramitacaoEditor.vue`: remount via `editorEpoch` após inserir placeholder ou aplicar modelo |
| **Validar** | Formulário de tramitação → clicar placeholder → texto aparece; aplicar modelo → corpo substituído |
| **Reteste 31/jul** | **Falhou** — editor vazio ao inserir chip; publicação mantém `{{...}}` (H-JUL-08, H-JUL-09) |
| **Nota operador** | Toolbar Quill (Heading, B/I/U) visível = editor carregado; corpo escuro/vazio = bug de sync |

---

## 4. Despacho final Super OS ✅ (fase 1)

| Campo | Valor |
|-------|-------|
| **Sintoma** | Despacho em lote listava/protocolava todas as demandas do cluster |
| **Correção** | `cluster_despacho_service.py`: protocola **apenas o líder**; seguidoras integradas via `ClusterAderenciaService.integrar_seguidoras_sem_protocolo_ao_operacional` |
| **Pendente (fase 2)** | Despacho personalizado com dados por demanda (ex. nome do solicitante) — requer evolução de template |
| **Validar** | Super OS: só líder na fila Protocolo; seguidoras espelhadas ao processo líder |
| **Reteste 31/jul** | **Falhou** — fila lista todas; seguidora com 2 despachos iniciais; detalhe cluster HTML cru e metadados da última vinculada (H-JUL-05, H-JUL-06, H-JUL-15, H-JUL-16) |
| **Correção 2026-08-03 (H-JUL-05)** | `cluster_service.filtrar_listagem_apenas_lideres` na fila `protocolados`; hub e frontend alinhados |
| **Correção 2026-08-03 (H-JUL-06)** | Timeline deduplica DESPACHO do líder; `mesclarTramitacoesProtocoloEditaveis` não reintroduz espelho na seguidora; integração única no despacho Super OS |
| **Reteste** | Pendente em homologação (RT-SOS) |

---

## 5. Despacho inicial — sem assinatura do gestor ✅

| Campo | Valor |
|-------|-------|
| **Regra acordada** | Apenas operador Protocolo assina; despacho executado na hora |
| **Correção** | `registrar_assinaturas_despacho_inicial`: execução imediata via `DemandaDespachoService.despachar_multiplo`; preview com `requer_validacao_gestor: false` |
| **Validar** | Despacho manual: operador assina → demanda protocolada sem fila de gestor SGAC |
| **Reteste 31/jul** | **Parcial** — assinatura OK; **Desfazer** não revertia nó *(H-JUL-02)* |
| **Correção 2026-08-03** | `tramitacao_janela_edicao_service._reverter_despacho_inicial_protocolo`: remove nós bootstrap, pernas, assinaturas e cancela notificações pós-despacho |
| **Reteste** | Pendente em homologação (RT-SEC) |

---

## 6. Despacho final — assinatura assíncrona ✅

| Campo | Valor |
|-------|-------|
| **Regra acordada** | Operador Protocolo assina → tramitação pendente → gestor SGAC valida em fila separada |
| **Correção** | Frontend: `modoPainelAssinaturaProtocolo` → `operador_apenas`; backend: `registrar_assinaturas_despacho_devolutiva` com validação gestor assíncrona (padrão conclusão final); executor `_executar_despacho_devolutiva` |
| **Validar** | Lista e detalhe: operador assina → pendente gestor → validação em Assinaturas pendentes |
| **Reteste 31/jul** | **Falhou** — modal ainda permitia operador assinar como gestor *(H-JUL-03)*; pendente visível a todos na timeline (H-JUL-10); gestor protocolo erro 400 na conclusão (H-JUL-11) |
| **Correção 2026-08-03** | Backend devolve `operador_apenas`; devolutiva não executa imediatamente — `aguardando_validacao_gestor: true` até gestor SGAC validar |
| **Reteste** | Pendente em homologação (RT-ASS) |

---

## 7. Indicações — vereadores vinculados ⚠️ Parcial

| Campo | Valor |
|-------|-------|
| **Regra acordada** | Vereador(es) vinculado(s) e usuário Câmara acompanham: acesso, notificações, dashboard/mapa |
| **Já existia** | `DemandaVereadorVinculo`, escopo VEREADOR, `filtro_demandas_por_vereador`, `interessados_legislativos` |
| **Ajuste neste pacote** | `notificar_despacho_inicial_super_os` passa a usar `interessados_legislativos` (Câmara + vereadores vinculados) |
| **Validar** | Indicação protocolada: vereador vinculado vê demanda, recebe notificação de andamento, aparece no dashboard/mapa |
| **Reteste 31/jul** | **Falhou** — notificação OK; lista, dashboard e mapa **sem** indicação (H-JUL-07) |
| **Correção 2026-08-03** | `DemandaFilter.filter_autor` e dashboard usam `filtro_demandas_por_vereador` (ofícios próprios + indicações vinculadas) |
| **Reteste** | Pendente em homologação (RT-IND) |

---

## 8. Copiloto — CEP após ajuste no mapa ✅

| Campo | Valor |
|-------|-------|
| **Sintoma** | Mover pin no mapa não atualizava CEP/logradouro no formulário |
| **Causa** | Cache local `enderecoFormCopiloto` desatualizado após reverse geocode |
| **Correção** | `CopilotoView.ajustarMapaCopiloto`: sincroniza formulário com resposta da API; GPS avança fluxo para anexos (`chatbot_service` + frontend) |
| **Validar** | Copiloto: ajustar pin → CEP/endereço atualizam; GPS → etapa anexos |
| **Reteste 31/jul** | **Parcial** — atualização intermitente; busca logradouro na revisão não aceita espaço (H-JUL-13, H-JUL-14) |

---

## Mapa operacional — analítico alinhado aos pinos ✅

| Campo | Valor |
|-------|-------|
| **Sintoma** | Painel analítico incluía demandas sem geocoordenadas («Sem bairro») |
| **Correção** | Agregação somente a partir de `serializar_locations`; frontend calcula analítico da mesma lista dos pinos |
| **Validar** | Total analítico = quantidade de pinos no mapa |
| **Reteste 31/jul** | Não executado nesta rodada |
| **Backlog UX** | Filtro «demandas atrasadas» no mapa operacional (H-JUL-19) |

---

## Evidências de execução

```bash
cd backend && python manage.py test core.tests.test_assinatura_validacao_gestor core.tests.test_geocoding_fase2 core.tests.test_mapa_demanda_service --settings=config.settings_test
cd frontend && npm run build
```

---

## Referências técnicas

| Área | Arquivos principais |
|------|---------------------|
| Visibilidade gestor | `backend/core/services/demanda_visibilidade.py` |
| Assinaturas | `backend/core/services/assinatura_eletronica_service.py` |
| Timeline | `backend/core/services/operacional_estado_service.py` |
| Super OS | `backend/core/services/cluster_despacho_service.py` |
| Placeholders | `frontend/src/components/tramitacao/DescricaoTramitacaoEditor.vue` |
| Assinatura UI | `frontend/src/constants/assinaturaEletronica.js`, `DemandasView.vue` |
| Copiloto geo | `frontend/src/views/CopilotoView.vue`, `backend/core/services/chatbot_service.py` |
| Mapa | `frontend/src/views/MapaCalorView.vue`, `backend/core/services/mapa_demanda_service.py` |
