"""Orquestrador do copiloto conversacional: histórico persistente + Groq + triagem Sinapse.

Fluxo em **slot filling dinâmico** (sem sequência rígida de formulário):
1. Carrega `ChatSession.historico_mensagens`, acrescenta a nova mensagem do usuário.
2. Chama o Groq com contrato JSON: extrair imediatamente problemas, endereços e `texto_para_embedding`
   em `demandas_extraidas` (vários itens se houver vários problemas).
3. Mescla endereço inferido do texto livre (`_extrair_endereco_livre`) nos slots antes/depois do LLM,
   para não “perder” rua/CEP/bairro ditos na mesma frase do relato.
4. Se `acionar_triagem_sinapse`, gera embedding, chama `TriagemService` e aplica candidatos no
   rascunho no backend (sem segunda inferência Groq); histórico guarda marcador `[SISTEMA SINAPSE]` só
   para escolha numérica no chat.
5. Guardrails no backend reforçam endereço real (logradouro+bairro) e impedem triagem com slots vazios.
6. Persiste histórico, `estado_atual` e `demandas_rascunho`; em `VALIDACAO_FINAL` com confirmação,
   materializa `Demanda` reais.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

import requests
from django.conf import settings
from django.db import transaction

from integrations import sinapse_catalog

from ..models import Anexo, ChatSession, ChatSessaoAnexo, Demanda, Tendencia
from .carta_sinapse_sync import gestao_operacional_para_copiloto
from .copiloto_dominio import (
    candidatos_relevantes_dominio,
    detectar_dominio_operacional,
    variantes_triagem_por_dominio,
)
from .copiloto_faq_competencia import (
    detectar_faq_por_texto,
    faq_para_dict,
    faq_por_categoria,
    listar_categorias_para_prompt,
    listar_faq_detalhada_para_prompt,
    montar_motivo_recusa,
    montar_resposta_chat_fora_competencia,
    normalizar_categoria_orientacao,
    normalizar_competencia_llm,
)
from .copiloto_config import copiloto_faq_habilitada, copiloto_tendencias_habilitadas
from .geocoding_service import GeocodingService
from .tendencia_service import TendenciaService
from .triagem_service import TriagemService
from .triagem_otimizada_service import AdapterTriagemOtimizada
from .vector_service import VectorService

logger = logging.getLogger(__name__)

# Usuário “cutuca” a IA quando ela parou sem disparar a carta Sinapse
_NUDGE_TRIAGEM_RE = re.compile(
    r"^(então\??|entao\??|e\s+a[ií]\??|e\s+ai\??|continue|continua|ok|beleza|próximo|proximo|e\s+agora|\?+)$",
    re.IGNORECASE,
)

# --- System prompt (slot filling dinâmico + contrato JSON) ----------------------

COPILOT_JSON_CONTRACT = """
Responda com UM objeto JSON válido (sem markdown, sem texto fora do JSON):

{
  "usuario_forneceu_endereco_real": false,
  "resposta_agente": "string (sempre uma ou mais frases naturais ao cidadão; nunca vazia)",
  "estado_atual": "COLETA_DADOS | CONFIRMACAO_SINAPSE | COLETA_ENDERECO | VALIDACAO_FINAL",
  "demandas_extraidas": [
     {
       "titulo": "resumo curto do PEDIDO do cidadão (não invente nome de serviço da carta)",
       "descricao": "pedido na íntegra (relato completo do usuário, sem resumir demais)",
       "pedido_integral": "mesmo relato completo (cópia fiel do que o cidadão disse)",
       "texto_para_embedding": "problema + local JÁ ditos pelo usuário (null se faltar local)",
       "endereco": {
         "cep": null,
         "logradouro": null,
         "numero": null,
         "bairro": null,
         "complemento": null
       },
       "servico_local_id": null,
       "sinapse_servico_id_sugerido": null,
       "anexos_indices": null,
       "competencia_municipal": "sim | nao | incerto",
       "categoria_orientacao": null,
       "motivo_recusa": null,
       "teor_ouvidoria": false,
       "subtipo_ouvidoria": null
     }
  ],

`anexos_indices` (por demanda): lista de inteiros 0-based referindo aos anexos enviados na sessão
(ordem cronológica de upload). Preencha **somente** os anexos que pertencem **a esta** demanda.
`descricao` de cada item deve falar **apenas** daquele problema — nunca liste os outros pedidos.
  "acionar_triagem_sinapse": false,
  "confirmar_criacao_demandas": false
}

`usuario_forneceu_endereco_real` (obrigatório na raiz):
- Deve ser `true` **APENAS** se o usuário digitou explicitamente o nome de uma rua, avenida, praça ou CEP.
- Se ele só falou o problema (sem via pública nem CEP), DEVE ser `false`.
- Se for `false`, todos os campos de `endereco` em todas as demandas DEVEM ser `null` — **não** copie
  o texto do pedido para `logradouro` nem `bairro` para “preencher” o JSON.
