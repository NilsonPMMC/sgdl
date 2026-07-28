"""Gera relatório de aprendizado a partir do CSV legado (sem importar Demandas)."""

from django.core.management.base import BaseCommand

from core.services.corpus_legado_service import (
    corpus_legado_csv_path,
    corpus_legado_json_path,
    gerar_relatorio_corpus,
)


class Command(BaseCommand):
    help = (
        "Analisa docs/bd-legado-demandas-vereadores.csv e gera docs/insights/corpus-legado.json. "
        "Não altera Demandas nem o fluxo do Copiloto."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            type=str,
            default="",
            help="Caminho alternativo do CSV legado",
        )
        parser.add_argument(
            "--saida",
            type=str,
            default="",
            help="Caminho alternativo do JSON de saída",
        )

    def handle(self, *args, **options):
        csv_path = corpus_legado_csv_path()
        json_path = corpus_legado_json_path()
        if options.get("csv"):
            from pathlib import Path

            csv_path = Path(options["csv"]).resolve()
        if options.get("saida"):
            from pathlib import Path

            json_path = Path(options["saida"]).resolve()

        self.stdout.write(f"Lendo {csv_path} …")
        rel = gerar_relatorio_corpus(csv_path=csv_path, json_path=json_path)
        self.stdout.write(self.style.SUCCESS(f"✓ {rel['total_registros']} registros analisados"))
        self.stdout.write(f"  JSON: {json_path}")
        self.stdout.write(f"  SHA256 CSV: {rel.get('checksum_csv', '')[:16]}…")
        self.stdout.write("")
        self.stdout.write("Top 10 trends:")
        for t in (rel.get("top_trends") or [])[:10]:
            self.stdout.write(
                f"  {t['volume']:5d}  {t['titulo']}  → atalho: {t.get('atalho_sugerido')}"
            )
