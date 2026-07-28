"""Gera rascunho do de-para serviço legado → Sinapse (curadoria Protocolo)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from django.core.management.base import BaseCommand

from core.services.corpus_legado_service import (
    corpus_legado_depara_path,
    corpus_legado_json_path,
)


class Command(BaseCommand):
    help = (
        "Gera rascunho de docs/insights/depara-legado-sinapse.json a partir do corpus legado. "
        "Revisar IDs antes de homologação — não altera triagem automaticamente."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--saida",
            type=str,
            default="",
            help="Caminho alternativo do JSON de saída",
        )
        parser.add_argument(
            "--limite",
            type=int,
            default=20,
            help="Quantidade de serviços legado no rascunho",
        )
        parser.add_argument(
            "--forcar",
            action="store_true",
            help="Sobrescreve arquivo existente",
        )

    def handle(self, *args, **options):
        from integrations import sinapse_catalog

        json_corpus = corpus_legado_json_path()
        if not json_corpus.is_file():
            self.stderr.write(
                self.style.ERROR(
                    f"Corpus não encontrado: {json_corpus}. "
                    "Execute: python manage.py analisar_corpus_legado"
                )
            )
            return

        saida = corpus_legado_depara_path()
        if options.get("saida"):
            saida = Path(options["saida"]).resolve()
        if saida.is_file() and not options.get("forcar"):
            self.stderr.write(
                self.style.WARNING(
                    f"Arquivo já existe: {saida}. Use --forcar para sobrescrever."
                )
            )
            return

        rel = json.loads(json_corpus.read_text(encoding="utf-8"))
        limite = max(1, min(int(options.get("limite") or 20), 40))
        mapeamentos: list[dict] = []

        for row in (rel.get("top_servicos") or [])[:limite]:
            serv = (row.get("servico") or "").strip()
            if not serv or serv.lower() == "outros":
                continue
            consulta = serv
            sid = sinapse_catalog.resolver_servico_por_titulo(serv)
            titulo_sinapse = None
            confianca = "baixa"
            if sid:
                catalog = sinapse_catalog.get_servico(int(sid))
                titulo_sinapse = (catalog.titulo or "").strip() if catalog else None
                confianca = "media"
            entrada: dict = {
                "servico_legado": serv,
                "consulta_sinapse": consulta,
                "confianca": confianca,
            }
            if sid:
                entrada["sinapse_servico_id"] = int(sid)
            if titulo_sinapse:
                entrada["titulo_sinapse"] = titulo_sinapse
            mapeamentos.append(entrada)

        payload = {
            "versao": 1,
            "gerado_em": datetime.now(timezone.utc).isoformat(),
            "nota": (
                "Rascunho automático — revisar com Protocolo antes de homologação. "
                "Assistivo; não substitui confirmação na carta."
            ),
            "mapeamentos": mapeamentos,
        }
        saida.parent.mkdir(parents=True, exist_ok=True)
        saida.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"✓ {len(mapeamentos)} mapeamentos → {saida}"))
