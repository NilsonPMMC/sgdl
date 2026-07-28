"""Alertas de possível duplicidade ao registrar demanda pelo Copiloto."""

from __future__ import annotations

from typing import Any

from django.conf import settings

from core.models import Demanda
from core.services.cluster_service import haversine_metros

_STATUS_COMPARACAO = (
    "RASCUNHO",
    "AGUARDANDO_PROTOCOLO",
    "EM_EXECUCAO",
)

_STATUS_LABEL = {
    "RASCUNHO": "Rascunho",
    "AGUARDANDO_PROTOCOLO": "Aguardando protocolo",
    "EM_EXECUCAO": "Em execução",
}

_NIVEL_EM_TRAMITE = frozenset({"AGUARDANDO_PROTOCOLO", "EM_EXECUCAO"})

_PRIORIDADE_STATUS = {
    "EM_EXECUCAO": 0,
    "AGUARDANDO_PROTOCOLO": 1,
    "RASCUNHO": 2,
}


def _raio_duplicidade_metros() -> float:
    return float(getattr(settings, "CLUSTER_RADIUS_METERS", 300))


def _mesmo_bairro(bairro_a: str | None, bairro_b: str | None) -> bool:
    a = (bairro_a or "").strip().lower()
    b = (bairro_b or "").strip().lower()
    return bool(a and b and a == b)


def _locais_compatíveis(
    *,
    latitude_novo: float | None,
    longitude_novo: float | None,
    bairro_novo: str | None,
    latitude_existente: float | None,
    longitude_existente: float | None,
    bairro_existente: str | None,
    sinapse_servico_id: int | None,
) -> bool:
    """Mesma regra do cluster: serviço + entorno geográfico (~300 m)."""
    from integrations import sinapse_catalog

    if sinapse_servico_id and not sinapse_catalog.servico_requer_localizacao(
        int(sinapse_servico_id)
    ):
        return True

    if (
        latitude_novo is not None
        and longitude_novo is not None
        and latitude_existente is not None
        and longitude_existente is not None
    ):
        dist = haversine_metros(
            float(latitude_novo),
            float(longitude_novo),
            float(latitude_existente),
            float(longitude_existente),
        )
        return dist <= _raio_duplicidade_metros()

    return _mesmo_bairro(bairro_novo, bairro_existente)


def _montar_alerta(d: Demanda) -> dict[str, Any]:
    status = d.status
    status_label = _STATUS_LABEL.get(status, status)
    titulo = d.titulo or ""
    if status in _NIVEL_EM_TRAMITE:
        nivel = "em_tramite"
        gravidade = "alta"
        if status == "AGUARDANDO_PROTOCOLO":
            mensagem = (
                f"Já existe o processo #{d.id} («{titulo}») aguardando protocolo. "
                "Recomendamos não enviar este ofício."
            )
        else:
            mensagem = (
                f"Já existe o processo #{d.id} («{titulo}») em execução. "
                "Recomendamos não enviar este ofício."
            )
    else:
        nivel = "rascunho"
        gravidade = "media"
        mensagem = (
            f"Existe um rascunho semelhante (#{d.id} — «{titulo}»). "
            "Revise se não é o mesmo pedido antes de protocolar."
        )

    proto = (d.protocolo_legislativo or "").strip()
    return {
        "demanda_id": d.id,
        "titulo": titulo,
        "status": status,
        "status_label": status_label,
        "protocolo_legislativo": d.protocolo_legislativo,
        "protocolo_exibicao": proto or f"#{d.id}",
        "logradouro": d.logradouro,
        "bairro": d.bairro,
        "similaridade": 1.0,
        "nivel": nivel,
        "gravidade": gravidade,
        "mensagem": mensagem,
    }


