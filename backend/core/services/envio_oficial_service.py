"""Envio oficial de ofícios (unitário e em lote) com assinatura eletrônica."""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from core.models import Demanda, Tramitacao
from core.services.assinatura_eletronica_service import (
    DECLARACAO_ENVIO,
    AssinaturaEletronicaService,
)
from core.services.protocolo_numeracao_service import proximo_protocolo_legislativo
from integrations import sinapse_catalog

logger = logging.getLogger(__name__)


def demanda_trilha_tendencia(demanda: Demanda) -> bool:
    return bool(
        demanda.tendencia_id
        or demanda.origem_vinculo == Demanda.ORIGEM_VINCULO_TENDENCIA
    )


def orgao_id_para_envio_demanda(demanda: Demanda) -> int | None:
    if demanda.sinapse_orgao_id:
        return int(demanda.sinapse_orgao_id)
    tendencia = demanda.tendencia
    if tendencia and tendencia.sinapse_orgao_id:
        return int(tendencia.sinapse_orgao_id)
    if demanda.sinapse_servico_id:
        return sinapse_catalog.get_orgao_id_for_servico(int(demanda.sinapse_servico_id))
    return None


class EnvioOficialService:
    def _pode_enviar_demanda(self, demanda: Demanda, usuario) -> None:
        if demanda.status != "RASCUNHO":
            raise ValueError("Esta demanda já foi enviada.")
        if demanda.autor_id != usuario.pk and getattr(usuario, "perfil", None) != "GESTOR":
            raise ValueError("Apenas o autor do ofício (ou gestor) pode enviar oficialmente.")

    def _validar_requisitos_envio(self, demanda: Demanda) -> None:
        trilha_tendencia = demanda_trilha_tendencia(demanda)
        if trilha_tendencia:
            if not demanda.tendencia_id:
                raise ValueError(
                    "Não é possível enviar. Esta solicitação está na trilha de tendência "
                    "mas não possui tendência vinculada."
                )
            return

        if not demanda.sinapse_servico_id:
            raise ValueError(
                "Não é possível enviar. A demanda não possui um serviço vinculado na carta Sinapse."
            )
        from core.services.carta_utilizacao_service import CartaUtilizacaoService

        CartaUtilizacaoService().validar_protocolo(
            int(demanda.sinapse_servico_id),
            contexto="envio_oficial",
        )
        orgao_id = sinapse_catalog.get_orgao_id_for_servico(int(demanda.sinapse_servico_id))
        if not orgao_id:
            raise ValueError(
                "Não é possível enviar. O serviço não tem órgão responsável no catálogo."
            )

    def preparar_preview(self, demanda: Demanda, usuario) -> dict[str, Any]:
        self._pode_enviar_demanda(demanda, usuario)
        preview = AssinaturaEletronicaService().preparar_preview_envio(demanda)
        return {
            "demanda_id": demanda.pk,
            "titulo": demanda.titulo,
            **preview,
        }

    def preparar_preview_lote(
        self, demanda_ids: list[int], usuario
    ) -> dict[str, Any]:
        if not demanda_ids:
            raise ValueError("Informe ao menos uma demanda para pré-visualização.")
        if len(demanda_ids) > 50:
            raise ValueError("Limite de 50 ofícios por lote.")

        demandas = self._carregar_demandas_lote(demanda_ids, usuario)
        itens = []
        for demanda in demandas:
            self._validar_requisitos_envio(demanda)
            itens.append(self.preparar_preview(demanda, usuario))
        return {
            "total": len(itens),
            "itens": itens,
            "declaracao_exigida": DECLARACAO_ENVIO,
        }

    def _carregar_demandas_lote(
        self, demanda_ids: list[int], usuario
    ) -> list[Demanda]:
        ids_unicos = []
        vistos: set[int] = set()
        for raw in demanda_ids:
            try:
                pk = int(raw)
            except (TypeError, ValueError):
                raise ValueError(f"ID de demanda inválido: {raw!r}") from None
            if pk in vistos:
                continue
            vistos.add(pk)
            ids_unicos.append(pk)

        if not ids_unicos:
            raise ValueError("Informe ao menos uma demanda válida.")

        demandas = list(
            Demanda.objects.select_related("tendencia", "autor")
            .filter(pk__in=ids_unicos)
            .order_by("pk")
        )
        encontrados = {d.pk for d in demandas}
        faltando = [pk for pk in ids_unicos if pk not in encontrados]
        if faltando:
            raise ValueError(f"Demanda(s) não encontrada(s): {', '.join(map(str, faltando))}")

        for demanda in demandas:
            self._pode_enviar_demanda(demanda, usuario)
        return demandas

    def _executar_envio(
        self,
        demanda: Demanda,
        usuario,
        *,
        hash_documento: str | None,
        declaracao: str | None,
        request=None,
    ) -> dict[str, Any]:
        self._pode_enviar_demanda(demanda, usuario)
        self._validar_requisitos_envio(demanda)

        assinatura = AssinaturaEletronicaService().registrar_assinatura(
            demanda,
            usuario,
            hash_documento_informado=hash_documento,
            declaracao=declaracao,
            request=request,
        )

        trilha_tendencia = demanda_trilha_tendencia(demanda)
        orgao_id = orgao_id_para_envio_demanda(demanda)
        protocolo_leg = proximo_protocolo_legislativo(demanda.autor_id)

        if orgao_id:
            demanda.sinapse_orgao_id = orgao_id
        if trilha_tendencia:
            demanda.origem_vinculo = Demanda.ORIGEM_VINCULO_TENDENCIA
            demanda.sinapse_servico_id = None
        demanda.protocolo_legislativo = protocolo_leg
        demanda.status = "AGUARDANDO_PROTOCOLO"
        demanda.save()

        if trilha_tendencia:
            tendencia_titulo = (
                demanda.tendencia.titulo if demanda.tendencia_id else "tendência"
            )
            desc_tram = (
                f"Ofício enviado (trilha tendência «{tendencia_titulo}»). "
                f"Protocolo legislativo: {protocolo_leg}. "
                "Aguardando despacho do Protocolo (órgão pode ser definido na carta depois)."
            )
        else:
            desc_tram = (
                f"Demanda enviada oficialmente. Protocolo do Legislativo gerado: {protocolo_leg}."
            )

        Tramitacao.objects.create(
            demanda=demanda,
            responsavel=usuario,
            tipo="ENVIO_OFICIAL",
            descricao=desc_tram,
        )

        svc_ass = AssinaturaEletronicaService()
        return {
            "demanda_id": demanda.pk,
            "protocolo_legislativo": protocolo_leg,
            "titulo": demanda.titulo,
            "status": demanda.status,
            "assinatura_eletronica": {
                "codigo_validacao": assinatura.codigo_validacao,
                "hash_assinatura": assinatura.hash_assinatura,
                "url_validacao": svc_ass.url_qr_validacao(assinatura.codigo_validacao),
            },
        }

    @transaction.atomic
    def enviar_demanda(
        self,
        demanda: Demanda,
        usuario,
        *,
        hash_documento: str | None,
        declaracao: str | None,
        request=None,
    ) -> dict[str, Any]:
        return self._executar_envio(
            demanda,
            usuario,
            hash_documento=hash_documento,
            declaracao=declaracao,
            request=request,
        )

    @transaction.atomic
    def enviar_lote(
        self,
        usuario,
        *,
        demanda_ids: list[int],
        declaracao: str | None,
        hashes: list[dict[str, Any]] | None,
        request=None,
    ) -> dict[str, Any]:
        if not demanda_ids:
            raise ValueError("Informe ao menos uma demanda para envio em lote.")
        if len(demanda_ids) > 50:
            raise ValueError("Limite de 50 ofícios por lote.")

        hash_por_id: dict[int, str] = {}
        for item in hashes or []:
            if not isinstance(item, dict):
                continue
            try:
                did = int(item.get("demanda_id"))
            except (TypeError, ValueError):
                continue
            hash_por_id[did] = (item.get("hash_documento") or "").strip()

        demandas = self._carregar_demandas_lote(demanda_ids, usuario)
        for demanda in demandas:
            self._validar_requisitos_envio(demanda)

        enviadas: list[dict[str, Any]] = []
        for demanda in demandas:
            enviadas.append(
                self._executar_envio(
                    demanda,
                    usuario,
                    hash_documento=hash_por_id.get(int(demanda.pk)),
                    declaracao=declaracao,
                    request=request,
                )
            )

        return {
            "total": len(enviadas),
            "enviadas": enviadas,
        }
