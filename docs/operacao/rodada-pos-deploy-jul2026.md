# Rodada pós-deploy — homologação jul/2026

> **Data dos testes:** 31/jul/2026 (tarde)  
> **Ambiente:** https://sgdl.mogidascruzes.sp.gov.br  
> **Deploy validado:** pacote commit `e9638c1` (correções reunião 31/jul)  
> **Formato H2:** `tela · perfil · esperado · obtido · severidade`  
> **Índice:** [apontamentos-reuniao-jul2026.md](apontamentos-reuniao-jul2026.md) · [homologacao-e2e-registro.md](homologacao-e2e-registro.md)

---

## Resultado da rodada

| Gate | Resultado | Motivo |
|------|-----------|--------|
| **Piloto contínuo** | **NO-GO** | 2 bloqueantes de segurança/RBAC + regressões em assinaturas e Super OS |
| **Reteste mínimo** | Pendente | Após correção P0 — ver § Plano próximo dia útil |

**Participação:** operador(es) homologação (Protocolo, Secretaria, Gestor, Vereador).  
**Evidências visuais:** screenshots anexados na sessão de teste (despacho inicial, editor placeholders, scatter duplicado, Super OS, cluster, modal devolutiva, status final).

---

## Matriz de validação — pacote jul/2026

| Item | Tema | Resultado rodada | ID achados |
|------|------|------------------|------------|
| 1 | Gestor setorial — visibilidade pós-assinatura | **Falhou** | H-JUL-04 |
| 2 | Duplicidade timeline despacho final | **Falhou** | H-JUL-12, H-JUL-18 |
| 3 | Placeholders tramitação | **Falhou** | H-JUL-08, H-JUL-09 |
| 4 | Super OS — só líder + integração seguidoras | **Falhou** | H-JUL-05, H-JUL-06, H-JUL-15, H-JUL-16, H-JUL-17 |
| 5 | Despacho inicial — sem gestor | **Parcial → corrigido dev** | H-JUL-02 *(reteste pendente)* |
| 6 | Despacho final — operador assina, gestor valida | **Parcial → corrigido dev** | H-JUL-03 *(reteste pendente)*; H-JUL-10, H-JUL-11 |
| 7 | Indicações — vereador vinculado | **Falhou** | H-JUL-07 |
| 8 | Copiloto — CEP após pin | **Parcial** | H-JUL-13, H-JUL-14 |
| — | Mapa analítico = pinos | **Não retestado** | — |
| — | Janela CRUD 60 s (tarefa 1 backlog) | **Corrigido dev** | H-JUL-01, H-JUL-02 *(reteste pendente)* |

---

## Achados H-JUL (detalhado)

### P0 — Bloqueantes

| ID | Registro | Severidade | Área provável |
|----|----------|------------|---------------|
| **H-JUL-01** | DemandaDetailView / timeline · **PROTOCOLO** · após logout Secretaria e login Protocolo, despachos da Secretaria aparecem com **Corrigir/Desfazer** e contador 60s · operador Protocolo **não deveria** ter CRUD em andamento de outro perfil/setor · **bloqueante** | bloqueante | `tramitacao_janela_edicao_service` — **corrigido 2026-08-03** (CRUD restrito ao autor + operador pendente gestor) |
| **H-JUL-02** | Despacho inicial · **PROTOCOLO** · dentro da janela 60s **Desfazer** apaga texto na timeline mas **nó operacional permanece**; notificação já enviada à Secretaria; Secretaria **acessa link** do despacho desfeito · **bloqueante** | bloqueante | `tramitacao_janela_edicao_service` — **corrigido 2026-08-03** (reverte nós bootstrap, pernas, metadados e notificações) |

### P1 — Alta (fluxo crítico)

