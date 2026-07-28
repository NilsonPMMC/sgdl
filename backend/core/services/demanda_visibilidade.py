"""Regras de visibilidade de demandas por perfil (rascunhos e escopo RBAC)."""

from __future__ import annotations

from django.db.models import Q, QuerySet

from core.models import Demanda
from core.services.gestor_escopo import (
    STATUS_FILA_PROTOCOLO_CENTRAL,
    TIPO_SETORIAL,
    gestor_protocolo_sgac,
    orgaos_escopo_gestor,
    tipo_gestor,
)


def demanda_ids_pendencia_operacional(orgao_id: int) -> list[int]:
    """
    Demandas em que o órgão ainda tem trabalho operacional pendente.

    Scatter/transversal: só enquanto houver perna ou nó aberto do órgão.
    Fluxo direto: enquanto a demanda titular do órgão estiver na fila operacional.
    """
    from core.models_no_operacional import NoOperacional, StatusNoOperacional
    from core.models_operacional import FluxoRoteamento
    from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional
    from core.services.devolutiva_alerta_service import demanda_ids_alerta_devolutiva

    oid = int(orgao_id)
    ids: set[int] = set()

    for perna in PernaOperacional.objects.filter(
        sinapse_orgao_id=oid,
        status__in=StatusPernaOperacional.ATIVOS,
    ).only("demanda_id", "pk"):
        did = int(perna.demanda_id)
        if _scatter_orgao_encerrado(did, oid):
            continue
        ids.add(did)

    ids.update(
        NoOperacional.objects.filter(
            sinapse_orgao_id=oid,
            status=StatusNoOperacional.ABERTO,
        ).values_list("demanda_id", flat=True)
    )

    candidatas = Demanda.objects.filter(
        sinapse_orgao_id=oid,
        status__in=("PROTOCOLADO", "EM_EXECUCAO", "AGUARDANDO_TRANSFERENCIA"),
    ).values("pk", "fluxo_roteamento", "nos_ativos")

    for row in candidatas:
        pk = int(row["pk"])
        if pk in ids:
            continue
        fluxo = row.get("fluxo_roteamento") or ""
        nos = int(row.get("nos_ativos") or 0)
        if fluxo == FluxoRoteamento.FLUXO_TRANSVERSAL or nos > 0:
            continue
        if PernaOperacional.objects.filter(
            demanda_id=pk,
            status__in=StatusPernaOperacional.ATIVOS,
        ).exists():
            continue
        ids.add(pk)

    ids.update(demanda_ids_alerta_devolutiva(oid))
    return list(ids)


def _ids_unidades_usuario(user) -> list[int]:
    from core.services.tramitacao_setor_service import UnidadeAdministrativaService

    return UnidadeAdministrativaService().ids_unidades_do_usuario(user)


def _filtro_ua_setor(ids_ua: list[int], orgao_id: int | None = None):
    """UA do setor ou, se vazio no nó/perna, qualquer registro do órgão (fallback)."""
    from django.db.models import Q

    base = Q(unidade_administrativa_id__in=ids_ua)
    if orgao_id:
        base = base | Q(
            unidade_administrativa_id__isnull=True,
            sinapse_orgao_id=int(orgao_id),
        )
    return base


def _filtro_ua_estrito(ids_ua: list[int]):
    """Somente UAs vinculadas — escopo de setor sem fallback ao órgão inteiro."""
    from django.db.models import Q

    return Q(unidade_administrativa_id__in=ids_ua)


def _scatter_setor_encerrado(demanda_id: int, orgao_id: int, ids_ua: list[int]) -> bool:
    """True quando não restam nós abertos do órgão nos setores informados."""
    from core.models_no_operacional import NoOperacional, StatusNoOperacional

    if not ids_ua:
        return _scatter_orgao_encerrado(demanda_id, orgao_id)

    oid = int(orgao_id)
    qs = NoOperacional.objects.filter(
        demanda_id=int(demanda_id),
        sinapse_orgao_id=oid,
        unidade_administrativa_id__in=[int(u) for u in ids_ua],
    )
    if not qs.exists():
        return False
    return not qs.filter(status=StatusNoOperacional.ABERTO).exists()


