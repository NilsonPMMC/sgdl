"""Serviço de pernas operacionais — demanda única, roteamento transversal (P3)."""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from core.models import Demanda, Tramitacao
from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional
from integrations import sinapse_catalog

logger = logging.getLogger(__name__)


def _orgao_lider_processo(demanda: Demanda) -> int | None:
    oid = demanda.sinapse_orgao_lider_id or demanda.sinapse_orgao_id
    return int(oid) if oid else None


def _metadata_perna(
    *,
    origem: str,
    orgao_lider_imediato_id: int,
    orgao_abridor_id: int | None = None,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "origem": origem,
        "orgao_lider_imediato_id": int(orgao_lider_imediato_id),
    }
    if orgao_abridor_id is not None:
        meta["orgao_abridor_id"] = int(orgao_abridor_id)
    return meta


class PernaOperacionalService:
    def demanda_usa_pernas(self, demanda: Demanda) -> bool:
        return PernaOperacional.objects.filter(
            demanda_id=demanda.pk,
            status__in=StatusPernaOperacional.ATIVOS,
        ).exists()

    def listar_pernas(self, demanda: Demanda, *, incluir_canceladas: bool = False) -> list[PernaOperacional]:
        qs = PernaOperacional.objects.filter(demanda_id=demanda.pk).select_related(
            "unidade_administrativa", "conclusao_tramitacao"
        )
        if not incluir_canceladas:
            qs = qs.exclude(status=StatusPernaOperacional.CANCELADA)
        return list(qs.order_by("ordem", "pk"))

    @transaction.atomic
    def criar_pernas_no_despacho(
        self,
        demanda: Demanda,
        pernas_payload: list[dict[str, Any]],
        *,
        despacho_tramitacao: Tramitacao | None = None,
    ) -> list[PernaOperacional]:
        """Substitui clones B5 — N pernas na mesma demanda."""
        self.cancelar_pernas(demanda, motivo="redespacho")
        criadas: list[PernaOperacional] = []
        root = _orgao_lider_processo(demanda)
        from core.services.carta_setor_service import CartaSetorService

        carta_setor = CartaSetorService()
        for idx, item in enumerate(pernas_payload, start=1):
            orgao_id = int(item["secretaria_id"])
            uid = item.get("unidade_administrativa_id")
            unidade = carta_setor.resolver_unidade_para_orgao(demanda, orgao_id, uid)
            lid_imediato = int(root or orgao_id)
            perna = PernaOperacional.objects.create(
                demanda=demanda,
                sinapse_orgao_id=orgao_id,
                unidade_administrativa=unidade,
                ordem=idx,
                status=StatusPernaOperacional.PENDENTE,
                despacho_tramitacao=despacho_tramitacao,
                metadata=_metadata_perna(
                    origem="despacho",
                    orgao_lider_imediato_id=lid_imediato,
                ),
            )
            criadas.append(perna)
        logger.info(
            "Demanda pk=%s — %s perna(s) operacional(is) criada(s).",
            demanda.pk,
            len(criadas),
        )
        return criadas

    @transaction.atomic
    def adicionar_pernas(
        self,
        demanda: Demanda,
        pernas_payload: list[dict[str, Any]],
        *,
        tramitacao: Tramitacao | None = None,
        orgao_lider_imediato_id: int | None = None,
    ) -> list[PernaOperacional]:
        """Abre sub-pernas (diretório) — rota de conclusão aponta ao órgão gestor."""
        if not pernas_payload:
            raise ValueError("Informe ao menos um órgão integrado para abrir perna transversal.")

        lid_imediato = int(
            orgao_lider_imediato_id
            or _orgao_lider_processo(demanda)
            or pernas_payload[0]["secretaria_id"]
        )

        existentes = {
            (p.sinapse_orgao_id, p.unidade_administrativa_id)
            for p in self.listar_pernas(demanda)
            if p.status in StatusPernaOperacional.ATIVOS
        }
        if len(existentes) + len(pernas_payload) > 30:
            raise ValueError("Limite de 30 pernas operacionais atingido para este processo.")

        max_ordem = (
            PernaOperacional.objects.filter(demanda_id=demanda.pk)
            .order_by("-ordem")
            .values_list("ordem", flat=True)
            .first()
            or 0
        )
        status_inicial = (
            StatusPernaOperacional.EM_EXECUCAO
            if demanda.status == "EM_EXECUCAO"
            else StatusPernaOperacional.PENDENTE
        )
        criadas: list[PernaOperacional] = []
        from core.services.carta_setor_service import CartaSetorService

        carta_setor = CartaSetorService()
        for idx, item in enumerate(pernas_payload, start=max_ordem + 1):
            orgao_id = int(item["secretaria_id"])
            uid = item.get("unidade_administrativa_id")
            chave = (orgao_id, int(uid) if uid not in (None, "") else None)
            if chave in existentes:
                continue
            unidade = carta_setor.resolver_unidade_para_orgao(demanda, orgao_id, uid)
            perna = PernaOperacional.objects.create(
                demanda=demanda,
                sinapse_orgao_id=orgao_id,
                unidade_administrativa=unidade,
                ordem=idx,
                status=status_inicial,
                despacho_tramitacao=tramitacao,
                metadata=_metadata_perna(
                    origem="abertura_transversal",
                    orgao_lider_imediato_id=lid_imediato,
                    orgao_abridor_id=lid_imediato,
                ),
            )
            existentes.add(chave)
            criadas.append(perna)
        if not criadas:
            raise ValueError(
                "Nenhuma perna nova — os destinos já existem ou são internos ao órgão líder. "
                "Use o andamento para tramitação interna entre setores."
            )
        logger.info(
            "Demanda pk=%s — %s perna(s) transversal(is) adicionada(s).",
            demanda.pk,
            len(criadas),
        )
        return criadas

    @transaction.atomic
    def iniciar_execucao_pernas(self, demanda: Demanda) -> int:
        atualizadas = PernaOperacional.objects.filter(
            demanda_id=demanda.pk,
            status=StatusPernaOperacional.PENDENTE,
        ).update(status=StatusPernaOperacional.EM_EXECUCAO)
        return int(atualizadas)

    @transaction.atomic
    def cancelar_pernas(self, demanda: Demanda, *, motivo: str = "devolucao") -> int:
        return PernaOperacional.objects.filter(
            demanda_id=demanda.pk,
            status__in=(
                StatusPernaOperacional.PENDENTE,
                StatusPernaOperacional.EM_EXECUCAO,
            ),
        ).update(status=StatusPernaOperacional.CANCELADA)

    def pernas_nao_concluidas(self, demanda: Demanda) -> list[PernaOperacional]:
        """Pernas ativas que ainda não registraram conclusão parcial."""
        return list(
            PernaOperacional.objects.filter(
                demanda_id=demanda.pk,
                status__in=(
                    StatusPernaOperacional.PENDENTE,
                    StatusPernaOperacional.EM_EXECUCAO,
                ),
            ).select_related("unidade_administrativa")
        )

    def pernas_pendentes_conclusao(self, demanda: Demanda) -> list[PernaOperacional]:
        return self.pernas_nao_concluidas(demanda)

    def todas_pernas_concluidas(self, demanda: Demanda) -> bool:
        """True quando há pernas ativas e todas estão CONCLUIDA."""
        ativas = PernaOperacional.objects.filter(
            demanda_id=demanda.pk,
            status__in=StatusPernaOperacional.ATIVOS,
        )
        if not ativas.exists():
            return False
        return not ativas.exclude(status=StatusPernaOperacional.CONCLUIDA).exists()

    def orgao_tem_perna_concluida(self, demanda: Demanda, orgao_id: int) -> bool:
        return PernaOperacional.objects.filter(
            demanda_id=demanda.pk,
            sinapse_orgao_id=int(orgao_id),
            status=StatusPernaOperacional.CONCLUIDA,
        ).exists()

    @transaction.atomic
    def garantir_perna_orgao(
        self,
        demanda: Demanda,
        orgao_id: int,
        *,
        orgao_lider_imediato_id: int | None = None,
        status: str | None = None,
        unidade_administrativa_id: int | None = None,
    ) -> PernaOperacional:
        """Garante perna individual por órgão (líder incluído) — idempotente."""
        uid = unidade_administrativa_id
        qs = PernaOperacional.objects.filter(
            demanda_id=demanda.pk,
            sinapse_orgao_id=int(orgao_id),
        )
        if uid not in (None, ""):
            perna = qs.filter(unidade_administrativa_id=int(uid)).first()
        else:
            perna = qs.filter(unidade_administrativa_id__isnull=True).first()
            if not perna:
                perna = qs.first()
        if perna:
            if status and perna.status not in (StatusPernaOperacional.CONCLUIDA, StatusPernaOperacional.CANCELADA):
                if perna.status != status:
                    perna.status = status
                    perna.save(update_fields=["status", "atualizada_em"])
            return perna

        lid = int(
            orgao_lider_imediato_id
            or _orgao_lider_processo(demanda)
            or orgao_id
        )
        st = status or (
            StatusPernaOperacional.EM_EXECUCAO
            if demanda.status == "EM_EXECUCAO"
            else StatusPernaOperacional.PENDENTE
        )
        unidade = None
        if uid not in (None, ""):
            from core.models_unidade_administrativa import UnidadeAdministrativa

            unidade = UnidadeAdministrativa.objects.filter(
                pk=int(uid), ativo=True, sinapse_orgao_id=int(orgao_id)
            ).first()
        max_ordem = (
            PernaOperacional.objects.filter(demanda_id=demanda.pk)
            .order_by("-ordem")
            .values_list("ordem", flat=True)
            .first()
            or 0
        )
        return PernaOperacional.objects.create(
            demanda=demanda,
            sinapse_orgao_id=int(orgao_id),
            unidade_administrativa=unidade,
            ordem=max_ordem + 1,
            status=st,
            metadata=_metadata_perna(
                origem="sincronizacao",
                orgao_lider_imediato_id=lid,
            ),
        )

    @transaction.atomic
    def sincronizar_pernas_transversal(self, demanda: Demanda) -> None:
        """
        Repara demandas sem perna do líder ou com conclusões só na timeline.
        Idempotente — seguro chamar ao montar estado operacional.
        """
        from core.models_operacional import EventoOperacional

        lider_id = _orgao_lider_processo(demanda)
        if not lider_id:
            return

        status_exec = (
            StatusPernaOperacional.EM_EXECUCAO
            if demanda.status == "EM_EXECUCAO"
            else StatusPernaOperacional.PENDENTE
        )
        self.garantir_perna_orgao(
            demanda,
            int(lider_id),
            orgao_lider_imediato_id=int(lider_id),
            status=status_exec,
        )

        for tram in demanda.tramitacoes.filter(tipo="EXECUCAO").order_by("timestamp"):
            meta = tram.metadata if isinstance(tram.metadata, dict) else {}
            if meta.get("acao") != "ABERTURA_PERNAS_TRANSVERSAL":
                continue
            gestor = int(meta.get("orgao_gestor_id") or lider_id)
            for item in meta.get("pernas") or []:
                oid = item.get("secretaria_id")
                if not oid:
                    continue
                uid = item.get("unidade_administrativa_id")
                self.garantir_perna_orgao(
                    demanda,
                    int(oid),
                    orgao_lider_imediato_id=gestor,
                    status=status_exec,
                    unidade_administrativa_id=int(uid) if uid not in (None, "") else None,
                )

        for tram in demanda.tramitacoes.filter(tipo=EventoOperacional.CONCLUSAO_PARCIAL).order_by(
            "timestamp"
        ):
            meta = tram.metadata if isinstance(tram.metadata, dict) else {}
            perna = None
            pid = meta.get("perna_id")
            if pid:
                perna = PernaOperacional.objects.filter(pk=int(pid), demanda_id=demanda.pk).first()
            if not perna:
                oid = meta.get("sinapse_orgao_id")
                if oid:
                    candidatos = [
                        p
                        for p in self.pernas_nao_concluidas(demanda)
                        if int(p.sinapse_orgao_id) == int(oid)
                    ]
                    if len(candidatos) == 1:
                        perna = candidatos[0]
            if perna and perna.status != StatusPernaOperacional.CONCLUIDA:
                self.marcar_concluida(perna, tram)

    def resolver_perna_para_conclusao(
        self,
        demanda: Demanda,
        orgao_id: int,
        *,
        perna_id: int | None = None,
    ) -> PernaOperacional | None:
        pendentes = [
            p
            for p in self.pernas_nao_concluidas(demanda)
            if int(p.sinapse_orgao_id) == int(orgao_id)
        ]
        if not pendentes:
            return None
        if perna_id:
            return next((p for p in pendentes if p.pk == int(perna_id)), None)
        if len(pendentes) == 1:
            return pendentes[0]
        return None

    def contar_pendentes_orgao(self, demanda: Demanda, orgao_id: int) -> int:
        return len(
            [
                p
                for p in self.pernas_nao_concluidas(demanda)
                if int(p.sinapse_orgao_id) == int(orgao_id)
            ]
        )

    def filhos_pernas_pendentes(self, demanda: Demanda, orgao_gestor_id: int) -> list[PernaOperacional]:
        """Sub-pernas abertas por orgao_gestor_id ainda sem conclusão parcial."""
        gestor = int(orgao_gestor_id)
        return [
            p
            for p in self.pernas_nao_concluidas(demanda)
            if int((p.metadata or {}).get("orgao_lider_imediato_id") or 0) == gestor
        ]

    def orgao_lider_imediato_perna(self, perna: PernaOperacional) -> int | None:
        meta = perna.metadata if isinstance(perna.metadata, dict) else {}
        lid = meta.get("orgao_lider_imediato_id")
        if lid:
            return int(lid)
        return _orgao_lider_processo(perna.demanda)

    def serializar_perna(self, perna: PernaOperacional) -> dict[str, Any]:
        ua = perna.unidade_administrativa
        setor = None
        if ua:
            setor = ua.sigla or ua.nome
        lid = self.orgao_lider_imediato_perna(perna)
        return {
            "perna_id": perna.pk,
            "demanda_id": perna.demanda_id,
            "sinapse_orgao_id": perna.sinapse_orgao_id,
            "orgao_nome": sinapse_catalog.get_orgao_nome(perna.sinapse_orgao_id),
            "unidade_administrativa_id": ua.pk if ua else None,
            "setor_nome": setor,
            "status": perna.status,
            "ordem": perna.ordem,
            "concluida": perna.status == StatusPernaOperacional.CONCLUIDA,
            "orgao_lider_imediato_id": lid,
            "orgao_lider_imediato_nome": sinapse_catalog.get_orgao_nome(lid) if lid else None,
        }

    def participantes_transversal(self, demanda: Demanda) -> list[dict[str, Any]]:
        return [self.serializar_perna(p) for p in self.listar_pernas(demanda)]

    def pendencias_conclusao(self, demanda: Demanda) -> list[dict[str, Any]]:
        return [
            self.serializar_perna(p)
            for p in self.pernas_pendentes_conclusao(demanda)
        ]

    @transaction.atomic
    def marcar_concluida(
        self,
        perna: PernaOperacional,
        tramitacao: Tramitacao,
    ) -> PernaOperacional:
        perna.status = StatusPernaOperacional.CONCLUIDA
        perna.conclusao_tramitacao = tramitacao
        perna.save(update_fields=["status", "conclusao_tramitacao", "atualizada_em"])
        return perna

    def orgaos_com_perna_ativa(self, demanda_id: int) -> set[int]:
        return set(
            PernaOperacional.objects.filter(
                demanda_id=demanda_id,
                status__in=StatusPernaOperacional.ATIVOS,
            ).values_list("sinapse_orgao_id", flat=True)
        )

    def demanda_ids_visiveis_por_orgao(self, orgao_id: int) -> list[int]:
        """Demandas em que a secretaria tem perna ativa (escopo P3)."""
        from core.services.demanda_visibilidade import _scatter_orgao_encerrado

        ids: list[int] = []
        for did in (
            PernaOperacional.objects.filter(
                sinapse_orgao_id=int(orgao_id),
                status__in=StatusPernaOperacional.ATIVOS,
            )
            .values_list("demanda_id", flat=True)
            .distinct()
        ):
            if _scatter_orgao_encerrado(int(did), int(orgao_id)):
                continue
            ids.append(int(did))
        return ids
