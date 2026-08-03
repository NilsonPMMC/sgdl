"""Janela temporal para correção de tramitações/despachos após registro."""

from __future__ import annotations

import logging

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from core.models import Tramitacao

logger = logging.getLogger(__name__)

# Tipos operacionais com texto livre — elegíveis à janela de correção.
_TIPOS_COM_JANELA = frozenset(
    {
        "DESPACHO",
        "TRIAGEM_PROTOCOLO",
        "COMENTARIO",
        "ANALISE_TECNICA",
        "EXECUCAO",
        "PROGRAMACAO",
        "CONCLUSAO",
        "TRANSFERENCIA",
        "ENCAMINHAMENTO_SETOR",
        "SOLICITACAO_DEVOLUTIVA",
        "DEVOLUTIVA_PROTOCOLO",
        "CONCLUSAO_TECNICA",
        "CONCLUSAO_PARCIAL",
        "DEVOLUCAO",
        "CONCLUSAO_FINAL",
        "OPERACAO_NO",
    }
)


def segundos_janela_edicao() -> int:
    try:
        valor = int(getattr(settings, "DESPACHO_JANELA_EDICAO_SEGUNDOS", 60))
    except (TypeError, ValueError):
        valor = 60
    return max(0, valor)


class TramitacaoJanelaEdicaoService:
    @staticmethod
    def tipo_elegivel(tipo: str | None) -> bool:
        return (tipo or "").strip().upper() in _TIPOS_COM_JANELA

    @staticmethod
    def _meta(tramitacao: Tramitacao) -> dict:
        raw = tramitacao.metadata
        return raw if isinstance(raw, dict) else {}

    @classmethod
    def tramitacao_aguardando_gestor(cls, tramitacao: Tramitacao) -> bool:
        return bool(cls._meta(tramitacao).get("aguardando_validacao_gestor"))

    @classmethod
    def deve_abrir_janela(cls, tramitacao: Tramitacao) -> bool:
        if segundos_janela_edicao() <= 0:
            return False
        meta = cls._meta(tramitacao)
        if meta.get("staging") or meta.get("propagacao_cluster"):
            return False
        return cls.tipo_elegivel(tramitacao.tipo)

    @classmethod
    def abrir_janela(cls, tramitacao: Tramitacao) -> None:
        if not cls.deve_abrir_janela(tramitacao):
            return
        agora = timezone.now()
        tramitacao.editavel_ate = agora + timezone.timedelta(seconds=segundos_janela_edicao())
        tramitacao.save(update_fields=["editavel_ate"])

    @staticmethod
    def tramitacao_editavel(tramitacao: Tramitacao) -> bool:
        limite = tramitacao.editavel_ate
        if limite is None:
            return False
        return timezone.now() <= limite

    @staticmethod
    def segundos_restantes(tramitacao: Tramitacao) -> int:
        limite = tramitacao.editavel_ate
        if limite is None:
            return 0
        delta = (limite - timezone.now()).total_seconds()
        return max(0, int(delta))

    @staticmethod
    def encerrar_janela(tramitacao: Tramitacao) -> None:
        if tramitacao.editavel_ate is None:
            return
        tramitacao.editavel_ate = None
        tramitacao.save(update_fields=["editavel_ate"])

    @classmethod
    def _usuario_e_autor(cls, usuario, tramitacao: Tramitacao) -> bool:
        uid = getattr(usuario, "id", None)
        if uid is None:
            return False
        return tramitacao.responsavel_id == uid

    @classmethod
    def _usuario_admin_suporte(cls, usuario) -> bool:
        return bool(getattr(usuario, "is_superuser", False)) or getattr(
            usuario, "perfil", None
        ) == "ADMIN"

    @classmethod
    def _usuario_pode_acessar_correcao(cls, usuario, tramitacao: Tramitacao) -> bool:
        from core.services.demanda_visibilidade import usuario_pode_acessar_demanda

        if not usuario_pode_acessar_demanda(usuario, tramitacao.demanda):
            return False
        if cls._usuario_e_autor(usuario, tramitacao):
            return True
        return cls._usuario_admin_suporte(usuario)

    @classmethod
    def usuario_pode_corrigir_pendente_gestor(cls, usuario, tramitacao: Tramitacao) -> bool:
        if not cls.tramitacao_aguardando_gestor(tramitacao):
            return False
        if cls._usuario_e_autor(usuario, tramitacao):
            return True

        from core.models_assinatura_eletronica import AssinaturaValidacaoGestor

        uid = getattr(usuario, "id", None)
        validacao = (
            AssinaturaValidacaoGestor.objects.filter(
                tramitacao=tramitacao,
                status=AssinaturaValidacaoGestor.STATUS_PENDENTE,
            )
            .order_by("-criado_em")
            .first()
        )
        if validacao is None:
            validacao = (
                AssinaturaValidacaoGestor.objects.filter(
                    demanda=tramitacao.demanda,
                    status=AssinaturaValidacaoGestor.STATUS_PENDENTE,
                )
                .order_by("-criado_em")
                .first()
            )
        if validacao is not None and validacao.operador_id == uid:
            return True
        return cls._usuario_admin_suporte(usuario)

    @classmethod
    def usuario_pode_corrigir(cls, usuario, tramitacao: Tramitacao) -> bool:
        if not cls.tramitacao_editavel(tramitacao):
            return False
        if cls.tramitacao_aguardando_gestor(tramitacao):
            return cls.usuario_pode_corrigir_pendente_gestor(usuario, tramitacao)
        return cls._usuario_pode_acessar_correcao(usuario, tramitacao)

    @classmethod
    def copias_cluster(cls, tramitacao: Tramitacao):
        return Tramitacao.objects.filter(
            metadata__propagacao_cluster=True,
            metadata__tramitacao_origem_id=tramitacao.pk,
        )

    @classmethod
    def sincronizar_descricao_cluster(cls, tramitacao: Tramitacao, descricao: str) -> None:
        prefixo = "[Super OS] "
        texto = (descricao or "").strip()
        if texto and not texto.startswith(prefixo):
            texto = f"{prefixo}{texto}"
        for copia in cls.copias_cluster(tramitacao):
            copia.descricao = texto
            copia.save(update_fields=["descricao"])

    @classmethod
    def remover_copias_cluster(cls, tramitacao: Tramitacao) -> None:
        cls.copias_cluster(tramitacao).delete()

    @classmethod
    def finalizar_apos_validacao_gestor(cls, tramitacao: Tramitacao) -> None:
        meta = dict(cls._meta(tramitacao))
        if meta.get("aguardando_validacao_gestor"):
            meta.pop("aguardando_validacao_gestor", None)
            tramitacao.metadata = meta
            tramitacao.save(update_fields=["metadata"])
        cls.abrir_janela(tramitacao)

    @classmethod
    def _sincronizar_payload_validacao_pendente(cls, tramitacao: Tramitacao, descricao: str) -> None:
        from core.models_assinatura_eletronica import (
            AssinaturaEletronica,
            AssinaturaValidacaoGestor,
        )
        from core.services.assinatura_eletronica_service import AssinaturaEletronicaService

        validacao = (
            AssinaturaValidacaoGestor.objects.filter(
                tramitacao=tramitacao,
                status=AssinaturaValidacaoGestor.STATUS_PENDENTE,
            )
            .order_by("-criado_em")
            .first()
        )
        if validacao is None:
            return
        payload = dict(validacao.payload if isinstance(validacao.payload, dict) else {})
        texto = (descricao or "").strip()
        etapa = validacao.etapa
        if etapa == AssinaturaEletronica.ETAPA_DESPACHO_INICIAL:
            payload["texto_despacho"] = texto
        elif etapa == AssinaturaEletronica.ETAPA_CONCLUSAO_FINAL:
            payload["parecer_resposta"] = texto
        else:
            payload["parecer_operacional"] = texto
        validacao.payload = payload
        validacao.hash_documento = AssinaturaEletronicaService().hash_canonical(payload)
        validacao.save(update_fields=["payload", "hash_documento"])

    @classmethod
    def _cancelar_pendente_gestor(cls, tramitacao: Tramitacao) -> None:
        from core.models_assinatura_eletronica import (
            AssinaturaEletronica,
            AssinaturaValidacaoGestor,
        )
        from core.services.assinatura_eletronica_service import AssinaturaEletronicaService

        validacao = (
            AssinaturaValidacaoGestor.objects.filter(
                tramitacao=tramitacao,
                status=AssinaturaValidacaoGestor.STATUS_PENDENTE,
            )
            .order_by("-criado_em")
            .first()
        )
        if validacao is None:
            return
        etapa = validacao.etapa
        if etapa == AssinaturaEletronica.ETAPA_DESPACHO_INICIAL:
            AssinaturaEletronicaService().liberar_assinaturas_despacho_inicial(tramitacao.demanda)
            return
        if etapa == AssinaturaEletronica.ETAPA_CONCLUSAO_FINAL:
            AssinaturaEletronicaService().liberar_assinaturas_conclusao_final(tramitacao.demanda)
            return
        validacao.status = AssinaturaValidacaoGestor.STATUS_CANCELADA
        validacao.save(update_fields=["status"])
        AssinaturaEletronica.objects.filter(
            demanda=tramitacao.demanda,
            etapa=etapa,
            tramitacao=tramitacao,
        ).delete()

    @classmethod
    def reabrir_janela(cls, tramitacao: Tramitacao) -> None:
        """Reinicia a contagem da janela de correção (ex.: após salvar edição)."""
        if segundos_janela_edicao() <= 0:
            return
        meta = cls._meta(tramitacao)
        if meta.get("staging") or meta.get("propagacao_cluster"):
            return
        if not cls.tipo_elegivel(tramitacao.tipo):
            return
        agora = timezone.now()
        tramitacao.editavel_ate = agora + timezone.timedelta(seconds=segundos_janela_edicao())
        tramitacao.save(update_fields=["editavel_ate"])

    @classmethod
    def _sincronizar_metadata_descricao(cls, tramitacao: Tramitacao) -> None:
        meta = dict(cls._meta(tramitacao))
        texto = (tramitacao.descricao or "").strip()
        tipo = (tramitacao.tipo or "").strip().upper()
        if tipo in ("CONCLUSAO_FINAL", "DEVOLUTIVA_PROTOCOLO"):
            if "Parecer:\n" in texto:
                meta["parecer"] = texto.split("Parecer:\n", 1)[-1].strip()
            else:
                meta["parecer"] = texto
        elif tipo == "OPERACAO_NO" and meta.get("scatter_gather"):
            meta["observacao_encerramento"] = texto
        meta_changed = meta != cls._meta(tramitacao)
        if meta_changed:
            tramitacao.metadata = meta
            tramitacao.save(update_fields=["metadata"])

    @classmethod
    def atualizar_descricao(cls, tramitacao: Tramitacao, descricao: str) -> Tramitacao:
        tramitacao.descricao = (descricao or "").strip()
        tramitacao.save(update_fields=["descricao"])
        cls._sincronizar_metadata_descricao(tramitacao)
        if cls.tramitacao_aguardando_gestor(tramitacao):
            cls._sincronizar_payload_validacao_pendente(tramitacao, tramitacao.descricao)
        cls.sincronizar_descricao_cluster(tramitacao, tramitacao.descricao)
        cls.reabrir_janela(tramitacao)
        return tramitacao

    @classmethod
    @transaction.atomic
    def excluir_tramitacao(cls, tramitacao: Tramitacao) -> None:
        demanda = tramitacao.demanda
        tipo = tramitacao.tipo
        meta = dict(tramitacao.metadata) if isinstance(tramitacao.metadata, dict) else {}
        tramitacao_id = tramitacao.pk
        aguardando_gestor = cls.tramitacao_aguardando_gestor(tramitacao)

        if aguardando_gestor:
            cls._cancelar_pendente_gestor(tramitacao)
            tramitacao.delete()
            logger.info(
                "Tramitação pendente de gestor removida demanda=%s tram=%s",
                demanda.pk,
                tramitacao_id,
            )
            return

        cls._limpar_assinaturas(tramitacao_id)
        cls._reverter_operacao_scatter(tramitacao)
        cls._reverter_efeitos_protocolo(tramitacao)
        cls.remover_copias_cluster(tramitacao)
        tramitacao.delete()
        cls._reverter_estado_demanda(demanda, tipo=tipo, meta=meta, tramitacao_id=tramitacao_id)

    @staticmethod
    def _limpar_assinaturas(tramitacao_id: int | None) -> None:
        if not tramitacao_id:
            return
        from core.models_assinatura_eletronica import (
            AssinaturaEletronica,
            AssinaturaValidacaoGestor,
        )

        AssinaturaValidacaoGestor.objects.filter(tramitacao_id=tramitacao_id).delete()
        AssinaturaEletronica.objects.filter(tramitacao_id=tramitacao_id).delete()

    @classmethod
    def _reverter_operacao_scatter(cls, tramitacao: Tramitacao) -> None:
        from core.models_no_operacional import (
            AcaoNoOperacional,
            NoOperacional,
            StatusNoOperacional,
        )
        from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional

        tramitacao_id = tramitacao.pk
        meta = tramitacao.metadata if isinstance(tramitacao.metadata, dict) else {}
        acao_no = (meta.get("acao_no") or "").strip().upper()
        no_id = meta.get("no_id")

        for no in NoOperacional.objects.filter(encerramento_tramitacao_id=tramitacao_id):
            cls._reverter_encerramento_no(no)

        if no_id not in (None, ""):
            no = NoOperacional.objects.filter(pk=int(no_id)).first()
            if no and no.encerramento_tramitacao_id == tramitacao_id:
                cls._reverter_encerramento_no(no)

        nos_removidos: set[int] = set()
        no_filhos_ids = meta.get("no_filhos_ids") or []
        if isinstance(no_filhos_ids, list):
            for nid in no_filhos_ids:
                try:
                    nid_int = int(nid)
                except (TypeError, ValueError):
                    continue
                filho = NoOperacional.objects.filter(pk=nid_int).first()
                if filho:
                    cls._excluir_subarvore_no(filho, tramitacao_id, nos_removidos)

        for no in NoOperacional.objects.filter(abertura_tramitacao_id=tramitacao_id):
            if no.pk not in nos_removidos:
                cls._excluir_subarvore_no(no, tramitacao_id, nos_removidos)

        for no in NoOperacional.objects.filter(metadata__tramitacao_despacho_id=tramitacao_id):
            if no.pk not in nos_removidos:
                cls._excluir_subarvore_no(no, tramitacao_id, nos_removidos)

        if no_id not in (None, "") and acao_no in {
            AcaoNoOperacional.DESPACHAR,
            AcaoNoOperacional.DESPACHAR_ENCERRAR,
        }:
            for filho in NoOperacional.objects.filter(
                parent_id=int(no_id),
                metadata__origem_acao=AcaoNoOperacional.DESPACHAR,
            ):
                if filho.pk not in nos_removidos:
                    cls._excluir_subarvore_no(filho, tramitacao_id, nos_removidos)

        PernaOperacional.objects.filter(conclusao_tramitacao_id=tramitacao_id).update(
            status=StatusPernaOperacional.EM_EXECUCAO,
            conclusao_tramitacao_id=None,
        )

        demanda = tramitacao.demanda
        from core.services.scatter_gather_service import NoOperacionalService

        NoOperacionalService().sincronizar_contador_nos(demanda)

    @classmethod
    def _excluir_subarvore_no(
        cls,
        no,
        tramitacao_origem_id: int,
        nos_removidos: set[int],
    ) -> None:
        from core.models_no_operacional import NoOperacional

        if no.pk in nos_removidos:
            return
        nos_removidos.add(no.pk)

        for filho in list(NoOperacional.objects.filter(parent_id=no.pk)):
            cls._excluir_subarvore_no(filho, tramitacao_origem_id, nos_removidos)

        abertura_id = no.abertura_tramitacao_id
        if abertura_id and abertura_id != tramitacao_origem_id:
            cls._excluir_tramitacao_derivada(abertura_id)

        encerramento_id = no.encerramento_tramitacao_id
        if encerramento_id and encerramento_id != tramitacao_origem_id:
            cls._excluir_tramitacao_derivada(encerramento_id)

        no.delete()

    @classmethod
    def _excluir_tramitacao_derivada(cls, tramitacao_id: int) -> None:
        tram = Tramitacao.objects.filter(pk=tramitacao_id).first()
        if not tram:
            return
        cls._limpar_assinaturas(tramitacao_id)
        cls.remover_copias_cluster(tram)
        tram.delete()

    @classmethod
    def _excluir_no_bootstrap(cls, no, tramitacao_origem_id: int) -> None:
        abertura_id = no.abertura_tramitacao_id
        if abertura_id and abertura_id != tramitacao_origem_id:
            cls._limpar_assinaturas(abertura_id)
            Tramitacao.objects.filter(pk=abertura_id).delete()
        no.delete()

    @classmethod
    def _reverter_despacho_inicial_protocolo(cls, tramitacao: Tramitacao) -> None:
        """Desfaz efeitos do despacho inicial: nós bootstrap, assinaturas e notificações."""
        from core.models_assinatura_eletronica import AssinaturaEletronica
        from core.models_no_operacional import NoOperacional
        from core.models_perna_operacional import PernaOperacional
        from core.services.notificacao_service import NotificacaoService
        from core.services.scatter_gather_service import NoOperacionalService

        demanda = tramitacao.demanda
        tramitacao_id = tramitacao.pk
        perna_ids = list(
            PernaOperacional.objects.filter(despacho_tramitacao_id=tramitacao_id).values_list(
                "pk", flat=True
            )
        )

        nos = NoOperacional.objects.filter(demanda_id=demanda.pk)
        if perna_ids:
            nos = nos.filter(
                models.Q(perna_operacional_id__in=perna_ids)
                | models.Q(metadata__origem__in=("bootstrap_perna", "bootstrap_sem_pernas"))
            )
        else:
            nos = nos.filter(
                metadata__origem__in=("bootstrap_perna", "bootstrap_sem_pernas")
            )

        for no in list(nos):
            cls._excluir_no_bootstrap(no, tramitacao_id)

        NoOperacionalService().sincronizar_contador_nos(demanda)

        AssinaturaEletronica.objects.filter(
            demanda=demanda,
            etapa=AssinaturaEletronica.ETAPA_DESPACHO_INICIAL,
        ).delete()

        NotificacaoService().cancelar_notificacoes_pos_despacho_inicial(
            demanda,
            referencia=tramitacao.timestamp,
        )

    @classmethod
    def _reverter_efeitos_protocolo(cls, tramitacao: Tramitacao) -> None:
        from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional

        tramitacao_id = tramitacao.pk
        meta = tramitacao.metadata if isinstance(tramitacao.metadata, dict) else {}

        if tramitacao.tipo == "DESPACHO" and meta.get("etapa") == "DESPACHO_PROTOCOLO":
            cls._reverter_despacho_inicial_protocolo(tramitacao)
            PernaOperacional.objects.filter(despacho_tramitacao_id=tramitacao_id).delete()

        if tramitacao.tipo == "CONCLUSAO_FINAL":
            from core.models_assinatura_eletronica import AssinaturaEletronica

            demanda = tramitacao.demanda
            PernaOperacional.objects.filter(conclusao_tramitacao_id=tramitacao_id).update(
                status=StatusPernaOperacional.EM_EXECUCAO,
                conclusao_tramitacao_id=None,
            )
            demanda.tramitacoes.filter(tipo="ENCERRAMENTO_DEVOLUTIVA").delete()
            AssinaturaEletronica.objects.filter(
                demanda=demanda,
                etapa=AssinaturaEletronica.ETAPA_CONCLUSAO_FINAL,
                tramitacao__isnull=True,
            ).delete()

    @staticmethod
    def _reverter_encerramento_no(no) -> None:
        from core.models_no_operacional import StatusNoOperacional

        meta = dict(no.metadata or {})
        meta.pop("acao_encerramento", None)
        meta.pop("observacao_encerramento", None)
        no.status = StatusNoOperacional.ABERTO
        no.concluido_em = None
        no.encerramento_tramitacao = None
        no.metadata = meta
        no.save(
            update_fields=[
                "status",
                "concluido_em",
                "encerramento_tramitacao",
                "metadata",
            ]
        )

    @staticmethod
    def _reverter_estado_demanda(
        demanda,
        *,
        tipo: str,
        meta: dict,
        tramitacao_id: int | None = None,
    ) -> None:
        del tramitacao_id
        update_fields: list[str] = []

        if tipo == "DESPACHO" and meta.get("etapa") == "DESPACHO_PROTOCOLO":
            if demanda.status in ("PROTOCOLADO", "EM_EXECUCAO", "EM_OPERACAO"):
                demanda.status = "AGUARDANDO_PROTOCOLO"
                update_fields.append("status")
            for campo, valor in (
                ("fluxo_roteamento", ""),
                ("sinapse_orgao_lider_id", None),
                ("modo_entrada_processo", ""),
                ("orquestrador_conclusao", ""),
                ("inicio_execucao_automatico", False),
                ("protocolo_executivo", None),
                ("data_inicio_prazo", None),
                ("prazo_efetivo_dias", None),
                ("prazo_origem", ""),
                ("sinapse_orgao_id", None),
                ("unidade_administrativa", None),
                ("nos_ativos", 0),
            ):
                if getattr(demanda, campo) != valor:
                    setattr(demanda, campo, valor)
                    update_fields.append(campo)

        if tipo == "CONCLUSAO_FINAL":
            if demanda.status == "FINALIZADO":
                from core.models_operacional import ESTADO_AGUARDANDO_CONCLUSAO_FINAL

                if demanda.fluxo_roteamento:
                    demanda.status = ESTADO_AGUARDANDO_CONCLUSAO_FINAL
                else:
                    demanda.status = "AGUARDANDO_DEVOLUTIVA_PROTOCOLO"
                demanda.data_finalizacao = None
                update_fields.extend(["status", "data_finalizacao"])

        if tipo == "DEVOLUTIVA_PROTOCOLO" and demanda.status == "FINALIZADO":
            demanda.status = "AGUARDANDO_DEVOLUTIVA_PROTOCOLO"
            demanda.data_finalizacao = None
            update_fields.extend(["status", "data_finalizacao"])
            demanda.tramitacoes.filter(tipo="ENCERRAMENTO_DEVOLUTIVA").delete()

        if update_fields:
            demanda.save(update_fields=update_fields)
            logger.info(
                "Estado da demanda %s revertido após desfazer tramitação tipo=%s",
                demanda.pk,
                tipo,
            )