def _scatter_orgao_encerrado(demanda_id: int, orgao_id: int) -> bool:
    """True quando o órgão já teve nós scatter e todos foram concluídos."""
    from core.models_no_operacional import NoOperacional, StatusNoOperacional

    if not NoOperacional.objects.filter(
        demanda_id=int(demanda_id),
        sinapse_orgao_id=int(orgao_id),
    ).exists():
        return False
    return not NoOperacional.objects.filter(
        demanda_id=int(demanda_id),
        sinapse_orgao_id=int(orgao_id),
        status=StatusNoOperacional.ABERTO,
    ).exists()


def demanda_ids_participacao_scatter_encerrada(orgao_id: int) -> list[int]:
    """Demandas em que o órgão concluiu a participação scatter (qualquer setor)."""
    from core.models_no_operacional import NoOperacional, StatusNoOperacional

    oid = int(orgao_id)
    ids: set[int] = set()
    for did in (
        NoOperacional.objects.filter(
            sinapse_orgao_id=oid,
            status=StatusNoOperacional.CONCLUIDO,
        )
        .values_list("demanda_id", flat=True)
        .distinct()
    ):
        if _scatter_orgao_encerrado(int(did), oid):
            ids.add(int(did))
    return list(ids)


def demanda_ids_participacao_scatter_encerrada_setor(user) -> list[int]:
    """Demandas em que o setor do usuário concluiu a participação scatter."""
    from core.models_no_operacional import NoOperacional, StatusNoOperacional

    orgao_id = getattr(user, "sinapse_orgao_id", None)
    ids_ua = _ids_unidades_usuario(user)
    if not orgao_id:
        return []
    oid = int(orgao_id)
    if not ids_ua:
        return demanda_ids_participacao_scatter_encerrada(oid)

    ids: set[int] = set()
    uas = [int(u) for u in ids_ua]
    for did in (
        NoOperacional.objects.filter(
            sinapse_orgao_id=oid,
            status=StatusNoOperacional.CONCLUIDO,
            unidade_administrativa_id__in=uas,
        )
        .values_list("demanda_id", flat=True)
        .distinct()
    ):
        if _scatter_setor_encerrado(int(did), oid, uas):
            ids.add(int(did))
    return list(ids)


def demanda_ids_pendencia_setor(user) -> list[int]:
    """Pendência operacional restrita aos setores vinculados ao usuário."""
    from core.models_no_operacional import NoOperacional, StatusNoOperacional
    from core.models_operacional import FluxoRoteamento
    from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional
    from core.services.devolutiva_alerta_service import demanda_ids_alerta_devolutiva

    orgao_id = getattr(user, "sinapse_orgao_id", None)
    ids_ua = _ids_unidades_usuario(user)
    if not orgao_id:
        return []
    oid = int(orgao_id)
    if not ids_ua:
        return demanda_ids_pendencia_operacional(oid)

    uas = [int(u) for u in ids_ua]
    ua_q = _filtro_ua_estrito(uas)
    ids: set[int] = set()

    for perna in PernaOperacional.objects.filter(
        sinapse_orgao_id=oid,
        status__in=StatusPernaOperacional.ATIVOS,
    ).filter(ua_q):
        did = int(perna.demanda_id)
        if _scatter_setor_encerrado(did, oid, uas):
            continue
        ids.add(did)

    for did in NoOperacional.objects.filter(
        sinapse_orgao_id=oid,
        status=StatusNoOperacional.ABERTO,
    ).filter(ua_q).values_list("demanda_id", flat=True):
        if _scatter_setor_encerrado(int(did), oid, uas):
            continue
        ids.add(int(did))

    for row in Demanda.objects.filter(
        unidade_administrativa_id__in=uas,
        sinapse_orgao_id=oid,
        status__in=("PROTOCOLADO", "EM_EXECUCAO", "AGUARDANDO_TRANSFERENCIA"),
    ).values("pk", "fluxo_roteamento", "nos_ativos"):
        pk = int(row["pk"])
        if pk in ids:
            continue
        fluxo = row.get("fluxo_roteamento") or ""
        nos = int(row.get("nos_ativos") or 0)
        if fluxo == FluxoRoteamento.FLUXO_TRANSVERSAL or nos > 0:
            continue
        if PernaOperacional.objects.filter(
            demanda_id=pk,
            status__in=StatusPernaOperacional.ATIVOS,
        ).filter(ua_q).exists():
            continue
        if NoOperacional.objects.filter(
            demanda_id=pk,
            status=StatusNoOperacional.ABERTO,
        ).filter(ua_q).exists():
            continue
        ids.add(pk)

    ids.update(demanda_ids_alerta_devolutiva(oid))
    return list(ids)


