"""
Construção de texto RAG e campos estruturados para ServicoOtimizado (v3).

Evita templates genéricos idênticos que colapsam embeddings.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class CartaRagPacote:
    titulo_display: str
    intencao_servico: str
    problemas_resolve: list[str]
    texto_rag_otimizado: str
    palavras_chave: list[str]
    categoria: str


def construir_pacote_rag(
    titulo: str,
    descricao: str,
    sinapse_servico_id: int | None = None,
) -> CartaRagPacote:
    """Gera pacote completo para persistência e embedding."""
    titulo_limpo = _limpar_html(titulo) or "Serviço público"
    descricao_limpa = _limpar_html(descricao)
    categoria = _detectar_categoria(titulo_limpo, descricao_limpa)

    if categoria == "pavimentacao":
        return _pacote_pavimentacao(titulo_limpo, descricao_limpa, sinapse_servico_id)
    if categoria == "iluminacao":
        return _pacote_iluminacao(titulo_limpo, descricao_limpa)
    if categoria == "limpeza":
        return _pacote_limpeza(titulo_limpo, descricao_limpa)
    if categoria == "saneamento":
        return _pacote_saneamento(titulo_limpo, descricao_limpa)
    if categoria == "animais":
        return _pacote_animais(titulo_limpo, descricao_limpa)
    if categoria == "licenciamento":
        return _pacote_licenciamento(titulo_limpo, descricao_limpa)
    if categoria == "vegetacao":
        return _pacote_vegetacao(titulo_limpo, descricao_limpa)
    if categoria == "saude":
        return _pacote_saude(titulo_limpo, descricao_limpa)
    if categoria == "transporte":
        return _pacote_transporte(titulo_limpo, descricao_limpa)
    if categoria == "transito":
        return _pacote_transito(titulo_limpo, descricao_limpa)
    if categoria == "seguranca":
        return _pacote_seguranca(titulo_limpo, descricao_limpa)
    if categoria == "procon":
        return _pacote_procon(titulo_limpo, descricao_limpa)
    if categoria == "tributo":
        return _pacote_tributo(titulo_limpo, descricao_limpa)
    return _pacote_generico(titulo_limpo, descricao_limpa, sinapse_servico_id)


def _detectar_categoria(titulo: str, descricao: str) -> str:
    t = f"{titulo} {descricao}".lower()
    if re.search(r"\b(tapa[\s-]?buraco|buraco|cratera|pavimenta|asfalto|pavimento)\b", t):
        return "pavimentacao"
    if re.search(r"\b(ilumina|lâmpada|lampada|poste|luz)\b", t) and (
        "pública" in t or "publica" in t or "poste" in t
    ):
        return "iluminacao"
    if re.search(
        r"\b(coleta de lixo|lixo|entulho|limpeza urbana|capina|varri[cç][aã]o|varredura|sujeira)\b",
        t,
    ):
        return "limpeza"
    if re.search(r"\b(água|agua|esgoto|semae|saneamento|vazamento)\b", t):
        return "saneamento"
    if re.search(r"\b(animal|cão|cao|cachorro|gato|pet|recolhimento)\b", t):
        return "animais"
    # Mobilidade antes de licenciamento — evita colapso de embeddings entre alvarás de modalidades distintas
    if re.search(
        r"\b(táxi|taxi|taxista|ônibus|onibus|transporte escolar|transporte remunerado|"
        r"transporte de carga|motorista auxiliar|permissão de táxi|permissao de taxi)\b",
        t,
    ):
        return "transporte"
    if re.search(r"\b(alvará|alvara|licença|licenca|autorização|autorizacao)\b", t):
        return "licenciamento"
    if re.search(r"\b(poda|árvore|arvore|arbor|galho|queda de árvore|queda de arvore)\b", t):
        return "vegetacao"
    if re.search(
        r"\b(saúde|saude|consulta médica|consulta medica|vacina|ubs|hospital|exame|ambulatório)\b",
        t,
    ):
        return "saude"
    # Trânsito antes de tributo — evita confundir «guia» de pagamento com guia de calçada
    if re.search(
        r"\b(trânsito|transito|sinaliza|lombada|radar|semáforo|semaforo|"
        r"multas de trânsito|multa de trânsito|liberação de veículo|liberacao de veiculo)\b",
        t,
    ):
        return "transito"
    if re.search(
        r"\b(proibido estacionar|pintura de guia|rebaixamento de guia|faixa de pedestre|"
        r"caçamba|cacamba|estacionamento irregular|remoção de veículo)\b",
        t,
    ):
        return "transito"
    if re.search(
        r"\b(ronda|guarda civil|guarda municipal|\bgcm\b|patrimônio|patrimonio|"
        r"boletim de ocorrência|boletim de ocorrencia|segurança municipal|seguranca municipal)\b",
        t,
    ):
        return "seguranca"
    if re.search(r"\bprocon\b", t) or re.search(
        r"\b(proteção ao consumidor|protecao ao consumidor|defesa do consumidor|"
        r"direito do consumidor|reclamação contra loja|reclamacao contra loja|"
        r"atendimento ao consumidor)\b",
        t,
    ):
        return "procon"
    if re.search(r"\b(iptu|iss|itbi|tributo|imposto|taxa|cadastro ccm|nota fiscal)\b", t):
        return "tributo"
    return "generico"


def _pacote_pavimentacao(titulo: str, descricao: str, sid: int | None) -> CartaRagPacote:
    problemas = [
        "Buraco ou cratera na rua, avenida ou estrada",
        "Asfalto quebrado com risco de acidente ou dano ao veículo",
        "Via esburacada com carros precisando desviar",
        "Pavimento danificado após chuva ou tráfego pesado",
    ]
    intencao = (
        f"O serviço «{titulo}» atende solicitações de reparo e manutenção de vias "
        "com buracos, crateras ou pavimento danificado no município."
    )
    texto = _montar_texto_rag(
        titulo=titulo,
        intencao=intencao,
        problemas=problemas,
        descricao=descricao,
        extras_solicitacao=[
            "Tapa-buraco na minha rua",
            "Reparo urgente por risco de acidente",
            "Cratera perigosa na via",
        ],
        palavras=[
            titulo.lower(),
            "buraco",
            "cratera",
            "tapa buraco",
            "reparo de rua",
            "asfalto quebrado",
            "via esburacada",
            "pavimentação",
            "acidente",
            "manutenção viária",
        ],
        sinapse_id=sid,
    )
    return CartaRagPacote(titulo, intencao, problemas, texto, _uniq_palavras(texto), "pavimentacao")


def _pacote_iluminacao(titulo: str, descricao: str) -> CartaRagPacote:
    problemas = [
        "Poste ou lâmpada apagada na rua",
        "Local escuro com risco à segurança",
        "Iluminação pública defeituosa ou piscando",
    ]
    intencao = f"O serviço «{titulo}» trata de iluminação pública e conserto de pontos apagados."
    texto = _montar_texto_rag(
        titulo, intencao, problemas, descricao,
        extras_solicitacao=["Lâmpada queimada", "Poste sem luz"],
        palavras=[titulo.lower(), "iluminação", "luz", "poste", "lâmpada", "rua escura"],
    )
    return CartaRagPacote(titulo, intencao, problemas, texto, _uniq_palavras(texto), "iluminacao")


def _pacote_limpeza(titulo: str, descricao: str) -> CartaRagPacote:
    titulo_l = titulo.lower()
    eh_varricao = "varri" in titulo_l or "varredura" in titulo_l

    if eh_varricao:
        problemas = [
            "Rua ou calçada suja com sujeira, poeira e restos sem varrição",
            "Falta de varrição na rua do bairro",
            "Acúmulo de lixo e sujeira na via pública",
            "Calçada ou rua precisando de limpeza e varrição",
        ]
        intencao = (
            f"O serviço «{titulo}» atende pedidos de limpeza de vias públicas: "
            "varrição de ruas, remoção de sujeira e manutenção da limpeza urbana."
        )
        extras = [
            "A rua está suja e precisa de varrição",
            "Sujeira acumulada na rua",
            "Falta varrição na minha rua",
        ]
        palavras = [
            titulo.lower(),
            "varrição",
            "varricao",
            "varredura",
            "sujeira",
            "rua suja",
            "limpeza urbana",
            "limpeza de rua",
            "lixo na rua",
            "calçada suja",
            "via pública",
            "zeladoria",
        ]
    else:
        problemas = [
            "Lixo ou entulho não coletado",
            "Resíduos acumulados em via ou terreno",
            "Rua suja por falta de coleta ou limpeza",
            "Necessidade de coleta especial ou limpeza",
        ]
        intencao = f"O serviço «{titulo}» trata de coleta, limpeza urbana e remoção de resíduos nas vias."
        extras = ["Coleta atrasada", "Retirada de entulho", "Sujeira na rua"]
        palavras = [
            titulo.lower(),
            "lixo",
            "coleta",
            "entulho",
            "limpeza",
            "resíduo",
            "sujeira",
            "rua suja",
        ]

    texto = _montar_texto_rag(
        titulo, intencao, problemas, descricao,
        extras_solicitacao=extras,
        palavras=palavras,
    )
    return CartaRagPacote(titulo, intencao, problemas, texto, _uniq_palavras(palavras), "limpeza")


def _pacote_saneamento(titulo: str, descricao: str) -> CartaRagPacote:
    problemas = [
        "Falta de água ou vazamento",
        "Esgoto entupido ou transbordando",
        "Problemas com conta ou ligação de água/esgoto",
    ]
    intencao = f"O serviço «{titulo}» trata de abastecimento, esgoto e saneamento."
    texto = _montar_texto_rag(
        titulo, intencao, problemas, descricao,
        extras_solicitacao=["Vazamento", "Segunda via de conta"],
        palavras=[titulo.lower(), "água", "esgoto", "vazamento", "semae", "saneamento"],
    )
    return CartaRagPacote(titulo, intencao, problemas, texto, _uniq_palavras(texto), "saneamento")


def _pacote_animais(titulo: str, descricao: str) -> CartaRagPacote:
    problemas = [
        "Animal abandonado, ferido ou em risco na via",
        "Necessidade de recolhimento ou castração",
        "Denúncia de maus-tratos",
    ]
    intencao = f"O serviço «{titulo}» trata de proteção animal e controle de animais em via pública."
    texto = _montar_texto_rag(
        titulo, intencao, problemas, descricao,
        extras_solicitacao=["Animal na rua", "Socorro a pet ferido"],
        palavras=[titulo.lower(), "animal", "cachorro", "gato", "recolhimento", "castração"],
    )
    return CartaRagPacote(titulo, intencao, problemas, texto, _uniq_palavras(texto), "animais")


def _pacote_licenciamento(titulo: str, descricao: str) -> CartaRagPacote:
    problemas = [
        "Abrir ou regularizar negócio ou atividade",
        "Renovar alvará ou licença",
        "Obter autorização para funcionamento ou evento",
    ]
    intencao = f"O serviço «{titulo}» trata de licenças, alvarás e autorizações administrativas."
    palavras = [titulo.lower(), "alvará", "alvara", "licença", "licenca", "autorização", "negócio"]
    texto = _montar_texto_rag(
        titulo, intencao, problemas, descricao,
        extras_solicitacao=["Novo alvará", "Renovação de licença"],
        palavras=palavras,
    )
    return CartaRagPacote(titulo, intencao, problemas, texto, _uniq_palavras(palavras), "licenciamento")


def _pacote_vegetacao(titulo: str, descricao: str) -> CartaRagPacote:
    problemas = [
        "Árvore com risco de queda ou galhos perigosos",
        "Necessidade de poda ou remoção de árvore",
        "Vegetação alta atrapalhando via ou calçada",
    ]
    intencao = f"O serviço «{titulo}» trata de poda, árvores e manejo de vegetação urbana."
    palavras = [titulo.lower(), "poda", "árvore", "arvore", "galho", "vegetação", "capina", "queda"]
    texto = _montar_texto_rag(
        titulo, intencao, problemas, descricao,
        extras_solicitacao=["Poda de árvore", "Árvore com risco de cair"],
        palavras=palavras,
    )
    return CartaRagPacote(titulo, intencao, problemas, texto, _uniq_palavras(palavras), "vegetacao")


def _pacote_saude(titulo: str, descricao: str) -> CartaRagPacote:
    problemas = [
        "Necessidade de atendimento ou consulta de saúde",
        "Vacinação ou exames",
        "Orientação sobre serviços de saúde municipal",
    ]
    intencao = f"O serviço «{titulo}» trata de saúde pública e atendimento ao cidadão."
    palavras = [titulo.lower(), "saúde", "saude", "consulta", "vacina", "exame", "ubs", "atendimento"]
    texto = _montar_texto_rag(
        titulo, intencao, problemas, descricao,
        extras_solicitacao=["Agendar consulta", "Vacinação"],
        palavras=palavras,
    )
    return CartaRagPacote(titulo, intencao, problemas, texto, _uniq_palavras(palavras), "saude")


def _subtipo_transporte(titulo: str) -> str:
    t = titulo.lower()
    if re.search(r"\btáxi\b|\btaxi\b", t):
        return "taxi"
    if "escolar" in t:
        return "escolar"
    if "carga" in t or "remunerado" in t or "estacionamento" in t:
        return "carga"
    if re.search(r"\bônibus\b|\bonibus\b", t):
        return "onibus"
    return "geral"


def _pacote_transporte(titulo: str, descricao: str) -> CartaRagPacote:
    sub = _subtipo_transporte(titulo)
    if sub == "taxi":
        problemas = [
            "Renovação, emissão ou regularização de alvará de táxi / taxista",
            "Permissão, motorista auxiliar ou substituição de veículo de táxi",
            "Cadastro ou alteração de dados do taxista na Secretaria de Mobilidade",
        ]
        intencao = (
            f"O serviço «{titulo}» é da modalidade TÁXI: alvará, permissão e cadastro "
            "de taxistas e veículos de táxi — não confundir com transporte escolar ou de carga."
        )
        palavras = [
            titulo.lower(),
            "táxi", "taxi", "taxista", "taxistas", "alvará", "alvara",
            "renovação", "renovacao", "permissão", "permissao",
            "motorista auxiliar", "mobilidade", "semob",
        ]
        extras = ["Alvará para taxistas", "Renovar alvará do meu táxi", "Licença de taxista"]
    elif sub == "escolar":
        problemas = [
            "Renovação ou suspensão de alvará de transporte escolar",
            "Cadastro de veículo ou motorista de transporte escolar",
        ]
        intencao = (
            f"O serviço «{titulo}» é de TRANSPORTE ESCOLAR — alvará e cadastro de vans/ônibus escolares, "
            "não é táxi nem transporte de carga."
        )
        palavras = [titulo.lower(), "transporte escolar", "escolar", "alvará", "alvara", "van escolar", "semob"]
        extras = ["Alvará transporte escolar", "Renovar alvará escolar"]
    elif sub == "carga":
        problemas = [
            "Renovação de alvará de estacionamento para transporte remunerado de carga",
            "Cadastro de veículo de carga na mobilidade",
        ]
        intencao = (
            f"O serviço «{titulo}» é de TRANSPORTE REMUNERADO DE CARGA — alvará de estacionamento "
            "para caminhões e veículos de carga, não é táxi nem transporte escolar."
        )
        palavras = [
            titulo.lower(), "transporte de carga", "carga", "remunerado",
            "estacionamento", "alvará", "alvara", "caminhão", "caminhao", "semob",
        ]
        extras = ["Alvará de estacionamento para carga", "Renovar alvará de caminhão"]
    else:
        problemas = [
            "Problemas com transporte público ou linhas",
            "Licença ou cadastro de transporte na mobilidade",
            "Alteração de itinerário ou horário",
        ]
        intencao = f"O serviço «{titulo}» trata de transporte e mobilidade no município."
        palavras = [titulo.lower(), "ônibus", "onibus", "transporte", "mobilidade", "linha", "horário"]
        extras = ["Problema no ônibus", "Cartão de transporte"]

    texto = _montar_texto_rag(
        titulo, intencao, problemas, descricao,
        extras_solicitacao=extras,
        palavras=palavras,
    )
    return CartaRagPacote(titulo, intencao, problemas, texto, _uniq_palavras(palavras), "transporte")


def _subtipo_transito(titulo: str) -> str:
    t = titulo.lower()
    if "sinaliz" in t:
        return "sinalizacao"
    if "lombada" in t:
        return "lombada"
    if "multa" in t:
        return "multas"
    if "caçamba" in t or "cacamba" in t or "carga" in t or "descarga" in t:
        return "carga_descarga"
    if "estacionamento" in t or "cartão" in t or "cartao" in t:
        return "estacionamento"
    if "rebaixamento" in t and "guia" in t:
        return "guia"
    return "geral"


def _pacote_transito(titulo: str, descricao: str) -> CartaRagPacote:
    sub = _subtipo_transito(titulo)
    if sub == "sinalizacao":
        problemas = [
            "Implantação ou alteração de placa de proibido estacionar e regulamentação de vagas",
            "Pintura de guia, faixa amarela ou sinalização horizontal na via",
            "Nova sinalização vertical, horizontal ou semafórica em rua ou avenida",
            "Alteração de sinalização existente por demanda do bairro ou comerciantes",
        ]
        intencao = (
            f"O serviço «{titulo}» trata de SINALIZAÇÃO DE TRÂNSITO: placas, pintura de guia, "
            "faixas e demais marcas viárias — não é reserva de parque, cultura ou tributo."
        )
        palavras = [
            titulo.lower(),
            "trânsito", "transito", "sinalização", "sinalizacao", "sinaliza",
            "proibido estacionar", "estacionar", "pintura de guia", "guia",
            "faixa", "placa", "horizontal", "vertical", "semáforo", "semaforo",
            "via pública", "rua", "avenida", "semob", "mobilidade",
        ]
        extras = [
            "Proibido estacionar e pintura de guia na minha rua",
            "Colocar placa de proibido estacionar",
            "Pintar guia amarela na via",
        ]
    elif sub == "lombada":
        problemas = [
            "Pedido de implantação de lombada ou redutor de velocidade",
            "Via com excesso de velocidade próximo a escola ou comércio",
        ]
        intencao = f"O serviço «{titulo}» trata de implantação de lombadas e redutores de velocidade."
        palavras = [titulo.lower(), "lombada", "redutor", "velocidade", "trânsito", "transito", "via"]
        extras = ["Lombada na rua", "Redutor de velocidade"]
    elif sub == "multas":
        problemas = [
            "Consulta, defesa ou recurso de multa de trânsito municipal",
            "Recurso de autuação ou segunda instância",
        ]
        intencao = f"O serviço «{titulo}» trata de multas e recursos de infrações de trânsito."
        palavras = [titulo.lower(), "multa", "trânsito", "transito", "recurso", "defesa", "autuação"]
        extras = ["Recurso de multa", "Consultar multa de trânsito"]
    elif sub == "carga_descarga":
        problemas = [
            "Autorização para colocação de caçamba ou carga/descarga em via",
        ]
        intencao = f"O serviço «{titulo}» trata de autorizações de carga, descarga e caçambas na via."
        palavras = [titulo.lower(), "caçamba", "cacamba", "carga", "descarga", "trânsito", "transito"]
        extras = ["Autorização para caçamba", "Carga e descarga na rua"]
    elif sub == "guia":
        problemas = [
            "Autorização para rebaixamento de guia de calçada",
            "Acesso de veículo à garagem com alteração de guia",
        ]
        intencao = f"O serviço «{titulo}» trata de rebaixamento de guia de calçada (trânsito/vias)."
        palavras = [titulo.lower(), "rebaixamento", "guia", "calçada", "trânsito", "transito"]
        extras = ["Rebaixar guia da calçada", "Acesso à garagem"]
    else:
        problemas = [
            "Demanda relacionada a trânsito, vias e mobilidade urbana",
            "Autorização ou solicitação junto à Secretaria de Mobilidade",
        ]
        intencao = f"O serviço «{titulo}» trata de trânsito e mobilidade no município."
        palavras = [titulo.lower(), "trânsito", "transito", "via", "mobilidade", "semob"]
        extras = [f"Solicitação sobre {titulo.lower()}"]

    texto = _montar_texto_rag(
        titulo, intencao, problemas, descricao,
        extras_solicitacao=extras,
        palavras=palavras,
    )
    return CartaRagPacote(titulo, intencao, problemas, texto, _uniq_palavras(palavras), "transito")


def _subtipo_seguranca(titulo: str) -> str:
    t = titulo.lower()
    if "ronda" in t:
        return "ronda"
    if "boletim" in t or "ocorrência" in t or "ocorrencia" in t:
        return "boletim"
    return "geral"


def _pacote_seguranca(titulo: str, descricao: str) -> CartaRagPacote:
    sub = _subtipo_seguranca(titulo)
    if sub == "ronda":
        problemas = [
            "Intensificação de rondas da Guarda Civil em praças, patrimônios e entorno de escolas",
            "Maior presença da GCM próximo a instituições de ensino, colégios e creches",
            "Ronda em patrimônio público municipal (praças, prédios, entorno de equipamentos públicos)",
            "Solicitação de estudos ou reforço de rondas em bairro específico",
        ]
        intencao = (
            f"O serviço «{titulo}» trata de RONDAS da Guarda Civil Municipal em patrimônios públicos "
            "(praças, equipamentos públicos e entorno de escolas) — não é transporte escolar nem vaga em creche."
        )
        palavras = [
            titulo.lower(),
            "ronda", "rondas", "guarda civil", "gcm", "patrimônio", "patrimonio",
            "praça", "praca", "escola", "escolar", "ensino", "colégio", "colegio",
            "intensificação", "intensificacao", "segurança", "seguranca", "bairro",
        ]
        extras = [
            "Intensificar rondas escolares no bairro",
            "Mais ronda da GCM perto da escola",
            "Reforço de ronda em patrimônio público",
        ]
    else:
        problemas = [
            "Demanda relacionada à Guarda Civil Municipal ou segurança pública municipal",
        ]
        intencao = f"O serviço «{titulo}» trata de segurança municipal e Guarda Civil."
        palavras = [titulo.lower(), "guarda civil", "gcm", "segurança", "seguranca", "municipal"]
        extras = [f"Solicitação sobre {titulo.lower()}"]

    texto = _montar_texto_rag(
        titulo, intencao, problemas, descricao,
        extras_solicitacao=extras,
        palavras=palavras,
    )
    return CartaRagPacote(titulo, intencao, problemas, texto, _uniq_palavras(palavras), "seguranca")


def _subtipo_procon(titulo: str) -> str:
    t = titulo.lower()
    if "online" in t:
        return "online"
    if "presencial" in t:
        return "presencial"
    if "certid" in t:
        return "certidao"
    if "fiscaliz" in t:
        return "fiscalizacao"
    if "cadastro" in t and "reclama" in t:
        return "reclamacoes"
    return "geral"


def _pacote_procon(titulo: str, descricao: str) -> CartaRagPacote:
    sub = _subtipo_procon(titulo)
    if sub == "online":
        problemas = [
            "Atendimento de proteção ao consumidor pela internet (PROCON municipal)",
            "Reclamação contra estabelecimento comercial ou prestador de serviço",
            "Orientação sobre direitos do consumidor sem ir presencialmente",
        ]
        intencao = (
            f"O serviço «{titulo}» é o PROCON municipal ONLINE — defesa do consumidor, "
            "reclamações e orientação. Não é assistência social nem proteção à família."
        )
        extras = ["Proteção ao consumidor online", "Reclamação no PROCON pela internet"]
    elif sub == "presencial":
        problemas = [
            "Atendimento presencial de proteção ao consumidor no PROCON",
            "Registrar reclamação contra comércio ou serviço presencialmente",
        ]
        intencao = (
            f"O serviço «{titulo}» é atendimento PRESENCIAL do PROCON municipal — "
            "defesa do consumidor. Não confundir com programas de assistência social."
        )
        extras = ["Ir ao PROCON", "Atendimento presencial consumidor"]
    elif sub == "certidao":
        problemas = [
            "Emissão de certidão relacionada a direitos do consumidor ou PROCON",
        ]
        intencao = f"O serviço «{titulo}» emite certidões do PROCON municipal."
        extras = ["Certidão PROCON", "Certidão negativa consumidor"]
    elif sub == "fiscalizacao":
        problemas = [
            "Denúncia ou solicitação de fiscalização PROCON em estabelecimento",
        ]
        intencao = f"O serviço «{titulo}» trata de fiscalização do PROCON municipal."
        extras = ["Fiscalização PROCON", "Denúncia comercial"]
    else:
        problemas = [
            "Proteção e defesa do consumidor perante fornecedores e comércio",
            "Reclamação, orientação ou cadastro no PROCON municipal",
            "Problemas com produto, serviço ou estabelecimento comercial",
        ]
        intencao = (
            f"O serviço «{titulo}» é do PROCON — proteção ao consumidor municipal. "
            "Não é «Proteção e Atendimento à Família» nem assistência social."
        )
        extras = ["Proteção ao consumidor", "Defesa do consumidor", "Reclamação PROCON"]

    palavras = [
        titulo.lower(),
        "procon", "consumidor", "proteção ao consumidor", "protecao ao consumidor",
        "defesa do consumidor", "reclamação", "reclamacao", "direito do consumidor",
        "loja", "comércio", "comercio", "fornecedor", "produto", "serviço",
        "nota fiscal paulista", "cadastro estadual reclamações",
    ]
    texto = _montar_texto_rag(
        titulo, intencao, problemas, descricao,
        extras_solicitacao=extras,
        palavras=palavras,
    )
    return CartaRagPacote(titulo, intencao, problemas, texto, _uniq_palavras(palavras), "procon")


def _pacote_tributo(titulo: str, descricao: str) -> CartaRagPacote:
    problemas = [
        "Consulta ou emissão de documento fiscal/tributário",
        "Parcelamento ou segunda via de tributo",
        "Dúvidas sobre IPTU, ISS ou taxas municipais",
    ]
    intencao = f"O serviço «{titulo}» trata de tributos, taxas e obrigações fiscais municipais."
    palavras = [titulo.lower(), "iptu", "iss", "itbi", "taxa", "tributo", "guia", "parcelamento", "certidão"]
    texto = _montar_texto_rag(
        titulo, intencao, problemas, descricao,
        extras_solicitacao=["Segunda via", "Parcelar débito"],
        palavras=palavras,
    )
    return CartaRagPacote(titulo, intencao, problemas, texto, _uniq_palavras(palavras), "tributo")


def _pacote_generico(titulo: str, descricao: str, sid: int | None) -> CartaRagPacote:
    frases = _extrair_frases_descricao(descricao, max_frases=4)
    problemas = frases if frases else [f"Solicitação ou consulta sobre: {titulo}"]
    assunto = titulo.split(":", 1)[-1].strip() if ":" in titulo else titulo
    intencao = (
        f"O serviço «{titulo}» é o canal municipal para pedidos sobre {assunto}. "
        f"Use este serviço quando a demanda for especificamente sobre «{titulo}»."
    )
    palavras_titulo = [
        p for p in re.findall(r"\w{3,}", f"{titulo} {descricao}".lower())
        if p not in _STOPWORDS
    ]
    # Título costuma ser o discriminador mais forte no long tail
    partes_titulo = re.findall(r"\w{3,}", titulo.lower())
    palavras = _uniq_palavras(
        partes_titulo + palavras_titulo + [assunto.lower(), "serviço público", "município", "solicitação"]
    )
    extras = [
        f"Quero solicitar {assunto.lower()}",
        f"Preciso de {assunto.lower()}",
        f"Informações sobre {titulo.lower()}",
    ]
    texto = _montar_texto_rag(
        titulo,
        intencao,
        problemas,
        descricao[:500],
        extras_solicitacao=extras,
        palavras=palavras,
        sinapse_id=sid,
    )
    return CartaRagPacote(titulo, intencao, problemas, texto, palavras, "generico")


def _montar_texto_rag(
    titulo: str,
    intencao: str,
    problemas: list[str],
    descricao: str,
    extras_solicitacao: list[str],
    palavras: list[str],
    sinapse_id: int | None = None,
) -> str:
    linhas = [titulo.upper(), "", f"Intenção: {intencao}", "", "Situações que este serviço atende:"]
    for p in problemas:
        linhas.append(f"- {p}")
    if descricao.strip():
        linhas.extend(["", "Detalhes:", descricao.strip()[:350]])
    if extras_solicitacao:
        linhas.extend(["", "Exemplos de como o cidadão pede:"])
        for e in extras_solicitacao:
            linhas.append(f"- {e}")
    if sinapse_id:
        linhas.append(f"\nReferência Sinapse: {sinapse_id}")
    linhas.append(f"\nPalavras-chave: {', '.join(_uniq_palavras(palavras))}")
    return "\n".join(linhas)


def _extrair_frases_descricao(descricao: str, max_frases: int = 3) -> list[str]:
    if not descricao:
        return []
    partes = re.split(r"[.!?]\s+", descricao)
    frases = [p.strip() for p in partes if len(p.strip()) > 25]
    return frases[:max_frases]


def _limpar_html(texto: str) -> str:
    if not texto:
        return ""
    texto_limpo = html.unescape(texto)
    texto_limpo = re.sub(r"<[^>]+>", "", texto_limpo)
    texto_limpo = re.sub(r"\s+", " ", texto_limpo).strip()
    return texto_limpo


def _uniq_palavras(palavras: list[str]) -> list[str]:
    vistos: set[str] = set()
    out: list[str] = []
    for p in palavras:
        k = p.strip().lower()
        if k and k not in vistos and len(k) >= 2:
            vistos.add(k)
            out.append(k)
    return out[:20]


_STOPWORDS = frozenset(
    {"de", "da", "do", "em", "na", "no", "para", "com", "por", "e", "o", "a", "os", "as", "um", "uma"}
)
