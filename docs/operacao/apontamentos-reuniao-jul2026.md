# Apontamentos — reunião homologação (jul/2026)

> **Contexto:** reunião operacional de homologação (31/jul/2026) — correções priorizadas antes do piloto contínuo.  
> **Índice:** [ROADMAP-PROXIMAS-TAREFAS-JUL2026.md](../ROADMAP-PROXIMAS-TAREFAS-JUL2026.md) · [piloto-apontamentos-jun2026.md](piloto-apontamentos-jun2026.md)

**Data do registro:** 2026-07-31  
**Ambiente:** homologação operacional  
**Commit de referência:** ver `git log` após push deste pacote

---

## Resumo executivo

| # | Tema | Status | Commit |
|---|------|--------|--------|
| 1 | Gestor setorial — visibilidade pós-assinatura (fechar nó) | **Concluído** | neste pacote |
| 2 | Duplicidade tramitação no despacho final | **Concluído** | neste pacote |
| 3 | Placeholders nos formulários de tramitação | **Concluído** | neste pacote |
| 4 | Despacho Super OS — só líder + integração seguidoras | **Concluído** (fase 1) | neste pacote |
| 5 | Despacho inicial — sem validação gestor | **Concluído** | neste pacote |
| 6 | Despacho final — operador assina; gestor valida depois | **Concluído** | neste pacote |
| 7 | Indicações — vereadores vinculados acompanham processo | **Parcial** | neste pacote |
| 8 | Copiloto / mapa — CEP após ajuste de pin | **Concluído** | neste pacote |

**Extras no mesmo pacote (sessão anterior):** analítico do mapa operacional alinhado aos pinos georreferenciados (`MapaCalorView` + `mapa_demanda_service`).

---

## 1. Gestor setorial — visibilidade após notificação de assinatura ✅

| Campo | Valor |
|-------|-------|
| **Sintoma** | Gestor setorial recebia notificação para validar tramitação (fechar nó scatter), mas a demanda não aparecia na fila nem no detalhe |
| **Causa** | Assimetria entre quem recebe `ASSINATURA_PENDENTE` e regras de `usuario_pode_acessar_demanda` / fila operacional |
| **Correção** | `demanda_visibilidade.py`: grant explícito via `demanda_ids_com_validacao_gestor_pendente` (usa `usuario_pode_validar_assinatura_gestor`) |
| **Validar** | Gestor setorial: notificação → abrir demanda → validar em Assinaturas pendentes |

---

## 2. Duplicidade no despacho final (ex. demanda 2004) ✅

| Campo | Valor |
|-------|-------|
| **Sintoma** | Duas entradas na timeline após conclusão (origem Protocolo, ação automatizada) |
| **Causa** | `CONCLUSAO_FINAL` + `ENCERRAMENTO_DEVOLUTIVA` automático exibidos em sequência |
| **Correção** | `operacional_estado_service.montar_timeline_operacional`: ocultar `ENCERRAMENTO_DEVOLUTIVA` quando já existe `CONCLUSAO_FINAL` |
| **Validar** | Demanda com fluxo operacional finalizado — uma conclusão final visível na timeline |

---

## 3. Biblioteca de placeholders na tramitação ✅

| Campo | Valor |
|-------|-------|
| **Sintoma** | Chips de placeholder e modelos de texto não atualizavam o editor Quill |
| **Causa** | PrimeVue `Editor` não sincroniza `modelValue` programático |
| **Correção** | `DescricaoTramitacaoEditor.vue`: remount via `editorEpoch` após inserir placeholder ou aplicar modelo |
| **Validar** | Formulário de tramitação → clicar placeholder → texto aparece; aplicar modelo → corpo substituído |

---

## 4. Despacho final Super OS ✅ (fase 1)

| Campo | Valor |
|-------|-------|
| **Sintoma** | Despacho em lote listava/protocolava todas as demandas do cluster |
| **Correção** | `cluster_despacho_service.py`: protocola **apenas o líder**; seguidoras integradas via `ClusterAderenciaService.integrar_seguidoras_sem_protocolo_ao_operacional` |
| **Pendente (fase 2)** | Despacho personalizado com dados por demanda (ex. nome do solicitante) — requer evolução de template |
| **Validar** | Super OS: só líder na fila Protocolo; seguidoras espelhadas ao processo líder |

---

## 5. Despacho inicial — sem assinatura do gestor ✅

| Campo | Valor |
|-------|-------|
| **Regra acordada** | Apenas operador Protocolo assina; despacho executado na hora |
| **Correção** | `registrar_assinaturas_despacho_inicial`: execução imediata via `DemandaDespachoService.despachar_multiplo`; preview com `requer_validacao_gestor: false` |
| **Validar** | Despacho manual: operador assina → demanda protocolada sem fila de gestor SGAC |

---

## 6. Despacho final — assinatura assíncrona ✅

| Campo | Valor |
|-------|-------|
| **Regra acordada** | Operador Protocolo assina → tramitação pendente → gestor SGAC valida em fila separada |
| **Correção** | Frontend: `modoPainelAssinaturaProtocolo` → `operador_apenas` para devolutiva/conclusão; `DemandasView` usa `conclusaoFinalOperacional` quando `fluxo_roteamento`; `buildDevolutivaPayload` com modo operador |
| **Validar** | Lista e detalhe: operador assina → pendente gestor → validação em Assinaturas pendentes |

---

## 7. Indicações — vereadores vinculados ⚠️ Parcial

| Campo | Valor |
|-------|-------|
| **Regra acordada** | Vereador(es) vinculado(s) e usuário Câmara acompanham: acesso, notificações, dashboard/mapa |
| **Já existia** | `DemandaVereadorVinculo`, escopo VEREADOR, `filtro_demandas_por_vereador`, `interessados_legislativos` |
| **Ajuste neste pacote** | `notificar_despacho_inicial_super_os` passa a usar `interessados_legislativos` (Câmara + vereadores vinculados) |
| **Validar** | Indicação protocolada: vereador vinculado vê demanda, recebe notificação de andamento, aparece no dashboard/mapa |
| **Risco** | Vínculos não materializados no Copiloto → vereador não acompanha; conferir `sincronizar_vinculos_vereador` na criação |

---

## 8. Copiloto — CEP após ajuste no mapa ✅

| Campo | Valor |
|-------|-------|
| **Sintoma** | Mover pin no mapa não atualizava CEP/logradouro no formulário |
| **Causa** | Cache local `enderecoFormCopiloto` desatualizado após reverse geocode |
| **Correção** | `CopilotoView.ajustarMapaCopiloto`: sincroniza formulário com resposta da API; GPS avança fluxo para anexos (`chatbot_service` + frontend) |
| **Validar** | Copiloto: ajustar pin → CEP/endereço atualizam; GPS → etapa anexos |

---

## Mapa operacional — analítico alinhado aos pinos ✅

| Campo | Valor |
|-------|-------|
| **Sintoma** | Painel analítico incluía demandas sem geocoordenadas («Sem bairro») |
| **Correção** | Agregação somente a partir de `serializar_locations`; frontend calcula analítico da mesma lista dos pinos |
| **Validar** | Total analítico = quantidade de pinos no mapa |

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