def demanda_ids_em_operacao_setor(user) -> list[int]:
    """Demandas com pendência aberta nos setores vinculados ao usuário."""
    from core.models_no_operacional import NoOperacional, StatusNoOperacional
    from core.models_operacional import FluxoRoteamento
    from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional

    ids_ua = _ids_unidades_usuario(user)
    orgao_id = getattr(user, "sinapse_orgao_id", None)
    if not ids_ua or not orgao_id:
        return []

    oid = int(orgao_id)
    uas = [int(u) for u in ids_ua]
    ua_q = _filtro_ua_estrito(uas)
    demanda_ids: set[int] = set()

    demanda_ids.update(
        NoOperacional.objects.filter(ua_q, status=StatusNoOperacional.ABERTO).values_list(
            "demanda_id", flat=True
        )
    )
    demanda_ids.update(
        PernaOperacional.objects.filter(
            ua_q,
            status__in=StatusPernaOperacional.ATIVOS,
        ).values_list("demanda_id", flat=True)
    )
    for did in list(demanda_ids):
        if _scatter_setor_encerrado(int(did), oid, uas):
            demanda_ids.discard(int(did))

    for row in Demanda.objects.filter(
        unidade_administrativa_id__in=uas,
        sinapse_orgao_id=oid,
        status__in=("PROTOCOLADO", "EM_EXECUCAO", "AGUARDANDO_TRANSFERENCIA"),
    ).values("pk", "fluxo_roteamento", "nos_ativos"):
        pk = int(row["pk"])
        if pk in demanda_ids:
            continue
        fluxo = row.get("fluxo_roteamento") or ""
        nos = int(row.get("nos_ativos") or 0)
        if fluxo == FluxoRoteamento.FLUXO_TRANSVERSAL or nos > 0:
            continue
        if PernaOperacional.objects.filter(
            demanda_id=pk,
            status__in=StatusPernaOperacional.ATIVOS,
        ).filter(ua_q).exists():
            continue
        if NoOperacional.objects.filter(
            demanda_id=pk,
            status=StatusNoOperacional.ABERTO,
        ).filter(ua_q).exists():
            continue
        demanda_ids.add(pk)

    return list(demanda_ids)


