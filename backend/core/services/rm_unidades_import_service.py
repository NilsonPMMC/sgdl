"""Importação da planilha RM271698 → UnidadeAdministrativa (C6)."""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.models_depara_rm import DeParaRmSinapse
from core.models_unidade_administrativa import UnidadeAdministrativa

logger = logging.getLogger(__name__)

DEFAULT_XLSX = Path(__file__).resolve().parents[3] / "docs" / "RM271698 - UNIDADES (1).xlsx"
DEFAULT_DEPARA_CSV = Path(__file__).resolve().parents[3] / "docs" / "de-para-rm-sinapse.csv"


@dataclass
class ImportRmResultado:
    total_linhas: int = 0
    importadas: int = 0
    atualizadas: int = 0
    ignoradas_orfaos: int = 0
    ignoradas_inativas: int = 0
    erros: list[str] = field(default_factory=list)
    orfaos_por_cod: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_linhas": self.total_linhas,
            "importadas": self.importadas,
            "atualizadas": self.atualizadas,
            "ignoradas_orfaos": self.ignoradas_orfaos,
            "ignoradas_inativas": self.ignoradas_inativas,
            "erros": self.erros[:50],
            "orfaos_por_cod": self.orfaos_por_cod,
        }


def extrair_cod_rm(sigla_unidade: str) -> str | None:
    partes = (sigla_unidade or "").strip().upper().split("-")
    if len(partes) >= 2:
        return partes[1] or None
    return None


def extrair_sigla_curta(sigla_unidade: str) -> str:
    partes = (sigla_unidade or "").strip().upper().split("-")
    if len(partes) >= 3:
        return "-".join(partes[2:])[:32]
    if partes:
        return partes[-1][:32]
    return ""


def sigla_para_importacao(sigla_completa: str, sinapse_unidade_id: int) -> str:
    """Sigla RM completa (até 32 chars) ou fallback pelo ID."""
    base = (sigla_completa or "").strip().upper()[:32]
    if base:
        return base
    curta = extrair_sigla_curta(sigla_completa)
    if curta:
        return curta
    return f"U{sinapse_unidade_id}"[:32]