| ID | Registro | Severidade | Área provável |
|----|----------|------------|---------------|
| **H-JUL-03** | Modal assinatura devolutiva/conclusão · **PROTOCOLO** · ainda exibe checkbox **«ASSINO COMO GESTOR DO PROTOCOLO»** · operador deve assinar **somente por si**; gestor valida depois com login próprio · **bloqueante funcional** | bloqueante | `assinatura_eletronica_service`, `assinatura_etapa_executor_service`, `DemandaDetailView.vue` — **corrigido 2026-08-03** (modo `operador_apenas`; validação gestor assíncrona na devolutiva) |
| **H-JUL-04** | Assinaturas pendentes / link pós-assinatura · **GESTOR SETORIAL (secretaria)** · **404** ao abrir demanda após operador assinar · hipótese: gestor setorial sem acesso à fila **devolutivas** / escopo de demanda · **bloqueante** | bloqueante | `demanda_visibilidade.py` — **corrigido 2026-08-03** (`aplicar_escopo_perfil` inclui `demanda_ids_com_validacao_gestor_pendente` no queryset) |
| **H-JUL-05** | DemandasView / Super OS · **PROTOCOLO** · fila despacho lote ainda lista **todas** demandas vinculadas ao cluster, não só líder (R3.4) · **incômodo → bloqueante operacional** | bloqueante | `cluster_service.filtrar_listagem_por_perfil`, `DemandaViewSet`, `consulta_hub_service` — **corrigido 2026-08-03** |
| **H-JUL-06** | Timeline Super OS · **PROTOCOLO** · demanda **seguidora** recebe **dois** «Despacho inicial (Protocolo)» idênticos; **líder** permanece com um (correto) · evidência: SUPER-2026-0011 · **bloqueante** | bloqueante | `operacional_estado_service.montar_timeline_operacional`, `operacionalEstado.js` (`mesclarTramitacoesProtocoloEditaveis`), `DemandaDetailView.vue`, `cluster_despacho_service` — **corrigido 2026-08-03** (dedupe DESPACHO na timeline; integração única no despacho Super OS) |
| **H-JUL-07** | Indicação · **VEREADOR (autor vinculado)** · notificação recebida **OK** · demanda **não** aparece em `/demandas`, dashboard nem mapa operacional/calor (R5.3, R5.5) · **bloqueante** | bloqueante | `demanda_visibilidade.py`, `filtro_demandas_por_vereador`, `mapa_demanda_service`, materialização `DemandaVereadorVinculo` |

### P2 — Média

| ID | Registro | Severidade | Área provável |
|----|----------|------------|---------------|
| **H-JUL-08** | Timeline despacho · **PROTOCOLO** · texto publicado com placeholders literais `{{demanda_titulo}}`, `{{orgao_destino}}`, `{{protocolo_executivo}}` · deveria substituir na publicação · **incômodo** | incômodo | serviço de substituição de placeholders no backend ou no save da tramitação |
| **H-JUL-09** | DescricaoTramitacaoEditor · **PROTOCOLO/SECRETARIA** · clicar placeholder insere token no model mas **corpo do Editor Quill permanece vazio/escuro** (só `{{autor_nome}}` visível) · remount `editorEpoch` insuficiente · **incômodo** | incômodo | `DescricaoTramitacaoEditor.vue` — sync PrimeVue Editor ↔ v-model |
| **H-JUL-10** | Timeline · **outros perfis** · tramitações **aguardando validação gestor** visíveis na timeline completa após janela 60s do autor · deveriam ficar ocultas ou com badge «pendente aprovação gestor» para não-autores · **incômodo** | incômodo | `operacional_estado_service.montar_timeline_operacional`, flag `aguardando_validacao_gestor` |
| **H-JUL-11** | Conclusão final · **GESTOR DO PROTOCOLO** · POST `/demandas/4134/operacional/conclusao-final/` → **400** «Declaração do operador inválida. Use: ASSINO A CONCLUSAO FINAL» · gestor fechando nó não deveria exigir declaração de operador · **incômodo** | incômodo | `views.py` conclusão final, `assinatura_eletronica_service` |
| **H-JUL-12** | Timeline · **GESTOR SECRETARIA** · operação scatter-gather duplicada (2 cards idênticos «Operação scatter-gather») · placeholders não resolvidos · R4.7 persiste · **incômodo** | incômodo | scatter + timeline + placeholders |
| **H-JUL-13** | CopilotoView / revisão rascunho · **VEREADOR** · mover pin **intermitente** — nem sempre atualiza CEP/logradouro (R1.3) · **incômodo** | incômodo | `CopilotoView.ajustarMapaCopiloto`, race reverse geocode |
| **H-JUL-14** | Revisão rascunho · **VEREADOR** · busca logradouro (≥3 caracteres) **não aceita espaço** como caractere · impede buscas tipo «Rua Barão» · **incômodo** | incômodo | input/máscara logradouro em `CopilotoView.vue` ou `DemandaForm` |