def demanda_ids_encerrado_setor(user) -> list[int]:
    """Demandas em que o setor/órgão do usuário já encerrou a participação operacional."""
    from core.models_no_operacional import NoOperacional, StatusNoOperacional
    from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional

    orgao_id = getattr(user, "sinapse_orgao_id", None)
    if not orgao_id:
        return []

    oid = int(orgao_id)
    ids_ua = _ids_unidades_usuario(user)
    encerradas: set[int] = set()

    if ids_ua:
        encerradas.update(demanda_ids_participacao_scatter_encerrada_setor(user))
        ua_q = _filtro_ua_estrito([int(u) for u in ids_ua])
        encerradas.update(
            NoOperacional.objects.filter(
                ua_q,
                status=StatusNoOperacional.CONCLUIDO,
            ).values_list("demanda_id", flat=True)
        )
        encerradas.update(
            PernaOperacional.objects.filter(
                ua_q,
                status=StatusPernaOperacional.CONCLUIDA,
            ).values_list("demanda_id", flat=True)
        )
    else:
        encerradas.update(demanda_ids_participacao_scatter_encerrada(oid))
        encerradas.update(
            NoOperacional.objects.filter(
                sinapse_orgao_id=oid,
                status=StatusNoOperacional.CONCLUIDO,
            ).values_list("demanda_id", flat=True)
        )
        encerradas.update(
            PernaOperacional.objects.filter(
                sinapse_orgao_id=oid,
                status=StatusPernaOperacional.CONCLUIDA,
            ).values_list("demanda_id", flat=True)
        )

    em_aberto = set(demanda_ids_em_operacao_setor(user))
    pendencia = set(demanda_ids_pendencia_setor(user))
    from core.services.devolutiva_alerta_service import demanda_ids_alerta_devolutiva

    alerta_leitura = set(demanda_ids_alerta_devolutiva(oid))
    # Devolutiva final (somente leitura) não bloqueia a fila Encerrado do setor.
    pendencia -= alerta_leitura
    em_aberto -= alerta_leitura
    from core.services.acompanhamento_demanda_service import AcompanhamentoDemandaService

    acompanhando = set(AcompanhamentoDemandaService().demanda_ids_acompanhando(user))
    return [
        int(d)
        for d in encerradas
        if int(d) not in em_aberto
        and int(d) not in pendencia
        and int(d) not in acompanhando
    ]


def filtrar_demandas_em_operacao_setor(qs: QuerySet[Demanda], user) -> QuerySet[Demanda]:
    ids = demanda_ids_em_operacao_setor(user)
    if not ids:
        return qs.none()
    return qs.filter(pk__in=ids)


def filtrar_demandas_encerrado_setor(qs: QuerySet[Demanda], user) -> QuerySet[Demanda]:
    ids = demanda_ids_encerrado_setor(user)
    if not ids:
        return qs.none()
    return qs.filter(pk__in=ids)


def filtrar_demandas_minha_unidade(qs: QuerySet[Demanda], user) -> QuerySet[Demanda]:
    """Compatível com Protocolo — delega ao escopo de setor em operação."""
    return filtrar_demandas_em_operacao_setor(qs, user)


def aplicar_escopo_fila_operacional(qs: QuerySet[Demanda], user) -> QuerySet[Demanda]:
    """Restringe fila operacional às demandas com pendência real do órgão/setor."""
    if getattr(user, "perfil", None) != "SECRETARIA":
        return qs
    orgao_id = getattr(user, "sinapse_orgao_id", None)
    if not orgao_id:
        return qs.none()
    ids_ua = _ids_unidades_usuario(user)
    if ids_ua:
        pendencia = demanda_ids_pendencia_setor(user)
    else:
        pendencia = demanda_ids_pendencia_operacional(int(orgao_id))
    if not pendencia:
        return qs.none()
    return qs.filter(pk__in=pendencia)


def _mapa_uas_gestor_por_orgao(user, orgaos: list[int]) -> dict[int, list[int]]:
    """Unidades vinculadas ao gestor setorial, agrupadas por órgão Sinapse."""
    from core.models_unidade_administrativa import UnidadeAdministrativa

    resultado: dict[int, list[int]] = {int(o): [] for o in orgaos}
    all_uas = [int(u) for u in _ids_unidades_usuario(user)]
    if not all_uas:
        return resultado
    for ua_id, oid in UnidadeAdministrativa.objects.filter(pk__in=all_uas).values_list(
        "pk", "sinapse_orgao_id"
    ):
        if oid is not None and int(oid) in resultado:
            resultado[int(oid)].append(int(ua_id))
    return resultado


