from django.core.management.base import BaseCommand

from core.models import Usuario
from core.services.usuario_vinculo_service import UsuarioVinculoService


class Command(BaseCommand):
    help = (
        "Aplica privilégios U4 em usuários GESTOR "
        "(is_staff + is_superuser; referência institucional opcional)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Lista usuários afetados sem alterar o banco.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        usuarios = list(Usuario.objects.filter(perfil="GESTOR").order_by("pk"))

        if not usuarios:
            self.stdout.write(self.style.WARNING("Nenhum usuário GESTOR encontrado."))
            return

        if dry_run:
            for u in usuarios:
                self.stdout.write(
                    f"  - {u.username} (pk={u.pk}) staff={u.is_staff} super={u.is_superuser} "
                    f"orgao={u.sinapse_orgao_id}"
                )
            return

        resultados = UsuarioVinculoService().sincronizar_todos_gestor()
        self.stdout.write(
            self.style.SUCCESS(f"Privilégios aplicados em {len(resultados)} gestor(es).")
        )
        for r in resultados:
            self.stdout.write(
                f"  - {r['username']}: admin_pleno={r['admin_pleno']} "
                f"ref_orgao={r['referencia_orgao']} ref_setores={r['referencia_unidades']}"
            )
