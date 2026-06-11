# API — Fluxo de serviços (Protocolo AUTO/MANUAL)

> Configuração de despacho automático por serviço da carta Sinapse.  
> Guia operacional: [operacao/fluxo-auto-manual.md](../operacao/fluxo-auto-manual.md)

## Autenticação

JWT Bearer — perfil **`GESTOR`** (ou `is_staff`). Perfil **PROTOCOLO** recebe **403** em todas as rotas (P14).

## Endpoints

Base: `/api/fluxo-servicos/`

| Método | URL | Descrição |
|--------|-----|-----------|
| GET | `/api/fluxo-servicos/` | Lista configurações salvas |
| GET | `/api/fluxo-servicos/carta/` | Carta Sinapse + modo efetivo por serviço |
| POST | `/api/fluxo-servicos/upsert/` | Cria ou atualiza regra por `sinapse_servico_id` |
| POST | `/api/fluxo-servicos/` | Alias de upsert (body com `sinapse_servico_id`) |
| PATCH | `/api/fluxo-servicos/{id}/` | Atualiza registro existente |

### GET `/carta/`

Query params:

| Param | Tipo | Descrição |
|-------|------|-----------|
| `q` | string | Busca no título do serviço |
| `orgao_id` | int | Filtra por órgão Sinapse |
| `limit` | int | Máx. 500 (default 200) |
| `offset` | int | Paginação |

Resposta (trecho de item em `results[]`):

```json
{
  "sinapse_servico_id": 12345,
  "titulo": "Varrição de ruas",
  "orgao_id": 2001,
  "orgao_nome": "Secretaria de Serviços Urbanos",
  "modo": "MANUAL",
  "ativo": true,
  "despacho_automatico": false,
  "config_id": null,
  "observacoes": ""
}
```

Serviços sem configuração explícita retornam `modo: "MANUAL"` e `despacho_automatico: false`.

### POST `/upsert/`

Body:

```json
{
  "sinapse_servico_id": 12345,
  "modo": "AUTOMATICO",
  "ativo": true,
  "observacoes": "Homologado em jun/2026"
}
```

| Campo | Obrigatório | Valores |
|-------|-------------|---------|
| `sinapse_servico_id` | Sim | ID em `catalog_servico` (Sinapse) |
| `modo` | Não | `MANUAL` (default) \| `AUTOMATICO` |
| `ativo` | Não | `true` (default) — `false` desliga auto mesmo com `AUTOMATICO` |
| `observacoes` | Não | Texto livre (máx. 2000) |

Resposta 200 — serializer padrão:

```json
{
  "id": 1,
  "sinapse_servico_id": 12345,
  "modo": "AUTOMATICO",
  "ativo": true,
  "despacho_automatico": true,
  "observacoes": "",
  "atualizado_em": "2026-06-10T12:00:00Z"
}
```

Erros comuns:

| HTTP | Causa |
|------|-------|
| 403 | Usuário não Gestor |
| 400 | `sinapse_servico_id` ausente ou serviço inexistente na carta |

## Comportamento após upsert

Alterações aplicam-se a **novas** demandas que entrarem em `AGUARDANDO_PROTOCOLO` com:

- `sinapse_servico_id` igual ao configurado
- `origem_vinculo=CARTA` (não tendência)
- embedding presente (cluster/despacho auto)

Demandas já na fila podem ser reprocessadas quando o pipeline IA ou coorte rodar novamente.

## Frontend

| Tela | Rota |
|------|------|
| Gestão de fluxo | `/gestao-fluxo-servicos` (`FluxoServicosView.vue`) |

## Testes

```bash
cd backend
python manage.py test core.tests.test_fluxo_protocolo --settings=config.settings_test
```
