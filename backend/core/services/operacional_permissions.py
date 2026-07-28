"""RBAC rígido para transições da Gestão Operacional — Portal dos Vereadores."""

from __future__ import annotations

from core.models import Demanda
from core.models_operacional import FluxoRoteamento
from core.services.envio_oficial_service import demanda_trilha_tendencia


def perfil_usuario(usuario) -> str:
    return (getattr(usuario, "perfil", None) or "").upper()


def usuario_e_vereador(usuario) -> bool:
    return perfil_usuario(usuario) == "VEREADOR"


def usuario_e_protocolo(usuario) -> bool:
    return perfil_usuario(usuario) == "PROTOCOLO" or bool(getattr(usuario, "is_staff", False))


def usuario_e_secretaria(usuario) -> bool:
    return perfil_usuario(usuario) == "SECRETARIA"


def usuario_e_gestor(usuario) -> bool:
    return perfil_usuario(usuario) == "GESTOR"


def orgao_usuario(usuario) -> int | None:
    oid = getattr(usuario, "sinapse_orgao_id", None)
    return int(oid) if oid else None


def usuario_secretaria_do_orgao(usuario, orgao_id: int | None) -> bool:
    if not usuario_e_secretaria(usuario) or orgao_id is None:
        return False
    return orgao_usuario(usuario) == int(orgao_id)


def usuario_pode_entrada_vereador(usuario, demanda: Demanda) -> bool:
    if not usuario_e_vereador(usuario) and not usuario_e_gestor(usuario):
        return False
    if usuario_e_vereador(usuario) and demanda.autor_id != usuario.pk:
        return False
    return demanda.status == "RASCUNHO"


def usuario_pode_triagem_protocolo(usuario) -> bool:
    return usuario_e_protocolo(usuario)


def usuario_pode_recusa_protocolo(usuario) -> bool:
    return usuario_e_protocolo(usuario)


def usuario_pode_iniciar_execucao(usuario, demanda: Demanda) -> bool:
    if not usuario_e_secretaria(usuario):
        return False
    return usuario_secretaria_do_orgao(usuario, demanda.sinapse_orgao_id)


def usuario_e_secretaria_lider(usuario, demanda: Demanda) -> bool:
    lider = demanda.sinapse_orgao_lider_id or demanda.sinapse_orgao_id
    return usuario_secretaria_do_orgao(usuario, lider)


def usuario_pode_conclusao_tecnica(usuario, demanda: Demanda) -> bool:
    if usuario_e_secretaria(usuario):
        if demanda.fluxo_roteamento == FluxoRoteamento.FLUXO_TRANSVERSAL:
            return False
        if not demanda.fluxo_roteamento:
            return usuario_secretaria_do_orgao(usuario, demanda.sinapse_orgao_id)
        return usuario_e_secretaria_lider(usuario, demanda)
    if usuario_e_gestor(usuario):
        from core.services.assinatura_eletronica_service import AssinaturaEletronicaService

        return AssinaturaEletronicaService().usuario_pode_assinar_conclusao(usuario, demanda)
    return False


def usuario_pode_conclusao_parcial(usuario, demanda: Demanda) -> bool:
    if not usuario_e_secretaria(usuario):
        return False
    if demanda.fluxo_roteamento != FluxoRoteamento.FLUXO_TRANSVERSAL:
        return False
    orgao = orgao_usuario(usuario)
    if not orgao:
        return False
    from core.services.perna_operacional_service import PernaOperacionalService

    if PernaOperacionalService().demanda_usa_pernas(demanda):
        return PernaOperacionalService().contar_pendentes_orgao(demanda, orgao) > 0
    return usuario_secretaria_do_orgao(usuario, demanda.sinapse_orgao_id)


def usuario_pode_orquestrar_transversal(usuario, demanda: Demanda) -> bool:
    """Legado — abertura transversal substituída por scatter-gather."""
    return False


def usuario_pode_operar_no_scatter(usuario, no) -> bool:
    """
    Secretaria ou Gestor (Setorial/Geral) pode operar nó scatter-gather
    no escopo do órgão/setor vinculado ao usuário.
    """
    from core.models_no_operacional import NoOperacional
    from core.services.tramitacao_setor_service import UnidadeAdministrativaService

    if not isinstance(no, NoOperacional):
        return False

    if usuario_e_secretaria(usuario):
        orgao_user = orgao_usuario(usuario)
        if orgao_user is None or int(orgao_user) != int(no.sinapse_orgao_id):
            return False
    elif usuario_e_gestor(usuario):
        from core.services.gestor_escopo import TIPO_GERAL, orgaos_escopo_gestor, tipo_gestor

        if tipo_gestor(usuario) != TIPO_GERAL:
            orgaos = orgaos_escopo_gestor(usuario)
            if int(no.sinapse_orgao_id) not in orgaos:
                return False
    else:
        return False

    ids_ua = UnidadeAdministrativaService().ids_unidades_do_usuario(usuario)
    if not ids_ua:
        return True
    if no.unidade_administrativa_id is None:
        return False
    return int(no.unidade_administrativa_id) in ids_ua


def usuario_pode_devolucao_secretaria(usuario, demanda: Demanda) -> bool:
    if not usuario_e_secretaria(usuario):
        return False
    if demanda.status != "PROTOCOLADO":
        return False
    return usuario_secretaria_do_orgao(usuario, demanda.sinapse_orgao_id)


def usuario_pode_conclusao_final(usuario) -> bool:
    return usuario_e_protocolo(usuario)


def classificar_entrada(demanda: Demanda) -> str:
    from core.models_operacional import TipoEntrada

    if demanda_trilha_tendencia(demanda):
        return TipoEntrada.TENDENCIA
    return TipoEntrada.CARTA_SERVICO
