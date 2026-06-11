from django.core.management.base import BaseCommand

from core.models import Usuario
from core.services.usuario_vinculo_service import UsuarioVinculoService


class Command(BaseCommand):
    help = (
        "Aplica vínculo institucional U2 em usuários PROTOCOLO "
        "(sinapse_orgao_id=12 + responsável UA SGAC)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Lista usuários afetados sem alterar o banco.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        service = UsuarioVinculoService()
        usuarios = list(
            Usuario.objects.filter(perfil="PROTOCOLO").order_by("pk")
        )

        if not usuarios:
            self.stdout.write(self.style.WARNING("Nenhum usuário PROTOCOLO encontrado."))
            return

        if dry_run:
            ua = service.resolver_unidade_protocolo()
            self.stdout.write(
                f"[dry-run] {len(usuarios)} usuário(s) PROTOCOLO; "
                f"UA SGAC: {ua.pk if ua else 'NÃO ENCONTRADA'}"
            )
            for u in usuarios:
                self.stdout.write(
                    f"  - {u.username} (pk={u.pk}) orgao_atual={u.sinapse_orgao_id}"
                )
            return

        resultados = service.sincronizar_todos_protocolo()
        orgao_ok = sum(1 for r in resultados if not r["orgao_atualizado"])
        resp_novos = sum(1 for r in resultados if r["responsavel_criado"])
        sem_ua = sum(1 for r in resultados if not r["unidade_encontrada"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Vínculo aplicado em {len(resultados)} usuário(s) PROTOCOLO."
            )
        )
        self.stdout.write(f"  Já com órgão 12: {orgao_ok + sum(1 for r in resultados if r['orgao_atualizado'])}")
        self.stdout.write(f"  Órgão atualizado agora: {sum(1 for r in resultados if r['orgao_atualizado'])}")
        self.stdout.write(f"  Responsáveis SGAC criados: {resp_novos}")
        if sem_ua:
            self.stdout.write(
                self.style.WARNING(f"  Sem UA SGAC no banco: {sem_ua} usuário(s)")
            )

        for r in resultados:
            self.stdout.write(
                f"  - {r['username']}: orgao_atualizado={r['orgao_atualizado']} "
                f"responsavel_novo={r['responsavel_criado']} ua={r.get('unidade_id')}"
            )