def _demanda_ids_pendencia_para_orgao_uas(orgao_id: int, uas: list[int]) -> list[int]:
    """Pendência operacional de um órgão restrita a setores (UAs)."""
    from core.models_no_operacional import NoOperacional, StatusNoOperacional
    from core.models_operacional import FluxoRoteamento
    from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional
    from core.services.devolutiva_alerta_service import demanda_ids_alerta_devolutiva

    oid = int(orgao_id)
    uas_norm = [int(u) for u in uas]
    ua_q = _filtro_ua_estrito(uas_norm)
    ids: set[int] = set()

    for perna in PernaOperacional.objects.filter(
        sinapse_orgao_id=oid,
        status__in=StatusPernaOperacional.ATIVOS,
    ).filter(ua_q):
        did = int(perna.demanda_id)
        if _scatter_setor_encerrado(did, oid, uas_norm):
            continue
        ids.add(did)

    for did in NoOperacional.objects.filter(
        sinapse_orgao_id=oid,
        status=StatusNoOperacional.ABERTO,
    ).filter(ua_q).values_list("demanda_id", flat=True):
        if _scatter_setor_encerrado(int(did), oid, uas_norm):
            continue
        ids.add(int(did))

    for row in Demanda.objects.filter(
        unidade_administrativa_id__in=uas_norm,
        sinapse_orgao_id=oid,
        status__in=("PROTOCOLADO", "EM_EXECUCAO", "AGUARDANDO_TRANSFERENCIA"),
    ).values("pk", "fluxo_roteamento", "nos_ativos"):
        pk = int(row["pk"])
        if pk in ids:
            continue
        fluxo = row.get("fluxo_roteamento") or ""
        nos = int(row.get("nos_ativos") or 0)
        if fluxo == FluxoRoteamento.FLUXO_TRANSVERSAL or nos > 0:
            continue
        if PernaOperacional.objects.filter(
            demanda_id=pk,
            status__in=StatusPernaOperacional.ATIVOS,
        ).filter(ua_q).exists():
            continue
        if NoOperacional.objects.filter(
            demanda_id=pk,
            status=StatusNoOperacional.ABERTO,
        ).filter(ua_q).exists():
            continue
        ids.add(pk)

    ids.update(demanda_ids_alerta_devolutiva(oid))
    return list(ids)


def _demanda_ids_em_operacao_para_orgao_uas(orgao_id: int, uas: list[int]) -> list[int]:
    """Demandas com execução aberta nos setores informados."""
    from core.models_no_operacional import NoOperacional, StatusNoOperacional
    from core.models_operacional import FluxoRoteamento
    from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional

    oid = int(orgao_id)
    uas_norm = [int(u) for u in uas]
    ua_q = _filtro_ua_estrito(uas_norm)
    demanda_ids: set[int] = set()

    demanda_ids.update(
        NoOperacional.objects.filter(ua_q, status=StatusNoOperacional.ABERTO).values_list(
            "demanda_id", flat=True
        )
    )
    demanda_ids.update(
        PernaOperacional.objects.filter(
            ua_q,
            status__in=StatusPernaOperacional.ATIVOS,
        ).values_list("demanda_id", flat=True)
    )
    for did in list(demanda_ids):
        if _scatter_setor_encerrado(int(did), oid, uas_norm):
            demanda_ids.discard(int(did))

    for row in Demanda.objects.filter(
        unidade_administrativa_id__in=uas_norm,
        sinapse_orgao_id=oid,
        status__in=("PROTOCOLADO", "EM_EXECUCAO", "AGUARDANDO_TRANSFERENCIA"),
    ).values("pk", "fluxo_roteamento", "nos_ativos"):
        pk = int(row["pk"])
        if pk in demanda_ids:
            continue
        fluxo = row.get("fluxo_roteamento") or ""
        nos = int(row.get("nos_ativos") or 0)
        if fluxo == FluxoRoteamento.FLUXO_TRANSVERSAL or nos > 0:
            continue
        if PernaOperacional.objects.filter(
            demanda_id=pk,
            status__in=StatusPernaOperacional.ATIVOS,
        ).filter(ua_q).exists():
            continue
        if NoOperacional.objects.filter(
            demanda_id=pk,
            status=StatusNoOperacional.ABERTO,
        ).filter(ua_q).exists():
            continue
        demanda_ids.add(pk)

    return list(demanda_ids)


