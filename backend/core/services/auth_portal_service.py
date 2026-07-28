"""Regras de portal de login (vereador vs prefeitura)."""

from __future__ import annotations

from rest_framework.exceptions import AuthenticationFailed

PORTAL_VEREADOR = "vereador"
PORTAL_PREFEITURA = "prefeitura"

PORTAL_PERFIS: dict[str, frozenset[str]] = {
    PORTAL_VEREADOR: frozenset({"VEREADOR", "ASSESSOR"}),
    PORTAL_PREFEITURA: frozenset({"PROTOCOLO", "SECRETARIA", "GESTOR"}),
}

PORTAL_LABELS: dict[str, str] = {
    PORTAL_VEREADOR: "Portal do Vereador",
    PORTAL_PREFEITURA: "Portal Operacional",
}


def portal_para_perfil(perfil: str | None) -> str:
    if perfil in PORTAL_PERFIS[PORTAL_VEREADOR]:
        return PORTAL_VEREADOR
    return PORTAL_PREFEITURA


def perfil_permitido_no_portal(perfil: str | None, portal: str | None, *, is_staff: bool = False) -> bool:
    if not portal:
        return True
    permitidos = PORTAL_PERFIS.get(portal)
    if not permitidos:
        return True
    if perfil in permitidos:
        return True
    if is_staff and portal == PORTAL_PREFEITURA:
        return True
    return False


def assert_portal_permitido(portal: str | None, user) -> None:
    """Levanta ValidationError se o perfil não corresponde ao portal de login."""
    portal_norm = (portal or "").strip().lower()
    if not portal_norm or portal_norm not in PORTAL_PERFIS:
        return

    perfil = getattr(user, "perfil", None)
    if perfil_permitido_no_portal(perfil, portal_norm, is_staff=bool(getattr(user, "is_staff", False))):
        return

    destino = portal_para_perfil(perfil)
    raise AuthenticationFailed(
        {
            "detail": (
                f"Esta conta ({perfil or 'sem perfil'}) não pode entrar por "
                f"{PORTAL_LABELS.get(portal_norm, portal_norm)}. "
                f"Utilize {PORTAL_LABELS.get(destino, destino)}."
            ),
            "code": "wrong_portal",
            "portal_correto": destino,
            "portal_label": PORTAL_LABELS.get(destino, destino),
            "perfil": perfil,
        }
    )
