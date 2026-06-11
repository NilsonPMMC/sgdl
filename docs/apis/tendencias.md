# Tendências — API e modelo (Fase A)

Solicitações **fora da carta Sinapse** viram `Tendencia` (embedding 1024d, volume de ocorrências). O fluxo Copiloto **carta** permanece igual; o braço tendências exige `COPILOTO_TENDENCIAS_ENABLED=true`.

## Modelo

| Entidade | Uso |
|----------|-----|
| `Tendencia` | Tema não catalogado; `embedding` 1024d; `status` ABERTA → VINCULADA_CARTA |
| `TendenciaOcorrencia` | Cada demanda vinculada |
| `Demanda.origem_vinculo` | `CARTA` (default) ou `TENDENCIA` |
| `Demanda.tendencia` | FK opcional |

## Variáveis (.env)

```env
COPILOTO_TENDENCIAS_ENABLED=true
TENDENCIA_SIMILARITY_THRESHOLD=0.85
COPILOTO_TRIAGEM_SCORE_LIMIAR=0.45
```

- `COPILOTO_TRIAGEM_SCORE_LIMIAR`: no rascunho, `fora_carta=true` quando o melhor candidato Sinapse fica abaixo do limiar (sem serviço confirmado).

## Endpoints

| Método | URL | Quem | Descrição |
|--------|-----|------|-----------|
| POST | `/api/v1/chat/confirmar-tendencia/` | Autenticado | Grava tendência no item do rascunho |
| POST | `/api/tendencias/buscar-similares/` | Autenticado | `{ "texto", "limite"? }` → candidatos por embedding |
| GET | `/api/tendencias/` | PROTOCOLO, GESTOR | Lista tendências |
| GET | `/api/tendencias/{id}/` | PROTOCOLO, GESTOR | Detalhe |
| PATCH | `/api/tendencias/{id}/` | PROTOCOLO, GESTOR | `status`, `titulo`, `sinapse_orgao_id`, … |
| POST | `/api/tendencias/{id}/promover-carta/` | PROTOCOLO, GESTOR | `{ "sinapse_servico_id" }` |
| GET | `/api/tendencias/{id}/ocorrencias/` | PROTOCOLO, GESTOR | Demandas ligadas |

### Confirmar tendência (copiloto)

```json
POST /api/v1/chat/confirmar-tendencia/
{
  "session_id": "uuid",
  "indice_demanda": 0,
  "titulo": "Problema não catalogado",
  "descricao_resumo": "",
  "sinapse_orgao_id": 2001,
  "tendencia_id": null
}
```

Resposta inclui `demandas_extraidas[]` com `fora_carta`, `tendencia`, `origem_vinculo`.

### Materialização

Com flag ativa, ao confirmar «sim» no Copiloto, itens com `origem_vinculo=TENDENCIA` geram `Demanda` + `TendenciaOcorrencia` + ofício (órgão da tendência ou Protocolo Geral).

## Frontend

| Tela | Rota | Perfis |
|------|------|--------|
| Gestão de Tendências | `/gestao-tendencias` (`TendenciasGestaoView.vue`) | PROTOCOLO, GESTOR |
| Copiloto (trilha tendência) | `/copiloto` | VEREADOR, GESTOR |

`ApiService`: `listarTendencias`, `obterTendencia`, `listarTendenciaOcorrencias`, `atualizarTendencia`, `promoverTendenciaCarta`, `buscarTendenciasSimilares`, `confirmarTendenciaCopiloto`.

## Homologação

```bash
cd backend && python manage.py migrate
python manage.py test core.tests.TendenciaServiceTests core.tests.TendenciaAPITests core.tests.CopilotoConfirmarTendenciaTests
```

Busca vetorial exige **PostgreSQL + pgvector** (em SQLite retorna lista vazia na similaridade, mas `buscar_ou_criar` por slug funciona).
