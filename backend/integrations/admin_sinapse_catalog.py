"""Admin somente leitura para tabelas `catalog_*` do barramento Sinapse."""

from __future__ import annotations

import re
from html import unescape

from django.contrib import admin, messages
from django.db import connections

from integrations.models_sinapse import (
    SINAPSE_DB_ALIAS,
    CatalogOrgao,
    CatalogServico,
)


def _sinapse_disponivel() -> bool:
    return SINAPSE_DB_ALIAS in connections.databases


class SinapseCatalogReadOnlyAdmin(admin.ModelAdmin):
    """Listagem/consulta no Postgres Sinapse; sem criar, editar ou excluir."""

    show_full_result_count = False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not _sinapse_disponivel():
            return qs.none()
        return qs.using(SINAPSE_DB_ALIAS)

    def changelist_view(self, request, extra_context=None):
        if not _sinapse_disponivel():
            self.message_user(
                request,
                "Banco Sinapse não configurado (DATABASES['sinapse']). "
                "As tabelas do catálogo não podem ser listadas.",
                level=messages.WARNING,
            )
        return super().changelist_view(request, extra_context=extra_context)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return bool(request.user.is_active and request.user.is_staff and _sinapse_disponivel())

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ()
        return [f.name for f in self.model._meta.fields if f.name != "embedding"]

    def get_exclude(self, request, obj=None):
        excluded = set(super().get_exclude(request, obj) or ())
        excluded.add("embedding")
        return tuple(excluded)


@admin.register(CatalogOrgao)
class CatalogOrgaoAdmin(SinapseCatalogReadOnlyAdmin):
    """Órgãos responsáveis (equivale às secretarias no SGDL — `sinapse_orgao_id`)."""

    list_display = ("id", "nome", "tipo_orgao", "grupo", "slug", "updated_at")
    list_filter = ("tipo_orgao", "grupo")
    search_fields = ("nome", "slug", "tipo_orgao")
    ordering = ("nome",)
    date_hierarchy = "updated_at"

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "id",
                    "nome",
                    "tipo_orgao",
                    "grupo",
                    "slug",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )


@admin.register(CatalogServico)
class CatalogServicoAdmin(SinapseCatalogReadOnlyAdmin):
    """Carta de serviços municipal (vinculada às demandas via `sinapse_servico_id`)."""

    list_display = (
        "id",
        "titulo_curto",
        "id_orgao",
        "id_categoria",
        "status",
        "prazo_resumo",
        "updated_at",
    )
    list_filter = ("status", "id_orgao", "id_categoria", "id_tipo_atendimento")
    search_fields = ("titulo", "departamento", "slug", "texto_limpo_rag")
    ordering = ("titulo",)
    raw_id_fields = (
        "id_categoria",
        "id_orgao",
        "id_tipo_publico",
        "id_tipo_atendimento",
    )
    date_hierarchy = "updated_at"

    @admin.display(description="Título")
    def titulo_curto(self, obj: CatalogServico) -> str:
        t = (obj.titulo or "").strip()
        return t[:100] + ("…" if len(t) > 100 else "")

    @admin.display(description="Prazo")
    def prazo_resumo(self, obj: CatalogServico) -> str:
        p = (obj.prazo or "").strip()
        if not p:
            return "—"
        p = re.sub(r"<[^>]+>", " ", unescape(p))
        p = re.sub(r"\s+", " ", p).strip()
        return p[:80] + ("…" if len(p) > 80 else "")

    fieldsets = (
        (
            "Identificação",
            {
                "fields": (
                    "id",
                    "titulo",
                    "slug",
                    "status",
                    "id_orgao",
                    "id_categoria",
                    "id_tipo_publico",
                    "id_tipo_atendimento",
                    "departamento",
                )
            },
        ),
        (
            "Atendimento",
            {
                "fields": (
                    "prazo",
                    "agendamento",
                    "solicitacao_internet",
                    "solicitacao_perfil",
                    "atendimento_dia_hora",
                    "documentos_necessarios",
                    "telefone",
                    "email",
                )
            },
        ),
        (
            "Conteúdo",
            {
                "fields": (
                    "descricao_html",
                    "requisitos_html",
                    "fluxo_html",
                    "observacoes_html",
                    "texto_limpo_rag",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadados",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )
