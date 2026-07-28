"""Acompanhamento gerencial de processos (fixar/desfixar) — Secretaria e Gestor."""

from __future__ import annotations

from django.db.models import QuerySet
from django.utils import timezone

from core.models import Demanda, Tramitacao, Usuario
from core.models_acompanhamento import DemandaAcompanhamento
from core.services.demanda_visibilidade import _ids_unidades_usuario
from core.services.gestor_escopo import TIPO_GERAL, TIPO_SETORIAL, orgaos_escopo_gestor, tipo_gestor

STATUS_TERMINAL = frozenset(
    {"FINALIZADO", "DEVOLVIDO_VEREADOR", "CANCELADO", "RASCUNHO", "AGUARDANDO_PROTOCOLO"}
)
STATUS_OPERACIONAL = frozenset(
    {
        "PROTOCOLADO",
        "EM_EXECUCAO",
        "AGUARDANDO_TRANSFERENCIA",
        "AGUARDANDO_DEVOLUTIVA_PROTOCOLO",
    }
)


class AcompanhamentoDemandaError(ValueError):
    pass


class AcompanhamentoDemandaService:
    PERFIS_ELEGIVEIS = frozenset({"SECRETARIA", "GESTOR"})

    def perfil_elegivel(self, user) -> bool:
        return getattr(user, "perfil", None) in self.PERFIS_ELEGIVEIS

    def demanda_em_operacao(self, demanda: Demanda) -> bool:
        return (demanda.status or "") in STATUS_OPERACIONAL

    def usuario_participou_demanda(self, user, demanda: Demanda) -> bool:
        """Processo já passou pelo setor/escopo do usuário."""
        if not self.perfil_elegivel(user):
            return False

        perfil = user.perfil
        if perfil == "GESTOR" and tipo_gestor(user) == TIPO_GERAL:
            return self.demanda_em_operacao(demanda)

        from core.models_no_operacional import NoOperacional
        from core.models_perna_operacional import PernaOperacional

        orgao_ids: list[int] = []
        uas: list[int] = []

        if perfil == "SECRETARIA":
            oid = getattr(user, "sinapse_orgao_id", None)
            if not oid:
                return False
            orgao_ids = [int(oid)]
            uas = [int(u) for u in _ids_unidades_usuario(user)]
        else:
            orgao_ids = orgaos_escopo_gestor(user)
            if not orgao_ids:
                return False
            uas = [int(u) for u in _ids_unidades_usuario(user)]

        did = int(demanda.pk)

        no_qs = NoOperacional.objects.filter(demanda_id=did, sinapse_orgao_id__in=orgao_ids)
        if uas:
            no_qs = no_qs.filter(unidade_administrativa_id__in=uas)
        if no_qs.exists():
            return True

        perna_qs = PernaOperacional.objects.filter(
            demanda_id=did, sinapse_orgao_id__in=orgao_ids
        )
        if uas:
            perna_qs = perna_qs.filter(unidade_administrativa_id__in=uas)
        if perna_qs.exists():
            return True

        if uas:
            if Tramitacao.objects.filter(demanda_id=did, unidade_destino_id__in=uas).exists():
                return True

        if perfil == "SECRETARIA" and demanda.sinapse_orgao_id in orgao_ids:
            if uas:
                if demanda.unidade_administrativa_id in uas:
                    return True
            else:
                return True

        return False

    def pode_acompanhar(self, user, demanda: Demanda) -> bool:
        if not self.perfil_elegivel(user):
            return False
        if (demanda.status or "") in STATUS_TERMINAL:
            return False
        if not self.demanda_em_operacao(demanda):
            return False
        if not self.usuario_participou_demanda(user, demanda):
            return False
        return True

    def usuario_acompanha_ativo(self, user, demanda_id: int) -> bool:
        if not user or not getattr(user, "is_authenticated", False):
            return False
        return DemandaAcompanhamento.objects.filter(
            usuario_id=user.pk,
            demanda_id=int(demanda_id),
            ativo=True,
        ).exists()

    def demanda_ids_acompanhando(self, user) -> list[int]:
        if not self.perfil_elegivel(user):
            return []
        return list(
            DemandaAcompanhamento.objects.filter(usuario=user, ativo=True).values_list(
                "demanda_id", flat=True
            )
        )

    def usuarios_acompanhando(self, demanda: Demanda) -> list[Usuario]:
        return list(
            Usuario.objects.filter(
                acompanhamentos_demanda__demanda=demanda,
                acompanhamentos_demanda__ativo=True,
                is_active=True,
            ).distinct()
        )

    def acompanhar(
        self,
        user,
        demanda: Demanda,
        *,
        origem: str = DemandaAcompanhamento.ORIGEM_MANUAL,
        no_operacional_id: int | None = None,
    ) -> DemandaAcompanhamento:
        if not self.pode_acompanhar(user, demanda):
            raise AcompanhamentoDemandaError(
                "Não é possível acompanhar este processo no momento."
            )

        registro, created = DemandaAcompanhamento.objects.get_or_create(
            usuario=user,
            demanda=demanda,
            defaults={
                "origem": origem,
                "no_operacional_id": no_operacional_id,
                "ativo": True,
                "encerrado_em": None,
            },
        )
        if not created:
            registro.ativo = True
            registro.encerrado_em = None
            if origem:
                registro.origem = origem
            if no_operacional_id:
                registro.no_operacional_id = no_operacional_id
            registro.save(
                update_fields=["ativo", "encerrado_em", "origem", "no_operacional_id"]
            )
        return registro

    def desacompanhar(self, user, demanda: Demanda) -> bool:
        updated = DemandaAcompanhamento.objects.filter(
            usuario=user,
            demanda=demanda,
            ativo=True,
        ).update(ativo=False, encerrado_em=timezone.now())
        return updated > 0

    def encerrar_acompanhamentos_demanda(self, demanda: Demanda) -> int:
        """Desativa todos os acompanhamentos quando o processo é finalizado."""
        return DemandaAcompanhamento.objects.filter(
            demanda=demanda,
            ativo=True,
        ).update(ativo=False, encerrado_em=timezone.now())

    def somente_acompanhamento(self, user, demanda: Demanda) -> bool:
        """Usuário só acompanha — sem pendência operacional no setor."""
        if not self.usuario_acompanha_ativo(user, demanda.pk):
            return False
        if not self.perfil_elegivel(user):
            return False

        from core.services.demanda_visibilidade import (
            demanda_ids_em_operacao_setor,
            demanda_ids_pendencia_setor,
        )

        did = int(demanda.pk)
        perfil = getattr(user, "perfil", None)

        if perfil == "SECRETARIA":
            return did not in set(demanda_ids_em_operacao_setor(user))

        if perfil == "GESTOR":
            if tipo_gestor(user) == TIPO_GERAL:
                return True
            em_op = set(demanda_ids_em_operacao_setor(user)) | set(
                demanda_ids_pendencia_setor(user)
            )
            return did not in em_op

        return False


def filtrar_demandas_acompanhando(qs: QuerySet[Demanda], user) -> QuerySet[Demanda]:
    ids = AcompanhamentoDemandaService().demanda_ids_acompanhando(user)
    if not ids:
        return qs.none()
    return qs.filter(pk__in=ids)
