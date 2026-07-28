"""Subtipos de Gestor (U7): Geral vs Setorial — escopo de dados e admin."""

from __future__ import annotations

from core.models import Usuario
from core.models_unidade_administrativa import UnidadeAdministrativa
from core.services.tramitacao_setor_service import UnidadeAdministrativaService

TIPO_GERAL = "GERAL"
TIPO_SETORIAL = "SETORIAL"

# Demandas exclusivas do Protocolo / gestor central (não visíveis ao gestor setorial).
STATUS_FILA_PROTOCOLO_CENTRAL = frozenset(
    {
        "AGUARDANDO_PROTOCOLO",
        "AGUARDANDO_DEVOLUTIVA_PROTOCOLO",
        "DEVOLVIDO_VEREADOR",
    }
)

FILAS_APENAS_PROTOCOLO_CENTRAL = frozenset({"protocolados", "devolutivas"})

FILAS_GESTOR_SETORIAL = frozenset({"operacionais", "stand_by", "finalizados"})


def ids_unidades_ativas(usuario) -> list[int]:
    return UnidadeAdministrativaService().ids_unidades_do_usuario(usuario)


def tipo_gestor(usuario) -> str | None:
    """GESTOR sem vínculo org/setor = Geral; com vínculo = Setorial."""
    if getattr(usuario, "perfil", None) != "GESTOR":
        return None
    # Conta admin legada: superuser sem órgão explícito permanece Geral
    # (pode haver vínculos UA residuais de sincronizações antigas).
    if usuario.is_superuser and not usuario.sinapse_orgao_id:
        return TIPO_GERAL
    if usuario.sinapse_orgao_id or ids_unidades_ativas(usuario):
        return TIPO_SETORIAL
    return TIPO_GERAL


def gestor_operacional(user) -> bool:
    """Gestor (Geral ou Setorial) ou Protocolo — operação e leitura operacional."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    return getattr(user, "perfil", None) in ("GESTOR", "PROTOCOLO")


def pode_consultar_unidades(user) -> bool:
    """Lista setores/órgãos — formulários de tramitação e gestão operacional."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    perfil = getattr(user, "perfil", None)
    return perfil in ("GESTOR", "PROTOCOLO", "SECRETARIA")


def pode_gerir_unidades(user) -> bool:
    """CRUD de setores, import RM, responsáveis."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "perfil", None) == "PROTOCOLO":
        return True
    return gestor_pode_crud_admin(user)


def pode_consultar_depara_rm(user) -> bool:
    """Leitura do de-para RM ↔ Sinapse (catálogo operacional)."""
    return gestor_operacional(user)


def orgaos_escopo_gestor(usuario) -> list[int]:
    """Órgãos Sinapse visíveis para Gestor Setorial."""
    if tipo_gestor(usuario) != TIPO_SETORIAL:
        return []
    orgaos: set[int] = set()
    if usuario.sinapse_orgao_id:
        orgaos.add(int(usuario.sinapse_orgao_id))
    uids = ids_unidades_ativas(usuario)
    if uids:
        for oid in UnidadeAdministrativa.objects.filter(pk__in=uids).values_list(
            "sinapse_orgao_id", flat=True
        ):
            if oid is not None:
                orgaos.add(int(oid))
    return sorted(orgaos)


def usuario_pode_painel_protocolo_central(usuario) -> bool:
    """
    Filas e ações centralizadas do Protocolo (protocolados, devolutivas, finalizados).
    Protocolo, gestor SGAC ou gestor geral (sem vínculo setorial).
    """
    perfil = getattr(usuario, "perfil", None)
    if perfil == "PROTOCOLO":
        return True
    if perfil == "GESTOR":
        if gestor_protocolo_sgac(usuario):
            return True
        if tipo_gestor(usuario) == TIPO_GERAL:
            return True
    return False


def usuario_pode_acessar_fila_demanda(usuario, fila: str) -> bool:
    """RBAC por fila do painel de demandas."""
    chave = (fila or "").strip().lower()
    if not chave:
        return True
    if usuario_pode_painel_protocolo_central(usuario):
        return True
    perfil = getattr(usuario, "perfil", None)
    if perfil == "PROTOCOLO":
        return True
    if perfil == "GESTOR" and tipo_gestor(usuario) == TIPO_SETORIAL:
        return chave in FILAS_GESTOR_SETORIAL
    if perfil == "SECRETARIA":
        return chave == "operacionais"
    return False


def gestor_protocolo_sgac(usuario) -> bool:
    """Gestor setorial da UA SGAC (754) — visão operacional ampliada (protocolo)."""
    from core.models_unidade_administrativa import UnidadeAdministrativaResponsavel
    from core.services.usuario_vinculo_service import PROTOCOLO_UNIDADE_PK

    if getattr(usuario, "perfil", None) != "GESTOR":
        return False
    if gestor_admin_pleno(usuario):
        return False
    uids = ids_unidades_ativas(usuario)
    if PROTOCOLO_UNIDADE_PK in uids:
        return True
    return UnidadeAdministrativaResponsavel.objects.filter(
        unidade_id=PROTOCOLO_UNIDADE_PK,
        usuario=usuario,
        ativo=True,
    ).exists()


def gestor_admin_pleno(usuario) -> bool:
    return tipo_gestor(usuario) == TIPO_GERAL


def privilegios_django_gestor(usuario) -> dict[str, bool]:
    if tipo_gestor(usuario) == TIPO_SETORIAL:
        return {"is_staff": True, "is_superuser": False}
    return {"is_staff": True, "is_superuser": True}


def gestor_pode_crud_admin(user) -> bool:
    """CRUD administrativo (usuários, carta, FAQ, import, fluxo config…)."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "perfil", None) == "GESTOR":
        return gestor_admin_pleno(user) and bool(user.is_staff)
    return bool(user.is_staff)


def gestor_pode_gerir_unidade_no_escopo(user, unidade: UnidadeAdministrativa | None) -> bool:
    """Gestor Setorial pode operar setores dos órgãos do seu escopo."""
    if not user or unidade is None or getattr(user, "perfil", None) != "GESTOR":
        return False
    if gestor_admin_pleno(user) and user.is_staff:
        return True
    if tipo_gestor(user) != TIPO_SETORIAL:
        return False
    oid = unidade.sinapse_orgao_id
    if oid is None:
        return False
    return int(oid) in set(orgaos_escopo_gestor(user))


def pode_gerir_responsaveis_unidade(user, unidade: UnidadeAdministrativa | None) -> bool:
    """Vincular/desvincular responsáveis — Protocolo, Gestor Geral ou Setorial no escopo."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "perfil", None) == "PROTOCOLO":
        return True
    if gestor_pode_crud_admin(user):
        return True
    return gestor_pode_gerir_unidade_no_escopo(user, unidade)


def aplicar_filtro_orgaos_gestor(qs, user, *, campo: str = "sinapse_orgao_id"):
    """Restringe queryset ao escopo de órgãos do Gestor Setorial."""
    orgaos = orgaos_escopo_gestor(user)
    if not orgaos:
        return qs
    return qs.filter(**{f"{campo}__in": orgaos})
