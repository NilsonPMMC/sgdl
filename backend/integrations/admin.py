from django.contrib import admin

from . import admin_sinapse_catalog  # noqa: F401 — CatalogOrgao e CatalogServico (Sinapse)
from .models import SinapseServiceSync, SinapseServicoMap

@admin.register(SinapseServicoMap)
class SinapseServicoMapAdmin(admin.ModelAdmin):
    list_display = (
        "sinapse_service_id",
        "match_status",
        "match_rule",
        "confidence",
        "last_manual_actor",
        "last_seen_at",
        "updated_at",
    )
    list_filter = ("match_status", "match_rule")
    search_fields = ("sinapse_service_id", "notes")
    readonly_fields = ("created_at", "updated_at", "last_seen_at")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "sinapse_service_id",
                    "match_status",
                    "match_rule",
                    "confidence",
                    "notes",
                    "last_manual_actor",
                    "last_manual_at",
                    "last_seen_at",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )


@admin.register(SinapseServiceSync)
class SinapseServiceSyncAdmin(admin.ModelAdmin):
    list_display = (
        "sinapse_service_id",
        "status_sync",
        "source_table",
        "version",
        "last_sync_at",
    )
    list_filter = ("status_sync", "source_table")
    search_fields = ("sinapse_service_id",)
    readonly_fields = ("created_at", "updated_at", "hash_payload")
