"""Gera relatório de IDs duplicados na planilha RM271698 (conferência)."""

from pathlib import Path

from django.core.management.base import BaseCommand

from core.services.rm_unidades_import_service import DEFAULT_XLSX


class Command(BaseCommand):
    help = "Gera docs/operacao/rm271698-ids-duplicados-conferencia.md"

    def handle(self, *args, **options):
        import openpyxl
        from collections import defaultdict

        xlsx = DEFAULT_XLSX
        if not xlsx.is_file():
            self.stderr.write(f"Planilha não encontrada: {xlsx}")
            return

        wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
        ws = wb.active
        by_id: dict[int, list] = defaultdict(list)
        all_rows = 0
        for i, r in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            if r[1] is None:
                continue
            all_rows += 1
            uid = int(r[1])
            by_id[uid].append(
                {
                    "linha": i,
                    "sigla": str(r[2] or "").strip(),
                    "nome": str(r[3] or "").strip(),
                    "email": str(r[4] or "").strip(),
                }
            )

        dups = {k: v for k, v in by_id.items() if len(v) > 1}
        out_path = Path(__file__).resolve().parents[4] / "docs" / "operacao" / "rm271698-ids-duplicados-conferencia.md"

        def esc(s: str) -> str:
            return (s or "").replace("|", "\\|")

        lines = [
            "# Relatório de conferência — IDs duplicados na RM271698",
            "",
            "> Gerado por `manage.py gerar_relatorio_rm_duplicados`. Validação com fonte RM/SEI; não altera o banco.",
            "",
            "## Resumo",
            "",
            "| Métrica | Valor |",
            "|---------|-------|",
            f"| Linhas na planilha | {all_rows} |",
            f"| IDs únicos (`ID_UNIDADE`) | {len(by_id)} |",
            f"| Linhas extras (duplicatas) | {all_rows - len(by_id)} |",
            f"| IDs com mais de uma linha | {len(dups)} |",
            f"| Registros no banco SGDL (esperado) | {len(by_id)} |",
            "",
            "A importação SGDL usa `ID_UNIDADE` como chave (`UnidadeAdministrativa.sinapse_unidade_id`): "
            "**1 registro por ID**. Linhas repetidas atualizam o mesmo registro; "
            "a **última linha processada** prevalece no e-mail.",
            "",
            "Ver também: [importacao-unidades-rm271698.md](importacao-unidades-rm271698.md).",
            "",
            "---",
            "",
            "## Detalhamento por ID",
            "",
        ]

        for uid in sorted(dups.keys()):
            ocorrencias = dups[uid]
            siglas = {o["sigla"] for o in ocorrencias}
            nomes = {o["nome"] for o in ocorrencias}
            emails = [o["email"] for o in ocorrencias]
            emails_unicos = set(emails)
            conflito = len(siglas) > 1 or len(nomes) > 1 or len(emails_unicos) > 1
            lines.append(f"### ID `{uid}` — {len(ocorrencias)} ocorrências")
            lines.append("")
            if conflito:
                lines.append("**Atenção:** sigla, nome ou e-mail divergem entre linhas.")
            else:
                lines.append("Mesma sigla/nome em todas as linhas; possível duplicata de exportação.")
            lines.append("")
            lines.append("| Linha | Sigla | Unidade | E-mail |")
            lines.append("|-------|-------|---------|--------|")
            for o in ocorrencias:
                lines.append(
                    f"| {o['linha']} | {esc(o['sigla'])} | {esc(o['nome'][:80])} | {esc(o['email'])} |"
                )
            lines.append("")
            if len(emails_unicos) > 1:
                ult = ocorrencias[-1]
                lines.append(
                    f"E-mails distintos: {len(emails_unicos)} — na importação prevalece "
                    f"a **linha {ult['linha']}** (`{ult['email']}`)."
                )
                lines.append("")

        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Relatório: {out_path}"))
        self.stdout.write(f"IDs duplicados: {len(dups)}")
