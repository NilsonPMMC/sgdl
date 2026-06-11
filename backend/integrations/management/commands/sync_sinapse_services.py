import json
from pathlib import Path
import requests

from django.core.management.base import BaseCommand, CommandError
from django.core.mail import send_mail
from django.conf import settings

from integrations.services.sinapse_sync_service import SinapseSyncService
from integrations.sinapse_client import SinapseClientError


class Command(BaseCommand):
    help = "Sincroniza (ou simula) a Carta de Serviços a partir da base Sinapse."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Executa apenas leitura/mapeamento, sem persistir no SGDL.",
        )
        parser.add_argument(
            "--full-sync",
            action="store_true",
            help="Executa sincronizacao persistente da base Sinapse para rastreabilidade local.",
        )
        parser.add_argument(
            "--incremental-sync",
            action="store_true",
            help="Executa sincronizacao incremental usando versao `updated_at` da fonte.",
        )
        parser.add_argument(
            "--reconcile",
            action="store_true",
            help="Executa reconciliacao e marca divergencias de integridade na base local.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Quantidade máxima de registros para leitura.",
        )
        parser.add_argument(
            "--offset",
            type=int,
            default=0,
            help="Offset da leitura paginada.",
        )
        parser.add_argument(
            "--table",
            type=str,
            default=None,
            help="Tabela/fonte da carta de serviços no Sinapse (schema.tabela ou tabela).",
        )
        parser.add_argument(
            "--test-connection",
            action="store_true",
            help="Valida conexão com o banco Sinapse e encerra.",
        )
        parser.add_argument(
            "--list-candidate-tables",
            action="store_true",
            help="Lista tabelas candidatas com nomes relacionados a serviço/carta.",
        )
        parser.add_argument(
            "--list-unmatched",
            action="store_true",
            help="Lista pendencias de mapeamento Sinapse sem correspondencia local.",
        )
        parser.add_argument(
            "--bind-manual",
            action="store_true",
            help="Vincula manualmente um sinapse_service_id a um servico local.",
        )
        parser.add_argument(
            "--sinapse-id",
            type=str,
            default=None,
            help="ID do servico no catalogo Sinapse para vinculacao manual.",
        )
        parser.add_argument(
            "--servico-id",
            type=int,
            default=None,
            help="ID do Servico local no SGDL para vinculacao manual.",
        )
        parser.add_argument(
            "--actor",
            type=str,
            default=None,
            help="Identificador do responsavel pela vinculacao manual (auditoria).",
        )
        parser.add_argument(
            "--sync-health-report",
            action="store_true",
            help="Gera relatorio de saude do sync e nivel de alerta operacional.",
        )
        parser.add_argument(
            "--notify-alert-email",
            action="store_true",
            help="Quando houver ALERT em --sync-health-report, envia e-mail para destinatarios configurados.",
        )
        parser.add_argument(
            "--generate-scheduler-artifacts",
            action="store_true",
            help="Gera templates de cron e systemd para operacao de sync.",
        )
        parser.add_argument(
            "--notify-alert-webhook",
            action="store_true",
            help="Quando houver ALERT em --sync-health-report, envia payload para webhook institucional.",
        )

    def handle(self, *args, **options):
        try:
            service = SinapseSyncService(table_name=options.get("table"))

            if options["test_connection"]:
                ok = service.test_connection()
                if not ok:
                    raise CommandError("Conexão Sinapse não validada.")
                self.stdout.write(self.style.SUCCESS("Conexão Sinapse OK."))
                return

            if options["list_candidate_tables"]:
                candidates = service.list_candidate_tables()
                if not candidates:
                    self.stdout.write("Nenhuma tabela candidata encontrada.")
                    return
                self.stdout.write(json.dumps(candidates, indent=2, ensure_ascii=False))
                return

            if options["list_unmatched"]:
                data = service.list_unmatched(limit=options["limit"])
                self.stdout.write(json.dumps(data, indent=2, ensure_ascii=False, default=str))
                self.stdout.write(self.style.SUCCESS("Listagem de mapeamentos UNMATCHED finalizada."))
                return

            if options["bind_manual"]:
                sinapse_id = options.get("sinapse_id")
                servico_id = options.get("servico_id")
                if not sinapse_id or not servico_id:
                    raise CommandError("Para --bind-manual, informe --sinapse-id e --servico-id.")
                result = service.bind_manual_mapping(
                    sinapse_service_id=sinapse_id,
                    servico_local_id=servico_id,
                    actor=options.get("actor"),
                )
                self.stdout.write(json.dumps(result, indent=2, ensure_ascii=False, default=str))
                self.stdout.write(self.style.SUCCESS("Vinculacao manual finalizada."))
                return

            if options["sync_health_report"]:
                report = service.sync_health_report()
                self.stdout.write(json.dumps(report, indent=2, ensure_ascii=False, default=str))
                if report["alert_level"] == "ALERT":
                    self.stdout.write(self.style.WARNING("Relatorio de saude com ALERTA."))
                    if options["notify_alert_email"]:
                        recipients = getattr(settings, "SINAPSE_ALERT_EMAIL_RECIPIENTS", [])
                        if recipients:
                            subject = "[SGDL][ALERTA] Saude da sincronizacao Sinapse"
                            body = json.dumps(report, indent=2, ensure_ascii=False, default=str)
                            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=False)
                            self.stdout.write(self.style.SUCCESS(f"Alerta enviado por e-mail para: {', '.join(recipients)}"))
                        else:
                            self.stdout.write(self.style.WARNING("SINAPSE_ALERT_EMAIL_RECIPIENTS nao configurado."))
                    if options["notify_alert_webhook"]:
                        webhook_url = getattr(settings, "SINAPSE_ALERT_WEBHOOK_URL", "")
                        if webhook_url:
                            payload = {
                                "source": "sgdl",
                                "event": "sinapse_sync_alert",
                                "report": report,
                            }
                            timeout = int(getattr(settings, "SINAPSE_ALERT_WEBHOOK_TIMEOUT", 10))
                            resp = requests.post(webhook_url, json=payload, timeout=timeout)
                            resp.raise_for_status()
                            self.stdout.write(self.style.SUCCESS("Alerta enviado para webhook institucional."))
                        else:
                            self.stdout.write(self.style.WARNING("SINAPSE_ALERT_WEBHOOK_URL nao configurado."))
                else:
                    self.stdout.write(self.style.SUCCESS("Relatorio de saude OK."))
                return

            if options["generate_scheduler_artifacts"]:
                artifacts_dir = Path(settings.BASE_DIR).parent / "docs" / "ops"
                artifacts_dir.mkdir(parents=True, exist_ok=True)

                cron_template = artifacts_dir / "sinapse-sync.cron.example"
                cron_template.write_text(
                    "\n".join(
                        [
                            "# Incremental diario (08:00)",
                            "0 8 * * * cd /var/www/sgdl/backend && /usr/bin/python manage.py sync_sinapse_services --incremental-sync --table public.catalog_servico --limit 200",
                            "",
                            "# Full semanal (segunda 07:00)",
                            "0 7 * * 1 cd /var/www/sgdl/backend && /usr/bin/python manage.py sync_sinapse_services --full-sync --table public.catalog_servico --limit 200",
                            "",
                            "# Health report diario com e-mail (08:10)",
                            "10 8 * * * cd /var/www/sgdl/backend && /usr/bin/python manage.py sync_sinapse_services --sync-health-report --notify-alert-email --notify-alert-webhook",
                            "",
                        ]
                    ),
                    encoding="utf-8",
                )

                systemd_template = artifacts_dir / "sinapse-sync.service.example"
                systemd_template.write_text(
                    "\n".join(
                        [
                            "[Unit]",
                            "Description=SGDL Sinapse Sync Job",
                            "",
                            "[Service]",
                            "Type=oneshot",
                            "WorkingDirectory=/var/www/sgdl/backend",
                            "ExecStart=/usr/bin/python manage.py sync_sinapse_services --incremental-sync --table public.catalog_servico --limit 200",
                            "User=www-data",
                            "",
                            "[Install]",
                            "WantedBy=multi-user.target",
                            "",
                        ]
                    ),
                    encoding="utf-8",
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        json.dumps(
                            {
                                "cron_template": str(cron_template),
                                "systemd_template": str(systemd_template),
                            },
                            ensure_ascii=False,
                        )
                    )
                )
                return

            sync_modes = [
                options["dry_run"],
                options["full_sync"],
                options["incremental_sync"],
                options["reconcile"],
                options["list_unmatched"],
                options["bind_manual"],
                options["sync_health_report"],
                options["generate_scheduler_artifacts"],
            ]
            if sum(1 for mode in sync_modes if mode) > 1:
                raise CommandError(
                    "Use apenas um modo por execucao: --dry-run, --full-sync, --incremental-sync, --reconcile, --list-unmatched, --bind-manual, --sync-health-report ou --generate-scheduler-artifacts."
                )

            if options["full_sync"]:
                summary = service.full_sync(batch_size=options["limit"])
                self.stdout.write(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
                self.stdout.write(self.style.SUCCESS("Full-sync Sinapse finalizado."))
                return

            if options["incremental_sync"]:
                summary = service.incremental_sync(batch_size=options["limit"])
                self.stdout.write(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
                self.stdout.write(self.style.SUCCESS("Incremental-sync Sinapse finalizado."))
                return

            if options["reconcile"]:
                summary = service.reconcile(batch_size=options["limit"])
                self.stdout.write(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
                self.stdout.write(self.style.SUCCESS("Reconcile Sinapse finalizado."))
                return

            if not options["dry_run"]:
                raise CommandError(
                    "Use --dry-run, --full-sync, --incremental-sync, --reconcile, --list-unmatched, --bind-manual, --sync-health-report ou --generate-scheduler-artifacts."
                )

            summary = service.dry_run(limit=options["limit"], offset=options["offset"])
            self.stdout.write(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
            self.stdout.write(self.style.SUCCESS("Dry-run Sinapse finalizado."))

        except SinapseClientError as exc:
            raise CommandError(str(exc)) from exc