def demanda_ids_pendencia_gestor_setorial(user) -> list[int]:
    from core.services.gestor_escopo import TIPO_SETORIAL, orgaos_escopo_gestor, tipo_gestor

    if getattr(user, "perfil", None) != "GESTOR" or tipo_gestor(user) != TIPO_SETORIAL:
        return []
    orgaos = orgaos_escopo_gestor(user)
    if not orgaos:
        return []
    ua_map = _mapa_uas_gestor_por_orgao(user, orgaos)
    ids: set[int] = set()
    for oid in orgaos:
        uas = ua_map.get(int(oid), [])
        if uas:
            ids.update(_demanda_ids_pendencia_para_orgao_uas(int(oid), uas))
        else:
            ids.update(demanda_ids_pendencia_operacional(int(oid)))
    return list(ids)


def demanda_ids_em_operacao_gestor_setorial(user) -> list[int]:
    from core.services.gestor_escopo import TIPO_SETORIAL, orgaos_escopo_gestor, tipo_gestor

    if getattr(user, "perfil", None) != "GESTOR" or tipo_gestor(user) != TIPO_SETORIAL:
        return []
    orgaos = orgaos_escopo_gestor(user)
    if not orgaos:
        return []
    ua_map = _mapa_uas_gestor_por_orgao(user, orgaos)
    ids: set[int] = set()
    for oid in orgaos:
        uas = ua_map.get(int(oid), [])
        if uas:
            ids.update(_demanda_ids_em_operacao_para_orgao_uas(int(oid), uas))
        else:
            ids.update(demanda_ids_pendencia_operacional(int(oid)))
    return list(ids)


def aplicar_escopo_fila_operacional_gestor_setorial(
    qs: QuerySet[Demanda], user
) -> QuerySet[Demanda]:
    pendencia = demanda_ids_pendencia_gestor_setorial(user)
    if not pendencia:
        return qs.none()
    return qs.filter(pk__in=pendencia)


def filtrar_demandas_em_operacao_gestor_setorial(
    qs: QuerySet[Demanda], user
) -> QuerySet[Demanda]:
    ids = demanda_ids_em_operacao_gestor_setorial(user)
    if not ids:
        return qs.none()
    return qs.filter(pk__in=ids)


def filtrar_demandas_por_unidades(
    qs: QuerySet[Demanda], unidades_ids: list[int]
) -> QuerySet[Demanda]:
    """Restringe demandas aos setores com execução operacional aberta."""
    from core.services.demanda_localizacao_operacional_service import (
        demanda_ids_com_setores_operacionais_abertos,
    )

    ids = demanda_ids_com_setores_operacionais_abertos(unidades_ids)
    if not ids:
        return qs.none()
    return qs.filter(pk__in=ids)


def parse_unidades_administrativas_request(request) -> list[int]:
    """Extrai IDs de UAs da query string (lista repetida ou CSV)."""
    qp = getattr(request, "query_params", None) or getattr(request, "GET", None)
    if qp is None:
        return []
    uas_list = list(qp.getlist("unidades_administrativas"))
    if not uas_list:
        uas_list = list(qp.getlist("unidades_administrativas[]"))
    if not uas_list:
        single = qp.get("unidade_administrativa")
        if single not in (None, ""):
            uas_list = [single]
    parsed: list[int] = []
    for raw in uas_list:
        for part in str(raw).split(","):
            part = part.strip()
            if part.isdigit():
                parsed.append(int(part))
    return parsed


