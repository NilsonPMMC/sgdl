# Geocodificação de endereços — Mogi das Cruzes

> **Status:** **Fases 1–3 concluídas** (jun/2026) · homologação operacional  
> **Escopo:** Copiloto, revisão de ofícios/indicações (rascunho), cluster (~300 m), mapa operacional

---

## Objetivo

Oferecer uma cadeia **robusta e auditável** de localização para demandas legislativas em Mogi das Cruzes: normalização canônica de endereço, geocodificação progressiva (ViaCEP → OSM → base local → LLM assistivo), confirmação explícita pelo operador e **ajuste manual do pin** no mapa.

---

## Visão das três fases

| Fase | Tema | Entregas principais | Status |
|------|------|---------------------|--------|
| **1** | Normalização + geocode confiável | `endereco_normalizacao.py`, variantes OSM, chave canônica, gate cluster, integração `geocoding_service` | **OK** |
| **2** | UX Copiloto + reverse geocode | Autocomplete CEP/logradouro, confirmação explícita de local, reverse geocode, formulário alinhado ao `DemandaForm` | **OK** |
| **3** | Base local + parsing assistivo | `ViaReferenciaMogi`, seed de vias, fuzzy bairro, parsing LLM (Groq) só estruturação textual | **OK** |

**Complemento pós-fases (jun/2026):** pin **arrastável** no Copiloto e na revisão de rascunho; persistência de coordenadas manuais (`ajuste_mapa`) na sessão e na materialização da demanda.

---

## Fase 1 — Normalização e geocode para cluster

### Backend

- **`core/services/endereco_normalizacao.py`**
  - Expansão de abreviações (`av` → `Avenida`, `r` → `Rua`, `vl` → `Vila`, iniciais de nomes).
  - `chave_endereco_canonica` — mesma chave para `Av.` e `Avenida`.
  - `filtrar_coordenadas_para_persistencia` / `coordenadas_elegiveis_cluster` — gate ~300 m.
  - `endereco_resumo_humano`, `montar_alerta_geocode`.
- **`core/services/geocoding_service.py`**
  - Viewbox Mogi das Cruzes, variantes de via para Nominatim, `resolver_endereco_geocode()`.
- **`core/services/cluster_service.py`** — cluster por chave canônica de endereço.
- **`core/services/chatbot_service.py`** — extração determinística de endereço na etapa `COLETA_ENDERECO`.

### Testes

- `backend/core/tests/test_geocoding_fase1.py`

---

## Fase 2 — UX guiada e reverse geocode

### Backend

- Reverse geocode (Nominatim) em `resolver_endereco_geocode()` quando há logradouro+bairro.
- `editar_local_demanda()` **não** confirma local automaticamente.
- Fluxo Copiloto: resumo + alerta + mapa + botão «Confirmar local».

### API

| Método | Endpoint | Uso |
|--------|----------|-----|
| GET | `/api/v1/geocoding/cep/` | ViaCEP |
| GET | `/api/v1/geocoding/logradouros/` | Autocomplete de vias |
| POST | `/api/v1/geocoding/resolver/` | Forward geocode |
| POST | `/api/v1/geocoding/reverse/` | Endereço a partir de lat/lng |
| POST | `/api/v1/chat/atualizar-localizacao/` | GPS ou ajuste de pin no Copiloto (`fonte`, `confirmar_local`) |

### Frontend

- Autocomplete CEP/logradouro no **Copiloto** e **DemandaForm**.
- `CopilotoContextoPainel.vue` — estado de local pendente/confirmado.

### Testes

- `backend/core/tests/test_geocoding_fase2.py`

---

## Fase 3 — Base local de vias e parsing assistivo

### Backend

- **Modelo** `ViaReferenciaMogi` (`core/models_via_referencia.py`, migration `0070`).
- **`via_referencia_service.py`** — lookup por chave canônica antes do OSM.
- **`endereco_parsing_service.py`** — LLM (Groq) apenas para parsing estruturado (sem coords).
- **Fuzzy bairro** (`fuzzywuzzy`) em `bairros_equivalentes()`.
- **Seed:** `python manage.py seed_vias_referencia_mogi`

### Settings (`.env` / `settings.py`)

| Variável | Default | Descrição |
|----------|---------|-----------|
| `GEOCODING_VIA_REFERENCIA_ENABLED` | `True` | Usa base local de vias |
| `GEOCODING_LLM_PARSING_ENABLED` | `True` | Parsing assistivo Groq |
| `GEOCODING_BAIRRO_FUZZY_THRESHOLD` | `90` | Limiar fuzzy bairro |

### Testes

- `backend/core/tests/test_geocoding_fase3.py`

---

## Ajuste manual do pin (mapa)

| Tela | Componente | Comportamento |
|------|------------|---------------|
| Copiloto | `MapaLocalAjustavel.vue` | Arrastar pin → `POST atualizar-localizacao` com `fonte=ajuste_mapa`, `confirmar_local=false` |
| Revisão ofício | `DemandaForm.vue` | Pin Leaflet arrastável + reverse geocode |
| Revisão indicação | `IndicacaoFormView.vue` | Idem |

**Regras de persistência**

- Coordenadas com `coordenadas_fonte` ∈ `{ajuste_mapa, gps_dispositivo}` **não** são sobrescritas por re-geocode do endereço textual.
- `_materializar_demandas()` usa `_coordenadas_endereco_materializacao()` — prioriza pin/GPS do rascunho ao criar a demanda.

---

## Fluxo operador (Copiloto)

1. Informar endereço (texto livre, CEP ou autocomplete).
2. Conferir resumo, alerta e mapa.
3. Opcional: arrastar pin para o local exato.
4. Clicar **«Confirmar local»** (ou «Continuar sem local»).
5. Finalizar → demanda em rascunho com coords persistidas.

---

## Evidências de homologação

```bash
cd backend
python manage.py test core.tests.test_geocoding_fase1 core.tests.test_geocoding_fase2 core.tests.test_geocoding_fase3
python manage.py check --deploy
cd ../frontend && npm run build
```

**Amostra manual sugerida:** 10 endereços reais de Mogi (incl. abreviações `av`, `r`, `vl` e vírgula logradouro+bairro).

---

## Referências técnicas

| Área | Arquivos |
|------|----------|
| Normalização | `backend/core/services/endereco_normalizacao.py` |
| Geocode | `backend/core/services/geocoding_service.py` |
| Copiloto / sessão | `backend/core/services/chatbot_service.py` |
| API | `backend/core/views_geocoding.py`, `backend/core/views.py` |
| Mapa UI | `frontend/src/components/mapa/MapaLocalAjustavel.vue` |
| Util frontend | `frontend/src/utils/mapaLocalAjustavel.js` |

---

## Histórico

| Data | Evento |
|------|--------|
| 2026-06-13 | Apontamento H2-09 (busca endereço) — backlog B1 |
| 2026-06-22 | Fases 1–3 implementadas; pin arrastável; persistência `ajuste_mapa` |
| — | Validação amostra 10 vias MC em homologação contínua |