- O campo `logradouro` deve conter **APENAS** o nome da rua, avenida ou praça (ex.: "Rua Maestro
  Laurindo José Gonçalves"). **NUNCA** inclua verbos, comandos ou o texto inicial do usuário como
  "crie oficio solicitando".

Extração (somente do que o usuário disse):
- Preencha campos **apenas** com informação **explícita** no histórico do cidadão. Dúvida ⇒ `null`.
- `texto_para_embedding`: use só problema + local que o usuário **já informou**; não complete com suposição.
- Múltiplos objetos em `demandas_extraidas` **somente** se o usuário pediu **mais de um serviço/problema
  diferente** na mesma conversa. **Nunca** crie um objeto por candidato do Sinapse.
- Após `[SISTEMA SINAPSE]`: atualize **somente** `sinapse_servico_id_sugerido` (e `servico_local_id` se
  vier do mapeamento) da demanda que **já existia**; não acrescente demandas novas; não copie títulos
  genéricos da carta para `titulo`/`descricao` se o usuário não os disse.
- `confirmar_criacao_demandas`: true só se o estado anterior era VALIDACAO_FINAL e o cidadão confirmou.

Competência municipal (obrigatório em cada item de `demandas_extraidas`):
- `competencia_municipal`: `sim` se o pedido é serviço público municipal (zeladoria, obras, parques, saúde na via, etc.);
  `nao` se não compete à Prefeitura/gabinete (receitas, piadas, energia da concessionária, conta de água da SABESP,
  telefonia/Procon, etc.); `incerto` se faltar contexto.
- `categoria_orientacao`: quando `nao`, use **somente** uma categoria listada no system prompt (FAQ cadastrada);
  se houver correspondência, reproduza a orientação oficial (`mensagem` + `orgao_hint`) na `resposta_agente`.
- `motivo_recusa`: frase curta quando `competencia_municipal` for `nao`; combine com a orientação da FAQ quando aplicável; senão `null`.
- Se `nao`, `resposta_agente` deve usar a orientação cadastrada na FAQ (não invente órgão ou procedimento).
""".strip()

COPILOT_SYSTEM_PROMPT = f"""
Você é o assistente de triagem do Gabinete (zeladoria e serviços municipais). Converse de forma
natural e objetiva, estruturando o pedido em JSON sem inventar dados.

O que precisamos registrar (por solicitação):
1. **Pedido na íntegra** — `descricao` e `pedido_integral` com o relato completo do cidadão.
2. **Serviço(s)** — título curto; a carta Sinapse é consultada pelo sistema (não invente IDs).
3. **Localização** — só quando o assunto exigir (zeladoria, obras, eventos em parque, etc.); cadastros
   puramente administrativos podem seguir sem endereço se o usuário não informou.
4. **Documentos** — se o usuário enviou anexo(s), preencha `anexos_indices` (0-based, ordem de upload
   na sessão) na demanda correspondente; se houver um único pedido, vincule todos os anexos a ele.

REGRA 1: NUNCA invente ruas, bairros, CEP ou descrições. Dúvida ⇒ `null` nos campos de endereço.

REGRA 2: Múltiplas demandas **somente** se o usuário pediu mais de um serviço/problema distinto.
Nunca crie demanda por candidato da busca vetorial. **Nunca** use em `titulo` o nome de um serviço da carta
que o cidadão não citou (ex.: evite «Manutenção e Revitalização do Redutor de Velocidade» como catálogo —
prefira «Manutenção de redutor na Av. X»). Candidatos Sinapse são referência para o painel; o cidadão escolhe,
ignora ou pede nova busca — você não lista opções na `resposta_agente`.

REGRA 3 — RELATO E TÍTULO (ofício e cadastro):
- `descricao` e `pedido_integral` devem reproduzir **todo** o pedido do cidadão: números de linha (ex.: 209),
  quantidades, objetivos, **datas e horários de eventos**, **estado atual do local** (ex.: «via interditada»,
  «lâmpada queimada»), prazos, nomes próprios e contexto — **nunca** resuma para «Solicitação de transporte coletivo».
- `titulo` é um **resumo curto do pedido** (ex.: «Aumento de veículos na linha 209»), não o nome do serviço da carta
- `sinapse_servico_id_sugerido` e `servico_local_id`: **somente** inteiro ID Sinapse confirmado no painel — **nunca** nome
  do serviço (ex.: nunca `"Transporte Coletivo"`); deixe `null` até o cidadão/equipe escolher no painel.

REGRA DE COMPETÊNCIA (Prefeitura / gabinete):
- Pedidos que **não** são serviço público municipal → `competencia_municipal: "nao"` (ex.: receita de bolo,
  dever de casa, piada, conta de luz da concessionária, falta de água em casa via SABESP, internet da operadora).
- Pedidos de zeladoria, vias, iluminação **pública**, parques, limpeza, obras → `competencia_municipal: "sim"`.
- Cadastro, inscrição, alvará ou permissão de **táxi / taxista** (Secretaria de Mobilidade) → `competencia_municipal: "sim"` — **não** é Procon nem consumidor privado.
- Iluminação de via pública / poste na rua → `sim` (municipal). Conta de luz / medidor em casa → `nao` + `ENERGIA_CONCESSIONARIA`.
- Com `nao`, não peça endereço para ofício; explique e oriente o canal adequado.

Trilha Ouvidoria (A′ — serviço «Atendimento ao Cidadão»):
- Quando o pedido for **manifestação institucional** (denúncia, reclamação sobre atendimento, sugestão ou elogio
  à Prefeitura) — e **não** pedido operacional de zeladoria/obras — use `teor_ouvidoria: true` e
  `subtipo_ouvidoria`: `denuncia` | `reclamacao` | `sugestao` | `elogio`.
- Pedidos de buraco, lombada, iluminação, limpeza etc. → `teor_ouvidoria: false` (trilha carta A).
- Com `teor_ouvidoria: true`, o sistema vincula ao serviço Ouvidoria; não invente outro serviço da carta.
- Exemplos Ouvidoria: «registro uma sugestão para instalar totem no PAC» → sugestao; «elogio ao atendimento» → elogio;
  «denúncia de irregularidade» → denuncia; «reclamação sobre demora/omissão no atendimento» → reclamacao.

REGRA DE ESTADO (flexível — o backend ajusta etapas):
- Falta relato do problema → `COLETA_DADOS`; peça o pedido com suas palavras.
- Problema claro, sem local e o tipo costuma precisar de local → sugira endereço sem pressionar;
  `usuario_forneceu_endereco_real` só com rua/CEP/bairro/parque **explícitos** (bairro sozinho vale).
- Com relato suficiente → `acionar_triagem_sinapse = true` para o sistema buscar na carta.
- Após `[SISTEMA SINAPSE]`: não liste opções no chat; o painel mostra a carta (≥ 66,66% de similaridade).
- Anexo no início da conversa: extraia o pedido do texto do usuário e vincule `anexos_indices`.

Orientação operacional (quando o serviço da carta já estiver definido):
- Se o painel ou contexto trouxer `gestao_operacional` (prazo, documentos, taxas do Sinapse), use **somente**
  esses dados para orientar o cidadão sobre o que levar, taxas e prazo **estimado** do serviço completo.
- Não invente documentos nem valores; se a lista estiver vazia, diga que o cidadão deve confirmar no
  canal oficial ao cidadão (ColabGov, portal online, etc.) indicado na carta.

Comunique-se de forma cordial e humana, sem prometer prazos legais.

Limpeza de endereço:
- O campo `logradouro` deve conter APENAS o nome da rua, avenida ou praça (ex.: "Rua Maestro Laurindo
  José Gonçalves"). NUNCA inclua verbos, comandos ou o texto inicial do usuário como "crie oficio
  solicitando".

EXEMPLO DE COMPORTAMENTO:
User: "gerar oficio solicitando tapa buraco"
Assistant (Internal JSON):
{{
  "usuario_forneceu_endereco_real": false,
  "estado_atual": "COLETA_ENDERECO",
  "resposta_agente": "Entendi que você precisa de um Tapa Buraco. Por favor, me informe o nome da rua e o bairro para eu registrar a solicitação.",
  "acionar_triagem_sinapse": false,
  "demandas_extraidas": [
    {{
       "titulo": "Tapa Buraco",
       "descricao": "Solicitação de tapa buraco",
       "texto_para_embedding": "tapa buraco via publica",
       "endereco": {{ "cep": null, "logradouro": null, "numero": null, "bairro": null, "complemento": null }},
       "competencia_municipal": "sim"
    }}
  ]
}}

EXEMPLO múltiplas solicitações distintas (mesmo endereço):
User: "reparo em buracos na via e instalação de lombada na Rua Ipiranga, nº 1001, Centro"
Assistant (Internal JSON):
{{
  "usuario_forneceu_endereco_real": true,
  "estado_atual": "COLETA_DADOS",
  "resposta_agente": "Entendi duas solicitações no mesmo local: reparo de buracos e instalação de lombada. Vou consultar a carta de serviços para cada uma.",
  "acionar_triagem_sinapse": true,
  "demandas_extraidas": [
    {{
       "titulo": "Reparo em buracos na via",
       "descricao": "Solicito reparo em buracos na via na Rua Ipiranga, próximo ao número 1001, no Centro.",
       "pedido_integral": "reparo em buracos na via e instalação de lombada na Rua Ipiranga, nº 1001, Centro",
       "texto_para_embedding": "reparo tapa buraco via Rua Ipiranga Centro",
       "endereco": {{ "cep": null, "logradouro": "Rua Ipiranga", "numero": 1001, "bairro": "Centro", "complemento": null }},
       "competencia_municipal": "sim"
    }},
    {{
       "titulo": "Instalação de lombada",
       "descricao": "Solicito instalação de lombada na Rua Ipiranga, próximo ao número 1001, no Centro.",
       "pedido_integral": "reparo em buracos na via e instalação de lombada na Rua Ipiranga, nº 1001, Centro",
       "texto_para_embedding": "instalação lombada redutor velocidade Rua Ipiranga Centro",
       "endereco": {{ "cep": null, "logradouro": "Rua Ipiranga", "numero": 1001, "bairro": "Centro", "complemento": null }},
       "competencia_municipal": "sim"
    }}
  ]
}}

EXEMPLO fora de competência:
User: "quero receita de bolo"
Assistant (Internal JSON):
{{
  "usuario_forneceu_endereco_real": false,
  "estado_atual": "COLETA_DADOS",
  "resposta_agente": "Esse assunto não é um serviço público municipal que o gabinete protocola como ofício. Posso ajudar com zeladoria, obras, meio ambiente ou outros serviços da Prefeitura.",
  "acionar_triagem_sinapse": false,
  "demandas_extraidas": [
    {{
       "titulo": "Receita de bolo",
       "descricao": "Pedido de receita de bolo",
       "texto_para_embedding": "receita de bolo",
       "competencia_municipal": "nao",
       "categoria_orientacao": null,
       "motivo_recusa": "Não é solicitação de serviço público municipal."
    }}
  ]
}}

{COPILOT_JSON_CONTRACT}
""".strip()

_ENDERECO_VAZIO: dict[str, Any] = {
    "cep": None,
    "logradouro": None,
    "numero": None,
    "bairro": None,
    "complemento": None,
}

# Eixos distintos detectáveis no mesmo relato → uma demanda por eixo (mesmo endereço).
_EIXOS_PEDIDO_COMPOSTO: tuple[dict[str, Any], ...] = (
    {
        "id": "pavimentacao_buraco",
        "titulo_padrao": "Reparo em buracos na via",
        "descricao_verbo": "reparo em buracos na via",
        "texto_embedding": "reparo tapa buraco cratera via pública asfalto pavimentação",
        "gatilhos": ("buraco", "buracos", "tapa", "cratera", "esburacad", "afundamento"),
    },
    {
        "id": "mobilidade_sinalizacao",
        "titulo_padrao": "Placa ou sinalização de trânsito",
        "descricao_verbo": "placa ou sinalização de trânsito",
        "texto_embedding": "placa sinalização vertical horizontal semáforo trânsito mobilidade alteração",
        "gatilhos": (
            "placa de sinal",
            "placa sinal",
            "sinalização",
            "sinalizacao",
            "sinaliz",
            "semáforo",
            "semaforo",
        ),
    },
    {
        "id": "mobilidade_lombada",
        "titulo_padrao": "Instalação de lombada",
        "descricao_verbo": "instalação de lombada",
        "texto_embedding": "instalação implantação lombada redutor velocidade trânsito mobilidade",
        "gatilhos": ("lombad", "redutor de velocidade", "redutor"),
    },
    {
        "id": "pavimentacao_nivelamento",
        "titulo_padrao": "Nivelamento e cascalhamento",
        "descricao_verbo": "nivelamento e cascalhamento",
        "texto_embedding": "nivelamento cascalhamento estrada municipal pavimentação",
        "gatilhos": ("nivelamento", "cascalh"),
    },
    {
        "id": "limpeza_urbana",
        "titulo_padrao": "Limpeza urbana",
        "descricao_verbo": "limpeza urbana",
        "texto_embedding": "limpeza varrição coleta entulho sujeira via",
        "gatilhos": ("limpeza urbana", "varrição", "varricao", "entulho", "capina"),
    },
    {
        "id": "meio_ambiente_poda",
        "titulo_padrao": "Poda ou corte de árvore",
        "descricao_verbo": "poda ou corte de árvore",
        "texto_embedding": "poda corte árvore galho poda arborização meio ambiente",
        "gatilhos": (
            "poda",
            "podar",
            "árvore",
            "arvore",
            "arvores",
            "árvores",
            "galho",
            "galhos",
            "corte de árvore",
            "corte de arvore",
        ),
    },
)

_TITULO_GENERICO_RE = re.compile(
    r"^(solicita(?:ção|cao)? de |pedido de )?"
    r"(transporte coletivo|serviço público|servico publico|demanda|solicitação|solicitacao)"
    r"\.?$",
    re.IGNORECASE,
)
_MENSAGEM_COMANDO_FLUXO_RE = re.compile(
    r"^(sim|não|nao|confirmar|continuar|gerar rascunhos|ok|prosseguir)[\s,.!?]*$",
    re.IGNORECASE,
)

_SINAPSE_PREFIX = "[SISTEMA SINAPSE]"
_SINAPSE_PREFIX_LEGACY = "[SINAPSE_TRIAGEM]"

# Remove verbos/comandos colados no logradouro pelo LLM
_LIMPEZA_PREFIXO_LOGRADOURO_RE = re.compile(
    r"^(?:(?:crie|criar|gerar|elabore|elaborar|solicite|solicitar|fazer|faça)\s+)+"
    r"(?:(?:um|uma)\s+)?(?:of[ií]cio\s+)?(?:de\s+)?(?:solicitando\s+)?",
    re.IGNORECASE,
)
_EXTRAI_VIA_RE = re.compile(
    r"(?:na\s+)?((?:rua|r\.?\s+|av\.?\s+|avenida|trav\.?\s+|travessa|al\.?\s+|alameda)\s+[^,]+?)(?=\s*,\s*|\s+\d{5}\s*-?\s*\d{3}|\s+\d{8}\s*$|$)",
    re.IGNORECASE,
)
_PALAVRAS_PEDIDO_NO_LOGRADOURO_RE = re.compile(
    r"\b(of[ií]cio|solicit|tapa|buraco|lombada|instala|uso\s+de|ações|acoes|social|sociais|agosto|janeiro|fevereiro|março|abril|maio|junho|julho|setembro|outubro|novembro|dezembro)\b",
    re.IGNORECASE,
)
_LOGRADOURO_FRASE_PEDIDO_RE = re.compile(
    r"\b(solicito|solicitação|solicitacao|reserva|informo|gostaria|preciso|dia\s+\d|no\s+dia)\b",
    re.IGNORECASE,
)
_BAIRRO_EXPLICITO_RE = re.compile(
    r"\b(?:no\s+)?bairro\s+([\wáàâãéêíóôõúç0-9][\wáàâãéêíóôõúç0-9\s\-]{1,78})",
    re.IGNORECASE,
)
_PALAVRAS_PEDIDO_NO_BAIRRO_RE = re.compile(
    r"\b("
    r"solicit|of[ií]cio|transporte|apresenta|competi[cç][aã]o|acoes|ações|social|"
    r"reserva|evento|uso\s+de|espaço|espaco|solicita|demanda|protocol|"
    r"agosto|janeiro|fevereiro|março|abril|maio|junho|julho|setembro|outubro|novembro|dezembro"
    r")\b",
    re.IGNORECASE,
)
_PARQUE_EXTRACAO_RE = re.compile(
    r"\bparque\s+([\wáàâãéêíóôõúç\-]+(?:\s+[\wáàâãéêíóôõúç\-]+)?)",
    re.IGNORECASE,
)
_STOP_PALAVRA_PARQUE = frozenset(
    {
        "para",
        "no",
        "na",
        "em",
        "dia",
        "de",
        "do",
        "da",
        "com",
        "por",
        "uso",
        "espaco",
        "espaço",
        "acoes",
        "ações",
        "social",
        "sociais",
        "evento",
        "eventos",
        "solicito",
        "solicitação",
        "solicitacao",
    }
)
_TEXTOS_PULAR_ENDERECO_RE = re.compile(
    r"\b(sem\s+endere[cç]o|n[aã]o\s+informar(?:\s+local)?|pular\s+endere[cç]o|continuar\s+sem\s+local|sem\s+local)\b",
    re.IGNORECASE,
)

# Pedidos claramente fora da competência do gabinete / prefeitura (fase mínima — sem LLM dedicado).
_FORA_COMPETENCIA_EXPLICITO_RE = (
    re.compile(
        r"\b(receita|card[aá]pio|ingrediente|modo\s+de\s+preparo|culin[aá]ria)\b.*\b(bolo|bolos|torta|doce|salgado|comida)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(bolo|bolos)\b.*\b(receita|card[aá]pio)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(dever\s+de\s+casa|trabalho\s+escolar|reda[cç][aã]o\s+escolar)\b", re.IGNORECASE),
    re.compile(r"\b(piada|charada|adivinha|hor[oó]scopo|signo\s+do)\b", re.IGNORECASE),
    re.compile(
        r"\b(como\s+fazer|tutorial|passo\s+a\s+passo)\b.*\b(receita|bolo|comida|culin)\b",
        re.IGNORECASE,
    ),
)

# Palavras-chave mínimas se o modelo esquecer o flag (fallback conservador)
_CONFIRM_RE = re.compile(
    r"\b(sim|confirmo|pode\s+(criar|protocolar|enviar)|está\s+certo|ok\s+para\s+protocolar)\b",
    re.IGNORECASE,
)

# Mensagens automáticas do copiloto — não são endereço (extração regex)
_TEXTO_SEM_ENDERECO_RE = re.compile(
    r"^(?:segue(?:m)?\s+anexo(?:s)?(?:\s+para\s+an[aá]lise(?:\s+da\s+solicita[cç][aã]o)?)?\.?|"
    r"continuar\s+sem\s+anexos?\.?|"
    r"continuar\s+sem\s+local\.?|"
    r"confirmar\s+(?:o\s+)?local(?:\s+(?:da\s+)?solicita[cç][aã]o\s+\d+)?\.?|"
    r"confirmar\s+(?:os\s+)?(?:documentos|anexos)(?:\s+(?:da\s+)?solicita[cç][aã]o\s+\d+)?\.?|"
    r"sim|n[aã]o|nao|\d{1,2})\s*\.?$",
    re.IGNORECASE,
)
_TEXTO_ANEXO_UI_RE = re.compile(
    r"^📎\s+.+$",
    re.IGNORECASE,
)
_TEXTO_CONTINUAR_SEM_ANEXOS_RE = re.compile(
    r"^continuar\s+sem\s+anexos?\.?$",
    re.IGNORECASE,
)
_TEXTO_CONFIRMAR_LOCAL_RE = re.compile(
    r"^confirmar\s+(?:o\s+)?local(?:\s+(?:da\s+)?solicita[cç][aã]o\s+(\d+))?\.?$",
    re.IGNORECASE,
)
_TEXTO_CONFIRMAR_ANEXOS_RE = re.compile(
    r"^confirmar\s+(?:os\s+)?(?:documentos|anexos)(?:\s+(?:da\s+)?solicita[cç][aã]o\s+(\d+))?\.?$",
    re.IGNORECASE,
)
_TEXTO_FINALIZAR_RE = re.compile(
    r"^(?:finalizar|concluir|encerrar|gerar\s+(?:rascunhos?|of[ií]cios?))\.?$",
    re.IGNORECASE,
)
_TEXTO_RECUSA_VALIDACAO_RE = re.compile(
    r"^(?:n[aã]o|nao|cancelar|voltar|ajustar|corrigir)\.?$",
    re.IGNORECASE,
)
_VALOR_ENDERECO_INVALIDO_RE = re.compile(
    r"\b(anexo|segue|solicita|an[aá]lise|analise|confirma|continuar|of[ií]cio|protocol|demanda)\b",
    re.IGNORECASE,
)


class ChatbotService:
    """Orquestra uma rodada de conversa com memória e triagem Sinapse."""

    def __init__(self) -> None:
        self.api_key: str = getattr(settings, "GROQ_API_KEY", "") or ""
        self.base_url: str = getattr(
            settings,
            "GROQ_BASE_URL",
            "https://api.groq.com/openai/v1/chat/completions",
        )
        self.model: str = getattr(
            settings, "GROQ_CHAT_MODEL", getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile")
        )
        self.timeout: int = int(getattr(settings, "GROQ_TIMEOUT", 60))
        self.temperature: float = float(getattr(settings, "GROQ_TEMPERATURE", 0.2))

    def interagir(
        self,
        *,
        usuario,
        session_id: str | None,
        mensagem: str,
        anexos_upload: list | None = None,
        anexo_demanda_indices: list[int | None] | None = None,
        indices_aprovados: list[int] | None = None,
        corpus_sinapse_servico_id: int | None = None,
        corpus_atalho_id: str | None = None,
    ) -> dict[str, Any]:
        """Executa uma rodada completa (persistência + opcional 2º call Groq pós-Sinapse)."""
        texto = (mensagem or "").strip()
        arquivos = list(anexos_upload or [])
        if not texto and not arquivos:
            return {
                "erro": "mensagem vazia",
                "session_id": str(session_id) if session_id else None,
                "resposta_agente": "Por favor, descreva o problema ou a solicitação.",
                "estado_atual": ChatSession.ESTADO_COLETA_DADOS,
                "demandas_extraidas": [],
            }
        if not texto and arquivos:
            texto = "Segue(m) anexo(s) para análise da solicitação."

        session = self._obter_sessao(usuario, session_id)
        arquivos_turno = list(arquivos)
        if arquivos and not self._rascunho_tem_problema_util(list(session.demandas_rascunho or [])):
            qtd = len(arquivos)
            texto = (
                f"{texto} O cidadão enviou {qtd} arquivo(s) neste turno; "
                "extraia o pedido na íntegra e preencha anexos_indices na demanda correspondente."
            )
        estado_antes = session.estado_atual
        historico: list[dict[str, Any]] = list(session.historico_mensagens or [])
        historico.append({"role": "user", "content": texto})

        if not self.api_key:
            logger.warning("GROQ_API_KEY ausente; copiloto degradado.")
            resposta = {
                "resposta_agente": (
                    "O assistente inteligente não está configurado no momento. "
                    "Contate o suporte ou use o fluxo tradicional de demandas."
                ),
                "estado_atual": estado_antes,
                "demandas_extraidas": list(session.demandas_rascunho or []),
                "acionar_triagem_sinapse": False,
                "confirmar_criacao_demandas": False,
            }
            historico.append(
                {"role": "assistant", "content": json.dumps(resposta, ensure_ascii=False)}
            )
            self._persistir_apos_turno(session, historico, resposta)
            return self._montar_resposta_http(session, resposta, criadas=[])

        texto_limpo = self._normalizar_comando_usuario(texto)
        if (
            not arquivos
            and session.estado_atual == ChatSession.ESTADO_VALIDACAO_FINAL
            and _TEXTO_RECUSA_VALIDACAO_RE.match(texto_limpo)
        ):
            parsed = self._processar_recusa_validacao_final(session)
            historico.append(
                {"role": "assistant", "content": json.dumps(parsed, ensure_ascii=False)}
            )
            self._persistir_apos_turno(session, historico, parsed)
            return self._montar_resposta_http(session, parsed, criadas=[])

        confirm_curto = bool(_CONFIRM_RE.search(texto_limpo)) and len(texto_limpo) < 96
        quer_gerar_rascunhos = not arquivos and (
            _TEXTO_FINALIZAR_RE.match(texto_limpo)
            or (
                session.estado_atual == ChatSession.ESTADO_VALIDACAO_FINAL
                and confirm_curto
            )
        )
        if quer_gerar_rascunhos:
            parsed, demandas_criadas = self._processar_finalizar_ou_confirmar(
                session, usuario, historico, texto_limpo, indices_aprovados=indices_aprovados
            )
            historico.append(
                {"role": "assistant", "content": json.dumps(parsed, ensure_ascii=False)}
            )
            self._persistir_apos_turno(session, historico, parsed)
            return self._montar_resposta_http(session, parsed, criadas=demandas_criadas)

        if not arquivos:
            rev_parsed = self._tentar_processar_revisao_conversacional(
                session, texto_limpo
            )
            if rev_parsed:
                historico.append(
                    {"role": "assistant", "content": json.dumps(rev_parsed, ensure_ascii=False)}
                )
                self._persistir_apos_turno(session, historico, rev_parsed)
                return self._montar_resposta_http(session, rev_parsed, criadas=[])

        if self._turno_pula_llm_groq(texto, arquivos, session=session):
            parsed = self._montar_resposta_sem_llm(
                session, estado_antes, arquivos, texto_limpo
            )
            self._processar_anexos_turno(
                session,
                arquivos_turno,
                texto=texto,
                rascunho=list(session.demandas_rascunho or parsed.get("demandas_extraidas") or []),
                indices_demanda=anexo_demanda_indices,
                parsed=parsed,
            )
            historico.append(
                {"role": "assistant", "content": json.dumps(parsed, ensure_ascii=False)}
            )
            self._persistir_apos_turno(session, historico, parsed)
            return self._montar_resposta_http(session, parsed, criadas=[])

        faq_imediata = self._turno_resposta_faq_imediata(texto_limpo, session)
        if faq_imediata:
            parsed = faq_imediata
            historico.append(
                {"role": "assistant", "content": json.dumps(parsed, ensure_ascii=False)}
            )
            self._persistir_apos_turno(session, historico, parsed)
            return self._montar_resposta_http(session, parsed, criadas=[])

        corpus_servico_turno = (
            int(corpus_sinapse_servico_id) if corpus_sinapse_servico_id else None
        )
        parsed, historico_pos_llm = self._rodada_llm_com_triagem(
            historico,
            session=session,
            corpus_servico_id=corpus_servico_turno,
        )
        parsed = self._tentar_aplicar_escolha_sinapse_numerica(historico, texto, parsed)
        merged = self._merge_demandas_rascunho(session.demandas_rascunho, parsed.get("demandas_extraidas"))
        self._pre_classificar_faq_em_lista(merged, texto_sessao=texto)
        self._aplicar_classificacao_competencia_rascunho(merged, texto_sessao=texto)
        if self._usuario_modo_indicacao(usuario):
            self._marcar_rascunho_indicacao(merged, usuario)
        self._limpar_triagem_fora_competencia(merged)
        bloqueados_pos = self._indices_fora_competencia(merged)
        if bloqueados_pos and len(bloqueados_pos) == len(merged):
            parsed["acionar_triagem_sinapse"] = False
            msg_fc = self._mensagem_chat_fora_competencia(merged)
            if msg_fc:
                parsed["resposta_agente"] = msg_fc
        if corpus_servico_turno:
            self._aplicar_preselecao_corpus_atalho(
                merged,
                corpus_servico_turno,
                parsed,
                texto_sessao=texto,
                eixo_id=(corpus_atalho_id or "").strip() or None,
            )
            parsed["acionar_triagem_sinapse"] = False
        ChatbotService._limpar_servico_nao_confirmado(merged)
        if self._expandir_demandas_compostas_no_rascunho(merged, texto):
            if not corpus_servico_turno:
                self._atualizar_triagem_demandas(session, merged, forcar=True)
        ChatbotService._normalizar_lista_demandas_compostas(merged)
        merged = self._preservar_relato_rascunho(session, merged)
        if not corpus_servico_turno:
            self._retriagem_pendentes_se_necessario(session, merged, ultimo_texto=texto)
        parsed["demandas_extraidas"] = merged
        self._processar_anexos_turno(
            session,
            arquivos_turno,
            texto=texto,
            rascunho=merged,
            indices_demanda=anexo_demanda_indices,
            parsed=parsed,
        )
        self._refinar_apos_escolha_numerica(parsed, texto)
        self._fallback_endereco_e_resumo(parsed, texto)
        self._fallback_coleta_sem_resposta_llm(parsed, texto)

        demandas_criadas: list[dict[str, Any]] = []
        confirm_llm = parsed.get("confirmar_criacao_demandas") is True
        confirm_curto = bool(_CONFIRM_RE.search(texto)) and len(texto) < 96
        if estado_antes == ChatSession.ESTADO_VALIDACAO_FINAL and (confirm_llm or confirm_curto):
            rascunho = parsed.get("demandas_extraidas")
            if not rascunho:
                rascunho = list(session.demandas_rascunho or [])
            modo_ind = self._usuario_modo_indicacao(usuario)
            if modo_ind:
                rascunho_filtrado = self._filtrar_rascunho_para_materializacao(rascunho)
                sem_servico = self._indices_demandas_sem_servico_confirmado(rascunho_filtrado)
                if sem_servico:
                    nums = ", ".join(str(i + 1) for i in sem_servico)
                    parsed["resposta_agente"] = (
                        f"Antes de gerar a indicação, confirme o serviço da carta ou registre "
                        f"como tendência na(s) solicitação(ões) {nums}."
                    )
                    parsed["estado_atual"] = ChatSession.ESTADO_VALIDACAO_FINAL
                incompletos = self._indices_indicacao_incompleta(rascunho_filtrado)
                if not sem_servico and incompletos:
                    nums = ", ".join(str(i + 1) for i in incompletos)
                    parsed["resposta_agente"] = (
                        f"Antes de gerar o rascunho, vincule vereadores e informe o número "
                        f"na(s) solicitação(ões) {nums}."
                    )
                    parsed["estado_atual"] = ChatSession.ESTADO_VALIDACAO_FINAL
                elif not sem_servico and not self._sessao_tem_anexo_pdf(session):
                    parsed["resposta_agente"] = (
                        "Anexe o PDF da indicação assinada pelos vereadores antes de confirmar."
                    )
                    parsed["estado_atual"] = ChatSession.ESTADO_VALIDACAO_FINAL
                elif not sem_servico:
                    demandas_criadas = self._materializar_demandas(
                        usuario, rascunho_filtrado, session=session
                    )
            else:
                sem_servico = self._indices_demandas_sem_servico_confirmado(rascunho)
                if sem_servico:
                    nums = ", ".join(str(i + 1) for i in sem_servico)
                    parsed["resposta_agente"] = (
                        f"Antes de gerar os ofícios, confirme o serviço da carta para a(s) solicitação(ões) "
                        f"{nums} no painel «Serviço na carta» (lado direito) ou diga qual opção da lista corresponde."
                    )
                    parsed["estado_atual"] = ChatSession.ESTADO_VALIDACAO_FINAL
                else:
                    informativos = self._indices_servico_informativo(rascunho)
                    if informativos:
                        nums = ", ".join(str(i + 1) for i in informativos)
                        parsed["resposta_agente"] = (
                            f"A(s) solicitação(ões) {nums} apontam para serviço(s) "
                            f"«somente orientação» e não podem virar ofício. "
                            f"Consulte a orientação no painel ou escolha outro serviço."
                        )
                        parsed["estado_atual"] = ChatSession.ESTADO_VALIDACAO_FINAL
                    else:
                        incoerentes = self._indices_servico_incoerente(rascunho)
                        if incoerentes:
                            nums = ", ".join(str(i + 1) for i in incoerentes)
                            parsed["resposta_agente"] = (
                                f"O serviço escolhido não parece combinar com o pedido na(s) solicitação(ões) {nums}. "
                                "Ajuste a opção da carta no painel antes de confirmar."
                            )
                            parsed["estado_atual"] = ChatSession.ESTADO_VALIDACAO_FINAL
                        else:
                            demandas_criadas = self._materializar_demandas(
                                usuario, rascunho, session=session
                            )
            parsed["confirmar_criacao_demandas"] = False
            if demandas_criadas:
                parsed["estado_atual"] = ChatSession.ESTADO_COLETA_DADOS
                parsed["demandas_extraidas"] = []
                resumos = [
                    f"#{x['id']} {x.get('titulo', 'Demanda')} ({x.get('servico_nome', 'serviço')})"
                    for x in demandas_criadas
                ]
                ids_txt = ", ".join(str(x["id"]) for x in demandas_criadas)
                oficio_url = next((x.get("oficio_url") for x in demandas_criadas if x.get("oficio_url")), None)
                parsed["resposta_agente"] = (
                    f"Criei {len(demandas_criadas)} demanda(s) em rascunho: {ids_txt}. "
                    + " · ".join(resumos[:4])
                    + ". Revise na lista de demandas antes do protocolo."
                    + (f" Ofício em PDF disponível no anexo da demanda #{demandas_criadas[0]['id']}." if oficio_url else "")
                )
                historico_pos_llm.append(
                    {
                        "role": "system",
                        "content": (
                            "[SGDL] Demandas criadas com sucesso: "
                            + json.dumps(demandas_criadas, ensure_ascii=False)
                        ),
                    }
                )
            else:
                logger.warning(
                    "Copiloto: usuário confirmou mas nenhuma Demanda foi criada (rascunho=%s).",
                    rascunho,
                )
                parsed["resposta_agente"] = (
                    "Quase lá: não consegui amarrar o serviço escolhido ao cadastro local. "
                    "Descreva de novo qual serviço da carta faz mais sentido, ou abra pelo cadastro "
                    "tradicional de demandas; o protocolo pode revisar o vínculo com a carta Sinapse."
                )

        self._garantir_resposta_agente_nao_vazia(parsed)
        self._forcar_regras_estado_rigidas(parsed, pos_sinapse=False, session=session)

        self._persistir_apos_turno(session, historico_pos_llm, parsed)
        parsed["demandas_extraidas"] = list(session.demandas_rascunho or [])
        return self._montar_resposta_http(session, parsed, criadas=demandas_criadas)

    @staticmethod
    def _mensagem_eh_somente_anexo(texto: str) -> bool:
        t = (texto or "").strip()
        if not t:
            return True
        if _TEXTO_ANEXO_UI_RE.match(t):
            return True
        return bool(
            re.match(
                r"^segue\s*\(?m?\)?\s+anexo\s*\(?s?\)?"
                r"(?:\s+para\s+an[aá]lise(?:\s+da\s+solicita[cç][aã]o)?)?\.?$",
                t,
                re.IGNORECASE,
            )
        )

    @staticmethod
    def _normalizar_comando_usuario(texto: str) -> str:
        """Remove aspas/colchetes que o usuário cola junto com comandos do fluxo."""
        t = (texto or "").strip()
        while len(t) >= 2 and t[0] in '"\'«»“”‘’' and t[-1] in '"\'«»“”‘’':
            t = t[1:-1].strip()
        return t.strip()

    def _turno_pula_llm_groq(
        self, texto: str, arquivos: list[Any], *, session: ChatSession | None = None
    ) -> bool:
        """Comandos de fluxo e coleta de endereço não passam pelo Groq (evita loop)."""
        t = self._normalizar_comando_usuario(texto)
        if arquivos and self._mensagem_eh_somente_anexo(t):
            rascunho = list(session.demandas_rascunho or []) if session else []
            if not self._rascunho_tem_problema_util(rascunho):
                return False
            return True
        if (
            session is not None
            and session.estado_atual == ChatSession.ESTADO_VALIDACAO_FINAL
            and _TEXTO_RECUSA_VALIDACAO_RE.match(t)
        ):
            return True
        if _TEXTOS_PULAR_ENDERECO_RE.search(t):
            return True
        if _TEXTO_CONFIRMAR_LOCAL_RE.match(t):
            return True
        if _TEXTO_CONFIRMAR_ANEXOS_RE.match(t):
            return True
        if _TEXTO_CONTINUAR_SEM_ANEXOS_RE.match(t):
            return True
        if (
            session is not None
            and session.estado_atual == ChatSession.ESTADO_VALIDACAO_FINAL
            and t
            and not _TEXTO_FINALIZAR_RE.match(t)
            and not (_CONFIRM_RE.search(t) and len(t) < 96)
            and ChatbotService._texto_parece_ter_referencia_local(t)
        ):
            return True
        if (
            session is not None
            and session.estado_atual == ChatSession.ESTADO_COLETA_ENDERECO
            and t
            and not _TEXTO_FINALIZAR_RE.match(t)
        ):
            return True
        return False

    def _montar_resposta_sem_llm(
        self,
        session: ChatSession,
        estado_antes: str,
        arquivos: list[Any],
        texto: str,
    ) -> dict[str, Any]:
        rascunho = list(session.demandas_rascunho or [])
        texto_limpo = (texto or "").strip()

        if arquivos:
            qtd = len(arquivos)
            plano = self._planejar_passo_fluxo(session, rascunho)
            if plano.get("estado_atual") == ChatSession.ESTADO_VALIDACAO_FINAL:
                msg = (
                    f"Recebi {qtd} arquivo(s). Revise o painel e confirme abaixo "
                    "(ou diga «sim» / «finalizar») para gerar os rascunhos."
                )
            else:
                msg = (
                    f"Recebi {qtd} arquivo(s). {plano.get('resposta_agente', '')}"
                ).strip()
            plano["resposta_agente"] = msg
            session.estado_atual = plano["estado_atual"]
            session.demandas_rascunho = rascunho
            session.save(update_fields=["estado_atual", "demandas_rascunho", "atualizado_em"])
            return plano

        if _TEXTO_RECUSA_VALIDACAO_RE.match(texto_limpo):
            return self._processar_recusa_validacao_final(session)

        if _TEXTOS_PULAR_ENDERECO_RE.search(texto_limpo):
            self._processar_coleta_endereco_usuario(rascunho, texto_limpo)
            session.demandas_rascunho = rascunho
            plano = self._planejar_passo_fluxo(session, rascunho)
            session.estado_atual = plano["estado_atual"]
            session.save(update_fields=["estado_atual", "demandas_rascunho", "atualizado_em"])
            return plano

        m_conf_local = _TEXTO_CONFIRMAR_LOCAL_RE.match(texto_limpo)
        if m_conf_local:
            indice_raw = m_conf_local.group(1)
            indice_alvo = int(indice_raw) - 1 if indice_raw else None
            if indice_alvo is None:
                indice_rev = self._indice_demanda_em_revisao(rascunho, "local")
                if indice_rev is not None:
                    indice_alvo = indice_rev
            if self._confirmar_local_inferido_rascunho(
                rascunho, indice_demanda=indice_alvo, session=session
            ):
                revisao_encerrada = False
                if indice_alvo is not None and 0 <= indice_alvo < len(rascunho):
                    item_rev = rascunho[indice_alvo]
                    if isinstance(item_rev, dict) and item_rev.pop("_revisao_etapa", None):
                        revisao_encerrada = True
                session.demandas_rascunho = rascunho
                plano = self._planejar_passo_fluxo(session, rascunho)
                if revisao_encerrada:
                    plano["revisao_encerrada"] = True
                session.estado_atual = plano["estado_atual"]
                session.save(update_fields=["estado_atual", "demandas_rascunho", "atualizado_em"])
                return plano
            plano = {
                "usuario_forneceu_endereco_real": False,
                "resposta_agente": (
                    "Ainda não identifiquei um local válido para confirmar. "
                    "Informe rua e bairro, CEP, parque ou use o GPS."
                ),
                "estado_atual": ChatSession.ESTADO_COLETA_ENDERECO,
                "demandas_extraidas": rascunho,
                "acionar_triagem_sinapse": False,
                "confirmar_criacao_demandas": False,
            }
            session.estado_atual = plano["estado_atual"]
            session.save(update_fields=["estado_atual", "atualizado_em"])
            return plano

        m_conf_anexos = _TEXTO_CONFIRMAR_ANEXOS_RE.match(texto_limpo)
        if m_conf_anexos:
            indice_rev = self._indice_demanda_em_revisao(rascunho, "anexos")
            if indice_rev is not None and isinstance(rascunho[indice_rev], dict):
                rascunho[indice_rev].pop("_revisao_etapa", None)
            session.demandas_rascunho = rascunho
            plano = self._planejar_passo_fluxo(session, rascunho, apos_sem_anexos=True)
            if indice_rev is not None:
                qtd = session.anexos_sessao.filter(indice_demanda=indice_rev).count()
                plano["revisao_encerrada"] = True
                plano["resposta_agente"] = (
                    f"Documentos da solicitação {indice_rev + 1} confirmados"
                    + (f" ({qtd} arquivo(s))." if qtd else ".")
                    + " "
                    + (plano.get("resposta_agente") or "")
                ).strip()
            else:
                qtd = session.anexos_sessao.count()
                if qtd:
                    plano["resposta_agente"] = (
                        f"Documentos confirmados ({qtd} arquivo(s) na sessão). "
                        + (plano.get("resposta_agente") or "")
                    ).strip()
            session.estado_atual = plano["estado_atual"]
            session.save(update_fields=["estado_atual", "demandas_rascunho", "atualizado_em"])
            return plano

        if _TEXTO_CONTINUAR_SEM_ANEXOS_RE.match(texto_limpo):
            if not self._rascunho_tem_endereco_suficiente(rascunho):
                session.estado_atual = ChatSession.ESTADO_COLETA_ENDERECO
                plano = {
                    "usuario_forneceu_endereco_real": False,
                    "resposta_agente": (
                        "Antes dos anexos, informe o local (rua e bairro, CEP ou parque) "
                        "ou digite «continuar sem local»."
                    ),
                    "estado_atual": ChatSession.ESTADO_COLETA_ENDERECO,
                    "demandas_extraidas": rascunho,
                    "acionar_triagem_sinapse": False,
                    "confirmar_criacao_demandas": False,
                }
                session.save(update_fields=["estado_atual", "atualizado_em"])
                return plano
            plano = self._planejar_passo_fluxo(session, rascunho, apos_sem_anexos=True)
            session.estado_atual = plano["estado_atual"]
            session.demandas_rascunho = rascunho
            session.save(update_fields=["estado_atual", "demandas_rascunho", "atualizado_em"])
            return plano

        if estado_antes == ChatSession.ESTADO_COLETA_ENDERECO and texto_limpo:
            if self._processar_coleta_endereco_usuario(rascunho, texto_limpo):
                session.demandas_rascunho = rascunho
                if self._rascunho_tem_endereco_suficiente(rascunho):
                    plano = self._planejar_passo_fluxo(session, rascunho)
                else:
                    plano = {
                        "usuario_forneceu_endereco_real": True,
                        "resposta_agente": self._mensagem_revisar_local_inferido(rascunho),
                        "estado_atual": ChatSession.ESTADO_COLETA_ENDERECO,
                        "demandas_extraidas": rascunho,
                        "acionar_triagem_sinapse": False,
                        "confirmar_criacao_demandas": False,
                    }
                session.estado_atual = plano["estado_atual"]
                session.save(update_fields=["estado_atual", "demandas_rascunho", "atualizado_em"])
                return plano
            plano = {
                "usuario_forneceu_endereco_real": False,
                "resposta_agente": (
                    "Não reconheci o local. Envie CEP, rua com bairro, nome do parque "
                    "ou digite «continuar sem local»."
                ),
                "estado_atual": ChatSession.ESTADO_COLETA_ENDERECO,
                "demandas_extraidas": rascunho,
                "acionar_triagem_sinapse": False,
                "confirmar_criacao_demandas": False,
            }
            session.estado_atual = plano["estado_atual"]
            session.save(update_fields=["estado_atual", "atualizado_em"])
            return plano

        if (
            estado_antes == ChatSession.ESTADO_VALIDACAO_FINAL
            and texto_limpo
            and self._texto_parece_ter_referencia_local(texto_limpo)
            and not _TEXTO_FINALIZAR_RE.match(texto_limpo)
        ):
            for item in rascunho:
                if isinstance(item, dict) and not item.get("descartada"):
                    item["requer_localizacao"] = True
            if self._processar_coleta_endereco_usuario(rascunho, texto_limpo):
                session.demandas_rascunho = rascunho
                if self._rascunho_tem_endereco_suficiente(rascunho):
                    plano = self._planejar_passo_fluxo(session, rascunho)
                else:
                    plano = {
                        "usuario_forneceu_endereco_real": True,
                        "resposta_agente": self._mensagem_revisar_local_inferido(rascunho),
                        "estado_atual": ChatSession.ESTADO_COLETA_ENDERECO,
                        "demandas_extraidas": rascunho,
                        "acionar_triagem_sinapse": False,
                        "confirmar_criacao_demandas": False,
                    }
                session.estado_atual = plano["estado_atual"]
                session.save(update_fields=["estado_atual", "demandas_rascunho", "atualizado_em"])
                return plano
            plano = {
                "usuario_forneceu_endereco_real": False,
                "resposta_agente": (
                    "Não reconheci o local com clareza. Informe rua e bairro, CEP completo "
                    "ou referência do local (ex.: praça, esquina)."
                ),
                "estado_atual": ChatSession.ESTADO_COLETA_ENDERECO,
                "demandas_extraidas": rascunho,
                "acionar_triagem_sinapse": False,
                "confirmar_criacao_demandas": False,
            }
            session.estado_atual = plano["estado_atual"]
            session.save(update_fields=["estado_atual", "demandas_rascunho", "atualizado_em"])
            return plano

        plano = self._planejar_passo_fluxo(session, rascunho)
        session.estado_atual = plano["estado_atual"]
        session.demandas_rascunho = rascunho
        session.save(update_fields=["estado_atual", "demandas_rascunho", "atualizado_em"])
        return plano

    def _obter_sessao(self, usuario, session_id: str | None) -> ChatSession:
        if session_id:
            try:
                uid = uuid.UUID(str(session_id))
            except (ValueError, TypeError) as exc:
                raise ValueError("session_id inválido") from exc
            session = ChatSession.objects.filter(id=uid, autor=usuario).first()
            if not session:
                raise PermissionError("Sessão inexistente ou acesso negado.")
            return session
        return ChatSession.objects.create(autor=usuario)

    def _rodada_llm_com_triagem(
        self,
        historico: list[dict[str, Any]],
        *,
        session: ChatSession | None = None,
        corpus_servico_id: int | None = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Uma inferência Groq; triagem Sinapse vetorial aplicada no backend."""
        ultimo_usuario = ""
        for msg in reversed(historico):
            if isinstance(msg, dict) and msg.get("role") == "user":
                ultimo_usuario = (msg.get("content") or "").strip()
                break

        hist_llm = list(historico)
        gestao_msg = self._mensagem_gestao_operacional_rascunho(session)
        if gestao_msg:
            hist_llm.append({"role": "system", "content": gestao_msg})

        parsed = self._chamar_groq_json(hist_llm)
        if corpus_servico_id is not None:
            parsed["acionar_triagem_sinapse"] = False
        ChatbotService._limpar_servico_nao_confirmado(parsed.get("demandas_extraidas") or [])
        self._expandir_demandas_compostas(parsed, ultimo_usuario)
        ChatbotService._normalizar_lista_demandas_compostas(
            parsed.get("demandas_extraidas") or []
        )
        self._enriquecer_slot_e_triagem_por_contexto(ultimo_usuario, parsed)
        self._pre_classificar_faq_nas_demandas(parsed, texto_sessao=ultimo_usuario)
        dems_llm = parsed.get("demandas_extraidas")
        if isinstance(dems_llm, list):
            self._aplicar_classificacao_competencia_rascunho(
                dems_llm, texto_sessao=ultimo_usuario
            )
            self._aplicar_trilha_ouvidoria_rascunho(
                dems_llm, texto_sessao=ultimo_usuario
            )
            self._alinhar_resposta_agente_ouvidoria(parsed)
            self._alinhar_resposta_agente_faq(parsed)
        bloqueados = self._indices_fora_competencia(dems_llm if isinstance(dems_llm, list) else [])
        if bloqueados and len(bloqueados) == len(dems_llm or []):
            parsed["acionar_triagem_sinapse"] = False
            if not (parsed.get("resposta_agente") or "").strip():
                parsed["resposta_agente"] = self._mensagem_chat_fora_competencia(
                    dems_llm or []
                )
        self._forcar_regras_estado_rigidas(parsed, pos_sinapse=False, session=session)
        if parsed.get("usuario_forneceu_endereco_real") is True:
            self._preencher_endereco_do_texto_usuario(ultimo_usuario, parsed)
        historico_out = list(historico)
        n_demandas_antes_sinapse = len(parsed.get("demandas_extraidas") or [])

        if corpus_servico_id is not None:
            parsed["acionar_triagem_sinapse"] = False

        if parsed.get("acionar_triagem_sinapse"):
            dems_pre = parsed.get("demandas_extraidas")
            if isinstance(dems_pre, list) and all(
                isinstance(x, dict) and self._item_trilha_ouvidoria(x) for x in dems_pre
            ):
                parsed["acionar_triagem_sinapse"] = False
                self._alinhar_resposta_agente_ouvidoria(parsed)
        if parsed.get("acionar_triagem_sinapse"):
            marcador_sinapse = self._aplicar_triagem_sinapse_local(
                parsed,
                n_demandas_antes=n_demandas_antes_sinapse,
            )
            if marcador_sinapse:
                historico_out.append({"role": "system", "content": marcador_sinapse})
            else:
                parsed["acionar_triagem_sinapse"] = False
                if not (parsed.get("resposta_agente") or "").strip():
                    parsed["resposta_agente"] = (
                        "Não consegui consultar a carta de serviços neste momento "
                        "(texto insuficiente ou indisponibilidade técnica). "
                        "Pode repetir o que precisa e onde é, com rua ou bairro e CEP se tiver?"
                    )

        historico_out.append(
            {"role": "assistant", "content": json.dumps(parsed, ensure_ascii=False)}
        )
        return parsed, historico_out

    def _aplicar_triagem_sinapse_local(
        self,
        parsed: dict[str, Any],
        *,
        n_demandas_antes: int,
    ) -> str | None:
        """
        Executa busca na carta Sinapse e atualiza o rascunho sem segunda chamada ao LLM.
        Retorna texto de marcador para o histórico (escolha numérica no chat).
        """
        injecao, candidatos_ui, blocos_triagem = self._montar_injecao_sinapse(
            parsed.get("demandas_extraidas") or []
        )
        if not blocos_triagem:
            return None

        self._anexar_candidatos_triagem_a_parsed(parsed, blocos_triagem)
        self._podar_demandas_extras_sinapse(parsed, n_demandas_antes)
        dems_triagem = parsed.get("demandas_extraidas")
        if isinstance(dems_triagem, list):
            self._aplicar_classificacao_competencia_rascunho(dems_triagem)
            self._alinhar_resposta_agente_faq(parsed)
        parsed["acionar_triagem_sinapse"] = False
        self._forcar_regras_estado_rigidas(parsed, pos_sinapse=True, session=session)
        self._montar_resposta_pos_triagem_sinapse(parsed, blocos_triagem, candidatos_ui)
        msg_fc = self._mensagem_chat_fora_competencia(
            parsed.get("demandas_extraidas") if isinstance(parsed.get("demandas_extraidas"), list) else []
        )
        if msg_fc:
            parsed["resposta_agente"] = msg_fc
            parsed["estado_atual"] = ChatSession.ESTADO_COLETA_DADOS

        est = parsed.get("estado_atual")
        validos = {c[0] for c in ChatSession.ESTADO_CHOICES}
        if est not in validos:
            parsed["estado_atual"] = ChatSession.ESTADO_COLETA_DADOS

        return injecao or None

    def _montar_resposta_pos_triagem_sinapse(
        self,
        parsed: dict[str, Any],
        blocos: list[dict[str, Any]],
        candidatos_primeira: list[dict[str, Any]],
    ) -> None:
        """Mensagem curta no chat; candidatos com score só no card «Serviço na carta»."""
        dems = parsed.get("demandas_extraidas")
        if not isinstance(dems, list):
            dems = []
            parsed["demandas_extraidas"] = dems

        ra = (parsed.get("resposta_agente") or "").strip()

        if len(blocos) > 1:
            parsed["resposta_agente"] = self._mensagem_convite_carta_sinapse_painel(
                parsed, varias_solicitacoes=True
            )
            return

        cands: list[dict[str, Any]] = []
        if dems and isinstance(dems[0], dict):
            raw = dems[0].get("candidatos_sinapse")
            if isinstance(raw, list):
                cands = raw
        if not cands:
            cands = candidatos_primeira

        if len(cands) > 1:
            parsed["resposta_agente"] = self._mensagem_convite_carta_sinapse_painel(parsed)
            return

        if cands:
            self._sobrepor_lista_opcoes_sinapse(parsed, cands)
            if ra and len(ra) > 48 and parsed.get("estado_atual") != ChatSession.ESTADO_VALIDACAO_FINAL:
                parsed["resposta_agente"] = self._mensagem_convite_carta_sinapse_painel(parsed)
            return

        if not ra:
            parsed["resposta_agente"] = self._fallback_resposta_pre_triagem(parsed)

    @staticmethod
    def _linhas_opcoes_sinapse(candidatos: Any) -> list[str]:
        if not isinstance(candidatos, list):
            return []
        linhas: list[str] = []
        for i, c in enumerate(candidatos[:6], 1):
            if not isinstance(c, dict):
                continue
            tit = (c.get("titulo") or "serviço").strip()
            org = (c.get("orgao") or "").strip()
            pct = c.get("score")
            extra = f" ({org})" if org else ""
            score_txt = f" — {int(round(float(pct) * 100))}% similaridade" if pct is not None else ""
            linhas.append(f"{i}) {tit}{extra}{score_txt}")
        return linhas

    def _enriquecer_slot_e_triagem_por_contexto(
        self, ultimo_usuario: str, parsed: dict[str, Any]
    ) -> None:
        """Preenche texto_para_embedding e, em cutucadas, força triagem quando fizer sentido."""
        dems = parsed.get("demandas_extraidas")
        if not isinstance(dems, list):
            return
        for item in dems:
            if not isinstance(item, dict):
                continue
            te = (item.get("texto_para_embedding") or "").strip()
            if te:
                continue
            t = (item.get("titulo") or "").strip()
            d = (item.get("descricao") or "").strip()
            merged = f"{t} {d}".strip()
            if len(merged) >= 10:
                item["texto_para_embedding"] = merged[:500]

        precisa_servico = any(
            isinstance(x, dict)
            and not x.get("servico_local_id")
            and len((x.get("texto_para_embedding") or "").strip()) >= 12
            for x in dems
        )
        est = parsed.get("estado_atual")
        if not precisa_servico or est not in (
            None,
            "",
            ChatSession.ESTADO_COLETA_DADOS,
        ):
            return
        u = (ultimo_usuario or "").strip()
        cutucada = bool(_NUDGE_TRIAGEM_RE.match(u)) or u in ("?", "??", "?!")
        if (
            cutucada
            and parsed.get("usuario_forneceu_endereco_real") is True
            and not parsed.get("acionar_triagem_sinapse")
        ):
            parsed["acionar_triagem_sinapse"] = True

    @staticmethod
    def _item_vinculo_catalogo_resolvido(item: dict[str, Any]) -> bool:
        if item.get("corpus_preselecao_servico_id") or item.get("corpus_atalho_eixo_id"):
            if ChatbotService._servico_confirmado_pelo_usuario(item):
                return True
        if item.get("tendencia_id") or item.get("origem_vinculo") == Demanda.ORIGEM_VINCULO_TENDENCIA:
            return True
        if item.get("trilha_ouvidoria"):
            raw = item.get("sinapse_servico_id_sugerido") or item.get("servico_local_id")
            if raw is not None:
                try:
                    return sinapse_catalog.servico_existe(int(raw))
                except (TypeError, ValueError):
                    pass
        if not ChatbotService._servico_confirmado_pelo_usuario(item):
            return False
        raw = item.get("sinapse_servico_id_sugerido") or item.get("servico_local_id")
        if raw is None:
            return False
        try:
            return sinapse_catalog.servico_existe(int(raw))
        except (TypeError, ValueError):
            return False

    def _demandas_pendentes_vinculo_carta(self, dems: list[Any]) -> bool:
        return any(
            isinstance(x, dict)
            and not x.get("descartada")
            and not x.get("fora_competencia")
            and self._item_tem_problema_relato(x)
            and not self._item_vinculo_catalogo_resolvido(x)
            for x in (dems or [])
        )

    @staticmethod
    def _titulo_primeira_demanda(parsed: dict[str, Any]) -> str:
        dems = parsed.get("demandas_extraidas") or []
        if isinstance(dems, list) and dems and isinstance(dems[0], dict):
            t = (dems[0].get("titulo") or "").strip()
            if t:
                return t
        return "sua solicitação"

    @staticmethod
    def _mensagem_convite_carta_sinapse_painel(
        parsed: dict[str, Any], *, varias_solicitacoes: bool = False
    ) -> str:
        """Texto curto no chat; opções com score ficam só no card/painel (sem lista numerada)."""
        if varias_solicitacoes:
            return (
                "Consultei a carta de serviços para suas solicitações. "
                "Para cada item, escolha no painel «Serviço na carta» abaixo "
                "(ou use a última opção para registrar como tendência)."
            )
        titulo = ChatbotService._titulo_primeira_demanda(parsed)
        return (
            f"Para «{titulo}», encontrei opções na carta de serviços. "
            "Escolha no painel abaixo a que melhor corresponde "
            "(ou a última linha para registrar como tendência)."
        )

    @staticmethod
    def _resposta_escolha_carta_sinapse(parsed: dict[str, Any]) -> str:
        dems = parsed.get("demandas_extraidas") or []
        varias = isinstance(dems, list) and len(dems) > 1
        return ChatbotService._mensagem_convite_carta_sinapse_painel(
            parsed, varias_solicitacoes=varias
        )

    @staticmethod
    def _resposta_pedir_endereco_opcional(parsed: dict[str, Any]) -> str:
        dems = parsed.get("demandas_extraidas") or []
        titulo = "sua solicitação"
        item0: dict[str, Any] | None = None
        if isinstance(dems, list) and dems and isinstance(dems[0], dict):
            item0 = dems[0]
            t = (item0.get("titulo") or "").strip()
            if t:
                titulo = t
        requer = (
            ChatbotService._item_requer_localizacao(item0)
            if item0
            else False
        )
        if requer:
            detalhe = (
                "Informe logradouro, bairro e, se possível, o CEP — ajuda na localização no mapa. "
                "Também vale nome de parque/área ou só o bairro (ex.: «bairro Centro»)."
            )
        else:
            detalhe = (
                "Se quiser, informe logradouro, bairro e CEP (recomendado), "
                "ou o nome do parque/local (ex.: Parque Centenário)."
            )
        return (
            f"Serviço da carta confirmado para «{titulo}». {detalhe} "
            "Use «Usar minha localização», confirme o endereço inferido ou "
            "«continuar sem local» para seguir sem endereço."
        )

    @staticmethod
    def _resposta_pedir_endereco_indicacao(parsed: dict[str, Any]) -> str:
        dems = parsed.get("demandas_extraidas") or []
        titulo = "sua indicação"
        if isinstance(dems, list) and dems and isinstance(dems[0], dict):
            t = (dems[0].get("titulo") or "").strip()
            if t:
                titulo = t
        return (
            f"Indicação «{titulo}» registrada. O local é opcional: informe logradouro, bairro "
            "e CEP (recomendado), use «Usar minha localização» ou «continuar sem local». "
            "Depois anexaremos o PDF assinado e os dados da Câmara (vereadores e número)."
        )

    def _rascunho_endereco_indicacao_resolvido(self, rascunho: list[Any]) -> bool:
        for item in rascunho or []:
            if not isinstance(item, dict):
                continue
            if item.get("descartada") or item.get("fora_competencia"):
                continue
            if not item.get("modo_indicacao"):
                continue
            if not self._item_local_confirmado_usuario(item):
                return False
        return True

    @staticmethod
    def _rascunho_tem_problema_util(rascunho: list[Any]) -> bool:
        return any(
            isinstance(x, dict) and ChatbotService._item_tem_problema_relato(x)
            for x in (rascunho or [])
        )

    def _item_requer_localizacao_vinculada(self, item: dict[str, Any]) -> bool:
        if self._item_vinculo_catalogo_resolvido(item):
            return self._item_requer_localizacao(item)
        return self._item_requer_localizacao(item)

    def _rascunho_tem_endereco_suficiente(self, rascunho: list[Any]) -> bool:
        for item in rascunho or []:
            if not isinstance(item, dict):
                continue
            if item.get("fora_competencia") or item.get("descartada"):
                continue
            if not self._item_requer_localizacao_vinculada(item):
                continue
            if self._item_local_confirmado_usuario(item):
                continue
            return False
        return True

    @classmethod
    def _item_local_confirmado_usuario(cls, item: dict[str, Any]) -> bool:
        if item.get("endereco_opcional_dispensado"):
            return True
        if item.get("local_confirmado_usuario"):
            return True
        return False

    def _indice_demanda_em_revisao(
        self, rascunho: list[Any], etapa: str | None = None
    ) -> int | None:
        for i, item in enumerate(rascunho or []):
            if not isinstance(item, dict):
                continue
            rev = item.get("_revisao_etapa")
            if rev and (etapa is None or rev == etapa):
                return i
        return None

    def _itens_alvo_coleta_endereco(self, rascunho: list[Any]) -> list[dict[str, Any]]:
        indice_rev = self._indice_demanda_em_revisao(rascunho, "local")
        if indice_rev is not None:
            item = rascunho[indice_rev]
            return [item] if isinstance(item, dict) else []
        alvos: list[dict[str, Any]] = []
        for item in rascunho or []:
            if not isinstance(item, dict):
                continue
            if item.get("fora_competencia") or item.get("descartada"):
                continue
            if item.get("modo_indicacao"):
                if self._item_local_confirmado_usuario(item):
                    continue
                alvos.append(item)
                continue
            if not self._item_requer_localizacao_vinculada(item):
                if not (
                    item.get("corpus_aguarda_complemento")
                    and not self._item_local_confirmado_usuario(item)
                ):
                    continue
            if self._item_local_confirmado_usuario(item):
                continue
            alvos.append(item)
        return alvos

    def _processar_coleta_endereco_usuario(self, rascunho: list[Any], texto: str) -> bool:
        """Interpreta mensagem na etapa COLETA_ENDERECO (sem Groq)."""
        bruto = self._normalizar_comando_usuario(texto or "")
        if not bruto:
            return False
        if _TEXTOS_PULAR_ENDERECO_RE.search(bruto):
            alvos = self._itens_alvo_coleta_endereco(rascunho)
            for item in alvos:
                item["endereco_opcional_dispensado"] = True
                item["endereco"] = dict(_ENDERECO_VAZIO)
                item.pop("latitude", None)
                item.pop("longitude", None)
                item.pop("coordenadas_fonte", None)
                item.pop("_geo_chave", None)
                item.pop("endereco_informado_usuario", None)
                item.pop("local_confirmado_usuario", None)
                if item.get("_revisao_etapa") == "local":
                    item.pop("_revisao_etapa", None)
            return bool(alvos)
        t = self._texto_util_para_extracao_endereco(bruto)
        if not t:
            return False
        ext = self._extrair_endereco_livre(t)
        parque = self._extrair_nome_parque(t)
        if parque and not ext.get("logradouro"):
            ext["logradouro"] = parque
        from core.services.endereco_normalizacao import endereco_minimo_para_geocode

        if not endereco_minimo_para_geocode(
            ext.get("logradouro"), ext.get("bairro")
        ) and not any(ext.get(k) for k in ("cep", "numero")):
            return False
        alvos = self._itens_alvo_coleta_endereco(rascunho)
        if not alvos:
            return False
        geocoder = GeocodingService()
        for item in alvos:
            cur = item.get("endereco") if isinstance(item.get("endereco"), dict) else {}
            item["endereco"] = self._merge_endereco_dicts(cur, ext)
            item.pop("local_confirmado_usuario", None)
            item.pop("endereco_informado_usuario", None)
            self._sanitizar_endereco_demanda(item)
            end = item.get("endereco") if isinstance(item.get("endereco"), dict) else {}
            lat, lng, fonte = self._resolver_coordenadas_item(
                item,
                geocoder,
                logradouro=end.get("logradouro"),
                bairro=end.get("bairro"),
                cep=end.get("cep"),
            )
            if lat is not None and lng is not None:
                item["latitude"] = round(lat, 6)
                item["longitude"] = round(lng, 6)
                item["coordenadas_fonte"] = fonte
                item["_geo_chave"] = GeocodingService.chave_endereco(
                    end.get("logradouro"), end.get("bairro"), end.get("cep")
                )
            else:
                item.pop("latitude", None)
                item.pop("longitude", None)
                item.pop("coordenadas_fonte", None)
        return True

    def _mensagem_revisar_local_inferido(self, rascunho: list[Any]) -> str:
        from core.services.endereco_normalizacao import (
            endereco_resumo_humano,
            montar_alerta_geocode,
        )

        partes_msg: list[str] = []
        for item in rascunho or []:
            if not isinstance(item, dict) or item.get("endereco_opcional_dispensado"):
                continue
            if not self._item_requer_localizacao_vinculada(item):
                continue
            if self._item_local_confirmado_usuario(item):
                continue
            end = item.get("endereco") if isinstance(item.get("endereco"), dict) else {}
            resumo = endereco_resumo_humano(end)
            if resumo:
                partes_msg.append(f"Identifiquei: {resumo}.")
            alerta = montar_alerta_geocode(
                logradouro=end.get("logradouro"),
                bairro=end.get("bairro"),
                cep=end.get("cep"),
                latitude=item.get("latitude"),
                longitude=item.get("longitude"),
                endereco_informado=True,
            )
            if alerta:
                partes_msg.append(alerta)
        intro = " ".join(partes_msg).strip()
        if intro:
            return (
                f"{intro} Confira no mapa e clique em «Confirmar local», "
                "complete o endereço (CEP recomendado) ou use «continuar sem local»."
            )
        return (
            "Informe logradouro e bairro (ou CEP), confira no mapa e clique em "
            "«Confirmar local», ou use «continuar sem local»."
        )

    @staticmethod
    def _extrair_nome_parque(texto: str) -> str | None:
        """Extrai só o nome do parque (ex.: «Parque Centenário»), sem o restante do pedido."""
        t = (texto or "").strip()
        if not t or "parque" not in t.lower():
            return None
        m = _PARQUE_EXTRACAO_RE.search(t)
        if not m:
            return None
        palavras: list[str] = []
        for bruto in m.group(1).split():
            w = bruto.strip(".,;:!?\"'()")
            if not w:
                continue
            wl = w.lower()
            if wl in _STOP_PALAVRA_PARQUE or re.match(r"^\d", wl):
                break
            palavras.append(w)
        if not palavras:
            return None
        nome = "Parque " + " ".join(p.capitalize() for p in palavras[:4])
        return nome if len(nome) <= 80 else None

    @staticmethod
    def _item_requer_localizacao(item: dict[str, Any] | None) -> bool:
        """Heurística: serviços de local físico costumam precisar de endereço/área."""
        if not item:
            return False
        if item.get("trilha_ouvidoria"):
            return False
        if item.get("endereco_opcional_dispensado"):
            return False
        if item.get("corpus_atalho_eixo_id") or item.get("corpus_preselecao_servico_id"):
            return True
        if item.get("corpus_aguarda_complemento"):
            return True
        partes = [
            (item.get("titulo") or ""),
            (item.get("descricao") or ""),
            (item.get("texto_para_embedding") or ""),
        ]
        svc = item.get("servico") if isinstance(item.get("servico"), dict) else {}
        partes.append(str(svc.get("nome") or ""))
        for c in item.get("candidatos_sinapse") or []:
            if isinstance(c, dict):
                partes.append(str(c.get("titulo") or ""))
        blob = " ".join(partes).lower()
        chaves = (
            "zeladoria",
            "tapa",
            "buraco",
            "lombada",
            "reserva",
            "espaço",
            "espaco",
            "parque",
            "evento",
            "reforma",
            "implanta",
            "poda",
            "capina",
            "iluminação",
            "iluminacao",
            "coleta",
            "limpeza",
            "vistoria",
            "alvará",
            "alvara",
            "lote",
            "obra",
            "ronda",
            "gcm",
            "patrulh",
            "segurança",
            "seguranca",
            "estrada",
            "manutenção",
            "manutencao",
            "nivelamento",
            "cascalh",
            "varri",
            "roçag",
            "rocag",
            "sinaliza",
            "semáforo",
            "semaforo",
            "via ",
            "rua",
            "avenida",
            "bairro",
        )
        return any(k in blob for k in chaves)

    @staticmethod
    def _extrair_bairro_explicito(texto: str) -> str | None:
        """Só extrai bairro com marcador explícito («bairro Centro»), não trechos do relato."""
        t = ChatbotService._texto_util_para_extracao_endereco(texto or "")
        if not t:
            return None
        m = _BAIRRO_EXPLICITO_RE.search(t)
        if not m:
            return None
        cand = m.group(1).strip(" .,;")
        if ChatbotService._valor_campo_endereco_valido("bairro", cand):
            return cand[:120]
        return None

    @staticmethod
    def _limpar_bairro(valor: str | None, texto_contexto: str | None = None) -> str | None:
        v = (valor or "").strip()
        if v and ChatbotService._valor_campo_endereco_valido("bairro", v):
            return v[:120]
        for fonte in (texto_contexto or "", valor or ""):
            ext = ChatbotService._extrair_bairro_explicito(fonte)
            if ext:
                return ext
        return None

    @staticmethod
    def _sanitizar_endereco_demanda(item: dict[str, Any]) -> None:
        """Remove logradouro/bairro inválidos (ex.: frase inteira do pedido colada pelo LLM)."""
        end = item.get("endereco") if isinstance(item.get("endereco"), dict) else {}
        if not any(
            (end.get(k) or "").strip()
            for k in ("cep", "logradouro", "bairro", "numero", "complemento")
        ):
            item["endereco"] = dict(_ENDERECO_VAZIO)
            return
        logr = ChatbotService._limpar_logradouro(
            (end.get("logradouro") or "").strip() or None,
            texto_contexto=None,
        )
        bairro = ChatbotService._limpar_bairro((end.get("bairro") or "").strip() or None)
        cep = (end.get("cep") or "").strip() or None
        if cep and not ChatbotService._valor_campo_endereco_valido("cep", cep):
            cep = None
        if logr and not ChatbotService._valor_campo_endereco_valido("logradouro", logr):
            logr = None
        if bairro and not ChatbotService._valor_campo_endereco_valido("bairro", bairro):
            bairro = None
        if not logr:
            bairro = None
        item["endereco"] = {
            "cep": cep,
            "logradouro": logr,
            "numero": end.get("numero") if logr else None,
            "bairro": bairro,
            "complemento": end.get("complemento") if logr else None,
        }

    @staticmethod
    def _sanitizar_enderecos_demandas(dems: list[Any]) -> None:
        for item in dems:
            if isinstance(item, dict):
                ChatbotService._sanitizar_endereco_demanda(item)

    def _planejar_passo_fluxo(
        self,
        session: ChatSession,
        rascunho: list[Any],
        *,
        apos_sem_anexos: bool = False,
    ) -> dict[str, Any]:
        """Próximo passo determinístico: carta → endereço → anexos → validação."""
        texto_sessao = self._texto_usuario_da_sessao(session)
        usuario = session.autor
        modo_ind = self._usuario_modo_indicacao(usuario)
        if modo_ind:
            self._marcar_rascunho_indicacao(rascunho, usuario)
        self._aplicar_classificacao_competencia_rascunho(rascunho, texto_sessao=texto_sessao)
        if modo_ind:
            self._marcar_rascunho_indicacao(rascunho, usuario)
        bloqueados = self._indices_fora_competencia(rascunho)
        if bloqueados:
            session.estado_atual = ChatSession.ESTADO_COLETA_DADOS
            return {
                "usuario_forneceu_endereco_real": False,
                "resposta_agente": self._mensagem_chat_fora_competencia(rascunho),
                "estado_atual": ChatSession.ESTADO_COLETA_DADOS,
                "demandas_extraidas": rascunho,
                "acionar_triagem_sinapse": False,
                "confirmar_criacao_demandas": False,
            }

        sem_servico = self._indices_demandas_sem_servico_confirmado(rascunho)
        if sem_servico:
            return {
                "usuario_forneceu_endereco_real": False,
                "resposta_agente": self._resposta_escolha_carta_sinapse(
                    {"demandas_extraidas": rascunho}
                ),
                "estado_atual": ChatSession.ESTADO_COLETA_DADOS,
                "demandas_extraidas": rascunho,
                "acionar_triagem_sinapse": True,
                "confirmar_criacao_demandas": False,
            }

        self._sanitizar_enderecos_demandas(rascunho)

        if modo_ind:
            if not self._rascunho_endereco_indicacao_resolvido(rascunho):
                session.estado_atual = ChatSession.ESTADO_COLETA_ENDERECO
                return {
                    "usuario_forneceu_endereco_real": False,
                    "resposta_agente": self._resposta_pedir_endereco_indicacao(
                        {"demandas_extraidas": rascunho}
                    ),
                    "estado_atual": ChatSession.ESTADO_COLETA_ENDERECO,
                    "demandas_extraidas": rascunho,
                    "acionar_triagem_sinapse": False,
                    "confirmar_criacao_demandas": False,
                }

            session.estado_atual = ChatSession.ESTADO_VALIDACAO_FINAL
            metadados_ok = not self._indices_indicacao_incompleta(rascunho)
            if apos_sem_anexos and metadados_ok:
                msg = (
                    "Revise serviço/tendência, vereadores, número e PDF no painel abaixo e confirme "
                    "para gerar o rascunho da indicação."
                )
            elif apos_sem_anexos:
                msg = (
                    "Revise serviço/tendência, vereadores e número da Câmara no painel abaixo e confirme "
                    "para gerar o rascunho da indicação."
                )
            elif not self._sessao_tem_anexo_pdf(session):
                msg = (
                    "Anexe o PDF da indicação com as assinaturas dos vereadores no bloco "
                    "de documentos abaixo. Depois informe vereadores e número para gerar o rascunho."
                )
            elif not metadados_ok:
                msg = (
                    "PDF recebido. Confirme o envio dos anexos; em seguida vincule os vereadores "
                    "e informe o número da indicação para gerar o rascunho."
                )
            else:
                msg = (
                    "Tudo pronto. Revise serviço/tendência, vereadores, número e PDF e confirme para gerar o rascunho."
                )
            return {
                "usuario_forneceu_endereco_real": False,
                "resposta_agente": msg,
                "estado_atual": ChatSession.ESTADO_VALIDACAO_FINAL,
                "demandas_extraidas": rascunho,
                "acionar_triagem_sinapse": False,
                "confirmar_criacao_demandas": False,
            }

        forneceu = self._rascunho_tem_endereco_suficiente(rascunho)
        if not forneceu:
            session.estado_atual = ChatSession.ESTADO_COLETA_ENDERECO
            return {
                "usuario_forneceu_endereco_real": False,
                "resposta_agente": self._resposta_pedir_endereco_opcional(
                    {"demandas_extraidas": rascunho}
                ),
                "estado_atual": ChatSession.ESTADO_COLETA_ENDERECO,
                "demandas_extraidas": rascunho,
                "acionar_triagem_sinapse": False,
                "confirmar_criacao_demandas": False,
            }

        session.estado_atual = ChatSession.ESTADO_VALIDACAO_FINAL
        if apos_sem_anexos:
            msg = (
                "Sem anexos complementares. Revise o resumo no painel e confirme abaixo "
                "(ou diga «sim» / «finalizar») para gerar os ofícios em rascunho."
            )
        else:
            msg = (
                "Local confirmado. Deseja anexar fotos ou PDFs? Use o bloco abaixo "
                "ou digite «continuar sem anexos». Em seguida confirme para gerar os rascunhos."
            )
        return {
            "usuario_forneceu_endereco_real": True,
            "resposta_agente": msg,
            "estado_atual": ChatSession.ESTADO_VALIDACAO_FINAL,
            "demandas_extraidas": rascunho,
            "acionar_triagem_sinapse": False,
            "confirmar_criacao_demandas": False,
        }

    def _propagar_anexos_indices_rascunho(self, session: ChatSession) -> None:
        rascunho = list(session.demandas_rascunho or [])
        anexos_sessao = list(session.anexos_sessao.order_by("criado_em"))
        if not anexos_sessao or not rascunho:
            return
        if len(rascunho) == 1 and anexos_sessao:
            item = rascunho[0]
            if isinstance(item, dict) and not item.get("anexos_indices"):
                item["anexos_indices"] = list(range(len(anexos_sessao)))
                session.demandas_rascunho = rascunho
                session.save(update_fields=["demandas_rascunho", "atualizado_em"])
            return
        mapa = self._mapa_anexos_por_demanda(
            anexos_sessao, rascunho, [None] * len(rascunho)
        )
        alterou = False
        for dem_idx, item in enumerate(rascunho):
            if not isinstance(item, dict):
                continue
            idxs = sorted(mapa.get(dem_idx, set()))
            if item.get("anexos_indices") != idxs:
                item["anexos_indices"] = idxs
                alterou = True
        if alterou:
            session.demandas_rascunho = rascunho
            session.save(update_fields=["demandas_rascunho", "atualizado_em"])

    def _processar_finalizar_ou_confirmar(
        self,
        session: ChatSession,
        usuario,
        historico: list[dict[str, Any]],
        texto: str,
        *,
        indices_aprovados: list[int] | None = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """«finalizar» / confirmação curta: gera rascunhos se o fluxo estiver completo."""
        rascunho = list(session.demandas_rascunho or [])
        demandas_criadas: list[dict[str, Any]] = []

        plano = self._planejar_passo_fluxo(session, rascunho)
        if plano.get("estado_atual") != ChatSession.ESTADO_VALIDACAO_FINAL:
            session.save(update_fields=["demandas_rascunho", "estado_atual", "atualizado_em"])
            return plano, demandas_criadas

        modo_ind = self._usuario_modo_indicacao(usuario)
        rascunho_filtrado = self._filtrar_rascunho_para_materializacao(
            rascunho, indices_aprovados=indices_aprovados
        )
        if not rascunho_filtrado:
            parsed = {
                **plano,
                "resposta_agente": (
                    "Nenhuma solicitação foi marcada para gerar rascunho. "
                    "Aprove pelo menos um item no painel ou na etapa final."
                ),
            }
            return parsed, demandas_criadas

        if modo_ind:
            incompletos = self._indices_indicacao_incompleta(rascunho_filtrado)
            sem_servico = self._indices_demandas_sem_servico_confirmado(rascunho_filtrado)
            if sem_servico:
                nums = ", ".join(str(i + 1) for i in sem_servico)
                parsed = {
                    **plano,
                    "resposta_agente": (
                        f"Antes de finalizar, confirme o serviço da carta ou registre como tendência "
                        f"na(s) solicitação(ões) {nums}."
                    ),
                }
                return parsed, demandas_criadas
            if incompletos:
                nums = ", ".join(str(i + 1) for i in incompletos)
                parsed = {
                    **plano,
                    "resposta_agente": (
                        f"Antes de finalizar, vincule vereadores e informe o número da indicação "
                        f"na(s) solicitação(ões) {nums}."
                    ),
                }
                return parsed, demandas_criadas
            if not self._sessao_tem_anexo_pdf(session):
                parsed = {
                    **plano,
                    "resposta_agente": (
                        "Anexe o PDF da indicação assinada pelos vereadores antes de gerar o rascunho."
                    ),
                }
                return parsed, demandas_criadas
        else:
            sem_servico = self._indices_demandas_sem_servico_confirmado(rascunho)
            if sem_servico:
                return plano, demandas_criadas

            incoerentes = self._indices_servico_incoerente(rascunho)
            if incoerentes:
                nums = ", ".join(str(i + 1) for i in incoerentes)
                parsed = {
                    **plano,
                    "resposta_agente": (
                        f"Antes de finalizar, ajuste o serviço da carta na(s) solicitação(ões) {nums}."
                    ),
                }
                return parsed, demandas_criadas

        demandas_criadas = self._materializar_demandas(
            usuario, rascunho_filtrado, session=session
        )
        if demandas_criadas:
            ids_txt = ", ".join(str(x["id"]) for x in demandas_criadas)
            if modo_ind:
                msg_ok = (
                    f"Pronto! Registrei {len(demandas_criadas)} indicação(ões) em rascunho: {ids_txt}. "
                    "Revise e protocolize quando estiver tudo certo."
                )
            else:
                msg_ok = (
                    f"Pronto! Criei {len(demandas_criadas)} demanda(s) em rascunho: {ids_txt}. "
                    "Revise na lista de demandas antes do protocolo."
                )
            parsed = {
                "resposta_agente": msg_ok,
                "estado_atual": ChatSession.ESTADO_COLETA_DADOS,
                "demandas_extraidas": [],
                "usuario_forneceu_endereco_real": True,
                "acionar_triagem_sinapse": False,
                "confirmar_criacao_demandas": False,
            }
            historico.append(
                {
                    "role": "system",
                    "content": (
                        "[SGDL] Demandas criadas: "
                        + json.dumps(demandas_criadas, ensure_ascii=False)
                    ),
                }
            )
        else:
            if modo_ind:
                msg_erro = (
                    "Não consegui gerar o rascunho da indicação. Confirme vereadores, número e PDF anexado."
                )
            else:
                msg_erro = (
                    "Não consegui gerar os rascunhos. Confirme o serviço na carta, "
                    "informe o local e tente «finalizar» novamente."
                )
            parsed = {
                **plano,
                "resposta_agente": msg_erro,
            }
        session.estado_atual = parsed.get("estado_atual", session.estado_atual)
        session.demandas_rascunho = parsed.get("demandas_extraidas", rascunho)
        session.save(
            update_fields=["demandas_rascunho", "estado_atual", "historico_mensagens", "atualizado_em"]
        )
        return parsed, demandas_criadas

    def _processar_recusa_validacao_final(self, session: ChatSession) -> dict[str, Any]:
        """H3-20 — «Não» na etapa final: volta ao fluxo editável sem materializar rascunhos."""
        rascunho = list(session.demandas_rascunho or [])
        session.estado_atual = ChatSession.ESTADO_COLETA_DADOS
        session.demandas_rascunho = rascunho
        session.save(update_fields=["estado_atual", "demandas_rascunho", "atualizado_em"])
        return {
            "resposta_agente": (
                "Sem problemas. Continue ajustando serviço, endereço ou anexos no painel. "
                "Quando estiver pronto, envie anexos ou diga «continuar sem anexos» para revisar de novo."
            ),
            "estado_atual": ChatSession.ESTADO_COLETA_DADOS,
            "demandas_extraidas": rascunho,
            "recusou_geracao_rascunhos": True,
            "usuario_forneceu_endereco_real": True,
            "acionar_triagem_sinapse": False,
            "confirmar_criacao_demandas": False,
        }

    def _sincronizar_estado_pos_vinculo_catalogo(
        self, session: ChatSession, parsed: dict[str, Any]
    ) -> None:
        """Após confirmar serviço ou tendência: endereço → anexos → validação (sem pular etapas)."""
        rascunho = list(session.demandas_rascunho or [])
        texto_sessao = self._texto_usuario_da_sessao(session)
        for item in rascunho:
            if isinstance(item, dict):
                self._hidratar_endereco_inferivel_item(
                    item, rascunho, texto_sessao=texto_sessao
                )
        plano = self._planejar_passo_fluxo(session, rascunho)
        parsed.update(plano)
        session.estado_atual = plano["estado_atual"]
        session.demandas_rascunho = rascunho
        session.save(update_fields=["estado_atual", "demandas_rascunho", "atualizado_em"])

    def _forcar_regras_estado_rigidas(
        self, parsed: dict[str, Any], *, pos_sinapse: bool = False, session: ChatSession | None = None
    ) -> None:
        """Barreira anti-alucinação: carta Sinapse antes de endereço; endereço só após vínculo."""
        dems = parsed.get("demandas_extraidas")
        if not isinstance(dems, list):
            dems = []
            parsed["demandas_extraidas"] = dems

        if session is not None and self._usuario_modo_indicacao(session.autor):
            self._marcar_rascunho_indicacao(dems, session.autor)

        forneceu = parsed.get("usuario_forneceu_endereco_real") is True
        pendente_carta = self._demandas_pendentes_vinculo_carta(dems)

        if forneceu:
            for item in dems:
                if isinstance(item, dict) and self._endereco_real_do_usuario(item):
                    item["endereco_informado_usuario"] = True
            if not self._rascunho_tem_endereco_suficiente(dems):
                forneceu = False
                parsed["usuario_forneceu_endereco_real"] = False

        if pos_sinapse:
            parsed["acionar_triagem_sinapse"] = False
            if pendente_carta:
                parsed["estado_atual"] = ChatSession.ESTADO_COLETA_DADOS
                parsed["resposta_agente"] = self._resposta_escolha_carta_sinapse(parsed)
            elif forneceu and dems:
                parsed["estado_atual"] = ChatSession.ESTADO_VALIDACAO_FINAL
            self._sanitizar_enderecos_demandas(dems)
            return

        if pendente_carta:
            parsed["acionar_triagem_sinapse"] = True
            parsed["estado_atual"] = ChatSession.ESTADO_COLETA_DADOS
            ra = (parsed.get("resposta_agente") or "").strip()
            if len(ra) < 24 or "rua" in ra.lower() or "bairro" in ra.lower() or "cep" in ra.lower():
                parsed["resposta_agente"] = self._resposta_escolha_carta_sinapse(parsed)
            self._sanitizar_enderecos_demandas(dems)
            return

        if not forneceu:
            self._limpar_enderecos_demandas(dems)
            parsed["usuario_forneceu_endereco_real"] = False
            parsed["acionar_triagem_sinapse"] = False
            precisa_local = any(
                isinstance(x, dict)
                and self._item_tem_problema_relato(x)
                and self._item_requer_localizacao_vinculada(x)
                for x in dems
            )
            if precisa_local and not self._rascunho_tem_endereco_suficiente(dems):
                parsed["estado_atual"] = ChatSession.ESTADO_COLETA_ENDERECO
                if self._demandas_pendentes_vinculo_carta(dems):
                    parsed["resposta_agente"] = self._resposta_escolha_carta_sinapse(parsed)
                else:
                    parsed["resposta_agente"] = self._resposta_pedir_endereco_opcional(parsed)
            elif self._demandas_pendentes_vinculo_carta(dems):
                parsed["estado_atual"] = ChatSession.ESTADO_COLETA_DADOS
                parsed["resposta_agente"] = self._resposta_escolha_carta_sinapse(parsed)
            elif dems and any(
                isinstance(x, dict) and self._item_tem_problema_relato(x) for x in dems
            ):
                parsed["estado_atual"] = ChatSession.ESTADO_VALIDACAO_FINAL
                parsed["resposta_agente"] = (
                    parsed.get("resposta_agente") or ""
                ).strip() or (
                    "Registrei o pedido. Revise o painel e confirme quando estiver pronto."
                )
            self._sanitizar_enderecos_demandas(dems)
            return

        if not dems or not any(
            isinstance(x, dict) and self._item_tem_problema_relato(x) for x in dems
        ):
            parsed["estado_atual"] = ChatSession.ESTADO_COLETA_DADOS
            parsed["acionar_triagem_sinapse"] = False
            self._sanitizar_enderecos_demandas(dems)
            return

        precisa_catalogo = any(
            isinstance(x, dict)
            and self._item_tem_problema_relato(x)
            and x.get("servico_local_id") is None
            and x.get("sinapse_servico_id_sugerido") is None
            for x in dems
        )
        if precisa_catalogo:
            parsed["acionar_triagem_sinapse"] = True
            ra = (parsed.get("resposta_agente") or "").strip()
            if len(ra) < 20:
                parsed["resposta_agente"] = self._fallback_resposta_pre_triagem(parsed)

        self._sanitizar_enderecos_demandas(dems)

    @staticmethod
    def _limpar_enderecos_demandas(dems: list[Any]) -> None:
        """Remove endereço colado pelo LLM quando o flag de endereço real é false."""
        for item in dems:
            if isinstance(item, dict):
                item["endereco"] = dict(_ENDERECO_VAZIO)

    @staticmethod
    def _resposta_pedir_endereco(parsed: dict[str, Any]) -> str:
        dems = parsed.get("demandas_extraidas") or []
        titulo = "sua solicitação"
        if isinstance(dems, list) and dems and isinstance(dems[0], dict):
            t = (dems[0].get("titulo") or "").strip()
            if t:
                titulo = t
        return (
            f"Entendi que você precisa de {titulo}. "
            "Por favor, me informe o nome da rua ou avenida e o bairro para eu registrar a solicitação."
        )

    @staticmethod
    def _item_tem_problema_relato(item: dict[str, Any]) -> bool:
        tit = (item.get("titulo") or "").strip()
        des = (item.get("descricao") or "").strip()
        te = (item.get("texto_para_embedding") or "").strip()
        return len(tit) >= 3 or len(des) >= 8 or len(te) >= 12

    @classmethod
    def _eixos_pedido_no_texto(cls, texto: str) -> list[dict[str, Any]]:
        t = (texto or "").lower()
        if not t.strip():
            return []
        out: list[dict[str, Any]] = []
        for eixo in _EIXOS_PEDIDO_COMPOSTO:
            if any(g in t for g in eixo["gatilhos"]):
                out.append(eixo)
        return out

    @classmethod
    def _titulo_padrao_eixo(cls, eixo_id: str | None) -> str | None:
        if not eixo_id:
            return None
        for eixo in _EIXOS_PEDIDO_COMPOSTO:
            if eixo.get("id") == eixo_id:
                return str(eixo.get("titulo_padrao") or "") or None
        return None

    @classmethod
    def _titulo_menciona_multiplos_eixos(cls, titulo: str, *, eixo_id: str | None = None) -> bool:
        """True quando o texto agrupa gatilhos de mais de um eixo operacional."""
        del eixo_id  # legado: decisão só pelo texto, sem forçar eixo inferido errado
        t = (titulo or "").lower()
        if not t:
            return False
        return len(cls._eixos_pedido_no_texto(t)) > 1

    @classmethod
    def _inferir_eixo_do_texto_usuario(cls, item: dict[str, Any]) -> str | None:
        """Infere eixo só pelo relato do cidadão (ignora candidatos Sinapse)."""
        titulo = (item.get("titulo") or "").lower()
        desc = (item.get("descricao") or "").lower()
        ped = (item.get("pedido_integral") or "").lower()
        te = (item.get("texto_para_embedding") or "").lower()
        melhor_id: str | None = None
        melhor_pts = 0
        for eixo in _EIXOS_PEDIDO_COMPOSTO:
            pts = 0
            for g in eixo.get("gatilhos") or ():
                if g in titulo:
                    pts += 4
                elif g in ped:
                    pts += 3
                elif g in desc:
                    pts += 2
                elif g in te:
                    pts += 1
            if pts > melhor_pts:
                melhor_pts = pts
                melhor_id = str(eixo["id"])
        return melhor_id if melhor_pts > 0 else None

    @classmethod
    def _inferir_eixo_principal_item(cls, item: dict[str, Any]) -> str | None:
        """Infere o eixo operacional dominante de um item (título, descrição ou carta)."""
        eixo_usuario = cls._inferir_eixo_do_texto_usuario(item)
        if eixo_usuario:
            return eixo_usuario
        titulo = (item.get("titulo") or "").lower()
        desc = (item.get("descricao") or "").lower()
        te = (item.get("texto_para_embedding") or "").lower()
        if not item.get("servico_confirmado_usuario"):
            cands = item.get("candidatos_sinapse")
            if isinstance(cands, list) and cands and isinstance(cands[0], dict):
                cand_tit = (cands[0].get("titulo") or "").lower()
                eixos_c = cls._eixos_pedido_no_texto(cand_tit)
                if len(eixos_c) == 1:
                    return str(eixos_c[0]["id"])
        melhor_id: str | None = None
        melhor_pts = 0
        for eixo in _EIXOS_PEDIDO_COMPOSTO:
            pts = 0
            for g in eixo.get("gatilhos") or ():
                if g in titulo:
                    pts += 3
                elif g in desc:
                    pts += 2
                elif g in te:
                    pts += 1
            if pts > melhor_pts:
                melhor_pts = pts
                melhor_id = str(eixo["id"])
        return melhor_id if melhor_pts > 0 else None

    @classmethod
    def _meta_eixo_pedido(cls, eixo_id: str | None) -> dict[str, Any] | None:
        if not eixo_id:
            return None
        for eixo in _EIXOS_PEDIDO_COMPOSTO:
            if eixo.get("id") == eixo_id:
                return eixo
        return None

    @classmethod
    def _descricao_especifica_eixo(
        cls, eixo: dict[str, Any], *, endereco: dict[str, Any] | None = None
    ) -> str:
        local = ""
        if isinstance(endereco, dict) and endereco:
            local = cls._formatar_sufixo_local_demanda({"endereco": endereco})
        verbo = eixo.get("descricao_verbo") or eixo.get("titulo_padrao") or "solicitação"
        if local:
            return f"Solicito {verbo}{local}."
        return f"Solicito {verbo}."

    @classmethod
    def _normalizar_item_pedido_composto(
        cls,
        item: dict[str, Any],
        *,
        endereco_ref: dict[str, Any] | None = None,
    ) -> None:
        """Garante título e relato específicos por eixo (ex.: buraco ≠ lombada)."""
        if cls._titulo_indica_sinalizacao(item):
            item["_eixo_pedido"] = "mobilidade_sinalizacao"
        eixo_id = cls._inferir_eixo_do_texto_usuario(item) or item.get("_eixo_pedido")
        if not eixo_id:
            eixo_id = cls._inferir_eixo_principal_item(item)
        if not eixo_id:
            return
        item["_eixo_pedido"] = str(eixo_id)
        eixo = cls._meta_eixo_pedido(str(eixo_id))
        if not eixo:
            return
        titulo_eixo = str(eixo.get("titulo_padrao") or "") or None
        blob = f"{item.get('titulo') or ''} {item.get('descricao') or ''}".strip()
        titulo_atual = (item.get("titulo") or "").strip()
        eixo_coerente = titulo_atual and any(
            g in titulo_atual.lower() or g in blob.lower()
            for g in (eixo.get("gatilhos") or ())
        )
        if titulo_eixo and not titulo_atual:
            item["titulo"] = titulo_eixo
        elif (
            titulo_eixo
            and not eixo_coerente
            and cls._titulo_menciona_multiplos_eixos(blob)
        ):
            item["titulo"] = titulo_eixo
        endereco = (
            item.get("endereco")
            if isinstance(item.get("endereco"), dict)
            else endereco_ref
        )
        desc = (item.get("descricao") or "").strip()
        if (
            not desc
            or cls._titulo_menciona_multiplos_eixos(desc)
            or len(cls._eixos_pedido_no_texto(desc)) > 1
        ):
            item["descricao"] = cls._descricao_especifica_eixo(
                eixo, endereco=endereco if isinstance(endereco, dict) else None
            )
        ped_atual = (item.get("pedido_integral") or "").strip()
        desc_atual = (item.get("descricao") or "").strip()
        if not ped_atual or len(ped_atual) < len(desc_atual):
            item["pedido_integral"] = desc_atual

    _DETALHE_COMPLEMENTAR_RELATO_RE = re.compile(
        r"\b("
        r"\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?"
        r"|(?:dia|em)\s+\d{1,2}\s+de\s+\w+"
        r"|(?:janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)"
        r"|(?:evento|festa|show|apresentação|apresentacao|realização|realizacao)"
        r"|(?:interditad|bloquead|inundad|alagad|queimad|apagad|sem\s+iluminação|sem\s+iluminacao)"
        r"|(?:desde|há|ha)\s+\d+\s+(?:dia|dias|semana|semanas|mês|mes|meses)"
        r")\w*",
        re.IGNORECASE,
    )

    @classmethod
    def _extrair_detalhes_complementares_relato(
        cls, relato: str, *, eixo: dict[str, Any] | None = None
    ) -> str:
        """Datas, estado do local e contexto de evento — preservados no ofício."""
        t = (relato or "").strip()
        if not t:
            return ""
        gatilhos_eixo = set(eixo.get("gatilhos") or ()) if eixo else set()
        trechos: list[str] = []
        for parte in re.split(r"[.;]\s+|\n+", t):
            p = parte.strip()
            if len(p) < 8:
                continue
            p_low = p.lower()
            if gatilhos_eixo and any(g in p_low for g in gatilhos_eixo) and not cls._DETALHE_COMPLEMENTAR_RELATO_RE.search(p):
                continue
            if cls._DETALHE_COMPLEMENTAR_RELATO_RE.search(p):
                if p not in trechos:
                    trechos.append(p)
        return ". ".join(trechos[:3])

    @classmethod
    def _normalizar_lista_demandas_compostas(cls, items: list[Any]) -> None:
        """Ajusta título/relato quando há vários pedidos ou texto agrupado indevidamente."""
        if not isinstance(items, list):
            return
        ativos = [
            x
            for x in items
            if isinstance(x, dict)
            and not x.get("descartada")
            and not x.get("fora_competencia")
        ]
        if not ativos:
            return
        precisa = len(ativos) >= 2 or any(
            cls._titulo_menciona_multiplos_eixos(
                f"{x.get('titulo') or ''} {x.get('descricao') or ''}"
            )
            for x in ativos
        )
        if not precisa:
            return
        endereco_comum = next(
            (x.get("endereco") for x in ativos if isinstance(x.get("endereco"), dict)),
            None,
        )
        end_ref = endereco_comum if isinstance(endereco_comum, dict) else None
        for item in ativos:
            cls._normalizar_item_pedido_composto(item, endereco_ref=end_ref)

    @staticmethod
    def _formatar_sufixo_local_demanda(item: dict[str, Any]) -> str:
        end = item.get("endereco") if isinstance(item.get("endereco"), dict) else {}
        log = (end.get("logradouro") or "").strip()
        num = ChatbotService._campo_endereco_str(end.get("numero"))
        bai = (end.get("bairro") or "").strip()
        if not log and not bai:
            return ""
        partes: list[str] = []
        if log:
            trecho = log
            if num:
                trecho += f", próximo ao número {num}"
            partes.append(trecho)
        if bai:
            partes.append(f"no {bai}")
        if len(partes) == 1:
            return f" {partes[0]}" if partes[0].startswith("no ") else f" na {partes[0]}"
        return f" na {partes[0]}, {partes[1]}"

    @staticmethod
    def _servico_confirmado_pelo_usuario(item: dict[str, Any]) -> bool:
        return bool(isinstance(item, dict) and item.get("servico_confirmado_usuario"))

    @classmethod
    def _escolha_carta_explicita_usuario(cls, item: dict[str, Any]) -> bool:
        """Pedido frequente ou confirmação manual na carta — não revalidar coerência lexical."""
        if not cls._servico_confirmado_pelo_usuario(item):
            return False
        if item.get("corpus_atalho_eixo_id") or item.get("corpus_preselecao_servico_id"):
            return True
        return item.get("origem_vinculo") == Demanda.ORIGEM_VINCULO_CARTA

    @classmethod
    def _limpar_servico_nao_confirmado(cls, items: list[Any]) -> None:
        """Remove vínculo automático da carta até o vereador confirmar no painel."""
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            if cls._servico_confirmado_pelo_usuario(item):
                continue
            if item.get("tendencia_id") or item.get("origem_vinculo") == Demanda.ORIGEM_VINCULO_TENDENCIA:
                continue
            if item.get("trilha_ouvidoria"):
                continue
            item.pop("sinapse_servico_id_sugerido", None)
            item.pop("servico_local_id", None)

    @classmethod
    def _resolver_sinapse_id_confirmado(cls, item: dict[str, Any]) -> int | None:
        if not cls._servico_confirmado_pelo_usuario(item):
            return None
        return cls._resolver_sinapse_id(item)

    @classmethod
    def _deve_adiar_anexos_multiplos_servicos(
        cls, rascunho: list[Any], texto: str = ""
    ) -> bool:
        ativos = [
            x
            for x in (rascunho or [])
            if isinstance(x, dict)
            and not x.get("descartada")
            and not x.get("fora_competencia")
        ]
        if len(ativos) >= 2:
            return any(not cls._item_vinculo_catalogo_resolvido(x) for x in ativos)
        candidatos = [
            (texto or "").strip(),
            *[
                " ".join(
                    p
                    for p in (
                        (x.get("pedido_integral") or "").strip(),
                        (x.get("descricao") or "").strip(),
                        (x.get("titulo") or "").strip(),
                    )
                    if p
                )
                for x in ativos
            ],
        ]
        candidatos = [c for c in candidatos if c]
        relato = max(candidatos, key=len) if candidatos else ""
        return len(cls._eixos_pedido_no_texto(relato)) >= 2

    def _processar_anexos_turno(
        self,
        session: ChatSession,
        arquivos: list,
        *,
        texto: str,
        rascunho: list[Any],
        indices_demanda: list[int | None] | None,
        parsed: dict[str, Any],
    ) -> None:
        if not arquivos:
            return
        if self._deve_adiar_anexos_multiplos_servicos(rascunho, texto):
            msg = (
                "Identifiquei mais de um serviço neste pedido. "
                "Confirme cada um na carta e anexe os documentos depois, "
                "na etapa «Documentos», vinculando cada arquivo à solicitação correta."
            )
            parsed["anexos_adiados"] = True
            atual = (parsed.get("resposta_agente") or "").strip()
            parsed["resposta_agente"] = f"{atual}\n\n{msg}".strip() if atual else msg
            return
        self._salvar_anexos_sessao(
            session,
            arquivos,
            texto_contexto=texto,
            rascunho=rascunho,
            indices_demanda=indices_demanda,
        )
        self._propagar_anexos_indices_rascunho(session)

    @classmethod
    def _expandir_demandas_compostas(
        cls, parsed: dict[str, Any], texto_usuario: str = ""
    ) -> bool:
        """
        Separa pedidos compostos (ex.: buraco + lombada) em demandas distintas com o mesmo endereço.
        Só atua quando há um único item ainda sem serviço confirmado na carta.
        """
        dems = parsed.get("demandas_extraidas")
        if not isinstance(dems, list) or len(dems) != 1:
            return False
        item = dems[0]
        if not isinstance(item, dict):
            return False
        if item.get("fora_competencia") or item.get("descartada"):
            return False
        if item.get("_expandida_pedidos_compostos"):
            return False
        if ChatbotService._item_vinculo_catalogo_resolvido(item):
            return False
        candidatos_relato = [
            (item.get("pedido_integral") or "").strip(),
            (item.get("descricao") or "").strip(),
            (texto_usuario or "").strip(),
            (item.get("titulo") or "").strip(),
        ]
        candidatos_relato = [c for c in candidatos_relato if c]
        relato = max(candidatos_relato, key=len) if candidatos_relato else ""
        eixos = cls._eixos_pedido_no_texto(relato)
        if len(eixos) < 2:
            return False

        endereco = dict(item.get("endereco") if isinstance(item.get("endereco"), dict) else _ENDERECO_VAZIO)
        local = cls._formatar_sufixo_local_demanda({**item, "endereco": endereco})
        relato_integral = relato.strip()
        novos: list[dict[str, Any]] = []
        for eixo in eixos:
            desc = f"Solicito {eixo['descricao_verbo']}{local}."
            complemento = cls._extrair_detalhes_complementares_relato(relato_integral, eixo=eixo)
            if complemento and complemento.lower() not in desc.lower():
                desc = f"{desc.rstrip('.')}. {complemento.rstrip('.')}."
            novo: dict[str, Any] = {
                "titulo": eixo["titulo_padrao"],
                "descricao": desc,
                "pedido_integral": relato_integral or desc,
                "texto_para_embedding": f"{eixo['texto_embedding']}{local}".strip()[:500],
                "endereco": dict(endereco),
                "competencia_municipal": item.get("competencia_municipal") or "sim",
                "_expandida_pedidos_compostos": True,
                "_eixo_pedido": eixo["id"],
            }
            for chave in (
                "latitude",
                "longitude",
                "coordenadas_fonte",
                "coordenadas_observacao",
                "endereco_informado_usuario",
            ):
                if item.get(chave) is not None:
                    novo[chave] = item[chave]
            novos.append(novo)

        parsed["demandas_extraidas"] = novos
        parsed["acionar_triagem_sinapse"] = True
        return True

    @classmethod
    def _expandir_demandas_compostas_no_rascunho(
        cls, items: list[Any], texto_usuario: str = ""
    ) -> bool:
        if not isinstance(items, list):
            return False
        wrapper = {"demandas_extraidas": items}
        if not cls._expandir_demandas_compostas(wrapper, texto_usuario):
            return False
        expandido = wrapper.get("demandas_extraidas")
        if not isinstance(expandido, list):
            return False
        items[:] = expandido
        return True

    def _atualizar_triagem_demandas(
        self,
        session: ChatSession,
        items: list[Any],
        *,
        forcar: bool = False,
    ) -> None:
        """Executa (ou refaz) triagem Sinapse para itens do rascunho."""
        texto_sessao = self._texto_usuario_da_sessao(session)
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("fora_competencia") or item.get("descartada"):
                continue
            if self._item_vinculo_catalogo_resolvido(item):
                continue
            if self._item_trilha_ouvidoria(item):
                continue
            if not forcar and item.get("candidatos_sinapse"):
                continue
            item.pop("sinapse_servico_id_sugerido", None)
            item.pop("servico_local_id", None)
            cands = self._triagem_sinapse_consolidada(item, texto_sessao=texto_sessao)
            item["candidatos_sinapse"] = cands
            item["candidatos_revisao"] = int(item.get("candidatos_revisao") or 0) + 1

    @staticmethod
    def _podar_demandas_extras_sinapse(parsed: dict[str, Any], n_antes: int) -> None:
        """Impede que o LLM multiplique demandas a partir dos candidatos vetoriais do Sinapse."""
        if n_antes <= 0:
            return
        dems = parsed.get("demandas_extraidas")
        if not isinstance(dems, list) or len(dems) <= n_antes:
            return
        logger.warning(
            "Copiloto: LLM expandiu demandas_extraidas de %s para %s após Sinapse; podando.",
            n_antes,
            len(dems),
        )
        parsed["demandas_extraidas"] = dems[:n_antes]

    @staticmethod
    def _fallback_resposta_pre_triagem(parsed: dict[str, Any]) -> str:
        """Mensagem natural quando o modelo omitiu texto mas os slots permitem ir ao catálogo."""
        dems = parsed.get("demandas_extraidas") or []
        if not isinstance(dems, list) or not dems:
            return (
                "Certo — com o que você já enviou, vou consultar o catálogo oficial de serviços "
                "para enquadrar direitinho."
            )
        titulos: list[str] = []
        for it in dems[:4]:
            if not isinstance(it, dict):
                continue
            t = (it.get("titulo") or "").strip()
            if t and t not in titulos:
                titulos.append(t)
        end_txt = ChatbotService._formatar_endereco_curto_para_fallback(dems)
        if len(titulos) == 1:
            foco = titulos[0]
        elif len(titulos) > 1:
            foco = " e ".join(titulos[:3])
        else:
            foco = "sua solicitação"
        suf = f" no {end_txt}" if end_txt else ""
        return (
            f"Entendi! Vou buscar no catálogo oficial os serviços ligados a {foco}{suf}. "
            "Já cruzo com a carta e volto com o enquadramento."
        )

    def _montar_injecao_sinapse(
        self, itens: list[dict[str, Any]]
    ) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
        """Executa embedding + TriagemService; devolve (mensagem system, candidatos UI, blocos por demanda)."""
        blocos: list[dict[str, Any]] = []

        for idx, item in enumerate(itens):
            if isinstance(item, dict) and self._item_trilha_ouvidoria(item):
                continue
            candidatos = self._triagem_sinapse_consolidada(item)
            if not candidatos:
                continue
            variantes = self._variantes_consulta_triagem_sinapse(item)
            texto_emb = variantes[0] if variantes else ""
            vetor = VectorService().generate_embedding(texto_emb) if texto_emb else None
            embedding_dims = len(vetor) if vetor else 0

            enriquecidos = []
            for c in candidatos:
                sid = c.get("servico_id")
                local_id = ChatbotService._sinapse_id_from_candidato(
                    sid,
                    (c.get("titulo") or "").strip() or None,
                    )
                enriquecidos.append(
                    {
                        **c,
                        "servico_local_id_mapeado": local_id,
                    }
                )

            blocos.append(
                {
                    "indice_demanda": idx,
                    "texto_usado_na_triagem": texto_emb,
                    "embedding_dims": embedding_dims,
                    "kernel_modelo": getattr(settings, "AI_KERNEL_EMBEDDING_MODEL", ""),
                    "candidatos_sinapse": enriquecidos,
                }
            )

        if not blocos:
            return "", [], []

        primeiro_cands: list[dict[str, Any]] = []
        raw0 = blocos[0].get("candidatos_sinapse")
        if isinstance(raw0, list):
            primeiro_cands = list(raw0)

        opcoes_formatadas = self._formatar_opcoes_sinapse_para_injecao(blocos)
        mensagem = (
            f"{_SINAPSE_PREFIX}: A busca vetorial retornou as opções abaixo. "
            "Escolha APENAS UMA que seja EXATAMENTE o que o usuário pediu. Ignore as outras. "
            "Retorne o JSON final atualizando APENAS o `sinapse_servico_id_sugerido` da demanda "
            f"correspondente. Opções retornadas: {opcoes_formatadas}"
        )
        return mensagem, primeiro_cands, blocos

    @staticmethod
    def _anexar_candidatos_triagem_a_parsed(
        parsed: dict[str, Any], blocos: list[dict[str, Any]]
    ) -> None:
        dems = parsed.get("demandas_extraidas")
        if not isinstance(dems, list):
            return
        for bloco in blocos:
            if not isinstance(bloco, dict):
                continue
            idx = int(bloco.get("indice_demanda") or 0)
            raw = bloco.get("candidatos_sinapse")
            if not isinstance(raw, list) or idx < 0 or idx >= len(dems):
                continue
            if not isinstance(dems[idx], dict):
                dems[idx] = {}
            dems[idx]["candidatos_sinapse"] = [
                {
                    "servico_id": c.get("servico_id"),
                    "titulo": (c.get("titulo") or "").strip(),
                    "orgao": (c.get("orgao") or "").strip() or None,
                    "score": c.get("score"),
                }
                for c in raw[:6]
                if isinstance(c, dict) and c.get("servico_id") is not None
            ]

    @staticmethod
    def _texto_rerank_candidato(item: dict[str, Any]) -> str:
        """Texto para desempate de candidatos — sem `texto_para_embedding` composto."""
        return " ".join(
            p
            for p in (
                (item.get("titulo") or ""),
                (item.get("descricao") or ""),
                (item.get("pedido_integral") or ""),
            )
            if p
        ).lower()

    @classmethod
    def _titulo_indica_sinalizacao(cls, item: dict[str, Any]) -> bool:
        titulo = (item.get("titulo") or "").lower()
        if not titulo:
            return False
        if not any(
            g in titulo
            for g in ("placa", "sinaliz", "semáforo", "semaforo", "horizontal", "vertical")
        ):
            return False
        if any(
            g in titulo
            for g in (
                "instalação de lombada",
                "instalacao de lombada",
                "implantação de lombada",
                "implantacao de lombada",
            )
        ):
            return "placa" in titulo or "sinaliz" in titulo
        return True

    @staticmethod
    def _pontuacao_candidato_ajustada(c: dict[str, Any], item: dict[str, Any]) -> float:
        """Score vetorial + regras de domínio/título (desempate e reranking no copiloto)."""
        texto = ChatbotService._texto_rerank_candidato(item)
        st = (c.get("titulo") or "").lower()
        pts = float(c.get("score") or 0.0)
        if ChatbotService._titulo_indica_sinalizacao(item):
            if "sinaliz" in st:
                pts += 0.58
            elif "lombad" in st or "redutor" in st:
                pts += 0.12
        elif any(
            w in texto
            for w in ("redutor", "lombad", "velocidade", "revitaliz", "manutenção", "manutencao")
        ):
            if "lombad" in st or "redutor" in st:
                pts += 0.50
            elif "sinaliz" in st or "trânsito" in st or "transito" in st:
                pts += 0.42
            elif "ilumina" in st or "luminária" in st or "luminaria" in st:
                pts -= 0.55
        elif "lombad" in texto:
            if "lombad" in st:
                pts += 0.45
            elif "ilumina" in st or "luminária" in st or "luminaria" in st:
                pts -= 0.55
        if any(w in texto for w in ("nivelamento", "cascalh")):
            if "nivelamento" in st or "cascalh" in st:
                pts += 0.55
            elif any(
                w in st
                for w in ("limpeza", "valeta", "córrego", "corrego", "bueiro", "coleta", "entulho")
            ):
                pts -= 0.50
        if any(w in texto for w in ("tapa", "buraco")) and ("tapa" in st or "burac" in st):
            pts += 0.35
        if any(w in texto for w in ("poda", "árvore", "arvore", "galho", "galhos")):
            if any(w in st for w in ("poda", "árvore", "arvore", "galho", "corte", "arbor")):
                pts += 0.62
            elif any(w in st for w in ("tapa", "burac", "paviment")):
                pts -= 0.58
        if any(w in texto for w in ("reserva", "espaço", "espaco", "evento", "ação", "acao")):
            if "reserva" in st and "parque" in st:
                pts += 0.4
            if "centen" in texto and "centen" in st:
                pts += 0.35
        if any(
            w in texto
            for w in (
                "transporte coletivo",
                "coletivo municipal",
                "linha ",
                "aumento de veículos",
                "aumento de veiculos",
            )
        ) or re.search(r"linha\s+\d", texto):
            if "coletivo" in st and any(w in st for w in ("linha", "ônibus", "onibus", "alteração", "alteracao", "horário", "horario", "ponto")):
                pts += 0.58
            elif "escolar" in st or "vaga" in st or "creche" in st:
                pts -= 0.55
        return pts

    @staticmethod
    def _escolher_melhor_candidato_sinapse(
        candidatos: list[dict[str, Any]], item: dict[str, Any]
    ) -> dict[str, Any] | None:
        if not candidatos:
            return None
        melhor: dict[str, Any] | None = None
        melhor_pts = -999.0
        for c in candidatos:
            if not isinstance(c, dict):
                continue
            pts = ChatbotService._pontuacao_candidato_ajustada(c, item)
            if pts > melhor_pts:
                melhor_pts = pts
                melhor = c
        return melhor or candidatos[0]

    def _melhor_candidato_coerente(
        self,
        candidatos: list[dict[str, Any]],
        item: dict[str, Any],
        *,
        texto_sessao: str = "",
    ) -> dict[str, Any] | None:
        """Melhor candidato cujo título combina com o relato (ignora falso positivo vetorial)."""
        texto = self._texto_coerencia_demanda(item, texto_sessao)
        melhor: dict[str, Any] | None = None
        melhor_pts = -999.0
        for c in candidatos:
            if not isinstance(c, dict):
                continue
            if not self._coerencia_texto_servico(texto, (c.get("titulo") or "")):
                continue
            pts = self._pontuacao_candidato_ajustada(c, item)
            if pts > melhor_pts:
                melhor_pts = pts
                melhor = c
        return melhor

    @staticmethod
    def _formatar_opcoes_sinapse_para_injecao(blocos: list[dict[str, Any]]) -> str:
        """Texto legível das opções vetoriais (sem JSON volumoso que confunde o modelo)."""
        partes: list[str] = []
        for bloco in blocos:
            if not isinstance(bloco, dict):
                continue
            idx = bloco.get("indice_demanda", 0)
            cands = bloco.get("candidatos_sinapse")
            if not isinstance(cands, list) or not cands:
                continue
            linhas: list[str] = []
            for i, c in enumerate(cands, 1):
                if not isinstance(c, dict):
                    continue
                sid = c.get("servico_id", "?")
                tit = (c.get("titulo") or "sem título").strip()
                org = (c.get("orgao") or "").strip()
                sufixo = f" ({org})" if org else ""
                linhas.append(f"{i}) servico_id={sid} — {tit}{sufixo}")
            if linhas:
                partes.append(f"[demanda índice {idx}] " + " | ".join(linhas))
        return " // ".join(partes) if partes else "(nenhuma opção retornada)"

    @staticmethod
    def _parse_candidatos_injecao_sinapse(injecao: str) -> list[dict[str, Any]]:
        """Extrai candidatos do texto `[SISTEMA SINAPSE]: ... Opções retornadas: ...`."""
        out: list[dict[str, Any]] = []
        for m in re.finditer(
            r"(\d+)\)\s*servico_id=([^\s—|]+)\s*—\s*([^|(]+)",
            injecao,
        ):
            sid_raw = m.group(2).strip().rstrip(",")
            tit = m.group(3).strip()
            sid: int | str = sid_raw
            if sid_raw.isdigit():
                sid = int(sid_raw)
            out.append({"servico_id": sid, "titulo": tit})
        return out

    @staticmethod
    def _sobrepor_lista_opcoes_sinapse(
        parsed: dict[str, Any], candidatos: list[dict[str, Any]]
    ) -> None:
        """Só complementa `resposta_agente` se o modelo veio vago — sem URA nem “qual número?”.

        Se o LLM já produziu texto natural (confirmação fluida), não sobrescreve.
        """
        if not candidatos:
            return
        ra = (parsed.get("resposta_agente") or "").strip()
        if ra and len(ra) > 48:
            return

        top = candidatos[0]
        titulo = (top.get("titulo") or "serviço identificado").strip()
        orgao = (top.get("orgao") or "").strip() or "órgão responsável na carta"
        end_txt = ChatbotService._formatar_endereco_curto_para_fallback(
            parsed.get("demandas_extraidas")
        )
        suf_end = f" O endereço anotado foi {end_txt}." if end_txt else ""

        parsed["resposta_agente"] = (
            f"Com base no seu pedido, o serviço do catálogo que melhor se aplica é «{titulo}» "
            f"({orgao}).{suf_end} Posso gerar o ofício em rascunho?"
        )
        parsed["estado_atual"] = ChatSession.ESTADO_VALIDACAO_FINAL

    @staticmethod
    def _formatar_endereco_curto_para_fallback(demandas_extraidas: Any) -> str:
        """Uma linha legível a partir do primeiro item com endereco preenchido."""
        if not isinstance(demandas_extraidas, list):
            return ""
        for item in demandas_extraidas:
            if not isinstance(item, dict):
                continue
            end = item.get("endereco")
            if not isinstance(end, dict):
                continue
            partes: list[str] = []
            logr = (end.get("logradouro") or "").strip()
            num = ChatbotService._campo_endereco_str(end.get("numero"))
            bai = (end.get("bairro") or "").strip()
            cep = (end.get("cep") or "").strip()
            if logr:
                partes.append(logr + (f", {num}" if num else ""))
            elif num:
                partes.append(f"nº {num}")
            if bai:
                partes.append(f"bairro {bai}")
            if cep:
                partes.append(f"CEP {cep}")
            if partes:
                return ", ".join(partes)[:220]
        return ""

    def _preencher_endereco_do_texto_usuario(
        self, ultimo_usuario: str, parsed: dict[str, Any]
    ) -> None:
        """Extrai CEP/rua/bairro do texto livre e preenche slots antes do LLM “esquecer” o endereço."""
        t = self._texto_util_para_extracao_endereco(ultimo_usuario or "")
        if len(t) < 6:
            return
        ext = self._extrair_endereco_livre(t)
        if not any(ext.get(k) for k in ("cep", "logradouro", "bairro", "numero")):
            return
        dems = parsed.get("demandas_extraidas")
        if not isinstance(dems, list) or not dems:
            return
        for item in dems:
            if not isinstance(item, dict):
                continue
            cur = item.get("endereco") if isinstance(item.get("endereco"), dict) else {}
            item["endereco"] = self._merge_endereco_dicts(cur, ext)

    @staticmethod
    def _resolver_sinapse_id(
        item: dict[str, Any],
        *,
        permitir_fallback_titulo: bool = False,
    ) -> int | None:
        raw = item.get("sinapse_servico_id_sugerido") or item.get("servico_local_id")
        if raw is not None:
            try:
                sid = int(raw)
                if sinapse_catalog.servico_existe(sid):
                    return sid
            except (TypeError, ValueError):
                pass
        if not permitir_fallback_titulo:
            return None
        titulo = (item.get("titulo") or "").strip() or None
        desc = (item.get("descricao") or "").strip() or None
        return sinapse_catalog.resolver_servico_por_titulo(titulo, texto_extra=desc)

    _STOPWORDS_COERENCIA = frozenset(
        {
            "para",
            "com",
            "sem",
            "uma",
            "uso",
            "nos",
            "nas",
            "dos",
            "das",
            "que",
            "por",
            "sobre",
            "mais",
            "muito",
            "esta",
            "este",
            "essa",
            "esse",
            "solicita",
            "solicitacao",
            "demanda",
            "servico",
            "serviço",
            "oficio",
            "ofício",
            "gerar",
            "crie",
            "criar",
            "rua",
            "avenida",
            "av",
            "bairro",
            "cep",
            "numero",
            "número",
            "solicito",
        }
    )

    # Só “parque” / “evento” em comum não basta para prender à carta (score vetorial alto, tema errado).
    _TOKENS_FRACOS_COERENCIA = frozenset(
        {
            "parque",
            "parques",
            "centenario",
            "centenário",
            "feffer",
            "leon",
            "particular",
            "secretaria",
            "municipal",
            "meio",
            "ambiente",
            "protecao",
            "proteção",
            "animal",
            "social",
            "assistencia",
            "assistência",
            "planejamento",
            "urbanismo",
            "urbanos",
            "zeladoria",
            "servicos",
        }
    )

    @staticmethod
    def _tokens_coerencia(texto: str) -> set[str]:
        """Palavras-chave do pedido (≥4 letras, sem stopwords)."""
        if not texto:
            return set()
        bruto = re.findall(r"[a-záàâãéêíóôõúç]{4,}", (texto or "").lower())
        return {w for w in bruto if w not in ChatbotService._STOPWORDS_COERENCIA}

    @classmethod
    def _tokens_coerencia_fortes(cls, texto: str) -> set[str]:
        return cls._tokens_coerencia(texto) - cls._TOKENS_FRACOS_COERENCIA

    @staticmethod
    def _coerencia_servico_demanda(titulo: str, servico_nome: str) -> bool:
        """False quando o título cidadão e o serviço da carta parecem de assuntos diferentes."""
        t = (titulo or "").lower()
        s = (servico_nome or "").lower()
        if not t or not s:
            return True
        if ("lombad" in t) and ("lombad" not in s) and ("ilumina" in s or "luminária" in s or "luminaria" in s):
            return False
        if any(w in t for w in ("tapa", "buraco")) and "tapa" not in s and "burac" not in s and "paviment" not in s:
            if "ilumina" in s:
                return False
        if any(w in t for w in ("poda", "árvore", "arvore", "galho")) and not any(
            w in s for w in ("poda", "árvore", "arvore", "galho", "corte", "arbor")
        ):
            if any(w in s for w in ("tapa", "burac", "paviment")):
                return False
        if (
            any(w in t for w in ("transporte coletivo", "coletivo municipal"))
            or re.search(r"linha\s+\d", t)
        ) and "escolar" in s and "coletivo" not in s:
            return False
        return True

    @classmethod
    def _coerencia_texto_servico(cls, texto_demanda: str, servico_nome: str) -> bool:
        """Combina regras fixas + sobreposição lexical forte (evita carta com score alto e tema errado)."""
        titulo_linha = (texto_demanda or "").split("\n", 1)[0]
        if not cls._coerencia_servico_demanda(titulo_linha, servico_nome):
            return False

        t_dem = (texto_demanda or "").lower()
        t_srv = (servico_nome or "").lower()
        if (
            any(w in t_dem for w in ("transporte coletivo", "coletivo municipal"))
            or re.search(r"linha\s+\d", t_dem)
        ) and "escolar" in t_srv and "coletivo" not in t_srv:
            return False
        if any(
            w in t_dem for w in ("fechament", "interdic", "bloqueio", "interdição")
        ) and not any(
            w in t_srv
            for w in (
                "fechament",
                "interdic",
                "bloqueio",
                "interdição",
                "transito",
                "trânsito",
                "circul",
                "via",
            )
        ):
            return False

        fortes_d = cls._tokens_coerencia_fortes(texto_demanda)
        fortes_s = cls._tokens_coerencia_fortes(servico_nome)
        if not fortes_d:
            return True
        if fortes_d & fortes_s:
            return True
        for td in fortes_d:
            for ts in fortes_s:
                if len(td) >= 5 and len(ts) >= 5 and (td[:5] == ts[:5] or td in ts or ts in td):
                    return True
        if any(w in t_dem for w in ("limpez", "roçag", "rocag", "capina", "varri", "entulho")):
            if any(
                w in t_srv
                for w in ("limpez", "varri", "roçag", "rocag", "capina", "entulho", "coleta", "ruas")
            ):
                return True
        return False

    @staticmethod
    def _melhor_candidato_dict(item: dict[str, Any]) -> dict[str, Any] | None:
        cands = item.get("candidatos_sinapse")
        if not isinstance(cands, list) or not cands:
            return None
        return ChatbotService._escolher_melhor_candidato_sinapse(cands, item)

    @staticmethod
    def _sinapse_id_from_candidato(servico_id: Any, titulo: str | None) -> int | None:
        if servico_id is not None:
            try:
                sid = int(servico_id)
                if sinapse_catalog.servico_existe(sid):
                    return sid
            except (TypeError, ValueError):
                pass
        return sinapse_catalog.resolver_servico_por_titulo(titulo)

    @classmethod
    def _system_prompt_copiloto(cls) -> str:
        base = COPILOT_SYSTEM_PROMPT
        if not copiloto_faq_habilitada():
            base = (
                base
                + "\n\nMODO OPERACIONAL ATUAL: não recuse pedidos por competência municipal/FAQ. "
                "Registre o relato na íntegra; se o serviço não existir na carta, o protocolo "
                "tratará como tendência para análise humana."
            )
            return base
        try:
            faqs = listar_faq_detalhada_para_prompt()
        except Exception:
            logger.exception("Copiloto: falha ao carregar FAQ para o prompt.")
            return base
        if not faqs:
            return base
        linhas = []
        for f in faqs:
            linhas.append(
                f"- **{f['categoria_orientacao']}** ({f['titulo']}): "
                f"{f['mensagem']} → {f['orgao_hint']}"
            )
        extra = (
            "\n\nFAQ oficial — orientações fora da competência municipal "
            "(use `categoria_orientacao` exata e reproduza a orientação na `resposta_agente` "
            "quando `competencia_municipal` for `nao`):\n"
            + "\n".join(linhas)
        )
        return base + extra

    @classmethod
    def _pre_classificar_faq_em_lista(
        cls, items: list[Any], *, texto_sessao: str = ""
    ) -> None:
        """Prioriza regex FAQ cadastrada sobre classificação genérica do LLM (A1)."""
        if not copiloto_faq_habilitada():
            return
        for item in items or []:
            if not isinstance(item, dict):
                continue
            if cls._resolver_sinapse_id(item) or cls._item_vinculo_catalogo_resolvido(item):
                continue
            texto = cls._texto_coerencia_demanda(item, texto_sessao)
            if not texto.strip():
                continue
            faq = detectar_faq_por_texto(texto)
            if not faq:
                continue
            if cls._texto_parece_demanda_municipal(texto):
                continue
            item["categoria_orientacao"] = faq.categoria_orientacao
            item["competencia_municipal"] = "nao"
            item["fora_competencia"] = True
            item["faq_orientacao"] = faq_para_dict(faq)
            item["motivo_recusa"] = montar_motivo_recusa(faq=faq)
            item["candidatos_sinapse"] = []
            item.pop("sinapse_servico_id_sugerido", None)
            item.pop("servico_local_id", None)

    @classmethod
    def _pre_classificar_faq_nas_demandas(
        cls, parsed: dict[str, Any], *, texto_sessao: str = ""
    ) -> None:
        dems = parsed.get("demandas_extraidas")
        if isinstance(dems, list):
            cls._pre_classificar_faq_em_lista(dems, texto_sessao=texto_sessao)

    @classmethod
    def _limpar_triagem_fora_competencia(cls, items: list[Any]) -> None:
        for item in items or []:
            if isinstance(item, dict) and item.get("fora_competencia"):
                item["candidatos_sinapse"] = []
                item.pop("sinapse_servico_id_sugerido", None)
                item.pop("servico_local_id", None)

    def _turno_resposta_faq_imediata(
        self, texto: str, session: ChatSession
    ) -> dict[str, Any] | None:
        """
        Atalho determinístico: pedido bate FAQ cadastrada → recusa sem Groq/carta.
        Evita cair em «registre como tendência» quando o assunto é fora da competência.
        """
        if not copiloto_faq_habilitada():
            return None
        t = (texto or "").strip()
        if len(t) < 8:
            return None
        rascunho = list(session.demandas_rascunho or [])
        if rascunho and self._rascunho_tem_problema_util(rascunho):
            return None
        if self._texto_parece_demanda_municipal(t):
            return None
        faq = detectar_faq_por_texto(t)
        if not faq:
            return None
        titulo = t[:120] if len(t) <= 120 else f"{t[:117]}…"
        item: dict[str, Any] = {
            "titulo": titulo,
            "descricao": t,
            "pedido_integral": t,
            "texto_para_embedding": None,
            "endereco": dict(_ENDERECO_VAZIO),
            "competencia_municipal": "nao",
            "categoria_orientacao": faq.categoria_orientacao,
            "fora_competencia": True,
            "motivo_recusa": montar_motivo_recusa(faq=faq),
            "faq_orientacao": faq_para_dict(faq),
            "candidatos_sinapse": [],
        }
        msg = montar_resposta_chat_fora_competencia([item])
        return {
            "usuario_forneceu_endereco_real": False,
            "resposta_agente": msg,
            "estado_atual": ChatSession.ESTADO_COLETA_DADOS,
            "demandas_extraidas": [item],
            "acionar_triagem_sinapse": False,
            "confirmar_criacao_demandas": False,
        }

    @classmethod
    def _alinhar_resposta_agente_faq(cls, parsed: dict[str, Any]) -> None:
        if not copiloto_faq_habilitada():
            return
        dems = parsed.get("demandas_extraidas")
        if not isinstance(dems, list):
            return
        msg_faq = montar_resposta_chat_fora_competencia(dems)
        if not msg_faq:
            return
        indices = cls._indices_fora_competencia(dems)
        if not indices:
            return
        if len(indices) == len(dems):
            parsed["resposta_agente"] = msg_faq
            return
        atual = (parsed.get("resposta_agente") or "").strip()
        parsed["resposta_agente"] = f"{atual}\n\n{msg_faq}".strip() if atual else msg_faq

    @staticmethod
    def _mensagem_gestao_operacional_rascunho(session: ChatSession | None) -> str | None:
        if not session:
            return None
        rascunho = list(session.demandas_rascunho or [])
        blocos: list[dict[str, Any]] = []
        for i, item in enumerate(rascunho):
            if not isinstance(item, dict):
                continue
            sid = ChatbotService._resolver_sinapse_servico_id(item)
            gestao = gestao_operacional_para_copiloto(sid)
            if not gestao:
                continue
            blocos.append(
                {"demanda_indice": i, "sinapse_servico_id": sid, "gestao_operacional": gestao}
            )
        if not blocos:
            return None
        return (
            "[SGDL GESTÃO] Dados operacionais do Sinapse (prazo completo, documentos e taxas; "
            "use para orientar o cidadão, sem inventar): "
            + json.dumps(blocos, ensure_ascii=False)
        )

    def _chamar_groq_json(self, historico_sem_system: list[dict[str, Any]]) -> dict[str, Any]:
        messages: list[dict[str, str]] = [
            {"role": "system", "content": self._system_prompt_copiloto()},
            *self._sanitizar_historico(historico_sem_system),
        ]
        raw = self._post_groq(messages)
        return self._parse_json_resposta(raw)

    def _sanitizar_historico(
        self, historico: list[dict[str, Any]]
    ) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        for m in historico:
            if not isinstance(m, dict):
                continue
            role = m.get("role")
            content = m.get("content")
            if role not in ("user", "assistant", "system") or not isinstance(content, str):
                continue
            if len(content) > 120_000:
                content = content[:120_000] + "…"
            out.append({"role": role, "content": content})
        return out

    def _post_groq(self, messages: list[dict[str, str]]) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": self.temperature,
        }
        for tentativa in range(2):
            try:
                response = requests.post(
                    self.base_url, headers=headers, json=payload, timeout=self.timeout
                )
            except requests.Timeout:
                logger.error("Timeout (%ss) Groq chat.", self.timeout)
                return "{}"
            except requests.ConnectionError as exc:
                logger.error("Falha de conexão Groq: %s", exc)
                return "{}"

            if response.status_code == 429 and tentativa == 0:
                espera = self._segundos_retry_groq_429(response)
                logger.warning("Groq 429 TPM; nova tentativa em %.1fs.", espera)
                time.sleep(espera)
                continue

            if not response.ok:
                logger.error(
                    "Groq HTTP %s: %s",
                    response.status_code,
                    (response.text or "")[:400],
                )
                return "{}"

            try:
                data = response.json()
            except ValueError:
                logger.error("Groq retornou corpo não JSON.")
                return "{}"

            return self._extrair_content_string(data)

        return "{}"

    @staticmethod
    def _segundos_retry_groq_429(response: requests.Response) -> float:
        corpo = response.text or ""
        m = re.search(r"try again in\s+([\d.]+)\s*s", corpo, re.IGNORECASE)
        if m:
            try:
                return min(max(float(m.group(1)) + 0.25, 1.0), 30.0)
            except ValueError:
                pass
        return 2.0

    @staticmethod
    def _extrair_content_string(data: dict[str, Any]) -> str:
        if not isinstance(data, dict):
            return "{}"
        if data.get("error"):
            logger.error("Groq erro: %s", data.get("error"))
            return "{}"
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            return "{}"
        msg = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = msg.get("content") if isinstance(msg, dict) else None
        if not isinstance(content, str) or not content.strip():
            return "{}"
        return content.strip()

    @staticmethod
    def _parse_json_resposta(content: str) -> dict[str, Any]:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.warning("JSON do assistente inválido: %s | trecho=%s", exc, content[:200])
            return {
                "resposta_agente": content[:2000],
                "estado_atual": ChatSession.ESTADO_COLETA_DADOS,
                "demandas_extraidas": [],
                "acionar_triagem_sinapse": False,
                "confirmar_criacao_demandas": False,
                "usuario_forneceu_endereco_real": False,
            }
        if not isinstance(parsed, dict):
            return {
                "resposta_agente": "Resposta inesperada do modelo.",
                "estado_atual": ChatSession.ESTADO_COLETA_DADOS,
                "demandas_extraidas": [],
                "acionar_triagem_sinapse": False,
                "confirmar_criacao_demandas": False,
                "usuario_forneceu_endereco_real": False,
            }
        parsed.setdefault("resposta_agente", "")
        parsed.setdefault("demandas_extraidas", [])
        parsed.setdefault("acionar_triagem_sinapse", False)
        parsed.setdefault("confirmar_criacao_demandas", False)
        parsed.setdefault("usuario_forneceu_endereco_real", False)
        if parsed.get("usuario_forneceu_endereco_real") is not True:
            parsed["usuario_forneceu_endereco_real"] = False
        est = parsed.get("estado_atual")
        validos = {c[0] for c in ChatSession.ESTADO_CHOICES}
        if est not in validos:
            parsed["estado_atual"] = ChatSession.ESTADO_COLETA_DADOS
        if not isinstance(parsed["demandas_extraidas"], list):
            parsed["demandas_extraidas"] = []
        ra = parsed.get("resposta_agente")
        if ra is None or not isinstance(ra, str):
            ra = ""
        parsed["resposta_agente"] = ra.strip()
        if not parsed["resposta_agente"]:
            logger.warning(
                "Copiloto: JSON do Groq sem resposta_agente (estado=%s, acionar_triagem=%s, n_demandas=%s).",
                parsed.get("estado_atual"),
                parsed.get("acionar_triagem_sinapse"),
                len(parsed["demandas_extraidas"]),
            )
        ChatbotService._normalizar_demandas_competencia_parseadas(parsed["demandas_extraidas"])
        return parsed

    @staticmethod
    def _normalizar_demandas_competencia_parseadas(demandas: list[Any]) -> None:
        for item in demandas or []:
            if not isinstance(item, dict):
                continue
            comp = normalizar_competencia_llm(item.get("competencia_municipal"))
            if comp:
                item["competencia_municipal"] = comp
            else:
                item.pop("competencia_municipal", None)
            cat = normalizar_categoria_orientacao(item.get("categoria_orientacao"))
            if cat:
                item["categoria_orientacao"] = cat
            else:
                item.pop("categoria_orientacao", None)
            mr = item.get("motivo_recusa")
            if mr is not None and not str(mr).strip():
                item.pop("motivo_recusa", None)

    @staticmethod
    def _garantir_resposta_agente_nao_vazia(parsed: dict[str, Any]) -> None:
        ra = parsed.get("resposta_agente")
        if isinstance(ra, str) and ra.strip():
            parsed["resposta_agente"] = ra.strip()
            return
        logger.error(
            "Copiloto: resposta_agente ainda vazio após fallbacks (estado=%s).",
            parsed.get("estado_atual"),
        )
        parsed["resposta_agente"] = (
            "Recebi sua mensagem, mas não consegui formatar uma resposta legível agora. "
            "Pode repetir ou acrescentar um detalhe (o que ocorre e onde)?"
        )

    @staticmethod
    def _tentar_aplicar_escolha_sinapse_numerica(
        historico: list[dict[str, Any]],
        mensagem_usuario: str,
        parsed: dict[str, Any],
    ) -> dict[str, Any]:
        """Se o usuário enviar só um índice (1..N) após injeção Sinapse, preenche servico_local_id."""
        t = (mensagem_usuario or "").strip()
        if not re.fullmatch(r"[1-9]|1[0-9]", t):
            return parsed
        escolha = int(t)
        injecao: str | None = None
        for msg in reversed(historico):
            if not isinstance(msg, dict) or msg.get("role") != "system":
                continue
            content = msg.get("content")
            if not isinstance(content, str):
                continue
            if content.startswith(f"{_SINAPSE_PREFIX}:"):
                injecao = content
                break
            if content.startswith(f"{_SINAPSE_PREFIX_LEGACY} "):
                injecao = content
                break
        cands: list[dict[str, Any]] = []
        i0 = 0
        if not injecao:
            dems = parsed.get("demandas_extraidas")
            if isinstance(dems, list) and dems and isinstance(dems[0], dict):
                raw = dems[0].get("candidatos_sinapse")
                if isinstance(raw, list) and raw:
                    cands = [c for c in raw if isinstance(c, dict)]
            if not cands:
                return parsed
        elif injecao.startswith(f"{_SINAPSE_PREFIX_LEGACY} "):
            try:
                data = json.loads(injecao[len(_SINAPSE_PREFIX_LEGACY) + 1 :].strip())
                blocos = data.get("itens")
                if isinstance(blocos, list) and blocos and isinstance(blocos[0], dict):
                    primeiro = blocos[0]
                    i0 = int(primeiro.get("indice_demanda") or 0)
                    raw = primeiro.get("candidatos_sinapse")
                    if isinstance(raw, list):
                        cands = [c for c in raw if isinstance(c, dict)]
            except json.JSONDecodeError:
                return parsed
        elif injecao:
            cands = ChatbotService._parse_candidatos_injecao_sinapse(injecao)
        if not cands:
            return parsed
        idx = escolha - 1
        if idx < 0 or idx >= len(cands):
            return parsed
        esc = cands[idx]
        if not isinstance(esc, dict):
            return parsed
        lid = esc.get("servico_local_id_mapeado")
        if lid is None:
            lid = ChatbotService._sinapse_id_from_candidato(
                esc.get("servico_id"),
                (esc.get("titulo") or "").strip() or None,
            )
            if lid is not None:
                logger.info(
                    "Copiloto: opção %s usou fallback por título Sinapse → servico_local_id=%s",
                    escolha,
                    lid,
                )
        if lid is None:
            logger.warning(
                "Copiloto: opção %s sem vínculo com serviço local (Sinapse: %s).",
                escolha,
                (esc.get("titulo") or "")[:80],
            )
            return parsed
        try:
            lid_int = int(lid)
        except (TypeError, ValueError):
            return parsed

        dems = parsed.get("demandas_extraidas")
        if not isinstance(dems, list) or not dems:
            dems = [{}]
            parsed["demandas_extraidas"] = dems
        while len(dems) <= i0:
            dems.append({})
        if not isinstance(dems[i0], dict):
            dems[i0] = {}
        dems[i0]["servico_local_id"] = lid_int
        sid = esc.get("servico_id")
        if sid is not None:
            dems[i0]["sinapse_servico_id_sugerido"] = sid
        dems[i0]["servico_confirmado_usuario"] = True
        if not (dems[i0].get("titulo") or "").strip():
            tit = (esc.get("titulo") or "").strip()
            if tit:
                dems[i0]["titulo"] = tit[:200]
        parsed["acionar_triagem_sinapse"] = False
        return parsed

    @staticmethod
    def _texto_util_para_extracao_endereco(texto: str) -> str:
        """Ignora frases automáticas (ex.: envio só de anexo) na extração de CEP/bairro."""
        t = (texto or "").strip()
        if not t:
            return ""
        if _TEXTO_SEM_ENDERECO_RE.match(t):
            return ""
        return t

    @staticmethod
    def _campo_endereco_str(valor: Any) -> str:
        if valor is None:
            return ""
        return str(valor).strip()

    @staticmethod
    def _valor_campo_endereco_valido(chave: str, valor: Any) -> bool:
        if valor in (None, "", []):
            return False
        v = str(valor).strip()
        if chave == "cep":
            return bool(re.fullmatch(r"\d{5}-\d{3}", v) or re.fullmatch(r"\d{8}", v))
        if chave == "bairro":
            if len(v) < 3 or len(v) > 60:
                return False
            if len(v.split()) > 5:
                return False
            if _VALOR_ENDERECO_INVALIDO_RE.search(v):
                return False
            if _PALAVRAS_PEDIDO_NO_BAIRRO_RE.search(v):
                return False
            if _LOGRADOURO_FRASE_PEDIDO_RE.search(v):
                return False
            if _PALAVRAS_PEDIDO_NO_LOGRADOURO_RE.search(v):
                return False
            if v.endswith(".") and len(v.split()) > 3:
                return False
            return True
        if chave == "logradouro":
            if len(v) < 4 or len(v) > 120:
                return False
            if len(v.split()) > 7:
                return False
            if _VALOR_ENDERECO_INVALIDO_RE.search(v):
                return False
            if _PALAVRAS_PEDIDO_NO_LOGRADOURO_RE.search(v):
                return False
            if _LOGRADOURO_FRASE_PEDIDO_RE.search(v):
                return False
            low = v.lower()
            if re.match(
                r"^(?:rua|r\.?\s+|av\.?\s+|avenida|trav\.?\s+|travessa|al\.?\s+|alameda|praça|praca)\s+",
                low,
            ):
                return True
            parque = ChatbotService._extrair_nome_parque(v)
            if parque and parque.lower() == v.lower():
                return True
            return False
        if chave in ("numero", "complemento"):
            return len(v) <= 120 and not _VALOR_ENDERECO_INVALIDO_RE.search(v)
        return True

    @staticmethod
    def _merge_endereco_dicts(
        base: dict[str, Any] | None, update: dict[str, Any] | None
    ) -> dict[str, Any]:
        out: dict[str, Any] = dict(base) if isinstance(base, dict) else {}
        if not isinstance(update, dict):
            return out
        for k, v in update.items():
            if v in (None, "", []):
                continue
            if k in ("cep", "logradouro", "bairro", "numero", "complemento"):
                if not ChatbotService._valor_campo_endereco_valido(k, v):
                    continue
                base_val = out.get(k)
                if base_val not in (None, "", []) and ChatbotService._valor_campo_endereco_valido(
                    k, base_val
                ):
                    continue
                out[k] = v
        return out

    @staticmethod
    def _titulo_eh_generico(titulo: str, *, servico_nome: str = "") -> bool:
        t = (titulo or "").strip()
        if len(t) < 12:
            return True
        if _TITULO_GENERICO_RE.match(t):
            return True
        tl = t.lower()
        genericos = (
            "transporte coletivo",
            "solicitação de transporte coletivo",
            "solicitacao de transporte coletivo",
            "pedido de transporte coletivo",
            "solicitação de serviço",
            "solicitacao de servico",
        )
        if tl in genericos:
            return True
        svc = (servico_nome or "").strip().lower()
        if svc and tl == svc:
            return True
        # Tema da carta ("Iluminação Pública: Troca...") — prefixo antes de ":" é assunto válido.
        if svc and ":" in svc:
            prefix = svc.split(":", 1)[0].strip().lower()
            if tl == prefix:
                return False
        return False

    @staticmethod
    def _mensagens_usuario_relevantes(session: ChatSession | None) -> list[str]:
        if not session:
            return []
        out: list[str] = []
        for msg in session.historico_mensagens or []:
            if not isinstance(msg, dict) or msg.get("role") != "user":
                continue
            t = str(msg.get("content") or "").strip()
            if len(t) < 20:
                continue
            if ChatbotService._mensagem_eh_somente_anexo(t):
                continue
            if _MENSAGEM_COMANDO_FLUXO_RE.match(t):
                continue
            out.append(t)
        return out

    @classmethod
    def _relato_integral_item(
        cls, item: dict[str, Any], *, session: ChatSession | None = None
    ) -> str:
        """Relato completo para ofício/cadastro — prioriza pedido_integral e mensagens longas do cidadão."""
        if item.get("_eixo_pedido"):
            candidatos_eixo = [
                (item.get("pedido_integral") or "").strip(),
                (item.get("descricao") or "").strip(),
            ]
            candidatos_eixo = [c for c in candidatos_eixo if c]
            if candidatos_eixo:
                return max(candidatos_eixo, key=len)
        candidatos: list[str] = []
        for key in ("pedido_integral", "descricao"):
            t = (item.get(key) or "").strip()
            if t:
                candidatos.append(t)
        for msg in cls._mensagens_usuario_relevantes(session):
            candidatos.append(msg)
        titulo = (item.get("titulo") or "").strip()
        if titulo and len(titulo) >= 20:
            candidatos.append(titulo)
        if not candidatos:
            return titulo or "Solicitação"
        return max(candidatos, key=len)

    @classmethod
    def _titulo_demanda_item(
        cls,
        item: dict[str, Any],
        relato: str,
        *,
        servico_nome: str = "",
    ) -> str:
        """Título = resumo do pedido do cidadão, nunca só categoria ou nome da carta."""
        eixo_corpus = (item.get("corpus_atalho_eixo_id") or "").strip()
        if eixo_corpus:
            from core.services.corpus_legado_service import CorpusLegadoService

            meta = CorpusLegadoService().meta_pedido_frequente(eixo_corpus)
            rotulo = (meta or {}).get("rotulo") or ""
            if rotulo:
                return rotulo[:200]
        titulo = (item.get("titulo") or "").strip()
        if titulo and not cls._titulo_eh_generico(titulo, servico_nome=servico_nome):
            return titulo[:200]
        eixo_id = item.get("_eixo_pedido") or cls._inferir_eixo_principal_item(item)
        if eixo_id:
            titulo_eixo = cls._titulo_padrao_eixo(str(eixo_id))
            if titulo_eixo:
                return titulo_eixo[:200]
        rel = (relato or "").strip()
        if not rel:
            return (titulo or "Solicitação")[:200]
        rel_limpo = re.sub(
            r"^(solicita(?:ção|cao)?|pede|pedido de?)\s+",
            "",
            rel,
            flags=re.IGNORECASE,
        ).strip()
        m = re.match(r"^(.{15,200}?[.!?]|.{15,200})", rel_limpo, re.DOTALL)
        derived = (m.group(1) if m else rel_limpo[:200]).strip()
        return (derived or titulo or "Solicitação")[:200]

    @staticmethod
    def _normalizar_sinapse_id_rascunho(item: dict[str, Any]) -> None:
        """Remove IDs inválidos (ex.: nome de serviço vindo do LLM em vez de inteiro)."""
        for key in ("sinapse_servico_id_sugerido", "servico_local_id"):
            raw = item.get(key)
            if raw is None:
                continue
            try:
                sid = int(raw)
            except (TypeError, ValueError):
                item.pop(key, None)
                continue
            if sinapse_catalog.servico_existe(sid):
                item[key] = sid
            else:
                item.pop(key, None)

    def _preservar_relato_rascunho(
        self, session: ChatSession, items: list[Any]
    ) -> list[dict[str, Any]]:
        """Evita perder detalhes do cidadão quando o LLM resume demais em turnos posteriores."""
        if not isinstance(items, list):
            return []
        ChatbotService._normalizar_lista_demandas_compostas(items)
        out: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            row = dict(item)
            self._normalizar_sinapse_id_rascunho(row)
            ChatbotService._normalizar_item_pedido_composto(row)
            if row.get("_eixo_pedido"):
                out.append(row)
                continue
            relato = self._relato_integral_item(row, session=session)
            desc_atual = (row.get("descricao") or "").strip()
            if len(relato) > len(desc_atual):
                row["descricao"] = relato
            ped_atual = (row.get("pedido_integral") or "").strip()
            if len(relato) > len(ped_atual):
                row["pedido_integral"] = relato
            svc_nome = ""
            sid = self._resolver_sinapse_id(row)
            if sid:
                cat = sinapse_catalog.get_servico(sid)
                svc_nome = (cat.titulo if cat else "") or ""
            titulo_atual = (row.get("titulo") or "").strip()
            if row.get("corpus_atalho_eixo_id") and titulo_atual:
                out.append(row)
                continue
            if self._titulo_eh_generico(titulo_atual, servico_nome=svc_nome):
                row["titulo"] = self._titulo_demanda_item(
                    row, relato, servico_nome=svc_nome
                )[:200]
            out.append(row)
        return out

    @staticmethod
    def _deve_retriagem_apos_mensagem(ultimo_texto: str, item: dict[str, Any]) -> bool:
        """Retriagem quando o cidadão acrescenta contexto (ex.: «transporte coletivo») sem confirmar serviço."""
        u = (ultimo_texto or "").strip()
        if len(u) < 5:
            return False
        if _MENSAGEM_COMANDO_FLUXO_RE.match(u):
            return False
        low = u.lower()
        gatilhos = (
            "transporte coletivo",
            "coletivo municipal",
            "linha ",
            "linha n",
            "ônibus",
            "onibus",
            "alteração",
            "alteracao",
            "horário",
            "horario",
            "veículo",
            "veiculo",
            "frota",
            "passageiro",
        )
        if any(g in low for g in gatilhos):
            return True
        relato = (item.get("pedido_integral") or item.get("descricao") or "").lower()
        return len(u) >= 8 and u.lower() not in relato

    def _retriagem_pendentes_se_necessario(
        self,
        session: ChatSession,
        items: list[Any],
        *,
        ultimo_texto: str = "",
    ) -> None:
        """Atualiza candidatos da carta após refinamento do pedido (sem confirmar serviço)."""
        if not isinstance(items, list):
            return
        texto_sessao = self._texto_usuario_da_sessao(session)
        alterou = False
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("fora_competencia") or item.get("descartada"):
                continue
            if self._item_vinculo_catalogo_resolvido(item):
                continue
            if not self._deve_retriagem_apos_mensagem(ultimo_texto, item):
                continue
            if item.get("_eixo_pedido"):
                base_emb = (item.get("texto_para_embedding") or item.get("descricao") or "").strip()
                item["texto_para_embedding"] = f"{base_emb} {ultimo_texto}".strip()[:500]
            else:
                relato = self._relato_integral_item(item, session=session)
                item["descricao"] = relato
                item["pedido_integral"] = relato
                item["texto_para_embedding"] = f"{relato} {ultimo_texto}".strip()[:500]
            self._normalizar_sinapse_id_rascunho(item)
            antigos = item.get("candidatos_sinapse")
            antigo_ids = tuple(
                c.get("servico_id")
                for c in (antigos if isinstance(antigos, list) else [])
                if isinstance(c, dict)
            )
            cands = self._triagem_sinapse_consolidada(item, texto_sessao=texto_sessao)
            if not cands:
                continue
            item["candidatos_sinapse"] = cands
            novos_ids = tuple(c.get("servico_id") for c in cands[:8] if isinstance(c, dict))
            if novos_ids != antigo_ids:
                item.pop("sinapse_servico_id_sugerido", None)
                item.pop("servico_local_id", None)
                item["candidatos_revisao"] = int(item.get("candidatos_revisao") or 0) + 1
            alterou = True
        if alterou:
            session.demandas_rascunho = items
            session.save(update_fields=["demandas_rascunho", "atualizado_em"])

    @staticmethod
    def _merge_demandas_rascunho(old: Any, new: Any) -> list[dict[str, Any]]:
        """Evita perder servico_local_id / Sinapse quando o LLM devolve só endereço ou lista parcial."""
        old_list = [dict(x) for x in (old or []) if isinstance(x, dict)]
        new_list = [dict(x) for x in (new or []) if isinstance(x, dict)]
        if not new_list:
            return old_list
        if (
            len(new_list) == 1
            and len(old_list) > 1
            and all(o.get("_expandida_pedidos_compostos") for o in old_list)
        ):
            nw = new_list[0]
            out_preservado: list[dict[str, Any]] = []
            for old_item in old_list:
                merged_old = dict(old_item)
                if isinstance(nw.get("endereco"), dict):
                    merged_old["endereco"] = ChatbotService._merge_endereco_dicts(
                        merged_old.get("endereco")
                        if isinstance(merged_old.get("endereco"), dict)
                        else {},
                        nw["endereco"],
                    )
                for chave in (
                    "latitude",
                    "longitude",
                    "coordenadas_fonte",
                    "coordenadas_observacao",
                    "endereco_informado_usuario",
                ):
                    if nw.get(chave) not in (None, "", []) and merged_old.get(chave) in (
                        None,
                        "",
                        [],
                    ):
                        merged_old[chave] = nw[chave]
                ChatbotService._normalizar_item_pedido_composto(merged_old)
                ChatbotService._normalizar_sinapse_id_rascunho(merged_old)
                out_preservado.append(merged_old)
            return out_preservado
        out: list[dict[str, Any]] = []
        for i, nw in enumerate(new_list):
            merged: dict[str, Any] = dict(old_list[i]) if i < len(old_list) else {}
            for k, v in nw.items():
                if k == "endereco":
                    merged["endereco"] = ChatbotService._merge_endereco_dicts(
                        merged.get("endereco") if isinstance(merged.get("endereco"), dict) else {},
                        v if isinstance(v, dict) else {},
                    )
                elif k in ("descricao", "pedido_integral"):
                    novo = str(v).strip() if v not in (None, "", []) else ""
                    antigo = str(merged.get(k) or "").strip()
                    if len(novo) > len(antigo):
                        merged[k] = v
                    elif antigo:
                        merged[k] = merged.get(k) or antigo
                elif k == "titulo":
                    novo = str(v).strip() if v not in (None, "", []) else ""
                    antigo = str(merged.get(k) or "").strip()
                    if (
                        antigo
                        and ChatbotService._titulo_eh_generico(novo)
                        and not ChatbotService._titulo_eh_generico(antigo)
                    ):
                        merged[k] = antigo
                    elif (
                        antigo
                        and ChatbotService._titulo_menciona_multiplos_eixos(novo)
                        and not ChatbotService._titulo_menciona_multiplos_eixos(antigo)
                    ):
                        merged[k] = antigo
                    elif v not in (None, "", []):
                        merged[k] = v
                elif v not in (None, "", []):
                    merged[k] = v
            for k in (
                "servico_local_id",
                "sinapse_servico_id_sugerido",
                "titulo",
                "descricao",
                "pedido_integral",
                "texto_para_embedding",
                "candidatos_sinapse",
                "competencia_municipal",
                "categoria_orientacao",
                "motivo_recusa",
                "faq_orientacao",
                "latitude",
                "longitude",
                "coordenadas_fonte",
                "_geo_chave",
                "endereco_informado_usuario",
                "endereco_opcional_dispensado",
                "anexos_indices",
            ):
                if merged.get(k) in (None, "", []) and i < len(old_list):
                    ov = old_list[i].get(k)
                    if ov not in (None, "", []):
                        merged[k] = ov
            if not isinstance(merged.get("endereco"), dict) and i < len(old_list):
                oe = old_list[i].get("endereco")
                if isinstance(oe, dict):
                    merged["endereco"] = dict(oe)
            ChatbotService._normalizar_sinapse_id_rascunho(merged)
            out.append(merged)
        return out

    @staticmethod
    def _endereco_minimo_para_protocolo(item: dict[str, Any]) -> bool:
        end = item.get("endereco")
        if not isinstance(end, dict):
            return False
        cep = str(end.get("cep") or "").replace("-", "").strip()
        logr = (end.get("logradouro") or "").strip()
        bairro = (end.get("bairro") or "").strip()
        if len(cep) >= 8 and cep.isdigit():
            return len(logr) >= 4 or len(bairro) >= 3
        return len(logr) >= 8 and len(bairro) >= 3

    @staticmethod
    def _endereco_real_do_usuario(item: dict[str, Any]) -> bool:
        """Endereço válido informado explicitamente (não inferido do relato inicial)."""
        end = item.get("endereco")
        if not isinstance(end, dict):
            return False
        logr = (end.get("logradouro") or "").strip()
        bairro = (end.get("bairro") or "").strip()
        cep = str(end.get("cep") or "").replace("-", "").strip()
        if cep and len(cep) >= 8 and cep.isdigit():
            return bool(
                logr and ChatbotService._valor_campo_endereco_valido("logradouro", logr)
            ) or bool(
                bairro and ChatbotService._valor_campo_endereco_valido("bairro", bairro)
            )
        if logr and ChatbotService._valor_campo_endereco_valido("logradouro", logr):
            if ChatbotService._extrair_nome_parque(logr):
                return True
            return len(bairro) >= 2 and ChatbotService._valor_campo_endereco_valido(
                "bairro", bairro
            )
        return False

    @staticmethod
    def _endereco_suficiente_para_triagem(item: dict[str, Any]) -> bool:
        """Alias para compatibilidade interna — mesma regra rígida de endereço real."""
        return ChatbotService._endereco_real_do_usuario(item)

    @staticmethod
    def _extrair_endereco_livre(texto: str) -> dict[str, Any]:
        texto = ChatbotService._texto_util_para_extracao_endereco(texto or "")
        t = (texto or "").strip()
        out: dict[str, Any] = {
            "cep": None,
            "logradouro": None,
            "numero": None,
            "bairro": None,
            "complemento": None,
        }
        if not t:
            return out
        m_cep = re.search(r"\b(\d{5})-?(\d{3})\b", t)
        if m_cep:
            out["cep"] = f"{m_cep.group(1)}-{m_cep.group(2)}"
        m_num = re.search(
            r"(?:altura|n[º°]|número|num\.?)\s*(?:do\s*|da\s*)?(\d{1,5})\b",
            t,
            re.IGNORECASE,
        )
        if m_num:
            out["numero"] = m_num.group(1)
        bairro_exp = ChatbotService._extrair_bairro_explicito(t)
        if bairro_exp:
            out["bairro"] = bairro_exp
        parts = [p.strip() for p in t.split(",") if p.strip()]
        for p in parts:
            pl = p.lower()
            if re.match(
                r"^(?:rua|r\.?\s+|av\.?\s+|avenida\s+|trav\.?\s+|travessa\s+|al\.?\s+|alameda\s+)",
                pl,
                re.IGNORECASE,
            ) or " rua " in pl:
                out["logradouro"] = re.sub(
                    r"\s*na\s+altura\s+do\s*",
                    " ",
                    p,
                    flags=re.IGNORECASE,
                ).strip()[:240]
                break
        if not (out.get("logradouro") or "").strip():
            parque = ChatbotService._extrair_nome_parque(t)
            if parque:
                out["logradouro"] = parque
        if not (out.get("logradouro") or "").strip() and parts:
            first = parts[0]
            from core.services.endereco_normalizacao import normalizar_logradouro

            first_norm = normalizar_logradouro(first)
            candidato = first_norm if ChatbotService._valor_campo_endereco_valido(
                "logradouro", first_norm
            ) else first
            if (
                not re.fullmatch(r"\d+", candidato)
                and "cep" not in candidato.lower()
                and ChatbotService._valor_campo_endereco_valido("logradouro", candidato)
            ):
                out["logradouro"] = candidato[:240]
        if not ChatbotService._campo_endereco_str(out.get("numero")):
            for i, p in enumerate(parts):
                ps = p.strip()
                if not re.fullmatch(r"\d{1,5}", ps):
                    continue
                if i == 0 and len(parts) > 1:
                    continue
                cep_flat = (out.get("cep") or "").replace("-", "")
                if cep_flat and ps in cep_flat:
                    continue
                out["numero"] = ps
                break
        if not out.get("bairro"):
            for p in parts[1:]:
                seg = p.strip()
                if not seg:
                    continue
                if re.search(r"\b\d{5}-?\d{3}\b", seg):
                    continue
                if re.fullmatch(r"\d{1,5}", seg):
                    continue
                if re.match(
                    r"^(?:rua|r\.?\s+|av\.?\s+|avenida\s+|trav\.?\s+|travessa\s+|al\.?\s+|alameda\s+)",
                    seg,
                    re.IGNORECASE,
                ):
                    continue
                if ChatbotService._valor_campo_endereco_valido("bairro", seg):
                    out["bairro"] = seg[:120]
                    break
        if not out.get("bairro"):
            for p in parts[1:]:
                seg = p.strip()
                if re.search(r"\b\d{5}-?\d{3}\b", seg):
                    continue
                m_bairro = re.search(r"[-–]\s*([^-–]+?)(?:\s*-\s*[A-Z]{2}\b|$)", seg)
                if m_bairro:
                    cand = m_bairro.group(1).strip(" .")
                    if ChatbotService._valor_campo_endereco_valido("bairro", cand):
                        out["bairro"] = cand[:120]
                        break
        if out.get("logradouro"):
            from core.services.endereco_normalizacao import normalizar_logradouro

            out["logradouro"] = normalizar_logradouro(out["logradouro"])[:240]
        if out.get("bairro"):
            from core.services.endereco_normalizacao import normalizar_bairro

            out["bairro"] = normalizar_bairro(out["bairro"])[:120]
        from core.services.endereco_parsing_service import EnderecoParsingService

        return EnderecoParsingService().enriquecer_com_llm(out, t)

    @staticmethod
    def _texto_resumo_confirmacao(item: dict[str, Any]) -> str:
        tit = (item.get("titulo") or "Demanda").strip() or "Demanda"
        end = item.get("endereco") if isinstance(item.get("endereco"), dict) else {}
        cep = (end.get("cep") or "—").strip()
        log = (end.get("logradouro") or "—").strip()
        num = ChatbotService._campo_endereco_str(end.get("numero"))
        suf_num = f", nº {num}" if num else ""
        bai = (end.get("bairro") or "").strip()
        suf_bai = f" — bairro {bai}" if bai else ""
        return (
            f"Resumo do pedido: {tit} em {log}{suf_num}, CEP {cep}{suf_bai}. "
            "Está correto? Responda sim para criar o rascunho no sistema ou diga o que deseja ajustar."
        )

    def _refinar_apos_escolha_numerica(self, parsed: dict[str, Any], texto: str) -> None:
        """Após merge com sessão: escolha só com dígitos → estado explícito e mensagem clara."""
        t = (texto or "").strip()
        if not re.fullmatch(r"[1-9]|1[0-9]", t):
            return
        dems = parsed.get("demandas_extraidas")
        if not isinstance(dems, list) or not dems or not isinstance(dems[0], dict):
            return
        d0 = dems[0]
        if d0.get("servico_local_id") is None and d0.get("sinapse_servico_id_sugerido") is None:
            return
        if parsed.get("usuario_forneceu_endereco_real") is True:
            parsed["estado_atual"] = ChatSession.ESTADO_VALIDACAO_FINAL
            parsed["resposta_agente"] = self._texto_resumo_confirmacao(d0)
            return
        parsed["estado_atual"] = ChatSession.ESTADO_COLETA_ENDERECO
        parsed["usuario_forneceu_endereco_real"] = False
        titulo_op = (d0.get("titulo") or "o serviço escolhido").strip()
        parsed["resposta_agente"] = (
            f"Registrei a opção «{titulo_op}». "
            "Para eu seguir, me diga o endereço: CEP, ou rua/avenida com bairro (o número ajuda, mas não é obrigatório)."
        )

    def _fallback_endereco_e_resumo(self, parsed: dict[str, Any], texto: str) -> None:
        """Se o Groq deixar resposta_agente vazia, preenche endereço a partir do texto e monta o resumo."""
        if parsed.get("usuario_forneceu_endereco_real") is not True:
            return
        ra = (parsed.get("resposta_agente") or "").strip()
        if ra:
            return
        dems = parsed.get("demandas_extraidas")
        if not isinstance(dems, list) or not dems or not isinstance(dems[0], dict):
            return
        d0 = dems[0]
        if d0.get("servico_local_id") is None and d0.get("sinapse_servico_id_sugerido") is None:
            return
        t = self._texto_util_para_extracao_endereco(texto or "")
        if len(t) < 8:
            return
        if re.fullmatch(r"[1-9]|1[0-9]", t):
            return
        ext = self._extrair_endereco_livre(t)
        if not any(ext.get(k) for k in ("cep", "logradouro", "bairro", "numero")):
            return
        cur = d0.get("endereco") if isinstance(d0.get("endereco"), dict) else {}
        d0["endereco"] = self._merge_endereco_dicts(cur, ext)
        d0["endereco_informado_usuario"] = True
        self._sanitizar_endereco_demanda(d0)
        if parsed.get("usuario_forneceu_endereco_real") is True:
            parsed["estado_atual"] = ChatSession.ESTADO_VALIDACAO_FINAL
            parsed["resposta_agente"] = self._texto_resumo_confirmacao(d0)
        else:
            self._limpar_enderecos_demandas([d0])
            parsed["estado_atual"] = ChatSession.ESTADO_COLETA_ENDERECO
            parsed["usuario_forneceu_endereco_real"] = False
            parsed["acionar_triagem_sinapse"] = False
            parsed["resposta_agente"] = ChatbotService._resposta_pedir_endereco(parsed)

    @staticmethod
    def _texto_parece_ter_referencia_local(texto: str) -> bool:
        t = (texto or "").strip().lower()
        if not t:
            return False
        if re.search(r"\b\d{5}-?\d{3}\b", t):
            return True
        if re.search(
            r"\b(rua|r\.|av\.?|avenida|estrada|rodovia|alameda|travessa|viela|praça|praia)\b",
            t,
        ):
            return True
        if "bairro" in t or "cep" in t or "km " in t:
            return True
        return False

    def _fallback_coleta_sem_resposta_llm(self, parsed: dict[str, Any], texto: str) -> None:
        """Quando o Groq devolve `resposta_agente` vazio (ex.: só tipo de serviço, sem local)."""
        if (parsed.get("resposta_agente") or "").strip():
            return
        t = (texto or "").strip()
        if len(t) < 4:
            return
        dems = parsed.get("demandas_extraidas")
        d0: dict[str, Any] = {}
        if isinstance(dems, list) and dems and isinstance(dems[0], dict):
            d0 = dems[0]
        if d0.get("servico_local_id") is not None:
            logger.warning(
                "Copiloto: resposta vazia com servico_local_id=%s; aguardando outros fallbacks.",
                d0.get("servico_local_id"),
            )
            return
        est = parsed.get("estado_atual")
        if est == ChatSession.ESTADO_VALIDACAO_FINAL:
            parsed["resposta_agente"] = (
                "Não consegui reler o resumo. Responda sim para criar o rascunho no sistema "
                "ou diga o que deseja ajustar."
            )
            logger.warning("Copiloto: resposta vazia em VALIDACAO_FINAL.")
            return
        if self._texto_parece_ter_referencia_local(t):
            parsed["resposta_agente"] = (
                "Pelo que você escreveu, parece haver um endereço ou referência de local. "
                "Vou usar isso na próxima etapa; se faltar algum detalhe, eu pergunto só o necessário."
            )
            parsed.setdefault("estado_atual", ChatSession.ESTADO_COLETA_DADOS)
            logger.warning(
                "Copiloto: resposta_agente vazio com possível local (len=%s); pedindo consolidação.",
                len(t),
            )
            return
        slot = {
            "titulo": t[:120],
            "descricao": t,
            "texto_para_embedding": t[:500],
            "endereco": {
                "cep": None,
                "logradouro": None,
                "numero": None,
                "bairro": None,
                "complemento": None,
            },
            "servico_local_id": None,
            "sinapse_servico_id_sugerido": None,
        }
        if not isinstance(dems, list) or not dems:
            parsed["demandas_extraidas"] = [slot]
        elif isinstance(dems[0], dict):
            d0 = dems[0]
            d0.setdefault("titulo", slot["titulo"])
            d0.setdefault("descricao", slot["descricao"])
            d0.setdefault("texto_para_embedding", slot["texto_para_embedding"])
            d0.setdefault("endereco", slot["endereco"])
        parsed["resposta_agente"] = (
            "Entendi o pedido. Para cruzar com o catálogo de serviços, preciso saber onde é: "
            "CEP ou rua/avenida com bairro (como você preferir anotar)."
        )
        parsed["estado_atual"] = ChatSession.ESTADO_COLETA_DADOS
        logger.warning(
            "Copiloto: resposta_agente vazio do Groq; fallback pedindo local (len_user=%s, estado_llm=%s).",
            len(t),
            est,
        )

    def _persistir_apos_turno(
        self,
        session: ChatSession,
        historico: list[dict[str, Any]],
        parsed: dict[str, Any],
    ) -> None:
        session.historico_mensagens = historico
        session.estado_atual = parsed.get("estado_atual", session.estado_atual)
        session.demandas_rascunho = self._merge_demandas_rascunho(
            session.demandas_rascunho,
            parsed.get("demandas_extraidas"),
        )
        texto_sessao = self._texto_usuario_da_sessao(session)
        self._pre_classificar_faq_em_lista(session.demandas_rascunho or [], texto_sessao=texto_sessao)
        self._sanitizar_enderecos_demandas(session.demandas_rascunho or [])
        self._aplicar_classificacao_competencia_rascunho(
            session.demandas_rascunho or [],
            texto_sessao=texto_sessao,
        )
        self._limpar_triagem_fora_competencia(session.demandas_rascunho or [])
        bloqueados = self._indices_fora_competencia(session.demandas_rascunho or [])
        if bloqueados:
            msg_fc = self._mensagem_chat_fora_competencia(session.demandas_rascunho or [])
            if msg_fc and parsed.get("estado_atual") != ChatSession.ESTADO_VALIDACAO_FINAL:
                parsed["resposta_agente"] = msg_fc
                parsed["estado_atual"] = ChatSession.ESTADO_COLETA_DADOS
                session.estado_atual = ChatSession.ESTADO_COLETA_DADOS
        session.save(
            update_fields=[
                "historico_mensagens",
                "estado_atual",
                "demandas_rascunho",
                "atualizado_em",
            ]
        )

    @staticmethod
    def _limiar_carta_copiloto() -> float:
        return float(getattr(settings, "COPILOTO_CARTA_SCORE_MINIMO", 0.6666))

    def _tem_match_forte_na_carta(
        self, item: dict[str, Any], *, texto_sessao: str = ""
    ) -> bool:
        cands = item.get("candidatos_sinapse")
        if not isinstance(cands, list) or not cands:
            return False
        if (self._score_max_candidatos(item) or 0.0) < self._limiar_carta_copiloto():
            return False
        melhor = self._melhor_candidato_dict(item)
        if not melhor:
            return False
        texto = self._texto_coerencia_demanda(item, texto_sessao)
        return self._coerencia_texto_servico(texto, (melhor.get("titulo") or ""))

    _DOMINIO_MUNICIPAL_INDICIOS = frozenset(
        {
            "burac",
            "tapa",
            "lombad",
            "ilumin",
            "luminar",
            "lampad",
            "poste",
            "entulh",
            "lixo",
            "coleta",
            "limpez",
            "capina",
            "poda",
            "arvore",
            "árvore",
            "galho",
            "bueiro",
            "esgoto",
            "agua",
            "água",
            "encan",
            "fiscaliz",
            "vistoria",
            "alvará",
            "alvara",
            "licenc",
            "licenç",
            "parque",
            "praça",
            "praca",
            "via",
            "rua",
            "avenida",
            "calçada",
            "calcada",
            "paviment",
            "asfalt",
            "transito",
            "trânsito",
            "sinaliz",
            "fechament",
            "interdic",
            "zelador",
            "denunci",
            "ocupação",
            "ocupacao",
            "irregular",
            "constru",
            "habit",
            "moradia",
            "escorpi",
            "mosquito",
            "dengue",
            "animal",
            "cachorro",
            "gato",
            "evento",
            "reserva",
            "oficio",
            "ofício",
            "taxista",
            "taxi",
            "táxi",
            "motorista auxiliar",
            "permissão",
            "permissao",
        }
    )

    @classmethod
    def _texto_parece_demanda_municipal(cls, texto: str) -> bool:
        t = (texto or "").lower()
        if not t:
            return False
        if detectar_faq_por_texto(texto):
            return False
        return any(ind in t for ind in cls._DOMINIO_MUNICIPAL_INDICIOS)

    @classmethod
    def _motivo_padrao_fora_competencia(cls) -> str:
        return (
            "Este pedido não corresponde a um serviço público municipal tratado pelo gabinete "
            "(zeladoria, obras, meio ambiente, saúde pública na via, etc.). Não é possível gerar ofício."
        )

    @staticmethod
    def _faq_para_item(
        item: dict[str, Any], texto: str
    ) -> dict[str, str] | None:
        cat = normalizar_categoria_orientacao(item.get("categoria_orientacao"))
        faq = faq_por_categoria(cat) if cat else None
        if not faq:
            faq = detectar_faq_por_texto(texto)
        if faq:
            item["categoria_orientacao"] = faq.categoria_orientacao
            return faq_para_dict(faq)
        return None

    @classmethod
    def _todas_demandas_competencia_negativa_llm(cls, parsed: dict[str, Any]) -> bool:
        dems = parsed.get("demandas_extraidas")
        if not isinstance(dems, list) or not dems:
            return False
        for item in dems:
            if not isinstance(item, dict):
                return False
            if normalizar_competencia_llm(item.get("competencia_municipal")) != "nao":
                return False
        return True

    def _item_fora_competencia_heuristica(
        self, item: dict[str, Any], *, texto_sessao: str = ""
    ) -> tuple[bool, str | None]:
        """Padrões explícitos + falso positivo vetorial (score alto sem coerência)."""
        texto = self._texto_coerencia_demanda(item, texto_sessao)
        if not texto.strip():
            return False, None

        for pat in _FORA_COMPETENCIA_EXPLICITO_RE:
            if pat.search(texto):
                return True, (
                    "O assunto informado não é uma solicitação de serviço público municipal "
                    "(ex.: receitas, conteúdo pessoal ou pedidos sem relação com a Prefeitura)."
                )

        if self._texto_parece_demanda_municipal(texto):
            return False, None

        melhor = self._melhor_candidato_dict(item)
        if not melhor:
            return False, None

        score = float(melhor.get("score") or 0.0)
        if score < self._limiar_carta_copiloto():
            return False, None

        nome_srv = (melhor.get("titulo") or "").strip()
        if self._coerencia_texto_servico(texto, nome_srv):
            return False, None

        logger.info(
            "Copiloto: fora de competência (score alto sem coerência municipal): pedido=%r servico=%r score=%.2f",
            texto[:80],
            nome_srv[:80],
            score,
        )
        return True, self._motivo_padrao_fora_competencia()

    def _item_fora_competencia(
        self, item: dict[str, Any], *, texto_sessao: str = ""
    ) -> tuple[bool, str | None]:
        """LLM (`competencia_municipal`) + FAQ + heurística determinística."""
        if not isinstance(item, dict):
            return False, None
        if not copiloto_faq_habilitada():
            item.pop("fora_competencia", None)
            item.pop("faq_orientacao", None)
            item.pop("motivo_recusa", None)
            item.pop("categoria_orientacao", None)
            if not item.get("competencia_municipal"):
                item["competencia_municipal"] = "sim"
            return False, None
        if self._resolver_sinapse_id(item) or self._item_vinculo_catalogo_resolvido(item):
            return False, None

        texto = self._texto_coerencia_demanda(item, texto_sessao)
        if not texto.strip():
            return False, None

        faq_dict = self._faq_para_item(item, texto)
        comp = normalizar_competencia_llm(item.get("competencia_municipal"))
        motivo_llm = (item.get("motivo_recusa") or "").strip() or None

        for pat in _FORA_COMPETENCIA_EXPLICITO_RE:
            if pat.search(texto):
                motivo = montar_motivo_recusa(
                    motivo_llm=motivo_llm,
                    faq=faq_por_categoria(item.get("categoria_orientacao"))
                    if item.get("categoria_orientacao")
                    else detectar_faq_por_texto(texto),
                    padrao=(
                        "O assunto informado não é uma solicitação de serviço público municipal "
                        "(ex.: receitas, conteúdo pessoal ou pedidos sem relação com a Prefeitura)."
                    ),
                )
                if faq_dict:
                    item["faq_orientacao"] = faq_dict
                return True, motivo

        # Indícios municipais prevalecem sobre FAQ/LLM errado (ex.: inscrição de taxista ≠ Procon)
        if self._texto_parece_demanda_municipal(texto):
            item.pop("faq_orientacao", None)
            item.pop("categoria_orientacao", None)
            item["competencia_municipal"] = "sim"
            return False, None

        if faq_dict and comp != "sim":
            item["faq_orientacao"] = faq_dict
            faq_obj = faq_por_categoria(item.get("categoria_orientacao"))
            return True, montar_motivo_recusa(
                motivo_llm=motivo_llm,
                faq=faq_obj,
                padrao=self._motivo_padrao_fora_competencia(),
            )

        if comp == "sim":
            item.pop("faq_orientacao", None)
            return False, None

        if comp == "nao":
            if self._texto_parece_demanda_municipal(texto):
                logger.info(
                    "Copiloto: LLM competencia_municipal=nao com indícios municipais; mantendo na carta. pedido=%r",
                    texto[:80],
                )
                item.pop("faq_orientacao", None)
                item.pop("categoria_orientacao", None)
                item["competencia_municipal"] = "sim"
                return False, None
            if faq_dict:
                item["faq_orientacao"] = faq_dict
            faq_obj = faq_por_categoria(item.get("categoria_orientacao"))
            return True, montar_motivo_recusa(
                motivo_llm=motivo_llm,
                faq=faq_obj,
                padrao=self._motivo_padrao_fora_competencia(),
            )

        hc, hm = self._item_fora_competencia_heuristica(item, texto_sessao=texto_sessao)
        if hc:
            if faq_dict:
                item["faq_orientacao"] = faq_dict
            faq_obj = faq_por_categoria(item.get("categoria_orientacao")) or detectar_faq_por_texto(
                texto
            )
            return True, montar_motivo_recusa(
                motivo_llm=motivo_llm,
                faq=faq_obj,
                padrao=hm,
            )

        item.pop("faq_orientacao", None)
        return False, None

    def _aplicar_classificacao_competencia_rascunho(
        self, rascunho: list[Any], *, texto_sessao: str = ""
    ) -> bool:
        alterou = False
        for item in rascunho or []:
            if not isinstance(item, dict):
                continue
            fc, motivo = self._item_fora_competencia(item, texto_sessao=texto_sessao)
            if item.get("fora_competencia") != fc:
                alterou = True
            item["fora_competencia"] = fc
            if fc:
                item["motivo_recusa"] = motivo
                item["candidatos_sinapse"] = []
                item.pop("sinapse_servico_id_sugerido", None)
                item.pop("servico_local_id", None)
                faq_dict = self._faq_para_item(item, self._texto_coerencia_demanda(item, texto_sessao))
                if faq_dict:
                    item["faq_orientacao"] = faq_dict
            else:
                item.pop("motivo_recusa", None)
                item.pop("faq_orientacao", None)
        return alterou

    def _alinhar_resposta_agente_ouvidoria(self, parsed: dict[str, Any]) -> None:
        dems = parsed.get("demandas_extraidas")
        if not isinstance(dems, list) or not dems:
            return
        ativos = [
            x
            for x in dems
            if isinstance(x, dict) and not x.get("fora_competencia") and not x.get("descartada")
        ]
        if not ativos or not all(self._item_trilha_ouvidoria(x) for x in ativos):
            return
        parsed["acionar_triagem_sinapse"] = False
        resposta_atual = (parsed.get("resposta_agente") or "").strip().lower()
        deslocar_carta = any(
            termo in resposta_atual
            for termo in (
                "carta de serviços",
                "carta de servicos",
                "tendência",
                "tendencia",
                "escolha no painel",
            )
        )
        if resposta_atual and not deslocar_carta:
            return
        subtipos = {
            str(x.get("subtipo_ouvidoria") or (x.get("trilha_ouvidoria") or {}).get("subtipo") or "")
            for x in ativos
        }
        if subtipos == {"sugestao"}:
            parsed["resposta_agente"] = (
                "Identifiquei sua manifestação como sugestão à Ouvidoria Geral. "
                "O serviço já está vinculado — revise o painel e confirme para gerar o ofício."
            )
            return
        if subtipos == {"elogio"}:
            parsed["resposta_agente"] = (
                "Identifiquei seu elogio para registro na Ouvidoria Geral. "
                "Revise o painel e confirme para gerar o ofício."
            )
            return
        if subtipos == {"denuncia"}:
            parsed["resposta_agente"] = (
                "Identifiquei sua denúncia para protocolo na Ouvidoria Geral. "
                "Revise o painel e confirme para gerar o ofício."
            )
            return
        parsed["resposta_agente"] = (
            "Registrei sua manifestação para a Ouvidoria Geral. "
            "Revise o painel e confirme para gerar o ofício."
        )

    def _aplicar_trilha_ouvidoria_rascunho(
        self, rascunho: list[Any], *, texto_sessao: str = ""
    ) -> bool:
        """Trilha A′ (O1): força serviço Ouvidoria quando o teor for manifestação institucional."""
        from core.services.copiloto_ouvidoria import (
            detectar_teoria_ouvidoria,
            orientacao_ouvidoria,
        )
        from integrations import sinapse_catalog

        alterou = False
        for item in rascunho or []:
            if not isinstance(item, dict) or item.get("fora_competencia"):
                continue
            if self._item_vinculo_catalogo_resolvido(item):
                continue
            texto = self._texto_coerencia_demanda(item, texto_sessao)
            groq_teoria = item.get("teor_ouvidoria")
            groq_subtipo = item.get("subtipo_ouvidoria")
            det = detectar_teoria_ouvidoria(
                texto,
                llm_teoria=groq_teoria,
                llm_subtipo=groq_subtipo,
            )
            if not det:
                continue
            sid = int(det["servico_sinapse_id"])
            if not sinapse_catalog.servico_existe(sid):
                continue
            catalog = sinapse_catalog.get_servico(sid)
            orgao_id = sinapse_catalog.get_orgao_id_for_servico(sid)
            item["sinapse_servico_id_sugerido"] = sid
            item["servico_local_id"] = sid
            item["servico_confirmado_usuario"] = True
            item["trilha_ouvidoria"] = {
                "subtipo": det["subtipo"],
                "motivo": det["motivo"],
                "fonte_classificacao": det["fonte_classificacao"],
                "detalhe_fonte": det["detalhe_fonte"],
                "agente_teoria": det.get("agente_teoria", groq_teoria),
                "agente_subtipo": det.get("agente_subtipo", groq_subtipo),
                "orientacao": orientacao_ouvidoria(det["subtipo"]),
            }
            logger.info(
                "Copiloto ouvidoria aplicada: titulo=%r subtipo=%s fonte=%s | %s | "
                "agente_teoria=%r agente_subtipo=%r",
                (item.get("titulo") or "")[:80],
                det["subtipo"],
                det["fonte_classificacao"],
                det["detalhe_fonte"],
                det.get("agente_teoria", groq_teoria),
                det.get("agente_subtipo", groq_subtipo),
            )
            item["teor_ouvidoria"] = True
            item["subtipo_ouvidoria"] = det["subtipo"]
            item["endereco_opcional_dispensado"] = True
            item["candidatos_sinapse"] = [
                {
                    "servico_id": sid,
                    "titulo": (catalog.titulo if catalog else "Ouvidoria"),
                    "orgao": sinapse_catalog.get_orgao_nome(orgao_id) or "Ouvidoria Geral",
                    "score": 1.0,
                }
            ]
            item.pop("candidatos_revisao", None)
            alterou = True
        return alterou

    @staticmethod
    def _item_trilha_ouvidoria(item: dict[str, Any]) -> bool:
        return bool(isinstance(item, dict) and item.get("trilha_ouvidoria"))

    @staticmethod
    def _indices_fora_competencia(rascunho: list[Any]) -> list[int]:
        out: list[int] = []
        for i, item in enumerate(rascunho or []):
            if isinstance(item, dict) and item.get("fora_competencia"):
                out.append(i)
        return out

    def _mensagem_chat_fora_competencia(self, rascunho: list[Any]) -> str:
        msg = montar_resposta_chat_fora_competencia(rascunho)
        if msg:
            return msg
        indices = self._indices_fora_competencia(rascunho)
        if not indices:
            return ""
        titulos: list[str] = []
        for i in indices:
            item = rascunho[i]
            if isinstance(item, dict):
                t = (item.get("titulo") or f"Solicitação {i + 1}").strip()
                titulos.append(f"«{t}»")
        lista = ", ".join(titulos) if titulos else "o pedido informado"
        return (
            f"Não consigo dar continuidade a {lista}: não se trata de um serviço público municipal "
            "atendido pelo gabinete. Reformule descrevendo um problema de zeladoria, obras, meio ambiente "
            "ou outro serviço da Prefeitura — ou use o cadastro tradicional se for outro assunto."
        )

    @staticmethod
    def _usuario_modo_indicacao(usuario) -> bool:
        return getattr(usuario, "perfil", None) == "CAMARA"

    @classmethod
    def _marcar_rascunho_indicacao(cls, rascunho: list[Any], usuario) -> None:
        if not cls._usuario_modo_indicacao(usuario):
            return
        for item in rascunho or []:
            if not isinstance(item, dict):
                continue
            item["modo_indicacao"] = True

    @staticmethod
    def _indicacao_metadados_ok(item: dict[str, Any]) -> bool:
        ids = item.get("vereadores_vinculados_ids") or []
        if not ids:
            return False
        try:
            numero = int(item.get("numero_indicacao"))
        except (TypeError, ValueError):
            return False
        return numero >= 1

    def _indices_indicacao_incompleta(self, rascunho: list[Any]) -> list[int]:
        out: list[int] = []
        for i, item in enumerate(rascunho or []):
            if not isinstance(item, dict):
                continue
            if item.get("descartada") or item.get("fora_competencia"):
                continue
            if not item.get("modo_indicacao"):
                continue
            if not self._indicacao_metadados_ok(item):
                out.append(i)
        return out

    @staticmethod
    def _sessao_tem_anexo_pdf(session: ChatSession) -> bool:
        for anexo in session.anexos_sessao.all():
            nome = (getattr(anexo.arquivo, "name", None) or str(anexo.arquivo or "")).lower()
            if nome.endswith(".pdf"):
                return True
        return False

    def _indices_demandas_sem_servico_confirmado(self, rascunho: list[Any]) -> list[int]:
        out: list[int] = []
        for i, item in enumerate(rascunho or []):
            if not isinstance(item, dict):
                continue
            if item.get("fora_competencia"):
                continue
            if item.get("descartada"):
                continue
            if self._resolver_sinapse_id(item) is not None:
                continue
            if self._item_vinculo_catalogo_resolvido(item):
                continue
            if item.get("tendencia_id") or item.get("origem_vinculo") == Demanda.ORIGEM_VINCULO_TENDENCIA:
                continue
            if self._servico_confirmado_pelo_usuario(item) and self._resolver_sinapse_id(item):
                continue
            out.append(i)
        return out

    def _indices_servico_incoerente(self, rascunho: list[Any]) -> list[int]:
        out: list[int] = []
        for i, item in enumerate(rascunho or []):
            if not isinstance(item, dict):
                continue
            if item.get("descartada"):
                continue
            if not self._servico_confirmado_pelo_usuario(item):
                continue
            if self._escolha_carta_explicita_usuario(item):
                continue
            sid = self._resolver_sinapse_id(item)
            if not sid:
                continue
            catalog = sinapse_catalog.get_servico(sid)
            nome = (catalog.titulo if catalog else "") or ""
            texto_coh = self._texto_coerencia_demanda(item)
            if not self._coerencia_texto_servico(texto_coh, nome):
                out.append(i)
        return out

    def _indices_servico_informativo(self, rascunho: list[Any]) -> list[int]:
        from core.services.carta_utilizacao_service import CartaUtilizacaoService

        svc = CartaUtilizacaoService()
        out: list[int] = []
        for i, item in enumerate(rascunho or []):
            if not isinstance(item, dict):
                continue
            if item.get("fora_competencia") or item.get("descartada"):
                continue
            sid = self._resolver_sinapse_id(item)
            if not sid:
                continue
            if not svc.pode_protocolar(sid):
                out.append(i)
        return out

    @staticmethod
    def _filtrar_rascunho_para_materializacao(
        rascunho: list[Any],
        *,
        indices_aprovados: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for i, item in enumerate(rascunho or []):
            if not isinstance(item, dict):
                continue
            if item.get("descartada"):
                continue
            if indices_aprovados is not None and i not in indices_aprovados:
                continue
            if indices_aprovados is None and item.get("aprovado_final") is False:
                continue
            out.append(item)
        return out

    _ETAPAS_REVISAO_COPILOTO = frozenset({"pedido", "servico", "local", "anexos"})

    @classmethod
    def _desconfirmar_servico_item(cls, item: dict[str, Any]) -> None:
        item.pop("servico_confirmado_usuario", None)
        item.pop("sinapse_servico_id_sugerido", None)
        item.pop("servico_local_id", None)
        item.pop("tendencia_id", None)
        item.pop("tendencia", None)
        item.pop("origem_vinculo", None)
        item.pop("vinculo_servico_ignorado", None)

    @classmethod
    def _resetar_local_demanda_item(cls, item: dict[str, Any]) -> None:
        item["endereco"] = dict(_ENDERECO_VAZIO)
        for k in (
            "latitude",
            "longitude",
            "coordenadas_fonte",
            "_geo_chave",
            "endereco_informado_usuario",
            "endereco_opcional_dispensado",
            "local_confirmado_usuario",
            "_eixo_pedido",
        ):
            item.pop(k, None)

    @classmethod
    def _vinculo_servico_snapshot(cls, item: dict[str, Any]) -> tuple[str, int] | None:
        if item.get("tendencia_id"):
            try:
                return ("tendencia", int(item["tendencia_id"]))
            except (TypeError, ValueError):
                pass
        sid = cls._resolver_sinapse_id_confirmado(item)
        if sid is not None:
            return ("carta", int(sid))
        return None

    def _resetar_anexos_demanda_sessao(
        self,
        session: ChatSession,
        rascunho: list[Any],
        indice_demanda: int,
    ) -> None:
        if 0 <= indice_demanda < len(rascunho):
            item = rascunho[indice_demanda]
            if isinstance(item, dict):
                item["anexos_indices"] = []
        ids_remover: list[int] = []
        for anexo in session.anexos_sessao.all():
            if getattr(anexo, "indice_demanda", None) == indice_demanda:
                ids_remover.append(anexo.pk)
        if ids_remover:
            ChatSessaoAnexo.objects.filter(pk__in=ids_remover).delete()
        self._propagar_anexos_indices_rascunho(session)

    @classmethod
    def _item_tem_local_inferido_pendente(cls, item: dict[str, Any]) -> bool:
        if item.get("fora_competencia") or item.get("descartada"):
            return False
        if not cls._item_requer_localizacao(item):
            return False
        if item.get("endereco_opcional_dispensado"):
            return False
        em_revisao_local = item.get("_revisao_etapa") == "local"
        if not em_revisao_local and cls._item_local_confirmado_usuario(item):
            return False
        if item.get("_revisao_etapa") == "local":
            if item.get("latitude") is not None and item.get("longitude") is not None:
                return True
            end = item.get("endereco") if isinstance(item.get("endereco"), dict) else {}
            logr = (end.get("logradouro") or "").strip()
            bairro = (end.get("bairro") or "").strip()
            cep = (end.get("cep") or "").strip()
            if logr and (bairro or cep):
                return True
            return False
        if item.get("latitude") is not None and item.get("longitude") is not None:
            return True
        end = item.get("endereco") if isinstance(item.get("endereco"), dict) else {}
        logr = (end.get("logradouro") or "").strip()
        bairro = (end.get("bairro") or "").strip()
        cep = (end.get("cep") or "").strip()
        if logr and (bairro or cep):
            return True
        return False

    @classmethod
    def _copiar_endereco_irmao_sessao(
        cls,
        item: dict[str, Any],
        rascunho: list[Any],
    ) -> bool:
        """Copia endereço/coords de outra solicitação da mesma sessão quando o item está incompleto."""
        end = item.get("endereco") if isinstance(item.get("endereco"), dict) else {}
        tem_endereco = bool(
            cls._campo_endereco_str(end.get("logradouro"))
            and (
                cls._campo_endereco_str(end.get("bairro"))
                or cls._campo_endereco_str(end.get("cep"))
            )
        )
        if tem_endereco and item.get("latitude") is not None:
            return False
        for outro in rascunho or []:
            if outro is item or not isinstance(outro, dict):
                continue
            if outro.get("descartada") or outro.get("fora_competencia"):
                continue
            end_out = outro.get("endereco") if isinstance(outro.get("endereco"), dict) else {}
            if not (
                cls._campo_endereco_str(end_out.get("logradouro"))
                and (
                    cls._campo_endereco_str(end_out.get("bairro"))
                    or cls._campo_endereco_str(end_out.get("cep"))
                )
            ):
                continue
            if not isinstance(item.get("endereco"), dict):
                item["endereco"] = dict(_ENDERECO_VAZIO)
            end = item["endereco"]
            for chave in ("cep", "logradouro", "numero", "bairro", "complemento"):
                if not cls._campo_endereco_str(end.get(chave)) and cls._campo_endereco_str(
                    end_out.get(chave)
                ):
                    end[chave] = end_out[chave]
            if item.get("latitude") is None and outro.get("latitude") is not None:
                item["latitude"] = outro["latitude"]
                item["longitude"] = outro["longitude"]
                item["coordenadas_fonte"] = outro.get("coordenadas_fonte")
                item["_geo_chave"] = outro.get("_geo_chave")
            return True
        return False

    @staticmethod
    def _texto_curto_demanda(item: dict[str, Any]) -> str:
        end = item.get("endereco") if isinstance(item.get("endereco"), dict) else {}
        partes = [
            (item.get("titulo") or "").strip(),
            (item.get("pedido_integral") or "").strip(),
            (item.get("descricao") or "").strip(),
            ChatbotService._campo_endereco_str(end.get("logradouro")),
            ChatbotService._campo_endereco_str(end.get("bairro")),
            ChatbotService._campo_endereco_str(end.get("cep")),
        ]
        return " ".join(p for p in partes if p)

    def _campos_endereco_ui(
        self,
        item: dict[str, Any],
        *,
        texto_contexto: str | None = None,
    ) -> dict[str, Any]:
        end = item.get("endereco") if isinstance(item.get("endereco"), dict) else {}
        logradouro = self._limpar_logradouro(
            ChatbotService._campo_endereco_str(end.get("logradouro")) or None,
            texto_contexto=texto_contexto,
        )
        bairro = ChatbotService._limpar_bairro(
            ChatbotService._campo_endereco_str(end.get("bairro")) or None,
            texto_contexto=texto_contexto,
        )
        cep_raw = ChatbotService._campo_endereco_str(end.get("cep")) or None
        cep = (
            cep_raw
            if cep_raw and self._valor_campo_endereco_valido("cep", cep_raw)
            else None
        )
        if logradouro and not self._valor_campo_endereco_valido("logradouro", logradouro):
            logradouro = None
        if bairro and not self._valor_campo_endereco_valido("bairro", bairro):
            bairro = None
        if not logradouro:
            bairro = None
        numero = end.get("numero") if logradouro else None
        complemento = end.get("complemento") if logradouro else None
        return {
            "cep": cep,
            "logradouro": logradouro,
            "bairro": bairro,
            "numero": numero,
            "complemento": complemento,
        }

    def _persistir_endereco_validado_item(
        self,
        item: dict[str, Any],
        *,
        texto_contexto: str | None = None,
        rascunho: list[Any] | None = None,
    ) -> bool:
        """Normaliza e grava endereço no rascunho; retorna se há local confirmável."""
        if rascunho:
            self._copiar_endereco_irmao_sessao(item, rascunho)
        texto = texto_contexto or self._texto_curto_demanda(item)
        self._aplicar_endereco_canonico(item, texto, preservar_existente=True)
        campos = self._campos_endereco_ui(item, texto_contexto=texto)
        if not isinstance(item.get("endereco"), dict):
            item["endereco"] = dict(_ENDERECO_VAZIO)
        end = item["endereco"]
        for chave in ("cep", "logradouro", "numero", "bairro", "complemento"):
            val = campos.get(chave)
            end[chave] = val
        tem_endereco = bool(
            campos.get("logradouro") and (campos.get("bairro") or campos.get("cep"))
        )
        tem_coords = item.get("latitude") is not None and item.get("longitude") is not None
        return tem_endereco or tem_coords

    def _hidratar_endereco_inferivel_item(
        self,
        item: dict[str, Any],
        rascunho: list[Any],
        *,
        texto_sessao: str,
    ) -> bool:
        """Reaproveita endereço já dito na sessão (ou de outra solicitação) sem confirmar."""
        if self._item_local_confirmado_usuario(item):
            return False
        if item.get("fora_competencia") or item.get("descartada"):
            return False
        if not self._item_requer_localizacao_vinculada(item):
            return False

        texto_item = self._texto_contexto_demanda(item, texto_sessao)
        self._copiar_endereco_irmao_sessao(item, rascunho)
        self._aplicar_endereco_canonico(item, texto_item, preservar_existente=True)
        campos = self._campos_endereco_ui(item, texto_contexto=texto_item)
        if isinstance(item.get("endereco"), dict):
            for chave in ("cep", "logradouro", "numero", "bairro", "complemento"):
                item["endereco"][chave] = campos.get(chave)

        if item.get("latitude") is None:
            lat, lng, fonte = self._resolver_coordenadas_item(
                item,
                GeocodingService(),
                logradouro=campos.get("logradouro"),
                bairro=campos.get("bairro"),
                cep=campos.get("cep"),
            )
            if lat is not None and lng is not None:
                item["latitude"] = round(lat, 6)
                item["longitude"] = round(lng, 6)
                item["coordenadas_fonte"] = fonte
                item["_geo_chave"] = GeocodingService.chave_endereco(
                    campos.get("logradouro"), campos.get("bairro"), campos.get("cep")
                )

        return self._item_tem_local_inferido_pendente(item)

    def _confirmar_local_inferido_rascunho(
        self,
        rascunho: list[Any],
        *,
        indice_demanda: int | None = None,
        session: ChatSession | None = None,
    ) -> bool:
        geocoder = GeocodingService()
        texto_sessao = self._texto_usuario_da_sessao(session) if session else ""
        alterou = False
        for i, item in enumerate(rascunho or []):
            if not isinstance(item, dict):
                continue
            if indice_demanda is not None and i != indice_demanda:
                continue
            if session and texto_sessao:
                self._hidratar_endereco_inferivel_item(
                    item, rascunho, texto_sessao=texto_sessao
                )
            texto_item = self._texto_curto_demanda(item)
            if not self._persistir_endereco_validado_item(
                item, texto_contexto=texto_item, rascunho=rascunho
            ):
                continue
            if not self._item_tem_local_inferido_pendente(item):
                continue
            item["endereco_informado_usuario"] = True
            item["local_confirmado_usuario"] = True
            campos = self._campos_endereco_ui(item, texto_contexto=texto_item)
            if item.get("latitude") is None or item.get("longitude") is None:
                lat, lng, fonte = self._resolver_coordenadas_item(
                    item,
                    geocoder,
                    logradouro=campos.get("logradouro"),
                    bairro=campos.get("bairro"),
                    cep=campos.get("cep"),
                )
                if lat is not None and lng is not None:
                    item["latitude"] = round(lat, 6)
                    item["longitude"] = round(lng, 6)
                    item["coordenadas_fonte"] = fonte
                    item["_geo_chave"] = GeocodingService.chave_endereco(
                        campos.get("logradouro"), campos.get("bairro"), campos.get("cep")
                    )
            alterou = True
        return alterou

    def _resetar_dependentes_servico(
        self,
        session: ChatSession,
        rascunho: list[Any],
        indice_demanda: int,
    ) -> None:
        if indice_demanda < 0 or indice_demanda >= len(rascunho):
            return
        item = rascunho[indice_demanda]
        if not isinstance(item, dict):
            return
        self._resetar_local_demanda_item(item)
        self._resetar_anexos_demanda_sessao(session, rascunho, indice_demanda)

    def revisar_etapa_copiloto(
        self,
        *,
        usuario,
        session_id: str,
        indice_demanda: int,
        etapa: str,
    ) -> dict[str, Any]:
        etapa_norm = (etapa or "").strip().lower()
        if etapa_norm not in self._ETAPAS_REVISAO_COPILOTO:
            raise ValueError("Etapa de revisão inválida.")

        session = self._obter_sessao(usuario, session_id)
        rascunho = list(session.demandas_rascunho or [])
        if indice_demanda < 0 or indice_demanda >= len(rascunho):
            raise ValueError("Índice de demanda inválido.")

        item = rascunho[indice_demanda]
        if not isinstance(item, dict):
            raise ValueError("Item de rascunho inválido.")
        if item.get("descartada"):
            raise ValueError("Não é possível revisar uma solicitação descartada.")
        if item.get("fora_competencia"):
            raise ValueError("Não é possível revisar solicitação fora da competência municipal.")

        num = indice_demanda + 1
        tinha_vinculo = self._vinculo_servico_snapshot(item) is not None

        titulo_curto = (item.get("titulo") or f"Solicitação {num}").strip()

        if etapa_norm == "pedido":
            item["_revisao_etapa"] = "pedido"
            item["_titulo_anterior_revisao"] = titulo_curto
            session.estado_atual = ChatSession.ESTADO_COLETA_DADOS
            msg = (
                f"Vamos revisar o pedido de «{titulo_curto}». "
                "Descreva na conversa o que deseja alterar. "
                "Se for outro tipo de serviço (ex.: limpeza em vez de poda), diga o novo pedido "
                "e escolha o serviço correto na carta."
            )
        elif etapa_norm == "servico":
            if tinha_vinculo:
                self._resetar_dependentes_servico(session, rascunho, indice_demanda)
            self._desconfirmar_servico_item(item)
            texto_sessao = self._texto_usuario_da_sessao(session)
            if not item.get("candidatos_sinapse"):
                item["candidatos_sinapse"] = self._buscar_candidatos_sinapse_item(
                    item, texto_sessao=texto_sessao
                )
            plano = self._planejar_passo_fluxo(session, rascunho)
            msg = (
                f"Vamos escolher outro serviço para «{titulo_curto}». "
                "Use o bloco da carta abaixo para selecionar a opção correta ou registrar tendência. "
                "O local e os anexos desta solicitação foram removidos e precisarão ser informados de novo."
                if tinha_vinculo
                else f"Escolha o serviço da carta para «{titulo_curto}» no bloco abaixo."
            )
            session.estado_atual = plano["estado_atual"]
        elif etapa_norm == "local":
            if not self._item_vinculo_catalogo_resolvido(item):
                raise ValueError("Confirme o serviço antes de revisar o local.")
            item.pop("endereco_informado_usuario", None)
            item.pop("endereco_opcional_dispensado", None)
            item.pop("local_confirmado_usuario", None)
            item["_revisao_etapa"] = "local"
            session.estado_atual = ChatSession.ESTADO_COLETA_ENDERECO
            local_atual = self._formatar_sufixo_local_demanda(item).strip()
            if local_atual:
                msg = (
                    f"O local atual de «{titulo_curto}»{local_atual}. "
                    "Informe na conversa o endereço correto (rua, bairro, CEP ou parque), "
                    "use o GPS ou digite «confirmar local» se o ponto no mapa estiver certo."
                )
            else:
                msg = (
                    f"Onde deve ser executado «{titulo_curto}»? "
                    "Informe na conversa o endereço, bairro, CEP ou use o botão de localização."
                )
        else:  # anexos
            if not self._item_vinculo_catalogo_resolvido(item):
                raise ValueError("Confirme o serviço antes de revisar os anexos.")
            item["_revisao_etapa"] = "anexos"
            session.estado_atual = ChatSession.ESTADO_VALIDACAO_FINAL
            msg = (
                f"Sobre os documentos de «{titulo_curto}»: envie novos arquivos no bloco abaixo, "
                "diga na conversa o que deseja remover ou use «confirmar documentos» / "
                "«continuar sem anexos» quando estiver satisfeito."
            )

        session.demandas_rascunho = rascunho
        session.save(update_fields=["demandas_rascunho", "estado_atual", "atualizado_em"])
        parsed: dict[str, Any] = {
            "resposta_agente": msg,
            "estado_atual": session.estado_atual,
            "demandas_extraidas": rascunho,
            "revisao_etapa": etapa_norm,
            "revisao_indice_demanda": indice_demanda,
        }
        if etapa_norm == "anexos":
            parsed["reabrir_anexos"] = True
        return self._montar_resposta_http(session, parsed, criadas=[])

    @staticmethod
    def _texto_indica_novo_assunto(item: dict[str, Any], texto: str) -> bool:
        antigo = f"{item.get('titulo') or ''} {item.get('descricao') or ''}".lower()
        novo = (texto or "").strip().lower()
        if not novo or len(novo) > 200:
            return False
        if novo in antigo or antigo in novo:
            return False
        tokens_ant = set(re.findall(r"\w{4,}", antigo))
        tokens_nov = set(re.findall(r"\w{4,}", novo))
        return not bool(tokens_ant & tokens_nov)

    def _tentar_processar_revisao_conversacional(
        self,
        session: ChatSession,
        texto_limpo: str,
    ) -> dict[str, Any] | None:
        texto = (texto_limpo or "").strip()
        if not texto:
            return None
        if _TEXTO_CONFIRMAR_LOCAL_RE.match(texto) or _TEXTO_CONFIRMAR_ANEXOS_RE.match(texto):
            return None
        if _TEXTO_CONTINUAR_SEM_ANEXOS_RE.match(texto) or _TEXTOS_PULAR_ENDERECO_RE.search(texto):
            return None
        rascunho = list(session.demandas_rascunho or [])
        indice = self._indice_demanda_em_revisao(rascunho, "pedido")
        if indice is None:
            return None
        item = rascunho[indice]
        if not isinstance(item, dict):
            return None
        return self._processar_revisao_pedido(session, rascunho, indice, item, texto)

    def _processar_revisao_pedido(
        self,
        session: ChatSession,
        rascunho: list[Any],
        indice: int,
        item: dict[str, Any],
        texto: str,
    ) -> dict[str, Any]:
        texto_limpo = (texto or "").strip()
        item_antigo = {
            "titulo": item.get("_titulo_anterior_revisao") or item.get("titulo"),
            "descricao": item.get("descricao"),
        }
        titulo_linha = texto_limpo.split("\n", 1)[0].strip()
        titulo = (titulo_linha[:200] if titulo_linha else f"Solicitação {indice + 1}").strip()
        item["pedido_integral"] = texto_limpo
        item["descricao"] = texto_limpo
        item["titulo"] = titulo
        item["texto_para_embedding"] = texto_limpo[:500]
        item.pop("_eixo_pedido", None)
        novo_eixo = ChatbotService._inferir_eixo_do_texto_usuario(item)
        if novo_eixo:
            item["_eixo_pedido"] = novo_eixo
        item.pop("_revisao_etapa", None)
        item.pop("_titulo_anterior_revisao", None)

        mudou_assunto = self._texto_indica_novo_assunto(item_antigo, texto_limpo)
        tinha_vinculo = self._vinculo_servico_snapshot(item) is not None
        if mudou_assunto and tinha_vinculo:
            self._resetar_dependentes_servico(session, rascunho, indice)
            self._desconfirmar_servico_item(item)
            texto_sessao = self._texto_usuario_da_sessao(session)
            item["candidatos_sinapse"] = self._buscar_candidatos_sinapse_item(
                item, texto_sessao=texto_sessao
            )
            plano = self._planejar_passo_fluxo(session, rascunho)
            session.estado_atual = plano["estado_atual"]
            session.demandas_rascunho = rascunho
            session.save(update_fields=["estado_atual", "demandas_rascunho", "atualizado_em"])
            parsed = dict(plano)
            parsed["resposta_agente"] = (
                f"Atualizei o pedido para «{titulo}». Como o assunto mudou, "
                "escolha o serviço correto na carta abaixo."
            )
            parsed["revisao_encerrada"] = True
            parsed["demandas_extraidas"] = rascunho
            return parsed

        plano = self._planejar_passo_fluxo(session, rascunho)
        session.estado_atual = plano["estado_atual"]
        session.demandas_rascunho = rascunho
        session.save(update_fields=["estado_atual", "demandas_rascunho", "atualizado_em"])
        parsed = dict(plano)
        parsed["resposta_agente"] = (
            f"Pedido da solicitação {indice + 1} atualizado: «{titulo}». "
            "O serviço confirmado permanece; use «Revisar» em Serviço se precisar trocar."
        )
        parsed["revisao_encerrada"] = True
        parsed["demandas_extraidas"] = rascunho
        return parsed

    def editar_pedido_demanda(
        self,
        *,
        usuario,
        session_id: str,
        indice_demanda: int,
        titulo: str | None = None,
        descricao: str | None = None,
        pedido_integral: str | None = None,
    ) -> dict[str, Any]:
        session = self._obter_sessao(usuario, session_id)
        rascunho = list(session.demandas_rascunho or [])
        if indice_demanda < 0 or indice_demanda >= len(rascunho):
            raise ValueError("Índice de demanda inválido.")
        item = rascunho[indice_demanda]
        if not isinstance(item, dict):
            raise ValueError("Item de rascunho inválido.")

        alterou = False
        if titulo is not None:
            t = str(titulo).strip()
            if t:
                item["titulo"] = t[:200]
                alterou = True
        if descricao is not None:
            d = str(descricao).strip()
            if d:
                item["descricao"] = d
                alterou = True
        if pedido_integral is not None:
            p = str(pedido_integral).strip()
            if p:
                item["pedido_integral"] = p
                item["descricao"] = p
                alterou = True
        if not alterou:
            raise ValueError("Informe título, descrição ou pedido integral.")

        texto_emb = (item.get("pedido_integral") or item.get("descricao") or "").strip()
        if texto_emb:
            item["texto_para_embedding"] = texto_emb[:500]

        session.demandas_rascunho = rascunho
        session.save(update_fields=["demandas_rascunho", "atualizado_em"])
        parsed = {
            "resposta_agente": "Pedido atualizado para esta solicitação.",
            "estado_atual": session.estado_atual,
            "demandas_extraidas": rascunho,
        }
        return self._montar_resposta_http(session, parsed, criadas=[])

    def editar_local_demanda(
        self,
        *,
        usuario,
        session_id: str,
        indice_demanda: int,
        endereco: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        session = self._obter_sessao(usuario, session_id)
        rascunho = list(session.demandas_rascunho or [])
        if indice_demanda < 0 or indice_demanda >= len(rascunho):
            raise ValueError("Índice de demanda inválido.")
        item = rascunho[indice_demanda]
        if not isinstance(item, dict):
            raise ValueError("Item de rascunho inválido.")
        if not self._item_vinculo_catalogo_resolvido(item):
            raise ValueError("Confirme o serviço antes de editar o local.")

        end_in = endereco if isinstance(endereco, dict) else {}
        end_atual = (
            item.get("endereco") if isinstance(item.get("endereco"), dict) else dict(_ENDERECO_VAZIO)
        )
        merged = dict(end_atual)
        for k in ("cep", "logradouro", "numero", "bairro", "complemento"):
            if k in end_in and end_in[k] not in (None, ""):
                merged[k] = end_in[k]
        item["endereco"] = merged
        item.pop("endereco_opcional_dispensado", None)
        item.pop("local_confirmado_usuario", None)
        item.pop("endereco_informado_usuario", None)

        texto_sessao = self._texto_usuario_da_sessao(session)
        texto_item = self._texto_contexto_demanda(item, texto_sessao)
        self._aplicar_endereco_canonico(item, texto_item)

        logradouro = self._limpar_logradouro(
            (merged.get("logradouro") or "").strip() or None,
            texto_contexto=texto_item,
        )
        bairro = ChatbotService._limpar_bairro(
            (merged.get("bairro") or "").strip() or None,
            texto_contexto=texto_item,
        )
        cep = (merged.get("cep") or "").strip() or None
        geocoder = GeocodingService()
        lat, lng, fonte = self._resolver_coordenadas_item(
            item,
            geocoder,
            logradouro=logradouro,
            bairro=bairro,
            cep=cep,
        )
        if lat is not None and lng is not None:
            item["latitude"] = round(lat, 6)
            item["longitude"] = round(lng, 6)
            item["coordenadas_fonte"] = fonte
            if fonte == "gps_dispositivo":
                item["_geo_chave"] = f"gps:{item['latitude']},{item['longitude']}"
            else:
                item["_geo_chave"] = GeocodingService.chave_endereco(logradouro, bairro, cep)

        session.demandas_rascunho = rascunho
        session.save(update_fields=["demandas_rascunho", "atualizado_em"])
        parsed = {
            "resposta_agente": (
                "Endereço aplicado. Confira logradouro, bairro e mapa; "
                "clique em «Confirmar local» para seguir."
            ),
            "estado_atual": session.estado_atual,
            "demandas_extraidas": rascunho,
        }
        self._sincronizar_estado_pos_vinculo_catalogo(session, parsed)
        return self._montar_resposta_http(session, parsed, criadas=[])

    def remover_anexo_sessao_copiloto(
        self,
        *,
        usuario,
        session_id: str,
        indice_sessao: int,
    ) -> dict[str, Any]:
        session = self._obter_sessao(usuario, session_id)
        anexos = list(session.anexos_sessao.order_by("criado_em"))
        if indice_sessao < 0 or indice_sessao >= len(anexos):
            raise ValueError("Índice de anexo inválido.")
        anexos[indice_sessao].delete()
        self._propagar_anexos_indices_rascunho(session)
        rascunho = list(session.demandas_rascunho or [])
        parsed = {
            "resposta_agente": "Anexo removido da sessão.",
            "estado_atual": session.estado_atual,
            "demandas_extraidas": rascunho,
        }
        return self._montar_resposta_http(session, parsed, criadas=[])

    def retriagem_carta_demanda(
        self,
        *,
        usuario,
        session_id: str,
        indice_demanda: int,
    ) -> dict[str, Any]:
        session = self._obter_sessao(usuario, session_id)
        rascunho = list(session.demandas_rascunho or [])
        if indice_demanda < 0 or indice_demanda >= len(rascunho):
            raise ValueError("Índice de demanda inválido.")
        item = rascunho[indice_demanda]
        if not isinstance(item, dict):
            item = {}
            rascunho[indice_demanda] = item
        item.pop("sinapse_servico_id_sugerido", None)
        item.pop("servico_local_id", None)
        item.pop("vinculo_servico_ignorado", None)
        texto_sessao = self._texto_usuario_da_sessao(session)
        cands = self._buscar_candidatos_sinapse_item(item, texto_sessao=texto_sessao)
        item["candidatos_sinapse"] = cands
        session.demandas_rascunho = rascunho
        session.save(update_fields=["demandas_rascunho", "atualizado_em"])
        parsed = {
            "resposta_agente": "Nova busca na carta concluída. Escolha uma opção no painel ou registre como tendência.",
            "estado_atual": session.estado_atual,
            "demandas_extraidas": rascunho,
        }
        self._sincronizar_estado_pos_vinculo_catalogo(session, parsed)
        return self._montar_resposta_http(session, parsed, criadas=[])

    def ignorar_servico_sugerido_demanda(
        self,
        *,
        usuario,
        session_id: str,
        indice_demanda: int,
    ) -> dict[str, Any]:
        session = self._obter_sessao(usuario, session_id)
        rascunho = list(session.demandas_rascunho or [])
        if indice_demanda < 0 or indice_demanda >= len(rascunho):
            raise ValueError("Índice de demanda inválido.")
        item = rascunho[indice_demanda]
        if not isinstance(item, dict):
            item = {}
            rascunho[indice_demanda] = item
        item["vinculo_servico_ignorado"] = True
        item.pop("sinapse_servico_id_sugerido", None)
        item.pop("servico_local_id", None)
        session.demandas_rascunho = rascunho
        session.save(update_fields=["demandas_rascunho", "atualizado_em"])
        parsed = {
            "resposta_agente": (
                "Sugestões da carta ignoradas para esta solicitação. "
                "Use «Nova busca» ou registre como tendência, se aplicável."
            ),
            "estado_atual": session.estado_atual,
            "demandas_extraidas": rascunho,
        }
        return self._montar_resposta_http(session, parsed, criadas=[])

    def atualizar_localizacao_demanda(
        self,
        *,
        usuario,
        session_id: str,
        indice_demanda: int,
        latitude: float,
        longitude: float,
        fonte: str = "gps_dispositivo",
        confirmar_local: bool | None = None,
    ) -> dict[str, Any]:
        session = self._obter_sessao(usuario, session_id)
        rascunho = list(session.demandas_rascunho or [])
        if indice_demanda < 0 or indice_demanda >= len(rascunho):
            raise ValueError("Índice de demanda inválido.")
        item = rascunho[indice_demanda]
        if not isinstance(item, dict):
            item = {}
            rascunho[indice_demanda] = item
        lat = round(float(latitude), 6)
        lng = round(float(longitude), 6)
        fonte_norm = (fonte or "gps_dispositivo").strip().lower()
        if confirmar_local is None:
            confirmar_local = fonte_norm == "gps_dispositivo"
        item["latitude"] = lat
        item["longitude"] = lng
        item["coordenadas_fonte"] = fonte_norm
        item["_geo_chave"] = f"gps:{lat},{lng}"
        if confirmar_local:
            item["endereco_informado_usuario"] = True
            item["local_confirmado_usuario"] = True
        else:
            item.pop("local_confirmado_usuario", None)
        if fonte_norm == "gps_dispositivo":
            msg_resposta = self._preencher_endereco_reverso_gps(item, GeocodingService())
        elif fonte_norm == "ajuste_mapa":
            geocoder = GeocodingService()
            rev = geocoder.buscar_endereco_por_coordenadas(lat, lng)
            if rev:
                end = item.get("endereco") if isinstance(item.get("endereco"), dict) else {}
                for chave in ("logradouro", "bairro", "cep"):
                    val = rev.get(chave)
                    if val:
                        end[chave] = val
                item["endereco"] = end
            msg_resposta = (
                "Ponto ajustado no mapa. Confirme o local quando estiver no lugar correto."
            )
        else:
            msg_resposta = "Localização atualizada."
        session.demandas_rascunho = rascunho
        session.save(update_fields=["demandas_rascunho", "atualizado_em"])
        parsed = {
            "resposta_agente": msg_resposta,
            "estado_atual": session.estado_atual,
            "demandas_extraidas": rascunho,
        }
        return self._montar_resposta_http(session, parsed, criadas=[])

    def marcar_demanda_rascunho(
        self,
        *,
        usuario,
        session_id: str,
        indice_demanda: int,
        aprovado_final: bool | None = None,
        descartada: bool | None = None,
    ) -> dict[str, Any]:
        session = self._obter_sessao(usuario, session_id)
        rascunho = list(session.demandas_rascunho or [])
        if indice_demanda < 0 or indice_demanda >= len(rascunho):
            raise ValueError("Índice de demanda inválido.")
        item = rascunho[indice_demanda]
        if not isinstance(item, dict):
            raise ValueError("Item de rascunho inválido.")
        if aprovado_final is not None:
            item["aprovado_final"] = bool(aprovado_final)
        if descartada is not None:
            item["descartada"] = bool(descartada)
            if descartada:
                item["aprovado_final"] = False
                item.pop("sinapse_servico_id_sugerido", None)
                item.pop("servico_local_id", None)
                item.pop("tendencia_id", None)
                item.pop("tendencia", None)
                item["vinculo_servico_ignorado"] = True
            else:
                item.pop("vinculo_servico_ignorado", None)
        session.demandas_rascunho = rascunho
        session.save(update_fields=["demandas_rascunho", "atualizado_em"])
        parsed = {
            "resposta_agente": "",
            "estado_atual": session.estado_atual,
            "demandas_extraidas": rascunho,
        }
        self._sincronizar_estado_pos_vinculo_catalogo(session, parsed)
        return self._montar_resposta_http(session, parsed, criadas=[])

    def atualizar_metadados_indicacao_copiloto(
        self,
        *,
        usuario,
        session_id: str,
        indice_demanda: int,
        vereadores_vinculados_ids: list[int] | None = None,
        autor_vereador_id: int | None = None,
        numero_indicacao: int | None = None,
    ) -> dict[str, Any]:
        if not self._usuario_modo_indicacao(usuario):
            raise ValueError("Metadados de indicação disponíveis apenas para perfil CAMARA.")
        session = self._obter_sessao(usuario, session_id)
        rascunho = list(session.demandas_rascunho or [])
        if indice_demanda < 0 or indice_demanda >= len(rascunho):
            raise ValueError("Índice de demanda inválido.")
        item = rascunho[indice_demanda]
        if not isinstance(item, dict):
            item = {}
            rascunho[indice_demanda] = item
        item["modo_indicacao"] = True
        if vereadores_vinculados_ids is not None:
            ids: list[int] = []
            for raw in vereadores_vinculados_ids:
                try:
                    ids.append(int(raw))
                except (TypeError, ValueError):
                    continue
            item["vereadores_vinculados_ids"] = list(dict.fromkeys(ids))
        if autor_vereador_id is not None:
            try:
                item["autor_vereador_id"] = int(autor_vereador_id)
            except (TypeError, ValueError):
                item.pop("autor_vereador_id", None)
        if numero_indicacao is not None:
            try:
                item["numero_indicacao"] = int(numero_indicacao)
            except (TypeError, ValueError):
                raise ValueError("Número da indicação inválido.")
        session.demandas_rascunho = rascunho
        session.save(update_fields=["demandas_rascunho", "atualizado_em"])
        parsed = {
            "resposta_agente": "",
            "estado_atual": session.estado_atual,
            "demandas_extraidas": rascunho,
        }
        return self._montar_resposta_http(session, parsed, criadas=[])

    def confirmar_servico_demanda(
        self,
        *,
        usuario,
        session_id: str,
        indice_demanda: int,
        sinapse_servico_id: int,
    ) -> dict[str, Any]:
        session = self._obter_sessao(usuario, session_id)
        rascunho = list(session.demandas_rascunho or [])
        if indice_demanda < 0 or indice_demanda >= len(rascunho):
            raise ValueError("Índice de demanda inválido.")
        if not sinapse_catalog.servico_existe(sinapse_servico_id):
            raise ValueError("Serviço não encontrado na carta Sinapse.")
        from core.services.carta_utilizacao_service import CartaUtilizacaoService

        CartaUtilizacaoService().validar_protocolo(
            int(sinapse_servico_id),
            contexto="confirmar_servico_copiloto",
        )
        item = rascunho[indice_demanda]
        if not isinstance(item, dict):
            item = {}
            rascunho[indice_demanda] = item
        vinculo_anterior = self._vinculo_servico_snapshot(item)
        item["sinapse_servico_id_sugerido"] = int(sinapse_servico_id)
        item["servico_local_id"] = int(sinapse_servico_id)
        item["servico_confirmado_usuario"] = True
        item["origem_vinculo"] = Demanda.ORIGEM_VINCULO_CARTA
        item.pop("vinculo_servico_ignorado", None)
        item.pop("tendencia_id", None)
        item.pop("tendencia", None)
        vinculo_novo = ("carta", int(sinapse_servico_id))
        if vinculo_anterior and vinculo_anterior != vinculo_novo:
            self._resetar_dependentes_servico(session, rascunho, indice_demanda)
        session.demandas_rascunho = rascunho
        session.save(update_fields=["demandas_rascunho", "atualizado_em"])
        parsed: dict[str, Any] = {
            "resposta_agente": "Serviço da carta registrado para esta solicitação.",
            "estado_atual": session.estado_atual,
            "demandas_extraidas": rascunho,
        }
        self._sincronizar_estado_pos_vinculo_catalogo(session, parsed)
        return self._montar_resposta_http(session, parsed, criadas=[])

    def confirmar_tendencia_demanda(
        self,
        *,
        usuario,
        session_id: str,
        indice_demanda: int,
        titulo: str = "",
        descricao_resumo: str = "",
        sinapse_orgao_id: int | None = None,
        tendencia_id: int | None = None,
    ) -> dict[str, Any]:
        """Vincula item do rascunho à trilha tendência (fora da carta Sinapse)."""
        session = self._obter_sessao(usuario, session_id)
        rascunho = list(session.demandas_rascunho or [])
        if indice_demanda < 0 or indice_demanda >= len(rascunho):
            raise ValueError("Índice de demanda inválido.")
        item = rascunho[indice_demanda]
        if not isinstance(item, dict):
            item = {}
            rascunho[indice_demanda] = item

        vinculo_anterior = self._vinculo_servico_snapshot(item)

        svc = TendenciaService()
        if tendencia_id is not None:
            tendencia = Tendencia.objects.filter(pk=int(tendencia_id)).first()
            if not tendencia:
                raise ValueError("Tendência não encontrada.")
        else:
            titulo_limpo = (titulo or item.get("titulo") or "Solicitação fora da carta").strip()
            texto_emb = (item.get("texto_para_embedding") or titulo_limpo).strip()
            desc = (descricao_resumo or item.get("descricao") or "").strip()
            orgao = sinapse_orgao_id
            if orgao is None and item.get("sinapse_orgao_id_sugerido"):
                try:
                    orgao = int(item["sinapse_orgao_id_sugerido"])
                except (TypeError, ValueError):
                    orgao = None
            tendencia = svc.buscar_ou_criar(
                titulo=titulo_limpo,
                texto_embedding=texto_emb,
                descricao_resumo=desc,
                sinapse_orgao_id=orgao,
                criado_por=usuario,
                score_triagem_max=self._score_max_candidatos(item),
            )

        item["tendencia_id"] = tendencia.id
        item["origem_vinculo"] = Demanda.ORIGEM_VINCULO_TENDENCIA
        item["sinapse_servico_id_sugerido"] = None
        item.pop("servico_local_id", None)
        item["candidatos_sinapse"] = []
        item["tendencia"] = {
            "id": tendencia.id,
            "titulo": tendencia.titulo,
            "volume_total": tendencia.volume_total,
            "sinapse_orgao_id": tendencia.sinapse_orgao_id,
        }
        vinculo_novo = ("tendencia", int(tendencia.id))
        if vinculo_anterior and vinculo_anterior != vinculo_novo:
            self._resetar_dependentes_servico(session, rascunho, indice_demanda)
        session.demandas_rascunho = rascunho
        session.save(update_fields=["demandas_rascunho", "atualizado_em"])

        parsed = {
            "resposta_agente": (
                f"Registrei como tendência «{tendencia.titulo}» (volume {tendencia.volume_total})."
            ),
            "estado_atual": session.estado_atual,
            "demandas_extraidas": rascunho,
        }
        self._sincronizar_estado_pos_vinculo_catalogo(session, parsed)
        return self._montar_resposta_http(session, parsed, criadas=[])

    @staticmethod
    def _score_max_candidatos(item: dict[str, Any]) -> float | None:
        cands = item.get("candidatos_sinapse")
        if not isinstance(cands, list) or not cands:
            return None
        scores = [
            float(c.get("score"))
            for c in cands
            if isinstance(c, dict) and c.get("score") is not None
        ]
        return max(scores) if scores else None

    @staticmethod
    def _texto_coerencia_demanda(item: dict[str, Any], texto_sessao: str = "") -> str:
        partes = [
            (item.get("titulo") or "").strip(),
            (item.get("descricao") or "").strip(),
            (item.get("texto_para_embedding") or "").strip(),
        ]
        if texto_sessao:
            partes.append(texto_sessao.strip()[:400])
        return "\n".join(p for p in partes if p)

    def _item_sugere_trilha_tendencia(
        self, item: dict[str, Any], *, texto_sessao: str = ""
    ) -> bool:
        modo, dominio = self._classificar_modo_vinculo_servico(item, texto_sessao=texto_sessao)
        item["modo_vinculo_servico"] = modo
        if dominio:
            item["dominio_operacional"] = dominio
        if modo in ("carta_forte", "carta_dominio"):
            return False
        if not copiloto_tendencias_habilitadas():
            return False
        return True

    @staticmethod
    def _variantes_consulta_triagem_sinapse(
        item: dict[str, Any], *, texto_sessao: str = ""
    ) -> list[str]:
        """Monta consultas complementares (tema + local) para a triagem vetorial."""
        titulo = (item.get("titulo") or "").strip()
        desc = (item.get("descricao") or "").strip()
        te = (item.get("texto_para_embedding") or "").strip()
        eixo = ChatbotService._meta_eixo_pedido(item.get("_eixo_pedido"))
        if eixo and eixo.get("texto_embedding"):
            te = str(eixo["texto_embedding"])
        end = item.get("endereco") if isinstance(item.get("endereco"), dict) else {}
        loc = " ".join(
            x
            for x in (
                (end.get("logradouro") or "").strip(),
                (end.get("bairro") or "").strip(),
                (end.get("cep") or "").strip(),
            )
            if x
        )
        corpus = " ".join(
            p for p in (titulo, desc, te, loc, (texto_sessao or "")[:500]) if p
        )
        variantes: list[str] = []

        def add(texto: str) -> None:
            limpo = " ".join((texto or "").split())[:500]
            if len(limpo) >= 8 and limpo not in variantes:
                variantes.append(limpo)

        add(f"{titulo} {desc}".strip())
        if te:
            add(te)
        if loc:
            add(f"{titulo} {loc}".strip())
            add(f"reserva de espaço {loc}")

        corpus_low = corpus.lower()
        m_parque = re.search(r"parque\s+([\wáàâãéêíóôõúç\-]+)", corpus_low)
        if m_parque:
            nome_parque = f"parque {m_parque.group(1).strip()}"
            for stop in ("ação", "acao", "social", "para", "realização", "realizacao"):
                nome_parque = re.sub(rf"\s+{stop}.*$", "", nome_parque).strip()
            if len(nome_parque) >= 10:
                add(f"reserva de espaço {nome_parque}")
                add(f"reserva de espaços e eventos {nome_parque}")
        if "centen" in corpus_low:
            add("reserva de espaços e eventos parque centenário")
            add("reserva espaço parque centenário")
        for variante_dom in variantes_triagem_por_dominio(corpus):
            add(variante_dom)
        if "reserva" in corpus_low and any(
            x in corpus_low for x in ("ação social", "acao social", "evento", "eventos")
        ):
            sufixo = m_parque.group(0).strip() if m_parque else loc
            if sufixo:
                add(f"reserva de espaço para ação social {sufixo}")
            else:
                add("reserva de espaço para ação social")

        return variantes[:6]

    def _triagem_sinapse_consolidada(
        self, item: dict[str, Any], *, texto_sessao: str = ""
    ) -> list[dict[str, Any]]:
        """Executa triagem para cada variante e mantém o melhor score por servico_id."""
        variantes = self._variantes_consulta_triagem_sinapse(item, texto_sessao=texto_sessao)
        if not variantes:
            return []

        # Usar triagem otimizada se configurado
        from django.conf import settings
        usar_base_otimizada = getattr(settings, 'USAR_BASE_SERVICOS_OTIMIZADA', True)
        triagem = AdapterTriagemOtimizada(usar_base_otimizada=usar_base_otimizada)
        vector_svc = VectorService()
        por_id: dict[int, dict[str, Any]] = {}

        for texto_emb in variantes:
            try:
                vetor = vector_svc.generate_embedding(texto_emb)
            except Exception:
                logger.warning(
                    "Copiloto triagem: falha ao gerar embedding para variante=%s",
                    texto_emb[:80],
                    exc_info=True,
                )
                continue
            if not vetor or len(vetor) != 1024:
                logger.warning(
                    "Copiloto triagem: embedding vazio para variante=%s", texto_emb[:80]
                )
                continue
            for c in triagem.buscar_servico_sinapse(
                vetor, top_k=8, texto_consulta=texto_emb
            ):
                if not isinstance(c, dict) or c.get("servico_id") is None:
                    continue
                sid = int(c["servico_id"])
                score = float(c.get("score") or 0.0)
                atual = por_id.get(sid)
                if atual is None or score > float(atual.get("score") or 0.0):
                    por_id[sid] = {
                        "servico_id": sid,
                        "titulo": (c.get("titulo") or "").strip(),
                        "orgao": c.get("orgao"),
                        "score": c.get("score"),
                    }

        return sorted(
            por_id.values(),
            key=lambda x: float(x.get("score") or 0.0),
            reverse=True,
        )

    @staticmethod
    def _limiar_carta_dominio() -> float:
        return float(getattr(settings, "COPILOTO_CARTA_SCORE_DOMINIO", 0.40))

    @classmethod
    def _filtrar_candidatos_para_ui(
        cls,
        candidatos: list[dict[str, Any]],
        *,
        modo: str = "carta_forte",
        texto_coerencia: str = "",
    ) -> list[dict[str, Any]]:
        """Filtra candidatos para o select do copiloto conforme o modo de vínculo."""
        if not candidatos:
            return []
        item_ctx: dict[str, Any] = {}
        if texto_coerencia.strip():
            item_ctx = {
                "titulo": texto_coerencia.strip().split("\n", 1)[0],
                "descricao": texto_coerencia,
                "texto_para_embedding": texto_coerencia,
            }

        def _pts(c: dict[str, Any]) -> float:
            if item_ctx:
                return cls._pontuacao_candidato_ajustada(c, item_ctx)
            return float(c.get("score") or 0.0)

        if modo == "carta_dominio":
            limiar = cls._limiar_carta_dominio()
            max_n = 8
        else:
            limiar = cls._limiar_carta_copiloto()
            max_n = 5
        ordenados = sorted(candidatos, key=_pts, reverse=True)
        if item_ctx:
            acima = [c for c in ordenados if _pts(c) >= limiar]
        else:
            acima = [c for c in ordenados if float(c.get("score") or 0.0) >= limiar]
        if texto_coerencia.strip() and acima:
            coerentes = [
                c
                for c in acima
                if cls._coerencia_texto_servico(texto_coerencia, (c.get("titulo") or ""))
            ]
            if coerentes:
                coerentes.sort(key=_pts, reverse=True)
                return cls._enriquecer_candidatos_utilizacao(coerentes[:max_n])
        return cls._enriquecer_candidatos_utilizacao(acima[:max_n])

    @staticmethod
    def _enriquecer_candidatos_utilizacao(candidatos: list[dict[str, Any]]) -> list[dict[str, Any]]:
        from core.services.carta_utilizacao_service import CartaUtilizacaoService

        svc = CartaUtilizacaoService()
        return [svc.enriquecer_candidato(c) for c in candidatos]

    def _classificar_modo_vinculo_servico(
        self, item: dict[str, Any], *, texto_sessao: str = ""
    ) -> tuple[str, dict[str, Any] | None]:
        """
        carta_forte: match ≥ 66,66% coerente.
        carta_dominio: eixo operacional reconhecido (ex.: mobilidade) — listar carta OU tendência.
        tendencia: sem candidatos úteis na carta.
        """
        texto = self._texto_coerencia_demanda(item, texto_sessao)
        dominio = detectar_dominio_operacional(texto)
        raw = item.get("candidatos_sinapse")
        consolidado = raw if isinstance(raw, list) else []

        limiar_forte = self._limiar_carta_copiloto()
        melhor_coerente = self._melhor_candidato_coerente(
            consolidado, item, texto_sessao=texto_sessao
        )
        if melhor_coerente and float(melhor_coerente.get("score") or 0.0) >= limiar_forte:
            return "carta_forte", dominio

        melhor = self._melhor_candidato_dict(item)
        best = self._score_max_candidatos(item) or 0.0
        if melhor and best >= limiar_forte:
            if self._coerencia_texto_servico(texto, (melhor.get("titulo") or "")):
                return "carta_forte", dominio

        if dominio and consolidado:
            relev = candidatos_relevantes_dominio(
                consolidado,
                dominio,
                score_minimo=self._limiar_carta_dominio(),
            )
            if relev:
                return "carta_dominio", dominio

        return "tendencia", dominio

    def _buscar_candidatos_sinapse_item(
        self, item: dict[str, Any], *, texto_sessao: str = ""
    ) -> list[dict[str, Any]]:
        """Busca vetorial na carta (variantes + domínio); retorna lista consolidada sem filtrar score."""
        return self._triagem_sinapse_consolidada(item, texto_sessao=texto_sessao)[:10]

    def _popular_candidatos_sinapse_rascunho(
        self, session: ChatSession, items: list[Any]
    ) -> bool:
        """Garante candidatos da carta no rascunho (ex.: após confirmar tendência sem triagem prévia)."""
        if not items:
            return False
        texto_sessao = self._texto_usuario_da_sessao(session)
        alterou = False
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("fora_competencia"):
                continue
            if (
                self._item_vinculo_catalogo_resolvido(item)
                or item.get("servico_confirmado_usuario")
                or item.get("corpus_preselecao_servico_id")
            ):
                continue
            cands = self._buscar_candidatos_sinapse_item(item, texto_sessao=texto_sessao)
            if cands:
                item["candidatos_sinapse"] = cands
                alterou = True
        if alterou:
            session.demandas_rascunho = items
            session.save(update_fields=["demandas_rascunho", "atualizado_em"])
        return alterou

    def _enriquecer_demandas_para_ui(
        self,
        session: ChatSession,
        items: list[Any],
    ) -> list[dict[str, Any]]:
        """Acrescenta serviço (carta), coordenadas e anexos vinculados para o painel do copiloto."""
        if not isinstance(items, list):
            return []

        texto_sessao = self._texto_usuario_da_sessao(session)
        anexos_sessao = list(session.anexos_sessao.order_by("criado_em"))
        geocoder = GeocodingService()
        mapa_anexos = self._mapa_anexos_por_demanda(
            anexos_sessao, items, [None] * len(items)
        )

        geo_persistido_no_rascunho = False
        resultado: list[dict[str, Any]] = []
        self._aplicar_classificacao_competencia_rascunho(items, texto_sessao=texto_sessao)
        ChatbotService._normalizar_lista_demandas_compostas(items)

        for dem_idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue

            self._normalizar_sinapse_id_rascunho(item)
            self._normalizar_item_pedido_composto(item)
            row: dict[str, Any] = dict(item)
            row["fora_competencia"] = bool(item.get("fora_competencia"))
            row["motivo_recusa"] = item.get("motivo_recusa")
            row["competencia_municipal"] = item.get("competencia_municipal")
            row["categoria_orientacao"] = item.get("categoria_orientacao")
            row["faq_orientacao"] = item.get("faq_orientacao")
            end_raw = item.get("endereco") if isinstance(item.get("endereco"), dict) else {}
            row["endereco"] = dict(end_raw)

            sid = self._resolver_sinapse_id(item)
            catalog = sinapse_catalog.get_servico(sid) if sid else None
            servico_nome = (catalog.titulo if catalog else "") or ""
            if sid and catalog and self._servico_confirmado_pelo_usuario(item):
                orgao_id = sinapse_catalog.get_orgao_id_for_servico(sid)
                gestao = gestao_operacional_para_copiloto(sid)
                row["servico"] = {
                    "sinapse_servico_id": sid,
                    "nome": servico_nome,
                    "orgao": sinapse_catalog.get_orgao_nome(orgao_id) or None,
                    "confirmado": True,
                    "gestao_operacional": gestao,
                }
                if self._escolha_carta_explicita_usuario(item):
                    row["servico_alerta"] = False
                else:
                    row["servico_alerta"] = not self._coerencia_texto_servico(
                        self._texto_coerencia_demanda(item, texto_sessao), servico_nome
                    )
            else:
                row["servico"] = None
                row["servico_alerta"] = False

            if row["fora_competencia"]:
                row["candidatos_sinapse"] = []
                row["servico"] = None
                row["servico_alerta"] = False
                row["requer_escolha_servico"] = False
                row["fora_carta"] = False
                row["origem_vinculo"] = None
                row["tendencia"] = None
            else:
                modo, dominio_ui = self._classificar_modo_vinculo_servico(
                    item, texto_sessao=texto_sessao
                )
                item["modo_vinculo_servico"] = modo
                if dominio_ui:
                    item["dominio_operacional"] = dominio_ui
                raw_cands = item.get("candidatos_sinapse")
                texto_coh = self._texto_coerencia_demanda(item, texto_sessao)
                if isinstance(raw_cands, list):
                    normalizados = [
                        {
                            "servico_id": c.get("servico_id"),
                            "titulo": (c.get("titulo") or "").strip(),
                            "orgao": c.get("orgao"),
                            "score": c.get("score"),
                        }
                        for c in raw_cands
                        if isinstance(c, dict) and c.get("servico_id") is not None
                    ]
                    if modo == "carta_dominio" and dominio_ui:
                        pool = candidatos_relevantes_dominio(
                            normalizados,
                            dominio_ui,
                            score_minimo=self._limiar_carta_dominio(),
                        )
                        row["candidatos_sinapse"] = self._filtrar_candidatos_para_ui(
                            pool or normalizados,
                            modo="carta_dominio",
                            texto_coerencia=texto_coh,
                        )
                    else:
                        row["candidatos_sinapse"] = self._filtrar_candidatos_para_ui(
                            normalizados,
                            modo=modo,
                            texto_coerencia=texto_coh,
                        )
                else:
                    row["candidatos_sinapse"] = []
                row["modo_vinculo_servico"] = modo
                row["dominio_operacional"] = dominio_ui
                melhor_cand = self._melhor_candidato_coerente(
                    raw_cands if isinstance(raw_cands, list) else [],
                    item,
                    texto_sessao=texto_sessao,
                ) if not sid else None
                if melhor_cand and not sid:
                    row["servico_alerta"] = False
                elif not sid:
                    melhor_raw = self._melhor_candidato_dict(item)
                    if melhor_raw:
                        row["servico_alerta"] = not self._coerencia_texto_servico(
                            texto_coh, (melhor_raw.get("titulo") or "")
                        )
                row["requer_escolha_servico"] = sid is None and (
                    len(row["candidatos_sinapse"]) > 0 or modo == "carta_dominio"
                )
                row["candidatos_revisao"] = int(item.get("candidatos_revisao") or 0)
                sugerido_ui = (
                    melhor_cand
                    or (self._melhor_candidato_dict(item) if not sid else None)
                )
                if sugerido_ui and not sid:
                    row["servico_sugerido_ui_id"] = sugerido_ui.get("servico_id")
                else:
                    row["servico_sugerido_ui_id"] = None
                trilha_ouv = item.get("trilha_ouvidoria")
                if isinstance(trilha_ouv, dict):
                    row["trilha_ouvidoria"] = trilha_ouv
                    row["teor_ouvidoria"] = True
                    row["subtipo_ouvidoria"] = trilha_ouv.get("subtipo")
                    if sid:
                        row["requer_escolha_servico"] = False
                row["fora_carta"] = self._item_sugere_trilha_tendencia(
                    item, texto_sessao=texto_sessao
                )
            if not row["fora_competencia"]:
                if sid is not None:
                    row["origem_vinculo"] = Demanda.ORIGEM_VINCULO_CARTA
                elif not row["fora_carta"]:
                    row["origem_vinculo"] = Demanda.ORIGEM_VINCULO_CARTA
                elif item.get("tendencia_id") or item.get("origem_vinculo") == Demanda.ORIGEM_VINCULO_TENDENCIA:
                    row["origem_vinculo"] = Demanda.ORIGEM_VINCULO_TENDENCIA
                else:
                    row["origem_vinculo"] = item.get("origem_vinculo") or Demanda.ORIGEM_VINCULO_CARTA
            tid = item.get("tendencia_id")
            if tid and not row["fora_competencia"]:
                tendencia = Tendencia.objects.filter(pk=int(tid)).first()
                if tendencia:
                    row["tendencia"] = {
                        "id": tendencia.id,
                        "titulo": tendencia.titulo,
                        "volume_total": tendencia.volume_total,
                        "status": tendencia.status,
                        "sinapse_orgao_id": tendencia.sinapse_orgao_id,
                        "sinapse_orgao_nome": (
                            sinapse_catalog.get_orgao_nome(tendencia.sinapse_orgao_id)
                            if tendencia.sinapse_orgao_id
                            else None
                        ),
                    }
                else:
                    row["tendencia"] = {"id": tid}
            else:
                row["tendencia"] = None

            item_geo = dict(item)
            if isinstance(item_geo.get("endereco"), dict):
                item_geo["endereco"] = dict(item_geo["endereco"])
            if (
                item.get("coordenadas_fonte") == "gps_dispositivo"
                and item.get("latitude") is not None
                and not ChatbotService._endereco_real_do_usuario(item)
            ):
                self._preencher_endereco_reverso_gps(item, geocoder)
            if not self._item_local_confirmado_usuario(item):
                self._hidratar_endereco_inferivel_item(item, items, texto_sessao=texto_sessao)
                item_geo = dict(item)
                if isinstance(item_geo.get("endereco"), dict):
                    item_geo["endereco"] = dict(item_geo["endereco"])
            texto_item = (
                self._texto_curto_demanda(item)
                if self._item_local_confirmado_usuario(item)
                else self._texto_contexto_demanda(item_geo, texto_sessao)
            )
            if self._item_local_confirmado_usuario(item):
                campos_end = self._campos_endereco_ui(item, texto_contexto=texto_item)
                row["endereco"] = campos_end
                logradouro = campos_end.get("logradouro")
                bairro = campos_end.get("bairro")
                cep = campos_end.get("cep")
                logr_final = logradouro
                coords_manuais = self._coords_manuais_persistidas_item(item)
                if coords_manuais is not None:
                    latitude, longitude, fonte_coord = coords_manuais
                    geo_chave = item.get("_geo_chave") or f"gps:{latitude},{longitude}"
                else:
                    latitude = item.get("latitude")
                    longitude = item.get("longitude")
                    fonte_coord = item.get("coordenadas_fonte") or ""
                    if latitude is None or longitude is None:
                        latitude, longitude, fonte_coord = self._resolver_coordenadas_item(
                            item,
                            geocoder,
                            logradouro=logradouro,
                            bairro=bairro,
                            cep=cep,
                        )
                        if latitude is not None and longitude is not None:
                            item["latitude"] = round(latitude, 6)
                            item["longitude"] = round(longitude, 6)
                            item["coordenadas_fonte"] = fonte_coord
                            item["_geo_chave"] = GeocodingService.chave_endereco(
                                logradouro, bairro, cep
                            )
                            geo_persistido_no_rascunho = True
                    geo_chave = item.get("_geo_chave") or GeocodingService.chave_endereco(
                        logradouro, bairro, cep
                    )
            else:
                self._aplicar_endereco_canonico(item_geo, texto_item, preservar_existente=True)
                end_geo = item_geo.get("endereco") if isinstance(item_geo.get("endereco"), dict) else {}
                logradouro = self._limpar_logradouro(
                    (end_geo.get("logradouro") or "").strip() or None,
                    texto_contexto=texto_item,
                )
                bairro = ChatbotService._limpar_bairro(
                    (end_geo.get("bairro") or "").strip() or None,
                    texto_contexto=texto_item,
                )
                cep = (end_geo.get("cep") or "").strip() or None
                logr_final = logradouro
                if logr_final and not self._valor_campo_endereco_valido("logradouro", logr_final):
                    logr_final = None
                if bairro and not self._valor_campo_endereco_valido("bairro", bairro):
                    bairro = None
                if not logr_final:
                    bairro = None
                if logr_final or self._item_tem_local_inferido_pendente(item):
                    row["endereco"] = {
                        "cep": cep if cep and self._valor_campo_endereco_valido("cep", cep) else None,
                        "logradouro": logr_final,
                        "bairro": bairro,
                        "numero": end_geo.get("numero") if logr_final else None,
                        "complemento": end_geo.get("complemento") if logr_final else None,
                    }
                else:
                    row["endereco"] = dict(_ENDERECO_VAZIO)
                    logradouro = None
                    bairro = None
                    cep = None
                    logr_final = None
                geo_chave = GeocodingService.chave_endereco(logradouro, bairro, cep)
                coords_manuais = self._coords_manuais_persistidas_item(item)
                if coords_manuais is not None:
                    latitude, longitude, fonte_coord = coords_manuais
                    geo_chave = item.get("_geo_chave") or f"gps:{latitude},{longitude}"
                else:
                    latitude, longitude, fonte_coord = self._resolver_coordenadas_item(
                        item,
                        geocoder,
                        logradouro=logradouro,
                        bairro=bairro,
                        cep=cep,
                    )
                    if latitude is not None and longitude is not None:
                        item["latitude"] = round(latitude, 6)
                        item["longitude"] = round(longitude, 6)
                        item["coordenadas_fonte"] = fonte_coord
                        if fonte_coord == "gps_dispositivo":
                            item["_geo_chave"] = f"gps:{item['latitude']},{item['longitude']}"
                        else:
                            item["_geo_chave"] = geo_chave
                        geo_persistido_no_rascunho = True
            row["latitude"] = round(latitude, 6) if latitude is not None else None
            row["longitude"] = round(longitude, 6) if longitude is not None else None
            row["coordenadas_fonte"] = fonte_coord
            row["_geo_chave"] = item.get("_geo_chave") or geo_chave
            _obs_coord = {
                "indisponivel": "Coordenadas indisponíveis (informe CEP ou rua válida).",
                "gps_dispositivo": "Localização registrada pelo GPS do dispositivo.",
                "cep": "Ponto aproximado pelo CEP (via não localizada no mapa).",
                "bairro_cep": "Ponto aproximado por bairro + CEP.",
                "logradouro": "Geocodificado pela via pública informada.",
                "viacep_logradouro": "Via pública confirmada pelos Correios (ViaCEP) e localizada no mapa.",
                "via_referencia_local": "Coordenadas da base local de vias de Mogi das Cruzes.",
                "ajuste_mapa": "Ponto ajustado manualmente no mapa.",
                "aproximada": "Ponto aproximado no município.",
            }
            row["coordenadas_observacao"] = _obs_coord.get(fonte_coord, "")
            from core.services.endereco_normalizacao import (
                endereco_resumo_humano,
                montar_alerta_geocode,
            )

            end_row = row.get("endereco") if isinstance(row.get("endereco"), dict) else {}
            row["endereco_resumo"] = endereco_resumo_humano(end_row)
            row["geocode_alerta"] = montar_alerta_geocode(
                logradouro=end_row.get("logradouro") or logr_final,
                bairro=end_row.get("bairro") or bairro,
                cep=end_row.get("cep") or cep,
                latitude=row.get("latitude"),
                longitude=row.get("longitude"),
                endereco_informado=bool(
                    item.get("endereco_informado_usuario")
                    or item.get("local_confirmado_usuario")
                ),
            )

            vinculados: list[dict[str, Any]] = []
            for ai in sorted(mapa_anexos.get(dem_idx, set())):
                if ai >= len(anexos_sessao):
                    continue
                chat_anexo = anexos_sessao[ai]
                nome = (chat_anexo.descricao or "").strip() or Path(
                    chat_anexo.arquivo.name
                ).name
                entrada: dict[str, Any] = {
                    "indice_sessao": ai,
                    "nome": nome,
                }
                if chat_anexo.arquivo:
                    entrada["url"] = chat_anexo.arquivo.url
                vinculados.append(entrada)
            row["anexos"] = vinculados
            row["requer_localizacao"] = self._item_requer_localizacao_vinculada(item)
            row["local_pendente_confirmacao"] = self._item_tem_local_inferido_pendente(item)
            row["limiar_carta"] = self._limiar_carta_copiloto()
            row["aprovado_final"] = item.get("aprovado_final")
            row["descartada"] = bool(item.get("descartada"))
            row["vinculo_servico_ignorado"] = bool(item.get("vinculo_servico_ignorado"))
            pedido = (item.get("pedido_integral") or item.get("descricao") or "").strip()
            if pedido:
                row["pedido_integral"] = pedido

            resultado.append(row)

        if geo_persistido_no_rascunho:
            session.save(update_fields=["demandas_rascunho", "atualizado_em"])

        return resultado

    def _montar_resposta_http(
        self,
        session: ChatSession,
        parsed: dict[str, Any],
        criadas: list[dict[str, Any]],
    ) -> dict[str, Any]:
        rascunho = list(session.demandas_rascunho or [])
        if rascunho:
            texto_sessao = self._texto_usuario_da_sessao(session)
            self._pre_classificar_faq_em_lista(rascunho, texto_sessao=texto_sessao)
            self._aplicar_classificacao_competencia_rascunho(rascunho, texto_sessao=texto_sessao)
            self._limpar_triagem_fora_competencia(rascunho)
            session.demandas_rascunho = rascunho
            self._marcar_rascunho_indicacao(rascunho, session.autor)
            if not any(
                item.get("fora_competencia") for item in rascunho if isinstance(item, dict)
            ):
                self._popular_candidatos_sinapse_rascunho(session, rascunho)
            rascunho = list(session.demandas_rascunho or rascunho)
        body: dict[str, Any] = {
            "session_id": str(session.id),
            "resposta_agente": parsed.get("resposta_agente", ""),
            "estado_atual": session.estado_atual,
            "demandas_extraidas": self._enriquecer_demandas_para_ui(session, rascunho),
        }
        if criadas:
            body["demandas_criadas"] = criadas
            alertas: list[dict[str, Any]] = []
            for c in criadas:
                for a in c.get("alertas_duplicidade") or []:
                    if a not in alertas:
                        alertas.append(a)
            if alertas:
                from .copiloto_duplicidade_service import resumir_alertas_duplicidade

                body["alertas_duplicidade"] = alertas[:8]
                body["duplicidade_resumo"] = resumir_alertas_duplicidade(alertas[:8])
        if parsed.get("recusou_geracao_rascunhos"):
            body["recusou_geracao_rascunhos"] = True
        if parsed.get("anexos_adiados"):
            body["anexos_adiados"] = True
        if parsed.get("revisao_etapa"):
            body["revisao_etapa"] = parsed["revisao_etapa"]
        if parsed.get("revisao_indice_demanda") is not None:
            body["revisao_indice_demanda"] = parsed["revisao_indice_demanda"]
        if parsed.get("reabrir_anexos"):
            body["reabrir_anexos"] = True
        if parsed.get("revisao_encerrada"):
            body["revisao_encerrada"] = True
        body["anexos_na_sessao"] = session.anexos_sessao.count()
        self._anexar_corpus_legado_opcional(
            body,
            texto=self._texto_usuario_da_sessao(session),
            demandas=body.get("demandas_extraidas"),
        )
        return body

    def _aplicar_preselecao_corpus_atalho(
        self,
        dems: list[Any],
        servico_id: int,
        parsed: dict[str, Any],
        *,
        texto_sessao: str = "",
        eixo_id: str | None = None,
        auto_confirmar: bool = True,
    ) -> None:
        """Injeta e confirma serviço da carta quando o usuário escolhe pedido frequente."""
        from integrations import sinapse_catalog

        if not isinstance(dems, list) or not dems:
            return

        catalog = sinapse_catalog.get_servico(int(servico_id))
        if not catalog:
            return

        from core.services.corpus_legado_service import CorpusLegadoService

        opcoes: list[dict[str, Any]] = []
        if eixo_id:
            det = CorpusLegadoService().detalhe_atalho_copiloto(eixo_id)
            if det:
                opcoes = list(det.get("opcoes_carta") or [])
        if not opcoes:
            opcoes = [
                {
                    "servico_id": int(servico_id),
                    "titulo": (catalog.titulo or "").strip(),
                    "orgao": sinapse_catalog.get_orgao_nome(catalog.id_orgao_id),
                    "score": 0.95,
                    "padrao": True,
                }
            ]

        candidatos: list[dict[str, Any]] = []
        for op in opcoes:
            sid = op.get("servico_id")
            if sid is None:
                continue
            candidatos.append(
                {
                    "servico_id": int(sid),
                    "titulo": (op.get("titulo") or "").strip(),
                    "orgao": op.get("orgao"),
                    "score": float(
                        op.get("score") or (0.95 if int(sid) == int(servico_id) else 0.85)
                    ),
                    "fonte": "corpus_atalho",
                }
            )
        candidatos.sort(key=lambda c: 0 if c.get("servico_id") == servico_id else 1)
        filtrados = self._enriquecer_candidatos_utilizacao(candidatos[:6])

        titulo_serv = (catalog.titulo or "").strip() or "serviço da carta"
        rotulo_eixo = ""
        if eixo_id:
            meta_eixo = CorpusLegadoService().meta_pedido_frequente(eixo_id)
            if meta_eixo:
                rotulo_eixo = (meta_eixo.get("rotulo") or "").strip()
        for dem in dems:
            if not isinstance(dem, dict) or dem.get("fora_competencia") or dem.get("descartada"):
                continue
            if dem.get("servico_confirmado_usuario"):
                continue
            if rotulo_eixo:
                dem["titulo"] = rotulo_eixo[:200]
            dem["requer_localizacao"] = True
            dem["corpus_aguarda_complemento"] = True
            dem.pop("endereco_opcional_dispensado", None)
            dem.pop("local_confirmado_usuario", None)
            dem.pop("endereco_informado_usuario", None)
            dem["endereco"] = dict(_ENDERECO_VAZIO)
            dem.pop("latitude", None)
            dem.pop("longitude", None)
            dem.pop("coordenadas_fonte", None)
            dem.pop("_geo_chave", None)
            dem["candidatos_sinapse"] = filtrados
            dem["servico_sugerido_ui_id"] = servico_id
            dem["corpus_preselecao_servico_id"] = servico_id
            if eixo_id:
                dem["corpus_atalho_eixo_id"] = eixo_id
            dem["modo_vinculo_servico"] = "carta_forte"
            dem["fora_carta"] = False
            dem["servico_alerta"] = False
            if auto_confirmar:
                dem["sinapse_servico_id_sugerido"] = int(servico_id)
                dem["servico_local_id"] = int(servico_id)
                dem["servico_confirmado_usuario"] = True
                dem["origem_vinculo"] = Demanda.ORIGEM_VINCULO_CARTA
                dem["corpus_aguarda_complemento"] = True
                dem["requer_escolha_servico"] = False
                dem.pop("vinculo_servico_ignorado", None)
                dem.pop("tendencia_id", None)
                dem.pop("tendencia", None)
            else:
                dem["requer_escolha_servico"] = len(filtrados) > 1

        parsed["acionar_triagem_sinapse"] = False
        if auto_confirmar and filtrados:
            parsed["resposta_agente"] = (
                f"Registrei **{titulo_serv}** na carta. "
                "Complemente com rua, número, bairro ou referência do local "
                "(pode descrever no campo abaixo)."
            )

    def _turno_corpus_atalho_direto(
        self,
        session: ChatSession,
        texto: str,
        servico_id: int,
        eixo_id: str | None,
    ) -> dict[str, Any]:
        """Pedido frequente: confirma serviço na carta sem Groq nem triagem vetorial."""
        texto_limpo = (texto or "").strip() or "Solicitação"
        rascunho = list(session.demandas_rascunho or [])
        alvos = [
            x
            for x in rascunho
            if isinstance(x, dict)
            and not x.get("descartada")
            and not x.get("fora_competencia")
        ]
        if not alvos:
            slot: dict[str, Any] = {
                "titulo": "Solicitação",
                "descricao": texto_limpo,
                "pedido_integral": texto_limpo,
                "texto_para_embedding": texto_limpo[:500],
            }
            rascunho = [slot]
        else:
            pendente = next(
                (d for d in alvos if not d.get("servico_confirmado_usuario")),
                None,
            )
            if pendente is None:
                slot = {
                    "titulo": "Solicitação",
                    "descricao": texto_limpo,
                    "pedido_integral": texto_limpo,
                    "texto_para_embedding": texto_limpo[:500],
                }
                rascunho = list(rascunho) + [slot]

        parsed: dict[str, Any] = {
            "demandas_extraidas": rascunho,
            "estado_atual": session.estado_atual,
            "acionar_triagem_sinapse": False,
            "confirmar_criacao_demandas": False,
            "usuario_forneceu_endereco_real": False,
        }
        self._aplicar_preselecao_corpus_atalho(
            rascunho,
            servico_id,
            parsed,
            texto_sessao=texto_limpo,
            eixo_id=eixo_id,
        )
        parsed["demandas_extraidas"] = rascunho
        self._forcar_regras_estado_rigidas(parsed, pos_sinapse=False, session=session)
        return parsed

    def _demanda_elegivel_hint_corpus(self, dem: dict[str, Any]) -> bool:
        """Hints só quando a carta não oferece match forte — não altera triagem."""
        if dem.get("fora_competencia"):
            return False
        if dem.get("descartada"):
            return False
        if dem.get("servico_confirmado_usuario"):
            return False
        serv = dem.get("servico")
        if isinstance(serv, dict) and serv.get("confirmado"):
            return False
        if dem.get("tendencia_id") or dem.get("origem_vinculo") == Demanda.ORIGEM_VINCULO_TENDENCIA:
            return False
        if dem.get("fora_carta"):
            return True
        cands = dem.get("candidatos_sinapse")
        if not isinstance(cands, list) or not cands:
            return True
        best = self._score_max_candidatos(dem) or 0.0
        return best < self._limiar_carta_copiloto()

    def _anexar_corpus_legado_opcional(
        self,
        body: dict[str, Any],
        *,
        texto: str = "",
        demandas: list[Any] | None = None,
    ) -> None:
        """Camada assistiva opcional — não altera triagem, tendências nem confirmação de serviço."""
        from core.services.copiloto_config import (
            corpus_legado_habilitado,
            corpus_legado_hints_copiloto_habilitados,
        )
        from core.services.corpus_legado_service import CorpusLegadoService

        if not corpus_legado_habilitado():
            return
        svc = CorpusLegadoService()
        atalhos = svc.atalhos_copiloto(limite=12)
        if atalhos:
            body["corpus_atalhos_top_trends"] = atalhos
        if not corpus_legado_hints_copiloto_habilitados():
            return

        demandas_alvo = demandas if isinstance(demandas, list) else body.get("demandas_extraidas")
        if not isinstance(demandas_alvo, list):
            demandas_alvo = []

        hints_globais: list[dict[str, Any]] = []
        for dem in demandas_alvo:
            if not isinstance(dem, dict):
                continue
            if not self._demanda_elegivel_hint_corpus(dem):
                continue
            texto_dem = self._texto_coerencia_demanda(dem, texto)
            if len((texto_dem or "").strip()) < 12:
                continue
            serv_prior = (dem.get("servico_legado_hint") or "").strip() or None
            sugestoes = svc.hints_pos_triagem(
                texto_dem,
                limite=3,
                servico_legado_prioritario=serv_prior,
            )
            if not sugestoes:
                continue
            dem["corpus_hints_historico"] = sugestoes
            hints_globais.extend(sugestoes)

        if hints_globais:
            vistos: set[str] = set()
            dedup: list[dict[str, Any]] = []
            for h in hints_globais:
                chave = (h.get("servico_legado") or h.get("id") or "").strip()
                if chave in vistos:
                    continue
                vistos.add(chave)
                dedup.append(h)
            body["corpus_sugestoes_historico"] = dedup[:3]

    @staticmethod
    def _texto_usuario_da_sessao(session: ChatSession | None) -> str:
        if not session:
            return ""
        partes: list[str] = []
        for msg in session.historico_mensagens or []:
            if isinstance(msg, dict) and msg.get("role") == "user":
                partes.append(str(msg.get("content") or ""))
        return " ".join(partes).strip()

    @staticmethod
    def _extrair_endereco_canonico(texto: str) -> dict[str, Any]:
        """Extrai CEP, bairro e via pública do texto livre do cidadão (regex, sem LLM)."""
        out: dict[str, Any] = dict(_ENDERECO_VAZIO)
        t = ChatbotService._texto_util_para_extracao_endereco(texto or "")
        if not t:
            return out

        m_cep = re.search(r"\b(\d{5})-?(\d{3})\b", t)
        if m_cep:
            out["cep"] = f"{m_cep.group(1)}-{m_cep.group(2)}"

        m_via = _EXTRAI_VIA_RE.search(t)
        if m_via:
            via = m_via.group(1).strip()
            via = _LIMPEZA_PREFIXO_LOGRADOURO_RE.sub("", via).strip()
            if len(via) >= 6:
                out["logradouro"] = via[:255]

        bairro_exp = ChatbotService._extrair_bairro_explicito(t)
        if bairro_exp:
            out["bairro"] = bairro_exp

        return out

    @staticmethod
    def _texto_contexto_demanda(item: dict[str, Any], texto_sessao: str) -> str:
        """Texto para regex de endereço: prioriza título/descrição do item + endereço já no rascunho."""
        end = item.get("endereco") if isinstance(item.get("endereco"), dict) else {}
        partes = [
            (item.get("titulo") or "").strip(),
            (item.get("descricao") or "").strip(),
            (end.get("logradouro") or "").strip(),
            (end.get("bairro") or "").strip(),
            (end.get("cep") or "").strip(),
        ]
        for bloco in re.split(r"(?<=\.)\s+", (texto_sessao or "").strip()):
            util = ChatbotService._texto_util_para_extracao_endereco(bloco)
            if util:
                partes.append(util)
        return " ".join(p for p in partes if p)

    @staticmethod
    def _preencher_endereco_reverso_gps(
        item: dict[str, Any], geocoder: GeocodingService
    ) -> str:
        """Preenche endereco no rascunho a partir de lat/lng (GPS). Retorna mensagem ao usuário."""
        lat = item.get("latitude")
        lng = item.get("longitude")
        if lat is None or lng is None:
            return "Localização do dispositivo registrada."
        if item.get("coordenadas_fonte") != "gps_dispositivo":
            return "Localização do dispositivo registrada."

        end = item.get("endereco") if isinstance(item.get("endereco"), dict) else {}
        if ChatbotService._endereco_real_do_usuario({"endereco": end}):
            return "Localização do dispositivo registrada."

        dados = geocoder.buscar_endereco_por_coordenadas(float(lat), float(lng))
        if not dados:
            return (
                "Localização do dispositivo registrada. "
                "Não foi possível identificar rua/bairro no mapa — informe o endereço por texto se precisar."
            )

        logr = (dados.get("logradouro") or "").strip() or None
        bai = (dados.get("bairro") or "").strip() or None
        cep = dados.get("cep")
        numero = dados.get("numero")
        if logr and not ChatbotService._valor_campo_endereco_valido("logradouro", logr):
            logr = None
        if bai and not ChatbotService._valor_campo_endereco_valido("bairro", bai):
            bai = None

        item["endereco"] = {
            "cep": cep,
            "logradouro": logr,
            "numero": numero,
            "bairro": bai,
            "complemento": end.get("complemento"),
        }
        item["_geo_chave"] = GeocodingService.chave_endereco(logr, bai, cep)
        partes = [p for p in (logr, bai, cep) if p]
        if partes:
            return (
                "Localização e endereço aproximado registrados: "
                + ", ".join(partes)
                + "."
            )
        return "Localização do dispositivo registrada."

    @staticmethod
    def _coords_manuais_persistidas_item(
        item: dict[str, Any],
    ) -> tuple[float, float, str] | None:
        """Coordenadas definidas pelo usuário (pin/GPS) — não re-geocodificar pelo endereço."""
        fonte = (item.get("coordenadas_fonte") or "").strip()
        if fonte not in ("ajuste_mapa", "gps_dispositivo"):
            return None
        lat = item.get("latitude")
        lng = item.get("longitude")
        if lat is None or lng is None:
            return None
        return float(lat), float(lng), fonte

    def _coordenadas_endereco_materializacao(
        self,
        item: dict[str, Any],
        geocoder: GeocodingService,
        *,
        logradouro: str | None,
        bairro: str | None,
        cep: str | None,
    ) -> tuple[float | None, float | None, str, str | None, str | None, str | None]:
        """
        Resolve lat/lng para criar Demanda, priorizando pin/GPS do rascunho.
        Retorna (latitude, longitude, fonte, logradouro, bairro, cep).
        """
        coords_manuais = self._coords_manuais_persistidas_item(item)
        if coords_manuais is not None:
            lat, lng, fonte = coords_manuais
            return lat, lng, fonte, logradouro, bairro, cep

        res_geo = geocoder.resolver_endereco_geocode(logradouro, bairro, cep)
        return (
            res_geo.get("latitude"),
            res_geo.get("longitude"),
            res_geo.get("fonte") or "indisponivel",
            res_geo.get("logradouro") or logradouro,
            res_geo.get("bairro") or bairro,
            res_geo.get("cep") or cep,
        )

    def _resolver_coordenadas_item(
        self,
        item: dict[str, Any],
        geocoder: GeocodingService,
        *,
        logradouro: str | None,
        bairro: str | None,
        cep: str | None,
    ) -> tuple[float | None, float | None, str]:
        """Prioriza GPS; normaliza endereço; geocodifica com gate para cluster."""
        raw_lat = item.get("latitude")
        raw_lng = item.get("longitude")
        fonte_item = (item.get("coordenadas_fonte") or "").strip()

        end = item.get("endereco") if isinstance(item.get("endereco"), dict) else {}
        logr = logradouro or end.get("logradouro")
        bai = bairro or end.get("bairro")
        cep_val = cep or end.get("cep")

        if raw_lat is not None and raw_lng is not None and fonte_item == "ajuste_mapa":
            return float(raw_lat), float(raw_lng), "ajuste_mapa"

        if raw_lat is not None and raw_lng is not None and fonte_item == "gps_dispositivo":
            res = geocoder.resolver_endereco_geocode(logr, bai, cep_val)
            for chave in ("logradouro", "bairro", "cep"):
                val = res.get(chave)
                if val:
                    if not isinstance(item.get("endereco"), dict):
                        item["endereco"] = {}
                    item["endereco"][chave] = val
            from core.services.endereco_normalizacao import filtrar_coordenadas_para_persistencia

            lat_p, lng_p, fonte_p = filtrar_coordenadas_para_persistencia(
                float(raw_lat),
                float(raw_lng),
                "gps_dispositivo",
                res.get("logradouro") or logr,
                res.get("bairro") or bai,
            )
            if lat_p is not None:
                return lat_p, lng_p, fonte_p
            return float(raw_lat), float(raw_lng), "gps_dispositivo"

        geo_chave = GeocodingService.chave_endereco(logr, bai, cep_val)
        if (
            raw_lat is not None
            and raw_lng is not None
            and fonte_item not in ("", "indisponivel")
            and (item.get("_geo_chave") or "") == geo_chave
        ):
            return float(raw_lat), float(raw_lng), fonte_item or "logradouro"

        res = geocoder.resolver_endereco_geocode(logr, bai, cep_val)
        if not isinstance(item.get("endereco"), dict):
            item["endereco"] = {}
        for chave in ("logradouro", "bairro", "cep"):
            val = res.get(chave)
            if val:
                item["endereco"][chave] = val

        return res.get("latitude"), res.get("longitude"), res.get("fonte") or "indisponivel"

    @staticmethod
    def _aplicar_endereco_canonico(
        item: dict[str, Any],
        texto_fonte: str,
        *,
        preservar_existente: bool = True,
    ) -> None:
        """Preenche endereço do rascunho com extração determinística (sem sobrescrever CEP da demanda)."""
        ext = ChatbotService._extrair_endereco_canonico(texto_fonte)
        if not any(ext.get(k) for k in ("cep", "logradouro", "bairro")):
            return
        end = item.get("endereco")
        if not isinstance(end, dict):
            end = {}
            item["endereco"] = end
        for chave in ("cep", "logradouro", "numero", "bairro", "complemento"):
            val = ext.get(chave)
            if val in (None, "", []):
                continue
            if preservar_existente and (end.get(chave) or "").strip():
                continue
            end[chave] = val

    @staticmethod
    def _limpar_logradouro(valor: str | None, texto_contexto: str | None = None) -> str | None:
        """Remove comandos do usuário; extrai só o nome da via pública."""
        fontes = [valor or "", texto_contexto or ""]
        for fonte in fontes:
            ext = ChatbotService._extrair_endereco_canonico(fonte)
            logr = (ext.get("logradouro") or "").strip()
            if logr and ChatbotService._valor_campo_endereco_valido("logradouro", logr):
                return logr[:255]
            parque = ChatbotService._extrair_nome_parque(fonte)
            if parque and len((fonte or "").split()) <= 6:
                return parque

        t = (valor or "").strip()
        if not t:
            return None
        anterior = None
        while anterior != t:
            anterior = t
            t = _LIMPEZA_PREFIXO_LOGRADOURO_RE.sub("", t).strip()
        if _PALAVRAS_PEDIDO_NO_LOGRADOURO_RE.search(t) or _LOGRADOURO_FRASE_PEDIDO_RE.search(t):
            parque = ChatbotService._extrair_nome_parque(t)
            if parque and len(t.split()) <= 6:
                return parque
            return None
        parque = ChatbotService._extrair_nome_parque(t)
        if parque and len(t.split()) <= 6:
            return parque
        if len(t) < 4 or not ChatbotService._valor_campo_endereco_valido("logradouro", t):
            return None
        return t[:255]

    def _aplicar_triagem_sinapse_no_item(self, item: dict[str, Any]) -> bool:
        """Busca carta Sinapse por item; preenche candidatos (sem confirmar serviço automaticamente)."""
        if item.get("tendencia_id") or item.get("origem_vinculo") == Demanda.ORIGEM_VINCULO_TENDENCIA:
            return False
        if self._servico_confirmado_pelo_usuario(item):
            return True

        candidatos = self._triagem_sinapse_consolidada(item)
        if not candidatos:
            return False
        item["candidatos_sinapse"] = candidatos
        return True

    @staticmethod
    def _resolver_sinapse_servico_id(item: dict[str, Any]) -> int | None:
        raw = item.get("sinapse_servico_id_sugerido")
        if raw is None:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    def _materializar_demanda_tendencia(
        self,
        usuario,
        item: dict[str, Any],
        *,
        texto_sessao: str,
        geocoder: GeocodingService,
        oficio_svc: Any,
        session: ChatSession | None,
        texto_item: str,
    ) -> dict[str, Any] | None:
        """Cria Demanda + tendência + ofício para item fora da carta."""
        from decimal import Decimal

        svc = TendenciaService()
        tid = item.get("tendencia_id")
        if tid:
            tendencia = Tendencia.objects.filter(pk=int(tid)).first()
            if not tendencia:
                tendencia = svc.buscar_ou_criar(
                    titulo=(item.get("titulo") or "Solicitação fora da carta"),
                    texto_embedding=(item.get("texto_para_embedding") or item.get("titulo") or ""),
                    descricao_resumo=(item.get("descricao") or ""),
                    sinapse_orgao_id=item.get("sinapse_orgao_id_sugerido"),
                    criado_por=usuario,
                    score_triagem_max=self._score_max_candidatos(item),
                )
        else:
            tendencia = svc.buscar_ou_criar(
                titulo=(item.get("titulo") or "Solicitação fora da carta"),
                texto_embedding=(item.get("texto_para_embedding") or item.get("titulo") or ""),
                descricao_resumo=(item.get("descricao") or ""),
                sinapse_orgao_id=item.get("sinapse_orgao_id_sugerido"),
                criado_por=usuario,
                score_triagem_max=self._score_max_candidatos(item),
            )

        servico_nome = "Solicitação não catalogada na carta de serviços"
        relato_usuario = self._relato_integral_item(item, session=session).strip()
        titulo = self._titulo_demanda_item(
            item, relato_usuario, servico_nome=servico_nome
        )[:200]
        if not relato_usuario:
            relato_usuario = titulo
        end = item.get("endereco") if isinstance(item.get("endereco"), dict) else {}
        logradouro = self._limpar_logradouro(
            (end.get("logradouro") or "").strip() or None,
            texto_contexto=texto_item,
        )
        bairro = (end.get("bairro") or "").strip() or None
        if bairro and not self._valor_campo_endereco_valido("bairro", bairro):
            bairro = None
        cep = (end.get("cep") or "").strip() or None
        numero = ChatbotService._campo_endereco_str(end.get("numero")) or None
        complemento = (end.get("complemento") or "").strip() or None

        orgao_id = tendencia.sinapse_orgao_id
        if orgao_id is None and item.get("sinapse_orgao_id_sugerido"):
            try:
                orgao_id = int(item["sinapse_orgao_id_sugerido"])
            except (TypeError, ValueError):
                orgao_id = None
        orgao_nome = sinapse_catalog.get_orgao_nome(orgao_id) or "Protocolo Geral"

        partes_end: list[str] = []
        if logradouro:
            trecho = logradouro
            if numero:
                trecho = f"{trecho}, {numero}"
            partes_end.append(trecho)
        if bairro:
            partes_end.append(f"Bairro {bairro}")
        if cep:
            partes_end.append(f"CEP {cep}")
        if complemento:
            partes_end.append(complemento)
        endereco_fmt = " — ".join(partes_end)

        autor_nome = usuario.get_full_name() or usuario.username
        autor_cargo = getattr(usuario, "cargo", None) or ""
        if oficio_svc:
            descricao = oficio_svc.montar_descricao_oficio(
                titulo=titulo,
                relato=relato_usuario,
                endereco_formatado=endereco_fmt,
                servico_nome=servico_nome,
                orgao_nome=orgao_nome,
                autor_nome=autor_nome,
                autor_cargo=autor_cargo,
            )
        else:
            descricao = relato_usuario

        latitude, longitude, _fonte_geo = self._resolver_coordenadas_item(
            item,
            geocoder,
            logradouro=logradouro,
            bairro=bairro,
            cep=cep,
        )
        campos_demanda: dict[str, Any] = {
            "titulo": titulo,
            "descricao": descricao,
            "autor": usuario,
            "cep": cep,
            "logradouro": logradouro,
            "numero": numero,
            "complemento": complemento,
            "bairro": bairro,
            "status": "RASCUNHO",
            "origem_vinculo": Demanda.ORIGEM_VINCULO_TENDENCIA,
            "tendencia": tendencia,
            "sinapse_servico_id": None,
            "sinapse_orgao_id": orgao_id,
        }
        if latitude is not None and longitude is not None:
            campos_demanda["latitude"] = Decimal(str(round(latitude, 6)))
            campos_demanda["longitude"] = Decimal(str(round(longitude, 6)))

        with transaction.atomic():
            d = Demanda.objects.create(**campos_demanda)
            svc.registrar_ocorrencia(
                tendencia,
                demanda=d,
                session=session,
                indice_demanda=None,
                texto_origem=texto_item[:8000],
                score_triagem_max=self._score_max_candidatos(item),
            )

        return {
            "demanda": d,
            "resumo": {
                "id": d.id,
                "titulo": d.titulo,
                "servico_nome": servico_nome,
                "sinapse_servico_id": None,
                "tendencia_id": tendencia.id,
                "tendencia_titulo": tendencia.titulo,
                "latitude": float(d.latitude) if d.latitude is not None else None,
                "longitude": float(d.longitude) if d.longitude is not None else None,
                "oficio_pdf": None,
                "oficio_url": None,
            },
        }

    def _materializar_demanda_indicacao(
        self,
        usuario,
        item: dict[str, Any],
        *,
        texto_sessao: str,
        geocoder: GeocodingService,
        session: ChatSession | None,
        texto_item: str,
    ) -> dict[str, Any] | None:
        """Cria Demanda de indicação legislativa (perfil CAMARA) a partir do rascunho do copiloto."""
        from decimal import Decimal

        from .indicacao_numeracao_service import IndicacaoNumeracaoService
        from .indicacao_service import sincronizar_vinculos_vereador

        relato_usuario = self._relato_integral_item(item, session=session).strip()
        titulo = self._titulo_demanda_item(
            item, relato_usuario, servico_nome="Indicação legislativa"
        )[:200]
        if not relato_usuario:
            relato_usuario = titulo

        try:
            numero = int(item.get("numero_indicacao"))
        except (TypeError, ValueError):
            logger.warning("Indicação sem número válido no rascunho.")
            return None

        num_svc = IndicacaoNumeracaoService()
        cfg = num_svc.carregar_config()
        ano = int(cfg.ano)
        try:
            num_svc.validar_numero(numero, ano)
        except ValueError as exc:
            logger.info("Materialização indicação bloqueada (número): %s", exc)
            return None

        end = item.get("endereco") if isinstance(item.get("endereco"), dict) else {}
        logradouro = self._limpar_logradouro(
            (end.get("logradouro") or "").strip() or None,
            texto_contexto=texto_item,
        )
        bairro = (end.get("bairro") or "").strip() or None
        if bairro and not self._valor_campo_endereco_valido("bairro", bairro):
            bairro = None
        cep = (end.get("cep") or "").strip() or None
        numero_end = ChatbotService._campo_endereco_str(end.get("numero")) or None
        complemento = (end.get("complemento") or "").strip() or None

        latitude, longitude, _fonte_geo, logradouro, bairro, cep = (
            self._coordenadas_endereco_materializacao(
                item,
                geocoder,
                logradouro=logradouro,
                bairro=bairro,
                cep=cep,
            )
        )

        trilha_tendencia = (
            item.get("tendencia_id")
            or item.get("origem_vinculo") == Demanda.ORIGEM_VINCULO_TENDENCIA
            or (
                copiloto_tendencias_habilitadas()
                and (
                    item.get("vinculo_servico_ignorado")
                    or self._item_sugere_trilha_tendencia(item, texto_sessao=texto_sessao)
                )
            )
        )
        sinapse_id = self._resolver_sinapse_id_confirmado(item)
        if not trilha_tendencia and sinapse_id is None:
            if not self._item_vinculo_catalogo_resolvido(item):
                logger.warning(
                    "Indicação ignorada (serviço/tendência não confirmados): %s",
                    titulo[:80],
                )
                return None

        campos_demanda: dict[str, Any] = {
            "titulo": titulo,
            "descricao": relato_usuario,
            "autor": usuario,
            "cep": cep,
            "logradouro": logradouro,
            "numero": numero_end,
            "complemento": complemento,
            "bairro": bairro,
            "status": "RASCUNHO",
            "tipo_legislativo": Demanda.TIPO_LEGISLATIVO_INDICACAO,
            "numero_indicacao": numero,
            "ano_indicacao": ano,
            "sinapse_servico_id": None,
            "sinapse_orgao_id": None,
        }

        tendencia_obj = None
        if trilha_tendencia:
            from .tendencia_service import TendenciaService

            svc_tend = TendenciaService()
            tid = item.get("tendencia_id")
            if tid:
                tendencia_obj = Tendencia.objects.filter(pk=int(tid)).first()
            if not tendencia_obj:
                tendencia_obj = svc_tend.buscar_ou_criar(
                    titulo=(item.get("titulo") or titulo or "Indicação fora da carta"),
                    texto_embedding=(item.get("texto_para_embedding") or titulo or ""),
                    descricao_resumo=(item.get("descricao") or relato_usuario or ""),
                    sinapse_orgao_id=item.get("sinapse_orgao_id_sugerido"),
                    criado_por=usuario,
                    score_triagem_max=self._score_max_candidatos(item),
                )
            orgao_id = tendencia_obj.sinapse_orgao_id
            if orgao_id is None and item.get("sinapse_orgao_id_sugerido"):
                try:
                    orgao_id = int(item["sinapse_orgao_id_sugerido"])
                except (TypeError, ValueError):
                    orgao_id = None
            campos_demanda["origem_vinculo"] = Demanda.ORIGEM_VINCULO_TENDENCIA
            campos_demanda["tendencia"] = tendencia_obj
            campos_demanda["sinapse_orgao_id"] = orgao_id
        elif sinapse_id is not None:
            from core.services.carta_utilizacao_service import CartaUtilizacaoService

            try:
                CartaUtilizacaoService().validar_protocolo(
                    sinapse_id,
                    contexto="materializar_indicacao_copiloto",
                )
            except ValueError as exc:
                logger.info(
                    "Materialização indicação bloqueada (serviço informativo): %s — %s",
                    sinapse_id,
                    exc,
                )
                return None
            orgao_id = sinapse_catalog.get_orgao_id_for_servico(sinapse_id)
            campos_demanda["sinapse_servico_id"] = sinapse_id
            campos_demanda["sinapse_orgao_id"] = orgao_id
            campos_demanda["origem_vinculo"] = Demanda.ORIGEM_VINCULO_CARTA

        if latitude is not None and longitude is not None:
            campos_demanda["latitude"] = Decimal(str(round(latitude, 6)))
            campos_demanda["longitude"] = Decimal(str(round(longitude, 6)))

        try:
            with transaction.atomic():
                d = Demanda.objects.create(**campos_demanda)
                sincronizar_vinculos_vereador(
                    d,
                    item.get("vereadores_vinculados_ids"),
                    autor_vereador_id=item.get("autor_vereador_id"),
                )
                if trilha_tendencia and tendencia_obj is not None:
                    from .tendencia_service import TendenciaService

                    TendenciaService().registrar_ocorrencia(
                        tendencia_obj,
                        demanda=d,
                        session=session,
                        indice_demanda=None,
                        texto_origem=texto_item[:8000],
                        score_triagem_max=self._score_max_candidatos(item),
                    )
        except ValueError as exc:
            logger.info("Materialização indicação bloqueada (vínculos): %s", exc)
            return None

        return {"demanda": d}

    def _materializar_demandas(
        self,
        usuario,
        rascunhos: list[Any],
        *,
        session: ChatSession | None = None,
    ) -> list[dict[str, Any]]:
        criadas: list[dict[str, Any]] = []
        if not isinstance(rascunhos, list):
            return criadas

        texto_sessao = self._texto_usuario_da_sessao(session)
        geocoder = GeocodingService()
        oficio_svc = None
        try:
            from .oficio_service import OficioService

            oficio_svc = OficioService()
        except ImportError:
            logger.warning("OficioService indisponível; descrição sem texto formal de ofício.")

        demandas_objs: list[Demanda] = []
        autor_nome = usuario.get_full_name() or usuario.username
        autor_cargo = getattr(usuario, "cargo", None) or ""
        from .copiloto_duplicidade_service import buscar_alertas_duplicidade

        for item in rascunhos:
            if not isinstance(item, dict):
                continue

            if item.get("fora_competencia") or item.get("descartada"):
                logger.warning(
                    "Rascunho ignorado (fora de competência ou descartado): %s",
                    (item.get("titulo") or "")[:80],
                )
                continue

            texto_item = self._texto_contexto_demanda(item, texto_sessao)

            if item.get("modo_indicacao"):
                criada = self._materializar_demanda_indicacao(
                    usuario,
                    item,
                    texto_sessao=texto_sessao,
                    geocoder=geocoder,
                    session=session,
                    texto_item=texto_item,
                )
                if criada:
                    demandas_objs.append(criada["demanda"])
                continue

            self._aplicar_endereco_canonico(item, texto_item)
            preservado = self._preservar_relato_rascunho(session, [item])
            if preservado:
                item.update(preservado[0])

            trilha_tendencia = (
                item.get("tendencia_id")
                or item.get("origem_vinculo") == Demanda.ORIGEM_VINCULO_TENDENCIA
                or (
                    copiloto_tendencias_habilitadas()
                    and (
                        item.get("vinculo_servico_ignorado")
                        or self._item_sugere_trilha_tendencia(item, texto_sessao=texto_sessao)
                    )
                )
            )

            sinapse_id = self._resolver_sinapse_id_confirmado(item)
            if sinapse_id is not None:
                catalog = sinapse_catalog.get_servico(sinapse_id)
                if not catalog:
                    logger.warning("Serviço Sinapse inválido no rascunho: %s", sinapse_id)
                    continue

                from core.services.carta_utilizacao_service import CartaUtilizacaoService

                try:
                    CartaUtilizacaoService().validar_protocolo(
                        sinapse_id,
                        contexto="materializar_demanda_copiloto",
                    )
                except ValueError as exc:
                    logger.info(
                        "Materialização bloqueada (serviço informativo): %s — %s",
                        sinapse_id,
                        exc,
                    )
                    continue

                orgao_id = sinapse_catalog.get_orgao_id_for_servico(sinapse_id)
                orgao_nome = sinapse_catalog.get_orgao_nome(orgao_id) or ""
                servico_nome = catalog.titulo if catalog else ""

                relato_usuario = self._relato_integral_item(item, session=session).strip()
                titulo = self._titulo_demanda_item(
                    item, relato_usuario, servico_nome=servico_nome
                )[:200]
                if not relato_usuario:
                    relato_usuario = titulo
                end = item.get("endereco") if isinstance(item.get("endereco"), dict) else {}

                logradouro = self._limpar_logradouro(
                    (end.get("logradouro") or "").strip() or None,
                    texto_contexto=texto_item,
                )
                bairro = (end.get("bairro") or "").strip() or None
                if bairro and not self._valor_campo_endereco_valido("bairro", bairro):
                    bairro = None
                cep = (end.get("cep") or "").strip() or None
                numero = ChatbotService._campo_endereco_str(end.get("numero")) or None
                complemento = (end.get("complemento") or "").strip() or None

                latitude, longitude, _fonte_geo, logradouro, bairro, cep = (
                    self._coordenadas_endereco_materializacao(
                        item,
                        geocoder,
                        logradouro=logradouro,
                        bairro=bairro,
                        cep=cep,
                    )
                )

                partes_end: list[str] = []
                if logradouro:
                    trecho = logradouro
                    if numero:
                        trecho = f"{trecho}, {numero}"
                    partes_end.append(trecho)
                if bairro:
                    partes_end.append(f"Bairro {bairro}")
                if cep:
                    partes_end.append(f"CEP {cep}")
                if complemento:
                    partes_end.append(complemento)
                endereco_fmt = " — ".join(partes_end)

                if oficio_svc:
                    descricao = oficio_svc.montar_descricao_oficio(
                        titulo=titulo,
                        relato=relato_usuario,
                        endereco_formatado=endereco_fmt,
                        servico_nome=servico_nome,
                        orgao_nome=orgao_nome,
                        autor_nome=autor_nome,
                        autor_cargo=autor_cargo,
                    )
                else:
                    descricao = relato_usuario

                campos_demanda: dict[str, Any] = {
                    "titulo": titulo,
                    "descricao": descricao,
                    "autor": usuario,
                    "cep": cep,
                    "logradouro": logradouro,
                    "numero": numero,
                    "complemento": complemento,
                    "bairro": bairro,
                    "status": "RASCUNHO",
                    "sinapse_servico_id": sinapse_id,
                    "sinapse_orgao_id": orgao_id,
                }
                if latitude is not None and longitude is not None:
                    campos_demanda["latitude"] = Decimal(str(round(latitude, 6)))
                    campos_demanda["longitude"] = Decimal(str(round(longitude, 6)))

                with transaction.atomic():
                    d = Demanda.objects.create(**campos_demanda)
                demandas_objs.append(d)
                continue

            if trilha_tendencia:
                criada = self._materializar_demanda_tendencia(
                    usuario,
                    item,
                    texto_sessao=texto_sessao,
                    geocoder=geocoder,
                    oficio_svc=oficio_svc,
                    session=session,
                    texto_item=texto_item,
                )
                if criada:
                    demandas_objs.append(criada["demanda"])
                continue

            logger.warning(
                "Rascunho ignorado (serviço da carta não confirmado): %s",
                (item.get("titulo") or "")[:80],
            )
            continue

        if not demandas_objs:
            return criadas

        if session is not None:
            self._copiar_anexos_sessao_para_demandas(
                session, demandas_objs, rascunho_items=rascunhos
            )

        for d in demandas_objs:
            oficio_url: str | None = None
            alertas_dup = buscar_alertas_duplicidade(
                usuario,
                titulo=d.titulo,
                descricao=d.descricao,
                logradouro=d.logradouro,
                bairro=d.bairro,
                latitude=float(d.latitude) if d.latitude is not None else None,
                longitude=float(d.longitude) if d.longitude is not None else None,
                sinapse_servico_id=d.sinapse_servico_id,
                excluir_demanda_id=d.id,
            )

            if d.origem_vinculo == Demanda.ORIGEM_VINCULO_TENDENCIA:
                tend = d.tendencia
                servico_nome = "Solicitação não catalogada na carta de serviços"
                resumo = {
                    "id": d.id,
                    "titulo": d.titulo,
                    "servico_nome": servico_nome,
                    "sinapse_servico_id": None,
                    "tendencia_id": tend.id if tend else None,
                    "tendencia_titulo": tend.titulo if tend else None,
                    "latitude": float(d.latitude) if d.latitude is not None else None,
                    "longitude": float(d.longitude) if d.longitude is not None else None,
                    "oficio_pdf": None,
                    "oficio_url": oficio_url,
                }
            elif d.tipo_legislativo == Demanda.TIPO_LEGISLATIVO_INDICACAO:
                resumo = {
                    "id": d.id,
                    "titulo": d.titulo,
                    "tipo_legislativo": Demanda.TIPO_LEGISLATIVO_INDICACAO,
                    "numero_indicacao": d.numero_indicacao,
                    "ano_indicacao": d.ano_indicacao,
                    "servico_nome": "Indicação legislativa",
                    "sinapse_servico_id": None,
                    "latitude": float(d.latitude) if d.latitude is not None else None,
                    "longitude": float(d.longitude) if d.longitude is not None else None,
                    "oficio_pdf": None,
                    "oficio_url": None,
                }
            else:
                resumo = {
                    "id": d.id,
                    "titulo": d.titulo,
                    "servico_nome": (
                        sinapse_catalog.get_servico(d.sinapse_servico_id).titulo
                        if sinapse_catalog.get_servico(d.sinapse_servico_id)
                        else ""
                    ),
                    "sinapse_servico_id": d.sinapse_servico_id,
                    "latitude": float(d.latitude) if d.latitude is not None else None,
                    "longitude": float(d.longitude) if d.longitude is not None else None,
                    "oficio_pdf": None,
                    "oficio_url": oficio_url,
                }
            if alertas_dup:
                from .copiloto_duplicidade_service import resumir_alertas_duplicidade

                resumo["alertas_duplicidade"] = alertas_dup
                resumo["duplicidade_resumo"] = resumir_alertas_duplicidade(alertas_dup)
            criadas.append(resumo)
        return criadas

    @staticmethod
    def _inferir_indice_demanda_pelo_texto(texto: str, rascunho: list[Any]) -> int | None:
        """Heurística: associa anexo à demanda quando o usuário indica na mensagem."""
        if not rascunho:
            return None
        if len(rascunho) == 1:
            return 0

        t = (texto or "").lower()
        if not t:
            return None

        for i, item in enumerate(rascunho):
            if not isinstance(item, dict):
                continue
            titulo = (item.get("titulo") or "").strip().lower()
            if len(titulo) >= 4 and titulo in t:
                return i

        ordinais = (
            (r"\b(primeir[ao]|1\s*ª|1a|item\s*1|solicita[cç][aã]o\s*1|demanda\s*1)\b", 0),
            (r"\b(segund[ao]|2\s*ª|2a|item\s*2|solicita[cç][aã]o\s*2|demanda\s*2)\b", 1),
            (r"\b(terceir[ao]|3\s*ª|3a|item\s*3|solicita[cç][aã]o\s*3|demanda\s*3)\b", 2),
        )
        for padrao, idx in ordinais:
            if re.search(padrao, t) and idx < len(rascunho):
                return idx
        return None

    @staticmethod
    def _normalizar_anexos_indices(raw: Any) -> list[int]:
        if not isinstance(raw, list):
            return []
        out: list[int] = []
        for v in raw:
            try:
                out.append(int(v))
            except (TypeError, ValueError):
                continue
        return out

    @classmethod
    def _mapa_anexos_por_demanda(
        cls,
        anexos_sessao: list,
        rascunho_items: list[Any],
        demandas: list[Demanda],
    ) -> dict[int, set[int]]:
        """demanda_index -> conjunto de índices em anexos_sessao (ordem cronológica)."""
        n_anexos = len(anexos_sessao)
        n_dem = len(demandas)
        mapa: dict[int, set[int]] = {i: set() for i in range(n_dem)}

        vinculos_explicitos: dict[int, int] = {}
        for ai, chat_anexo in enumerate(anexos_sessao):
            ind = getattr(chat_anexo, "indice_demanda", None)
            if ind is not None and 0 <= ind < n_dem:
                vinculos_explicitos[ai] = ind

        if n_dem > 1 and vinculos_explicitos:
            for ai, dem_idx in vinculos_explicitos.items():
                mapa[dem_idx].add(ai)
            return mapa

        for dem_idx, item in enumerate(rascunho_items):
            if dem_idx >= n_dem or not isinstance(item, dict):
                continue
            for ai in cls._normalizar_anexos_indices(item.get("anexos_indices")):
                if 0 <= ai < n_anexos:
                    mapa[dem_idx].add(ai)

        if not any(mapa.values()):
            for ai, dem_idx in vinculos_explicitos.items():
                mapa[dem_idx].add(ai)

        if n_dem == 1 and n_anexos and not any(mapa.values()):
            mapa[0] = set(range(n_anexos))

        return mapa

    def _salvar_anexos_sessao(
        self,
        session: ChatSession,
        arquivos: list,
        *,
        texto_contexto: str = "",
        rascunho: list[Any] | None = None,
        indices_demanda: list[int | None] | None = None,
    ) -> int:
        rasc = rascunho if rascunho is not None else list(session.demandas_rascunho or [])
        indice_inferido = self._inferir_indice_demanda_pelo_texto(texto_contexto, rasc)
        from core.services.anexo_validacao_service import (
            coletar_nomes_anexos_sessao,
            normalizar_nome_arquivo,
            validar_lote_nomes_arquivo,
        )

        nomes_sessao = coletar_nomes_anexos_sessao(session)
        nomes_novos = [getattr(arq, "name", None) or "anexo" for arq in arquivos]
        validar_lote_nomes_arquivo(nomes_sessao, nomes_novos)
        salvos = 0
        for i, arq in enumerate(arquivos):
            nome = getattr(arq, "name", None) or "anexo"
            nomes_sessao.add(normalizar_nome_arquivo(nome))
            indice: int | None = indice_inferido
            if indices_demanda and i < len(indices_demanda):
                expl = indices_demanda[i]
                if expl is not None:
                    indice = expl
            ChatSessaoAnexo.objects.create(
                session=session,
                arquivo=arq,
                descricao=str(nome)[:200],
                indice_demanda=indice,
            )
            salvos += 1
        return salvos

    @classmethod
    def _copiar_anexos_sessao_para_demandas(
        cls,
        session: ChatSession,
        demandas: list[Demanda],
        *,
        rascunho_items: list[Any] | None = None,
    ) -> None:
        from django.core.files.base import ContentFile

        anexos_sessao = list(session.anexos_sessao.order_by("criado_em"))
        if not anexos_sessao or not demandas:
            return

        rascunho = rascunho_items if rascunho_items is not None else list(session.demandas_rascunho or [])
        rascunho_completo = list(session.demandas_rascunho or rascunho)

        indice_origem_para_demanda: dict[int, int] = {}
        for dem_idx, item in enumerate(rascunho):
            if not isinstance(item, dict):
                continue
            for orig_idx, orig in enumerate(rascunho_completo):
                if orig is item:
                    indice_origem_para_demanda[orig_idx] = dem_idx
                    break

        mapa: dict[int, set[int]] = {i: set() for i in range(len(demandas))}
        vinculos_explicitos = 0
        for ai, chat_anexo in enumerate(anexos_sessao):
            ind = getattr(chat_anexo, "indice_demanda", None)
            if ind is not None and ind in indice_origem_para_demanda:
                mapa[indice_origem_para_demanda[ind]].add(ai)
                vinculos_explicitos += 1

        if not vinculos_explicitos:
            mapa = cls._mapa_anexos_por_demanda(anexos_sessao, rascunho, demandas)

        if not any(mapa.values()):
            logger.warning(
                "Copiloto: %s anexo(s) na sessão sem vínculo explícito a %s demanda(s); "
                "não replicados em todas as demandas.",
                len(anexos_sessao),
                len(demandas),
            )
            return

        for dem_idx, anexo_idxs in mapa.items():
            if dem_idx >= len(demandas):
                continue
            demanda = demandas[dem_idx]
            for ai in sorted(anexo_idxs):
                if ai >= len(anexos_sessao):
                    continue
                chat_anexo = anexos_sessao[ai]
                chat_anexo.arquivo.open("rb")
                try:
                    conteudo = chat_anexo.arquivo.read()
                finally:
                    chat_anexo.arquivo.close()
                nome = Path(chat_anexo.arquivo.name).name
                anexo = Anexo(demanda=demanda, descricao=chat_anexo.descricao)
                anexo.arquivo.save(nome, ContentFile(conteudo), save=True)
