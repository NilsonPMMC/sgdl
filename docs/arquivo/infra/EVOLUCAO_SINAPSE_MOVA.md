# Evolucao SGDL: Sinapse + Referencia MOVA

## Contexto

Objetivo da evolucao: apos estabilizacao para homologacao, elevar o SGDL para um modelo interoperavel, orientado a servicos e com melhor experiencia digital.

Eixos:
- Integracao com Sinapse (barramento de dados interoperantes), com prioridade para Carta de Servicos.
- Evolucao de UX/UI inspirada no fluxo conversacional do MOVA.
- Introducao progressiva de IA aplicada a triagem, classificacao e apoio operacional.

## Analise comparativa (SGDL x MOVA)

### 1) UX/UI e fluxo do usuario

SGDL atual:
- Fluxo orientado a telas administrativas tradicionais.
- Boa cobertura funcional por perfil, mas menos guiado para o cidadao.
- Baixa contextualizacao durante preenchimento (menos assistencia passo a passo).

MOVA (referencia observada):
- Fluxo em etapas ("wizard/chat") com microdecisoes.
- Confirmacao de analise antes do envio (`StepAnalysis`), reduzindo erro de classificacao.
- Cross-sell de demandas multiplas identificadas no mesmo relato.
- Estados de sucesso e continuidade bem definidos.

Recomendacao para SGDL:
- Aplicar padrao de fluxo guiado para abertura de demanda (especialmente para perfis externos).
- Introduzir etapa de "confirmacao de entendimento" antes de protocolar.
- Manter modo admin atual, mas criar jornada simplificada para abertura e acompanhamento.

### 2) IA e inteligencia operacional

SGDL atual:
- Regras de negocio e indicadores consolidados.
- Sem camada LLM estruturada no fluxo de entrada.

MOVA (referencia observada):
- Servico LLM robusto (`intelligence/services.py`) com:
  - parse resiliente de JSON;
  - classificacao por intent/categoria/urgencia;
  - suporte a multiplas demandas no mesmo texto;
  - trilha para deduplicacao semantica + geografica.
- Endpoint de pre-analise (`analyze_draft`) para validar com o usuario antes do envio.

Recomendacao para SGDL:
- Fase 2.1: adicionar pre-analise nao bloqueante no fluxo de abertura (categoria sugerida + urgencia + resumo).
- Fase 2.2: deduplicacao semantica gradual para demandas repetidas.
- Fase 2.3: usar IA para apoio, nunca para decisao final automatica sem auditoria humana.

### 3) Interoperabilidade com Sinapse (Carta de Servicos)

Diretriz:
- Carta de Servicos deve ser tratada como "fonte mestra interoperavel" para:
  - nomenclatura oficial do servico;
  - orgao responsavel;
  - SLA/prazo;
  - documentos e requisitos.

Arquitetura recomendada no SGDL:
1. Camada `integrations/sinapse_client.py` (isolada do dominio).
2. Job de sincronizacao (full + incremental) com rastreabilidade:
   - `sinapse_service_id`, `version`, `last_sync_at`, `hash_payload`.
3. Tabela de mapeamento local:
   - `ServicoSinapseMap(servico_local_id, sinapse_id, status_sync, divergencia)`.
4. Fallback:
   - se Sinapse indisponivel, manter leitura local em cache com alerta operacional.

Contrato minimo de dados da Carta de Servicos:
- `service_id`
- `service_name`
- `provider_secretariat`
- `sla_days`
- `required_documents`
- `channels`
- `active`
- `updated_at`

## Riscos e mitigacoes

- Risco: dependencia externa do barramento.
  - Mitigacao: cache local + retries + circuito de contingencia.
- Risco: classificacao incorreta por IA.
  - Mitigacao: etapa de confirmacao humana + log/auditoria das sugestoes.
- Risco: divergencia entre servico local e carta oficial.
  - Mitigacao: rotina de reconciliacao e painel de inconsistencias.

## Roadmap sugerido (pos-homologacao)

### Sprint A - Base de interoperabilidade
- Criar cliente Sinapse e modelo de mapeamento.
- Sincronizar Carta de Servicos (somente leitura).
- Exibir no SGDL origem e versao do servico.

### Sprint B - UX guiado
- Novo fluxo de abertura em etapas (beta controlado).
- Confirmacao de entendimento antes de enviar.
- Melhorias de mensagens, feedback e estados de erro.

### Sprint C - IA assistiva
- Endpoint de pre-analise de rascunho.
- Sugestao de categoria/urgencia com aceite humano.
- Telemetria de acerto da IA (precisao operacional).

## Criterios de pronto da evolucao

- Integracao Sinapse auditavel (logs + versao + fallback).
- Fluxo UX guiado com taxa de conclusao superior ao fluxo atual.
- IA com modo assistivo, sem decisao automatica irreversivel.
- Testes de contrato API (Sinapse) e smoke por perfil atualizados.

## Referencia de roadmap detalhado

- Ver documento tecnico detalhado: `docs/ROADMAP_SGDL_SERVIDOR_APIS_LLM.md`
- Inclui:
  - configuracao de servidor por fase,
  - conexoes com APIs (Sinapse e contratos internos),
  - uso do Kernel compartilhado em `/opt/shared_ai_service/shared_ai_service`,
  - criterios de aceite e gates de qualidade.
