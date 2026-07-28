"""
Repara nó operacional scatter-gather criado sem setor (unidade administrativa).

Atualiza o nó, a tramitação de abertura e o metadata do evento.

Uso:
  python manage.py reparar_no_sem_setor --listar --demanda-id 3420
  python manage.py reparar_no_sem_setor --no-id 338 --unidade-id 1451 --dry-run
  python manage.py reparar_no_sem_setor --tramitacao-id 1105 --unidade-id 1451
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Tramitacao
from core.models_no_operacional import NoOperacional, StatusNoOperacional
from core.models_unidade_administrativa import UnidadeAdministrativa
from core.services.scatter_gather_service import NoOperacionalService


class Command(BaseCommand):
    help = "Vincula setor (UA) a nó operacional aberto criado sem unidade administrativa."

    def add_arguments(self, parser):
        parser.add_argument("--no-id", type=int, default=None, help="ID do nó operacional.")
        parser.add_argument(
            "--tramitacao-id",
            type=int,
            default=None,
            help="ID da tramitação de encaminhamento (abertura do nó).",
        )
        parser.add_argument(
            "--unidade-id",
            type=int,
            default=None,
            help="ID da unidade administrativa (setor) a vincular.",
        )
        parser.add_argument(
            "--demanda-id",
            type=int,
            default=None,
            help="Com --listar, filtra nós da demanda.",
        )
        parser.add_argument(
            "--listar",
            action="store_true",
            help="Lista nós abertos sem setor (candidatos a reparo).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simula sem gravar alterações.",
        )

    def handle(self, *args, **options):
        if options["listar"]:
            self._listar(options["demanda_id"])
            return

        no = self._resolver_no(options["no_id"], options["tramitacao_id"])
        unidade_id = options["unidade_id"]
        if not unidade_id:
            raise CommandError("Informe --unidade-id com o setor correto.")

        unidade = UnidadeAdministrativa.objects.filter(pk=unidade_id, ativo=True).first()
        if not unidade:
            raise CommandError(f"Unidade administrativa #{unidade_id} não encontrada ou inativa.")

        if int(unidade.sinapse_orgao_id) != int(no.sinapse_orgao_id):
            raise CommandError(
                f"Setor #{unidade_id} ({unidade.sigla}) pertence ao órgão "
                f"{unidade.sinapse_orgao_id}, mas o nó #{no.pk} é do órgão {no.sinapse_orgao_id}."
            )

        if no.unidade_administrativa_id == unidade.pk:
            self.stdout.write(self.style.WARNING(f"Nó #{no.pk} já está vinculado ao setor #{unidade.pk}."))
            return

        if no.status != StatusNoOperacional.ABERTO:
            raise CommandError(f"Nó #{no.pk} não está aberto (status={no.status}).")

        tram = no.abertura_tramitacao
        rotulo = f"{unidade.sigla} — {unidade.nome}" if unidade.sigla else unidade.nome
        self.stdout.write(
            f"Reparo: nó #{no.pk} demanda #{no.demanda_id} órgão {no.sinapse_orgao_id} "
            f"→ setor #{unidade.pk} ({rotulo})"
        )
        if tram:
            self.stdout.write(f"  tramitação abertura #{tram.pk} ({tram.tipo})")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry-run — nenhuma alteração gravada."))
            return

        with transaction.atomic():
            no.unidade_administrativa = unidade
            no.save(update_fields=["unidade_administrativa"])

            if tram:
                meta = tram.metadata if isinstance(tram.metadata, dict) else {}
                meta["setor_id"] = int(unidade.pk)
                meta["setor_nome"] = rotulo
                meta["reparo_sem_setor"] = True
                tram.metadata = meta
                tram.save(update_fields=["metadata"])

        self.stdout.write(self.style.SUCCESS(f"Nó #{no.pk} reparado com setor #{unidade.pk}."))

    def _listar(self, demanda_id: int | None) -> None:
        qs = NoOperacional.objects.filter(
            status=StatusNoOperacional.ABERTO,
            unidade_administrativa_id__isnull=True,
        ).order_by("demanda_id", "pk")
        if demanda_id:
            qs = qs.filter(demanda_id=demanda_id)

        if not qs.exists():
            self.stdout.write("Nenhum nó aberto sem setor encontrado.")
            return

        svc = NoOperacionalService()
        for no in qs.select_related("demanda", "abertura_tramitacao"):
            orgao = int(no.sinapse_orgao_id)
            uas = UnidadeAdministrativa.objects.filter(sinapse_orgao_id=orgao, ativo=True).order_by(
                "nome"
            )[:12]
            self.stdout.write(
                f"\nNó #{no.pk} | demanda #{no.demanda_id} | órgão {orgao} | "
                f"tram abertura #{no.abertura_tramitacao_id or '—'}"
            )
            if uas:
                self.stdout.write("  Setores disponíveis (amostra):")
                for ua in uas:
                    self.stdout.write(f"    {ua.pk}: {ua.sigla} — {ua.nome}")
            else:
                self.stdout.write("  (sem UAs ativas cadastradas para o órgão)")

    def _resolver_no(self, no_id: int | None, tramitacao_id: int | None) -> NoOperacional:
        if no_id:
            no = NoOperacional.objects.filter(pk=no_id).first()
            if not no:
                raise CommandError(f"Nó operacional #{no_id} não encontrado.")
            return no
        if tramitacao_id:
            no = NoOperacional.objects.filter(abertura_tramitacao_id=tramitacao_id).first()
            if not no:
                raise CommandError(
                    f"Nenhum nó encontrado com abertura_tramitacao_id={tramitacao_id}."
                )
            return no
        raise CommandError("Informe --no-id ou --tramitacao-id.")
