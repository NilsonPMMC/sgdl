# Reunião de trabalho — homologação SGDL (jun/2026)

> **Realizada:** 2026-06-11 · **Registro H2:** [homologacao-e2e-registro.md](homologacao-e2e-registro.md)

---

## Resultado

Homologação operacional com operadores. Identificados **5 apontamentos** para ajuste antes do piloto.

**Acordado com o time:**
- **+1 semana** de desenvolvimento nos ajustes abaixo
- **Testes remotos** na aplicação (homologação) durante a semana
- Meta piloto mantida: **2ª quinzena jun/2026** — 2 gabinetes + Protocolo + Gestão (+ secretaria zeladoria, a confirmar)

**Gate piloto:** **GO condicional** — A1–A5 OK; Onda B em andamento.

---

## Apontamentos registrados

### 1. Copiloto × FAQ (A1)

**Achado:** Copiloto **não está calibrado** com os dados da FAQ cadastrada — respostas/orientações desalinhadas ao banco.

**Severidade:** incômodo (qualidade do piloto)

**Ação:** Revisar integração FAQ → Groq (competência, recusa, orientações por categoria); validar com casos reais da reunião.

**Status 2026-06-10:** **OK** — validado em homologação (A1).

---

### 2. Visibilidade Vereador — regra P8 (A2)

**Achado:** Regra de visualização para perfil **Vereador** **não está ativa** — vereador vê **todo o processo** operacional interno.

**Referência documentada:** [onda2-polimento-ux.md](../especificacoes/onda2-polimento-ux.md) — **P8** (timeline filtrada; marcos + conclusão).

**Severidade:** bloqueante

**Ação:** Reativar filtro backend (`TramitacaoVisibilidade`) + frontend (`DemandaDetailView`); testes `test_tramitacao_visibilidade_vereador`.

---

### 3. Assinatura eletrônica — chefia órgão/setor na conclusão (A3)

**Achado:** Necessário implantar **assinatura eletrônica da chefia do órgão/setor** na **conclusão** do processo (secretaria).

**Severidade:** bloqueante (piloto)

**Ação:** Estender modelo `AssinaturaEletronica` / fluxo de conclusão e devolutiva protocolo com declaração + hash + responsável UA.

**Status 2026-06-13:** **[~] Implementado em dev** — diálogo de assinatura na conclusão (`DemandaDetailView`); prévia + declaração «ASSINO A CONCLUSAO OPERACIONAL»; validação de chefia UA no backend. **Aguarda validação remota** pelos operadores de Secretaria.

---

### 4. Assinatura eletrônica — despachos Protocolo (A4)

**Achado:** Necessário implantar assinatura eletrônica no:
- **Despacho inicial** (protocolo ao despachar)
- **Despacho final** (entrega/devolutiva ao vereador)

Incluir assinatura do **gestor do protocolo** (secretário do órgão), além do operador que executa o despacho.

**Severidade:** bloqueante (piloto)

**Ação:** Cadeia de assinaturas no `despachar` e `despachar-devolutiva`; UI declaração + trilha auditável.

**Status 2026-06-12:** **Implementado em dev** — UI em `DemandaDetailView` e `DemandasView`; prévia persistida no banco (`AssinaturaPendingAcao`, mig. `0063`). Correções de homologação: serializer `assinaturas`, lista sem fluxo de prévia. **Aguarda validação remota** pelos operadores de Protocolo.

---

### 5. Isolamento Secretaria — CRÍTICO (A5)

**Achado:** Usuários vinculados a **uma secretaria** estão vendo processos de **todas** as secretarias.

**Severidade:** **bloqueante / crítico** (segurança e confidencialidade)

**Ação:** Revisão urgente RBAC — queryset `Demanda`, mapa, relatórios, clusters; garantir filtro por `sinapse_orgao_id` e UA conforme [modulo-usuarios-perfis.md](../especificacoes/modulo-usuarios-perfis.md).

---

## Priorização sugerida (dev)

| Ordem | ID | Tema |
|-------|-----|------|
| P0 | **A5** | Isolamento Secretaria |
| P0 | **A2** | Visibilidade Vereador (P8) |
| P1 | **A4** | Assinaturas Protocolo (inicial + final + gestor) |
| P1 | **A3** | Assinatura chefia setor na conclusão |
| P2 | **A1** | Copiloto calibrado com FAQ |

---

## Rodada pós-GO — 2026-06-13

Novos apontamentos (H2-09…H2-17) → **Onda B** (B1–B9). Detalhe: [piloto-apontamentos-jun2026.md](piloto-apontamentos-jun2026.md).

**Gate:** mantido **GO condicional** — nenhum bloqueante novo; priorizar B4, B5, B7, B8 antes do piloto.

---

## Encerramento dev — 2026-06-12 (histórico)

| ID | Entrega | Status |
|----|---------|--------|
| **A5** | RBAC Secretaria (isolamento órgão/UA) | **OK** |
| **A2** | Visibilidade Vereador (P8) | **OK** |
| **A4** | Assinaturas Protocolo (despacho inicial + devolutiva + gestor) | **OK** |
| **A3** | Assinatura chefia UA na conclusão (**Órgão/Secretaria**) | **OK** |
| **A1** | Copiloto × FAQ | **OK** |

**Gate piloto:** **GO** — piloto operacional previsto para 2ª quinzena jun/2026.

---

## Referências

- [homologacao-e2e-registro.md](homologacao-e2e-registro.md) — H2-04 … H2-17
- [piloto-apontamentos-jun2026.md](piloto-apontamentos-jun2026.md) — Onda B (B1–B9)
- [ROADMAP.md](../ROADMAP.md) — Onda Ajustes + Onda B
- [ROADMAP_PRODUTO.md](../ROADMAP_PRODUTO.md) — fases 3.5 / 4.6 / 2.2

**Última atualização:** 2026-06-13 — Onda B registrada; gate **GO condicional**.
