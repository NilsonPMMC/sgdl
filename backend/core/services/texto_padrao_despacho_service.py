"""Escopo, visibilidade e placeholders de textos padrão de despacho."""

from __future__ import annotations

import re
from typing import Any

from django.db.models import Count, Q, QuerySet

from core.models import Usuario
from core.models_texto_padrao_despacho import (
    CategoriaTextoPadraoDespacho,
    EscopoTextoPadraoDespacho,
    TextoPadraoDespacho,
)
from core.models_unidade_administrativa import UnidadeAdministrativa
from core.services.gestor_escopo import (
    TIPO_GERAL,
    gestor_admin_pleno,
    ids_unidades_ativas,
    orgaos_escopo_gestor,
    tipo_gestor,
)
from core.services.usuario_vinculo_service import (
    PROTOCOLO_SINAPSE_ORGAO_ID,
    PROTOCOLO_UNIDADE_PK,
    UsuarioVinculoService,
)
from integrations import sinapse_catalog

PERFIS_TEXTO_PADRAO = frozenset({"PROTOCOLO", "SECRETARIA", "GESTOR"})

_PLACEHOLDER = re.compile(r"\{\{\s*([a-z0-9_]+)\s*\}\}", re.I)

_CATEGORIAS_LEGADAS_PROTOCOLO = frozenset(
    {"DESPACHO", "DEVOLUTIVA", "CONCLUSAO_FINAL", "RECUSA", "PROTOCOLO"}
)
_CATEGORIAS_LEGADAS_OPERACIONAL = frozenset({"ANDAMENTO", "CONCLUSAO", "OPERACIONAL"})


def usuario_pode_acessar_modulo(usuario) -> bool:
    return bool(
        usuario
        and getattr(usuario, "is_authenticated", False)
        and getattr(usuario, "perfil", None) in PERFIS_TEXTO_PADRAO
    )


def usuario_usa_categoria_protocolo(usuario: Usuario) -> bool:
    from core.services.gestor_escopo import gestor_protocolo_sgac

    perfil = getattr(usuario, "perfil", None)
    if perfil == "PROTOCOLO":
        return True
    if perfil == "GESTOR" and gestor_protocolo_sgac(usuario):
        return True
    return False


def categoria_padrao_criacao(usuario: Usuario) -> str:
    if usuario_usa_categoria_protocolo(usuario):
        return CategoriaTextoPadraoDespacho.PROTOCOLO
    return CategoriaTextoPadraoDespacho.OPERACIONAL


def categorias_visiveis_usuario(usuario: Usuario) -> list[str]:
    if gestor_admin_pleno(usuario) and usuario.is_staff:
        return [
            CategoriaTextoPadraoDespacho.PROTOCOLO,
            CategoriaTextoPadraoDespacho.OPERACIONAL,
        ]
    if usuario_usa_categoria_protocolo(usuario):
        return [CategoriaTextoPadraoDespacho.PROTOCOLO]
    return [CategoriaTextoPadraoDespacho.OPERACIONAL]


def normalizar_categoria_legada(valor: str | None) -> str:
    chave = (valor or "").strip().upper()
    if chave in _CATEGORIAS_LEGADAS_PROTOCOLO or chave == CategoriaTextoPadraoDespacho.PROTOCOLO:
        return CategoriaTextoPadraoDespacho.PROTOCOLO
    return CategoriaTextoPadraoDespacho.OPERACIONAL


def resolver_escopo_criacao(usuario: Usuario) -> dict[str, Any]:
    perfil = getattr(usuario, "perfil", None)
    if perfil == "PROTOCOLO":
        ua = UsuarioVinculoService().resolver_unidade_protocolo()
        return {
            "escopo_tipo": EscopoTextoPadraoDespacho.PROTOCOLO,
            "sinapse_orgao_id": PROTOCOLO_SINAPSE_ORGAO_ID,
            "unidade_padrao_id": ua.pk if ua else PROTOCOLO_UNIDADE_PK,
        }
    if perfil == "SECRETARIA":
        return {
            "escopo_tipo": EscopoTextoPadraoDespacho.SECRETARIA,
            "sinapse_orgao_id": usuario.sinapse_orgao_id,
            "unidade_padrao_id": None,
        }
    if perfil == "GESTOR":
        if tipo_gestor(usuario) == TIPO_GERAL:
            return {
                "escopo_tipo": EscopoTextoPadraoDespacho.GERAL,
                "sinapse_orgao_id": None,
                "unidade_padrao_id": None,
            }
        orgaos = orgaos_escopo_gestor(usuario)
        return {
            "escopo_tipo": EscopoTextoPadraoDespacho.SETORIAL,
            "sinapse_orgao_id": orgaos[0] if len(orgaos) == 1 else usuario.sinapse_orgao_id,
            "unidade_padrao_id": None,
        }
    raise PermissionError("Perfil sem permissão para criar textos padrão.")


def setores_disponiveis_usuario(usuario: Usuario) -> list[dict[str, Any]]:
    uids = ids_unidades_ativas(usuario)
    if not uids:
        escopo = resolver_escopo_criacao(usuario)
        padrao = escopo.get("unidade_padrao_id")
        if padrao:
            ua = UnidadeAdministrativa.objects.filter(pk=padrao).first()
            if ua:
                return [
                    {
                        "id": ua.pk,
                        "sigla": ua.sigla,
                        "nome": ua.nome,
                        "rotulo": ua.sigla or ua.nome,
                    }
                ]
        return []
    return [
        {
            "id": u.pk,
            "sigla": u.sigla,
            "nome": u.nome,
            "rotulo": u.sigla or u.nome,
        }
        for u in UnidadeAdministrativa.objects.filter(pk__in=uids).order_by("nome")
    ]


def exige_selecao_setores(usuario: Usuario, escopo: dict[str, Any]) -> bool:
    if escopo.get("escopo_tipo") in (
        EscopoTextoPadraoDespacho.GERAL,
        EscopoTextoPadraoDespacho.PROTOCOLO,
    ):
        return False
    return len(setores_disponiveis_usuario(usuario)) > 1


def resolver_unidades_criacao(
    usuario: Usuario,
    escopo: dict[str, Any],
    *,
    unidades_ids: list[int] | None = None,
) -> list[int]:
    """Valida e resolve IDs de UA vinculadas ao modelo."""
    permitidos = {s["id"] for s in setores_disponiveis_usuario(usuario)}
    tipo = escopo.get("escopo_tipo")

    if tipo == EscopoTextoPadraoDespacho.GERAL:
        return []

    if tipo == EscopoTextoPadraoDespacho.PROTOCOLO:
        padrao = escopo.get("unidade_padrao_id")
        if unidades_ids:
            selecionados = [int(x) for x in unidades_ids if x is not None]
            if padrao and padrao not in selecionados:
                selecionados = [int(padrao), *selecionados]
            return list(dict.fromkeys(selecionados))
        return [int(padrao)] if padrao else []

    if unidades_ids:
        selecionados = [int(x) for x in unidades_ids if x is not None]
        if permitidos:
            invalidos = set(selecionados) - permitidos
            if invalidos:
                raise ValueError("Setor(es) selecionado(s) não pertencem ao seu vínculo.")
        if not selecionados:
            raise ValueError("Selecione ao menos um setor.")
        return selecionados

    if len(permitidos) == 1:
        return [next(iter(permitidos))]

    if len(permitidos) > 1:
        raise ValueError("Selecione ao menos um setor para disponibilizar o modelo.")

    return []


def _q_visibilidade_usuario(usuario: Usuario) -> Q:
    q = Q(escopo_tipo=EscopoTextoPadraoDespacho.GERAL)
    perfil = getattr(usuario, "perfil", None)

    if perfil == "PROTOCOLO":
        q |= Q(
            escopo_tipo=EscopoTextoPadraoDespacho.PROTOCOLO,
            sinapse_orgao_id=PROTOCOLO_SINAPSE_ORGAO_ID,
        )
        return q

    uids = ids_unidades_ativas(usuario)

    if perfil == "SECRETARIA":
        oid = usuario.sinapse_orgao_id
        if oid:
            q |= Q(
                escopo_tipo=EscopoTextoPadraoDespacho.SECRETARIA,
                sinapse_orgao_id=int(oid),
                _n_unidades=0,
            )
        if uids:
            q |= Q(unidades__id__in=uids)
        return q

    if perfil == "GESTOR":
        if tipo_gestor(usuario) == TIPO_GERAL:
            return Q()
        orgaos = orgaos_escopo_gestor(usuario)
        if orgaos:
            q |= Q(
                escopo_tipo=EscopoTextoPadraoDespacho.SETORIAL,
                sinapse_orgao_id__in=orgaos,
                _n_unidades=0,
            )
            q |= Q(
                escopo_tipo=EscopoTextoPadraoDespacho.SECRETARIA,
                sinapse_orgao_id__in=orgaos,
                _n_unidades=0,
            )
        if uids:
            q |= Q(unidades__id__in=uids)
        q |= Q(
            escopo_tipo=EscopoTextoPadraoDespacho.PROTOCOLO,
            sinapse_orgao_id=PROTOCOLO_SINAPSE_ORGAO_ID,
        )
    return q