### P3 — Baixa / melhoria

| ID | Registro | Severidade | Área provável |
|----|----------|------------|---------------|
| **H-JUL-15** | ClustersView detalhe · **PROTOCOLO** · descrição exibe **HTML cru** (`<p>`, `&nbsp;`, `&ndash;`) · **cosmético** | cosmético | renderização `v-html` vs strip tags / campo resumo cluster |
| **H-JUL-16** | ClustersView detalhe · **PROTOCOLO** · metadados (bairro, serviço, órgão) refletem **última demanda vinculada**, não a **líder #4134** · **incômodo** | incômodo | API detalhe cluster — usar `demanda_lider_id` |
| **H-JUL-17** | DemandasView · **PROTOCOLO** · Super OS finalizada SUPER-2026-0011: demandas com status secundário divergente («Ofício assinado» vs «Devolutiva assinada») · **incômodo** | incômodo | espelhamento seguidoras / labels status pós-conclusão |
| **H-JUL-18** | Notificações · **VEREADOR** · encerramento Super OS gera **notificações duplicadas** (uma por demanda vinculada) · **incômodo** | incômodo | `notificacao_service` — deduplicar por cluster/demanda líder |
| **H-JUL-19** | MapaCalorView · **PROTOCOLO/SECRETARIA/GESTOR** · solicitar **filtro de demandas atrasadas** no mapa operacional/analítico · **melhoria** | melhoria | backlog UX mapa |
| **H-JUL-20** | DescricaoTramitacaoEditor · **PROTOCOLO** · «não notei Quill carregar» — toolbar Heading/Sans Serif visível = editor ativo; corpo vazio = bug H-JUL-09 · **ok (esclarecimento)** | — | documentação operador |

---

## Cenários de reteste (próximo dia útil)

Marque após deploy da correção P0/P1.

### RT-SEC — Segurança janela CRUD (H-JUL-01, H-JUL-02)

- [x] Secretaria registra andamento → logout → Protocolo abre mesma demanda → **sem** botões Corrigir/Desfazer no andamento alheio *(corrigido 2026-08-03 — retestar em homologação)*
- [x] Protocolo despacho inicial → Desfazer dentro de 60s → nó operacional **revertido**, notificações DESPACHO **removidas** *(corrigido 2026-08-03 — retestar em homologação)*
- [ ] Autor do andamento mantém CRUD apenas na própria tramitação durante 60s

### RT-ASS — Assinaturas (H-JUL-03, H-JUL-04, H-JUL-10, H-JUL-11)

- [x] Operador Protocolo — devolutiva/conclusão: modal **sem** checkbox gestor; só «ASSINO A DEVOLUTIVA» *(corrigido 2026-08-03 — retestar em homologação)*
- [x] Após assinatura operador → Gestor Protocolo valida em Assinaturas pendentes com **login gestor** *(corrigido 2026-08-03 — retestar em homologação)*
- [x] Gestor setorial secretaria: link da notificação abre demanda (**sem 404**) *(corrigido 2026-08-03 — retestar em homologação)*
- [ ] Tramitação pendente gestor: **autor** vê na timeline na janela 60s; **outros** veem oculto ou «pendente aprovação»
- [ ] Gestor Protocolo conclui nó direto → **sem** exigir declaração de operador

