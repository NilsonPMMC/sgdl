# Roteiro E2E no browser — operadores (Gate A1)

> **Ambiente:** homologação operacional · **URL:** https://sgdl.mogidascruzes.sp.gov.br  
> **Registro de achados:** formato H2 em [homologacao-e2e-registro.md](homologacao-e2e-registro.md)  
> **Checklist completo:** [homologacao-go-live.md](homologacao-go-live.md) §5.2–5.6  
> **Referência de encerramento OK:** demanda **2966** (status `FINALIZADO`)

---

## Antes de começar

| Item | Detalhe |
|------|---------|
| Navegador | Chrome ou Edge atualizado; permitir pop-up para preview PDF |
| Geolocalização | Habilitar para o domínio (Copiloto — etapa de endereço) |
| Tempo estimado | 45–60 min (4 blocos) |
| Quem participa | 1 vereador (ou assessor), 1 protocolo, 1 secretaria, 1 gestor |

### Usuários seed (senha `123`)

| Perfil | Login | Onde atua (Órgão › Setor) |
|--------|-------|---------------------------|
| Vereador | `vereador_0_martinsnicole` | Legislativo |
| Protocolo | `protocolo_0` | Secretaria de Governo › SGAC |
| Secretaria | `sec_serviços_0` | Serviços Urbanos › AG, SGG-EPL |
| Gestor | credencial de homologação* | — |

\* O login `admin` do seed local **não autentica** em produção (401). Use a conta de gestor configurada no ambiente ou solicite reset ao time técnico.

### Como registrar achados (H2)

Para cada problema, anote:

```
tela · perfil · esperado · obtido · severidade
```

Severidades: **bloqueante** | **incômodo** | **cosmético**

---

## Bloco 1 — Copiloto → rascunho → preview PDF (Vereador)

**Objetivo:** validar §5.2.1–5.2.3 (itens ainda pendentes no checklist).

### 1.1 Abrir o Copiloto

1. Login como **Vereador**.
2. Menu lateral → **Copiloto** (`/copiloto`).
3. Confirmar tag de estado no topo (ex.: «Coleta de dados»).

### 1.2 Descrever a solicitação

4. No chat, descreva um pedido **concreto com endereço**, por exemplo:
   > «Solicito poda de árvore na Rua Barão de Jaceguai, 100, Centro — árvore inclinada sobre a calçada.»
5. Aguarde resposta do assistente e abra o painel **Contexto** (botão no topo) para inspecionar `demandas_extraidas`.

**Esperado:** pelo menos 1 solicitação extraída; estado avança para «Confirmação Sinapse» ou «Endereço».

### 1.3 Confirmar serviço Sinapse

6. Se houver candidatos na carta, selecione um serviço no dropdown e clique **Confirmar serviço na carta** (ou **Confirmar sugestões**).
7. Alternativa: botão **Confirmar serviço na carta** no painel lateral.

**Esperado:** toast «Serviço confirmado»; serviço com `confirmado: true` no painel Contexto; estado «Endereço» (`COLETA_ENDERECO`).

### 1.4 Geocodificar endereço

8. Informe ou confirme o endereço no chat **ou** use **Usar minha localização** (GPS).
9. Se não houver coordenadas, use **Continuar sem local** apenas se o serviço não exigir mapa.

**Esperado:** `latitude` / `longitude` preenchidos no Contexto (ou observação de fonte de coordenadas).

### 1.5 Gerar rascunho

10. Marque a solicitação para aprovação final (checkbox, se houver mais de uma).
11. Clique **Sim, gerar rascunhos** ou **Finalizar** conforme o diálogo do assistente.
12. Na tela de sucesso, anote o(s) **ID(s)** das demandas criadas.
13. Clique **Revisar rascunhos** → lista `/demandas?status=RASCUNHO`.

**Esperado:** demanda(s) em status `RASCUNHO` com serviço Sinapse vinculado.

### 1.6 Revisar e pré-visualizar PDF

14. Abra a demanda → **Editar rascunho do ofício**.
15. Confira texto, serviço e endereço; salve se alterou algo.
16. Clique **Enviar Oficialmente**.
17. No dialog, aguarde o hash do documento e clique para **abrir o PDF** (nova aba).

**Esperado:** PDF renderiza sem erro 401/500; hash visível; checkbox de assinatura eletrônica habilitada.

> **Não envie** nesta rodada se o objetivo for só validar preview — feche o dialog. Para fluxo completo, marque a declaração e confirme (já validado via comando E2E na demanda 2966).

### Critérios de aceite — Bloco 1

- [ ] Rascunho criado pelo Copiloto com serviço confirmado
- [ ] Endereço/coordenadas registrados
- [ ] Preview PDF abre no dialog «Enviar Oficialmente»

---

## Bloco 2 — Filas Protocolo + Super OS (Protocolo)

**Objetivo:** validar §5.3.1 (visual), §5.5.2–5.5.4 (Super OS).

### 2.1 Filas (já OK via API — confirmar visual)

