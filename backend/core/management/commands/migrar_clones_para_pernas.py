"""
Migra clusters B5 legados (clones -D2) para PernaOperacional na demanda líder (P3).

Escopo: clusters multi-órgão (B5), mesmo vereador — NÃO migra Super OS multi-vereador.

Uso:
  python manage.py migrar_clones_para_pernas --dry-run
  python manage.py migrar_clones_para_pernas
  python manage.py migrar_clones_para_pernas --cluster-id 42
  python manage.py migrar_clones_para_pernas --demanda-id 3157
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import ClusterExecucao, Demanda, Tramitacao
from core.models_operacional import EventoOperacional
from core.models_perna_operacional import PernaOperacional, StatusPernaOperacional
from core.services.cluster_service import ClusterService
from core.services.perna_operacional_service import PernaOperacionalService
from integrations import sinapse_catalog


class Command(BaseCommand):
    help = "Migra desdobramentos B5 (clones multi-órgão) para pernas na demanda líder."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Somente simula — não grava pernas.",
        )
        parser.add_argument(
            "--cluster-id",
            type=int,
            default=None,
            help="Migrar apenas este cluster.",
        )
        parser.add_argument(
            "--demanda-id",
            type=int,
            default=None,
            help="Migrar cluster da demanda informada (líder ou clone).",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        cluster_id = options.get("cluster_id")
        demanda_id = options.get("demanda_id")

        if dry_run:
            self.stdout.write(self.style.WARNING("Modo dry-run — nenhuma alteração será gravada."))

        cluster_svc = ClusterService()
        perna_svc = PernaOperacionalService()

        clusters = self._clusters_alvo(cluster_svc, cluster_id=cluster_id, demanda_id=demanda_id)
        if not clusters:
            self.stdout.write("Nenhum cluster B5 legado elegível encontrado.")
            return

        total_pernas = 0
        total_clusters = 0
        total_ignorados = 0

        for cluster in clusters:
            resultado = self._migrar_cluster(
                cluster, cluster_svc, perna_svc, dry_run=dry_run
            )
            if resultado is None:
                total_ignorados += 1
                continue
            total_clusters += 1
            total_pernas += resultado["pernas"]
            self.stdout.write(
                f"Cluster #{cluster.pk}: líder #{resultado['lider_id']} — "
                f"{resultado['pernas']} perna(s), {resultado['clones']} clone(s) referenciado(s)."
            )
            for linha in resultado.get("detalhes") or []:
                self.stdout.write(f"  · {linha}")

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Resumo: {total_clusters} cluster(s) migrado(s), "
                f"{total_pernas} perna(s), {total_ignorados} ignorado(s)."
            )
        )
        if dry_run and total_clusters:
            self.stdout.write(
                self.style.WARNING("Execute sem --dry-run para aplicar.")
            )

    def _clusters_alvo(
        self,
        cluster_svc: ClusterService,
        *,
        cluster_id: int | None,
        demanda_id: int | None,
    ) -> list[ClusterExecucao]:
        if demanda_id:
            d = Demanda.objects.filter(pk=demanda_id).first()
            if not d or not d.cluster_id:
                self.stderr.write(f"Demanda #{demanda_id} sem cluster.")
                return []
            cluster_id = int(d.cluster_id)

        if cluster_id:
            c = ClusterExecucao.objects.filter(pk=cluster_id).first()
            return [c] if c else []

        ids = (
            Demanda.objects.filter(cluster_id__isnull=False)
            .values_list("cluster_id", flat=True)
            .distinct()
        )
        return list(ClusterExecucao.objects.filter(pk__in=ids).order_by("pk"))

    def _migrar_cluster(
        self,
        cluster: ClusterExecucao,
        cluster_svc: ClusterService,
        perna_svc: PernaOperacionalService,
        *,
        dry_run: bool,
    ) -> dict | None:
        cid = int(cluster.pk)
        if not cluster_svc.cluster_e_multi_destino_orgaos(cid):
            self.stdout.write(f"Cluster #{cid}: ignorado (não é multi-órgão B5).")
            return None

        demandas = list(
            Demanda.objects.filter(cluster_id=cid).order_by("pk")
        )
        if len(demandas) < 2:
            return None

        autores = {d.autor_id for d in demandas}
        if len(autores) > 1:
            self.stdout.write(
                f"Cluster #{cid}: ignorado (Super OS multi-vereador — {len(autores)} autores)."
            )
            return None

        lider = demandas[0]
        if perna_svc.demanda_usa_pernas(lider):
            self.stdout.write(
                f"Cluster #{cid}: ignorado — líder #{lider.pk} já possui pernas."
            )
            return None

        if lider.status in ("RASCUNHO", "AGUARDANDO_PROTOCOLO"):
            self.stdout.write(
                f"Cluster #{cid}: ignorado — líder #{lider.pk} ainda não protocolado."
            )
            return None

        detalhes: list[str] = []
        pernas_payload: list[dict] = []

        for idx, d in enumerate(demandas, start=1):
            orgao = d.sinapse_orgao_id
            if not orgao:
                detalhes.append(f"Demanda #{d.pk}: sem órgão — pulada.")
                continue
            uid = d.unidade_administrativa_id
            org_nome = sinapse_catalog.get_orgao_nome(orgao) or str(orgao)
            setor = d.unidade_administrativa.sigla if d.unidade_administrativa else "—"
            pernas_payload.append(
                {
                    "secretaria_id": int(orgao),
                    "unidade_administrativa_id": int(uid) if uid else None,
                    "_demanda_origem_id": d.pk,
                }
            )
            detalhes.append(
                f"Perna {idx}: {org_nome} › {setor} (origem demanda #{d.pk}"
                + (f" {d.protocolo_legislativo}" if d.protocolo_legislativo else "")
                + ")"
            )

        if not pernas_payload:
            return None

        if dry_run:
            return {
                "lider_id": lider.pk,
                "pernas": len(pernas_payload),
                "clones": len(demandas) - 1,
                "detalhes": detalhes,
            }

        with transaction.atomic():
            tram_despacho = (
                lider.tramitacoes.filter(tipo="DESPACHO").order_by("timestamp").first()
            )
            criadas = perna_svc.criar_pernas_no_despacho(
                lider,
                [
                    {
                        "secretaria_id": p["secretaria_id"],
                        "unidade_administrativa_id": p.get("unidade_administrativa_id"),
                    }
                    for p in pernas_payload
                ],
                despacho_tramitacao=tram_despacho,
            )

            for perna, src in zip(criadas, pernas_payload):
                origem_id = src.get("_demanda_origem_id")
                if not origem_id:
                    continue
                origem = next((d for d in demandas if d.pk == origem_id), None)
                if not origem:
                    continue
                tram_parcial = (
                    origem.tramitacoes.filter(tipo=EventoOperacional.CONCLUSAO_PARCIAL)
                    .order_by("-timestamp")
                    .first()
                )
                if tram_parcial:
                    perna_svc.marcar_concluida(perna, tram_parcial)
                    detalhes.append(
                        f"  → Perna #{perna.pk}: conclusão parcial herdada de #{origem_id}."
                    )
                elif origem.status == "EM_EXECUCAO" or lider.status == "EM_EXECUCAO":
                    if perna.status == StatusPernaOperacional.PENDENTE:
                        perna.status = StatusPernaOperacional.EM_EXECUCAO
                        perna.save(update_fields=["status", "atualizada_em"])

            meta = tram_despacho.metadata if tram_despacho and isinstance(tram_despacho.metadata, dict) else {}
            meta["migracao_p3"] = {
                "cluster_id": cid,
                "demandas_legadas": [d.pk for d in demandas[1:]],
            }
            if tram_despacho:
                tram_despacho.metadata = meta
                tram_despacho.save(update_fields=["metadata"])

        return {
            "lider_id": lider.pk,
            "pernas": len(pernas_payload),
            "clones": len(demandas) - 1,
            "detalhes": detalhes,
        }
