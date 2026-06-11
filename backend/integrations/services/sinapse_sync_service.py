import logging
import hashlib
import json
import re
from datetime import datetime
from html import unescape
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from integrations import sinapse_catalog
from integrations.models import SinapseServiceSync, SinapseServicoMap
from integrations.sinapse_client import SinapseClient, SinapseClientError

logger = logging.getLogger(__name__)


class SinapseSyncService:
    """
    Serviço de sincronização da Carta de Serviços via base Sinapse.
    Nesta sprint, entrega modo dry-run e mapeamento de colunas em memória.
    """

    def __init__(self, table_name: str | None = None):
        self.client = None
        self.table_name = table_name or settings.SINAPSE_SERVICE_TABLE

    def _client(self) -> SinapseClient:
        if self.client is None:
            self.client = SinapseClient()
        return self.client

    @staticmethod
    def _as_text(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def _strip_html(value: Any) -> str:
        text = SinapseSyncService._as_text(value)
        if not text:
            return ""
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</p\s*>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _parse_sla_days(value: Any) -> int | None:
        text = SinapseSyncService._strip_html(value).lower()
        if not text:
            return None
        # Extrai o primeiro inteiro relevante (ex.: "15 dias", "04 meses").
        match = re.search(r"\d+", text)
        if not match:
            return None
        number = int(match.group(0))
        if "mes" in text:
            return number * 30
        return number

    @staticmethod
    def _parse_list_field(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [SinapseSyncService._strip_html(v) for v in value if SinapseSyncService._strip_html(v)]

        text = SinapseSyncService._as_text(value)
        if not text:
            return []

        # Alguns campos chegam como JSON serializado em string.
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return [SinapseSyncService._strip_html(v) for v in parsed if SinapseSyncService._strip_html(v)]
            except json.JSONDecodeError:
                pass

        normalized = SinapseSyncService._strip_html(text)
        if not normalized:
            return []
        parts = re.split(r"[;\n|]+", normalized)
        cleaned = [part.strip(" -\t") for part in parts if part.strip(" -\t")]
        return cleaned or [normalized]

    @staticmethod
    def _provider_secretariat(raw: dict[str, Any]) -> str | None:
        candidates = [
            raw.get("provider_secretariat"),
            raw.get("secretaria"),
            raw.get("orgao"),
            raw.get("departamento"),
            raw.get("orgao_responsavel"),
        ]
        for candidate in candidates:
            text = SinapseSyncService._strip_html(candidate)
            if text:
                return text
        return None

    @staticmethod
    def _normalize_name(value: Any) -> str:
        text = SinapseSyncService._strip_html(value).lower()
        # Mantem apenas caracteres alfanumericos e espaco.
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _upsert_service_mapping(
        self,
        sinapse_service_id: str,
        service_name: str,
    ) -> tuple[bool, bool]:
        """Retorna (presente_no_catalogo, registro_map_criado_agora)."""
        try:
            in_catalog = sinapse_catalog.servico_existe(int(sinapse_service_id))
        except (TypeError, ValueError):
            in_catalog = False

        defaults = {
            "match_status": "AUTO" if in_catalog else "UNMATCHED",
            "match_rule": "catalog_servico_id" if in_catalog else "none",
            "confidence": "1.00" if in_catalog else "0.00",
            "notes": None if in_catalog else "Serviço ausente no catálogo Sinapse.",
            "last_seen_at": timezone.now(),
        }
        obj, created_now = SinapseServicoMap.objects.get_or_create(
            sinapse_service_id=sinapse_service_id,
            defaults=defaults,
        )

        if not created_now:
            obj.match_status = defaults["match_status"]
            obj.match_rule = defaults["match_rule"]
            obj.confidence = defaults["confidence"]
            obj.notes = defaults["notes"]
            obj.last_seen_at = defaults["last_seen_at"]
            obj.save(
                update_fields=[
                    "match_status",
                    "match_rule",
                    "confidence",
                    "notes",
                    "last_seen_at",
                    "updated_at",
                ]
            )
        return in_catalog, created_now

    def list_unmatched(
        self,
        limit: int = 100,
        match_status: str = "UNMATCHED",
        search: str | None = None,
        min_confidence: float | None = None,
    ) -> list[dict[str, Any]]:
        qs = SinapseServicoMap.objects.all().order_by("-updated_at")
        if match_status:
            qs = qs.filter(match_status=match_status.upper())
        if min_confidence is not None:
            qs = qs.filter(confidence__gte=min_confidence)
        qs = qs[:limit]

        output: list[dict[str, Any]] = []
        for item in qs:
            sync = SinapseServiceSync.objects.filter(sinapse_service_id=item.sinapse_service_id).first()
            payload = (sync.payload if sync else {}) or {}
            service_name = payload.get("service_name") or ""
            provider_secretariat = payload.get("provider_secretariat") or ""
            if search:
                term = search.strip().lower()
                if term and term not in item.sinapse_service_id.lower() and term not in service_name.lower() and term not in provider_secretariat.lower():
                    continue
            output.append(
                {
                    "sinapse_service_id": item.sinapse_service_id,
                    "service_name": service_name,
                    "provider_secretariat": provider_secretariat,
                    "match_status": item.match_status,
                    "match_rule": item.match_rule,
                    "confidence": float(item.confidence),
                    "catalog_servico_id": int(item.sinapse_service_id)
                    if str(item.sinapse_service_id).isdigit()
                    else None,
                    "catalog_titulo": (
                        sinapse_catalog.get_servico(int(item.sinapse_service_id)).titulo
                        if str(item.sinapse_service_id).isdigit()
                        and sinapse_catalog.get_servico(int(item.sinapse_service_id))
                        else None
                    ),
                    "last_manual_actor": item.last_manual_actor,
                    "last_manual_at": item.last_manual_at,
                    "notes": item.notes,
                    "updated_at": item.updated_at,
                }
            )
        return output

    def bind_manual_mapping(
        self,
        sinapse_service_id: str,
        servico_local_id: int | None = None,
        actor: str | None = None,
    ) -> dict[str, Any]:
        """Confirma vínculo com o catálogo Sinapse (servico_local_id legado = mesmo ID)."""
        catalog_id = servico_local_id
        if catalog_id is None:
            try:
                catalog_id = int(sinapse_service_id)
            except (TypeError, ValueError) as exc:
                raise SinapseClientError("ID de serviço Sinapse inválido.") from exc

        if not sinapse_catalog.servico_existe(int(catalog_id)):
            raise SinapseClientError(f"Serviço {catalog_id} não encontrado no catálogo Sinapse.")

        mapping, _ = SinapseServicoMap.objects.get_or_create(
            sinapse_service_id=str(sinapse_service_id),
            defaults={"last_seen_at": timezone.now()},
        )

        actor_name = (actor or "manual").strip() or "manual"
        now = timezone.now()
        audit_line = (
            f"[{now.isoformat()}] actor={actor_name} confirm catalog_id={catalog_id}"
        )
        existing_notes = (mapping.notes or "").strip()
        mapping.notes = f"{existing_notes}\n{audit_line}".strip() if existing_notes else audit_line
        mapping.match_status = "MANUAL"
        mapping.match_rule = "manual_catalog_confirm"
        mapping.confidence = "1.00"
        mapping.last_manual_actor = actor_name
        mapping.last_manual_at = now
        mapping.last_seen_at = now
        mapping.save()

        titulo = None
        try:
            catalog = sinapse_catalog.get_servico(int(catalog_id))
            titulo = catalog.titulo if catalog else None
        except Exception:
            titulo = None
        return {
            "sinapse_service_id": mapping.sinapse_service_id,
            "catalog_servico_id": int(catalog_id),
            "catalog_titulo": titulo,
            "match_status": mapping.match_status,
            "match_rule": mapping.match_rule,
            "last_manual_actor": mapping.last_manual_actor,
            "last_manual_at": mapping.last_manual_at,
        }

    def bulk_bind_manual(
        self,
        bindings: list[dict[str, Any]],
        actor: str | None = None,
    ) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for entry in bindings:
            sinapse_service_id = str(entry.get("sinapse_service_id") or "").strip()
            servico_local_id = entry.get("servico_local_id") or entry.get("catalog_servico_id")
            if not sinapse_service_id:
                errors.append(
                    {
                        "sinapse_service_id": sinapse_service_id or None,
                        "detail": "Informe sinapse_service_id em cada item.",
                    }
                )
                continue
            try:
                result = self.bind_manual_mapping(
                    sinapse_service_id=sinapse_service_id,
                    servico_local_id=int(servico_local_id) if servico_local_id else None,
                    actor=actor,
                )
                results.append(result)
            except (SinapseClientError, ValueError) as exc:
                errors.append({"sinapse_service_id": sinapse_service_id, "detail": str(exc)})

        return {
            "total_received": len(bindings),
            "total_bound": len(results),
            "total_errors": len(errors),
            "results": results,
            "errors": errors,
        }

    def sync_health_report(self) -> dict[str, Any]:
        total_sync = SinapseServiceSync.objects.count()
        total_maps = SinapseServicoMap.objects.count()
        unmatched = SinapseServicoMap.objects.filter(match_status="UNMATCHED").count()
        divergent = SinapseServiceSync.objects.filter(status_sync="DIVERGENT").count()
        error = SinapseServiceSync.objects.filter(status_sync="ERROR").count()
        last_sync = SinapseServiceSync.objects.order_by("-last_sync_at").values_list("last_sync_at", flat=True).first()

        unmatched_threshold = int(getattr(settings, "SINAPSE_ALERT_UNMATCHED_THRESHOLD", 200))
        divergent_threshold = int(getattr(settings, "SINAPSE_ALERT_DIVERGENT_THRESHOLD", 20))

        alert_level = "OK"
        reasons: list[str] = []
        if unmatched >= unmatched_threshold:
            alert_level = "ALERT"
            reasons.append(f"UNMATCHED acima do limiar ({unmatched} >= {unmatched_threshold})")
        if divergent >= divergent_threshold:
            alert_level = "ALERT"
            reasons.append(f"DIVERGENT acima do limiar ({divergent} >= {divergent_threshold})")
        if error > 0:
            alert_level = "ALERT"
            reasons.append(f"Registros em ERROR detectados ({error})")

        report = {
            "alert_level": alert_level,
            "reasons": reasons,
            "summary": {
                "total_sync_records": total_sync,
                "total_mapping_records": total_maps,
                "unmatched_mappings": unmatched,
                "divergent_sync_records": divergent,
                "error_sync_records": error,
                "last_sync_at": last_sync,
            },
            "thresholds": {
                "unmatched_threshold": unmatched_threshold,
                "divergent_threshold": divergent_threshold,
            },
        }
        return report

    @staticmethod
    def map_service_record(raw: dict[str, Any]) -> dict[str, Any]:
        """
        Contrato mínimo interno esperado.
        Como os nomes reais de colunas podem variar, aplicamos fallback por chaves comuns.
        """
        required_documents_raw = raw.get("required_documents") or raw.get("documentos") or raw.get("documentos_necessarios")
        channels_raw = raw.get("channels") or raw.get("canais") or raw.get("telefone")
        sla_raw = raw.get("sla_days") or raw.get("prazo_dias") or raw.get("prazo")

        return {
            "service_id": raw.get("service_id") or raw.get("id") or raw.get("codigo"),
            "service_name": raw.get("service_name") or raw.get("nome") or raw.get("titulo"),
            "provider_secretariat": SinapseSyncService._provider_secretariat(raw),
            "sla_days": SinapseSyncService._parse_sla_days(sla_raw),
            "required_documents": SinapseSyncService._parse_list_field(required_documents_raw),
            "channels": SinapseSyncService._parse_list_field(channels_raw),
            "active": raw.get("active") if "active" in raw else raw.get("ativo"),
            "updated_at": raw.get("updated_at") or raw.get("data_atualizacao"),
            "raw": raw,
        }

    def dry_run(self, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        rows = self._client().fetch_services(self.table_name, limit=limit, offset=offset)
        mapped = [self.map_service_record(row) for row in rows]

        missing_name = sum(1 for item in mapped if not item.get("service_name"))
        local_count = len(sinapse_catalog.list_servicos_api(limit=5000))

        sample = []
        for item in mapped[:5]:
            raw = item.get("raw") or {}
            sample.append(
                {
                    "service_id": item.get("service_id"),
                    "service_name": item.get("service_name"),
                    "provider_secretariat": item.get("provider_secretariat"),
                    "sla_days": item.get("sla_days"),
                    "updated_at": item.get("updated_at"),
                    "source_status": raw.get("status"),
                    "source_slug": raw.get("slug"),
                }
            )

        summary = {
            "table_name": self.table_name,
            "fetched": len(rows),
            "missing_service_name": missing_name,
            "local_services_count": local_count,
            "sample": sample,
        }
        logger.info(
            "Sinapse dry-run concluído: tabela=%s, fetched=%s, missing_name=%s",
            self.table_name,
            summary["fetched"],
            summary["missing_service_name"],
        )
        return summary

    @staticmethod
    def compute_payload_hash(payload: dict[str, Any]) -> str:
        normalized = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
        # Garante compatibilidade com JSONField mesmo quando vierem datetime/Decimal do driver.
        return json.loads(json.dumps(payload, ensure_ascii=False, default=str))

    @staticmethod
    def parse_dt(value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        raw = str(value).strip()
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _mark_divergence(self, service_id: str, message: str):
        obj, _ = SinapseServiceSync.objects.get_or_create(
            sinapse_service_id=service_id,
            defaults={
                "source_table": self.table_name,
                "version": "",
                "hash_payload": self.compute_payload_hash({"service_id": service_id, "error": message}),
                "payload": {"service_id": service_id, "error": message},
                "status_sync": "DIVERGENT",
                "divergencia": message,
                "last_sync_at": timezone.now(),
            },
        )
        if obj.status_sync != "DIVERGENT" or obj.divergencia != message:
            obj.status_sync = "DIVERGENT"
            obj.divergencia = message
            obj.last_sync_at = timezone.now()
            obj.save(update_fields=["status_sync", "divergencia", "last_sync_at", "updated_at"])

    def _sync_records(
        self,
        batch_size: int = 500,
        max_records: int | None = None,
        incremental: bool = False,
        reconcile: bool = False,
    ) -> dict[str, Any]:
        offset = 0
        processed = 0
        created = 0
        updated = 0
        unchanged = 0
        skipped_missing_id = 0
        skipped_missing_name = 0
        skipped_by_updated_at = 0
        divergentes = 0
        mapped_local = 0
        unmapped_local = 0
        mapping_records_created = 0
        seen_ids: set[str] = set()
        while True:
            if max_records is not None and processed >= max_records:
                break

            remaining = (max_records - processed) if max_records is not None else batch_size
            limit = min(batch_size, remaining) if max_records is not None else batch_size
            rows = self._client().fetch_services(self.table_name, limit=limit, offset=offset)
            if not rows:
                break

            mapped_rows = [self.map_service_record(row) for row in rows]

            for mapped in mapped_rows:
                mapped = self.sanitize_payload(mapped)
                service_id = mapped.get("service_id")
                service_name = mapped.get("service_name")
                service_id_str = str(service_id) if service_id is not None else ""

                if not service_id:
                    skipped_missing_id += 1
                    if reconcile:
                        divergentes += 1
                    continue

                seen_ids.add(service_id_str)

                if not service_name:
                    skipped_missing_name += 1
                    if reconcile:
                        self._mark_divergence(service_id_str, "Registro sem service_name.")
                        divergentes += 1
                    continue

                payload_hash = self.compute_payload_hash(mapped)
                source_version = str(mapped.get("updated_at") or "")

                existing = SinapseServiceSync.objects.filter(sinapse_service_id=service_id_str).first()
                if incremental and existing:
                    src_dt = self.parse_dt(source_version)
                    dst_dt = self.parse_dt(existing.version)
                    if src_dt and dst_dt and src_dt <= dst_dt:
                        skipped_by_updated_at += 1
                        continue

                with transaction.atomic():
                    obj, created_now = SinapseServiceSync.objects.get_or_create(
                        sinapse_service_id=service_id_str,
                        defaults={
                            "source_table": self.table_name,
                            "version": source_version,
                            "hash_payload": payload_hash,
                            "payload": mapped,
                            "status_sync": "SYNCED",
                            "divergencia": None,
                            "last_sync_at": timezone.now(),
                        },
                    )
                    is_mapped, map_created = self._upsert_service_mapping(
                        sinapse_service_id=service_id_str,
                        service_name=service_name,
                    )
                    if is_mapped:
                        mapped_local += 1
                    else:
                        unmapped_local += 1
                    if map_created:
                        mapping_records_created += 1

                if created_now:
                    created += 1
                    continue

                if obj.hash_payload == payload_hash:
                    unchanged += 1
                    obj.last_sync_at = timezone.now()
                    obj.source_table = self.table_name
                    obj.status_sync = "SYNCED"
                    obj.divergencia = None
                    obj.version = source_version or obj.version or ""
                    obj.save(
                        update_fields=[
                            "last_sync_at",
                            "source_table",
                            "status_sync",
                            "divergencia",
                            "version",
                            "updated_at",
                        ]
                    )
                    continue

                obj.source_table = self.table_name
                obj.version = source_version
                obj.hash_payload = payload_hash
                obj.payload = mapped
                obj.status_sync = "SYNCED"
                obj.divergencia = None
                obj.last_sync_at = timezone.now()
                obj.save()
                updated += 1

            processed += len(rows)
            offset += len(rows)

        if reconcile:
            stale_qs = SinapseServiceSync.objects.filter(source_table=self.table_name).exclude(
                sinapse_service_id__in=seen_ids
            )
            stale_count = stale_qs.count()
            if stale_count:
                stale_qs.update(
                    status_sync="DIVERGENT",
                    divergencia="Registro nao encontrado na leitura atual da fonte Sinapse.",
                    last_sync_at=timezone.now(),
                )
            divergentes += stale_count

        summary = {
            "table_name": self.table_name,
            "processed": processed,
            "created": created,
            "updated": updated,
            "unchanged": unchanged,
            "skipped_by_updated_at": skipped_by_updated_at,
            "skipped_missing_id": skipped_missing_id,
            "skipped_missing_name": skipped_missing_name,
            "divergentes": divergentes,
            "mapped_local": mapped_local,
            "unmapped_local": unmapped_local,
            "mapping_records_created": mapping_records_created,
            "mapping_total": SinapseServicoMap.objects.count(),
            "total_synced_records": SinapseServiceSync.objects.count(),
        }
        return summary

    def full_sync(self, batch_size: int = 500, max_records: int | None = None) -> dict[str, Any]:
        summary = self._sync_records(batch_size=batch_size, max_records=max_records, incremental=False, reconcile=False)
        logger.info(
            "Sinapse full-sync concluido tabela=%s processed=%s created=%s updated=%s unchanged=%s",
            self.table_name,
            summary["processed"],
            summary["created"],
            summary["updated"],
            summary["unchanged"],
        )
        return summary

    def incremental_sync(self, batch_size: int = 500, max_records: int | None = None) -> dict[str, Any]:
        summary = self._sync_records(batch_size=batch_size, max_records=max_records, incremental=True, reconcile=False)
        logger.info(
            "Sinapse incremental-sync concluido tabela=%s processed=%s created=%s updated=%s unchanged=%s skip_updated_at=%s",
            self.table_name,
            summary["processed"],
            summary["created"],
            summary["updated"],
            summary["unchanged"],
            summary["skipped_by_updated_at"],
        )
        return summary

    def reconcile(self, batch_size: int = 500, max_records: int | None = None) -> dict[str, Any]:
        summary = self._sync_records(batch_size=batch_size, max_records=max_records, incremental=False, reconcile=True)
        logger.info(
            "Sinapse reconcile concluido tabela=%s processed=%s divergentes=%s",
            self.table_name,
            summary["processed"],
            summary["divergentes"],
        )
        return summary

    def test_connection(self) -> bool:
        return self._client().test_connection()

    def list_candidate_tables(self) -> list[str]:
        return self._client().list_candidate_tables()
