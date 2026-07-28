"""Validação de nomes de arquivo em anexos (B3 — evitar duplicatas por nome)."""

from __future__ import annotations

from pathlib import Path


def normalizar_nome_arquivo(nome: str | None) -> str:
    """Basename case-insensitive para comparação."""
    return Path((nome or "").strip()).name.lower()


def coletar_nomes_anexos_demanda(demanda) -> set[str]:
    from core.models import Anexo

    nomes: set[str] = set()
    for anexo in Anexo.objects.filter(demanda=demanda):
        if anexo.arquivo:
            nomes.add(normalizar_nome_arquivo(Path(anexo.arquivo.name).name))
        if anexo.descricao:
            nomes.add(normalizar_nome_arquivo(anexo.descricao))
    return nomes


def coletar_nomes_anexos_sessao(session) -> set[str]:
    nomes: set[str] = set()
    for anexo in session.anexos_sessao.all():
        nome = (anexo.descricao or "").strip()
        if not nome and anexo.arquivo:
            nome = Path(anexo.arquivo.name).name
        if nome:
            nomes.add(normalizar_nome_arquivo(nome))
    return nomes


def validar_nome_arquivo_novo(nomes_existentes: set[str], nome_arquivo: str) -> None:
    """Rejeita upload quando o basename já existe no conjunto informado."""
    norm = normalizar_nome_arquivo(nome_arquivo)
    if not norm:
        raise ValueError("Nome de arquivo inválido.")
    if norm in nomes_existentes:
        exibicao = Path(nome_arquivo).name or nome_arquivo
        raise ValueError(
            f'Já existe um anexo com o nome «{exibicao}». '
            "Renomeie o arquivo ou remova o anexo anterior."
        )


def validar_lote_nomes_arquivo(
    nomes_existentes: set[str],
    nomes_novos: list[str],
) -> None:
    """Valida um lote de uploads contra existentes e entre si."""
    vistos = set(nomes_existentes)
    for nome in nomes_novos:
        validar_nome_arquivo_novo(vistos, nome)
        vistos.add(normalizar_nome_arquivo(nome))
