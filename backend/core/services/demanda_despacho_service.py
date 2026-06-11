"""Despacho unitário de demanda (Protocolo manual ou automático)."""

from __future__ import annotations

import logging

from django.utils import timezone

from core.models import Demanda, Tramitacao
from integrations import sinapse_catalog

logger = logging.getLogger(__name__)


def proximo_protocolo_executivo() -> str:
    ano = timezone.now().year
    ultimo = (
        Demanda.objects.filter(protocolo_executivo__startswith=f"{ano}-")
        .order_by("-protocolo_executivo")
        .first()
    )
    novo = 1
    if ultimo and ultimo.protocolo_executivo:
        try:
            novo = int(ultimo.protocolo_executivo.split("-")[-1]) + 1
        except (ValueError, IndexError):
            novo = (
                Demanda.objects.filter(protocolo_executivo__startswith=f"{ano}-").count()
                + 1
            )
    return f"{ano}-{novo:04d}"


class DemandaDespachoService:
    """Protocola e despacha uma demanda aguardando protocolo."""

    def despachar(
        self,
        demanda: Demanda,
        *,
        secretaria_id: int,
        usuario=None,
        automatico: bool = False,
        unidade_administrativa_id: int | None = None,
    ) -> Demanda:
        if demanda.status != "AGUARDANDO_PROTOCOLO":
            raise ValueError("Apenas demandas aguardando protocolo podem ser despachadas.")

        orgao_id = int(secretaria_id)
        if not sinapse_catalog.orgao_existe(orgao_id):
            raise ValueError("Órgão não encontrado no catálogo Sinapse.")

        orgao_nome = sinapse_catalog.get_orgao_nome(orgao_id) or str(orgao_id)
        protocolo_exec = proximo_protocolo_executivo()
        agora = timezone.now()

        unidade = None
        if unidade_administrativa_id:
            from core.models_unidade_administrativa import UnidadeAdministrativa

            try:
                unidade = UnidadeAdministrativa.objects.get(
                    pk=int(unidade_administrativa_id), ativo=True
                )
            except (UnidadeAdministrativa.DoesNotExist, TypeError, ValueError):
                raise ValueError("Setor de destino não encontrado ou inativo.")
            if int(unidade.sinapse_orgao_id) != orgao_id:
                raise ValueError("O setor informado não pertence ao órgão de despacho.")
        elif demanda.sinapse_servico_id:
            from core.services.carta_setor_service import CartaSetorService

            unidade = CartaSetorService().resolver_unidade(int(demanda.sinapse_servico_id))

        demanda.sinapse_orgao_id = orgao_id
        demanda.protocolo_executivo = protocolo_exec
        demanda.status = "PROTOCOLADO"
        demanda.data_inicio_prazo = agora
        from core.services.prazo_demanda_service import PrazoDemandaService

        PrazoDemandaService().aplicar_snapshot_protocolo(demanda)
        if unidade:
            demanda.unidade_administrativa = unidade
        update_fields = [
            "sinapse_orgao_id",
            "protocolo_executivo",
            "status",
            "data_inicio_prazo",
            "prazo_efetivo_dias",
            "prazo_origem",
        ]
        if unidade:
            update_fields.append("unidade_administrativa")
        demanda.save(update_fields=update_fields)

        if automatico:
            descricao = (
                f"Despacho automático (fluxo configurado para o serviço da carta) "
                f"→ {orgao_nome}. Protocolo executivo: {protocolo_exec}."
            )
        else:
            descricao = (
                f"Demanda despachada para a secretaria: {orgao_nome}. "
                f"Protocolo do Executivo gerado: {protocolo_exec}."
            )
        if unidade:
            rotulo = unidade.sigla or unidade.nome
            descricao += f"\nSetor operacional: {rotulo}."

        Tramitacao.objects.create(
            demanda=demanda,
            responsavel=usuario,
            tipo="DESPACHO",
            descricao=descricao,
            unidade_destino=unidade,
        )

        logger.info(
            "Demanda pk=%s despachada (%s) → orgao=%s protocolo=%s",
            demanda.pk,
            "auto" if automatico else "manual",
            orgao_id,
            protocolo_exec,
        )
        return demanda