def _demanda_visivel_participacao_orgaos(user, demanda: Demanda, orgaos: list[int]) -> bool:
    """Demanda acessível por perna, scatter-gather, alerta ou participação encerrada."""
    if not orgaos:
        return False
    from core.services.devolutiva_alerta_service import demanda_ids_alerta_devolutiva
    from core.services.perna_operacional_service import PernaOperacionalService
    from core.services.scatter_gather_service import NoOperacionalService

    did = int(demanda.pk)
    if demanda.sinapse_orgao_id in orgaos:
        return True
    for orgao_id in orgaos:
        if did in PernaOperacionalService().demanda_ids_visiveis_por_orgao(int(orgao_id)):
            return True
        if did in demanda_ids_alerta_devolutiva(int(orgao_id)):
            return True
        if did in NoOperacionalService().demanda_ids_visiveis_para_usuario(int(orgao_id), user):
            return True
    ids_ua = _ids_unidades_usuario(user)
    if ids_ua:
        if did in demanda_ids_participacao_scatter_encerrada_setor(user):
            return True
    else:
        for orgao_id in orgaos:
            if did in demanda_ids_participacao_scatter_encerrada(int(orgao_id)):
                return True
    return False


def _filtro_demandas_participacao_orgaos(user, orgaos: list[int]):
    """Q object — demandas visíveis por participação transversal/scatter nos órgãos."""
    from django.db.models import Q

    from core.services.devolutiva_alerta_service import demanda_ids_alerta_devolutiva
    from core.services.perna_operacional_service import PernaOperacionalService
    from core.services.scatter_gather_service import NoOperacionalService

    if not orgaos:
        return Q(pk__in=[])

    perna_ids: set[int] = set()
    nos_ids: set[int] = set()
    alerta_ids: set[int] = set()
    participacao_ids: set[int] = set()
    ids_ua = _ids_unidades_usuario(user)

    for orgao_id in orgaos:
        oid = int(orgao_id)
        perna_ids.update(PernaOperacionalService().demanda_ids_visiveis_por_orgao(oid))
        nos_ids.update(
            NoOperacionalService().demanda_ids_visiveis_para_usuario(oid, user)
        )
        alerta_ids.update(demanda_ids_alerta_devolutiva(oid))
        if ids_ua:
            participacao_ids.update(demanda_ids_participacao_scatter_encerrada_setor(user))
        else:
            participacao_ids.update(demanda_ids_participacao_scatter_encerrada(oid))

    return (
        Q(sinapse_orgao_id__in=orgaos)
        | Q(pk__in=perna_ids)
        | Q(pk__in=alerta_ids)
        | Q(pk__in=nos_ids)
        | Q(pk__in=participacao_ids)
    )


def aplicar_escopo_rascunho(qs: QuerySet[Demanda], user) -> QuerySet[Demanda]:
    """Rascunhos só visíveis ao autor vereador; demais perfis nunca veem RASCUNHO."""
    perfil = getattr(user, "perfil", None)
    if perfil == "VEREADOR" and getattr(user, "pk", None):
        return qs.filter(Q(~Q(status="RASCUNHO")) | Q(status="RASCUNHO", autor_id=user.pk))
    if perfil != "VEREADOR":
        return qs.exclude(status="RASCUNHO")
    return qs.exclude(status="RASCUNHO")


