"""Integração de demanda seguidora ao processo líder do cluster (Super OS)."""

from __future__ import annotations

import copy
import logging
from typing import Any

from django.core.files.base import ContentFile
from django.db import transaction

from core.models import AnexoTramitacao, Demanda, Tramitacao
from core.models_no_operacional import NoOperacional
from core.models_perna_operacional import PernaOperacional
from core.services.cluster_service import (
    CLUSTER_MIN_DEMANDAS,
    STATUS_ORDEM_GRUPO,
    ClusterService,
)

logger = logging.getLogger(__name__)

CAMPOS_DEMANDA_ESPELHADOS = (
    # protocolo_executivo é único por demanda — seguidora usa referência do líder (ver protocolo_executivo_efetivo).
    "sinapse_orgao_id",
    "unidade_administrativa_id",
    "status",
    "data_inicio_prazo",
    "fluxo_roteamento",
    "sinapse_orgao_lider_id",
    "modo_entrada_processo",
    "orquestrador_conclusao",
    "inicio_execucao_automatico",
    "nos_ativos",
    "prazo_efetivo_dias",
    "prazo_origem",
)


class ClusterAderenciaError(ValueError):
    """Erro de validação na aderência ao líder."""


def seguidora_pendente_integracao(seg: Demanda, lider: Demanda) -> bool:
    """Seguidora sem protocolo próprio que ainda não espelhou o líder operacional."""
    if (seg.protocolo_executivo or "").strip():
        return False
    if not (lider.protocolo_executivo or "").strip():
        return False
    if demanda_integrada_ao_lider(seg):
        return False
    if not seg.cluster_id or int(seg.cluster_id) != int(lider.cluster_id or 0):
        return False
    return True


def integrar_cluster_apos_protocolo(demanda: Demanda, *, usuario) -> list[int]:
    """Integra seguidoras do cluster ao líder operacional logo após o despacho."""
    if not demanda.cluster_id or not (demanda.protocolo_executivo or "").strip():
        return []
    svc = ClusterService()
    if svc.cluster_e_multi_destino_orgaos(int(demanda.cluster_id)):
        return []
    lider_pk = svc.lider_cluster_pk(int(demanda.cluster_id))
    if not lider_pk:
        return []
    lider = Demanda.objects.filter(pk=int(lider_pk)).first()
    if not lider:
        return []
    return ClusterAderenciaService().integrar_seguidoras_sem_protocolo_ao_operacional(
        lider, usuario=usuario
    )


def demanda_integrada_ao_lider(demanda: Demanda) -> bool:
    """True quando seguidora integrada ao processo líder (sem protocolo executivo próprio)."""
    if demanda.protocolo_executivo:
        return False
    if not demanda.cluster_id:
        return False
    lider_pk = ClusterService().lider_cluster_pk(int(demanda.cluster_id))
    if lider_pk is None or int(demanda.pk) == int(lider_pk):
        return False
    if Tramitacao.objects.filter(
        demanda_id=demanda.pk,
        tipo="COMENTARIO",
        metadata__acao="ADERIR_LIDER",
    ).exists():
        return True
    ordem = STATUS_ORDEM_GRUPO.get(demanda.status)
    if ordem is None or ordem <= STATUS_ORDEM_GRUPO["AGUARDANDO_PROTOCOLO"]:
        return False
    lider = Demanda.objects.filter(pk=int(lider_pk)).only("protocolo_executivo").first()
    return bool(lider and lider.protocolo_executivo)


def protocolo_executivo_efetivo(demanda: Demanda) -> str | None:
    """Protocolo executivo exibível — próprio ou, se integrada, o do líder do cluster."""
    if demanda.protocolo_executivo:
        return demanda.protocolo_executivo
    if not demanda_integrada_ao_lider(demanda):
        return None
    lider_pk = ClusterService().lider_cluster_pk(int(demanda.cluster_id))
    if not lider_pk:
        return None
    lider = Demanda.objects.filter(pk=int(lider_pk)).only("protocolo_executivo").first()
    return lider.protocolo_executivo if lider else None


