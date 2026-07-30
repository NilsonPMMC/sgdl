"""Seed da base local de vias de Mogi das Cruzes (geocoding Fase 3)."""

from django.core.management.base import BaseCommand

from core.models_via_referencia import ViaReferenciaMogi
from core.services.geocoding_service import GeocodingService
from core.services.via_referencia_service import ViaReferenciaService

_VIAS_SEED = (
    {
        "logradouro": "Avenida Francisco Ruiz",
        "bairro": "Vila da Prata",
        "latitude": -23.572229,
        "longitude": -46.185545,
        "observacao": "Homologação jun/2026 — variantes Av./Avenida",
    },
    {
        "logradouro": "Avenida Vereador Narciso Yague Guimarães",
        "bairro": "Centro Cívico",
        "observacao": "Via central MC",
    },
    {
        "logradouro": "Rua Dr. Ricardo",
        "bairro": "Centro",
        "observacao": "Centro histórico",
    },
    {
        "logradouro": "Parque Centenário",
        "bairro": "Vila Mogilar",
        "observacao": "Parque público frequente no Copiloto",
    },
)


class Command(BaseCommand):
    help = (
        "Popula/atualiza ViaReferenciaMogi com vias conhecidas. "
        "Coordenadas ausentes são resolvidas via GeocodingService (OSM/ViaCEP)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--geocode",
            action="store_true",
            help="Geocodificar vias sem lat/lng (consulta Nominatim).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas exibe o que seria gravado.",
        )

    def handle(self, *args, **options):
        geocode = bool(options["geocode"])
        dry_run = bool(options["dry_run"])
        svc_ref = ViaReferenciaService()
        geocoder = GeocodingService()
        criados = 0
        atualizados = 0

        for item in _VIAS_SEED:
            logr = item["logradouro"]
            bai = item["bairro"]
            lat = item.get("latitude")
            lng = item.get("longitude")
            obs = item.get("observacao", "")

            if (lat is None or lng is None) and geocode:
                res = geocoder.resolver_endereco_geocode(logr, bai, None)
                lat = res.get("latitude") or res.get("latitude_bruta")
                lng = res.get("longitude") or res.get("longitude_bruta")

            if dry_run:
                self.stdout.write(
                    f"[dry-run] {logr} | {bai} → lat={lat} lng={lng} ({obs})"
                )
                continue

            antes = ViaReferenciaMogi.objects.filter(
                chave_canonica=geocoder.chave_endereco(logr, bai, None)
            ).exists()
            obj = svc_ref.registrar(
                logradouro=logr,
                bairro=bai,
                latitude=float(lat) if lat is not None else None,
                longitude=float(lng) if lng is not None else None,
                origem=ViaReferenciaMogi.ORIGEM_SEED,
                observacao=obs,
            )
            if obj:
                if antes:
                    atualizados += 1
                else:
                    criados += 1
                self.stdout.write(self.style.SUCCESS(f"OK: {obj}"))

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run — nada gravado."))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Concluído: {criados} nova(s), {atualizados} atualizada(s)."
                )
            )
