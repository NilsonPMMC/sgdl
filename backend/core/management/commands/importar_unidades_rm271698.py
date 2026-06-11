"""Comando de importação RM271698 → UnidadeAdministrativa (C6)."""

from pathlib import Path

from django.core.management.base import BaseCommand

from core.services.rm_unidades_import_service import RmUnidadesImportService


class Command(BaseCommand):
    help = "Importa unidades administrativas da planilha RM271698."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simula a importação sem gravar no banco.",
        )
        parser.add_argument(
            "--xlsx",
            type=str,
            default="",
            help="Caminho alternativo para a planilha xlsx.",
        )
        parser.add_argument(
            "--depara-csv",
            type=str,
            default="",
            help="Caminho alternativo para o CSV de-para RM ↔ Sinapse.",
        )
        parser.add_argument(
            "--sem-csv",
            action="store_true",
            help="Não recarregar o CSV de-para antes da importação.",
        )

    def handle(self, *args, **options):
        svc = RmUnidadesImportService()
        if options["depara_csv"]:
            n = svc.carregar_depara_csv(options["depara_csv"])
            self.stdout.write(f"De-para carregado: {n} registros.")
        xlsx = options["xlsx"] or None
        resultado = svc.importar(
            xlsx_path=xlsx,
            dry_run=options["dry_run"],
            carregar_csv=not options["sem_csv"] and not options["depara_csv"],
        )
        data = resultado.to_dict()
        self.stdout.write(self.style.SUCCESS(f"Total linhas: {data['total_linhas']}"))
        self.stdout.write(f"Novas: {data['importadas']} | Atualizadas: {data['atualizadas']}")
        self.stdout.write(f"Órfãs (sem de-para): {data['ignoradas_orfaos']}")
        if data["orfaos_por_cod"]:
            self.stdout.write("Órfãos por COD_RM:")
            for cod, qtd in sorted(data["orfaos_por_cod"].items()):
                self.stdout.write(f"  {cod}: {qtd}")
        for err in data["erros"]:
            self.stdout.write(self.style.WARNING(err))
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry-run — nenhuma alteração persistida."))
