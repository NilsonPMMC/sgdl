"""Montagem do texto formal do ofício (corpo em prosa para `Demanda.descricao` e PDF)."""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from core.models_config import ConfiguracaoOficio


def _data_extenso_local() -> str:
    agora = timezone.localtime(timezone.now())
    meses = (
        "janeiro",
        "fevereiro",
        "março",
        "abril",
        "maio",
        "junho",
        "julho",
        "agosto",
        "setembro",
        "outubro",
        "novembro",
        "dezembro",
    )
    return f"{agora.day} de {meses[agora.month - 1]} de {agora.year}"


def montar_texto_oficio(
    *,
    titulo: str,
    relato: str,
    endereco_formatado: str,
    servico_nome: str,
    orgao_nome: str,
    autor_nome: str,
    autor_cargo: str,
    config: ConfiguracaoOficio | None = None,
) -> str:
    """Gera o texto integral do ofício em linguagem formal dirigida à Prefeitura."""
    cfg = config or ConfiguracaoOficio.carregar()
    municipio = (cfg.municipio or "").strip()
    data_linha = _data_extenso_local()

    titulo = (titulo or "Solicitação de serviço público").strip()
    relato = (relato or titulo).strip()
    endereco_formatado = (endereco_formatado or "").strip()
    servico_nome = (servico_nome or "").strip()
    orgao_nome = (orgao_nome or "").strip()

    linhas: list[str] = []
    if municipio:
        linhas.append(f"{municipio}, {data_linha}.")
    else:
        linhas.append(f"{data_linha}.")
    linhas.append("")
    linhas.append(cfg.destinatario_tratamento.strip() + ",")
    linhas.append(cfg.destinatario_nome.strip() + ",")
    if cfg.destinatario_cargo:
        linhas.append(cfg.destinatario_cargo.strip())
    linhas.append("")

    abertura_padrao = (
        "Venho, respeitosamente, solicitar a Vossa Excelência que determine "
        "à administração municipal, por meio do órgão competente, "
        "as providências necessárias quanto ao seguinte:"
    )
    linhas.append(abertura_padrao)
    linhas.append("")

    linhas.append(f"Assunto: {titulo}")
    if servico_nome:
        linhas.append(f"Serviço solicitado (Carta de Serviços): {servico_nome}")
    if orgao_nome:
        linhas.append(f"Órgão responsável: {orgao_nome}")
    if endereco_formatado:
        linhas.append(f"Localização: {endereco_formatado}")
    linhas.append("")

    linhas.append("Descrição da solicitação:")
    linhas.append(relato)
    linhas.append("")

    linhas.append("Nestes termos, pede deferimento.")
    linhas.append("")
    if municipio:
        linhas.append(f"{municipio}, {data_linha}.")
    else:
        linhas.append(f"{data_linha}.")
    linhas.append("")
    linhas.append(autor_nome.strip() or "Vereador")
    if autor_cargo:
        linhas.append(autor_cargo.strip())

    return "\n".join(linhas).strip()


def montar_texto_oficio_lote(
    *,
    itens: list[dict[str, Any]],
    endereco_formatado: str,
    autor_nome: str,
    autor_cargo: str,
    config: ConfiguracaoOficio | None = None,
) -> str:
    """Ofício único listando vários serviços no mesmo endereço."""
    cfg = config or ConfiguracaoOficio.carregar()
    municipio = (cfg.municipio or "").strip()
    data_linha = _data_extenso_local()

    linhas: list[str] = []
    if municipio:
        linhas.append(f"{municipio}, {data_linha}.")
    else:
        linhas.append(f"{data_linha}.")
    linhas.append("")
    linhas.append(cfg.destinatario_tratamento.strip() + ",")
    linhas.append(cfg.destinatario_nome.strip() + ",")
    if cfg.destinatario_cargo:
        linhas.append(cfg.destinatario_cargo.strip())
    linhas.append("")
    linhas.append(
        f"Venho, respeitosamente, solicitar a Vossa Excelência que determine à "
        f"{cfg.orgao_destinatario}, por meio dos órgãos competentes, o encaminhamento "
        f"das seguintes demandas de serviços públicos:"
    )
    linhas.append("")

    if endereco_formatado:
        linhas.append(f"Local comum das solicitações: {endereco_formatado}")
        linhas.append("")

    for i, item in enumerate(itens, start=1):
        titulo = (item.get("titulo") or f"Solicitação {i}").strip()
        relato = (item.get("relato") or item.get("descricao") or titulo).strip()
        servico = (item.get("servico_nome") or "").strip()
        orgao = (item.get("orgao_nome") or "").strip()
        linhas.append(f"{i}. {titulo}")
        if servico:
            linhas.append(f"   Serviço (Carta de Serviços): {servico}")
        if orgao:
            linhas.append(f"   Órgão: {orgao}")
        linhas.append(f"   {relato}")
        linhas.append("")

    linhas.append("Nestes termos, pede deferimento.")
    linhas.append("")
    if municipio:
        linhas.append(f"{municipio}, {data_linha}.")
    else:
        linhas.append(f"{data_linha}.")
    linhas.append("")
    linhas.append(autor_nome.strip() or "Vereador")
    if autor_cargo:
        linhas.append(autor_cargo.strip())

    return "\n".join(linhas).strip()


def montar_texto_resposta_cidadao(
    *,
    titulo_demanda: str,
    relato_demanda: str,
    parecer_operacional: str,
    resposta_protocolo: str,
    texto_resposta: str,
    protocolo_executivo: str | None,
    autor_nome: str,
    autor_cargo: str,
    orgao_nome: str,
    config: ConfiguracaoOficio | None = None,
) -> str:
    """Carta de devolutiva ao cidadão após retorno da Administração."""
    cfg = config or ConfiguracaoOficio.carregar()
    municipio = (cfg.municipio or "").strip()
    data_linha = _data_extenso_local()

    linhas = []
    if municipio:
        linhas.append(f"{municipio}, {data_linha}.")
    else:
        linhas.append(f"{data_linha}.")
    linhas.extend(
        [
            "",
            "Prezado(a) cidadão(ã),",
            "",
            (
                f"Em resposta à solicitação registrada pela {cfg.instituicao_nome} "
                f"sobre «{(titulo_demanda or 'serviço público').strip()}», "
                "informamos o retorno da Administração Municipal:"
            ),
            "",
        ]
    )
    if protocolo_executivo:
        linhas.append(f"Protocolo de acompanhamento: {protocolo_executivo}.")
        linhas.append("")

    if relato_demanda.strip():
        linhas.extend(["Solicitação original:", relato_demanda.strip(), ""])

    if parecer_operacional.strip():
        linhas.extend(["Parecer da secretaria executora:", parecer_operacional.strip(), ""])

    if resposta_protocolo.strip():
        linhas.extend(["Encaminhamento do Protocolo Legislativo:", resposta_protocolo.strip(), ""])

    corpo = (texto_resposta or "").strip()
    if corpo:
        linhas.extend(["Resposta ao cidadão:", corpo, ""])
    else:
        linhas.append(
            "O serviço foi tratado pela secretaria competente conforme parecer acima."
        )
        linhas.append("")

    linhas.append("Permanecemos à disposição para esclarecimentos.")
    linhas.append("")
    linhas.append("Atenciosamente,")
    linhas.append("")
    linhas.append(autor_nome.strip() or "Vereador")
    if autor_cargo:
        linhas.append(autor_cargo.strip())
    if orgao_nome.strip():
        linhas.append(orgao_nome.strip())

    return "\n".join(linhas).strip()