def resumir_alertas_duplicidade(alertas: list[dict[str, Any]]) -> dict[str, Any]:
    """Resumo para UI: diferencia rascunho de processo já em tramitação."""
    em_tramite = [a for a in alertas if a.get("nivel") == "em_tramite"]
    rascunhos = [a for a in alertas if a.get("nivel") == "rascunho"]

    if em_tramite:
        refs = ", ".join(
            f"#{a['demanda_id']} ({a.get('status_label') or a.get('status')})"
            for a in em_tramite[:3]
        )
        return {
            "tem_duplicidade": True,
            "tem_em_tramite": True,
            "tem_rascunho": bool(rascunhos),
            "gravidade_maxima": "alta",
            "mensagem_resumo": (
                f"Atenção: processo(s) semelhante(s) já em tramitação: {refs}. "
                "Recomendamos não enviar este ofício e acompanhar o processo existente."
            ),
            "sugerir_nao_enviar": True,
        }

    if rascunhos:
        refs = ", ".join(f"#{a['demanda_id']}" for a in rascunhos[:3])
        return {
            "tem_duplicidade": True,
            "tem_em_tramite": False,
            "tem_rascunho": True,
            "gravidade_maxima": "media",
            "mensagem_resumo": (
                f"Rascunho(s) semelhante(s) já registrado(s): {refs}. "
                "Revise se não é o mesmo pedido antes de protocolar."
            ),
            "sugerir_nao_enviar": False,
        }

    return {
        "tem_duplicidade": False,
        "tem_em_tramite": False,
        "tem_rascunho": False,
        "gravidade_maxima": None,
        "mensagem_resumo": "",
        "sugerir_nao_enviar": False,
    }


def alertas_duplicidade_para_demanda(demanda: Demanda, usuario) -> dict[str, Any]:
    """Pacote de alertas para pré-visualização/envio oficial de uma demanda."""
    alertas = buscar_alertas_duplicidade(
        usuario,
        titulo=demanda.titulo,
        descricao=demanda.descricao,
        logradouro=demanda.logradouro,
        bairro=demanda.bairro,
        latitude=float(demanda.latitude) if demanda.latitude is not None else None,
        longitude=float(demanda.longitude) if demanda.longitude is not None else None,
        sinapse_servico_id=demanda.sinapse_servico_id,
        excluir_demanda_id=demanda.id,
    )
    return {
        "alertas_duplicidade": alertas,
        "duplicidade_resumo": resumir_alertas_duplicidade(alertas),
    }


def buscar_alertas_duplicidade(
    usuario,
    *,
    titulo: str = "",
    descricao: str = "",
    logradouro: str | None = None,
    bairro: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    sinapse_servico_id: int | None = None,
    excluir_demanda_id: int | None = None,
    limite: int = 3,
) -> list[dict[str, Any]]:
    """
    Retorna processos do autor com o mesmo serviço Sinapse no mesmo entorno (~300 m).

    Considera apenas status: rascunho, aguardando protocolo e em execução.
    Serviços sem localização obrigatória comparam somente pelo serviço.
    """
    del titulo, descricao  # mantidos na assinatura por compatibilidade de chamadas

    if sinapse_servico_id is None:
        return []

    candidatos: list[Demanda] = []
    qs = (
        Demanda.objects.filter(
            autor=usuario,
            status__in=_STATUS_COMPARACAO,
            sinapse_servico_id=int(sinapse_servico_id),
        )
        .order_by("-data_criacao")
        .only(
            "id",
            "titulo",
            "status",
            "protocolo_legislativo",
            "logradouro",
            "bairro",
            "sinapse_servico_id",
            "latitude",
            "longitude",
            "data_criacao",
        )[:80]
    )
    for d in qs:
        if excluir_demanda_id is not None and d.id == excluir_demanda_id:
            continue
        lat_ex = float(d.latitude) if d.latitude is not None else None
        lon_ex = float(d.longitude) if d.longitude is not None else None
        if not _locais_compatíveis(
            latitude_novo=latitude,
            longitude_novo=longitude,
            bairro_novo=bairro,
            latitude_existente=lat_ex,
            longitude_existente=lon_ex,
            bairro_existente=d.bairro,
            sinapse_servico_id=sinapse_servico_id,
        ):
            continue
        candidatos.append(d)

    candidatos.sort(
        key=lambda d: (
            _PRIORIDADE_STATUS.get(d.status, 9),
            -(d.data_criacao.timestamp() if d.data_criacao else 0),
        )
    )
    return [_montar_alerta(d) for d in candidatos[:limite]]
