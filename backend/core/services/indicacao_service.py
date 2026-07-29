"""Regras de negócio para indicações legislativas (perfil CAMARA)."""

from __future__ import annotations

from core.models import Demanda, DemandaVereadorVinculo, Usuario
from core.services.indicacao_numeracao_service import anexo_pdf_indicacao


def demanda_eh_indicacao(demanda: Demanda) -> bool:
    return getattr(demanda, "tipo_legislativo", None) == Demanda.TIPO_LEGISLATIVO_INDICACAO


def filtro_demandas_por_vereador(vereador_id: int):
    """Demandas do vereador como autor ou vinculadas em indicações."""
    from django.db.models import Q

    vid = int(vereador_id)
    return Q(autor_id=vid) | Q(
        tipo_legislativo=Demanda.TIPO_LEGISLATIVO_INDICACAO,
        vinculos_vereador__vereador_id=vid,
    )


def agregar_demandas_por_vereador(queryset, status_aberto: list[str]) -> list[dict]:
    """Contagem por vereador: ofícios (autor) + indicações (vínculo)."""
    from collections import defaultdict

    buckets: dict[int, dict] = defaultdict(
        lambda: {"total": 0, "abertas": 0, "first_name": "", "last_name": ""}
    )

    for demanda in (
        queryset.exclude(tipo_legislativo=Demanda.TIPO_LEGISLATIVO_INDICACAO)
        .filter(autor__perfil="VEREADOR")
        .select_related("autor")
        .iterator(chunk_size=500)
    ):
        autor = demanda.autor
        if not autor:
            continue
        bucket = buckets[int(autor.pk)]
        bucket["first_name"] = autor.first_name or ""
        bucket["last_name"] = autor.last_name or ""
        bucket["total"] += 1
        if demanda.status in status_aberto:
            bucket["abertas"] += 1

    indicacao_ids = queryset.filter(
        tipo_legislativo=Demanda.TIPO_LEGISLATIVO_INDICACAO
    ).values_list("pk", flat=True)
    for vinc in DemandaVereadorVinculo.objects.filter(
        demanda_id__in=indicacao_ids
    ).select_related("vereador", "demanda"):
        vereador = vinc.vereador
        if not vereador or vereador.perfil != "VEREADOR":
            continue
        bucket = buckets[int(vereador.pk)]
        bucket["first_name"] = vereador.first_name or ""
        bucket["last_name"] = vereador.last_name or ""
        bucket["total"] += 1
        if vinc.demanda.status in status_aberto:
            bucket["abertas"] += 1

    return sorted(
        [
            {
                "autor__first_name": data["first_name"],
                "autor__last_name": data["last_name"],
                "total": data["total"],
                "abertas": data["abertas"],
            }
            for data in buckets.values()
            if data["total"] > 0
        ],
        key=lambda row: row["total"],
        reverse=True,
    )


def usuario_pode_gerir_indicacao(usuario, demanda: Demanda) -> bool:
    perfil = getattr(usuario, "perfil", None)
    if perfil == "GESTOR":
        return True
    if perfil == "CAMARA" and demanda.autor_id == getattr(usuario, "pk", None):
        return True
    return False


def validar_rascunho_indicacao(demanda: Demanda) -> None:
    if not demanda_eh_indicacao(demanda):
        return
    if not demanda.vinculos_vereador.exists():
        raise ValueError("Informe ao menos um vereador vinculado à indicação.")
    if not anexo_pdf_indicacao(demanda):
        raise ValueError("Anexe o PDF da indicação assinada pelos vereadores responsáveis.")


def sincronizar_vinculos_vereador(
    demanda: Demanda,
    vereadores_ids: list[int] | None,
    *,
    autor_vereador_id: int | None = None,
) -> None:
    if not demanda_eh_indicacao(demanda):
        return
    ids = []
    for raw in vereadores_ids or []:
        try:
            ids.append(int(raw))
        except (TypeError, ValueError):
            continue
    ids = list(dict.fromkeys(ids))
    if autor_vereador_id and int(autor_vereador_id) not in ids:
        ids.insert(0, int(autor_vereador_id))
    if not ids:
        demanda.vinculos_vereador.all().delete()
        return
    vereadores = Usuario.objects.filter(pk__in=ids, perfil="VEREADOR")
    encontrados = {v.pk for v in vereadores}
    faltando = [i for i in ids if i not in encontrados]
    if faltando:
        raise ValueError(f"Vereador(es) inválido(s): {', '.join(map(str, faltando))}")
    demanda.vinculos_vereador.exclude(vereador_id__in=ids).delete()
    autor_id = int(autor_vereador_id) if autor_vereador_id else ids[0]
    for vid in ids:
        papel = (
            DemandaVereadorVinculo.PAPEL_AUTOR
            if vid == autor_id
            else DemandaVereadorVinculo.PAPEL_COAUTOR
        )
        DemandaVereadorVinculo.objects.update_or_create(
            demanda=demanda,
            vereador_id=vid,
            defaults={"papel": papel},
        )
