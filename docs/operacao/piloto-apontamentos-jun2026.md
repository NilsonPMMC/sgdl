# Apontamentos pós-GO — rodada operadores (jun/2026)

> **Contexto:** após validação **A1–A5** (gate **GO**, 2026-06-10), nova rodada de testes com operadores reais.  
> **Formato:** `tela · perfil · esperado · obtido · severidade`  
> **Índice:** [homologacao-e2e-registro.md](homologacao-e2e-registro.md) · [ROADMAP.md](../ROADMAP.md)

**Data do registro:** 2026-06-13  
**Ambiente:** homologação operacional

---

## Resumo

| Severidade | Qtd | IDs |
|------------|-----|-----|
| **Incômodo / qualidade piloto** | 4 | H2-09, H2-10, H2-11, H2-12 |
| **Melhoria operacional** | 4 | H2-13, H2-14, H2-15, H2-16 |
| **Cosmético** | 1 | H2-17 |

**Gate piloto:** mantido **GO** — itens da **Onda B** priorizados antes e durante abertura do piloto (2ª quinzena jun/2026).

> **Roteiro guiado pós-deploy:** use o documento mestre [ROTEIRO-HOMOLOGACAO-COMPLETO.md](ROTEIRO-HOMOLOGACAO-COMPLETO.md) — este arquivo registra achados (H2) e critérios; o roteiro completo concentra todas as fases de teste, **achados H3 rodada 1 (jun/2026)** e **rodada 2 (H3-17…H3-28, jun/2026)**.

---

## Perfil Vereador

### H2-09 · Busca de endereço (Copiloto / formulário)

| Campo | Valor |
|-------|-------|
| **Tela** | CopilotoView / DemandaForm — busca de logradouro |
| **Perfil** | VEREADOR |
| **Esperado** | Autocomplete identifica logradouros conhecidos de Mogi das Cruzes (rua, número, bairro) |
| **Obtido** | Usuário **não identifica logradouros** na busca — endereço difícil de localizar |
| **Severidade** | **incômodo** |
| **Backlog** | **B1** |
| **Refs. técnicas** | `backend/core/views_geocoding.py`; componentes de endereço no Copiloto e formulário de demanda |
| **Ação sugerida** | Auditar provedor geocoding (Nominatim/OSM ou equivalente); ampliar normalização (`logradouro`, sem acento, abreviações); fallback manual claro; amostra de 10 endereços reais de MC |
| **Status dev** | **[x] Concluído (2026-06-22)** — Fases 1–3 geocodificação MC: normalização, autocomplete, base local de vias, pin arrastável, persistência `ajuste_mapa`. Doc: [geocodificacao-endereco-mogi.md](../especificacoes/geocodificacao-endereco-mogi.md). Validar amostra 10 endereços reais MC em homologação. |

---

### H2-10 · Data repetida no texto do ofício (rascunho)

| Campo | Valor |
|-------|-------|
| **Tela** | Preview PDF / texto do ofício em rascunho |
| **Perfil** | VEREADOR |
| **Esperado** | Data aparece **uma vez** no corpo ou cabeçalho, conforme layout institucional |
| **Obtido** | Data **repetida no início e no fim** do texto do rascunho |
| **Severidade** | **incômodo** |
| **Backlog** | **B2** |
| **Refs. técnicas** | `backend/core/services/oficio_texto.py`; templates `demanda_oficio.html`, `oficio_lote.html`; `ConfiguracaoOficioView` |
| **Ação sugerida** | Revisar geração do corpo vs. rodapé (`data_emissao`); eliminar duplicata no template ou no serviço de montagem |
| **Status dev** | **[~] Implementado em dev (2026-06-13)** — data só no cabeçalho em `oficio_texto.py`; validar preview PDF em homologação |

---

### H2-11 · Anexos com o mesmo nome

| Campo | Valor |
|-------|-------|
| **Tela** | CopilotoView / DemandaForm — upload de anexos |
| **Perfil** | VEREADOR |
| **Esperado** | Sistema **impede ou alerta** envio de dois arquivos com o **mesmo nome** no mesmo turno/demanda |
| **Obtido** | Permite anexos duplicados por nome — risco de confusão na assinatura/protocolo |
| **Severidade** | **incômodo** |
| **Backlog** | **B3** |
| **Refs. técnicas** | upload Copiloto (`ChatSession` anexos); `DemandaForm`; validação backend nos endpoints de anexo |
| **Ação sugerida** | Validação client + API: rejeitar ou renomear (`arquivo (2).pdf`); mensagem clara ao usuário |
| **Status dev** | **[~] Implementado em dev (2026-06-13)** — API `AnexoSerializer` + Copiloto; alerta em `DemandaForm` e `CopilotoView` |

---

### H2-12 · A2 refinado — timeline genérica «Prefeitura» (P8)

