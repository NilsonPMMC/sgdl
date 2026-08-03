"""Despacho unitário e multi-secretaria de demanda (Protocolo manual ou automático)."""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.utils import timezone

from core.models import ClusterExecucao, Demanda, Tramitacao
from core.services.demanda_despacho_destinos import (
    normalizar_destinos_multi_orgao,
    pernas_para_resumo,
)
from core.services.operacional_estado_service import OperacionalEstadoService
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

    def limpar_rastros_reprotocolo(self, demanda: Demanda) -> None:
        """Zera campos de despacho quando a demanda volta à fila do Protocolo."""
        if demanda.status != "AGUARDANDO_PROTOCOLO":
            return
        update_fields: list[str] = []
        if demanda.protocolo_executivo:
            demanda.protocolo_executivo = None
            update_fields.append("protocolo_executivo")
        if demanda.data_inicio_prazo:
            demanda.data_inicio_prazo = None
            update_fields.append("data_inicio_prazo")
        if demanda.unidade_administrativa_id:
            demanda.unidade_administrativa = None
            update_fields.append("unidade_administrativa")
        if demanda.prazo_efetivo_dias is not None:
            demanda.prazo_efetivo_dias = None
            update_fields.append("prazo_efetivo_dias")
        if demanda.prazo_origem:
            demanda.prazo_origem = ""
            update_fields.append("prazo_origem")
        if demanda.fluxo_roteamento:
            demanda.fluxo_roteamento = ""
            update_fields.append("fluxo_roteamento")
        if demanda.sinapse_orgao_lider_id:
            demanda.sinapse_orgao_lider_id = None
            update_fields.append("sinapse_orgao_lider_id")
        if update_fields:
            demanda.save(update_fields=update_fields)
        from core.services.perna_operacional_service import PernaOperacionalService

        PernaOperacionalService().cancelar_pernas(demanda, motivo="reprotocolo")
        from core.services.perna_operacional_service import PernaOperacionalService

        PernaOperacionalService().cancelar_pernas(demanda, motivo="reprotocolo")

    def preparar_redespacho_protocolo(self, demanda: Demanda) -> None:
        """Recupera demanda inconsistente (assinatura sem despacho efetivado)."""
        if demanda.status != "AGUARDANDO_PROTOCOLO":
            return
        from core.models_assinatura_eletronica import (
            AssinaturaEletronica,
            AssinaturaValidacaoGestor,
        )
        from core.services.assinatura_eletronica_service import AssinaturaEletronicaService

        assinatura_svc = AssinaturaEletronicaService()
        # Despacho diferido: operador assinou e aguarda gestor — não limpar o ciclo atual.
        if AssinaturaValidacaoGestor.objects.filter(
            demanda=demanda,
            etapa=AssinaturaEletronica.ETAPA_DESPACHO_INICIAL,
            status=AssinaturaValidacaoGestor.STATUS_PENDENTE,
        ).exists():
            return
        if not assinatura_svc.possui_assinatura_despacho_inicial(demanda):
            return
        assinatura_svc.liberar_assinaturas_despacho_inicial(demanda)
        self.limpar_rastros_reprotocolo(demanda)
        logger.warning(
            "Demanda pk=%s recuperada para re-despacho (assinatura anterior sem protocolação).",
            demanda.pk,
        )

    def despachar_multiplo(
        self,
        demanda: Demanda,
        destinos: list[dict[str, Any]],
        *,
        usuario=None,
        automatico: bool = False,
        protocolo_executivo: str | None = None,
        arquivos_anexos: list | None = None,
        orquestrador_conclusao: str | None = None,
        texto_despacho: str | None = None,
        tramitacao_existente: Tramitacao | None = None,
    ) -> dict[str, Any]:
        """P3 — uma demanda, N pernas operacionais (órgão × setor)."""
        del orquestrador_conclusao  # legado
        if demanda.status != "AGUARDANDO_PROTOCOLO":
            raise ValueError("Apenas demandas aguardando protocolo podem ser despachadas.")
        if not destinos:
            raise ValueError("Informe ao menos um destino.")

        plano = normalizar_destinos_multi_orgao(demanda, destinos)
        destinos_orgao = plano["destinos"]
        pernas = plano.get("pernas") or []
        orgaos_integrados_ids: list[int] = plano.get("orgaos_integrados_ids") or []

        operacional = OperacionalEstadoService()
        operacional.validar_triagem_protocolo(
            demanda,
            usuario,
            total_destinos=len(destinos_orgao),
        )

        with transaction.atomic():
            primeira = destinos_orgao[0]
            principal = self.despachar(
                demanda,
                secretaria_id=int(primeira["secretaria_id"]),
                usuario=usuario,
                automatico=automatico,
                unidade_administrativa_id=primeira.get("unidade_administrativa_id"),
                protocolo_executivo=protocolo_executivo,
                multi_total=len(destinos_orgao),
                multi_indice=1,
                orgaos_integrados_ids=orgaos_integrados_ids or None,
                pernas_resumo=pernas,
                texto_despacho=texto_despacho,
                tramitacao_existente=tramitacao_existente,
            )
            tram_despacho = tramitacao_existente or (
                principal.tramitacoes.filter(tipo="DESPACHO").order_by("-timestamp").first()
            )

            from core.services.perna_operacional_service import PernaOperacionalService

            pernas_criadas = PernaOperacionalService().criar_pernas_no_despacho(
                principal,
                pernas,
                despacho_tramitacao=tram_despacho,
            )

            if arquivos_anexos and tram_despacho and not tramitacao_existente:
                from core.services.tramitacao_anexo_service import anexar_arquivos_tramitacao

                anexar_arquivos_tramitacao(tram_despacho, arquivos_anexos, copiar=False)

            triagem_meta = operacional.aplicar_triagem_protocolo(
                principal,
                total_destinos=len(destinos_orgao),
                secretaria_lider_id=int(primeira["secretaria_id"]),
                usuario=usuario,
                destinos_resumo=pernas_para_resumo(pernas) if pernas else [
                    {
                        "secretaria_id": int(d["secretaria_id"]),
                        "unidade_administrativa_id": d.get("unidade_administrativa_id"),
                        "unidade_administrativa_ids": d.get("unidade_administrativa_ids") or [],
                    }
                    for d in destinos_orgao
                ],
            )
            if tram_despacho and triagem_meta:
                meta = dict(tram_despacho.metadata if isinstance(tram_despacho.metadata, dict) else {})
                meta.update(triagem_meta)
                tram_despacho.metadata = meta
                tram_despacho.save(update_fields=["metadata"])
            perfil = operacional.definir_perfil_processo_no_despacho(
                principal,
                usuario=usuario,
                automatico=automatico,
            )
            logger.info(
                "Perfil processo %s — demanda pk=%s, %s perna(s), %s órgão(s).",
                perfil,
                principal.pk,
                len(pernas_criadas),
                len(destinos_orgao),
            )

        principal.refresh_from_db()
        return {
            "demanda": principal,
            "tramitacao_despacho_id": tram_despacho.pk if tram_despacho else None,
            "demandas_desdobradas": [],
            "pernas_operacionais": [
                {
                    "id": p.pk,
                    "sinapse_orgao_id": p.sinapse_orgao_id,
                    "unidade_administrativa_id": p.unidade_administrativa_id,
                    "ordem": p.ordem,
                }
                for p in pernas_criadas
            ],
            "total_destinos": len(destinos_orgao),
            "total_pernas": len(pernas),
            "orgao_competente_id": plano.get("orgao_competente_id"),
            "orgaos_integrados_ids": orgaos_integrados_ids,
        }

    def _clonar_demanda_para_destino(
        self,
        origem: Demanda,
        *,
        secretaria_id: int,
        unidade_administrativa_id: int | None,
        usuario,
        automatico: bool,
        multi_total: int,
        multi_indice: int,
    ) -> Demanda:
        leg_base = origem.protocolo_legislativo or f"REF-{origem.pk}"
        leg = f"{leg_base}-D{multi_indice}"[:64]

        clone = Demanda.objects.create(
            titulo=origem.titulo,
            descricao=origem.descricao,
            autor=origem.autor,
            cep=origem.cep,
            logradouro=origem.logradouro,
            numero=origem.numero,
            complemento=origem.complemento,
            bairro=origem.bairro,
            latitude=origem.latitude,
            longitude=origem.longitude,
            protocolo_legislativo=leg,
            sinapse_servico_id=origem.sinapse_servico_id,
            sinapse_orgao_id=secretaria_id,
            origem_vinculo=origem.origem_vinculo,
            tendencia=origem.tendencia,
            status="AGUARDANDO_PROTOCOLO",
        )
        return self.despachar(
            clone,
            secretaria_id=secretaria_id,
            usuario=usuario,
            automatico=automatico,
            unidade_administrativa_id=unidade_administrativa_id,
            protocolo_executivo=proximo_protocolo_executivo(),
            multi_total=multi_total,
            multi_indice=multi_indice,
            demanda_origem_id=origem.pk,
        )

    def _vincular_cluster_multi_orgao(
        self,
        lider: Demanda,
        clones: list[Demanda],
        *,
        usuario,
    ) -> None:
        from core.services.cluster_service import ClusterService

        cluster = lider.cluster
        if not cluster:
            cluster = ClusterExecucao.objects.create(
                sinapse_servico_id=lider.sinapse_servico_id,
                status="EM_ANDAMENTO",
                titulo=f"Multi-destino — {lider.protocolo_legislativo or lider.pk}"[:150],
            )
            lider.cluster = cluster
            lider.save(update_fields=["cluster"])

        svc = ClusterService()
        for clone in clones:
            try:
                svc.vincular_demanda_manual(clone, cluster, usuario=usuario)
            except ValueError:
                clone.cluster = cluster
                clone.save(update_fields=["cluster"])

    def despachar(
        self,
        demanda: Demanda,
        *,
        secretaria_id: int,
        usuario=None,
        automatico: bool = False,
        unidade_administrativa_id: int | None = None,
        protocolo_executivo: str | None = None,
        multi_total: int = 1,
        multi_indice: int = 1,
        demanda_origem_id: int | None = None,
        orgaos_integrados_ids: list[int] | None = None,
        pernas_resumo: list[dict[str, Any]] | None = None,
        texto_despacho: str | None = None,
        tramitacao_existente: Tramitacao | None = None,
    ) -> Demanda:
        if demanda.status != "AGUARDANDO_PROTOCOLO":
            raise ValueError("Apenas demandas aguardando protocolo podem ser despachadas.")

        orgao_id = int(secretaria_id)
        if not sinapse_catalog.orgao_existe(orgao_id):
            raise ValueError("Órgão não encontrado no catálogo Sinapse.")

        orgao_nome = sinapse_catalog.get_orgao_nome(orgao_id) or str(orgao_id)
        protocolo_exec = (protocolo_executivo or "").strip() or proximo_protocolo_executivo()
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
        if not demanda.fluxo_roteamento:
            from core.models_operacional import FluxoRoteamento

            demanda.fluxo_roteamento = (
                FluxoRoteamento.FLUXO_TRANSVERSAL
                if multi_total > 1
                else FluxoRoteamento.FLUXO_DIRETO
            )
            demanda.sinapse_orgao_lider_id = orgao_id
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
            "fluxo_roteamento",
            "sinapse_orgao_lider_id",
        ]
        if unidade:
            update_fields.append("unidade_administrativa")
        demanda.save(update_fields=update_fields)

        texto = (texto_despacho or "").strip()
        if automatico and not texto:
            if multi_total > 1:
                descricao = (
                    f"Despacho automático multi-secretaria ({multi_indice}/{multi_total}) "
                    f"→ {orgao_nome}. Protocolo executivo: {protocolo_exec}."
                )
            else:
                descricao = (
                    f"Despacho automático (fluxo configurado para o serviço da carta) "
                    f"→ {orgao_nome}. Protocolo executivo: {protocolo_exec}."
                )
        else:
            if len(texto) < 10:
                raise ValueError(
                    "Informe o texto do despacho do protocolo (mínimo 10 caracteres)."
                )
            descricao = texto

        from core.services.texto_padrao_despacho_service import resolver_descricao_tramitacao

        setor_destino = ""
        if unidade:
            setor_destino = (unidade.sigla or unidade.nome or "").strip()
        descricao = resolver_descricao_tramitacao(
            demanda,
            descricao,
            orgao_destino=orgao_nome,
            setor_destino=setor_destino,
            extra={"protocolo_executivo": protocolo_exec},
        )

        from core.services.tramitacao_setor_service import UnidadeAdministrativaService

        unidade_origem = None
        if usuario:
            unidade_origem = UnidadeAdministrativaService().unidade_principal_usuario(usuario)

        tram = tramitacao_existente
        meta_tram = {
            "etapa": "DESPACHO_PROTOCOLO",
            "protocolo_executivo": protocolo_exec,
            "total_pernas": len(pernas_resumo or []),
            "pernas": pernas_resumo or [],
            "multi_total": multi_total,
            "multi_indice": multi_indice,
        }
        if tram is not None:
            meta_atual = dict(tram.metadata if isinstance(tram.metadata, dict) else {})
            meta_atual.update(meta_tram)
            meta_atual.pop("aguardando_validacao_gestor", None)
            tram.descricao = descricao
            tram.unidade_destino = unidade
            tram.metadata = meta_atual
            tram.save(update_fields=["descricao", "unidade_destino", "metadata"])
        else:
            tram = Tramitacao.objects.create(
                demanda=demanda,
                responsavel=usuario,
                tipo="DESPACHO",
                descricao=descricao,
                unidade_origem=unidade_origem,
                unidade_destino=unidade,
                metadata=meta_tram,
            )

        if automatico:
            from core.services.assinatura_eletronica_service import AssinaturaEletronicaService

            AssinaturaEletronicaService().registrar_assinatura_despacho_automatico(demanda)

        if automatico and multi_total == 1 and not demanda_origem_id:
            operacional = OperacionalEstadoService()
            operacional.aplicar_triagem_protocolo(
                demanda,
                total_destinos=1,
                secretaria_lider_id=orgao_id,
                usuario=usuario,
            )
            operacional.definir_perfil_processo_no_despacho(
                demanda, usuario=usuario, automatico=True
            )
            from core.services.perna_operacional_service import PernaOperacionalService

            if not PernaOperacionalService().demanda_usa_pernas(demanda):
                PernaOperacionalService().criar_pernas_no_despacho(
                    demanda,
                    [
                        {
                            "secretaria_id": orgao_id,
                            "unidade_administrativa_id": unidade.pk if unidade else None,
                        }
                    ],
                    despacho_tramitacao=tram,
                )
            from core.services.perna_operacional_service import PernaOperacionalService

            if not PernaOperacionalService().demanda_usa_pernas(demanda):
                PernaOperacionalService().criar_pernas_no_despacho(
                    demanda,
                    [
                        {
                            "secretaria_id": orgao_id,
                            "unidade_administrativa_id": unidade.pk if unidade else None,
                        }
                    ],
                    despacho_tramitacao=tram,
                )

        if usuario and demanda.cluster_id:
            from core.services.cluster_aderencia_service import integrar_cluster_apos_protocolo

            integrar_cluster_apos_protocolo(demanda, usuario=usuario)

        logger.info(
            "Demanda pk=%s despachada (%s) → orgao=%s protocolo=%s",
            demanda.pk,
            "auto" if automatico else "manual",
            orgao_id,
            protocolo_exec,
        )
        return demanda
