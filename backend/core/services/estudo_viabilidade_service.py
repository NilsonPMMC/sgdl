"""Registro de resultado operacional e base stand-by de estudo/viabilidade."""

from __future__ import annotations

from typing import Any

from django.db import transaction

from core.models import Demanda
from core.models_estudo_viabilidade import (
    MotivoNaoExecucao,
    RegistroEstudoViabilidade,
    ResultadoOperacional,
)
from core.services import operacional_permissions as perm


class EstudoViabilidadeError(ValueError):
    pass


_RESULTADOS_STAND_BY = frozenset(
    {
        ResultadoOperacional.RESPONDIDO_SEM_EXECUCAO,
        ResultadoOperacional.ORIENTACAO,
    }
)


class EstudoViabilidadeService:
    @staticmethod
    def parse_payload_request(data: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(data, dict):
            return None
        resultado = str(data.get("resultado_operacional") or "").strip().upper()
        if not resultado:
            return None
        registrar_raw = data.get("registrar_stand_by")
        if isinstance(registrar_raw, bool):
            registrar_stand_by = registrar_raw
        else:
            registrar_stand_by = str(registrar_raw or "").lower() in (
                "1",
                "true",
                "yes",
                "sim",
            )
        return {
            "resultado_operacional": resultado,
            "motivo_nao_execucao": str(data.get("motivo_nao_execucao") or "").strip().upper(),
            "escopo_geografico": str(data.get("escopo_geografico") or "").strip(),
            "registrar_stand_by": registrar_stand_by,
        }

    @staticmethod
    def _validar_payload(payload: dict[str, Any]) -> dict[str, Any]:
        resultado = payload.get("resultado_operacional") or ResultadoOperacional.EXECUTADO
        validos_resultado = {c.value for c in ResultadoOperacional}
        if resultado not in validos_resultado:
            raise EstudoViabilidadeError(f"Resultado operacional inválido: {resultado}")

        motivo = (payload.get("motivo_nao_execucao") or "").strip().upper()
        validos_motivo = {c.value for c in MotivoNaoExecucao}
        if motivo and motivo not in validos_motivo:
            raise EstudoViabilidadeError(f"Motivo de não execução inválido: {motivo}")

        escopo = (payload.get("escopo_geografico") or "").strip()
        registrar_stand_by = bool(payload.get("registrar_stand_by"))

        if resultado == ResultadoOperacional.RESPONDIDO_SEM_EXECUCAO and not motivo:
            raise EstudoViabilidadeError(
                "Informe o motivo quando o processo for encerrado sem execução."
            )

        if registrar_stand_by:
            if resultado not in _RESULTADOS_STAND_BY:
                raise EstudoViabilidadeError(
                    "A base stand-by só se aplica a encerramentos sem execução ou orientação."
                )
            if len(escopo) < 3:
                raise EstudoViabilidadeError(
                    "Informe o escopo geográfico (mín. 3 caracteres) para registrar na base stand-by."
                )
            if resultado == ResultadoOperacional.RESPONDIDO_SEM_EXECUCAO and not motivo:
                raise EstudoViabilidadeError(
                    "Informe o motivo para registrar na base stand-by."
                )

        return {
            "resultado_operacional": resultado,
            "motivo_nao_execucao": motivo,
            "escopo_geografico": escopo,
            "registrar_stand_by": registrar_stand_by,
        }

    @transaction.atomic
    def registrar_conclusao_operacional(
        self,
        demanda: Demanda,
        usuario,
        *,
        parecer: str = "",
        payload: dict[str, Any] | None = None,
    ) -> Demanda:
        """Persiste resultado da conclusão operacional; cria registro stand-by se sinalizado."""
        dados = self._validar_payload(payload or {"resultado_operacional": ResultadoOperacional.EXECUTADO})

        demanda.resultado_operacional = dados["resultado_operacional"]
        demanda.motivo_nao_execucao = dados["motivo_nao_execucao"]
        demanda.escopo_geografico = dados["escopo_geografico"]
        demanda.stand_by_estudo_viabilidade = dados["registrar_stand_by"]
        demanda.save(
            update_fields=[
                "resultado_operacional",
                "motivo_nao_execucao",
                "escopo_geografico",
                "stand_by_estudo_viabilidade",
            ]
        )

        if not dados["registrar_stand_by"]:
            RegistroEstudoViabilidade.objects.filter(demanda=demanda).delete()
            return demanda

        orgao_id = demanda.sinapse_orgao_id
        unidade = demanda.unidade_administrativa
        if usuario and perm.orgao_usuario(usuario):
            orgao_id = orgao_id or perm.orgao_usuario(usuario)

        RegistroEstudoViabilidade.objects.update_or_create(
            demanda=demanda,
            defaults={
                "resultado_operacional": dados["resultado_operacional"],
                "motivo_nao_execucao": dados["motivo_nao_execucao"],
                "escopo_geografico": dados["escopo_geografico"],
                "parecer_snapshot": (parecer or "").strip()[:8000],
                "sinapse_orgao_id": orgao_id,
                "unidade_administrativa": unidade,
                "pode_retomar": True,
                "registrado_por": usuario,
            },
        )
        return demanda

    def usuario_ve_stand_by(self, usuario) -> bool:
        perfil = getattr(usuario, "perfil", None)
        return perfil in ("PROTOCOLO", "SECRETARIA", "GESTOR") or bool(
            getattr(usuario, "is_staff", False)
        )

    def queryset_stand_by(self, usuario):
        qs = (
            RegistroEstudoViabilidade.objects.select_related(
                "demanda",
                "demanda__autor",
                "unidade_administrativa",
                "registrado_por",
            )
            .order_by("-criado_em")
        )
        if getattr(usuario, "is_staff", False) or getattr(usuario, "perfil", None) == "GESTOR":
            return qs
        perfil = getattr(usuario, "perfil", None)
        if perfil == "PROTOCOLO":
            return qs
        if perfil == "SECRETARIA":
            oid = perm.orgao_usuario(usuario)
            if oid:
                return qs.filter(sinapse_orgao_id=int(oid))
            return qs.none()
        return qs.none()

    def buscar_referencias_stand_by(
        self,
        usuario,
        *,
        sinapse_servico_id: int | None,
        latitude: float | None = None,
        longitude: float | None = None,
        bairro: str | None = None,
        excluir_demanda_id: int | None = None,
        limite: int = 3,
    ) -> list[dict[str, Any]]:
        """Referências informativas para o executivo — não bloqueia novo protocolo."""
        if not self.usuario_ve_stand_by(usuario):
            return []
        if sinapse_servico_id is None:
            return []

        from core.services.copiloto_duplicidade_service import _locais_compatíveis

        refs: list[dict[str, Any]] = []
        qs = self.queryset_stand_by(usuario).filter(
            demanda__sinapse_servico_id=int(sinapse_servico_id),
            demanda__status="FINALIZADO",
        )[:40]
        for reg in qs:
            d = reg.demanda
            if excluir_demanda_id is not None and d.pk == int(excluir_demanda_id):
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
            refs.append(self.serializar_registro(reg, demanda=d))
            if len(refs) >= limite:
                break
        return refs

    @staticmethod
    def serializar_registro(
        registro: RegistroEstudoViabilidade,
        *,
        demanda: Demanda | None = None,
    ) -> dict[str, Any]:
        d = demanda or registro.demanda
        return {
            "id": registro.pk,
            "demanda_id": d.pk,
            "titulo": d.titulo,
            "status": d.status,
            "resultado_operacional": registro.resultado_operacional,
            "resultado_operacional_label": registro.get_resultado_operacional_display(),
            "motivo_nao_execucao": registro.motivo_nao_execucao,
            "motivo_nao_execucao_label": registro.get_motivo_nao_execucao_display()
            if registro.motivo_nao_execucao
            else "",
            "escopo_geografico": registro.escopo_geografico,
            "bairro": d.bairro,
            "logradouro": d.logradouro,
            "sinapse_servico_id": d.sinapse_servico_id,
            "sinapse_orgao_id": registro.sinapse_orgao_id,
            "pode_retomar": registro.pode_retomar,
            "criado_em": registro.criado_em.isoformat() if registro.criado_em else None,
            "mensagem_resumo": (
                f"Demanda #{d.pk} em stand-by (estudo/viabilidade): "
                f"{registro.get_resultado_operacional_display()}."
            ),
        }


def _request_data_dict(data) -> dict[str, Any]:
    if not data:
        return {}
    if hasattr(data, "dict"):
        return data.dict()
    if isinstance(data, dict):
        return data
    try:
        return dict(data)
    except (TypeError, ValueError):
        return {}


def registrar_resultado_operacional_request(request, demanda, usuario, *, parecer: str) -> None:
    """Aplica payload da requisição de conclusão operacional (retrocompatível)."""
    payload = EstudoViabilidadeService.parse_payload_request(
        _request_data_dict(getattr(request, "data", None))
    )
    if payload is None:
        payload = {
            "resultado_operacional": ResultadoOperacional.EXECUTADO,
            "registrar_stand_by": False,
        }
    try:
        EstudoViabilidadeService().registrar_conclusao_operacional(
            demanda,
            usuario,
            parecer=parecer,
            payload=payload,
        )
    except EstudoViabilidadeError as exc:
        raise ValueError(str(exc)) from exc


def registrar_resultado_operacional_se_processo_avancou(
    request, demanda, usuario, *, parecer: str, processo_avancou: bool
) -> None:
    """Scatter-gather — só persiste stand-by quando a secretaria enviou o payload."""
    if not processo_avancou:
        return
    payload = EstudoViabilidadeService.parse_payload_request(
        _request_data_dict(getattr(request, "data", None))
    )
    if payload is None:
        return
    try:
        EstudoViabilidadeService().registrar_conclusao_operacional(
            demanda,
            usuario,
            parecer=parecer,
            payload=payload,
        )
    except EstudoViabilidadeError as exc:
        raise ValueError(str(exc)) from exc