| Campo | Valor |
|-------|-------|
| **Tela** | DemandaDetailView — timeline / tramitações |
| **Perfil** | VEREADOR |
| **Esperado** | Ocultar trânsito operacional interno (**P8**), mas marcos visíveis devem **identificar secretaria e setor** responsáveis (ex.: «Secretaria de Zeladoria — Setor X concluiu o serviço») |
| **Obtido** | Conteúdo operacional foi sanitizado (OK vs. H2-05), porém **tudo aparece como ação da «Prefeitura»** — perde contexto institucional |
| **Severidade** | **incômodo** (refino de **A2** — não reabre bloqueante original) |
| **Backlog** | **B4** |
| **Refs. técnicas** | `tramitacao_visibilidade_service.py` (`username: "Prefeitura"`, textos institucionais genéricos); `frontend/src/constants/tramitacaoVisibilidade.js`; `DemandaDetailView.vue` (rótulo «Prefeitura») |
| **Ação sugerida** | Manter ocultação de DESPACHO/EXECUCAO/etc.; enriquecer marcos visíveis com `orgao_nome` + `unidade_administrativa` quando disponível; não expor nomes de servidores |

**Nota:** A2 original (ocultar tramitações operacionais) permanece **OK**; B4 é evolução de **qualidade da timeline**.

---

## Perfil Protocolo

### H2-13 · Despacho para múltiplas secretarias simultaneamente

| Campo | Valor |
|-------|-------|
| **Tela** | DemandasView / DemandaDetailView — despacho inicial |
| **Perfil** | PROTOCOLO |
| **Esperado** | Possibilidade de encaminhar **uma demanda** para **mais de um órgão + UA** ao mesmo tempo (ex.: Zeladoria + Meio Ambiente) |
| **Obtido** | Despacho atual permite **apenas um destino** (órgão/setor) por vez |
| **Severidade** | **melhoria operacional** (solicitação explícita: **aplicar**) |
| **Backlog** | **B5** |
| **Refs. técnicas** | `demanda_despacho_service.py`; `DemandaDespachoService.despachar()`; UI de despacho em `DemandasView.vue` / `DemandaDetailView.vue` |
| **Ação sugerida** | Modelar despacho múltiplo (N destinos → N tramitações ou Super OS transversal); UX de seleção múltipla; regras de conclusão quando várias secretarias respondem |
| **Status dev** | **[~] Implementado em dev (2026-06-10)** — MultiSelect + `despachar_multiplo()` com desdobramentos `-D2`; validar [roteiro-b5-b8-homologacao.md](roteiro-b5-b8-homologacao.md) |

---

### H2-14 · Identificação de cargos na assinatura

| Campo | Valor |
|-------|-------|
| **Tela** | Diálogo de assinatura — despacho / devolutiva |
| **Perfil** | PROTOCOLO |
| **Esperado** | Além de «assinar como gestor de protocolo», exibir **cargo conforme estrutura da prefeitura** (ex.: chefe de seção, auxiliar de apoio administrativo) |
| **Obtido** | Assinatura funciona, mas **rótulo genérico** — falta identificação formal do cargo |
| **Severidade** | **melhoria operacional** |
| **Backlog** | **B6** |
| **Refs. técnicas** | `Usuario.cargo` (serializer); `AssinaturaEletronicaService`; PDF de assinatura; catálogo RM271698 / vínculo UA |
| **Ação sugerida** | Propagar `cargo` do usuário (ou cargo da UA) para prévia PDF e registro `AssinaturaEletronica`; lista configurável de cargos por perfil/UA |
| **Status dev** | **[~] Implementado em dev (2026-06-13)** — cargo em prévias, gestores, validação pública e painel de assinaturas |

---

### H2-15 · Confirmação visual de despacho assinado

| Campo | Valor |
|-------|-------|
| **Tela** | DemandaDetailView / listagem Protocolo — pós-despacho |
| **Perfil** | PROTOCOLO |
| **Esperado** | Local claro para **confirmar que o despacho foi assinado** (operador + gestor), com data e trilha |
| **Obtido** | Fluxo de assinatura existe (**A4 OK**), mas operador **não localiza facilmente** o status «assinado» após concluir |
| **Severidade** | **melhoria operacional** |
| **Backlog** | **B7** |
| **Refs. técnicas** | `DemandaSerializer.assinaturas`; `AssinaturaEletronica`; timeline tipo DESPACHO (oculta ao vereador, visível ao Protocolo) |
| **Ação sugerida** | Badge «Despacho assinado» no detalhe; painel «Assinaturas» com etapa, signatário, cargo, data; link para validar código |
| **Status dev** | **[~] Implementado em dev (2026-06-13)** — painel «Assinaturas eletrônicas» + badge na listagem Protocolo; validar após despacho A4 em homologação |

---

### H2-16 · Anexos em despachos e respostas ao vereador

