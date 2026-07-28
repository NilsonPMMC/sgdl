# Corpus legado — aprendizado (não operacional)

Base: `docs/bd-legado-demandas-vereadores.csv` (~10k pedidos / 17 meses).

## O que é preservado

O corpus **não substitui** nada do SGDL atual:

| Componente | Preservado |
|------------|------------|
| Fluxo Copiloto (Agente → Sinapse → tendência) | Sim |
| Confirmação humana de serviço | Sim |
| Tendências vivas (`Tendencia` incremental) | Sim |
| Ouvidoria, duplicidade, FAQ | Sim |
| Demandas / protocolo / tramitação | Sim |

O legado alimenta uma **camada paralela de leitura** (JSON + API), sem gravar `Demanda` histórica.

## Geração do relatório

```bash
cd /var/www/sgdl/backend
python manage.py analisar_corpus_legado
```

Saída: `docs/insights/corpus-legado.json` (versionável, checksum do CSV).

## Flags (settings / .env)

| Variável | Padrão (homologação) | Efeito |
|----------|----------------------|--------|
| `CORPUS_LEGADO_ENABLED` | `True` | APIs e leitura do JSON |
| `CORPUS_LEGADO_HINTS_COPILOTO_ENABLED` | `True` | Hints pós-triagem quando score Sinapse baixo |
| `CORPUS_LEGADO_DEPARA_PATH` | `docs/insights/depara-legado-sinapse.json` | De-para serviço legado → Sinapse |

Com hints desligados, o Copiloto só recebe `corpus_atalhos_top_trends` (atalhos frequentes) — **sem alterar triagem**.

## De-para legado → Sinapse

Arquivo curado: `docs/insights/depara-legado-sinapse.json` (revisão Protocolo).

```bash
# Rascunho automático (revisar antes de usar)
python manage.py gerar_depara_legado_sinapse --forcar
```

O de-para enriquece `corpus_hints_historico` com `titulo_sinapse_historico` — **não** preenche `sinapse_servico_id` no rascunho automaticamente.

## APIs (read-only)

- `GET /api/v1/corpus-legado/top-trends/`
- `GET /api/v1/corpus-legado/top-setores/`
- `GET /api/v1/corpus-legado/atalhos-copiloto/`
- `GET /api/v1/corpus-legado/sugerir/?q=...` (≥ 8 caracteres)

## Próximas evoluções (sem quebrar o atual)

1. ~~UI: chips de atalho no Copiloto~~ (implementado)
2. ~~De-para serviço legado → Sinapse + hints pós-triagem~~ (Fase 1 — homologação)
3. Refinar de-para com curadoria Protocolo após piloto
