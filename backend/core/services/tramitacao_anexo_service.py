"""Anexos em tramitações operacionais (B8)."""

from __future__ import annotations

import logging

from django.core.files.base import ContentFile

from core.models import AnexoTramitacao, Demanda, Tramitacao
from core.services.anexo_validacao_service import validar_lote_nomes_arquivo

logger = logging.getLogger(__name__)

TIPOS_TRAMITACAO_EXCLUIDOS_ANEXOS_REUSO = frozenset(
    {
        "DEVOLUTIVA_PROTOCOLO",
        "CONCLUSAO_FINAL",
        "ENCERRAMENTO_DEVOLUTIVA",
        "CIENCIA_VEREADOR",
    }
)


def _demanda_ids_processo(demanda: Demanda) -> list[int]:
    """Demandas do processo cujos anexos operacionais podem ser reutilizados (inclui cluster)."""
    from core.services.operacional_estado_service import OperacionalEstadoService

    return OperacionalEstadoService()._demanda_ids_timeline(demanda)


def _nome_arquivo_upload(arquivo) -> str:
    nome = getattr(arquivo, "name", "") or "anexo"
    return nome.split("/")[-1]


def _copiar_upload(arquivo) -> ContentFile:
    """Releitura segura — uploads Django são consumíveis uma vez."""
    if hasattr(arquivo, "seek"):
        arquivo.seek(0)
    conteudo = arquivo.read()
    return ContentFile(conteudo, name=_nome_arquivo_upload(arquivo))


def _nome_setor(uid) -> str | None:
    if uid in (None, ""):
        return None
    from core.models_unidade_administrativa import UnidadeAdministrativa

    ua = UnidadeAdministrativa.objects.filter(pk=int(uid)).first()
    if ua:
        return ua.sigla or ua.nome
    return None


def _rotulo_origem_anexo(tram: Tramitacao) -> str:
    """Órgão/setor de origem do anexo — preferível ao tipo genérico da tramitação."""
    meta = tram.metadata if isinstance(tram.metadata, dict) else {}
    from integrations import sinapse_catalog

    orgao_nome = meta.get("orgao_nome")
    orgao_id = meta.get("orgao_id") or meta.get("sinapse_orgao_id")
    if not orgao_nome and orgao_id not in (None, ""):
        orgao_nome = sinapse_catalog.get_orgao_nome(int(orgao_id))

    setor_nome = meta.get("setor_nome")
    if not setor_nome:
        setor_nome = _nome_setor(meta.get("setor_id") or meta.get("unidade_administrativa_id"))

    if not setor_nome and tram.unidade_destino_id and tram.unidade_destino:
        setor_nome = tram.unidade_destino.sigla or tram.unidade_destino.nome

    if orgao_nome and setor_nome:
        return f"{orgao_nome} › {setor_nome}"
    if setor_nome:
        return setor_nome
    if orgao_nome:
        return orgao_nome
    if tram.unidade_destino_id and tram.unidade_destino:
        dest = tram.unidade_destino.sigla or tram.unidade_destino.nome
        if dest:
            return dest
    return tram.get_tipo_display()


def anexar_arquivos_tramitacao(
    tramitacao: Tramitacao,
    arquivos: list,
    *,
    copiar: bool = False,
) -> list[AnexoTramitacao]:
    """Persiste anexos na tramitação, rejeitando nomes duplicados no lote."""
    arquivos = [a for a in (arquivos or []) if a]
    if not arquivos:
        return []

    nomes = [_nome_arquivo_upload(a) for a in arquivos]
    validar_lote_nomes_arquivo(set(), nomes)

    criados: list[AnexoTramitacao] = []
    for arq in arquivos:
        payload = _copiar_upload(arq) if copiar else arq
        criados.append(AnexoTramitacao.objects.create(tramitacao=tramitacao, arquivo=payload))
    return criados


def listar_anexos_operacionais_demanda(demanda: Demanda) -> list[dict]:
    """Anexos de tramitações anteriores disponíveis para compor a devolutiva final."""
    demanda_ids = _demanda_ids_processo(demanda)
    items: list[dict] = []
    vistos: set[int] = set()
    trams = (
        Tramitacao.objects.filter(demanda_id__in=demanda_ids)
        .exclude(tipo__in=TIPOS_TRAMITACAO_EXCLUIDOS_ANEXOS_REUSO)
        .select_related("unidade_destino")
        .prefetch_related("anexos")
        .order_by("-timestamp")
    )
    for tram in trams:
        origem_label = _rotulo_origem_anexo(tram)
        for anexo in tram.anexos.all():
            if anexo.pk in vistos:
                continue
            vistos.add(anexo.pk)
            nome = anexo.arquivo.name.split("/")[-1] if anexo.arquivo else ""
            items.append(
                {
                    "id": anexo.pk,
                    "tramitacao_id": tram.pk,
                    "tipo_tramitacao": tram.tipo,
                    "tipo_display": tram.get_tipo_display(),
                    "origem_label": origem_label,
                    "nome": nome,
                    "arquivo": anexo.arquivo.url if anexo.arquivo else "",
                    "timestamp": tram.timestamp.isoformat(),
                }
            )
    return items


def vincular_anexos_existentes(
    tramitacao: Tramitacao,
    anexo_ids: list[int],
    *,
    demanda_id: int,
) -> list[AnexoTramitacao]:
    """Copia anexos já registrados no processo para a tramitação de devolutiva."""
    if not anexo_ids:
        return []

    demanda = Demanda.objects.get(pk=int(demanda_id))
    demanda_ids = _demanda_ids_processo(demanda)
    validos = {
        int(pk)
        for pk in AnexoTramitacao.objects.filter(
            pk__in=[int(x) for x in anexo_ids],
            tramitacao__demanda_id__in=demanda_ids,
        ).values_list("pk", flat=True)
    }
    existentes = {_nome_arquivo_upload(a.arquivo) for a in tramitacao.anexos.all()}
    criados: list[AnexoTramitacao] = []

    for aid in anexo_ids:
        if int(aid) not in validos:
            continue
        orig = AnexoTramitacao.objects.select_related("tramitacao").get(pk=int(aid))
        if not orig.arquivo:
            continue
        nome = _nome_arquivo_upload(orig.arquivo)
        if nome in existentes:
            continue
        with orig.arquivo.open("rb") as fh:
            payload = ContentFile(fh.read(), name=nome)
        criados.append(AnexoTramitacao.objects.create(tramitacao=tramitacao, arquivo=payload))
        existentes.add(nome)
    return criados


def serializar_anexos_tramitacao(tramitacao: Tramitacao | None) -> list[dict]:
    if not tramitacao:
        return []
    return [
        {
            "id": a.pk,
            "arquivo": a.arquivo.url if a.arquivo else "",
            "nome": a.arquivo.name.split("/")[-1] if a.arquivo else "",
        }
        for a in tramitacao.anexos.all()
    ]
