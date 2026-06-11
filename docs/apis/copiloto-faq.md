# FAQ Copiloto — base de conhecimento (banco + Admin)

Orientações exibidas quando o pedido **não compete** ao gabinete / Prefeitura (ex.: energia da concessionária).

## Modelo

| Modelo | Uso |
|--------|-----|
| `CopilotoFaqOrientacao` | Tema (título, mensagem, órgão sugerido, `categoria_orientacao` para o LLM) |
| `CopilotoFaqPadraoRegex` | Gatilhos regex (um por linha no Admin) |

Campos de auditoria: `fonte` (`MANUAL`, `LLM`, `MIGRACAO`), `ultima_sincronizacao_llm`, `municipio_referencia` (padrão **Mogi das Cruzes**).

## Django Admin

Menu: **FAQ Copiloto — base de conhecimento**. Edite textos e padrões regex; desative com `ativo=False` sem apagar histórico.

## Seed inicial

```bash
cd backend && python manage.py migrate
python manage.py seed_copiloto_faq
```

## API REST (Protocolo / Gestor)

| Método | URL | Descrição |
|--------|-----|-----------|
| GET | `/api/copiloto-faq/` | Lista entradas |
| GET | `/api/copiloto-faq/{id}/` | Detalhe + padrões |
| POST | `/api/copiloto-faq/` | Cria entrada manual |
| PATCH | `/api/copiloto-faq/{id}/` | Atualiza |
| GET | `/api/copiloto-faq/catalogo-llm/` | Categorias ativas para montar prompt da automação |
| GET | `/api/copiloto-faq/sugestoes-llm/?foco=` | Preview Groq (dry-run, não grava) |
| GET | `/api/v1/copiloto-faq/sugestoes-llm/?foco=` | Mesmo preview (alias v1 para o frontend) |
| POST | `/api/copiloto-faq/enriquecer-llm/` | Upsert via payload da IA |
| POST | `/api/v1/copiloto-faq/enriquecer-llm/` | Aprovação na curadoria web (201 Created) |

### Gestão web (Vue)

Rota: `/admin/faq-copiloto` — menu **FAQ Copiloto** (perfis **GESTOR** e **PROTOCOLO**).

| Aba | Função |
|-----|--------|
| **Base cadastrada** | Lista, cria e edita entradas + padrões regex (`GET/PATCH /api/copiloto-faq/`, `copiloto-faq-padroes/`) |
| **Curadoria IA** | Preview Groq e aprovação pontual |

Curadoria IA:

1. `GET v1/copiloto-faq/sugestoes-llm/?foco=...` — gera cards sem persistir.
2. `POST v1/copiloto-faq/enriquecer-llm/` — aprova uma sugestão por vez.

Resposta de sugestões (campo `sugestoes` unificado para a UI):

```json
{
  "municipio": "Mogi das Cruzes",
  "observacoes": "...",
  "sugestoes": [
    {
      "id": "nova-0",
      "tipo": "nova",
      "categoria_orientacao": "DETRAN_VEICULOS",
      "titulo": "...",
      "mensagem": "...",
      "orgao_hint": "...",
      "padroes_regex": ["\\\\bdetran\\\\b"]
    }
  ],
  "novas_entradas": [],
  "atualizacoes": [],
  "erros": []
}
```

### Enriquecimento LLM (automação futura)

```json
POST /api/copiloto-faq/enriquecer-llm/
{
  "categoria_orientacao": "TRANSPORTE_ESTADUAL",
  "titulo": "Rodovias estaduais",
  "mensagem": "Obras e concessões em rodovias estaduais não são ofício do gabinete municipal.",
  "orgao_hint": "DER-SP ou concessionária da rodovia",
  "padroes_regex": ["\\brodovia\\b", "\\bder\\b"],
  "municipio_referencia": "Mogi das Cruzes",
  "substituir_padroes": false,
  "notas_internas": "Sugestão Groq — revisar antes de homologar"
}
```

## Copiloto (runtime)

`ChatbotService` carrega a FAQ do banco (`copiloto_faq_service.carregar_catalogo_faq`) com cache invalidado ao salvar no Admin.

## Automação Groq (enriquecimento)

Comando de gestão que consulta o catálogo atual, pede lacunas à LLM (contexto **Mogi das Cruzes**) e grava via `aplicar_sugestao_llm` (`fonte=LLM`).

```bash
# Revisar JSON sem gravar
python manage.py enriquecer_faq_llm --dry-run

# Aplicar (até 5 entradas novas + atualizações de padrões)
python manage.py enriquecer_faq_llm --max-novas 5

# Foco temático
python manage.py enriquecer_faq_llm --foco "DETRAN, CNH e licenciamento de veículos"

# Auditoria no Admin
python manage.py enriquecer_faq_llm --usuario protocolo1
```

Variáveis opcionais (`.env`):

- `COPILOTO_FAQ_LLM_TIMEOUT` (padrão 90s)
- `COPILOTO_FAQ_LLM_TEMPERATURE` (padrão 0.25)
- `GROQ_API_KEY` (obrigatória)

Serviço: `core/services/copiloto_faq_enriquecimento_llm.py` (`CopilotoFaqEnriquecimentoLlmService`).

## Homologação

```bash
python manage.py test core.tests.CopilotoFaqCompetenciaTests core.tests.ForaCompetenciaCopilotoTests core.tests.CopilotoFaqApiTests core.tests.CopilotoFaqEnriquecimentoLlmTests --settings=config.settings_test
```