def aplicar_escopo_perfil(qs: QuerySet[Demanda], user) -> QuerySet[Demanda]:
    """Restringe queryset ao alcance operacional do perfil (A5 / U3 / P3)."""
    if not getattr(user, "is_authenticated", False):
        return qs.none()

    perfil = getattr(user, "perfil", None)
    if perfil == "VEREADOR" and getattr(user, "pk", None):
        return qs.filter(autor_id=user.pk)
    if perfil == "SECRETARIA":
        orgao_id = getattr(user, "sinapse_orgao_id", None)
        if orgao_id:
            from core.services.devolutiva_alerta_service import demanda_ids_alerta_devolutiva
            from core.services.perna_operacional_service import PernaOperacionalService
            from core.services.scatter_gather_service import NoOperacionalService

            perna_demanda_ids = PernaOperacionalService().demanda_ids_visiveis_por_orgao(
                int(orgao_id)
            )
            alerta_ids = demanda_ids_alerta_devolutiva(int(orgao_id))
            nos_demanda_ids = NoOperacionalService().demanda_ids_visiveis_para_usuario(
                int(orgao_id), user
            )
            ids_ua = _ids_unidades_usuario(user)
            if ids_ua:
                participacao_encerrada_ids = demanda_ids_participacao_scatter_encerrada_setor(
                    user
                )
            else:
                participacao_encerrada_ids = demanda_ids_participacao_scatter_encerrada(
                    int(orgao_id)
                )
            return qs.filter(
                Q(sinapse_orgao_id=orgao_id)
                | Q(pk__in=perna_demanda_ids)
                | Q(pk__in=alerta_ids)
                | Q(pk__in=nos_demanda_ids)
                | Q(pk__in=participacao_encerrada_ids)
            )
        return qs.none()
    if perfil == "GESTOR":
        if gestor_protocolo_sgac(user):
            return qs
        if tipo_gestor(user) == TIPO_SETORIAL:
            orgaos = orgaos_escopo_gestor(user)
            if not orgaos:
                return qs.none()
            return qs.filter(_filtro_demandas_participacao_orgaos(user, orgaos)).exclude(
                status__in=STATUS_FILA_PROTOCOLO_CENTRAL
            )
        return qs
    return qs


def aplicar_escopo_demanda(qs: QuerySet[Demanda], user) -> QuerySet[Demanda]:
    """Escopo completo: rascunhos + isolamento por perfil."""
    qs = aplicar_escopo_rascunho(qs, user)
    return aplicar_escopo_perfil(qs, user)


def usuario_pode_acessar_demanda(user, demanda: Demanda) -> bool:
    """Verificação pontual de acesso a uma demanda (detalhe/ações)."""
    if not getattr(user, "is_authenticated", False):
        return False

    from core.services.acompanhamento_demanda_service import AcompanhamentoDemandaService

    if AcompanhamentoDemandaService().usuario_acompanha_ativo(user, demanda.pk):
        return True

    perfil = getattr(user, "perfil", None)
    if demanda.status == "RASCUNHO":
        return perfil == "VEREADOR" and demanda.autor_id == user.pk
    if perfil == "VEREADOR":
        return demanda.autor_id == user.pk
    if perfil == "SECRETARIA":
        orgao_id = getattr(user, "sinapse_orgao_id", None)
        if not orgao_id:
            return False
        if demanda.sinapse_orgao_id == orgao_id:
            return True
        from core.services.devolutiva_alerta_service import demanda_ids_alerta_devolutiva
        from core.services.perna_operacional_service import PernaOperacionalService
        from core.services.scatter_gather_service import NoOperacionalService

        if demanda.pk in PernaOperacionalService().demanda_ids_visiveis_por_orgao(
            int(orgao_id)
        ):
            return True
        if demanda.pk in demanda_ids_alerta_devolutiva(int(orgao_id)):
            return True
        ids_ua = _ids_unidades_usuario(user)
        if ids_ua:
            if demanda.pk in demanda_ids_participacao_scatter_encerrada_setor(user):
                return True
        elif demanda.pk in demanda_ids_participacao_scatter_encerrada(int(orgao_id)):
            return True
        return demanda.pk in NoOperacionalService().demanda_ids_visiveis_para_usuario(
            int(orgao_id), user
        )
    if perfil == "GESTOR":
        if gestor_protocolo_sgac(user):
            return demanda.status != "RASCUNHO"
        if tipo_gestor(user) == TIPO_SETORIAL:
            if demanda.status in STATUS_FILA_PROTOCOLO_CENTRAL:
                return False
            orgaos = orgaos_escopo_gestor(user)
            return _demanda_visivel_participacao_orgaos(user, demanda, orgaos)
        return True
    return True
