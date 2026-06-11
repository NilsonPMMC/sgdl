"""
Limpa dados do SGDL para homologação / recomeço.

Uso:
  python manage.py limpar_banco              # pede confirmação
  python manage.py limpar_banco --noinput  # sem prompt (CI/scripts)
  python manage.py limpar_banco --noinput --modo completo   # flush total (inclui usuários)
  python manage.py limpar_banco --noinput --modo operacional  # mantém usuários, secretarias e serviços
"""

from __future__ import annotations

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Remove dados do banco (operacional ou completo via flush)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--noinput",
            action="store_true",
            help="Não pede confirmação interativa.",
        )
        parser.add_argument(
            "--modo",
            choices=("operacional", "completo"),
            default="operacional",
            help=(
                "operacional: demandas, copiloto, notificações, integração Sinapse local; "
                "completo: flush de todas as tabelas Django."
            ),
        )

    def handle(self, *args, **options):
        modo = options["modo"]
        if not options["noinput"]:
            self.stdout.write(
                self.style.WARNING(
                    f"ATENÇÃO: modo={modo}. Todos os dados listados serão apagados."
                )
            )
            if input("Digite LIMPAR para confirmar: ").strip() != "LIMPAR":
                raise CommandError("Operação cancelada.")

        if modo == "completo":
            self._flush_completo()
            return

        self._limpar_operacional()
        self.stdout.write(self.style.SUCCESS("Limpeza operacional concluída."))

    def _flush_completo(self) -> None:
        self.stdout.write("Executando flush completo (todas as tabelas Django)...")
        call_command("flush", "--noinput")
        self.stdout.write(
            self.style.SUCCESS(
                "Banco zerado. Crie um superusuário: python manage.py createsuperuser"
            )
        )

    @transaction.atomic
    def _limpar_operacional(self) -> None:
        """Apaga dados de negócio; preserva usuários, secretarias e catálogo de serviços locais."""
        from integrations.models import SinapseServiceSync, SinapseServicoMap

        from core.models import (
            Anexo,
            AnexoTramitacao,
            ChatSession,
            ClusterExecucao,
            Demanda,
            Notificacao,
            Tramitacao,
        )

        contagens: list[tuple[str, int]] = []

        def _del(label: str, qs) -> None:
            n, _ = qs.delete()
            contagens.append((label, n))

        _del("AnexoTramitacao", AnexoTramitacao.objects.all())
        _del("Anexo", Anexo.objects.all())
        _del("Tramitacao", Tramitacao.objects.all())
        _del("Notificacao", Notificacao.objects.all())
        _del("Demanda", Demanda.objects.all())
        _del("ChatSession", ChatSession.objects.all())
        _del("ClusterExecucao", ClusterExecucao.objects.all())
        _del("SinapseServicoMap", SinapseServicoMap.objects.all())
        _del("SinapseServiceSync", SinapseServiceSync.objects.all())

        for label, n in contagens:
            self.stdout.write(f"  {label}: {n} registro(s) removido(s)")

        self.stdout.write(
            "Preservados: Usuario (catálogo Sinapse é read-only). "
            "Sincronize a carta Sinapse depois: python manage.py sync_sinapse_services"
        )
