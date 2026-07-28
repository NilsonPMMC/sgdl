"""Scatter-gather — coreografia livre de nós operacionais (EM_OPERACAO)."""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.utils import timezone

from core.models import Demanda, Tramitacao
from core.models_no_operacional import AcaoNoOperacional, NoOperacional, StatusNoOperacional
from core.models_operacional import ESTADO_AGUARDANDO_CONCLUSAO_FINAL, ESTADO_EM_OPERACAO
from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional
from core.services import operacional_permissions as perm
from integrations import sinapse_catalog

logger = logging.getLogger(__name__)


def _validar_texto_operacional(texto: str, *, rotulo: str = "descrição") -> str:
    limpo = (texto or "").strip()
    if len(limpo) < 10:
        raise ScatterGatherError(
            f"Informe a {rotulo} do despacho (mínimo 10 caracteres)."
        )
    return limpo


def _parse_destinos_scatter(data: dict) -> list[dict[str, Any]]:
    """Destinos operacionais — lista de órgão/setor ou legado único."""
    import json

    raw = data.get("destinos")
    if isinstance(raw, str) and raw.strip():
        raw = json.loads(raw)
    destinos: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            oid = item.get("secretaria_id") or item.get("destino_orgao_id")
            if oid in (None, ""):
                continue
            uids = item.get("unidade_administrativa_ids") or []
            if isinstance(uids, str):
                uids = [uids]
            uid_single = item.get("unidade_administrativa_id") or item.get("destino_setor_id")
            if uids:
                for uid in uids:
                    if uid in (None, ""):
                        continue
                    destinos.append(
                        {
                            "secretaria_id": int(oid),
                            "unidade_administrativa_id": int(uid),
                        }
                    )
            elif uid_single not in (None, ""):
                destinos.append(
                    {
                        "secretaria_id": int(oid),
                        "unidade_administrativa_id": int(uid_single),
                    }
                )
            else:
                destinos.append({"secretaria_id": int(oid)})
    if destinos:
        from core.services.demanda_despacho_destinos import validar_setores_obrigatorios_pernas

        validar_setores_obrigatorios_pernas(destinos)
        return destinos
    orgao = data.get("destino_orgao_id") or data.get("secretaria_id")
    if orgao in (None, ""):
        return []
    setor = data.get("destino_setor_id") or data.get("unidade_administrativa_id")
    entry = {"secretaria_id": int(orgao)}
    if setor not in (None, ""):
        entry["unidade_administrativa_id"] = int(setor)
    pernas = [entry]
    from core.services.demanda_despacho_destinos import validar_setores_obrigatorios_pernas

    validar_setores_obrigatorios_pernas(pernas)
    return pernas


class ScatterGatherError(Exception):
    """Erro de validação ou transição scatter-gather."""


class ScatterGatherPermissaoError(ScatterGatherError):
    """Usuário sem permissão para operar o nó."""


class ScatterGatherDestinoDuplicadoError(ScatterGatherError):
    """Destino já possui nó operacional aberto — exige confirmação explícita."""

    def __init__(self, conflitos: list[dict[str, Any]], message: str | None = None):
        self.conflitos = conflitos
        super().__init__(
            message
            or "Já existe encaminhamento operacional aberto para um ou mais destinos."
        )


def _chave_destino(orgao_id: int, setor_id: int | None) -> tuple[int, int | None]:
    return (int(orgao_id), int(setor_id) if setor_id not in (None, "") else None)


def _resumo_texto(descricao: str, max_len: int = 200) -> str:
    import re

    texto = re.sub(r"<[^>]+>", " ", descricao or "")
    texto = re.sub(r"\s+", " ", texto).strip()
    if len(texto) <= max_len:
        return texto
        return texto[: max_len - 1].rstrip() + "…"


def _nome_setor_unidade(uid: int | None) -> str | None:
    if uid in (None, ""):
        return None
    from core.models_unidade_administrativa import UnidadeAdministrativa

    ua = UnidadeAdministrativa.objects.filter(pk=int(uid)).first()
    if ua:
        return ua.sigla or ua.nome
    return None


