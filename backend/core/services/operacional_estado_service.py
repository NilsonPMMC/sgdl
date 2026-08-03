"""Máquina de estados e validadores — Gestão Operacional (Portal dos Vereadores).

Projeção de estado: ``Demanda.status`` + ``Demanda.fluxo_roteamento``.
Log de eventos: ``Tramitacao`` com ``tipo`` e ``metadata`` (event sourcing lite).
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.utils import timezone

from core.models import Demanda, Tramitacao
from core.models_operacional import (
    ESTADO_AGUARDANDO_CONCLUSAO_FINAL,
    AcaoTriagemProtocolo,
    EventoOperacional,
    FluxoRoteamento,
    ModoEntradaProcesso,
    OrquestradorConclusao,
    PerfilProcesso,
    TipoEntrada,
)
from core.services.cluster_service import CLUSTER_MIN_DEMANDAS
from core.services.demanda_despacho_destinos import orgao_competente_servico
from core.services import operacional_permissions as perm
from core.services.envio_oficial_service import demanda_trilha_tendencia
from core.services.perna_operacional_service import PernaOperacionalService
from integrations import sinapse_catalog

logger = logging.getLogger(__name__)

TIPOS_ANEXOS_TIMELINE_VEREADOR = frozenset(
    {
        EventoOperacional.CONCLUSAO_PARCIAL,
        EventoOperacional.CONCLUSAO_TECNICA,
        "CONCLUSAO",
        EventoOperacional.SOLICITACAO_DEVOLUTIVA,
        EventoOperacional.DEVOLUTIVA_PROTOCOLO,
        EventoOperacional.CONCLUSAO_FINAL,
    }
)


class OperacionalEstadoError(ValueError):
    """Transição de estado inválida ou não permitida."""


class OperacionalPermissaoError(PermissionError):
    """Usuário sem perfil para emitir o evento."""


class OperacionalEstadoService:
    """Validação rígida de transições e registro de eventos operacionais."""

    def __init__(self) -> None:
        self._perna_svc = PernaOperacionalService()

    def _usa_pernas(self, demanda: Demanda) -> bool:
        return self._perna_svc.demanda_usa_pernas(demanda)

    def _payload_anexos_tramitacao(self, tram: Tramitacao) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        for anexo in tram.anexos.all():
            if not anexo.arquivo:
                continue
            payload.append(
                {
                    "id": anexo.pk,
                    "arquivo": anexo.arquivo.url,
                    "nome": anexo.arquivo.name.rsplit("/", 1)[-1],
                }
            )
        return payload

    # ------------------------------------------------------------------ helpers
    def classificar_entrada(self, demanda: Demanda) -> str:
        return perm.classificar_entrada(demanda)

    def resolver_fluxo_roteamento(
        self, *, total_destinos: int, demanda: Demanda | None = None
    ) -> str:
        # C1/C5: Protocolo despacha só ao competente; transversal aberto na execução.
        if demanda is not None:
            if (
                self.resolver_modo_entrada_processo(demanda)
                == ModoEntradaProcesso.CLUSTER_SUPER_OS
            ):
                return FluxoRoteamento.FLUXO_TRANSVERSAL
        if total_destinos > 1:
            return FluxoRoteamento.FLUXO_TRANSVERSAL
        return FluxoRoteamento.FLUXO_DIRETO

    def resolver_modo_entrada_processo(self, demanda: Demanda) -> str:
        if not demanda.cluster_id:
            return ModoEntradaProcesso.OFICIO_UNICO
        from core.services.cluster_service import ClusterService

        if ClusterService().grupo_super_os_ativo(demanda):
            return ModoEntradaProcesso.CLUSTER_SUPER_OS
        autores = (
            Demanda.objects.filter(cluster_id=demanda.cluster_id)
            .values_list("autor_id", flat=True)
            .distinct()
        )
        if len(set(autores)) > 1:
            return ModoEntradaProcesso.CLUSTER_SUPER_OS
        return ModoEntradaProcesso.OFICIO_UNICO

    def resolver_orquestrador_conclusao(
        self,
        *,
        fluxo_roteamento: str,
        automatico: bool = False,
        orquestrador_explicito: str | None = None,
    ) -> str:
        if fluxo_roteamento == FluxoRoteamento.FLUXO_DIRETO:
            return OrquestradorConclusao.SECRETARIA_LIDER
        if orquestrador_explicito in OrquestradorConclusao.VALID:
            return orquestrador_explicito
        if automatico:
            return OrquestradorConclusao.PROTOCOLO
        return OrquestradorConclusao.SECRETARIA_LIDER

    def resolver_perfil_processo(self, demanda: Demanda) -> str | None:
        if not demanda.fluxo_roteamento:
            return None
        modo = demanda.modo_entrada_processo or self.resolver_modo_entrada_processo(
            demanda
        )
        orq = demanda.orquestrador_conclusao or OrquestradorConclusao.SECRETARIA_LIDER
        return PerfilProcesso.resolver(
            modo_entrada=modo,
            fluxo_roteamento=demanda.fluxo_roteamento,
            orquestrador_conclusao=orq,
        )

    def participantes_processo_operacional(self, lider: Demanda) -> list[Demanda]:
        if self._eh_fluxo_transversal(lider) and lider.cluster_id:
            return self.participantes_fluxo_transversal(lider)
        return [lider]

    @transaction.atomic
    def definir_perfil_processo_no_despacho(
        self,
        lider: Demanda,
        *,
        usuario,
        automatico: bool = False,
        orquestrador_conclusao: str | None = None,
    ) -> str:
        """Define metadados do processo e entra em EM_OPERACAO com nós scatter-gather."""
        del orquestrador_conclusao  # legado — orquestrador removido do produto
        lider.refresh_from_db()
        modo = self.resolver_modo_entrada_processo(lider)
        fluxo = lider.fluxo_roteamento
        perfil = PerfilProcesso.resolver(
            modo_entrada=modo,
            fluxo_roteamento=fluxo,
            orquestrador_conclusao=OrquestradorConclusao.PROTOCOLO,
        )

        update = {
            "modo_entrada_processo": modo,
            "orquestrador_conclusao": "",
            "inicio_execucao_automatico": True,
        }
        ids = [lider.pk] + [
            d.pk
            for d in self.participantes_fluxo_transversal(lider)
            if d.pk != lider.pk
        ]
        Demanda.objects.filter(pk__in=ids).update(**update)
        lider.refresh_from_db()

        tram_triagem = (
            lider.tramitacoes.filter(tipo=EventoOperacional.TRIAGEM_PROTOCOLO)
            .order_by("-timestamp")
            .first()
        )
        tram_despacho = (
            lider.tramitacoes.filter(tipo=EventoOperacional.DESPACHO)
            .order_by("-timestamp")
            .first()
        )
        alvo_meta = tram_triagem or tram_despacho
        if alvo_meta:
            meta = dict(alvo_meta.metadata if isinstance(alvo_meta.metadata, dict) else {})
            meta.update(
                {
                    "perfil_processo": perfil,
                    "inicio_execucao_automatico": True,
                    "scatter_gather": True,
                }
            )
            alvo_meta.metadata = meta
            alvo_meta.save(update_fields=["metadata"])

        self.aplicar_entrada_operacao(lider, usuario, perfil=perfil)
        return perfil

    @transaction.atomic
    def aplicar_entrada_operacao(
        self,
        lider: Demanda,
        usuario,
        *,
        perfil: str | None = None,
    ) -> None:
        """PROTOCOLADO → EM_OPERACAO com bootstrap de nós operacionais."""
        perfil = perfil or self.resolver_perfil_processo(lider)
        self._perna_svc.iniciar_execucao_pernas(lider)
        for alvo in self.participantes_processo_operacional(lider):
            if alvo.status != "PROTOCOLADO":
                continue
            alvo.status = "EM_EXECUCAO"
            alvo.save(update_fields=["status"])
        from core.services.scatter_gather_service import NoOperacionalService

        NoOperacionalService().bootstrap_nos_iniciais(lider, usuario)

        from core.services.cluster_aderencia_service import ClusterAderenciaService

        ClusterAderenciaService().integrar_seguidoras_sem_protocolo_ao_operacional(
            lider, usuario=usuario
        )

    @transaction.atomic
    def aplicar_inicio_execucao(self, demanda: Demanda, usuario) -> Demanda:
        """Legado — reforça entrada em EM_OPERACAO se ainda protocolado."""
        lider = self.demanda_processo_lider(demanda)
        if lider.status == "EM_EXECUCAO":
            from core.services.scatter_gather_service import NoOperacionalService

            sg = NoOperacionalService()
            if not sg.nos_abertos_qs(lider.pk).exists():
                sg.bootstrap_nos_iniciais(lider, usuario)
            return lider
        self.validar_inicio_execucao(demanda, usuario)
        if demanda.pk != lider.pk and self._usa_pernas(lider):
            raise OperacionalEstadoError(
                "Inicie a execução na demanda principal do processo."
            )
        if demanda.pk != lider.pk and self._eh_fluxo_transversal(lider):
            raise OperacionalEstadoError(
                "Inicie a execução na demanda líder do processo transversal."
            )
        perfil = self.resolver_perfil_processo(lider)
        self.aplicar_entrada_operacao(lider, usuario, perfil=perfil)
        return lider

    @transaction.atomic
    def aplicar_abertura_pernas_transversal(
        self,
        demanda: Demanda,
        usuario,
        *,
        destinos_raw: dict[str, Any],
        observacao: str = "",
    ) -> dict[str, Any]:
        from core.services.demanda_despacho_destinos import (
            filtrar_pernas_abertura_transversal,
            parse_destinos_despacho,
            pernas_para_resumo,
        )

        lider = self.demanda_processo_lider(demanda)
        orgao_user = perm.orgao_usuario(usuario)
        if orgao_user is None:
            raise OperacionalPermissaoError(
                "Apenas secretarias do fluxo transversal podem abrir tramitação."
            )
        self._exigir_perfil(
            perm.usuario_pode_orquestrar_transversal(usuario, lider),
            "Apenas secretarias com perna ativa podem abrir tramitação transversal.",
        )
        self._exigir_estado(
            lider.status == "EM_EXECUCAO",
            "Abertura transversal só durante a execução operacional.",
        )

        pernas_solicitadas = parse_destinos_despacho(destinos_raw)
        pernas_novas = filtrar_pernas_abertura_transversal(
            lider, pernas_solicitadas, orgao_abridor_id=int(orgao_user)
        )
        if not pernas_novas:
            raise OperacionalEstadoError(
                "Informe ao menos um órgão integrado (diferente do seu) "
                "com setor ainda não aberto neste processo."
            )

        texto_obs = (observacao or "").strip()
        orgao_gestor_nome = sinapse_catalog.get_orgao_nome(int(orgao_user)) or str(orgao_user)
        orgaos_nomes = [
            sinapse_catalog.get_orgao_nome(int(p["secretaria_id"]))
            or str(p["secretaria_id"])
            for p in pernas_novas
        ]
        descricao = (
            f"{orgao_gestor_nome} abriu tramitação transversal — "
            f"{len(pernas_novas)} perna(s) em: {', '.join(dict.fromkeys(orgaos_nomes))}."
        )
        if texto_obs:
            descricao += f"\nObservação: {texto_obs}"

        pernas_resumo = pernas_para_resumo(pernas_novas)
        for p in pernas_resumo:
            p["orgao_nome"] = sinapse_catalog.get_orgao_nome(int(p["secretaria_id"]))

        tram = self.registrar_evento(
            lider,
            tipo="EXECUCAO",
            usuario=usuario,
            descricao=descricao,
            metadata={
                "acao": "ABERTURA_PERNAS_TRANSVERSAL",
                "pernas": pernas_resumo,
                "perfil_processo": self.resolver_perfil_processo(lider),
                "orgao_gestor_id": int(orgao_user),
                "orgao_gestor_nome": orgao_gestor_nome,
            },
        )

        criadas = self._perna_svc.adicionar_pernas(
            lider,
            pernas_novas,
            tramitacao=tram,
            orgao_lider_imediato_id=int(orgao_user),
        )

        if lider.fluxo_roteamento != FluxoRoteamento.FLUXO_TRANSVERSAL:
            lider.fluxo_roteamento = FluxoRoteamento.FLUXO_TRANSVERSAL
            lider.save(update_fields=["fluxo_roteamento"])

        return {
            "demanda": lider,
            "demanda_id": lider.pk,
            "pernas_novas": len(criadas),
            "pernas_criadas": [self._perna_svc.serializar_perna(p) for p in criadas],
            "total_pernas": len(self._perna_svc.listar_pernas(lider)),
        }

    @transaction.atomic
    def aplicar_inicio_execucao_automatico(
        self,
        lider: Demanda,
        usuario,
        *,
        perfil: str | None = None,
    ) -> None:
        """Alias legado — delega para entrada operacional scatter-gather."""
        self.aplicar_entrada_operacao(lider, usuario, perfil=perfil)

    def demanda_processo_lider(self, demanda: Demanda) -> Demanda:
        """Demanda principal do processo (líder em multi-destino ou Super OS)."""
        if self._usa_pernas(demanda):
            return demanda
        if not demanda.cluster_id:
            return demanda
        from core.services.cluster_service import ClusterService

        svc = ClusterService()
        total = Demanda.objects.filter(cluster_id=demanda.cluster_id).count()
        if not svc.cluster_e_multi_destino_orgaos(int(demanda.cluster_id)) and total < CLUSTER_MIN_DEMANDAS:
            return demanda
        lider_pk = svc.lider_cluster_pk(int(demanda.cluster_id))
        if lider_pk is not None and int(lider_pk) != int(demanda.pk):
            return Demanda.objects.get(pk=lider_pk)
        return demanda

    def participantes_fluxo_transversal(self, lider: Demanda) -> list[Demanda]:
        if lider.fluxo_roteamento != FluxoRoteamento.FLUXO_TRANSVERSAL:
            return [lider]
        if self._usa_pernas(lider):
            return [lider]
        if not lider.cluster_id:
            return [lider]
        return list(
            Demanda.objects.filter(cluster_id=lider.cluster_id).order_by("pk")
        )

    def orgao_lider_id(self, demanda: Demanda, *, secretaria_lider_id: int | None = None) -> int | None:
        if secretaria_lider_id:
            return int(secretaria_lider_id)
        orgao_carta = orgao_competente_servico(demanda)
        if orgao_carta:
            return orgao_carta
        return demanda.sinapse_orgao_id

    def _eh_fluxo_direto(self, demanda: Demanda) -> bool:
        return demanda.fluxo_roteamento in ("", FluxoRoteamento.FLUXO_DIRETO)

    def _eh_fluxo_transversal(self, demanda: Demanda) -> bool:
        return demanda.fluxo_roteamento == FluxoRoteamento.FLUXO_TRANSVERSAL

    def _exigir_perfil(self, condicao: bool, mensagem: str) -> None:
        if not condicao:
            raise OperacionalPermissaoError(mensagem)

    def _exigir_estado(self, condicao: bool, mensagem: str) -> None:
        if not condicao:
            raise OperacionalEstadoError(mensagem)

    def _parecer_valido(self, texto: str, *, minimo: int = 10) -> str:
        limpo = (texto or "").strip()
        if len(limpo) < minimo:
            raise OperacionalEstadoError(
                f"Informe a justificativa/parecer (mínimo {minimo} caracteres)."
            )
        return limpo

    # ----------------------------------------------------------- validadores RBAC
    def validar_entrada_vereador(self, demanda: Demanda, usuario) -> None:
        self._exigir_perfil(
            perm.usuario_pode_entrada_vereador(usuario, demanda),
            "Apenas o autor vereador pode enviar o ofício oficialmente.",
        )
        self._exigir_estado(
            demanda.status == "RASCUNHO",
            "Apenas rascunhos podem ser enviados.",
        )

    def validar_triagem_protocolo(
        self,
        demanda: Demanda,
        usuario,
        *,
        acao: str | None = None,
        total_destinos: int = 1,
    ) -> None:
        self._exigir_perfil(
            perm.usuario_pode_triagem_protocolo(usuario),
            "Apenas o Protocolo pode realizar a triagem e despacho inicial.",
        )
        self._exigir_estado(
            demanda.status == "AGUARDANDO_PROTOCOLO",
            "A demanda não está aguardando protocolo.",
        )
        if acao == AcaoTriagemProtocolo.VINCULAR_SERVICO:
            if not demanda_trilha_tendencia(demanda):
                raise OperacionalEstadoError(
                    "Vincular serviço só se aplica a demandas da trilha de tendência."
                )
        if acao == AcaoTriagemProtocolo.RECUSA_VEREADOR:
            if not demanda_trilha_tendencia(demanda):
                raise OperacionalEstadoError(
                    "Recusa ao vereador só se aplica a demandas da trilha de tendência."
                )

    def validar_recusa_protocolo(self, demanda: Demanda, usuario, *, parecer: str) -> str:
        self._exigir_perfil(
            perm.usuario_pode_recusa_protocolo(usuario),
            "Apenas o Protocolo pode recusar e devolver ao vereador.",
        )
        self._exigir_estado(
            demanda.status == "AGUARDANDO_PROTOCOLO",
            "Recusa só é permitida com demanda aguardando protocolo.",
        )
        if not demanda_trilha_tendencia(demanda):
            raise OperacionalEstadoError(
                "Recusa formal ao vereador aplica-se à trilha de tendência."
            )
        return self._parecer_valido(parecer)

    def validar_inicio_execucao(self, demanda: Demanda, usuario) -> None:
        self._exigir_perfil(
            perm.usuario_pode_iniciar_execucao(usuario, demanda),
            "Apenas a secretaria responsável pode iniciar a execução.",
        )
        self._exigir_estado(
            demanda.status == "PROTOCOLADO",
            "A demanda deve estar protocolada para iniciar execução.",
        )

    def validar_conclusao_tecnica(
        self, demanda: Demanda, usuario, *, parecer: str
    ) -> str:
        self._exigir_perfil(
            perm.usuario_pode_conclusao_tecnica(usuario, demanda),
            "Apenas a secretaria líder ou gestor setorial responsável pode emitir conclusão técnica no fluxo direto.",
        )
        self._exigir_estado(
            self._eh_fluxo_direto(demanda),
            "Conclusão técnica exclusiva do fluxo direto.",
        )
        self._exigir_estado(
            demanda.status == "EM_EXECUCAO",
            "Conclusão técnica exige demanda em execução.",
        )
        lider = self.demanda_processo_lider(demanda)
        self._exigir_estado(
            demanda.pk == lider.pk,
            "Conclusão técnica deve ser registrada na demanda líder do processo.",
        )
        return self._parecer_valido(parecer)

    def validar_conclusao_parcial(
        self, demanda: Demanda, usuario, *, parecer: str, perna_id: int | None = None
    ) -> str:
        lider = self.demanda_processo_lider(demanda)
        if self._usa_pernas(lider):
            orgao_user = perm.orgao_usuario(usuario)
            if orgao_user is None:
                raise OperacionalPermissaoError(
                    "Apenas secretarias do fluxo transversal podem emitir conclusão parcial."
                )
            perna = self._perna_svc.resolver_perna_para_conclusao(
                lider, orgao_user, perna_id=perna_id
            )
            if not perna:
                qtd = self._perna_svc.contar_pendentes_orgao(lider, orgao_user)
                if qtd > 1:
                    raise OperacionalEstadoError(
                        "Há várias pernas pendentes para sua secretaria — informe perna_id."
                    )
                raise OperacionalEstadoError(
                    "Nenhuma perna operacional pendente para sua secretaria."
                )
            self._exigir_perfil(
                perm.usuario_secretaria_do_orgao(usuario, perna.sinapse_orgao_id),
                "Apenas secretarias do fluxo transversal podem emitir conclusão parcial.",
            )
        else:
            self._exigir_perfil(
                perm.usuario_pode_conclusao_parcial(usuario, demanda),
                "Apenas secretarias do fluxo transversal podem emitir conclusão parcial.",
            )
        self._exigir_estado(
            self._eh_fluxo_transversal(lider),
            "Conclusão parcial exclusiva do fluxo transversal.",
        )
        self._exigir_estado(
            lider.status == "EM_EXECUCAO",
            "Conclusão parcial exige demanda em execução.",
        )
        if not self._usa_pernas(lider):
            orgao_check = perm.orgao_usuario(usuario) or demanda.sinapse_orgao_id
            if orgao_check and self._ja_tem_conclusao_parcial(demanda, int(orgao_check)):
                raise OperacionalEstadoError(
                    "Esta secretaria já registrou conclusão parcial neste processo."
                )
        return self._parecer_valido(parecer)

    def _resolver_lider_imediato_conclusao(self, lider: Demanda, orgao_id: int) -> int:
        """Líder imediato no modelo diretório — conclusão sobe para quem abriu a subpasta."""
        root = int(lider.sinapse_orgao_lider_id or lider.sinapse_orgao_id)
        if int(orgao_id) == root:
            return root
        if self._usa_pernas(lider):
            perna = self._perna_svc.resolver_perna_para_conclusao(lider, orgao_id)
            if perna:
                lid = self._perna_svc.orgao_lider_imediato_perna(perna)
                if lid:
                    return int(lid)
        return root

    def _reparar_status_se_pendentes(self, lider: Demanda) -> None:
        """Reverte avanço prematuro quando ainda há secretarias sem conclusão parcial."""
        if lider.nos_ativos == 0:
            from core.services.scatter_gather_service import NoOperacionalService

            if NoOperacionalService().processo_scatter_gather(lider):
                return
        if lider.status != ESTADO_AGUARDANDO_CONCLUSAO_FINAL:
            return
        if not self._eh_fluxo_transversal(lider):
            return
        if self.conclusoes_parciais_pendentes(lider):
            lider.status = "EM_EXECUCAO"
            lider.save(update_fields=["status"])
            logger.info(
                "Demanda pk=%s revertida para EM_EXECUCAO — conclusões parciais pendentes.",
                lider.pk,
            )

    def _montar_contexto_secretaria(self, demanda: Demanda, usuario) -> dict[str, Any]:
        orgao_user = perm.orgao_usuario(usuario)
        if orgao_user is None:
            return {}
        lider = self.demanda_processo_lider(demanda)
        lid_imediato = self._resolver_lider_imediato_conclusao(lider, orgao_user)
        filhos: list[dict[str, Any]] = []
        if self._usa_pernas(lider):
            filhos = [
                self._perna_svc.serializar_perna(p)
                for p in self._perna_svc.filhos_pernas_pendentes(lider, orgao_user)
            ]
        return {
            "orgao_sessao_id": orgao_user,
            "orgao_lider_imediato_id": lid_imediato,
            "orgao_lider_imediato_nome": sinapse_catalog.get_orgao_nome(lid_imediato),
            "filhos_pernas_pendentes": filhos,
            "pode_abrir_transversal": perm.usuario_pode_orquestrar_transversal(usuario, lider),
        }

    def validar_devolucao(self, demanda: Demanda, usuario, *, justificativa: str) -> str:
        self._exigir_perfil(
            perm.usuario_pode_devolucao_secretaria(usuario, demanda),
            "Apenas a secretaria responsável pode devolver ao Protocolo.",
        )
        self._exigir_estado(
            demanda.status == "PROTOCOLADO",
            "Devolução permitida apenas antes de iniciar a execução operacional.",
        )
        return self._parecer_valido(justificativa)

    def validar_conclusao_final(
        self, demanda: Demanda, usuario, *, parecer: str
    ) -> str:
        self._exigir_perfil(
            perm.usuario_pode_conclusao_final(usuario),
            "Apenas o Protocolo pode emitir a conclusão final.",
        )
        self._exigir_estado(
            demanda.status == ESTADO_AGUARDANDO_CONCLUSAO_FINAL,
            "Conclusão final exige processo com conclusão técnica pendente de despacho.",
        )
        lider = self.demanda_processo_lider(demanda)
        self._exigir_estado(
            demanda.pk == lider.pk,
            "Conclusão final deve ser registrada na demanda líder do processo.",
        )
        if not self._historico_tecnico_pronto(lider):
            raise OperacionalEstadoError(
                "Histórico técnico incompleto — aguarde todas as conclusões das secretarias."
            )
        return self._parecer_valido(parecer)

    # --------------------------------------------------------- estado derivado
    def _ja_tem_conclusao_parcial(self, demanda: Demanda, orgao_id: int | None = None) -> bool:
        if orgao_id is not None and self._usa_pernas(demanda):
            return self._perna_svc.orgao_tem_perna_concluida(demanda, int(orgao_id))
        if orgao_id is not None:
            return demanda.tramitacoes.filter(
                tipo=EventoOperacional.CONCLUSAO_PARCIAL,
                metadata__sinapse_orgao_id=int(orgao_id),
            ).exists()
        return demanda.tramitacoes.filter(tipo=EventoOperacional.CONCLUSAO_PARCIAL).exists()

    def _orgaos_obrigatorios_conclusao_transversal(self, lider: Demanda) -> set[int]:
        from core.services.demanda_despacho_destinos import orgaos_integrados_demanda

        orgaos: set[int] = set()
        lid = lider.sinapse_orgao_lider_id or lider.sinapse_orgao_id
        if lid:
            orgaos.add(int(lid))
        for item in orgaos_integrados_demanda(lider):
            oid = item.get("sinapse_orgao_id")
            if oid:
                orgaos.add(int(oid))
        if self._usa_pernas(lider):
            for p in self._perna_svc.listar_pernas(lider):
                orgaos.add(int(p.sinapse_orgao_id))
        for tram in lider.tramitacoes.filter(tipo=EventoOperacional.CONCLUSAO_PARCIAL):
            meta = tram.metadata if isinstance(tram.metadata, dict) else {}
            oid = meta.get("sinapse_orgao_id")
            if oid:
                orgaos.add(int(oid))
        for tram in lider.tramitacoes.filter(tipo="EXECUCAO"):
            meta = tram.metadata if isinstance(tram.metadata, dict) else {}
            if meta.get("acao") != "ABERTURA_PERNAS_TRANSVERSAL":
                continue
            for item in meta.get("pernas") or []:
                oid = item.get("secretaria_id")
                if oid:
                    orgaos.add(int(oid))
        return orgaos

    def conclusoes_parciais_pendentes(self, lider: Demanda) -> list[dict[str, Any]]:
        lider = self.demanda_processo_lider(lider)
        if self._usa_pernas(lider):
            return self._perna_svc.pendencias_conclusao(lider)
        if self._eh_fluxo_transversal(lider) and not lider.cluster_id:
            pendentes: list[dict[str, Any]] = []
            for orgao_id in sorted(self._orgaos_obrigatorios_conclusao_transversal(lider)):
                if not self._ja_tem_conclusao_parcial(lider, orgao_id):
                    pendentes.append(
                        {
                            "demanda_id": lider.pk,
                            "sinapse_orgao_id": orgao_id,
                            "orgao_nome": sinapse_catalog.get_orgao_nome(orgao_id),
                        }
                    )
            return pendentes
        participantes = self.participantes_fluxo_transversal(lider)
        pendentes = []
        for d in participantes:
            oid = d.sinapse_orgao_id
            if oid and not self._ja_tem_conclusao_parcial(d, oid):
                pendentes.append(
                    {
                        "demanda_id": d.pk,
                        "sinapse_orgao_id": oid,
                        "orgao_nome": sinapse_catalog.get_orgao_nome(oid),
                    }
                )
        return pendentes

    def _historico_tecnico_pronto(self, lider: Demanda) -> bool:
        lider = self.demanda_processo_lider(lider)
        from core.services.scatter_gather_service import NoOperacionalService

        sg = NoOperacionalService()
        if sg.processo_scatter_gather(lider) and lider.nos_ativos == 0:
            return True
        if lider.status == ESTADO_AGUARDANDO_CONCLUSAO_FINAL:
            return True
        if lider.tramitacoes.filter(metadata__consolidacao_nos=True).exists():
            return lider.nos_ativos == 0
        if self._eh_fluxo_direto(lider):
            return lider.tramitacoes.filter(
                tipo__in=(
                    EventoOperacional.CONCLUSAO_TECNICA,
                    EventoOperacional.SOLICITACAO_DEVOLUTIVA,
                )
            ).exists()
        return len(self.conclusoes_parciais_pendentes(lider)) == 0

    def _eventos_tecnicos_scatter_gather(self, lider: Demanda) -> list[dict[str, Any]]:
        """Encerramentos de todos os nós operacionais concluídos (por setor/secretaria)."""
        from core.models_no_operacional import NoOperacional, StatusNoOperacional

        eventos: list[dict[str, Any]] = []
        nos = (
            NoOperacional.objects.filter(
                demanda_id=lider.pk,
                status=StatusNoOperacional.CONCLUIDO,
                encerramento_tramitacao_id__isnull=False,
            )
            .select_related(
                "encerramento_tramitacao",
                "encerramento_tramitacao__responsavel",
                "unidade_administrativa",
            )
            .prefetch_related("encerramento_tramitacao__anexos")
            .order_by("concluido_em", "pk")
        )
        for no in nos:
            tram = no.encerramento_tramitacao
            if not tram:
                continue
            meta = tram.metadata if isinstance(tram.metadata, dict) else {}
            orgao_id = meta.get("orgao_id") or no.sinapse_orgao_id
            setor_nome = None
            if no.unidade_administrativa_id and no.unidade_administrativa:
                setor_nome = no.unidade_administrativa.sigla or no.unidade_administrativa.nome
            elif meta.get("setor_id") not in (None, ""):
                setor_nome = self._nome_setor_timeline(meta.get("setor_id"))
            ts = no.concluido_em or tram.timestamp
            eventos.append(
                {
                    "demanda_id": lider.pk,
                    "tramitacao_id": tram.pk,
                    "tipo": tram.tipo,
                    "parcial": True,
                    "orgao_id": orgao_id,
                    "orgao_nome": sinapse_catalog.get_orgao_nome(orgao_id),
                    "setor_nome": setor_nome,
                    "no_id": no.pk,
                    "parecer": meta.get("parecer") or tram.descricao or "",
                    "responsavel": (
                        tram.responsavel.get_full_name() or tram.responsavel.username
                        if tram.responsavel
                        else None
                    ),
                    "timestamp": ts.isoformat() if ts else None,
                    "anexos": self._payload_anexos_tramitacao(tram),
                }
            )
        return eventos

    def compilar_historico_tecnico(self, lider: Demanda) -> dict[str, Any]:
        """Payload para exibição no frontend (timeline / conclusão final)."""
        lider = self.demanda_processo_lider(lider)
        eventos: list[dict[str, Any]] = []

        from core.services.scatter_gather_service import NoOperacionalService

        if NoOperacionalService().processo_scatter_gather(lider):
            eventos = self._eventos_tecnicos_scatter_gather(lider)
        elif lider.fluxo_roteamento == FluxoRoteamento.FLUXO_TRANSVERSAL:
            if self._usa_pernas(lider):
                for perna in self._perna_svc.listar_pernas(lider):
                    if perna.status != "CONCLUIDA" or not perna.conclusao_tramitacao_id:
                        continue
                    tram = perna.conclusao_tramitacao
                    eventos.append(
                        self._serializar_evento_tecnico(lider, tram, parcial=True, perna=perna)
                    )
            else:
                for d in self.participantes_fluxo_transversal(lider):
                    tram = (
                        d.tramitacoes.filter(tipo=EventoOperacional.CONCLUSAO_PARCIAL)
                        .order_by("-timestamp")
                        .first()
                    )
                    if tram:
                        eventos.append(self._serializar_evento_tecnico(d, tram, parcial=True))
        else:
            tram = (
                lider.tramitacoes.filter(
                    tipo__in=(
                        EventoOperacional.CONCLUSAO_TECNICA,
                        EventoOperacional.SOLICITACAO_DEVOLUTIVA,
                    )
                )
                .order_by("-timestamp")
                .first()
            )
            if tram:
                eventos.append(self._serializar_evento_tecnico(lider, tram, parcial=False))

        return {
            "demanda_id": lider.pk,
            "fluxo_roteamento": lider.fluxo_roteamento,
            "tipo_entrada": self.classificar_entrada(lider),
            "orgao_lider_id": lider.sinapse_orgao_lider_id,
            "orgao_lider_nome": sinapse_catalog.get_orgao_nome(lider.sinapse_orgao_lider_id),
            "eventos_tecnicos": eventos,
            "pendencias_parciais": self.conclusoes_parciais_pendentes(lider),
            "pronto_conclusao_final": self._historico_tecnico_pronto(lider),
        }

    def _serializar_evento_tecnico(
        self, demanda: Demanda, tram: Tramitacao, *, parcial: bool, perna=None
    ) -> dict[str, Any]:
        meta = tram.metadata if isinstance(tram.metadata, dict) else {}
        orgao_id = meta.get("sinapse_orgao_id") or demanda.sinapse_orgao_id
        if perna is not None:
            orgao_id = perna.sinapse_orgao_id
        payload = {
            "demanda_id": demanda.pk,
            "tramitacao_id": tram.pk,
            "tipo": tram.tipo,
            "parcial": parcial,
            "orgao_id": orgao_id,
            "orgao_nome": sinapse_catalog.get_orgao_nome(orgao_id),
            "parecer": meta.get("parecer") or tram.descricao,
            "responsavel": (
                tram.responsavel.get_full_name() or tram.responsavel.username
                if tram.responsavel
                else None
            ),
            "timestamp": tram.timestamp.isoformat(),
            "anexos": self._payload_anexos_tramitacao(tram),
        }
        if perna is not None:
            payload["perna_id"] = perna.pk
            payload["setor_nome"] = (
                perna.unidade_administrativa.sigla or perna.unidade_administrativa.nome
                if perna.unidade_administrativa
                else None
            )
        return payload

    # ----------------------------------------------------------- mutações/eventos
    def registrar_evento(
        self,
        demanda: Demanda,
        *,
        tipo: str,
        usuario,
        descricao: str,
        metadata: dict[str, Any] | None = None,
        unidade_destino=None,
    ) -> Tramitacao:
        payload = dict(metadata or {})
        payload.setdefault("evento", tipo)
        payload.setdefault("fluxo_roteamento", demanda.fluxo_roteamento or None)
        payload.setdefault("registrado_em", timezone.now().isoformat())

        tram = Tramitacao.objects.create(
            demanda=demanda,
            responsavel=usuario,
            tipo=tipo,
            descricao=descricao,
            metadata=payload,
            unidade_destino=unidade_destino,
        )
        logger.info(
            "Evento operacional %s demanda=%s usuario=%s",
            tipo,
            demanda.pk,
            getattr(usuario, "pk", None),
        )
        return tram

    @transaction.atomic
    def aplicar_triagem_protocolo(
        self,
        demanda: Demanda,
        *,
        total_destinos: int,
        secretaria_lider_id: int,
        usuario,
        destinos_resumo: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Configura metadados do processo pós-despacho — sem tramitação automática."""
        self._exigir_perfil(
            perm.usuario_pode_triagem_protocolo(usuario),
            "Apenas o Protocolo pode realizar a triagem e despacho inicial.",
        )
        self._exigir_estado(
            demanda.status == "PROTOCOLADO",
            "A triagem operacional só se aplica após o despacho inicial.",
        )
        fluxo = self.resolver_fluxo_roteamento(
            total_destinos=total_destinos, demanda=demanda
        )
        orgao_competente = orgao_competente_servico(demanda)
        lider_id = self.orgao_lider_id(
            demanda, secretaria_lider_id=secretaria_lider_id
        )

        demanda.fluxo_roteamento = fluxo
        demanda.sinapse_orgao_lider_id = lider_id or orgao_competente
        demanda.save(update_fields=["fluxo_roteamento", "sinapse_orgao_lider_id"])

        tipo_entrada = self.classificar_entrada(demanda)
        modo_entrada = self.resolver_modo_entrada_processo(demanda)
        return {
            "acao": AcaoTriagemProtocolo.DESPACHO_MANUAL,
            "etapa": "DESPACHO_PROTOCOLO",
            "tipo_entrada": tipo_entrada,
            "modo_entrada_processo": modo_entrada,
            "fluxo_roteamento": fluxo,
            "total_destinos": total_destinos,
            "orgao_competente_id": orgao_competente,
            "secretaria_lider_id": lider_id,
            "destinos": destinos_resumo or [],
        }

    @transaction.atomic
    def aplicar_recusa_protocolo(
        self,
        demanda: Demanda,
        usuario,
        *,
        parecer: str,
    ) -> Demanda:
        texto = self.validar_recusa_protocolo(demanda, usuario, parecer=parecer)
        demanda.status = "DEVOLVIDO_VEREADOR"
        demanda.fluxo_roteamento = ""
        demanda.sinapse_orgao_lider_id = None
        demanda.modo_entrada_processo = ""
        demanda.orquestrador_conclusao = ""
        demanda.inicio_execucao_automatico = False
        demanda.save(
            update_fields=[
                "status",
                "fluxo_roteamento",
                "sinapse_orgao_lider_id",
                "modo_entrada_processo",
                "orquestrador_conclusao",
                "inicio_execucao_automatico",
            ]
        )

        self.registrar_evento(
            demanda,
            tipo=EventoOperacional.RECUSA_PROTOCOLO,
            usuario=usuario,
            descricao=f"Protocolo recusou a demanda e devolveu ao vereador.\nParecer:\n{texto}",
            metadata={
                "acao": AcaoTriagemProtocolo.RECUSA_VEREADOR,
                "parecer": texto,
                "tipo_entrada": TipoEntrada.TENDENCIA,
            },
        )
        return demanda

    @transaction.atomic
    def aplicar_conclusao_tecnica(
        self,
        demanda: Demanda,
        usuario,
        *,
        parecer: str,
    ) -> Demanda:
        texto = self.validar_conclusao_tecnica(demanda, usuario, parecer=parecer)
        demanda.status = ESTADO_AGUARDANDO_CONCLUSAO_FINAL
        demanda.save(update_fields=["status"])

        self.registrar_evento(
            demanda,
            tipo=EventoOperacional.CONCLUSAO_TECNICA,
            usuario=usuario,
            descricao=f"Conclusão técnica (fluxo direto).\nParecer:\n{texto}",
            metadata={"parecer": texto, "fluxo_roteamento": demanda.fluxo_roteamento},
        )
        return demanda

    @transaction.atomic
    def aplicar_conclusao_parcial(
        self,
        demanda: Demanda,
        usuario,
        *,
        parecer: str,
        perna_id: int | None = None,
        arquivos_anexos: list | None = None,
    ) -> dict[str, Any]:
        lider = self.demanda_processo_lider(demanda)
        if self._eh_fluxo_transversal(lider):
            self._perna_svc.sincronizar_pernas_transversal(lider)
            self._reparar_status_se_pendentes(lider)
            lider.refresh_from_db()
        texto = self.validar_conclusao_parcial(
            demanda, usuario, parecer=parecer, perna_id=perna_id
        )
        perna = None
        orgao_id = demanda.sinapse_orgao_id
        orgao_nome = sinapse_catalog.get_orgao_nome(orgao_id) or "Secretaria"
        if self._usa_pernas(lider):
            orgao_user = perm.orgao_usuario(usuario)
            perna = self._perna_svc.resolver_perna_para_conclusao(
                lider, orgao_user, perna_id=perna_id
            )
            orgao_id = perna.sinapse_orgao_id
            orgao_nome = sinapse_catalog.get_orgao_nome(orgao_id) or "Secretaria"
            if perna.unidade_administrativa:
                setor = perna.unidade_administrativa.sigla or perna.unidade_administrativa.nome
                orgao_nome = f"{orgao_nome} › {setor}"

        lid_destino = self._resolver_lider_imediato_conclusao(lider, orgao_id)

        tram = self.registrar_evento(
            lider,
            tipo=EventoOperacional.CONCLUSAO_PARCIAL,
            usuario=usuario,
            descricao=f"Conclusão parcial — {orgao_nome}.\nParecer:\n{texto}",
            metadata={
                "parecer": texto,
                "sinapse_orgao_id": orgao_id,
                "fluxo_roteamento": lider.fluxo_roteamento,
                "perna_id": perna.pk if perna else None,
                "orgao_lider_imediato_id": lid_destino,
                "orgao_lider_imediato_nome": sinapse_catalog.get_orgao_nome(lid_destino),
            },
        )
        if arquivos_anexos:
            from core.services.tramitacao_anexo_service import anexar_arquivos_tramitacao

            anexar_arquivos_tramitacao(tram, arquivos_anexos, copiar=True)
        if perna:
            self._perna_svc.marcar_concluida(perna, tram)

        pendentes = self.conclusoes_parciais_pendentes(lider)
        processo_avancou = False

        todas_concluidas = (
            self._perna_svc.todas_pernas_concluidas(lider)
            if self._usa_pernas(lider)
            else len(pendentes) == 0
        )

        if todas_concluidas and lider.status == "EM_EXECUCAO":
            lider.status = ESTADO_AGUARDANDO_CONCLUSAO_FINAL
            lider.save(update_fields=["status"])
            processo_avancou = True
            self.registrar_evento(
                lider,
                tipo=EventoOperacional.CONCLUSAO_TECNICA,
                usuario=usuario,
                descricao=(
                    "Todas as secretarias concluíram parcialmente — "
                    "processo aguardando conclusão final do Protocolo."
                ),
                metadata={
                    "consolidacao_transversal": True,
                    "fluxo_roteamento": lider.fluxo_roteamento,
                },
            )

        return {
            "demanda": lider,
            "lider": lider,
            "perna_id": perna.pk if perna else None,
            "pendencias_parciais": pendentes,
            "processo_avancou": processo_avancou,
            "ultima_conclusao_parcial": processo_avancou,
            "historico_tecnico": self.compilar_historico_tecnico(lider),
        }

    @transaction.atomic
    def aplicar_devolucao(
        self,
        demanda: Demanda,
        usuario,
        *,
        justificativa: str,
    ) -> Demanda:
        texto = self.validar_devolucao(demanda, usuario, justificativa=justificativa)
        orgao_nome = sinapse_catalog.get_orgao_nome(demanda.sinapse_orgao_id) or "Secretaria"
        status_anterior = demanda.status

        demanda.status = "AGUARDANDO_PROTOCOLO"
        demanda.fluxo_roteamento = ""
        demanda.sinapse_orgao_lider_id = None
        demanda.modo_entrada_processo = ""
        demanda.orquestrador_conclusao = ""
        demanda.inicio_execucao_automatico = False
        demanda.protocolo_executivo = None
        demanda.data_inicio_prazo = None
        demanda.unidade_administrativa = None
        demanda.prazo_efetivo_dias = None
        demanda.prazo_origem = ""
        demanda.save(
            update_fields=[
                "status",
                "fluxo_roteamento",
                "sinapse_orgao_lider_id",
                "modo_entrada_processo",
                "orquestrador_conclusao",
                "inicio_execucao_automatico",
                "protocolo_executivo",
                "data_inicio_prazo",
                "unidade_administrativa",
                "prazo_efetivo_dias",
                "prazo_origem",
            ]
        )

        from core.services.assinatura_eletronica_service import AssinaturaEletronicaService

        AssinaturaEletronicaService().liberar_assinaturas_despacho_inicial(demanda)

        self._perna_svc.cancelar_pernas(demanda, motivo="devolucao")

        self.registrar_evento(
            demanda,
            tipo=EventoOperacional.DEVOLUCAO,
            usuario=usuario,
            descricao=(
                f"{orgao_nome} devolveu o processo ao Protocolo para novo roteamento.\n"
                f"Status anterior: {status_anterior}.\n"
                f"Justificativa:\n{texto}"
            ),
            metadata={
                "justificativa": texto,
                "status_anterior": status_anterior,
                "sinapse_orgao_id": demanda.sinapse_orgao_id,
            },
        )
        return demanda

    @transaction.atomic
    def aplicar_conclusao_final(
        self,
        demanda: Demanda,
        usuario,
        *,
        parecer: str,
        historico_compilado: dict[str, Any] | None = None,
        tramitacao_existente: Tramitacao | None = None,
    ) -> Demanda:
        texto = self.validar_conclusao_final(demanda, usuario, parecer=parecer)
        historico = historico_compilado or self.compilar_historico_tecnico(demanda)
        descricao = f"Conclusão final do Protocolo.\nParecer:\n{texto}"
        metadata = {
            "parecer": texto,
            "historico_tecnico": historico,
        }

        if tramitacao_existente is not None:
            tram = tramitacao_existente
            meta = dict(tram.metadata if isinstance(tram.metadata, dict) else {})
            meta.update(metadata)
            meta.setdefault("evento", EventoOperacional.CONCLUSAO_FINAL)
            meta.setdefault("fluxo_roteamento", demanda.fluxo_roteamento or None)
            meta.pop("aguardando_validacao_gestor", None)
            tram.descricao = descricao
            tram.metadata = meta
            tram.save(update_fields=["descricao", "metadata"])
        else:
            self.registrar_evento(
                demanda,
                tipo=EventoOperacional.CONCLUSAO_FINAL,
                usuario=usuario,
                descricao=descricao,
                metadata=metadata,
            )

        from core.services.devolutiva_protocolo_service import DevolutivaProtocoloService

        DevolutivaProtocoloService().finalizar_apos_despacho_protocolo(demanda, usuario)
        return demanda

    def propagar_fluxo_para_cluster(
        self,
        lider: Demanda,
        *,
        fluxo: str,
        lider_orgao_id: int | None,
    ) -> None:
        """Sincroniza metadados de roteamento nos desdobramentos multi-secretaria."""
        if not lider.cluster_id:
            return
        Demanda.objects.filter(cluster_id=lider.cluster_id).exclude(pk=lider.pk).update(
            fluxo_roteamento=fluxo,
            sinapse_orgao_lider_id=lider_orgao_id,
            modo_entrada_processo=lider.modo_entrada_processo,
            orquestrador_conclusao=lider.orquestrador_conclusao,
            inicio_execucao_automatico=lider.inicio_execucao_automatico,
        )

    @transaction.atomic
    def aplicar_vincular_servico_tendencia(
        self,
        demanda: Demanda,
        usuario,
        *,
        sinapse_servico_id: int,
    ) -> Demanda:
        self.validar_triagem_protocolo(
            demanda,
            usuario,
            acao=AcaoTriagemProtocolo.VINCULAR_SERVICO,
        )
        sid = int(sinapse_servico_id)
        from core.services.carta_utilizacao_service import CartaUtilizacaoService

        CartaUtilizacaoService().validar_protocolo(sid, contexto="triagem_protocolo")
        orgao_id = sinapse_catalog.get_orgao_id_for_servico(sid)
        if not orgao_id:
            raise OperacionalEstadoError(
                "Serviço sem órgão responsável no catálogo Sinapse."
            )

        demanda.sinapse_servico_id = sid
        demanda.sinapse_orgao_id = int(orgao_id)
        demanda.origem_vinculo = Demanda.ORIGEM_VINCULO_CARTA
        demanda.save(
            update_fields=["sinapse_servico_id", "sinapse_orgao_id", "origem_vinculo"]
        )

        servico = sinapse_catalog.get_servico(sid)
        self.registrar_evento(
            demanda,
            tipo=EventoOperacional.TRIAGEM_PROTOCOLO,
            usuario=usuario,
            descricao=(
                f"Protocolo vinculou tendência ao serviço da carta: "
                f"{servico.titulo if servico else sid}."
            ),
            metadata={
                "acao": AcaoTriagemProtocolo.VINCULAR_SERVICO,
                "tipo_entrada": TipoEntrada.TENDENCIA,
                "sinapse_servico_id": sid,
                "sinapse_orgao_id": int(orgao_id),
            },
        )
        return demanda

    def _tipos_timeline_operacional(self) -> frozenset[str]:
        return frozenset(
            {
                EventoOperacional.ENTRADA_VEREADOR,
                EventoOperacional.TRIAGEM_PROTOCOLO,
                EventoOperacional.RECUSA_PROTOCOLO,
                EventoOperacional.DESPACHO,
                EventoOperacional.INICIO_EXECUCAO,
                EventoOperacional.CONCLUSAO_TECNICA,
                EventoOperacional.CONCLUSAO_PARCIAL,
                EventoOperacional.DEVOLUCAO,
                EventoOperacional.CONCLUSAO_FINAL,
                EventoOperacional.SOLICITACAO_DEVOLUTIVA,
                EventoOperacional.DEVOLUTIVA_PROTOCOLO,
                EventoOperacional.OPERACAO_NO,
                "ENCERRAMENTO_DEVOLUTIVA",
                "EXECUCAO",
                "ENCAMINHAMENTO_SETOR",
            }
        )

    def _nome_setor_timeline(self, uid: int | None) -> str | None:
        if uid in (None, ""):
            return None
        from core.models_unidade_administrativa import UnidadeAdministrativa

        ua = UnidadeAdministrativa.objects.filter(pk=int(uid)).first()
        if ua:
            return ua.sigla or ua.nome
        return None

    def _enriquecer_metadata_timeline(self, meta: dict[str, Any]) -> dict[str, Any]:
        from core.services.scatter_gather_service import _enriquecer_destinos_scatter

        destinos = meta.get("destinos")
        if isinstance(destinos, list) and destinos:
            meta["destinos"] = _enriquecer_destinos_scatter(destinos)

        pernas = meta.get("pernas")
        if not isinstance(pernas, list):
            return meta
        enriquecidas: list[dict[str, Any]] = []
        for p in pernas:
            if not isinstance(p, dict):
                continue
            item = dict(p)
            sid = item.get("secretaria_id")
            if sid and not item.get("orgao_nome"):
                item["orgao_nome"] = sinapse_catalog.get_orgao_nome(int(sid))
            uid = item.get("unidade_administrativa_id")
            if uid and not item.get("setor_nome"):
                item["setor_nome"] = self._nome_setor_timeline(uid)
            enriquecidas.append(item)
        meta["pernas"] = enriquecidas
        return meta

    @staticmethod
    def _dedupe_scatter_timeline(timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """H-JUL-12: evita cards scatter idênticos (ex.: encerramento em lote)."""
        from core.services.scatter_gather_visibilidade import ACOES_SCATTER_USUARIO

        vistos: set[tuple] = set()
        deduped: list[dict[str, Any]] = []
        for item in timeline:
            meta = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            acao = str(meta.get("acao_no") or item.get("tipo") or "").upper()
            if meta.get("scatter_gather") and acao in ACOES_SCATTER_USUARIO:
                chave = (
                    acao,
                    (item.get("descricao") or "").strip(),
                    item.get("responsavel"),
                    (item.get("timestamp") or "")[:16],
                )
                if chave in vistos:
                    continue
                vistos.add(chave)
            deduped.append(item)
        return deduped

    def _demanda_ids_timeline(self, demanda: Demanda) -> list[int]:
        """Demandas cujas tramitações compõem a timeline (inclui cluster Super OS)."""
        lider = self.demanda_processo_lider(demanda)
        ids: set[int] = {lider.pk}
        for d in self.participantes_fluxo_transversal(lider):
            ids.add(d.pk)
        cluster_id = demanda.cluster_id or lider.cluster_id
        if cluster_id:
            ids.update(
                Demanda.objects.filter(cluster_id=cluster_id).values_list("pk", flat=True)
            )
        return sorted(ids)

    def montar_timeline_operacional(
        self, demanda: Demanda, usuario=None
    ) -> list[dict[str, Any]]:
        lider = self.demanda_processo_lider(demanda)
        tipos = self._tipos_timeline_operacional()
        demanda_ids = self._demanda_ids_timeline(demanda)
        trams = (
            Tramitacao.objects.filter(demanda_id__in=demanda_ids, tipo__in=tipos)
            .select_related(
                "demanda",
                "responsavel",
                "unidade_destino",
                "unidade_origem",
            )
            .prefetch_related("anexos")
            .order_by("timestamp")
        )
        trams_list = list(trams)
        demandas_com_conclusao_final = {
            t.demanda_id
            for t in trams_list
            if t.tipo == EventoOperacional.CONCLUSAO_FINAL
        }
        timeline: list[dict[str, Any]] = []
        from core.services.scatter_gather_visibilidade import tramitacao_operacional_visivel
        from core.services.tramitacao_visibilidade_service import (
            perfil_usuario,
            rotulo_institucional_tramitacao,
        )

        eh_vereador = perfil_usuario(usuario) == "VEREADOR"
        conclusao_final_incluida = False
        from core.services.tramitacao_janela_edicao_service import TramitacaoJanelaEdicaoService

        for tram in trams_list:
            if (
                tram.tipo == "STATUS_UPDATE"
                and "Status sincronizado com o grupo Super OS" in (tram.descricao or "")
            ):
                continue
            if (
                tram.tipo == EventoOperacional.DEVOLUTIVA_PROTOCOLO
                and tram.demanda_id in demandas_com_conclusao_final
            ):
                continue
            if (
                tram.tipo == "ENCERRAMENTO_DEVOLUTIVA"
                and tram.demanda_id in demandas_com_conclusao_final
            ):
                continue
            if not tramitacao_operacional_visivel(tram):
                continue
            if usuario is not None and not eh_vereador:
                if not TramitacaoJanelaEdicaoService.usuario_pode_ver_tramitacao_timeline(
                    usuario, tram
                ):
                    continue
            meta = dict(tram.metadata if isinstance(tram.metadata, dict) else {})
            if meta.get("espelhada_do_lider"):
                continue
            meta = self._enriquecer_metadata_timeline(meta)
            tipo_exibicao = tram.tipo
            if meta.get("acao") == "ABERTURA_PERNAS_TRANSVERSAL":
                tipo_exibicao = "ABERTURA_PERNAS_TRANSVERSAL"
            elif meta.get("scatter_gather") and meta.get("acao_no"):
                tipo_exibicao = str(meta["acao_no"])
            if tipo_exibicao in ("ABERTURA_NO", "ENCAMINHAMENTO_NO"):
                continue
            if (
                tram.tipo == EventoOperacional.ENTRADA_VEREADOR
                and tram.demanda_id != demanda.pk
            ):
                continue
            if tram.tipo == EventoOperacional.DESPACHO and tram.demanda_id != lider.pk:
                continue
            if tram.tipo == EventoOperacional.CONCLUSAO_FINAL:
                if conclusao_final_incluida:
                    continue
                conclusao_final_incluida = True
            if eh_vereador:
                if tram.tipo == EventoOperacional.OPERACAO_NO:
                    continue
                if tipo_exibicao in (
                    "ENCERRAR",
                    "DESPACHAR",
                    "DESPACHAR_ENCERRAR",
                    "CONSOLIDAR",
                    "ABERTURA_PERNAS_TRANSVERSAL",
                ):
                    continue
            orgao_id = meta.get("orgao_id") or tram.demanda.sinapse_orgao_id
            orgao_nome = meta.get("orgao_nome") or sinapse_catalog.get_orgao_nome(orgao_id)
            uid = meta.get("unidade_administrativa_id")
            setor_nome = meta.get("setor_nome") or self._nome_setor_timeline(uid)
            if not setor_nome and tram.unidade_destino_id:
                setor_nome = self._nome_setor_timeline(tram.unidade_destino_id)
            tipo_rotulo = tipo_exibicao
            if tipo_exibicao in ("CONCLUSAO_PARCIAL", "CONCLUSAO_TECNICA"):
                tipo_rotulo = "CONCLUSAO"
            anexos_payload: list[dict[str, Any]] = []
            if eh_vereador:
                if tram.tipo in TIPOS_ANEXOS_TIMELINE_VEREADOR:
                    anexos_payload = self._payload_anexos_tramitacao(tram)
            else:
                anexos_payload = self._payload_anexos_tramitacao(tram)
            item_timeline = {
                "id": tram.pk,
                "demanda_id": tram.demanda_id,
                "tipo": tipo_exibicao,
                "descricao": tram.descricao,
                "metadata": meta,
                "fluxo_roteamento": meta.get("fluxo_roteamento")
                or tram.demanda.fluxo_roteamento
                or None,
                "orgao_id": orgao_id,
                "orgao_nome": orgao_nome,
                "setor_nome": setor_nome,
                "unidade_nome": setor_nome,
                "rotulo_institucional": rotulo_institucional_tramitacao(
                    tipo_rotulo,
                    demanda=tram.demanda,
                    tramitacao=tram,
                ),
                "anexos": anexos_payload,
                "no_id": meta.get("no_id"),
                "no_pai_id": meta.get("no_pai_id"),
                "no_filho_id": meta.get("no_filho_id"),
                "nos_ativos": meta.get("nos_ativos"),
                "responsavel": (
                    tram.responsavel.get_full_name() or tram.responsavel.username
                    if tram.responsavel
                    else None
                ),
                "timestamp": tram.timestamp.isoformat(),
                "ramificacao": (
                    "TRANSVERSAL"
                    if tram.demanda.fluxo_roteamento
                    == FluxoRoteamento.FLUXO_TRANSVERSAL
                    else "DIRETO"
                    if tram.demanda.fluxo_roteamento
                    == FluxoRoteamento.FLUXO_DIRETO
                    else None
                ),
            }
            if usuario is not None and not eh_vereador:
                item_timeline["pode_editar"] = TramitacaoJanelaEdicaoService.usuario_pode_corrigir(
                    usuario, tram
                )
                item_timeline["segundos_restantes_edicao"] = (
                    TramitacaoJanelaEdicaoService.segundos_restantes(tram)
                )
                item_timeline["aguardando_validacao_gestor"] = (
                    TramitacaoJanelaEdicaoService.tramitacao_aguardando_gestor(tram)
                )
                if tram.editavel_ate:
                    item_timeline["editavel_ate"] = tram.editavel_ate.isoformat()
            timeline.append(item_timeline)
        return self._dedupe_scatter_timeline(timeline)

    def acoes_disponiveis(self, demanda: Demanda, usuario) -> list[str]:
        acoes: list[str] = []
        lider = self.demanda_processo_lider(demanda)
        alvo = demanda

        if perm.usuario_pode_triagem_protocolo(usuario):
            if alvo.status == "AGUARDANDO_PROTOCOLO":
                acoes.append("triagem_despacho")
                if demanda_trilha_tendencia(alvo):
                    acoes.extend(["vincular_servico", "recusa_protocolo"])

        if alvo.status == "EM_EXECUCAO":
            from core.services.scatter_gather_service import NoOperacionalService

            sg = NoOperacionalService()
            if sg.nos_abertos_do_usuario(lider, usuario):
                acoes.extend(
                    [
                        "scatter_despachar",
                        "scatter_despachar_encerrar",
                        "scatter_encerrar",
                    ]
                )
                if sg.listar_grupos_nos_usuario(lider, usuario):
                    acoes.extend(
                        [
                            "scatter_consolidar",
                            "scatter_encerrar_lote",
                            "scatter_despachar_unificado",
                        ]
                    )

        if (
            perm.usuario_pode_conclusao_final(usuario)
            and lider.status == ESTADO_AGUARDANDO_CONCLUSAO_FINAL
            and alvo.pk == lider.pk
            and self._historico_tecnico_pronto(lider)
        ):
            acoes.append("conclusao_final")

        return acoes

    def _demanda_scatter_referencia(self, demanda: Demanda, usuario) -> int | None:
        """Demanda do cluster em que o operador tem nó scatter-gather aberto."""
        from core.services.scatter_gather_service import NoOperacionalService

        sg = NoOperacionalService()
        if sg.processo_scatter_gather(demanda) and sg.nos_abertos_do_usuario(demanda, usuario):
            return int(demanda.pk)
        if not demanda.cluster_id:
            return None
        orgao = perm.orgao_usuario(usuario)
        if orgao is None:
            return None
        candidatas = (
            Demanda.objects.filter(cluster_id=demanda.cluster_id, nos_ativos__gt=0)
            .exclude(pk=demanda.pk)
            .order_by("pk")
        )
        for cand in candidatas:
            if not sg.processo_scatter_gather(cand):
                continue
            if sg.nos_abertos_do_usuario(cand, usuario):
                return int(cand.pk)
        return None

    def montar_estado_operacional(self, demanda: Demanda, usuario) -> dict[str, Any]:
        from core.services.cluster_aderencia_service import (
            ClusterAderenciaService,
            demanda_integrada_ao_lider,
        )

        lider_ref = self.demanda_processo_lider(demanda)
        if lider_ref.cluster_id and (lider_ref.protocolo_executivo or "").strip():
            ClusterAderenciaService().integrar_seguidoras_sem_protocolo_ao_operacional(
                lider_ref, usuario=usuario
            )

        if demanda_integrada_ao_lider(demanda):
            ClusterAderenciaService().ressincronizar_com_lider(
                demanda, lider=lider_ref, usuario=usuario
            )
            demanda.refresh_from_db()

        lider = self.demanda_processo_lider(demanda)
        from core.services.scatter_gather_service import NoOperacionalService

        sg = NoOperacionalService()
        sg.reparar_gather_pendente(lider, usuario)
        sg.reparar_unidades_sem_setor(lider)
        lider.refresh_from_db()
        demanda.refresh_from_db()
        if self._eh_fluxo_transversal(lider):
            self._perna_svc.sincronizar_pernas_transversal(lider)
            self._reparar_status_se_pendentes(lider)
            lider.refresh_from_db()
        historico = self.compilar_historico_tecnico(lider)
        lider.refresh_from_db()
        processo_sg = sg.processo_scatter_gather(lider)
        return {
            "demanda_id": demanda.pk,
            "demanda_lider_id": lider.pk,
            "demanda_scatter_id": self._demanda_scatter_referencia(demanda, usuario),
            "processo_scatter_gather": processo_sg,
            "status": demanda.status,
            "status_display": demanda.get_status_display(),
            "estado_operacao": demanda.status,
            "nos_ativos": lider.nos_ativos,
            "arvore_nos": sg.montar_arvore_nos(lider),
            "nos_usuario": [
                sg.serializar_no_usuario(n) for n in sg.nos_abertos_do_usuario(lider, usuario)
            ],
            "destinos_nos_ativos": sg.listar_destinos_nos_ativos(lider),
            "grupos_nos_usuario": sg.listar_grupos_nos_usuario(lider, usuario),
            "grupos_nos_painel": sg.listar_grupos_painel_nos_usuario(lider, usuario),
            "tipo_entrada": self.classificar_entrada(lider),
            "modo_entrada_processo": lider.modo_entrada_processo or None,
            "fluxo_roteamento": lider.fluxo_roteamento or None,
            "orquestrador_conclusao": lider.orquestrador_conclusao or None,
            "perfil_processo": self.resolver_perfil_processo(lider),
            "inicio_execucao_automatico": lider.inicio_execucao_automatico,
            "sinapse_orgao_lider_id": lider.sinapse_orgao_lider_id,
            "orgao_lider_nome": sinapse_catalog.get_orgao_nome(lider.sinapse_orgao_lider_id),
            "historico_tecnico": historico,
            "pendencias_parciais": historico.get("pendencias_parciais") or [],
            "pronto_conclusao_final": historico.get("pronto_conclusao_final", False),
            "timeline": self.montar_timeline_operacional(lider, usuario=usuario),
            "acoes_disponiveis": self.acoes_disponiveis(demanda, usuario),
            "usa_pernas_operacionais": self._usa_pernas(lider),
            "pernas_operacionais": self._perna_svc.participantes_transversal(lider)
            if self._usa_pernas(lider)
            else [],
            "participantes_transversal": self._participantes_transversal_payload(lider),
            "contexto_secretaria": self._montar_contexto_secretaria(demanda, usuario),
        }

    def _participantes_transversal_payload(self, lider: Demanda) -> list[dict[str, Any]]:
        if self._usa_pernas(lider):
            return [
                {
                    "perna_id": p["perna_id"],
                    "demanda_id": lider.pk,
                    "sinapse_orgao_id": p["sinapse_orgao_id"],
                    "orgao_nome": p["orgao_nome"],
                    "setor_nome": p.get("setor_nome"),
                    "status": p["status"],
                    "conclusao_parcial": p["concluida"],
                    "orgao_lider_imediato_id": p.get("orgao_lider_imediato_id"),
                    "orgao_lider_imediato_nome": p.get("orgao_lider_imediato_nome"),
                }
                for p in self._perna_svc.participantes_transversal(lider)
            ]
        if lider.fluxo_roteamento != FluxoRoteamento.FLUXO_TRANSVERSAL:
            return []
        if not lider.cluster_id:
            return [
                {
                    "demanda_id": lider.pk,
                    "sinapse_orgao_id": orgao_id,
                    "orgao_nome": sinapse_catalog.get_orgao_nome(orgao_id),
                    "status": lider.status,
                    "conclusao_parcial": self._ja_tem_conclusao_parcial(lider, orgao_id),
                }
                for orgao_id in sorted(self._orgaos_obrigatorios_conclusao_transversal(lider))
            ]
        return [
            {
                "demanda_id": d.pk,
                "sinapse_orgao_id": d.sinapse_orgao_id,
                "orgao_nome": sinapse_catalog.get_orgao_nome(d.sinapse_orgao_id),
                "status": d.status,
                "conclusao_parcial": self._ja_tem_conclusao_parcial(
                    d, d.sinapse_orgao_id
                ),
            }
            for d in self.participantes_fluxo_transversal(lider)
        ]
