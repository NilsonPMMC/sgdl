"""Enriquece a FAQ do Copiloto via Groq (contexto Mogi das Cruzes / região)."""

import json

from django.core.management.base import BaseCommand

from core.services.copiloto_faq_enriquecimento_llm import CopilotoFaqEnriquecimentoLlmService


class Command(BaseCommand):
    help = (
        "Gera sugestões de FAQ (fora da competência municipal) com Groq e grava no banco. "
        "Requer GROQ_API_KEY. Use --dry-run para revisar o JSON antes de aplicar."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Chama o Groq e exibe o JSON sem gravar no banco.",
        )
        parser.add_argument(
            "--municipio",
            type=str,
            default="",
            help="Município de referência (padrão: ConfiguracaoOficio.municipio).",
        )
        parser.add_argument(
            "--max-novas",
            type=int,
            default=5,
            help="Máximo de entradas novas solicitadas ao modelo (padrão: 5).",
        )
        parser.add_argument(
            "--foco",
            type=str,
            default="",
            help="Instrução extra para o modelo (ex.: 'DETRAN e documentos de veículo').",
        )
        parser.add_argument(
            "--usuario",
            type=str,
            default="",
            help="Username Django para campo revisado_por (opcional).",
        )

    def handle(self, *args, **options):
        usuario = None
        username = (options.get("usuario") or "").strip()
        if username:
            from django.contrib.auth import get_user_model

            usuario = get_user_model().objects.filter(username=username).first()
            if not usuario:
                self.stderr.write(self.style.ERROR(f"Usuário não encontrado: {username}"))
                return

        municipio = (options.get("municipio") or "").strip() or None
        svc = CopilotoFaqEnriquecimentoLlmService()
        resultado = svc.executar(
            municipio=municipio,
            max_novas=max(1, min(int(options["max_novas"]), 15)),
            dry_run=bool(options["dry_run"]),
            usuario=usuario,
            foco=(options.get("foco") or "").strip() or None,
        )

        if resultado.erros:
            for e in resultado.erros:
                self.stderr.write(self.style.ERROR(e))

        if resultado.observacoes:
            self.stdout.write(self.style.NOTICE(f"Observações: {resultado.observacoes}"))

        if options["dry_run"] and resultado.sugestoes_brutas:
            self.stdout.write(
                json.dumps(resultado.sugestoes_brutas, ensure_ascii=False, indent=2)
            )
            self.stdout.write(
                self.style.WARNING("Dry-run: nenhuma alteração gravada no banco.")
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"FAQ {resultado.municipio}: "
                f"{resultado.novas_aplicadas} nova(s), "
                f"{resultado.atualizacoes_aplicadas} atualização(ões)."
            )
        )
        for ign in resultado.ignoradas:
            self.stdout.write(self.style.WARNING(f"Ignorado: {ign}"))