def _enriquecer_destinos_scatter(destinos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriquecidos: list[dict[str, Any]] = []
    for dest in destinos:
        if not isinstance(dest, dict):
            continue
        item = dict(dest)
        sid = item.get("secretaria_id")
        if sid and not item.get("orgao_nome"):
            item["orgao_nome"] = sinapse_catalog.get_orgao_nome(int(sid)) or str(sid)
        uid = item.get("unidade_administrativa_id")
        if uid and not item.get("setor_nome"):
            item["setor_nome"] = _nome_setor_unidade(uid)
        enriquecidos.append(item)
    return enriquecidos


class NoOperacionalService:
    ESTADO_OPERACAO = ESTADO_EM_OPERACAO

    def nos_abertos_qs(self, demanda_id: int):
        return NoOperacional.objects.filter(
            demanda_id=int(demanda_id),
            status=StatusNoOperacional.ABERTO,
        )

    def demanda_ids_visiveis_para_usuario(self, orgao_id: int, usuario) -> list[int]:
        """Demandas com nó operacional aberto para o órgão (escopo de visibilidade).

        Não restringe por setor do usuário — a filtragem por UA ocorre em
        ``nos_abertos_do_usuario`` / ações scatter, não na listagem de demandas.
        """
        return list(
            NoOperacional.objects.filter(
                sinapse_orgao_id=int(orgao_id),
                status=StatusNoOperacional.ABERTO,
            )
            .values_list("demanda_id", flat=True)
            .distinct()
        )

    def contar_nos_ativos(self, demanda_id: int) -> int:
        return self.nos_abertos_qs(demanda_id).count()

    @transaction.atomic
    def sincronizar_contador_nos(self, demanda: Demanda) -> int:
        """Recalcula ``nos_ativos`` sob lock pessimista (anti race condition)."""
        locked = Demanda.objects.select_for_update().get(pk=demanda.pk)
        total = self.contar_nos_ativos(locked.pk)
        if locked.nos_ativos != total:
            locked.nos_ativos = total
            locked.save(update_fields=["nos_ativos"])
        return total

    def _exigir_em_operacao(self, demanda: Demanda) -> None:
        if demanda.status != self.ESTADO_OPERACAO:
            raise ScatterGatherError(
                "Operações scatter-gather só durante a etapa EM_OPERACAO (EM_EXECUCAO)."
            )

    def _usuario_pode_operar_no(self, usuario, no: NoOperacional) -> bool:
        return perm.usuario_pode_operar_no_scatter(usuario, no)

    def _ids_unidades_usuario(self, usuario) -> list[int]:
        from core.services.tramitacao_setor_service import UnidadeAdministrativaService

        return UnidadeAdministrativaService().ids_unidades_do_usuario(usuario)

    def _aplicar_filtro_setor_nos_qs(self, qs, usuario):
        if perm.usuario_e_gestor(usuario):
            from core.services.gestor_escopo import TIPO_GERAL, orgaos_escopo_gestor, tipo_gestor

            if tipo_gestor(usuario) == TIPO_GERAL:
                pass
            else:
                orgaos = orgaos_escopo_gestor(usuario)
                if not orgaos:
                    return qs.none()
                qs = qs.filter(sinapse_orgao_id__in=orgaos)
        else:
            orgao = perm.orgao_usuario(usuario)
            if orgao is None:
                return qs.none()
            qs = qs.filter(sinapse_orgao_id=int(orgao))
        ids_ua = self._ids_unidades_usuario(usuario)
        if ids_ua:
            qs = qs.filter(unidade_administrativa_id__in=ids_ua)
        return qs

    def _particionar_nos_por_setor(
        self, nos: list[NoOperacional]
    ) -> list[list[NoOperacional]]:
        buckets: dict[int | None, list[NoOperacional]] = {}
        for no in nos:
            buckets.setdefault(no.unidade_administrativa_id, []).append(no)
        return list(buckets.values())

    def _resolver_unidade(self, orgao_id: int, unidade_id: int | None):
        if unidade_id in (None, ""):
            return None
        from core.models_unidade_administrativa import UnidadeAdministrativa

        return UnidadeAdministrativa.objects.filter(
            pk=int(unidade_id), ativo=True, sinapse_orgao_id=int(orgao_id)
        ).first()

    def nos_abertos_no_destino(
        self,
        demanda_id: int,
        orgao_id: int,
        setor_id: int | None,
    ) -> list[NoOperacional]:
        qs = (
            self.nos_abertos_qs(demanda_id)
            .filter(sinapse_orgao_id=int(orgao_id))
            .select_related(
                "unidade_administrativa",
                "responsavel_abertura",
                "abertura_tramitacao",
                "parent",
            )
        )
        if setor_id in (None, ""):
            qs = qs.filter(unidade_administrativa_id__isnull=True)
        else:
            qs = qs.filter(unidade_administrativa_id=int(setor_id))
        return list(qs.order_by("aberto_em", "pk"))

    def verificar_conflitos_destinos(
        self,
        demanda: Demanda,
        destinos: list[dict[str, Any]],
        *,
        no_operado_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Detecta nós abertos no mesmo órgão × setor dos destinos informados."""
        conflitos: list[dict[str, Any]] = []
        vistos: set[tuple[int, int | None]] = set()
        for dest in destinos:
            oid = int(dest["secretaria_id"])
            uid = dest.get("unidade_administrativa_id")
            setor_id = int(uid) if uid not in (None, "") else None
            chave = _chave_destino(oid, setor_id)
            if chave in vistos:
                continue
            vistos.add(chave)
            existentes = [
                n
                for n in self.nos_abertos_no_destino(demanda.pk, oid, setor_id)
                if no_operado_id is None or n.pk != int(no_operado_id)
            ]
            if not existentes:
                continue
            orgao_nome = sinapse_catalog.get_orgao_nome(oid) or str(oid)
            setor_nome = ""
            if setor_id:
                unidade = self._resolver_unidade(oid, setor_id)
                if unidade:
                    setor_nome = unidade.sigla or unidade.nome
            conflitos.append(
                {
                    "secretaria_id": oid,
                    "orgao_nome": orgao_nome,
                    "unidade_administrativa_id": setor_id,
                    "setor_nome": setor_nome,
                    "nos_existentes": [self.serializar_no(n) for n in existentes],
                }
            )
        return conflitos

    def listar_destinos_nos_ativos(self, demanda: Demanda) -> list[dict[str, Any]]:
        """Agrupa nós abertos por destino — usado para aviso/filtro no despacho scatter."""
        agrupado: dict[tuple[int, int | None], dict[str, Any]] = {}
        for no in self.nos_abertos_qs(demanda.pk).select_related(
            "unidade_administrativa",
            "responsavel_abertura",
            "abertura_tramitacao",
            "parent",
        ):
            chave = _chave_destino(no.sinapse_orgao_id, no.unidade_administrativa_id)
            if chave not in agrupado:
                orgao_nome = (
                    sinapse_catalog.get_orgao_nome(int(no.sinapse_orgao_id))
                    or str(no.sinapse_orgao_id)
                )
                setor_nome = ""
                if no.unidade_administrativa_id and no.unidade_administrativa:
                    u = no.unidade_administrativa
                    setor_nome = u.sigla or u.nome
                agrupado[chave] = {
                    "secretaria_id": int(no.sinapse_orgao_id),
                    "orgao_nome": orgao_nome,
                    "unidade_administrativa_id": no.unidade_administrativa_id,
                    "setor_nome": setor_nome,
                    "nos": [],
                }
            agrupado[chave]["nos"].append(self.serializar_no(no))
        return list(agrupado.values())

    def _origem_label_no(self, no: NoOperacional) -> str:
        meta = no.metadata if isinstance(no.metadata, dict) else {}
        origem = meta.get("origem")
        if origem in ("bootstrap_perna", "bootstrap_sem_pernas"):
            return "Via Protocolo"
        orgao_abridor_id = meta.get("orgao_abridor_id")
        if orgao_abridor_id not in (None, ""):
            nome = sinapse_catalog.get_orgao_nome(int(orgao_abridor_id))
            return f"Via {nome}" if nome else f"Via órgão #{orgao_abridor_id}"
        if no.parent_id:
            return "Via despacho operacional"
        return "Abertura operacional"

    def _resumo_abertura_no(self, no: NoOperacional) -> str:
        if no.abertura_tramitacao_id and no.abertura_tramitacao:
            return _resumo_texto(no.abertura_tramitacao.descricao)
        meta = no.metadata if isinstance(no.metadata, dict) else {}
        if meta.get("origem") in ("bootstrap_perna", "bootstrap_sem_pernas"):
            tram = (
                no.demanda.tramitacoes.filter(tipo="DESPACHO")
                .order_by("-timestamp")
                .first()
            )
            if tram:
                return _resumo_texto(tram.descricao)
        return ""

    def _payload_evento(
        self,
        *,
        acao: str,
        no: NoOperacional,
        no_filho: NoOperacional | None = None,
        nos_ativos: int,
        destino_orgao_id: int | None = None,
        destino_setor_id: int | None = None,
        destinos: list[dict[str, Any]] | None = None,
        no_filhos_ids: list[int] | None = None,
        observacao: str = "",
    ) -> dict[str, Any]:
        orgao_nome = sinapse_catalog.get_orgao_nome(int(no.sinapse_orgao_id)) or str(no.sinapse_orgao_id)
        payload: dict[str, Any] = {
            "acao_no": acao,
            "no_id": no.pk,
            "no_pai_id": no.parent_id,
            "no_status": no.status,
            "orgao_id": int(no.sinapse_orgao_id),
            "orgao_nome": orgao_nome,
            "setor_id": no.unidade_administrativa_id,
            "nos_ativos": nos_ativos,
            "scatter_gather": True,
        }
        if destinos:
            destinos = _enriquecer_destinos_scatter(destinos)
            payload["destinos"] = destinos
            if destinos:
                primeiro = destinos[0]
                destino_orgao_id = primeiro.get("secretaria_id")
                destino_setor_id = primeiro.get("unidade_administrativa_id")
        if destino_orgao_id is not None:
            payload["destino_orgao_id"] = int(destino_orgao_id)
            payload["destino_orgao_nome"] = (
                sinapse_catalog.get_orgao_nome(int(destino_orgao_id)) or str(destino_orgao_id)
            )
        if destino_setor_id is not None:
            payload["destino_setor_id"] = int(destino_setor_id)
        if no_filho is not None:
            payload["no_filho_id"] = no_filho.pk
            payload["no_filho_orgao_id"] = int(no_filho.sinapse_orgao_id)
        if no_filhos_ids:
            payload["no_filhos_ids"] = no_filhos_ids
        if observacao.strip():
            payload["observacao"] = observacao.strip()
        return payload

    def _scatter_aguarda_validacao_gestor(self, assinatura_ctx: dict[str, Any] | None) -> bool:
        return bool(
            assinatura_ctx
            and assinatura_ctx.get("assinar")
            and assinatura_ctx.get("obrigatoria")
        )

    def _registrar_assinatura_scatter_se_solicitada(
        self,
        demanda: Demanda,
        tram: Tramitacao,
        usuario,
        acao: str,
        assinatura_ctx: dict[str, Any] | None,
        request=None,
    ):
        if not assinatura_ctx or not assinatura_ctx.get("assinar"):
            return None
        from core.services.assinatura_eletronica_service import AssinaturaEletronicaService

        return AssinaturaEletronicaService().registrar_assinatura_operacao_scatter(
            demanda,
            tram,
            usuario,
            acao=acao,
            declaracao=assinatura_ctx.get("declaracao") or "",
            contexto_extra=assinatura_ctx,
            request=request,
        )

    def _unidade_origem_operador(self, usuario):
        from core.services.tramitacao_setor_service import UnidadeAdministrativaService

        return UnidadeAdministrativaService().unidade_principal_usuario(usuario)

    def _registrar_evento(
        self,
        demanda: Demanda,
        usuario,
        *,
        descricao: str,
        metadata: dict[str, Any],
        no: NoOperacional | None = None,
    ) -> Tramitacao:
        unidade_destino = None
        if no is not None and no.unidade_administrativa_id:
            unidade_destino = no.unidade_administrativa
        return Tramitacao.objects.create(
            demanda=demanda,
            responsavel=usuario,
            tipo="OPERACAO_NO",
            descricao=descricao,
            metadata=metadata,
            unidade_origem=self._unidade_origem_operador(usuario),
            unidade_destino=unidade_destino,
        )

    def _texto_abertura_bootstrap(self, demanda: Demanda, no: NoOperacional) -> str:
        tram_despacho = (
            demanda.tramitacoes.filter(tipo="DESPACHO").order_by("-timestamp").first()
        )
        if tram_despacho and (tram_despacho.descricao or "").strip():
            resumo = _resumo_texto(tram_despacho.descricao)
            if len(resumo) >= 10:
                return resumo
        orgao = sinapse_catalog.get_orgao_nome(int(no.sinapse_orgao_id)) or str(no.sinapse_orgao_id)
        setor = ""
        if no.unidade_administrativa_id and no.unidade_administrativa:
            setor = no.unidade_administrativa.sigla or no.unidade_administrativa.nome
        if setor:
            return f"Abertura operacional via protocolo — {orgao} › {setor}."
        return f"Abertura operacional via protocolo — {orgao}."

    def _registrar_abertura_bootstrap(
        self,
        demanda: Demanda,
        no: NoOperacional,
        usuario,
    ) -> Tramitacao:
        texto = self._texto_abertura_bootstrap(demanda, no)
        tram = self._registrar_evento(
            demanda,
            usuario,
            descricao=texto,
            metadata=self._payload_evento(
                acao="ABERTURA_NO",
                no=no,
                nos_ativos=self.contar_nos_ativos(demanda.pk),
            ),
            no=no,
        )
        no.abertura_tramitacao = tram
        no.save(update_fields=["abertura_tramitacao"])
        return tram

    def _registrar_encaminhamento_filho(
        self,
        demanda: Demanda,
        filho: NoOperacional,
        usuario,
        *,
        descricao: str,
        observacao: str,
        nos_ativos: int,
    ) -> Tramitacao:
        tram = self._registrar_evento(
            demanda,
            usuario,
            descricao=descricao,
            metadata=self._payload_evento(
                acao="ENCAMINHAMENTO_NO",
                no=filho,
                nos_ativos=nos_ativos,
                observacao=observacao,
            ),
            no=filho,
        )
        filho.abertura_tramitacao = tram
        filho.save(update_fields=["abertura_tramitacao"])
        return tram

    @transaction.atomic
    def _criar_no_filho(
        self,
        demanda: Demanda,
        parent: NoOperacional,
        *,
        destino_orgao_id: int,
        destino_setor_id: int | None,
        usuario,
        tramitacao: Tramitacao,
    ) -> NoOperacional:
        unidade = self._resolver_unidade(destino_orgao_id, destino_setor_id)
        return NoOperacional.objects.create(
            demanda=demanda,
            parent=parent,
            sinapse_orgao_id=int(destino_orgao_id),
            unidade_administrativa=unidade,
            status=StatusNoOperacional.ABERTO,
            responsavel_abertura=usuario,
            abertura_tramitacao=tramitacao,
            metadata={
                "origem_acao": AcaoNoOperacional.DESPACHAR,
                "no_pai_id": parent.pk,
                "orgao_abridor_id": perm.orgao_usuario(usuario),
            },
        )

    @transaction.atomic
    def _encerrar_no(
        self,
        demanda: Demanda,
        no: NoOperacional,
        usuario,
        *,
        acao: str,
        tramitacao: Tramitacao,
        observacao: str = "",
        permitir_filhos_abertos: bool = False,
    ) -> NoOperacional:
        if no.status != StatusNoOperacional.ABERTO:
            raise ScatterGatherError("Este nó já foi encerrado.")

        if not permitir_filhos_abertos:
            filhos_internos = self._filhos_abertos_internos(no)
            if filhos_internos:
                pendencias = self._rotular_filhos(filhos_internos)
                raise ScatterGatherError(
                    "Encerre ou conclua os encaminhamentos internos antes de encerrar este nó. "
                    f"Pendentes na mesma secretaria: {pendencias}."
                )

        agora = timezone.now()
        no.status = StatusNoOperacional.CONCLUIDO
        no.concluido_em = agora
        no.encerramento_tramitacao = tramitacao
        meta = dict(no.metadata or {})
        meta["acao_encerramento"] = acao
        if observacao.strip():
            meta["observacao_encerramento"] = observacao.strip()
        no.metadata = meta
        no.save(
            update_fields=[
                "status",
                "concluido_em",
                "encerramento_tramitacao",
                "metadata",
            ]
        )

        nos_ativos = self.sincronizar_contador_nos(demanda)
        self._concluir_perna_orgao_sem_nos_abertos(
            demanda, int(no.sinapse_orgao_id), tramitacao
        )
        from core.services.notificacao_service import NotificacaoService

        NotificacaoService().notificar_encerramento_setor(
            demanda,
            no,
            observacao=observacao,
            tramitacao=tramitacao,
        )
        self._avaliar_gather(demanda, usuario, nos_ativos=nos_ativos)
        return no

    def _concluir_perna_orgao_sem_nos_abertos(
        self,
        demanda: Demanda,
        orgao_id: int,
        tramitacao: Tramitacao,
    ) -> None:
        """Conclui perna do órgão quando não restam nós abertos dele (gather parcial)."""
        if self.nos_abertos_qs(demanda.pk).filter(sinapse_orgao_id=int(orgao_id)).exists():
            return
        from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional
        from core.services.perna_operacional_service import PernaOperacionalService

        svc = PernaOperacionalService()
        for perna in PernaOperacional.objects.filter(
            demanda_id=demanda.pk,
            sinapse_orgao_id=int(orgao_id),
            status__in=StatusPernaOperacional.ATIVOS,
        ):
            svc.marcar_concluida(perna, tramitacao)

    def sincronizar_pernas_scatter_obsoletas(
        self,
        *,
        demanda_id: int | None = None,
        cluster_id: int | None = None,
        dry_run: bool = False,
    ) -> int:
        """Conclui pernas ativas cujo órgão já encerrou todos os nós scatter."""
        from core.services.perna_operacional_service import PernaOperacionalService

        if demanda_id is None and cluster_id is None:
            return 0

        demanda_ids: list[int]
        if demanda_id is not None:
            demanda_ids = [int(demanda_id)]
        else:
            demanda_ids = list(
                Demanda.objects.filter(cluster_id=int(cluster_id)).values_list(
                    "pk", flat=True
                )
            )

        svc = PernaOperacionalService()
        corrigidas = 0
        for did in demanda_ids:
            pernas = PernaOperacional.objects.filter(
                demanda_id=int(did),
                status__in=StatusPernaOperacional.ATIVOS,
            )
            for perna in pernas:
                oid = int(perna.sinapse_orgao_id)
                if self.nos_abertos_qs(int(did)).filter(sinapse_orgao_id=oid).exists():
                    continue
                if not NoOperacional.objects.filter(
                    demanda_id=int(did),
                    sinapse_orgao_id=oid,
                ).exists():
                    continue
                ultimo_no = (
                    NoOperacional.objects.filter(
                        demanda_id=int(did),
                        sinapse_orgao_id=oid,
                        status=StatusNoOperacional.CONCLUIDO,
                    )
                    .order_by("-concluido_em", "-pk")
                    .first()
                )
                tram = (
                    ultimo_no.encerramento_tramitacao
                    if ultimo_no and ultimo_no.encerramento_tramitacao_id
                    else None
                )
                if dry_run:
                    corrigidas += 1
                    continue
                if tram:
                    svc.marcar_concluida(perna, tram)
                else:
                    perna.status = StatusPernaOperacional.CONCLUIDA
                    perna.save(update_fields=["status", "atualizada_em"])
                corrigidas += 1
                logger.info(
                    "Perna scatter obsoleta concluída — perna=%s demanda=%s orgao=%s",
                    perna.pk,
                    did,
                    oid,
                )
        return corrigidas

    def _avaliar_gather(self, demanda: Demanda, usuario, *, nos_ativos: int) -> None:
        if nos_ativos > 0:
            return
        locked = Demanda.objects.select_for_update().get(pk=demanda.pk)
        if locked.status == self.ESTADO_OPERACAO:
            locked.status = ESTADO_AGUARDANDO_CONCLUSAO_FINAL
            locked.save(update_fields=["status"])
            logger.info(
                "Gather scatter-gather — demanda pk=%s → %s (sem tramitação automática)",
                locked.pk,
                ESTADO_AGUARDANDO_CONCLUSAO_FINAL,
            )
            from core.services.notificacao_service import NotificacaoService

            NotificacaoService().notificar_todos_nos_encerrados(locked)
            from core.services.cluster_aderencia_service import ClusterAderenciaService

            ClusterAderenciaService().sincronizar_seguidoras_integradas(locked)
        self.sincronizar_pernas_gather(locked)

    def processo_scatter_gather(self, demanda: Demanda) -> bool:
        """Processo operacional com nós scatter-gather (substitui conclusão parcial legada)."""
        if demanda.inicio_execucao_automatico:
            return True
        return demanda.tramitacoes.filter(
            tipo="OPERACAO_NO",
            metadata__scatter_gather=True,
        ).exists()

    def _tramitacao_encerramento_orgao(
        self, demanda: Demanda, orgao_id: int
    ) -> Tramitacao | None:
        return (
            demanda.tramitacoes.filter(
                tipo="OPERACAO_NO",
                metadata__scatter_gather=True,
                metadata__acao_no__in=(
                    AcaoNoOperacional.ENCERRAR,
                    AcaoNoOperacional.DESPACHAR_ENCERRAR,
                ),
                metadata__orgao_id=int(orgao_id),
            )
            .order_by("-timestamp")
            .first()
        )

    @transaction.atomic
    def sincronizar_pernas_gather(self, demanda: Demanda) -> int:
        """Marca pernas operacionais concluídas quando o gather scatter encerrou todos os nós."""
        if self.contar_nos_ativos(demanda.pk) > 0:
            return 0
        from core.services.perna_operacional_service import PernaOperacionalService

        svc = PernaOperacionalService()
        atualizadas = 0
        for perna in PernaOperacional.objects.filter(
            demanda_id=demanda.pk,
            status__in=StatusPernaOperacional.ATIVOS,
        ):
            tram = self._tramitacao_encerramento_orgao(demanda, int(perna.sinapse_orgao_id))
            if not tram:
                tram = (
                    demanda.tramitacoes.filter(
                        tipo="OPERACAO_NO",
                        metadata__scatter_gather=True,
                        metadata__orgao_id=int(perna.sinapse_orgao_id),
                    )
                    .order_by("-timestamp")
                    .first()
                )
            if tram:
                svc.marcar_concluida(perna, tram)
                atualizadas += 1
        if atualizadas:
            logger.info(
                "Scatter-gather — demanda pk=%s: %s perna(s) sincronizada(s) como CONCLUIDA.",
                demanda.pk,
                atualizadas,
            )
        return atualizadas

    @transaction.atomic
    def reparar_unidades_sem_setor(self, demanda: Demanda) -> int:
        """
        Corrige pernas/nós abertos sem setor quando o órgão coincide com a demanda
        ou com o setor configurado na carta (Gestão de fluxo).
        """
        from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional
        from core.services.carta_setor_service import CartaSetorService

        carta_setor = CartaSetorService()
        corrigidos = 0

        for perna in PernaOperacional.objects.filter(
            demanda_id=demanda.pk,
            unidade_administrativa_id__isnull=True,
            status__in=StatusPernaOperacional.ATIVOS,
        ):
            ua = carta_setor.resolver_unidade_para_orgao(demanda, int(perna.sinapse_orgao_id))
            if ua:
                perna.unidade_administrativa = ua
                perna.save(update_fields=["unidade_administrativa"])
                corrigidos += 1

        for no in (
            self.nos_abertos_qs(demanda.pk)
            .filter(unidade_administrativa_id__isnull=True)
            .select_related("perna_operacional", "perna_operacional__unidade_administrativa")
        ):
            ua = None
            if no.perna_operacional_id and no.perna_operacional.unidade_administrativa_id:
                ua = no.perna_operacional.unidade_administrativa
            if not ua:
                ua = carta_setor.resolver_unidade_para_orgao(demanda, int(no.sinapse_orgao_id))
            if ua:
                no.unidade_administrativa = ua
                no.save(update_fields=["unidade_administrativa"])
                corrigidos += 1

        if corrigidos:
            logger.info(
                "Reparo setor scatter-gather demanda pk=%s — %s vínculo(s) corrigido(s).",
                demanda.pk,
                corrigidos,
            )
        return corrigidos

    @transaction.atomic
    def reparar_gather_pendente(self, demanda: Demanda, usuario=None) -> bool:
        """
        Consolida gather quando todos os nós foram encerrados mas o status/pernas
        não refletem a conclusão operacional (ex.: pernas legadas ainda EM_EXECUCAO).
        """
        if not self.processo_scatter_gather(demanda):
            return False
        locked = Demanda.objects.select_for_update().get(pk=demanda.pk)
        total = self.sincronizar_contador_nos(locked)
        locked.refresh_from_db()
        if total > 0:
            return False
        if locked.status not in (self.ESTADO_OPERACAO, ESTADO_AGUARDANDO_CONCLUSAO_FINAL):
            self.sincronizar_pernas_gather(locked)
            return False
        if locked.status == ESTADO_AGUARDANDO_CONCLUSAO_FINAL:
            return self.sincronizar_pernas_gather(locked) > 0
        self._avaliar_gather(locked, usuario, nos_ativos=0)
        return True

    @transaction.atomic
    def bootstrap_nos_iniciais(self, demanda: Demanda, usuario) -> list[NoOperacional]:
        """
        Cria nós raiz a partir das pernas do despacho ao entrar em EM_OPERACAO.
        Idempotente: não duplica se já existirem nós ativos.
        """
        if self.nos_abertos_qs(demanda.pk).exists():
            return list(self.nos_abertos_qs(demanda.pk))

        criados: list[NoOperacional] = []
        pernas = PernaOperacional.objects.filter(
            demanda_id=demanda.pk,
            status__in=StatusPernaOperacional.ATIVOS,
        ).exclude(status=StatusPernaOperacional.CANCELADA)

        if not pernas.exists():
            orgao = demanda.sinapse_orgao_lider_id or demanda.sinapse_orgao_id
            if orgao:
                no = NoOperacional.objects.create(
                    demanda=demanda,
                    sinapse_orgao_id=int(orgao),
                    unidade_administrativa=demanda.unidade_administrativa,
                    status=StatusNoOperacional.ABERTO,
                    responsavel_abertura=usuario,
                    metadata={"origem": "bootstrap_sem_pernas"},
                )
                criados.append(no)
        else:
            from core.services.carta_setor_service import CartaSetorService

            carta_setor = CartaSetorService()
            for perna in pernas.order_by("ordem", "pk"):
                unidade = perna.unidade_administrativa
                if not unidade:
                    unidade = carta_setor.resolver_unidade_para_orgao(
                        demanda, int(perna.sinapse_orgao_id)
                    )
                no = NoOperacional.objects.create(
                    demanda=demanda,
                    perna_operacional=perna,
                    sinapse_orgao_id=int(perna.sinapse_orgao_id),
                    unidade_administrativa=unidade,
                    status=StatusNoOperacional.ABERTO,
                    responsavel_abertura=usuario,
                    metadata={"origem": "bootstrap_perna", "perna_id": perna.pk},
                )
                criados.append(no)

        for no in criados:
            self._registrar_abertura_bootstrap(demanda, no, usuario)

        total = self.sincronizar_contador_nos(demanda)
        logger.info(
            "Bootstrap scatter-gather demanda pk=%s — %s nó(s), nos_ativos=%s",
            demanda.pk,
            len(criados),
            total,
        )
        if criados:
            from core.services.notificacao_service import NotificacaoService

            NotificacaoService().notificar_despacho_inicial_setores(demanda)
        return criados

    @transaction.atomic
    def _aplicar_despachar_destinos(
        self,
        demanda: Demanda,
        no_id: int,
        usuario,
        *,
        destinos: list[dict[str, Any]],
        observacao: str,
        descricao: str,
        acao: str,
        encerrar_pai: bool,
        arquivos_anexos: list | None = None,
        confirmar_destino_duplicado: bool = False,
        assinatura_ctx: dict[str, Any] | None = None,
        request=None,
    ) -> dict[str, Any]:
        self._exigir_em_operacao(demanda)
        Demanda.objects.select_for_update().get(pk=demanda.pk)
        no = NoOperacional.objects.select_for_update().get(pk=int(no_id), demanda_id=demanda.pk)
        if not self._usuario_pode_operar_no(usuario, no):
            raise ScatterGatherPermissaoError("Sem permissão para operar este nó.")

        destinos_payload = [
            {
                "secretaria_id": int(d["secretaria_id"]),
                "unidade_administrativa_id": d.get("unidade_administrativa_id"),
            }
            for d in destinos
        ]
        conflitos = self.verificar_conflitos_destinos(
            demanda, destinos_payload, no_operado_id=no_id
        )
        if conflitos and not confirmar_destino_duplicado:
            raise ScatterGatherDestinoDuplicadoError(conflitos)
        nos_antes = self.contar_nos_ativos(demanda.pk)
        tram = self._registrar_evento(
            demanda,
            usuario,
            descricao=descricao,
            metadata=self._payload_evento(
                acao=acao,
                no=no,
                nos_ativos=nos_antes,
                destinos=destinos_payload,
                observacao=observacao,
            ),
        )
        if arquivos_anexos:
            from core.services.tramitacao_anexo_service import anexar_arquivos_tramitacao

            anexar_arquivos_tramitacao(tram, arquivos_anexos, copiar=False)

        filhos: list[NoOperacional] = []
        for dest in destinos:
            oid = int(dest["secretaria_id"])
            uid = dest.get("unidade_administrativa_id")
            setor_id = int(uid) if uid not in (None, "") else None
            filhos.append(
                self._criar_no_filho(
                    demanda,
                    no,
                    destino_orgao_id=oid,
                    destino_setor_id=setor_id,
                    usuario=usuario,
                    tramitacao=tram,
                )
            )

        nos_pos_filhos = self.contar_nos_ativos(demanda.pk)
        for filho in filhos:
            self._registrar_encaminhamento_filho(
                demanda,
                filho,
                usuario,
                descricao=descricao,
                observacao=observacao,
                nos_ativos=nos_pos_filhos,
            )

        if encerrar_pai:
            if not self._scatter_aguarda_validacao_gestor(assinatura_ctx):
                self._encerrar_no(
                    demanda,
                    no,
                    usuario,
                    acao=acao,
                    tramitacao=tram,
                    observacao=observacao,
                    permitir_filhos_abertos=True,
                )

        nos_depois = self.sincronizar_contador_nos(demanda)
        tram.metadata = self._payload_evento(
            acao=acao,
            no=no,
            no_filho=filhos[0] if len(filhos) == 1 else None,
            no_filhos_ids=[f.pk for f in filhos],
            nos_ativos=nos_depois,
            destinos=destinos_payload,
            observacao=observacao,
        )
        tram.save(update_fields=["metadata"])
        demanda.refresh_from_db()

        assinatura = self._registrar_assinatura_scatter_se_solicitada(
            demanda, tram, usuario, acao, assinatura_ctx, request=request
        )

        resultado: dict[str, Any] = {
            "acao": acao,
            "no": no,
            "nos_ativos": demanda.nos_ativos,
            "tramitacao": tram,
            "tramitacao_id": tram.pk,
        }
        if assinatura is not None:
            resultado["assinatura_registrada"] = {
                "codigo_validacao": assinatura.codigo_validacao,
                "tramitacao_id": tram.pk,
            }
        if self._scatter_aguarda_validacao_gestor(assinatura_ctx) and encerrar_pai:
            resultado["aguardando_validacao_gestor"] = True
        if len(filhos) == 1:
            resultado["no_filho"] = filhos[0]
        else:
            resultado["nos_filhos"] = filhos
        if encerrar_pai and not (
            self._scatter_aguarda_validacao_gestor(assinatura_ctx)
        ):
            resultado["processo_avancou"] = demanda.status == ESTADO_AGUARDANDO_CONCLUSAO_FINAL
        if filhos:
            from core.services.notificacao_service import NotificacaoService

            origem = ""
            if no.unidade_administrativa:
                origem = no.unidade_administrativa.sigla or no.unidade_administrativa.nome
            NotificacaoService().notificar_despacho_operacional(
                demanda,
                destinos=destinos,
                origem_setor=origem,
            )
        return resultado

    @transaction.atomic
    def aplicar_despachar_destinos(
        self,
        demanda: Demanda,
        no_id: int,
        usuario,
        *,
        destinos: list[dict[str, Any]],
        observacao: str = "",
        arquivos_anexos: list | None = None,
        confirmar_destino_duplicado: bool = False,
        assinatura_ctx: dict[str, Any] | None = None,
        request=None,
    ) -> dict[str, Any]:
        if not destinos:
            raise ScatterGatherError("Informe ao menos um destino para o despacho.")
        descricao = _validar_texto_operacional(observacao, rotulo="descrição")
        return self._aplicar_despachar_destinos(
            demanda,
            no_id,
            usuario,
            destinos=destinos,
            observacao=observacao,
            descricao=descricao,
            acao=AcaoNoOperacional.DESPACHAR,
            encerrar_pai=False,
            arquivos_anexos=arquivos_anexos,
            confirmar_destino_duplicado=confirmar_destino_duplicado,
            assinatura_ctx=assinatura_ctx,
            request=request,
        )

    @transaction.atomic
    def aplicar_despachar(
        self,
        demanda: Demanda,
        no_id: int,
        usuario,
        *,
        destino_orgao_id: int,
        destino_setor_id: int | None = None,
        observacao: str = "",
        arquivos_anexos: list | None = None,
        confirmar_destino_duplicado: bool = False,
        assinatura_ctx: dict[str, Any] | None = None,
        request=None,
    ) -> dict[str, Any]:
        destinos = [{"secretaria_id": int(destino_orgao_id)}]
        if destino_setor_id not in (None, ""):
            destinos[0]["unidade_administrativa_id"] = int(destino_setor_id)
        descricao = _validar_texto_operacional(observacao, rotulo="descrição")
        return self._aplicar_despachar_destinos(
            demanda,
            no_id,
            usuario,
            destinos=destinos,
            observacao=observacao,
            descricao=descricao,
            acao=AcaoNoOperacional.DESPACHAR,
            encerrar_pai=False,
            arquivos_anexos=arquivos_anexos,
            confirmar_destino_duplicado=confirmar_destino_duplicado,
            assinatura_ctx=assinatura_ctx,
            request=request,
        )

    @transaction.atomic
    def aplicar_despachar_encerrar(
        self,
        demanda: Demanda,
        no_id: int,
        usuario,
        *,
        destino_orgao_id: int | None = None,
        destino_setor_id: int | None = None,
        destinos: list[dict[str, Any]] | None = None,
        observacao: str = "",
        arquivos_anexos: list | None = None,
        confirmar_destino_duplicado: bool = False,
        assinatura_ctx: dict[str, Any] | None = None,
        request=None,
    ) -> dict[str, Any]:
        lista = destinos or []
        if not lista and destino_orgao_id not in (None, ""):
            entry: dict[str, Any] = {"secretaria_id": int(destino_orgao_id)}
            if destino_setor_id not in (None, ""):
                entry["unidade_administrativa_id"] = int(destino_setor_id)
            lista = [entry]
        if not lista:
            raise ScatterGatherError("Informe ao menos um destino para despachar e encerrar.")
        descricao = _validar_texto_operacional(observacao, rotulo="descrição")
        return self._aplicar_despachar_destinos(
            demanda,
            no_id,
            usuario,
            destinos=lista,
            observacao=observacao,
            descricao=descricao,
            acao=AcaoNoOperacional.DESPACHAR_ENCERRAR,
            encerrar_pai=True,
            arquivos_anexos=arquivos_anexos,
            confirmar_destino_duplicado=confirmar_destino_duplicado,
            assinatura_ctx=assinatura_ctx,
            request=request,
        )

    @transaction.atomic
    def aplicar_encerrar(
        self,
        demanda: Demanda,
        no_id: int,
        usuario,
        *,
        observacao: str = "",
        arquivos_anexos: list | None = None,
        assinatura_ctx: dict[str, Any] | None = None,
        request=None,
    ) -> dict[str, Any]:
        self._exigir_em_operacao(demanda)
        Demanda.objects.select_for_update().get(pk=demanda.pk)
        no = NoOperacional.objects.select_for_update().get(pk=int(no_id), demanda_id=demanda.pk)
        if not self._usuario_pode_operar_no(usuario, no):
            raise ScatterGatherPermissaoError("Sem permissão para encerrar este nó.")

        orgao_nome = sinapse_catalog.get_orgao_nome(int(no.sinapse_orgao_id)) or str(no.sinapse_orgao_id)
        descricao = _validar_texto_operacional(observacao, rotulo="descrição do encerramento")

        tram = self._registrar_evento(
            demanda,
            usuario,
            descricao=descricao,
            metadata=self._payload_evento(
                acao=AcaoNoOperacional.ENCERRAR,
                no=no,
                nos_ativos=self.contar_nos_ativos(demanda.pk),
                observacao=observacao,
            ),
        )
        if arquivos_anexos:
            from core.services.tramitacao_anexo_service import anexar_arquivos_tramitacao

            anexar_arquivos_tramitacao(tram, arquivos_anexos, copiar=False)

        deferir_encerramento = self._scatter_aguarda_validacao_gestor(assinatura_ctx)
        if not deferir_encerramento:
            self._encerrar_no(
                demanda,
                no,
                usuario,
                acao=AcaoNoOperacional.ENCERRAR,
                tramitacao=tram,
                observacao=observacao,
            )
        nos_depois = self.sincronizar_contador_nos(demanda)
        tram.metadata = self._payload_evento(
            acao=AcaoNoOperacional.ENCERRAR,
            no=no,
            nos_ativos=nos_depois,
            observacao=observacao,
        )
        tram.save(update_fields=["metadata"])
        demanda.refresh_from_db()

        assinatura = self._registrar_assinatura_scatter_se_solicitada(
            demanda,
            tram,
            usuario,
            AcaoNoOperacional.ENCERRAR,
            assinatura_ctx,
            request=request,
        )

        resultado: dict[str, Any] = {
            "acao": AcaoNoOperacional.ENCERRAR,
            "no": no,
            "nos_ativos": demanda.nos_ativos,
            "tramitacao": tram,
            "tramitacao_id": tram.pk,
        }
        if deferir_encerramento:
            resultado["aguardando_validacao_gestor"] = True
        else:
            resultado["processo_avancou"] = demanda.status == ESTADO_AGUARDANDO_CONCLUSAO_FINAL
        if assinatura is not None:
            resultado["assinatura_registrada"] = {
                "codigo_validacao": assinatura.codigo_validacao,
                "tramitacao_id": tram.pk,
            }
        return resultado

    @transaction.atomic
    def finalizar_encerrar_apos_gestor(
        self,
        demanda: Demanda,
        no: NoOperacional,
        tram: Tramitacao,
        usuario,
        *,
        observacao: str = "",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        demanda = Demanda.objects.select_for_update().get(pk=demanda.pk)
        no = NoOperacional.objects.select_for_update().get(pk=no.pk, demanda_id=demanda.pk)
        self._encerrar_no(
            demanda,
            no,
            usuario,
            acao=AcaoNoOperacional.ENCERRAR,
            tramitacao=tram,
            observacao=observacao,
        )
        demanda.refresh_from_db()
        processo_avancou = demanda.status == ESTADO_AGUARDANDO_CONCLUSAO_FINAL
        self._aplicar_resultado_operacional_payload(payload, demanda, usuario, observacao, processo_avancou)
        return {
            "no": no,
            "processo_avancou": processo_avancou,
            "nos_ativos": demanda.nos_ativos,
        }

    @transaction.atomic
    def finalizar_despachar_encerrar_apos_gestor(
        self,
        demanda: Demanda,
        no_id: int,
        usuario,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        demanda = Demanda.objects.select_for_update().get(pk=demanda.pk)
        no = NoOperacional.objects.select_for_update().get(pk=int(no_id), demanda_id=demanda.pk)
        tram_id = payload.get("tramitacao_id")
        if tram_id in (None, ""):
            raise ScatterGatherError("Tramitação de encerramento não vinculada.")
        tram = Tramitacao.objects.get(pk=int(tram_id), demanda_id=demanda.pk)
        observacao = str(payload.get("observacao") or "")
        self._encerrar_no(
            demanda,
            no,
            usuario,
            acao=AcaoNoOperacional.DESPACHAR_ENCERRAR,
            tramitacao=tram,
            observacao=observacao,
            permitir_filhos_abertos=True,
        )
        demanda.refresh_from_db()
        processo_avancou = demanda.status == ESTADO_AGUARDANDO_CONCLUSAO_FINAL
        self._aplicar_resultado_operacional_payload(payload, demanda, usuario, observacao, processo_avancou)
        return {
            "no": no,
            "processo_avancou": processo_avancou,
            "nos_ativos": demanda.nos_ativos,
        }

    def _aplicar_resultado_operacional_payload(
        self,
        payload: dict[str, Any] | None,
        demanda: Demanda,
        usuario,
        parecer: str,
        processo_avancou: bool,
    ) -> None:
        if not processo_avancou or not payload or not payload.get("resultado_operacional"):
            return
        from core.services.estudo_viabilidade_service import EstudoViabilidadeService

        try:
            EstudoViabilidadeService().registrar_conclusao_operacional(
                demanda,
                usuario,
                parecer=parecer,
                payload=payload["resultado_operacional"],
            )
        except Exception as exc:
            logger.warning(
                "Falha ao registrar stand-by após encerramento scatter demanda=%s: %s",
                demanda.pk,
                exc,
            )

    def serializar_no(self, no: NoOperacional) -> dict[str, Any]:
        orgao_nome = sinapse_catalog.get_orgao_nome(int(no.sinapse_orgao_id)) or str(no.sinapse_orgao_id)
        setor_nome = ""
        if no.unidade_administrativa_id and no.unidade_administrativa:
            u = no.unidade_administrativa
            setor_nome = u.sigla or u.nome
        meta = no.metadata if isinstance(no.metadata, dict) else {}
        orgao_abridor_id = meta.get("orgao_abridor_id")
        orgao_abridor_nome = ""
        if orgao_abridor_id not in (None, ""):
            orgao_abridor_nome = (
                sinapse_catalog.get_orgao_nome(int(orgao_abridor_id)) or str(orgao_abridor_id)
            )
        abridor_nome = ""
        if no.responsavel_abertura_id and no.responsavel_abertura:
            u = no.responsavel_abertura
            abridor_nome = u.get_full_name() or u.username
        return {
            "id": no.pk,
            "parent_id": no.parent_id,
            "perna_id": no.perna_operacional_id,
            "status": no.status,
            "orgao_id": int(no.sinapse_orgao_id),
            "orgao_nome": orgao_nome,
            "setor_id": no.unidade_administrativa_id,
            "setor_nome": setor_nome,
            "aberto_em": no.aberto_em.isoformat() if no.aberto_em else None,
            "concluido_em": no.concluido_em.isoformat() if no.concluido_em else None,
            "origem_label": self._origem_label_no(no),
            "resumo_abertura": self._resumo_abertura_no(no),
            "orgao_abridor_nome": orgao_abridor_nome,
            "abridor_nome": abridor_nome,
            "metadata": meta,
        }

    def serializar_no_usuario(self, no: NoOperacional) -> dict[str, Any]:
        """Nó aberto do operador com pendências de encerramento."""
        item = self.serializar_no(no)
        internos = self._filhos_abertos_internos(no)
        outros_orgaos = self._filhos_abertos_outras_secretarias(no)
        item["pode_encerrar"] = len(internos) == 0
        item["filhos_abertos_internos"] = [self._serializar_filho_resumo(f) for f in internos]
        item["filhos_abertos_externos"] = [self._serializar_filho_resumo(f) for f in outros_orgaos]
        return item

    def _serializar_filho_resumo(self, filho: NoOperacional) -> dict[str, Any]:
        return {
            "id": filho.pk,
            "orgao_nome": sinapse_catalog.get_orgao_nome(int(filho.sinapse_orgao_id))
            or str(filho.sinapse_orgao_id),
            "setor_nome": (
                filho.unidade_administrativa.sigla or filho.unidade_administrativa.nome
                if filho.unidade_administrativa
                else ""
            ),
        }

    def listar_grupos_painel_nos_usuario(
        self, demanda: Demanda, usuario
    ) -> list[dict[str, Any]]:
        """Painel de gestão — 2+ nós abertos do operador no mesmo setor."""
        nos = list(self.nos_abertos_do_usuario(demanda, usuario))
        grupos: list[dict[str, Any]] = []
        for subset in self._particionar_nos_por_setor(nos):
            if len(subset) < 2:
                continue
            grupos.append(self._montar_grupo_painel_nos(subset))
        return grupos

    def _montar_grupo_painel_nos(self, nos: list[NoOperacional]) -> dict[str, Any]:
        serializados = [self.serializar_no_usuario(n) for n in nos]
        oid = int(nos[0].sinapse_orgao_id)
        orgao_nome = sinapse_catalog.get_orgao_nome(oid) or str(oid)
        setores: list[str] = []
        for no in nos:
            if no.unidade_administrativa:
                rotulo = no.unidade_administrativa.sigla or no.unidade_administrativa.nome
                if rotulo and rotulo not in setores:
                    setores.append(rotulo)
        if len(setores) == 1:
            setor_nome = setores[0]
        elif setores:
            setor_nome = ", ".join(setores)
        else:
            setor_nome = ""

        paralelos = self._filtrar_nos_equivalentes_paralelos(nos)
        canon = self.escolher_no_canonico(nos)

        return {
            "secretaria_id": oid,
            "unidade_administrativa_id": canon.unidade_administrativa_id,
            "orgao_nome": orgao_nome,
            "setor_nome": setor_nome,
            "setores_nomes": setores,
            "quantidade": len(nos),
            "no_canonico_id": canon.pk,
            "no_ids": [n.pk for n in nos],
            "nos": serializados,
            "equivalentes": len(paralelos) >= 2,
        }

    def montar_arvore_nos(self, demanda: Demanda) -> list[dict[str, Any]]:
        nos = list(
            NoOperacional.objects.filter(demanda_id=demanda.pk)
            .select_related("unidade_administrativa")
            .order_by("aberto_em", "pk")
        )
        mapa: dict[int, dict[str, Any]] = {}
        for no in nos:
            item = self.serializar_no(no)
            item["filhos"] = []
            mapa[no.pk] = item
        raizes: list[dict[str, Any]] = []
        for no in nos:
            item = mapa[no.pk]
            if no.parent_id and no.parent_id in mapa:
                mapa[no.parent_id]["filhos"].append(item)
            else:
                raizes.append(item)
        return raizes

    def nos_abertos_do_usuario(self, demanda: Demanda, usuario) -> list[NoOperacional]:
        orgao = perm.orgao_usuario(usuario)
        if orgao is None:
            return []
        qs = self.nos_abertos_qs(demanda.pk).select_related(
            "unidade_administrativa",
            "responsavel_abertura",
            "abertura_tramitacao",
            "parent",
            "demanda",
        )
        qs = self._aplicar_filtro_setor_nos_qs(qs, usuario)
        return list(qs.order_by("aberto_em", "pk"))

    def _prioridade_canonica_no(self, no: NoOperacional) -> tuple:
        meta = no.metadata if isinstance(no.metadata, dict) else {}
        origem = meta.get("origem")
        if origem == "bootstrap_perna":
            prio = 0
        elif origem == "bootstrap_sem_pernas":
            prio = 1
        elif no.perna_operacional_id:
            prio = 2
        else:
            prio = 3
        aberto = no.aberto_em or timezone.now()
        return (prio, aberto, no.pk)

    def escolher_no_canonico(self, nos: list[NoOperacional]) -> NoOperacional:
        if not nos:
            raise ScatterGatherError("Nenhum nó informado para consolidação.")
        return min(nos, key=self._prioridade_canonica_no)

    def _filtrar_nos_equivalentes_paralelos(
        self, nos: list[NoOperacional]
    ) -> list[NoOperacional]:
        """Exclui nós que são filhos de outro nó do conjunto (despacho ≠ redundância)."""
        if len(nos) < 2:
            return []
        ids = {n.pk for n in nos}
        nos_map = {n.pk: n for n in nos}

        def tem_ancestral_no_conjunto(no: NoOperacional) -> bool:
            pid = no.parent_id
            while pid:
                if pid in ids:
                    return True
                ancestral = nos_map.get(pid)
                if ancestral is None:
                    break
                pid = ancestral.parent_id
            return False

        paralelos = [n for n in nos if not tem_ancestral_no_conjunto(n)]
        return paralelos if len(paralelos) >= 2 else []

    def _filhos_abertos_internos(self, no: NoOperacional) -> list[NoOperacional]:
        """Filhos abertos na mesma secretaria que impedem encerrar o nó pai.

        Despacho para outro setor da mesma secretaria não bloqueia: cada setor
        encerra sua participação de forma independente.
        """
        orgao_pai = int(no.sinapse_orgao_id)
        qs = NoOperacional.objects.filter(
            parent_id=no.pk,
            status=StatusNoOperacional.ABERTO,
            sinapse_orgao_id=orgao_pai,
        )
        ua_pai = no.unidade_administrativa_id
        if ua_pai is not None:
            qs = qs.filter(unidade_administrativa_id=ua_pai)
        return list(qs.select_related("unidade_administrativa"))

    def _filhos_abertos_outras_secretarias(self, no: NoOperacional) -> list[NoOperacional]:
        orgao_pai = int(no.sinapse_orgao_id)
        return list(
            NoOperacional.objects.filter(
                parent_id=no.pk,
                status=StatusNoOperacional.ABERTO,
            )
            .exclude(sinapse_orgao_id=orgao_pai)
            .select_related("unidade_administrativa")
        )

    def _filhos_internos_bloqueantes_lote(
        self, no: NoOperacional, ids_grupo: set[int]
    ) -> list[NoOperacional]:
        return [f for f in self._filhos_abertos_internos(no) if f.pk not in ids_grupo]

    def _rotular_filhos(self, filhos: list[NoOperacional], limite: int = 4) -> str:
        rotulos = []
        for filho in filhos[:limite]:
            org = sinapse_catalog.get_orgao_nome(int(filho.sinapse_orgao_id)) or str(
                filho.sinapse_orgao_id
            )
            setor = ""
            if filho.unidade_administrativa:
                setor = filho.unidade_administrativa.sigla or filho.unidade_administrativa.nome
            rotulos.append(f"#{filho.pk} ({org}{f' › {setor}' if setor else ''})")
        extra = f" (+{len(filhos) - limite})" if len(filhos) > limite else ""
        return f"{', '.join(rotulos)}{extra}"

    def _classificar_nos_encerramento_lote(
        self, nos: list[NoOperacional]
    ) -> tuple[list[NoOperacional], list[dict[str, Any]]]:
        """Separa nós que podem ser encerrados dos bloqueados por filhos fora do lote."""
        ids_grupo = {n.pk for n in nos}
        encerraveis: list[NoOperacional] = []
        bloqueados: list[dict[str, Any]] = []
        for no in nos:
            internos = self._filhos_internos_bloqueantes_lote(no, ids_grupo)
            if internos:
                bloqueados.append(
                    {
                        "no_id": no.pk,
                        "motivo": "encaminhamentos_internos_abertos",
                        "filhos_internos": [self._serializar_filho_resumo(f) for f in internos],
                        "mensagem": (
                            f"O nó #{no.pk} possui encaminhamentos internos abertos: "
                            f"{self._rotular_filhos(internos)}. "
                            "Encerre-os antes de fechar este nó."
                        ),
                    }
                )
            else:
                encerraveis.append(no)
        return encerraveis, bloqueados

    def _profundidade_relativa_grupo(
        self,
        no: NoOperacional,
        ids_grupo: set[int],
        nos_map: dict[int, NoOperacional],
    ) -> int:
        depth = 0
        cur = no
        while cur.parent_id and cur.parent_id in ids_grupo:
            depth += 1
            cur = nos_map.get(cur.parent_id)
            if cur is None:
                break
        return depth

    def _ordenar_nos_encerramento_bottom_up(
        self, nos: list[NoOperacional]
    ) -> list[NoOperacional]:
        ids_grupo = {n.pk for n in nos}
        nos_map = {n.pk: n for n in nos}
        return sorted(
            nos,
            key=lambda n: self._profundidade_relativa_grupo(n, ids_grupo, nos_map),
            reverse=True,
        )

    def _validar_grupo_nos_usuario(
        self,
        demanda: Demanda,
        usuario,
        no_ids: list[int],
    ) -> list[NoOperacional]:
        if not no_ids:
            raise ScatterGatherError("Informe ao menos um nó operacional.")
        ids = sorted({int(i) for i in no_ids})
        nos: list[NoOperacional] = []
        for nid in ids:
            no = NoOperacional.objects.select_related(
                "unidade_administrativa",
                "responsavel_abertura",
                "abertura_tramitacao",
                "parent",
                "demanda",
            ).filter(pk=nid, demanda_id=demanda.pk, status=StatusNoOperacional.ABERTO).first()
            if not no:
                raise ScatterGatherError(f"Nó operacional #{nid} não encontrado ou já encerrado.")
            if not self._usuario_pode_operar_no(usuario, no):
                raise ScatterGatherPermissaoError(f"Sem permissão para operar o nó #{nid}.")
            nos.append(no)
        chaves = {int(n.sinapse_orgao_id) for n in nos}
        if len(chaves) != 1:
            raise ScatterGatherError(
                "Os nós selecionados devem pertencer ao mesmo órgão para ação unificada."
            )
        return nos

    def listar_grupos_nos_usuario(self, demanda: Demanda, usuario) -> list[dict[str, Any]]:
        """Agrupa nós abertos redundantes do usuário no mesmo setor."""
        nos = list(self.nos_abertos_do_usuario(demanda, usuario))
        grupos: list[dict[str, Any]] = []
        for subset in self._particionar_nos_por_setor(nos):
            paralelos = self._filtrar_nos_equivalentes_paralelos(subset)
            if len(paralelos) < 2:
                continue
            grupos.append(self._montar_grupo_equivalente_nos(paralelos))
        return grupos

    def _montar_grupo_equivalente_nos(
        self, paralelos: list[NoOperacional]
    ) -> dict[str, Any]:
        canon = self.escolher_no_canonico(paralelos)
        oid = int(paralelos[0].sinapse_orgao_id)
        orgao_nome = sinapse_catalog.get_orgao_nome(oid) or str(oid)
        setores: list[str] = []
        for no in paralelos:
            if no.unidade_administrativa:
                rotulo = no.unidade_administrativa.sigla or no.unidade_administrativa.nome
                if rotulo and rotulo not in setores:
                    setores.append(rotulo)
        if len(setores) == 1:
            setor_nome = setores[0]
        elif setores:
            setor_nome = ", ".join(setores)
        else:
            setor_nome = ""

        return {
            "secretaria_id": oid,
            "unidade_administrativa_id": canon.unidade_administrativa_id,
            "orgao_nome": orgao_nome,
            "setor_nome": setor_nome,
            "setores_nomes": setores,
            "quantidade": len(paralelos),
            "no_canonico_id": canon.pk,
            "no_ids": [n.pk for n in paralelos],
            "nos": [self.serializar_no(n) for n in paralelos],
        }

    @transaction.atomic
    def consolidar_nos_equivalentes(
        self,
        demanda: Demanda,
        usuario,
        *,
        no_ids: list[int],
        no_canonico_id: int | None = None,
        observacao: str = "",
    ) -> dict[str, Any]:
        """Mantém o nó canônico e encerra os demais nós equivalentes."""
        self._exigir_em_operacao(demanda)
        Demanda.objects.select_for_update().get(pk=demanda.pk)
        nos = self._validar_grupo_nos_usuario(demanda, usuario, no_ids)
        canon = next((n for n in nos if n.pk == int(no_canonico_id)), None) if no_canonico_id else None
        if canon is None:
            canon = self.escolher_no_canonico(nos)
        redundantes = [n for n in nos if n.pk != canon.pk]
        if not redundantes:
            raise ScatterGatherError("Não há nós redundantes para consolidar.")

        texto = (observacao or "").strip() or (
            f"Consolidação operacional — mantido nó #{canon.pk} "
            f"({self._origem_label_no(canon)}); encerrados {len(redundantes)} redundante(s)."
        )
        descricao = _validar_texto_operacional(texto, rotulo="justificativa da consolidação")
        nos_antes = self.contar_nos_ativos(demanda.pk)
        tram = self._registrar_evento(
            demanda,
            usuario,
            descricao=descricao,
            metadata={
                "acao_no": "CONSOLIDAR",
                "scatter_gather": True,
                "no_canonico_id": canon.pk,
                "no_ids": [n.pk for n in nos],
                "nos_redundantes_ids": [n.pk for n in redundantes],
                "nos_ativos": nos_antes,
            },
        )
        encerrados: list[NoOperacional] = []
        for no in redundantes:
            no = NoOperacional.objects.select_for_update().get(pk=no.pk)
            meta = dict(no.metadata or {})
            meta["consolidado_em"] = canon.pk
            meta["consolidacao"] = True
            no.metadata = meta
            no.save(update_fields=["metadata"])
            self._encerrar_no(
                demanda,
                no,
                usuario,
                acao="CONSOLIDAR",
                tramitacao=tram,
                observacao=texto,
            )
            encerrados.append(no)

        nos_depois = self.sincronizar_contador_nos(demanda)
        tram.metadata["nos_ativos"] = nos_depois
        tram.save(update_fields=["metadata"])
        demanda.refresh_from_db()
        canon.refresh_from_db()
        return {
            "acao": "CONSOLIDAR",
            "no_canonico": canon,
            "nos_encerrados": encerrados,
            "nos_ativos": demanda.nos_ativos,
            "processo_avancou": demanda.status == ESTADO_AGUARDANDO_CONCLUSAO_FINAL,
        }

    @transaction.atomic
    def encerrar_nos_lote(
        self,
        demanda: Demanda,
        usuario,
        *,
        no_ids: list[int],
        observacao: str = "",
        arquivos_anexos: list | None = None,
        assinatura_ctx: dict[str, Any] | None = None,
        request=None,
    ) -> dict[str, Any]:
        """Encerra os nós informados em uma única operação (parcial se houver bloqueios)."""
        self._exigir_em_operacao(demanda)
        Demanda.objects.select_for_update().get(pk=demanda.pk)
        nos = self._validar_grupo_nos_usuario(demanda, usuario, no_ids)
        nos_encerraveis, nos_bloqueados = self._classificar_nos_encerramento_lote(nos)

        if not nos_encerraveis:
            detalhes = "; ".join(b["mensagem"] for b in nos_bloqueados[:3])
            extra = f" (+{len(nos_bloqueados) - 3})" if len(nos_bloqueados) > 3 else ""
            raise ScatterGatherError(
                "Nenhum dos nós selecionados pode ser encerrado agora. "
                f"{detalhes}{extra}"
            )

        parcial = bool(nos_bloqueados)
        texto_base = (observacao or "").strip()
        if not texto_base:
            if parcial:
                texto_base = (
                    f"Encerramento parcial de {len(nos_encerraveis)} nó(s) operacional(is) "
                    f"({len(nos_bloqueados)} não encerrado(s) por encaminhamentos filhos abertos)."
                )
            else:
                texto_base = (
                    f"Encerramento unificado de {len(nos_encerraveis)} nó(s) operacional(is)."
                )
        descricao = _validar_texto_operacional(texto_base, rotulo="descrição do encerramento")

        encerrados: list[NoOperacional] = []
        anexos_aplicados = False
        assinaturas_registradas: list[dict[str, Any]] = []
        deferir_encerramento = self._scatter_aguarda_validacao_gestor(assinatura_ctx)
        for no in self._ordenar_nos_encerramento_bottom_up(nos_encerraveis):
            no = NoOperacional.objects.select_for_update().get(pk=no.pk)
            tram_no = self._registrar_evento(
                demanda,
                usuario,
                descricao=descricao,
                metadata=self._payload_evento(
                    acao=AcaoNoOperacional.ENCERRAR,
                    no=no,
                    nos_ativos=self.contar_nos_ativos(demanda.pk),
                    observacao=observacao,
                ),
            )
            if arquivos_anexos and not anexos_aplicados:
                from core.services.tramitacao_anexo_service import anexar_arquivos_tramitacao

                anexar_arquivos_tramitacao(tram_no, arquivos_anexos, copiar=False)
                anexos_aplicados = True
            if not deferir_encerramento:
                self._encerrar_no(
                    demanda,
                    no,
                    usuario,
                    acao=AcaoNoOperacional.ENCERRAR,
                    tramitacao=tram_no,
                    observacao=observacao,
                )
            tram_no.metadata = self._payload_evento(
                acao=AcaoNoOperacional.ENCERRAR,
                no=no,
                nos_ativos=self.contar_nos_ativos(demanda.pk),
                observacao=observacao,
            )
            tram_no.save(update_fields=["metadata"])
            assinatura = self._registrar_assinatura_scatter_se_solicitada(
                demanda,
                tram_no,
                usuario,
                AcaoNoOperacional.ENCERRAR,
                assinatura_ctx,
                request=request,
            )
            if assinatura is not None:
                assinaturas_registradas.append(
                    {
                        "codigo_validacao": assinatura.codigo_validacao,
                        "tramitacao_id": tram_no.pk,
                    }
                )
            encerrados.append(no)

        nos_depois = self.sincronizar_contador_nos(demanda)
        demanda.refresh_from_db()
        resultado = {
            "acao": "ENCERRAR_LOTE",
            "nos_encerrados": encerrados,
            "nos_bloqueados": nos_bloqueados,
            "encerramento_parcial": parcial,
            "nos_ativos": demanda.nos_ativos,
        }
        if deferir_encerramento:
            resultado["aguardando_validacao_gestor"] = True
        else:
            resultado["processo_avancou"] = demanda.status == ESTADO_AGUARDANDO_CONCLUSAO_FINAL
        if assinaturas_registradas:
            resultado["assinaturas_registradas"] = assinaturas_registradas
        return resultado

    @transaction.atomic
    def despachar_nos_unificado(
        self,
        demanda: Demanda,
        usuario,
        *,
        no_ids: list[int],
        destinos: list[dict[str, Any]],
        acao_scatter: str,
        observacao: str = "",
        arquivos_anexos: list | None = None,
        confirmar_destino_duplicado: bool = False,
        no_canonico_id: int | None = None,
        assinatura_ctx: dict[str, Any] | None = None,
        request=None,
    ) -> dict[str, Any]:
        """Consolida nós equivalentes e despacha uma única vez a partir do nó canônico."""
        nos = self._validar_grupo_nos_usuario(demanda, usuario, no_ids)
        canon_id: int
        if len(nos) > 1:
            consolidado = self.consolidar_nos_equivalentes(
                demanda,
                usuario,
                no_ids=[n.pk for n in nos],
                no_canonico_id=no_canonico_id,
                observacao="Consolidação automática antes do despacho unificado.",
            )
            canon_id = consolidado["no_canonico"].pk
            demanda.refresh_from_db()
        else:
            canon_id = int(no_canonico_id) if no_canonico_id else nos[0].pk
        if acao_scatter == AcaoNoOperacional.DESPACHAR_ENCERRAR:
            return self.aplicar_despachar_encerrar(
                demanda,
                canon_id,
                usuario,
                destinos=destinos,
                observacao=observacao,
                arquivos_anexos=arquivos_anexos,
                confirmar_destino_duplicado=confirmar_destino_duplicado,
                assinatura_ctx=assinatura_ctx,
                request=request,
            )
        return self.aplicar_despachar_destinos(
            demanda,
            canon_id,
            usuario,
            destinos=destinos,
            observacao=observacao,
            arquivos_anexos=arquivos_anexos,
            confirmar_destino_duplicado=confirmar_destino_duplicado,
            assinatura_ctx=assinatura_ctx,
            request=request,
        )

    @transaction.atomic
    def reparar_tramitacoes_operacionais(
        self,
        demanda: Demanda,
        usuario=None,
    ) -> dict[str, Any]:
        """
        Preenche lacunas de tramitação scatter-gather em demandas já processadas:
        aberturas bootstrap, encaminhamentos por filho e encerramentos individuais de lote.
        """
        from core.models import Usuario

        if usuario is None:
            usuario = (
                Usuario.objects.filter(is_superuser=True).first()
                or demanda.autor
            )
        criadas = {"abertura": 0, "encaminhamento": 0, "encerramento": 0}

        nos = list(
            NoOperacional.objects.filter(demanda_id=demanda.pk)
            .select_related("unidade_administrativa", "abertura_tramitacao", "encerramento_tramitacao")
            .order_by("pk")
        )
        for no in nos:
            meta = no.metadata if isinstance(no.metadata, dict) else {}
            origem = meta.get("origem")
            if origem in ("bootstrap_perna", "bootstrap_sem_pernas"):
                abertura_meta = (
                    _tram_meta_dict(no.abertura_tramitacao)
                    if no.abertura_tramitacao_id
                    else {}
                )
                if abertura_meta.get("acao_no") != "ABERTURA_NO":
                    self._registrar_abertura_bootstrap(demanda, no, usuario)
                    criadas["abertura"] += 1

        for no in nos:
            if not no.parent_id:
                continue
            abertura = no.abertura_tramitacao
            if not abertura:
                continue
            ab_meta = _tram_meta_dict(abertura)
            acao_ab = ab_meta.get("acao_no")
            if acao_ab in ("ENCAMINHAMENTO_NO", "ABERTURA_NO"):
                continue
            if acao_ab not in (
                AcaoNoOperacional.DESPACHAR,
                AcaoNoOperacional.DESPACHAR_ENCERRAR,
            ):
                continue
            descricao = abertura.descricao or ""
            observacao = ab_meta.get("observacao") or descricao
            self._registrar_encaminhamento_filho(
                demanda,
                no,
                usuario,
                descricao=descricao,
                observacao=observacao,
                nos_ativos=self.contar_nos_ativos(demanda.pk),
            )
            criadas["encaminhamento"] += 1

        lote_trams = Tramitacao.objects.filter(
            demanda_id=demanda.pk,
            tipo="OPERACAO_NO",
            metadata__acao_no="ENCERRAR_LOTE",
        ).prefetch_related("anexos")
        for tram_lote in lote_trams:
            meta_lote = _tram_meta_dict(tram_lote)
            no_ids = meta_lote.get("no_ids") or []
            descricao_lote = tram_lote.descricao or ""
            observacao_lote = meta_lote.get("observacao") or descricao_lote
            responsavel = tram_lote.responsavel or usuario
            for no_id in no_ids:
                no = NoOperacional.objects.filter(pk=int(no_id), demanda_id=demanda.pk).first()
                if not no or no.encerramento_tramitacao_id != tram_lote.pk:
                    continue
                no_meta = no.metadata if isinstance(no.metadata, dict) else {}
                descricao = (
                    (no_meta.get("observacao_encerramento") or "").strip()
                    or descricao_lote
                )
                observacao = descricao or observacao_lote
                tram_no = self._registrar_evento(
                    demanda,
                    responsavel,
                    descricao=descricao,
                    metadata=self._payload_evento(
                        acao=AcaoNoOperacional.ENCERRAR,
                        no=no,
                        nos_ativos=self.contar_nos_ativos(demanda.pk),
                        observacao=observacao,
                    ),
                )
                for anexo in tram_lote.anexos.all():
                    if anexo.arquivo:
                        from core.models import AnexoTramitacao

                        AnexoTramitacao.objects.create(
                            tramitacao=tram_no,
                            arquivo=anexo.arquivo,
                        )
                no.encerramento_tramitacao = tram_no
                no.save(update_fields=["encerramento_tramitacao"])
                criadas["encerramento"] += 1
            tram_lote.delete()

        return criadas


def _tram_meta_dict(tram: Tramitacao | None) -> dict:
    if tram is None:
        return {}
    raw = tram.metadata
    return raw if isinstance(raw, dict) else {}
