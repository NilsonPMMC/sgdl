"""Centralização de notificações operacionais por perfil (matriz homologação)."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Iterable

from django.utils import timezone

from core.models import Demanda, Notificacao, Tramitacao, Usuario
from core.models_no_operacional import NoOperacional
from core.services.gestor_escopo import (
    TIPO_GERAL,
    TIPO_SETORIAL,
    orgaos_escopo_gestor,
    tipo_gestor,
)
from core.services.tramitacao_setor_service import UnidadeAdministrativaService
from integrations import sinapse_catalog

logger = logging.getLogger(__name__)

DEDUPE_JANELA = timedelta(minutes=3)


class NotificacaoService:
    # ------------------------------------------------------------------ util

    def link_demanda(self, demanda_id: int) -> str:
        return f"/demandas/detalhes/{demanda_id}"

    def protocolo_rotulo(self, demanda: Demanda) -> str:
        from core.services.cluster_aderencia_service import protocolo_executivo_efetivo

        return (
            protocolo_executivo_efetivo(demanda)
            or demanda.protocolo_executivo
            or demanda.protocolo_legislativo
            or str(demanda.pk)
        )

    def criar(
        self,
        destinatario: Usuario,
        *,
        tipo: str,
        mensagem: str,
        link: str,
        dedupe: bool = True,
    ) -> Notificacao | None:
        if dedupe:
            existe = Notificacao.objects.filter(
                destinatario=destinatario,
                tipo=tipo,
                mensagem=mensagem,
                link=link,
                data_criacao__gte=timezone.now() - DEDUPE_JANELA,
            ).exists()
            if existe:
                return None
        return Notificacao.objects.create(
            destinatario=destinatario,
            tipo=tipo,
            mensagem=mensagem,
            link=link,
        )

    def criar_em_lote(
        self,
        destinatarios: Iterable[Usuario],
        *,
        tipo: str,
        mensagem: str,
        link: str,
        dedupe: bool = True,
    ) -> int:
        criadas = 0
        vistos: set[int] = set()
        for usuario in destinatarios:
            if not usuario or not usuario.is_active or usuario.pk in vistos:
                continue
            vistos.add(int(usuario.pk))
            if self.criar(
                usuario, tipo=tipo, mensagem=mensagem, link=link, dedupe=dedupe
            ):
                criadas += 1
        return criadas

    def _destinatarios_acompanhamento(self, demanda: Demanda) -> list[Usuario]:
        from core.services.acompanhamento_demanda_service import AcompanhamentoDemandaService

        return AcompanhamentoDemandaService().usuarios_acompanhando(demanda)

    def _notificar_acompanhantes(
        self,
        demanda: Demanda,
        tipo: str,
        mensagem: str,
        *,
        excluir: set[int] | None = None,
    ) -> int:
        destinatarios = self._destinatarios_acompanhamento(demanda)
        if excluir:
            destinatarios = [u for u in destinatarios if u.pk not in excluir]
        if not destinatarios:
            return 0
        prefixo = "[Acompanhamento] "
        return self.criar_em_lote(
            destinatarios,
            tipo=tipo,
            mensagem=f"{prefixo}{mensagem}",
            link=self.link_demanda(demanda.pk),
        )

    # ------------------------------------------------------------------ audiências

    def vereadores_interessados(self, demanda: Demanda) -> list[Usuario]:
        """Autor vereador e coautores do cluster/Super OS (ofícios)."""
        from core.services.cluster_service import CLUSTER_MIN_DEMANDAS, ClusterService

        autor_ids: set[int] = set()
        if demanda.autor_id and getattr(demanda.autor, "perfil", None) == "VEREADOR":
            autor_ids.add(int(demanda.autor_id))

        if demanda.cluster_id:
            svc = ClusterService()
            total = Demanda.objects.filter(cluster_id=demanda.cluster_id).count()
            super_os = svc.grupo_super_os_ativo(demanda) or total >= CLUSTER_MIN_DEMANDAS
            if super_os:
                for aid in Demanda.objects.filter(cluster_id=demanda.cluster_id).values_list(
                    "autor_id", flat=True
                ):
                    if aid:
                        autor_ids.add(int(aid))

        if not autor_ids:
            return []
        return list(
            Usuario.objects.filter(
                pk__in=autor_ids, perfil="VEREADOR", is_active=True
            ).order_by("pk")
        )

    def interessados_legislativos(self, demanda: Demanda) -> list[Usuario]:
        """Câmara (autor da indicação), vereadores vinculados ou autor do ofício."""
        from core.services.indicacao_service import demanda_eh_indicacao

        if not demanda_eh_indicacao(demanda):
            return self.vereadores_interessados(demanda)

        destinatarios: list[Usuario] = []
        vistos: set[int] = set()
        if demanda.autor_id:
            autor = demanda.autor
            if getattr(autor, "is_active", True) and autor.pk not in vistos:
                vistos.add(int(autor.pk))
                destinatarios.append(autor)
        for vereador in Usuario.objects.filter(
            pk__in=demanda.vinculos_vereador.values_list("vereador_id", flat=True),
            perfil="VEREADOR",
            is_active=True,
        ).order_by("pk"):
            if vereador.pk not in vistos:
                vistos.add(int(vereador.pk))
                destinatarios.append(vereador)
        return destinatarios

    def usuarios_protocolo(self) -> list[Usuario]:
        return list(Usuario.objects.filter(perfil="PROTOCOLO", is_active=True))

    def gestores_gerais(self) -> list[Usuario]:
        return [
            u
            for u in Usuario.objects.filter(perfil="GESTOR", is_active=True)
            if tipo_gestor(u) == TIPO_GERAL
        ]

    def setores_envolvidos_demanda(
        self,
        demanda: Demanda,
        *,
        extras_unidades: Iterable[int] | None = None,
    ) -> tuple[set[int], set[int]]:
        """Retorna (orgaos_sinapse, unidades_administrativas) envolvidos no processo."""
        from core.models_perna_operacional import PernaOperacional

        orgaos: set[int] = set()
        unidades: set[int] = set()

        if demanda.sinapse_orgao_id:
            orgaos.add(int(demanda.sinapse_orgao_id))
        if demanda.unidade_administrativa_id:
            unidades.add(int(demanda.unidade_administrativa_id))

        for oid, uid in NoOperacional.objects.filter(demanda_id=demanda.pk).values_list(
            "sinapse_orgao_id", "unidade_administrativa_id"
        ):
            if oid is not None:
                orgaos.add(int(oid))
            if uid is not None:
                unidades.add(int(uid))

        for oid, uid in PernaOperacional.objects.filter(demanda_id=demanda.pk).values_list(
            "sinapse_orgao_id", "unidade_administrativa_id"
        ):
            if oid is not None:
                orgaos.add(int(oid))
            if uid is not None:
                unidades.add(int(uid))

        for uid in extras_unidades or ():
            if uid not in (None, ""):
                unidades.add(int(uid))

        if unidades:
            from core.models_unidade_administrativa import UnidadeAdministrativa

            for oid in UnidadeAdministrativa.objects.filter(pk__in=unidades).values_list(
                "sinapse_orgao_id", flat=True
            ):
                if oid is not None:
                    orgaos.add(int(oid))

        return orgaos, unidades

    def _usuarios_secretaria_setores(
        self,
        orgaos: set[int],
        unidades: set[int],
        *,
        fallback_orgao_sem_setor: bool = True,
    ) -> list[Usuario]:
        """Secretarias vinculadas aos setores; fallback por órgão quando não há setor."""
        from core.models_unidade_administrativa import (
            UnidadeAdministrativa,
            UnidadeAdministrativaResponsavel,
        )

        usuarios: list[Usuario] = []
        vistos: set[int] = set()

        unidades_por_orgao: dict[int, set[int]] = {}
        if unidades:
            for uid, oid in UnidadeAdministrativa.objects.filter(pk__in=unidades).values_list(
                "pk", "sinapse_orgao_id"
            ):
                if oid is not None:
                    unidades_por_orgao.setdefault(int(oid), set()).add(int(uid))

        orgaos_alvo = set(orgaos) | set(unidades_por_orgao.keys())

        for orgao_id in orgaos_alvo:
            setores_org = unidades_por_orgao.get(orgao_id, set())
            if setores_org:
                for resp in (
                    UnidadeAdministrativaResponsavel.objects.filter(
                        unidade_id__in=setores_org,
                        ativo=True,
                        usuario__perfil="SECRETARIA",
                        usuario__is_active=True,
                    ).select_related("usuario")
                ):
                    u = resp.usuario
                    if u.pk not in vistos:
                        vistos.add(int(u.pk))
                        usuarios.append(u)
            elif fallback_orgao_sem_setor:
                for u in Usuario.objects.filter(
                    perfil="SECRETARIA",
                    sinapse_orgao_id=int(orgao_id),
                    is_active=True,
                ):
                    if u.pk not in vistos:
                        vistos.add(int(u.pk))
                        usuarios.append(u)

        return usuarios

    def _gestores_setoriais_envolvidos(
        self,
        orgaos: set[int],
        unidades: set[int],
        *,
        unidades_destino: set[int] | None = None,
    ) -> list[Usuario]:
        """
        Gestor setorial:
        - unidades_destino informado → apenas setores de destino geridos;
        - caso contrário → setores envolvidos no processo (SLA / encerramento).
        """
        from core.models_unidade_administrativa import UnidadeAdministrativa

        alvo_unidades = set(unidades_destino) if unidades_destino is not None else set(unidades)
        gestores: list[Usuario] = []
        vistos: set[int] = set()

        qs = Usuario.objects.filter(perfil="GESTOR", is_active=True).prefetch_related(
            "unidades_responsaveis"
        )

        unidades_map: dict[int, UnidadeAdministrativa] = {}
        if alvo_unidades:
            unidades_map = {
                u.pk: u
                for u in UnidadeAdministrativa.objects.filter(pk__in=alvo_unidades)
            }

        for usuario in qs:
            if tipo_gestor(usuario) != TIPO_SETORIAL:
                continue
            escopo_orgaos = set(orgaos_escopo_gestor(usuario))
            if orgaos and not escopo_orgaos.intersection(orgaos):
                continue

            ids_geridos = set(UnidadeAdministrativaService().ids_unidades_do_usuario(usuario))

            if unidades_destino is not None:
                if not alvo_unidades:
                    if not usuario.sinapse_orgao_id or int(usuario.sinapse_orgao_id) not in orgaos:
                        continue
                elif not alvo_unidades.intersection(ids_geridos):
                    if not ids_geridos and usuario.sinapse_orgao_id:
                        oid = int(usuario.sinapse_orgao_id)
                        dest_orgaos = {
                            unidades_map[u].sinapse_orgao_id
                            for u in alvo_unidades
                            if u in unidades_map and unidades_map[u].sinapse_orgao_id
                        }
                        if oid not in dest_orgaos:
                            continue
                    else:
                        continue
            else:
                if alvo_unidades:
                    if not ids_geridos.intersection(alvo_unidades):
                        if usuario.sinapse_orgao_id:
                            oid = int(usuario.sinapse_orgao_id)
                            envolvidos_org = {
                                unidades_map[u].sinapse_orgao_id
                                for u in alvo_unidades
                                if u in unidades_map and unidades_map[u].sinapse_orgao_id
                            }
                            if oid not in envolvidos_org and oid not in orgaos:
                                continue
                        else:
                            continue
                elif orgaos and escopo_orgaos.isdisjoint(orgaos):
                    continue

            if usuario.pk not in vistos:
                vistos.add(int(usuario.pk))
                gestores.append(usuario)

        return gestores

    def destinatarios_sla(self, demanda: Demanda) -> list[Usuario]:
        """Protocolo, secretarias e gestores setoriais envolvidos + gestores gerais + acompanhantes."""
        orgaos, unidades = self.setores_envolvidos_demanda(demanda)
        destinatarios: list[Usuario] = []
        vistos: set[int] = set()

        for lista in (
            self.usuarios_protocolo(),
            self._usuarios_secretaria_setores(orgaos, unidades),
            self._gestores_setoriais_envolvidos(orgaos, unidades),
            self.gestores_gerais(),
            self._destinatarios_acompanhamento(demanda),
        ):
            for u in lista:
                if u.pk not in vistos:
                    vistos.add(int(u.pk))
                    destinatarios.append(u)
        return destinatarios

    # ------------------------------------------------------------------ eventos — vereador

    def _notificar_vereadores(
        self,
        demanda: Demanda,
        tipo: str,
        mensagem: str,
        *,
        link: str | None = None,
    ) -> int:
        return self.criar_em_lote(
            self.interessados_legislativos(demanda),
            tipo=tipo,
            mensagem=mensagem,
            link=link or self.link_demanda(demanda.pk),
        )

    def notificar_despacho_inicial(
        self,
        demanda: Demanda,
        *,
        orgao_nome: str = "",
        super_os: str | None = None,
    ) -> int:
        from core.services.indicacao_service import demanda_eh_indicacao

        protocolo_exec = self.protocolo_rotulo(demanda)
        link = self.link_demanda(demanda.pk)
        if demanda_eh_indicacao(demanda):
            mensagem = (
                f"Indicação nº {demanda.protocolo_legislativo} protocolada "
                f"(ref. {protocolo_exec}) e despachada."
            )
            if orgao_nome:
                mensagem += f" Destino: {orgao_nome}."
            return self._notificar_vereadores(demanda, "DESPACHO", mensagem, link=link)
        if super_os:
            orgao_txt = orgao_nome or "secretaria competente"
            mensagem = (
                f"Super OS {super_os}: seu ofício nº {demanda.protocolo_legislativo} "
                f"foi protocolado (ref. {protocolo_exec}) e despachado para {orgao_txt}."
            )
        else:
            mensagem = (
                f"Seu ofício nº {demanda.protocolo_legislativo} foi protocolado "
                f"(nº {protocolo_exec}) e despachado."
            )
            if orgao_nome:
                mensagem += f" Destino: {orgao_nome}."
        return self._notificar_vereadores(demanda, "DESPACHO", mensagem, link=link)

    def notificar_despacho_inicial_super_os(
        self,
        cluster,
        demandas: list[Demanda],
        *,
        orgao_nome: str,
    ) -> int:
        protocolo_super = cluster.protocolo_super_os or ""
        total = 0
        vistos: set[int] = set()
        for demanda in demandas:
            for vereador in self.vereadores_interessados(demanda):
                if vereador.pk in vistos:
                    continue
                vistos.add(int(vereador.pk))
                mensagem = (
                    f"Super OS {protocolo_super}: ofício(s) do grupo foram protocolados "
                    f"e despachados para {orgao_nome}."
                )
                if self.criar(
                    vereador,
                    tipo="DESPACHO",
                    mensagem=mensagem,
                    link=self.link_demanda(demanda.pk),
                ):
                    total += 1
        return total

    def notificar_conclusao_final(self, demanda: Demanda) -> int:
        from core.services.indicacao_service import demanda_eh_indicacao

        protocolo = self.protocolo_rotulo(demanda)
        if demanda_eh_indicacao(demanda):
            mensagem = (
                f"Conclusão final da indicação {demanda.protocolo_legislativo} "
                f"(processo {protocolo}). Revise o laudo digital na tela do processo."
            )
        else:
            mensagem = (
                f"Conclusão final do processo {protocolo}. "
                "Revise o laudo digital na tela do processo."
            )
        return self._notificar_vereadores(
            demanda, "CONCLUSAO", mensagem, link=self.link_demanda(demanda.pk)
        ) + self._notificar_acompanhantes(demanda, "CONCLUSAO", mensagem)

    # ------------------------------------------------------------------ eventos — protocolo

    def notificar_oficio_enviado(self, demanda: Demanda) -> int:
        from core.services.indicacao_service import demanda_eh_indicacao

        link = self.link_demanda(demanda.pk)
        if demanda_eh_indicacao(demanda):
            mensagem = (
                f"Nova indicação nº {demanda.protocolo_legislativo} aguardando protocolo."
            )
            tipo = "NOVA_INDICACAO"
        else:
            mensagem = (
                f"Novo ofício nº {demanda.protocolo_legislativo} aguardando protocolo."
            )
            tipo = "NOVO_OFICIO"
        return self.criar_em_lote(
            self.usuarios_protocolo(),
            tipo=tipo,
            mensagem=mensagem,
            link=link,
        )

    def notificar_cluster_detectado(self, cluster, demanda: Demanda) -> int:
        from core.models import Demanda as DemandaModel

        total = DemandaModel.objects.filter(cluster_id=cluster.pk).count()
        link = self.link_demanda(demanda.pk)
        ref = cluster.protocolo_super_os or f"cluster #{cluster.pk}"
        mensagem = (
            f"Cluster detectado ({ref}): {total} ofício(s) vinculados — "
            f"último: nº {demanda.protocolo_legislativo}."
        )
        return self.criar_em_lote(
            self.usuarios_protocolo(),
            tipo="CLUSTER",
            mensagem=mensagem,
            link=link,
        )

    def notificar_todos_nos_encerrados(self, demanda: Demanda) -> int:
        protocolo = self.protocolo_rotulo(demanda)
        link = self.link_demanda(demanda.pk)
        mensagem = (
            f"Todos os nós operacionais encerrados no processo {protocolo}. "
            "Aguardando conclusão final."
        )
        return self.criar_em_lote(
            self.usuarios_protocolo(),
            tipo="ATUALIZACAO",
            mensagem=mensagem,
            link=link,
        ) + self._notificar_acompanhantes(demanda, "ATUALIZACAO", mensagem)

    def notificar_sla_atraso(self, demanda: Demanda) -> int:
        protocolo = self.protocolo_rotulo(demanda)
        link = self.link_demanda(demanda.pk)
        mensagem = (
            f"Alerta SLA: processo {protocolo} ({demanda.titulo}) está atrasado."
        )
        return self.criar_em_lote(
            self.destinatarios_sla(demanda),
            tipo="ATRASO",
            mensagem=mensagem,
            link=link,
        )

    # ------------------------------------------------------------------ eventos — secretarias / gestores

    def notificar_despacho_inicial_setores(self, demanda: Demanda) -> int:
        orgaos, unidades = self.setores_envolvidos_demanda(demanda)
        protocolo = self.protocolo_rotulo(demanda)
        link = self.link_demanda(demanda.pk)
        mensagem = (
            f"Nova demanda (protocolo nº {protocolo}) despachada para sua secretaria."
        )
        return self.criar_em_lote(
            self._usuarios_secretaria_setores(orgaos, unidades),
            tipo="DESPACHO",
            mensagem=mensagem,
            link=link,
        )

    def notificar_despacho_operacional(
        self,
        demanda: Demanda,
        *,
        destinos: list[dict],
        origem_setor: str = "",
    ) -> int:
        unidades_dest: set[int] = set()
        orgaos_dest: set[int] = set()
        for dest in destinos or []:
            sid = dest.get("secretaria_id")
            uid = dest.get("unidade_administrativa_id")
            if sid not in (None, ""):
                orgaos_dest.add(int(sid))
            if uid not in (None, ""):
                unidades_dest.add(int(uid))

        protocolo = self.protocolo_rotulo(demanda)
        link = self.link_demanda(demanda.pk)
        dest_txt = self._rotulo_destinos(destinos)
        mensagem = (
            f"Despacho operacional no processo {protocolo}"
            f"{f' ({origem_setor})' if origem_setor else ''}"
            f"{f' → {dest_txt}' if dest_txt else '.'}"
        )

        total = self.criar_em_lote(
            self._usuarios_secretaria_setores(orgaos_dest, unidades_dest),
            tipo="DESPACHO",
            mensagem=mensagem,
            link=link,
        )
        total += self.criar_em_lote(
            self._gestores_setoriais_envolvidos(
                orgaos_dest, unidades_dest, unidades_destino=unidades_dest or None
            ),
            tipo="DESPACHO",
            mensagem=mensagem,
            link=link,
        )
        total += self._notificar_acompanhantes(demanda, "DESPACHO", mensagem)
        return total

    def notificar_encerramento_setor(
        self,
        demanda: Demanda,
        no: NoOperacional,
        *,
        observacao: str = "",
        tramitacao: Tramitacao | None = None,
    ) -> int:
        orgao_nome = sinapse_catalog.get_orgao_nome(int(no.sinapse_orgao_id)) or str(
            no.sinapse_orgao_id
        )
        setor_nome = ""
        if no.unidade_administrativa:
            setor_nome = no.unidade_administrativa.sigla or no.unidade_administrativa.nome
        local = f"{orgao_nome} — {setor_nome}" if setor_nome else orgao_nome
        protocolo = self.protocolo_rotulo(demanda)
        link = self.link_demanda(demanda.pk)

        msg = f"Setor {local} encerrou participação no processo {protocolo}."

        orgaos, unidades = self.setores_envolvidos_demanda(
            demanda,
            extras_unidades=[no.unidade_administrativa_id]
            if no.unidade_administrativa_id
            else None,
        )

        total = self.criar_em_lote(
            self._usuarios_secretaria_setores(orgaos, unidades),
            tipo="ATUALIZACAO",
            mensagem=msg,
            link=link,
        )
        total += self.criar_em_lote(
            self._gestores_setoriais_envolvidos(orgaos, unidades),
            tipo="ATUALIZACAO",
            mensagem=msg,
            link=link,
        )
        logger.info(
            "Notificações encerramento setor demanda=%s no=%s criadas=%s",
            demanda.pk,
            no.pk,
            total,
        )
        total += self._notificar_acompanhantes(demanda, "ATUALIZACAO", msg)
        return total

    def notificar_assinatura_pendente_gestor(self, validacao) -> int:
        from core.models_assinatura_eletronica import AssinaturaEletronica, AssinaturaValidacaoGestor
        from core.services.assinatura_eletronica_service import AssinaturaEletronicaService

        demanda = validacao.demanda
        protocolo = self.protocolo_rotulo(demanda)
        etapa_display = dict(AssinaturaEletronica.ETAPA_CHOICES).get(
            validacao.etapa, validacao.etapa
        )
        link = f"/assinaturas-pendentes?validacao_assinatura={validacao.pk}"
        operador = validacao.operador.get_full_name() or validacao.operador.username
        mensagem = (
            f"Assinatura pendente de validação ({etapa_display}) no processo {protocolo}. "
            f"Solicitada por {operador}."
        )

        svc = AssinaturaEletronicaService()
        if validacao.tipo_gestor == AssinaturaValidacaoGestor.TIPO_GESTOR_PROTOCOLO:
            destinatarios = [
                Usuario.objects.get(pk=int(g["id"]))
                for g in svc.listar_gestores_protocolo()
            ]
        else:
            destinatarios = [
                Usuario.objects.get(pk=int(g["id"]))
                for g in svc.listar_gestores_setor(
                    unidade_administrativa_id=validacao.unidade_administrativa_id,
                    sinapse_orgao_id=validacao.sinapse_orgao_id,
                )
            ]

        return self.criar_em_lote(
            destinatarios,
            tipo="ASSINATURA_PENDENTE",
            mensagem=mensagem,
            link=link,
        )

    def _rotulo_destinos(self, destinos: list[dict]) -> str:
        partes: list[str] = []
        for dest in destinos or []:
            oid = dest.get("secretaria_id")
            uid = dest.get("unidade_administrativa_id")
            orgao = sinapse_catalog.get_orgao_nome(int(oid)) if oid else ""
            setor = ""
            if uid:
                from core.models_unidade_administrativa import UnidadeAdministrativa

                ua = UnidadeAdministrativa.objects.filter(pk=int(uid)).first()
                if ua:
                    setor = ua.sigla or ua.nome
            if orgao and setor:
                partes.append(f"{orgao} › {setor}")
            elif orgao:
                partes.append(orgao)
        return "; ".join(partes)
