import uuid

from django.db import models
from django.utils import timezone

# Registra os models read-only do barramento Sinapse no app registry.
from . import models_sinapse  # noqa: F401  (efeito colateral: registro de models)


class SinapseServicoMap(models.Model):
    MATCH_STATUS_CHOICES = (
        ("AUTO", "Auto mapeado"),
        ("MANUAL", "Mapeado manualmente"),
        ("UNMATCHED", "Sem correspondencia"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sinapse_service_id = models.CharField(max_length=100, unique=True)
    match_status = models.CharField(max_length=20, choices=MATCH_STATUS_CHOICES, default="UNMATCHED")
    match_rule = models.CharField(max_length=100, blank=True, null=True)
    confidence = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    notes = models.TextField(blank=True, null=True)
    last_manual_actor = models.CharField(max_length=150, blank=True, null=True)
    last_manual_at = models.DateTimeField(blank=True, null=True)
    last_seen_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["match_status"]),
            models.Index(fields=["last_seen_at"]),
        ]

    def __str__(self):
        return f"SinapseServicoMap<{self.sinapse_service_id}>"


class SinapseServiceSync(models.Model):
    STATUS_CHOICES = (
        ("SYNCED", "Sincronizado"),
        ("DIVERGENT", "Divergente"),
        ("ERROR", "Erro"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sinapse_service_id = models.CharField(max_length=100, unique=True)
    source_table = models.CharField(max_length=255, blank=True, null=True)
    version = models.CharField(max_length=64, blank=True, null=True)
    hash_payload = models.CharField(max_length=64)
    payload = models.JSONField(default=dict)
    status_sync = models.CharField(max_length=20, choices=STATUS_CHOICES, default="SYNCED")
    divergencia = models.TextField(blank=True, null=True)
    last_sync_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_sync_at"]
        indexes = [
            models.Index(fields=["status_sync"]),
            models.Index(fields=["last_sync_at"]),
        ]

    def __str__(self):
        return f"SinapseServiceSync<{self.sinapse_service_id}>"