1. Login como **Protocolo**.
2. Menu → **Demandas** (`/demandas`).
3. Alterne as abas **Protocolados**, **Operacionais**, **Devolutivas**.
4. Confirme que a URL muda (`?fila=protocolados` etc.) e a lista carrega sem banner de erro.

**Esperado:** 3 filas renderizam; mensagem contextual se vazia.

### 2.2 Preparar cenário Super OS (2 demandas, mesmo serviço)

Para formar cluster, são necessárias **≥2 demandas** do **mesmo `sinapse_servico_id`**, com endereços próximos (~300 m) quando o serviço exige local.

**Opção A — duas sessões Copiloto (recomendado):**

5. Como Vereador, crie **demanda A** (serviço ex.: poda/urbanismo — anote o `sinapse_servico_id`).
6. Envie oficialmente → `AGUARDANDO_PROTOCOLO`.
7. Repita com **segundo vereador seed** (se disponível) ou mesma conta com outro endereço próximo → **demanda B**, mesmo serviço.
8. Envie B oficialmente.

**Opção B — usar demandas já existentes** na fila de protocolados com tag «N vinculados» ou serviço igual.

### 2.3 Despachar Super OS

9. Login **Protocolo** → **Super Ordens (clusters)** (`/clusters`).
10. Localize cluster com **≥2 demandas** e autores diferentes (card «Super OS multi-vereador»).
11. Abra o cluster → revise demandas vinculadas.
12. Clique ação de **Despachar Super OS** → selecione secretaria de destino → confirme.

**Esperado:** toast com protocolo `SUPER-AAAA-NNNN`; demandas passam a `PROTOCOLADO`; cluster visível na lista.

### 2.4 Links líder ↔ vinculados

13. Abra detalhe da **demanda líder** (listagem Secretaria ou Protocolo).
14. Verifique links para processos vinculados e protocolo Super OS na coluna/tag.

**Esperado:** navegação entre líder e vinculados sem 404.

### Critérios de aceite — Bloco 2

- [ ] Três filas Protocolo OK visualmente
- [ ] Super OS despachada com protocolo `SUPER-*`
- [ ] Links entre demandas vinculadas no detalhe

---

## Bloco 3 — Secretaria (confirmação visual rápida)

**Objetivo:** reforçar §5.4 (UI) — maior parte já validada via API.

1. Login **Secretaria** (`sec_serviços_0`).
2. **Demandas** → aba **Operacionais**.
3. Ative filtro **Meu setor** (toggle «minha unidade»).
4. Confirme colunas **Setor**, **Parado há**, tag **N vinculados**.
5. Se houver demanda `EM_EXECUCAO` ou Super OS líder, abra e registre andamento tipo **Execução**.

**Esperado:** fila filtrada pelo setor UA; atuação exibida no perfil (`Órgão › Setor`).

---

## Bloco 4 — Gestor: relatórios + reconciliação Sinapse

**Objetivo:** validar §5.6.2–5.6.3 (UI).

### 4.1 Dashboard e relatórios

1. Login com **conta Gestor** de homologação.
2. **Dashboard** (`/`) — confirme cards KPI e gráficos.
3. **Relatórios** (`/relatorios`):
   - Selecione período (últimos 30 dias).
   - Filtre por status «Finalizado».
   - Clique **Buscar Relatórios**.
   - Use **Imprimir** (ícone) para validar layout de exportação.

**Esperado:** gráficos e tabela carregam; impressão abre diálogo do navegador sem erro.

### 4.2 Reconciliação Sinapse

4. Menu → **Reconciliação Sinapse** (`/integracoes/sinapse/reconciliacao`).
5. Confirme card de saúde (nível OK ou ALERT).
6. Filtro «Sem correspondência» → lista carrega.
7. (Opcional) selecione 1 linha + serviço da carta → vincular manualmente — **somente se autorizado** pelo gestor de dados.

**Esperado:** tabela UNMATCHED visível; perfil Protocolo **não** vê este menu (testar logout/login Protocolo → item ausente).

### Critérios de aceite — Bloco 4

- [ ] Relatórios com filtros + impressão OK
- [ ] Reconciliação Sinapse acessível ao Gestor
- [ ] Protocolo bloqueado na reconciliação (403 / menu oculto)

---

## Encerramento da rodada

1. Consolidar achados H2 em [homologacao-e2e-registro.md](homologacao-e2e-registro.md).
2. Marcar itens concluídos em [homologacao-go-live.md](homologacao-go-live.md) §5.2–5.6.
3. Decisão Gate A1:
   - **GO piloto** — nenhum bloqueante aberto
   - **NO-GO** — listar bloqueantes + responsável + prazo

### Comandos técnicos (apoio — time SGDL)

```bash
# Repetir proxy API (sem browser)
cd /var/www/sgdl/backend
python manage.py validar_e2e_ui_api --demanda-id 2966

# Ciclo legislativo completo (serviços)
python manage.py validar_e2e_homologacao --corrigir-vinculo-secretaria --manter-demanda
```

---

**Versão:** 2026-06-10 · Gate A1 · Onda 1 homologação
