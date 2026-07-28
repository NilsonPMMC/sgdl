"""
Repara Super OS quando o protocolo foi registrado fora da primeira demanda do cluster.

Integra seguidoras órfãs ao líder operacional (demanda protocolada), corrige
unidade_destino em tramitações scatter e reexecuta reparo de nós operacionais.

Uso:
  python manage.py reparar_cluster_super_os --dry-run
  python manage.py reparar_cluster_super_os
  python manage.py reparar_cluster_super_os --cluster-id 68
  python manage.py reparar_cluster_super_os --demanda-id 3415
  python manage.py reparar_cluster_super_os --username prot_homolog
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from core.models import Demanda
from core.services.cluster_reparo_service import (
    _usuario_reparo,
    clusters_candidatos_reparo,
    clusters_super_os_com_protocolo,
    diagnosticar_cluster,
    reparar_cluster_super_os,
    reparar_clusters_super_os,
)


class Command(BaseCommand):
    help = (
        "Repara clusters Super OS: integra demandas sem protocolo ao líder operacional "
        "e corrige tramitações scatter-gather sem unidade de destino."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simula o reparo sem gravar alterações.",
        )
        parser.add_argument(
            "--cluster-id",
            type=int,
            default=None,
            help="Repara apenas o cluster informado.",
        )
        parser.add_argument(
            "--demanda-id",
            type=int,
            default=None,
            help="Resolve o cluster a partir da demanda informada.",
        )
        parser.add_argument(
            "--username",
            type=str,
            default=None,
            help="Usuário responsável pela integração (default: primeiro perfil Protocolo).",
        )
        parser.add_argument(
            "--listar",
            action="store_true",
            help="Lista clusters candidatos a reparo e sai.",
        )
        parser.add_argument(
            "--listar-todos",
            action="store_true",
            help="Diagnóstico de todos os clusters Super OS com protocolo (inclui OK).",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        cluster_id: int | None = options["cluster_id"]
        demanda_id: int | None = options["demanda_id"]
        username: str | None = options["username"]
        listar: bool = options["listar"]
        listar_todos: bool = options["listar_todos"]

        if demanda_id is not None:
            demanda = Demanda.objects.filter(pk=demanda_id).only("cluster_id").first()
            if not demanda or not demanda.cluster_id:
                self.stdout.write(
                    self.style.ERROR(f"Demanda #{demanda_id} sem cluster vinculado.")
                )
                return
            cluster_id = int(demanda.cluster_id)

        if listar_todos and cluster_id is None:
            clusters = clusters_super_os_com_protocolo()
            if not clusters:
                self.stdout.write(
                    self.style.SUCCESS("Nenhum cluster Super OS com demanda protocolada.")
                )
                return
            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    f"Diagnóstico de {len(clusters)} cluster(s) Super OS:"
                )
            )
            for cid in clusters:
                self._imprimir_diagnostico(diagnosticar_cluster(cid))
            return

        if listar and cluster_id is None:
            candidatos = clusters_candidatos_reparo()
            if not candidatos:
                self.stdout.write(self.style.SUCCESS("Nenhum cluster candidato a reparo."))
                self.stdout.write(
                    "Use --listar-todos para ver todos os Super OS ou "
                    "--cluster-id 68 --listar para um cluster específico."
                )
                return
            self.stdout.write(self.style.MIGRATE_HEADING("Clusters candidatos:"))
            for cid in candidatos:
                diag = diagnosticar_cluster(cid)
                self._imprimir_diagnostico(diag)
            return

        usuario = _usuario_reparo(username)
        if not usuario and not dry_run and not listar:
            self.stdout.write(
                self.style.ERROR(
                    "Nenhum usuário Protocolo ativo. Informe --username ou crie um usuário PROTOCOLO."
                )
            )
            return

        if cluster_id is not None:
            diag = diagnosticar_cluster(int(cluster_id))
            self.stdout.write(self.style.MIGRATE_HEADING(f"Cluster #{cluster_id}"))
            self._imprimir_diagnostico(diag)
            if listar:
                return
            resultados = [
                reparar_cluster_super_os(
                    int(cluster_id), usuario=usuario, dry_run=dry_run
                )
            ]
        else:
            candidatos = clusters_candidatos_reparo()
            if not candidatos:
                self.stdout.write(
                    self.style.SUCCESS("Nenhum cluster Super OS precisa de reparo.")
                )
                return
            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    f"Reparando {len(candidatos)} cluster(s) candidato(s)…"
                )
            )
            resultados = reparar_clusters_super_os(
                cluster_ids=candidatos, usuario=usuario, dry_run=dry_run
            )

        integradas_total = 0
        trams_total = 0
        pernas_total = 0
        for res in resultados:
            if res.get("erro"):
                self.stdout.write(self.style.ERROR(f"  Erro cluster {res['cluster_id']}: {res['erro']}"))
                continue
            integradas = res.get("integradas") or []
            trams = int(res.get("tramitacoes_corrigidas") or 0)
            pernas = int(res.get("pernas_sincronizadas") or 0)
            integradas_total += len(integradas)
            trams_total += trams
            pernas_total += pernas
            prefixo = "[dry-run] " if dry_run else ""
            if res.get("motivo_skip"):
                self.stdout.write(
                    self.style.WARNING(
                        f"  Cluster {res['cluster_id']}: {res['motivo_skip']}"
                    )
                )
            self.stdout.write(
                self.style.SUCCESS(
                    f"  {prefixo}Cluster {res['cluster_id']}: "
                    f"líder operacional #{res.get('lider_operacional_id')} | "
                    f"integradas {integradas or '—'} | "
                    f"trams scatter corrigidas {trams} | "
                    f"pernas obsoletas {pernas}"
                )
            )

        prefixo = "[dry-run] " if dry_run else ""
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefixo}Concluído: {integradas_total} demanda(s) integrada(s), "
                f"{trams_total} tramitação(ões) corrigida(s), "
                f"{pernas_total} perna(s) sincronizada(s)."
            )
        )

    def _imprimir_diagnostico(self, diag: dict) -> None:
        cid = diag.get("cluster_id")
        if diag.get("tipo") == "multi_destino":
            self.stdout.write(f"  #{cid} — multi-órgão (ignorado)")
            return
        if not diag.get("reparavel"):
            motivo = diag.get("motivo") or "nada pendente"
            extras = []
            if diag.get("lider_divergente"):
                extras.append(
                    f"líder legado #{diag.get('lider_legado_id')} "
                    f"≠ operacional #{diag.get('lider_operacional_id')}"
                )
            if diag.get("protocolo_fora_primeira"):
                extras.append("protocolo fora da 1ª demanda")
            if diag.get("nos_fora_lider_legado"):
                extras.append("nós scatter fora do líder legado")
            extra_txt = f" ({'; '.join(extras)})" if extras else ""
            self.stdout.write(f"  #{cid} — OK ou sem reparo ({motivo}){extra_txt}")
            return
        legado = diag.get("lider_legado_id")
        oper = diag.get("lider_operacional_id")
        pend = diag.get("seguidoras_pendentes") or []
        trams = diag.get("tramitacoes_scatter_sem_unidade") or 0
        self.stdout.write(
            self.style.WARNING(
                f"  #{cid} — líder legado #{legado} → operacional #{oper} | "
                f"seguidoras pendentes {pend} | trams sem setor {trams} | "
                f"protocolo {diag.get('protocolo_executivo') or '—'}"
            )
        )