### RT-SOS — Super OS (H-JUL-05, H-JUL-06, H-JUL-15–17)

- [x] `/clusters` despacho Super OS: fila Protocolo mostra **só líder** *(corrigido 2026-08-03 — retestar em homologação)*
- [x] Após despacho: seguidora com **1** despacho inicial espelhado (não 2) *(corrigido 2026-08-03 — retestar em homologação)*
- [ ] Detalhe cluster: descrição legível (sem HTML cru); metadados da **demanda líder**
- [ ] Pós-finalização: status secundário **consistente** entre líder e seguidoras
- [ ] Vereador: **1** notificação de encerramento por Super OS

### RT-IND — Indicações (H-JUL-07)

- [ ] Vereador autor vinculado: demanda em `/demandas`, dashboard e mapa
- [ ] Notificação + listagem alinhadas

### RT-GEO — Copiloto / revisão (H-JUL-13, H-JUL-14)

- [ ] Mover pin 5× seguidas → CEP/logradouro atualizam sempre
- [ ] Busca logradouro aceita espaços («Rua Barão»)

### RT-PLC — Placeholders (H-JUL-08, H-JUL-09)

- [ ] Clicar placeholder → texto visível no editor
- [ ] Publicar despacho → texto **sem** `{{...}}` na timeline

---

## Plano próximo dia útil (prioridade dev)

| Ordem | ID | Entrega | Estimativa | Status dev |
|-------|-----|---------|------------|------------|
| 1 | H-JUL-01 | CRUD 60s restrito ao **autor** (e gestor do mesmo contexto) | 0,5 d | **Concluído 2026-08-03** |
| 2 | H-JUL-02 | Desfazer despacho inicial: reverter nó + cancelar notificações pendentes | 0,5 d | **Concluído 2026-08-03** |
| 3 | H-JUL-03 | Modal devolutiva/conclusão: modo `operador_apenas` sem checkbox gestor | 0,25 d | **Concluído 2026-08-03** |
| 4 | H-JUL-04 | Visibilidade gestor setorial + fila devolutivas / deep link notificação | 0,5 d | **Concluído 2026-08-03** |
| 5 | H-JUL-05, H-JUL-06 | Super OS: fila só líder + eliminar despacho duplicado seguidora | 1 d | **Concluído 2026-08-03** |
| 6 | H-JUL-07 | Indicações: listagem/dashboard/mapa vereador vinculado | 0,5 d |
| 7 | H-JUL-08, H-JUL-09 | Substituir placeholders na publicação + fix sync Editor | 0,5 d |
| 8 | H-JUL-10, H-JUL-12 | Timeline pendente gestor + dedupe scatter/conclusão | 0,5 d |
| 9 | H-JUL-11 | Conclusão final gestor protocolo sem declaração operador | 0,25 d |
| 10 | H-JUL-13–18 | Geo, cluster UI, status Super OS, notificações | 1 d |

**Meta reteste:** fim do 1º dia útil após deploy P0 (itens 1–4).

---

## Referências técnicas (investigação)

| Achado | Arquivos |
|--------|----------|
| CRUD cross-perfil | `backend/core/services/tramitacao_janela_edicao_service.py` (L100–149) |
| Desfazer / nó | `tramitacao_janela_edicao_service` desfazer, `DemandaDespachoService` |
| Modal assinatura | `frontend/src/views/DemandaDetailView.vue`, `assinatura_eletronica_service.py`, `assinatura_etapa_executor_service.py` |
| Super OS | `backend/core/services/cluster_despacho_service.py`, `operacional_estado_service.py`, `operacionalEstado.js` |
| Vereador indicação | `demanda_visibilidade.py`, `mapa_demanda_service.py` |
| Placeholders | `DescricaoTramitacaoEditor.vue`, serviço textos padrão |
| Timeline | `operacional_estado_service.py` |

---

*Registrado em 2026-07-31 · atualizado 2026-08-03 (correções H-JUL-01/02/03/04/05/06 em dev) · próxima revisão após reteste P0/P1 em homologação.*