class ClusterAderenciaService:
    def __init__(self) -> None:
        self._cluster = ClusterService()

    def _lider(self, demanda: Demanda) -> Demanda | None:
        if not demanda.cluster_id:
            return None
        lider_pk = self._cluster.lider_cluster_pk(int(demanda.cluster_id))
        if not lider_pk:
            return None
        return Demanda.objects.filter(pk=int(lider_pk)).first()

    def _ordem_status(self, status: str) -> int | None:
        return STATUS_ORDEM_GRUPO.get(status)

    def situacao_aderencia(self, demanda: Demanda) -> dict[str, Any]:
        """Payload para o Protocolo decidir entre integrar, desvincular ou despacho em lote."""
        base: dict[str, Any] = {
            "exibir_decisao": False,
            "aderir_lider": False,
            "desvincular_despacho": False,
            "super_os_lote": False,
            "motivo": "",
            "lider": None,
            "cluster_id": demanda.cluster_id,
        }
        if demanda.status != "AGUARDANDO_PROTOCOLO":
            base["motivo"] = "status_invalido"
            return base
        if not demanda.cluster_id:
            base["motivo"] = "sem_cluster"
            return base

        total = Demanda.objects.filter(cluster_id=demanda.cluster_id).count()
        if total < CLUSTER_MIN_DEMANDAS:
            base["motivo"] = "cluster_insuficiente"
            return base

        lider = self._lider(demanda)
        if lider is None:
            base["motivo"] = "lider_nao_encontrado"
            return base

        if int(lider.pk) == int(demanda.pk):
            cluster = demanda.cluster
            pendentes = Demanda.objects.filter(
                cluster_id=demanda.cluster_id,
                status="AGUARDANDO_PROTOCOLO",
            ).count()
            if pendentes >= CLUSTER_MIN_DEMANDAS and not self._cluster.cluster_ja_despachado(
                cluster
            ):
                base["super_os_lote"] = True
                base["motivo"] = "lider_aguardando_super_os"
            return base

        ordem_lider = self._ordem_status(lider.status)
        if ordem_lider is None or ordem_lider <= self._ordem_status("AGUARDANDO_PROTOCOLO"):
            base["motivo"] = "lider_aguardando_despacho"
            return base

        base["exibir_decisao"] = True
        base["aderir_lider"] = True
        base["desvincular_despacho"] = True
        base["motivo"] = "ok"
        base["lider"] = self._serializar_lider(lider)
        return base

    def _serializar_lider(self, lider: Demanda) -> dict[str, Any]:
        autor = lider.autor
        nome_autor = ""
        if autor:
            nome_autor = f"{autor.first_name or ''} {autor.last_name or ''}".strip() or autor.username
        return {
            "id": lider.pk,
            "protocolo_legislativo": lider.protocolo_legislativo,
            "protocolo_executivo": lider.protocolo_executivo,
            "status": lider.status,
            "status_display": lider.get_status_display(),
            "autor_nome": nome_autor,
            "nos_ativos": lider.nos_ativos,
        }

    @transaction.atomic
    def aderir_ao_processo_lider(self, demanda: Demanda, *, usuario) -> Demanda:
        situacao = self.situacao_aderencia(demanda)
        if not situacao.get("aderir_lider"):
            raise ClusterAderenciaError(
                situacao.get("motivo") or "Esta demanda não pode integrar ao processo líder."
            )

        lider = self._lider(demanda)
        if lider is None:
            raise ClusterAderenciaError("Líder do cluster não encontrado.")

        seguidora = Demanda.objects.select_for_update().get(pk=demanda.pk)
        lider = Demanda.objects.select_for_update().get(pk=lider.pk)

        self._aplicar_espelho_lider(seguidora, lider, usuario=usuario, registrar_comentario=True)
        return seguidora

    @transaction.atomic
    def ressincronizar_com_lider(
        self,
        seguidora: Demanda,
        *,
        lider: Demanda | None = None,
        usuario=None,
    ) -> bool:
        """Reespelha seguidora integrada quando o líder avançou de etapa."""
        if not demanda_integrada_ao_lider(seguidora):
            return False
        lider = lider or self._lider(seguidora)
        if lider is None:
            return False

        seguidora = Demanda.objects.select_for_update().get(pk=seguidora.pk)
        lider = Demanda.objects.select_for_update().get(pk=lider.pk)

        precisa = (
            seguidora.status != lider.status
            or seguidora.nos_ativos != lider.nos_ativos
            or seguidora.fluxo_roteamento != lider.fluxo_roteamento
        )
        if not precisa:
            return False

        self._aplicar_espelho_lider(seguidora, lider, usuario=usuario, registrar_comentario=False)
        logger.info(
            "Seguidora pk=%s ressincronizada com líder pk=%s (status=%s)",
            seguidora.pk,
            lider.pk,
            lider.status,
        )
        return True

    def sincronizar_seguidoras_integradas(self, lider: Demanda, *, usuario=None) -> list[int]:
        """Ressincroniza todas as seguidoras integradas ao processo líder."""
        if not lider.cluster_id:
            return []
        atualizados: list[int] = []
        for sib in Demanda.objects.filter(cluster_id=lider.cluster_id).exclude(pk=lider.pk):
            if self.ressincronizar_com_lider(sib, lider=lider, usuario=usuario):
                atualizados.append(int(sib.pk))
        return atualizados

    @transaction.atomic
    def integrar_seguidoras_sem_protocolo_ao_operacional(
        self, lider: Demanda, *, usuario
    ) -> list[int]:
        """Integra demandas do cluster sem protocolo executivo ao processo protocolado."""
        if not lider.cluster_id or not (lider.protocolo_executivo or "").strip():
            return []
        integradas: list[int] = []
        for sib in Demanda.objects.filter(cluster_id=lider.cluster_id).exclude(pk=lider.pk):
            if (sib.protocolo_executivo or "").strip():
                continue
            if demanda_integrada_ao_lider(sib):
                if self.ressincronizar_com_lider(sib, lider=lider, usuario=usuario):
                    integradas.append(int(sib.pk))
                continue
            self._aplicar_espelho_lider(
                sib, lider, usuario=usuario, registrar_comentario=True
            )
            integradas.append(int(sib.pk))
        return integradas

    def _aplicar_espelho_lider(
        self,
        seguidora: Demanda,
        lider: Demanda,
        *,
        usuario,
        registrar_comentario: bool,
    ) -> None:
        tram_map = self._espelhar_tramitacoes(lider, seguidora, usuario=usuario)
        perna_map = self._espelhar_pernas(lider, seguidora, tram_map)
        self._espelhar_nos_operacionais(lider, seguidora, tram_map, perna_map)

        update_fields: list[str] = []
        for campo in CAMPOS_DEMANDA_ESPELHADOS:
            setattr(seguidora, campo, getattr(lider, campo))
            update_fields.append(campo)
        seguidora._propagando_cluster_status = True  # noqa: SLF001
        seguidora.save(update_fields=update_fields)

        if not registrar_comentario:
            return

        from integrations import sinapse_catalog

        orgao_nome = ""
        if lider.sinapse_orgao_id:
            orgao_nome = (
                sinapse_catalog.get_orgao_nome(int(lider.sinapse_orgao_id))
                or str(lider.sinapse_orgao_id)
            )

        Tramitacao.objects.create(
            demanda=seguidora,
            responsavel=usuario,
            tipo="COMENTARIO",
            descricao=(
                f"Integrada ao processo líder #{lider.pk} "
                f"({lider.protocolo_legislativo or lider.pk}) por decisão do Protocolo. "
                f"Protocolo executivo de referência: {lider.protocolo_executivo or '—'}. "
                "Tramitações operacionais replicadas integralmente."
            ),
            metadata={
                "integracao_cluster": True,
                "lider_demanda_id": lider.pk,
                "acao": "ADERIR_LIDER",
            },
        )

        logger.info(
            "Demanda pk=%s integrada ao líder pk=%s (cluster pk=%s) por user=%s",
            seguidora.pk,
            lider.pk,
            seguidora.cluster_id,
            getattr(usuario, "pk", None),
        )

    def _espelhar_tramitacoes(
        self,
        lider: Demanda,
        seguidora: Demanda,
        *,
        usuario,
    ) -> dict[int, Tramitacao]:
        """Replica tramitações do líder na seguidora (exceto ENVIO_OFICIAL do líder)."""
        Tramitacao.objects.filter(demanda=seguidora).exclude(tipo="ENVIO_OFICIAL").delete()

        tram_map: dict[int, Tramitacao] = {}
        for tram in (
            Tramitacao.objects.filter(demanda=lider)
            .prefetch_related("anexos")
            .order_by("timestamp", "pk")
        ):
            if tram.tipo == "ENVIO_OFICIAL":
                continue
            copia = Tramitacao.objects.create(
                demanda=seguidora,
                responsavel=tram.responsavel,
                tipo=tram.tipo,
                descricao=tram.descricao,
                timestamp=tram.timestamp,
                unidade_origem=tram.unidade_origem,
                unidade_destino=tram.unidade_destino,
                metadata=self._metadata_tramitacao_espelhada(tram, lider.pk),
            )
            copia._propagando_cluster_tramitacao = True  # noqa: SLF001
            self._copiar_anexos_tramitacao(tram, copia)
            tram_map[int(tram.pk)] = copia
        return tram_map

    def _metadata_tramitacao_espelhada(self, tram: Tramitacao, lider_id: int) -> dict:
        meta = copy.deepcopy(tram.metadata) if isinstance(tram.metadata, dict) else {}
        meta["espelhada_do_lider"] = True
        meta["lider_demanda_id"] = int(lider_id)
        meta["tramitacao_lider_id"] = int(tram.pk)
        return meta

    def _copiar_anexos_tramitacao(self, origem: Tramitacao, destino: Tramitacao) -> None:
        for anexo in origem.anexos.all():
            if not anexo.arquivo:
                continue
            nome = anexo.arquivo.name.split("/")[-1]
            with anexo.arquivo.open("rb") as fh:
                payload = ContentFile(fh.read(), name=nome)
            AnexoTramitacao.objects.create(tramitacao=destino, arquivo=payload)

    def _espelhar_pernas(
        self,
        lider: Demanda,
        seguidora: Demanda,
        tram_map: dict[int, Tramitacao],
    ) -> dict[int, int]:
        PernaOperacional.objects.filter(demanda=seguidora).delete()
        perna_map: dict[int, int] = {}
        for perna in PernaOperacional.objects.filter(demanda=lider).order_by("ordem", "pk"):
            despacho = (
                tram_map.get(int(perna.despacho_tramitacao_id)).pk
                if perna.despacho_tramitacao_id and int(perna.despacho_tramitacao_id) in tram_map
                else None
            )
            conclusao = (
                tram_map.get(int(perna.conclusao_tramitacao_id)).pk
                if perna.conclusao_tramitacao_id and int(perna.conclusao_tramitacao_id) in tram_map
                else None
            )
            nova = PernaOperacional.objects.create(
                demanda=seguidora,
                sinapse_orgao_id=perna.sinapse_orgao_id,
                unidade_administrativa=perna.unidade_administrativa,
                status=perna.status,
                ordem=perna.ordem,
                despacho_tramitacao_id=despacho,
                conclusao_tramitacao_id=conclusao,
                metadata=copy.deepcopy(perna.metadata) if isinstance(perna.metadata, dict) else {},
            )
            perna_map[int(perna.pk)] = int(nova.pk)
        return perna_map

    def _espelhar_nos_operacionais(
        self,
        lider: Demanda,
        seguidora: Demanda,
        tram_map: dict[int, Tramitacao],
        perna_map: dict[int, int],
    ) -> None:
        NoOperacional.objects.filter(demanda=seguidora).delete()
        nos_lider = list(
            NoOperacional.objects.filter(demanda=lider).order_by("pk")
        )
        no_map: dict[int, int] = {}
        for no in nos_lider:
            parent_id = no_map.get(int(no.parent_id)) if no.parent_id else None
            perna_id = (
                perna_map.get(int(no.perna_operacional_id))
                if no.perna_operacional_id
                else None
            )
            abertura_id = (
                tram_map.get(int(no.abertura_tramitacao_id)).pk
                if no.abertura_tramitacao_id and int(no.abertura_tramitacao_id) in tram_map
                else None
            )
            encerramento_id = (
                tram_map.get(int(no.encerramento_tramitacao_id)).pk
                if no.encerramento_tramitacao_id and int(no.encerramento_tramitacao_id) in tram_map
                else None
            )
            novo = NoOperacional.objects.create(
                demanda=seguidora,
                parent_id=parent_id,
                perna_operacional_id=perna_id,
                sinapse_orgao_id=no.sinapse_orgao_id,
                unidade_administrativa=no.unidade_administrativa,
                status=no.status,
                responsavel_abertura=no.responsavel_abertura,
                abertura_tramitacao_id=abertura_id,
                encerramento_tramitacao_id=encerramento_id,
                metadata=copy.deepcopy(no.metadata) if isinstance(no.metadata, dict) else {},
                aberto_em=no.aberto_em,
                concluido_em=no.concluido_em,
            )
            no_map[int(no.pk)] = int(novo.pk)