class RmUnidadesImportService:
    def carregar_depara_csv(self, path: Path | str | None = None) -> int:
        csv_path = Path(path) if path else DEFAULT_DEPARA_CSV
        if not csv_path.is_file():
            return 0
        count = 0
        with csv_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                cod = (row.get("cod_rm") or "").strip().upper()
                if not cod:
                    continue
                orgao_raw = (row.get("sinapse_orgao_id") or "").strip()
                orgao_id = int(orgao_raw) if orgao_raw.isdigit() else None
                ativo_raw = (row.get("ativo") or "true").strip().lower()
                ativo = ativo_raw in ("1", "true", "sim", "yes")
                DeParaRmSinapse.objects.update_or_create(
                    cod_rm=cod,
                    defaults={
                        "sinapse_orgao_id": orgao_id,
                        "observacao": (row.get("observacao") or "")[:255],
                        "ativo": ativo,
                    },
                )
                count += 1
        return count

    def _mapa_depara(self) -> dict[str, DeParaRmSinapse]:
        return {d.cod_rm: d for d in DeParaRmSinapse.objects.all()}

    def _ler_planilha(self, path: Path) -> list[dict[str, Any]]:
        import openpyxl

        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        rows: list[dict[str, Any]] = []
        for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            if not row or all(c is None for c in row):
                continue
            orgao, id_unidade, sigla, nome, email = (row + (None,) * 5)[:5]
            if id_unidade is None:
                continue
            try:
                uid = int(id_unidade)
            except (TypeError, ValueError):
                continue
            rows.append(
                {
                    "linha": idx,
                    "orgao_rm": str(orgao or "").strip(),
                    "sinapse_unidade_id": uid,
                    "sigla_completa": str(sigla or "").strip().upper(),
                    "nome": str(nome or "").strip()[:200],
                    "email": str(email or "").strip()[:254],
                }
            )
        return rows

    def _resolver_sigla_unica(
        self,
        sinapse_orgao_id: int,
        sigla_completa: str,
        sinapse_unidade_id: int,
        *,
        excluir_pk: int | None = None,
    ) -> str:
        candidatos: list[str] = []
        for base in (
            sigla_para_importacao(sigla_completa, sinapse_unidade_id),
            extrair_sigla_curta(sigla_completa),
        ):
            sigla = (base or "").strip().upper()[:32]
            if sigla and sigla not in candidatos:
                candidatos.append(sigla)
            if sigla and len(sigla) <= 24:
                com_sufixo = f"{sigla}-{sinapse_unidade_id}"[:32]
                if com_sufixo not in candidatos:
                    candidatos.append(com_sufixo)
        candidatos.append(f"U{sinapse_unidade_id}"[:32])

        for sigla in candidatos:
            if not sigla:
                continue
            qs = UnidadeAdministrativa.objects.filter(
                sinapse_orgao_id=int(sinapse_orgao_id),
                sigla=sigla,
            )
            if excluir_pk:
                qs = qs.exclude(pk=excluir_pk)
            if not qs.exists():
                return sigla
        return f"U{sinapse_unidade_id}"[:32]

    def importar(
        self,
        *,
        xlsx_path: Path | str | None = None,
        dry_run: bool = False,
        carregar_csv: bool = True,
    ) -> ImportRmResultado:
        resultado = ImportRmResultado()
        xlsx = Path(xlsx_path) if xlsx_path else DEFAULT_XLSX
        if not xlsx.is_file():
            resultado.erros.append(f"Planilha não encontrada: {xlsx}")
            return resultado

        if carregar_csv:
            self.carregar_depara_csv()

        depara = self._mapa_depara()
        linhas = self._ler_planilha(xlsx)
        resultado.total_linhas = len(linhas)

        for item in linhas:
            cod = extrair_cod_rm(item["sigla_completa"])
            if not cod:
                resultado.erros.append(
                    f"Linha {item['linha']}: sigla inválida «{item['sigla_completa']}»."
                )
                continue

            mapping = depara.get(cod)
            if not mapping or not mapping.ativo or not mapping.sinapse_orgao_id:
                resultado.ignoradas_orfaos += 1
                resultado.orfaos_por_cod[cod] = resultado.orfaos_por_cod.get(cod, 0) + 1
                continue

            sigla_curta = extrair_sigla_curta(item["sigla_completa"])
            orgao_id = int(mapping.sinapse_orgao_id)
            existente = UnidadeAdministrativa.objects.filter(
                sinapse_unidade_id=item["sinapse_unidade_id"]
            ).first()
            sigla = self._resolver_sigla_unica(
                orgao_id,
                item["sigla_completa"],
                item["sinapse_unidade_id"],
                excluir_pk=existente.pk if existente else None,
            )
            defaults = {
                "sinapse_orgao_id": orgao_id,
                "nome": item["nome"] or sigla_curta or f"Unidade {item['sinapse_unidade_id']}",
                "sigla": sigla,
                "email_contato": item["email"],
                "cod_rm_orgao": cod,
                "ativo": True,
            }

            if dry_run:
                if existente:
                    resultado.atualizadas += 1
                else:
                    resultado.importadas += 1
                continue

            try:
                obj, created = UnidadeAdministrativa.objects.update_or_create(
                    sinapse_unidade_id=item["sinapse_unidade_id"],
                    defaults=defaults,
                )
            except Exception as exc:
                resultado.erros.append(
                    f"Linha {item['linha']} (ID {item['sinapse_unidade_id']}): {exc}"
                )
                continue
            if created:
                resultado.importadas += 1
            else:
                resultado.atualizadas += 1

        logger.info(
            "Importação RM271698 concluída dry_run=%s: %s",
            dry_run,
            resultado.to_dict(),
        )
        return resultado