def queryset_visivel(
    usuario: Usuario,
    *,
    categoria: str | None = None,
    incluir_inativos: bool = False,
) -> QuerySet[TextoPadraoDespacho]:
    qs = TextoPadraoDespacho.objects.select_related("criado_por").prefetch_related(
        "unidades"
    ).annotate(_n_unidades=Count("unidades", distinct=True))
    if not incluir_inativos:
        qs = qs.filter(ativo=True)

    cats = categorias_visiveis_usuario(usuario)
    if categoria:
        cat_norm = normalizar_categoria_legada(categoria)
        if cat_norm in cats:
            qs = qs.filter(categoria=cat_norm)
        else:
            qs = qs.none()
    else:
        qs = qs.filter(categoria__in=cats)

    filtro = _q_visibilidade_usuario(usuario)
    if filtro == Q():
        return qs.order_by("ordem", "titulo").distinct()
    return qs.filter(filtro).order_by("ordem", "titulo").distinct()


def pode_editar(usuario: Usuario, modelo: TextoPadraoDespacho) -> bool:
    if not usuario_pode_acessar_modulo(usuario):
        return False
    if gestor_admin_pleno(usuario) and usuario.is_staff:
        return True
    if modelo.criado_por_id and modelo.criado_por_id == usuario.pk:
        return True
    return False


def escopo_resumo(modelo: TextoPadraoDespacho) -> str:
    tipo = modelo.escopo_tipo
    if tipo == EscopoTextoPadraoDespacho.GERAL:
        return "Uso geral"
    org_nome = (
        sinapse_catalog.get_orgao_nome(modelo.sinapse_orgao_id)
        if modelo.sinapse_orgao_id
        else None
    )
    unidades = list(modelo.unidades.all())
    if not unidades and modelo.unidade_administrativa_id:
        unidades = [modelo.unidade_administrativa]
    if tipo == EscopoTextoPadraoDespacho.PROTOCOLO:
        if unidades:
            rotulo = unidades[0].sigla or unidades[0].nome
            return f"Protocolo › {rotulo}"
        return "Protocolo geral"
    if len(unidades) == 1:
        setor = unidades[0].sigla or unidades[0].nome
        return f"{org_nome or 'Órgão'} › {setor}" if org_nome else setor
    if len(unidades) > 1:
        rotulos = ", ".join((u.sigla or u.nome) for u in unidades[:3])
        extra = f" (+{len(unidades) - 3})" if len(unidades) > 3 else ""
        prefixo = org_nome or "Setores"
        return f"{prefixo} › {rotulos}{extra}"
    if org_nome:
        return f"{org_nome} (todo o órgão)"
    return modelo.get_escopo_tipo_display()


def aplicar_placeholders(corpo: str, contexto: dict[str, Any] | None) -> str:
    if not corpo or not contexto:
        return corpo or ""

    def _sub(match: re.Match[str]) -> str:
        chave = match.group(1).lower()
        val = contexto.get(chave)
        if val is None:
            return match.group(0)
        return str(val)

    return _PLACEHOLDER.sub(_sub, corpo)


def resolver_descricao_tramitacao(
    demanda,
    descricao: str,
    *,
    orgao_destino: str = "",
    setor_destino: str = "",
    extra: dict[str, Any] | None = None,
) -> str:
    """Substitui {{placeholders}} na publicação de tramitações (H-JUL-08)."""
    texto = descricao or ""
    if not texto.strip() or "{{" not in texto:
        return texto
    ctx_extra: dict[str, Any] = dict(extra or {})
    if orgao_destino:
        ctx_extra.setdefault("orgao_destino", orgao_destino)
    if setor_destino:
        ctx_extra.setdefault("setor_destino", setor_destino)
    if "protocolo_executivo" not in ctx_extra and demanda is not None:
        pe = (getattr(demanda, "protocolo_executivo", None) or "").strip()
        if pe:
            ctx_extra.setdefault("protocolo_executivo", pe)
    return aplicar_placeholders(texto, contexto_demanda(demanda, ctx_extra))


def _nome_usuario(usuario) -> str:
    if not usuario:
        return ""
    partes = [
        (getattr(usuario, "first_name", None) or "").strip(),
        (getattr(usuario, "last_name", None) or "").strip(),
    ]
    nome = " ".join(p for p in partes if p)
    return nome or getattr(usuario, "username", "") or ""


def contexto_demanda(demanda, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    if demanda is None:
        return dict(extra or {})
    from core.services.cluster_aderencia_service import protocolo_executivo_efetivo

    autor = getattr(demanda, "autor", None)
    prazo = None
    try:
        prazo = demanda.prazo_dias
    except Exception:
        prazo = getattr(demanda, "prazo_efetivo_dias", None)

    ctx = {
        "protocolo_legislativo": getattr(demanda, "protocolo_legislativo", "") or "",
        "protocolo_executivo": protocolo_executivo_efetivo(demanda) or "",
        "demanda_titulo": getattr(demanda, "titulo", "") or "",
        "autor_nome": _nome_usuario(autor),
        "orgao_destino": "",
        "setor_destino": "",
        "prazo_dias": str(prazo) if prazo is not None else "",
    }
    for chave, val in (extra or {}).items():
        if val is not None and str(val).strip() != "":
            ctx[chave] = val
    return ctx