| Campo | Valor |
|-------|-------|
| **Tela** | Despacho inicial / devolutiva Protocolo |
| **Perfil** | PROTOCOLO |
| **Esperado** | **Juntar anexos** (PDF, fotos, pareceres) nos despachos e nas respostas encaminhadas ao vereador |
| **Obtido** | Anexos no envio do vereador existem; **despachos e devolutivas sem upload** de documentos complementares |
| **Severidade** | **melhoria operacional** |
| **Backlog** | **B8** |
| **Refs. técnicas** | `Tramitacao` / anexos de tramitação; devolutiva em `devolutiva_protocolo_service.py` |
| **Ação sugerida** | Campo `anexos` no despacho e na devolutiva; exibir no pacote devolutiva do vereador (respeitando P8) |
| **Status dev** | **[~] Implementado em dev (2026-06-10)** — upload multipart + `anexos_devolutiva` no pacote; validar [roteiro-b5-b8-homologacao.md](roteiro-b5-b8-homologacao.md) |

---

### H2-17 · Formatação do histórico de tramitação

| Campo | Valor |
|-------|-------|
| **Tela** | DemandaDetailView — histórico / timeline (Protocolo, Secretaria) |
| **Perfil** | PROTOCOLO (também SECRETARIA) |
| **Esperado** | Textos com **quebras de linha e parágrafos** preservados (pareceres longos legíveis) |
| **Obtido** | Textos **corridos**, sem formatação — leitura confusa |
| **Severidade** | **cosmético** |
| **Backlog** | **B9** |
| **Refs. técnicas** | renderização `descricao` na timeline Vue; possível `white-space: pre-wrap` ou markdown sanitizado |
| **Ação sugerida** | CSS `white-space: pre-line` no componente de descrição; normalizar `\n` na gravação |
| **Status dev** | **[~] Implementado em dev (2026-06-13)** — `pre-line` para texto plano; HTML Quill com parágrafos estilizados |

---

## Plano de ação — Onda B

| Prioridade | ID | Entrega | Severidade | Status |
|------------|-----|---------|------------|--------|
| **P0** | **B4** | A2.1 — Timeline vereador com **secretaria/setor** (não só «Prefeitura») | incômodo | **[~] Implementado em dev (2026-06-13)** — validar em homologação |
| **P1** | **B5** | Despacho **multi-secretaria** (N órgãos + UAs) | melhoria | **[~] Implementado em dev (2026-06-10)** — validar roteiro B5+B8 |
| **P1** | **B7** | Indicador / painel **«despacho assinado»** | melhoria | **[~] Implementado em dev (2026-06-13)** — validar em homologação |
| **P1** | **B8** | **Anexos** em despachos e devolutivas Protocolo | melhoria | **[~] Implementado em dev (2026-06-10)** — validar roteiro B5+B8 |
| **P1** | **B1** | **Geocoding / busca de logradouro** — cobertura MC | incômodo | **[~] Implementado em dev (2026-06-13)** — validar amostra MC em homologação |
| **P2** | **B2** | Corrigir **data duplicada** no ofício rascunho | incômodo | **[~] Implementado em dev (2026-06-13)** — validar preview em homologação |
| **P2** | **B3** | Restringir anexos com **mesmo nome** | incômodo | **[~] Implementado em dev (2026-06-13)** — validar upload Copiloto + formulário |
| **P2** | **B6** | **Cargo** na assinatura (estrutura prefeitura) | melhoria | **[~] Implementado em dev (2026-06-13)** — validar diálogos + PDF em homologação |
| **P3** | **B9** | **Formatação** de textos longos na timeline | cosmético | **[~] Implementado em dev (2026-06-13)** — validar pareceres multilinha |

### Ordem sugerida de desenvolvimento

1. **B4 + B7** — quick wins de UX (timeline + feedback assinatura)  
2. **B1 + B2 + B3** — qualidade Vereador no Copiloto/ofício  
3. **B5 + B8** — evolução Protocolo (escopo maior)  
4. **B6 + B9** — polimento institucional  

### Critérios de pronto (Onda B)

| ID | Critério |
|----|----------|
| B1 | 10 endereços reais MC resolvem na busca; fallback manual documentado |
| B2 | Preview PDF sem data duplicada no corpo+rodapé |
| B3 | API retorna 400 ao repetir nome; UI alerta antes do upload |
| B4 | Timeline vereador exibe órgão/setor nos marcos; teste `test_tramitacao_visibilidade_vereador` estendido |
| B5 | Despacho com ≥2 destinos cria tramitações; secretarias veem só sua fila |
| B6 | PDF e registro de assinatura exibem `cargo` do signatário |
| B7 | Badge/painel visível ao Protocolo após dupla assinatura A4 |
| B8 | Upload em despacho/devolutiva; anexo no pacote devolutiva |
| B9 | Parecer multilinha legível na timeline Protocolo/Secretaria |

---

## Referências

- [reuniao-trabalho-jun2026.md](reuniao-trabalho-jun2026.md) — A1–A5  
- [especificacoes/onda2-polimento-ux.md](../especificacoes/onda2-polimento-ux.md) — P8 original  
- [modulo-usuarios-perfis.md](../especificacoes/modulo-usuarios-perfis.md) — cargos e vínculos UA  

**Última atualização:** 2026-06-10 (B5 + B8 em dev; roteiro mestre [ROTEIRO-HOMOLOGACAO-COMPLETO.md](ROTEIRO-HOMOLOGACAO-COMPLETO.md))
