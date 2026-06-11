"""Clusterização espacial + semântica de demandas (Super Ordem de Serviço)."""

from __future__ import annotations

import logging
import math
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Min, QuerySet
from django.utils import timezone

from core.models import ClusterExecucao, Demanda, Tramitacao
from core.services.triagem_service import cosine_similarity
from integrations import sinapse_catalog

logger = logging.getLogger(__name__)

CLUSTER_STATUS_ABERTOS = ("ABERTO", "EM_ANDAMENTO")
CLUSTER_STATUS_RESOLVIDO = "RESOLVIDO"

CLUSTER_MIN_DEMANDAS = 2

DEMANDA_STATUS_ELEGIVEIS = frozenset(
    {
        "AGUARDANDO_PROTOCOLO",
        "PROTOCOLADO",
        "EM_EXECUCAO",
        "AGUARDANDO_TRANSFERENCIA",
    }
)

DEMANDA_STATUS_CLUSTERIZAVEL = frozenset({"AGUARDANDO_PROTOCOLO"})

# Status em que uma demanda solta ainda pode formar par (inclui protocoladas sem cluster).
DEMANDA_STATUS_PAR_FORMACAO = frozenset(
    {
        "AGUARDANDO_PROTOCOLO",
        "PROTOCOLADO",
        "EM_EXECUCAO",
        "AGUARDANDO_TRANSFERENCIA",
    }
)

DEMANDA_STATUS_ENCERRADOS = frozenset({"FINALIZADO", "CANCELADO"})

STATUS_ORDEM_GRUPO: dict[str, int] = {
    "AGUARDANDO_PROTOCOLO": 1,
    "PROTOCOLADO": 2,
    "EM_EXECUCAO": 3,
    "AGUARDANDO_TRANSFERENCIA": 4,
    "AGUARDANDO_DEVOLUTIVA_PROTOCOLO": 4,
    "DEVOLVIDO_VEREADOR": 5,
    "FINALIZADO": 6,
    "CANCELADO": 6,
}


def embedding_presente(embedding: Any) -> bool:
    """True se há vetor pgvector/lista — evita `if embedding` em arrays numpy."""
    if embedding is None:
        return False
    try:
        return len(embedding) > 0
    except TypeError:
        return bool(embedding)


def _embedding_list(vetor: Any) -> list[float]:
    if not embedding_presente(vetor):
        return []
    return [float(x) for x in vetor]


def _media_embeddings(vetores: list[list[float]]) -> list[float]:
    if not vetores:
        return []
    dim = len(vetores[0])
    acc = [0.0] * dim
    for vetor in vetores:
        if len(vetor) != dim:
            continue
        for i, val in enumerate(vetor):
            acc[i] += val
    n = len(vetores)
    return [x / n for x in acc]


def haversine_metros(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Distância em metros entre dois pontos WGS84."""
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


class ClusterService:
    """Agrupa demandas do **mesmo serviço** no mesmo entorno geográfico (~300 m)."""

    def __init__(self) -> None:
        self.enabled = bool(getattr(settings, "CLUSTER_ENABLED", True))
        self.semantic_threshold = float(
            getattr(settings, "CLUSTER_SEMANTIC_THRESHOLD", 0.7)
        )
        self.radius_m = float(getattr(settings, "CLUSTER_RADIUS_METERS", 300))
        self.janela_agregacao_dias = int(
            getattr(settings, "CLUSTER_JANELA_AGREGACAO_DIAS", 90)
        )
        self.formacao_grace_minutes = int(
            getattr(settings, "CLUSTER_FORMACAO_GRACE_MINUTES", 20)
        )
        self.requer_mesmo_servico = bool(
            getattr(settings, "CLUSTER_REQUER_MESMO_SERVICO", True)
        )

    def atribuir_demanda_pk(self, demanda_pk: int) -> ClusterExecucao | None:
        try:
            demanda = Demanda.objects.select_related("cluster", "autor").get(pk=demanda_pk)
        except Demanda.DoesNotExist:
            return None
        return self.atribuir_demanda(demanda)

    def atribuir_demanda(self, demanda: Demanda) -> ClusterExecucao | None:
        if not self.enabled:
            return None
        if not _embedding_list(demanda.embedding):
            return None
        if not demanda.sinapse_servico_id:
            return None
        if demanda.status not in DEMANDA_STATUS_ELEGIVEIS:
            return None

        if demanda.cluster_id:
            self.reavaliar_fechamento_cluster(int(demanda.cluster_id))
            self._dissolver_cluster_insuficiente(int(demanda.cluster_id))
            demanda.refresh_from_db(fields=["cluster"])
            return demanda.cluster

        vetor = _embedding_list(demanda.embedding)
        cluster = self._buscar_cluster_compativel(demanda, vetor)
        if cluster is not None:
            with transaction.atomic():
                demanda.cluster = cluster
                demanda.save(update_fields=["cluster"])
                self._recalcular_centroide(cluster)
            logger.info(
                "Demanda pk=%s agrupada no cluster pk=%s (%s)",
                demanda.pk,
                cluster.pk,
                cluster.titulo[:60],
            )
            self.garantir_protocolo_super_os_cluster(cluster)
            return cluster

        par = self._buscar_demanda_solta_compativel(demanda, vetor)
        if par is None:
            return None

        with transaction.atomic():
            cluster = self._criar_cluster(demanda, vetor)
            demanda.cluster = cluster
            demanda.save(update_fields=["cluster"])
            par.cluster = cluster
            par.save(update_fields=["cluster"])
            self._recalcular_centroide(cluster)

        logger.info(
            "Demandas pk=%s e pk=%s agrupadas no novo cluster pk=%s",
            demanda.pk,
            par.pk,
            cluster.pk,
        )
        cluster = demanda.cluster
        if cluster is not None:
            self.garantir_protocolo_super_os_cluster(cluster)
        return cluster

    def deve_aguardar_par_para_demanda(self, demanda: Demanda) -> bool:
        """Evita despacho solo enquanto houver rascunho ou embedding pendente do mesmo serviço."""
        if not demanda.sinapse_servico_id:
            return False
        cutoff = timezone.now() - timedelta(minutes=max(1, self.formacao_grace_minutes))
        outros = Demanda.objects.filter(
            sinapse_servico_id=demanda.sinapse_servico_id,
            data_criacao__gte=cutoff,
        ).exclude(pk=demanda.pk)
        if outros.filter(status="RASCUNHO").exists():
            return True
        if outros.filter(
            status="AGUARDANDO_PROTOCOLO", embedding__isnull=True
        ).exists():
            return True
        return False

    def reconciliar_servico(self, sinapse_servico_id: int) -> list[int]:
        """Agrupa demandas soltas do serviço (inclui pares já protocolados)."""
        candidatas = list(
            Demanda.objects.filter(
                sinapse_servico_id=sinapse_servico_id,
                status__in=DEMANDA_STATUS_ELEGIVEIS,
                cluster__isnull=True,
            )
            .exclude(embedding__isnull=True)
            .order_by("pk")
        )
        agrupadas: list[int] = []
        clusters_tocados: set[int] = set()
        for demanda in candidatas:
            demanda.refresh_from_db(fields=["cluster_id"])
            if demanda.cluster_id:
                continue
            antes = demanda.cluster_id
            self.atribuir_demanda(demanda)
            demanda.refresh_from_db(fields=["cluster_id"])
            if demanda.cluster_id and demanda.cluster_id != antes:
                agrupadas.append(int(demanda.pk))
                clusters_tocados.add(int(demanda.cluster_id))
        for cluster_id in clusters_tocados:
            try:
                cluster = ClusterExecucao.objects.get(pk=cluster_id)
            except ClusterExecucao.DoesNotExist:
                continue
            self.garantir_protocolo_super_os_cluster(cluster)
        return agrupadas

    def garantir_protocolo_super_os_cluster(
        self, cluster: ClusterExecucao
    ) -> str | None:
        """Atribui protocolo Super OS a clusters retroativos (≥2 demandas, sem SUPER ainda)."""
        if cluster.protocolo_super_os:
            return cluster.protocolo_super_os
        membros = Demanda.objects.filter(cluster=cluster)
        if membros.count() < CLUSTER_MIN_DEMANDAS:
            return None
        from core.services.cluster_despacho_service import _proximo_protocolo_super_os

        protocolo = _proximo_protocolo_super_os()
        cluster.protocolo_super_os = protocolo
        if cluster.status == "ABERTO":
            cluster.status = "EM_ANDAMENTO"
        cluster.save(
            update_fields=["protocolo_super_os", "status", "atualizado_em"]
        )
        desc = (
            f"Agrupamento Super OS {protocolo} — demandas semanticamente compatíveis "
            f"no mesmo entorno de serviço."
        )
        for demanda in membros:
            Tramitacao.objects.create(
                demanda=demanda,
                responsavel=None,
                tipo="COMENTARIO",
                descricao=desc,
            )
        logger.info(
            "Super OS retroativa %s atribuída ao cluster pk=%s (%s demandas).",
            protocolo,
            cluster.pk,
            membros.count(),
        )
        return protocolo

    def demanda_elegivel_cluster(self, demanda: Demanda) -> dict[str, Any]:
        """Indica se a ação de cluster deve aparecer (≥2 processos, antes do protocolo)."""
        candidatos = (
            self._contar_candidatos_compatíveis(demanda)
            if demanda.sinapse_servico_id
            else 0
        )
        motivo = ""
        elegivel = False
        cluster_count = 0

        if not self.enabled:
            motivo = "cluster_desabilitado"
        elif not demanda.sinapse_servico_id:
            motivo = "sem_servico_sinapse"
        elif not embedding_presente(demanda.embedding):
            motivo = "sem_embedding"
        elif demanda.status not in DEMANDA_STATUS_CLUSTERIZAVEL:
            motivo = "apos_protocolo_ou_status_invalido"
        elif demanda.cluster_id:
            cluster_count = Demanda.objects.filter(cluster_id=demanda.cluster_id).count()
            elegivel = cluster_count >= CLUSTER_MIN_DEMANDAS
            motivo = "ok" if elegivel else "cluster_insuficiente"
        else:
            elegivel = candidatos > 0
            motivo = "ok" if elegivel else "sem_par_compativel"

        return {
            "elegivel": elegivel,
            "motivo": motivo,
            "cluster_id": demanda.cluster_id,
            "cluster_demandas_count": cluster_count,
            "candidatos_compatíveis": candidatos,
            "min_demandas": CLUSTER_MIN_DEMANDAS,
        }

    def vincular_demanda_manual(
        self,
        demanda: Demanda,
        cluster: ClusterExecucao,
        *,
        usuario,
    ) -> ClusterExecucao:
        if cluster.status == CLUSTER_STATUS_RESOLVIDO:
            raise ValueError("Cluster encerrado não aceita novas demandas.")
        if not demanda.sinapse_servico_id:
            raise ValueError("Demanda sem serviço Sinapse vinculado.")
        servico_cluster = self._servico_id_do_cluster(cluster)
        if servico_cluster and int(servico_cluster) != int(demanda.sinapse_servico_id):
            raise ValueError("Apenas demandas do mesmo serviço podem compor o cluster.")
        if demanda.cluster_id and int(demanda.cluster_id) != int(cluster.pk):
            raise ValueError("Demanda já pertence a outro cluster.")
        if not self._geo_compativel(demanda, cluster):
            raise ValueError(
                "Demanda fora do raio geográfico do cluster para este serviço."
            )

        with transaction.atomic():
            demanda.cluster = cluster
            demanda.save(update_fields=["cluster"])
            if not cluster.sinapse_servico_id:
                cluster.sinapse_servico_id = demanda.sinapse_servico_id
                cluster.save(update_fields=["sinapse_servico_id", "atualizado_em"])
            self._recalcular_centroide(cluster)
            Tramitacao.objects.create(
                demanda=demanda,
                responsavel=usuario,
                tipo="COMENTARIO",
                descricao=(
                    f"Vinculação manual ao cluster Super OS #{cluster.pk}"
                    f"{(' (' + cluster.protocolo_super_os + ')') if cluster.protocolo_super_os else ''}."
                ),
            )

        logger.info(
            "Demanda pk=%s vinculada manualmente ao cluster pk=%s por user=%s",
            demanda.pk,
            cluster.pk,
            getattr(usuario, "pk", None),
        )
        return cluster

    def desvincular_demanda_manual(self, demanda: Demanda, *, usuario) -> None:
        cluster = demanda.cluster
        if not cluster:
            raise ValueError("Demanda não está vinculada a um cluster.")

        cluster_id = int(cluster.pk)
        with transaction.atomic():
            demanda.cluster = None
            demanda.save(update_fields=["cluster"])
            Tramitacao.objects.create(
                demanda=demanda,
                responsavel=usuario,
                tipo="COMENTARIO",
                descricao=f"Desvinculação manual do cluster Super OS #{cluster_id}.",
            )
            self._reavaliar_cluster_apos_desvinculo(cluster)

        logger.info(
            "Demanda pk=%s desvinculada do cluster pk=%s por user=%s",
            demanda.pk,
            cluster_id,
            getattr(usuario, "pk", None),
        )

    def lider_cluster_pk(self, cluster_id: int) -> int | None:
        return (
            Demanda.objects.filter(cluster_id=cluster_id)
            .order_by("pk")
            .values_list("pk", flat=True)
            .first()
        )

    def grupo_super_os_ativo(self, demanda: Demanda) -> bool:
        if not demanda.cluster_id:
            return False
        return (
            Demanda.objects.filter(cluster_id=demanda.cluster_id).count()
            >= CLUSTER_MIN_DEMANDAS
        )

    def eh_lider_super_os(self, demanda: Demanda) -> bool:
        if not self.grupo_super_os_ativo(demanda):
            return True
        lider = self.lider_cluster_pk(int(demanda.cluster_id))
        return lider is not None and int(demanda.pk) == int(lider)

    def info_operacional_super_os(self, demanda: Demanda) -> dict[str, Any]:
        if not demanda.cluster_id:
            return {
                "ativo": False,
                "eh_lider": True,
                "lider_id": demanda.pk,
                "cluster_id": None,
                "protocolo_super_os": None,
                "total_vinculados": 0,
                "demandas_vinculadas": [],
                "tramitacao_apenas_lider": False,
            }

        total = Demanda.objects.filter(cluster_id=demanda.cluster_id).count()
        if total < CLUSTER_MIN_DEMANDAS:
            return {
                "ativo": False,
                "eh_lider": True,
                "lider_id": demanda.pk,
                "cluster_id": demanda.cluster_id,
                "protocolo_super_os": getattr(demanda.cluster, "protocolo_super_os", None),
                "total_vinculados": total,
                "demandas_vinculadas": [],
                "tramitacao_apenas_lider": False,
            }

        lider_pk = self.lider_cluster_pk(int(demanda.cluster_id))
        cluster = demanda.cluster
        vinculadas = []
        for d in Demanda.objects.filter(cluster_id=demanda.cluster_id).order_by("pk"):
            vinculadas.append(
                {
                    "id": d.pk,
                    "protocolo_executivo": d.protocolo_executivo,
                    "protocolo_legislativo": d.protocolo_legislativo,
                    "titulo": d.titulo,
                    "status": d.status,
                    "status_display": d.get_status_display(),
                }
            )
        return {
            "ativo": True,
            "eh_lider": int(demanda.pk) == int(lider_pk),
            "lider_id": lider_pk,
            "cluster_id": cluster.pk if cluster else demanda.cluster_id,
            "protocolo_super_os": cluster.protocolo_super_os if cluster else None,
            "total_vinculados": total,
            "demandas_vinculadas": vinculadas,
            "tramitacao_apenas_lider": True,
        }

    def filtrar_listagem_apenas_lideres(self, qs: QuerySet) -> QuerySet:
        """Oculta filhos de Super OS na listagem operacional (secretaria vê só o líder)."""
        agreg = (
            Demanda.objects.filter(cluster_id__isnull=False)
            .values("cluster_id")
            .annotate(total=Count("pk"), lider_pk=Min("pk"))
            .filter(total__gte=CLUSTER_MIN_DEMANDAS)
        )
        excluir: list[int] = []
        for row in agreg:
            excluir.extend(
                Demanda.objects.filter(cluster_id=row["cluster_id"])
                .exclude(pk=row["lider_pk"])
                .values_list("pk", flat=True)
            )
        if excluir:
            qs = qs.exclude(pk__in=excluir)
        return qs

    def exigir_lider_super_os(self, demanda: Demanda) -> None:
        """Levanta ValueError se a demanda não é a líder de um grupo Super OS ativo."""
        if self.grupo_super_os_ativo(demanda) and not self.eh_lider_super_os(demanda):
            lider = self.lider_cluster_pk(int(demanda.cluster_id))
            protocolo = ""
            if demanda.cluster and demanda.cluster.protocolo_super_os:
                protocolo = f" ({demanda.cluster.protocolo_super_os})"
            raise ValueError(
                f"Esta demanda faz parte de uma Super OS{protocolo}. "
                f"Registre andamentos apenas na demanda líder #{lider}."
            )

    def propagar_tramitacao_no_cluster(
        self, tramitacao: Tramitacao, *, usuario=None
    ) -> list[int]:
        """Replica andamento operacional do líder para as demandas vinculadas."""
        demanda = tramitacao.demanda
        if getattr(tramitacao, "_propagando_cluster_tramitacao", False):
            return []
        if not self.grupo_super_os_ativo(demanda):
            return []
        if not self.eh_lider_super_os(demanda):
            return []

        criados: list[int] = []
        prefixo = "[Super OS] "
        descricao = tramitacao.descricao or ""
        if not descricao.startswith(prefixo):
            descricao = f"{prefixo}{descricao}"

        for sib in Demanda.objects.filter(cluster_id=demanda.cluster_id).exclude(
            pk=demanda.pk
        ):
            copia = Tramitacao(
                demanda=sib,
                responsavel=usuario or tramitacao.responsavel,
                tipo=tramitacao.tipo,
                descricao=descricao,
                unidade_origem=tramitacao.unidade_origem,
                unidade_destino=tramitacao.unidade_destino,
            )
            copia._propagando_cluster_tramitacao = True  # noqa: SLF001
            copia.save()
            criados.append(int(sib.pk))

            if tramitacao.unidade_destino_id:
                update_fields = ["unidade_administrativa"]
                sib.unidade_administrativa_id = tramitacao.unidade_destino_id
                if (
                    tramitacao.unidade_destino
                    and tramitacao.unidade_destino.sinapse_orgao_id
                    and tramitacao.unidade_destino.sinapse_orgao_id != sib.sinapse_orgao_id
                ):
                    sib.sinapse_orgao_id = tramitacao.unidade_destino.sinapse_orgao_id
                    update_fields.append("sinapse_orgao_id")
                sib.save(update_fields=update_fields)

        return criados

    def propagar_status_no_cluster(self, demanda: Demanda, *, usuario=None) -> list[int]:
        """Propaga status avançado do líder para as demais demandas do grupo."""
        if getattr(demanda, "_propagando_cluster_status", False):
            return []
        if not demanda.cluster_id:
            return []
        novo_status = demanda.status
        ordem_novo = STATUS_ORDEM_GRUPO.get(novo_status)
        if ordem_novo is None:
            return []

        atualizados: list[int] = []
        agora = timezone.now()

        for sib in Demanda.objects.filter(cluster_id=demanda.cluster_id).exclude(
            pk=demanda.pk
        ):
            ordem_sib = STATUS_ORDEM_GRUPO.get(sib.status)
            if ordem_sib is not None and ordem_sib >= ordem_novo:
                continue

            sib._propagando_cluster_status = True  # noqa: SLF001
            sib.status = novo_status
            update_fields = ["status"]
            if novo_status == "FINALIZADO":
                sib.data_finalizacao = demanda.data_finalizacao or agora
                update_fields.append("data_finalizacao")
            if novo_status == "PROTOCOLADO" and demanda.data_inicio_prazo:
                sib.data_inicio_prazo = demanda.data_inicio_prazo
                update_fields.append("data_inicio_prazo")

            sib.save(update_fields=update_fields)
            Tramitacao.objects.create(
                demanda=sib,
                responsavel=usuario,
                tipo="STATUS_UPDATE",
                descricao=(
                    f"Status sincronizado com o grupo Super OS "
                    f"(demanda líder #{demanda.pk}): {novo_status}."
                ),
            )
            atualizados.append(int(sib.pk))

        if atualizados:
            self.reavaliar_fechamento_cluster(int(demanda.cluster_id))

        return atualizados

    def reavaliar_fechamento_cluster(self, cluster_id: int) -> None:
        """Marca cluster como RESOLVIDO quando todas as demandas estiverem encerradas."""
        try:
            cluster = ClusterExecucao.objects.get(pk=cluster_id)
        except ClusterExecucao.DoesNotExist:
            return

        if cluster.status == CLUSTER_STATUS_RESOLVIDO:
            return

        demandas = Demanda.objects.filter(cluster_id=cluster_id)
        if not demandas.exists():
            return

        abertas = demandas.exclude(status__in=DEMANDA_STATUS_ENCERRADOS).exists()
        if abertas:
            if cluster.status == "ABERTO":
                em_exec = demandas.filter(status="EM_EXECUCAO").exists()
                if em_exec:
                    cluster.status = "EM_ANDAMENTO"
                    cluster.save(update_fields=["status", "atualizado_em"])
            return

        cluster.status = CLUSTER_STATUS_RESOLVIDO
        cluster.save(update_fields=["status", "atualizado_em"])
        logger.info("Cluster pk=%s encerrado (todas demandas finalizadas/canceladas).", cluster_id)

    def _contar_candidatos_compatíveis(self, demanda: Demanda) -> int:
        if not demanda.sinapse_servico_id:
            return 0
        vetor = _embedding_list(demanda.embedding)
        if not vetor:
            return 0

        count = 0
        candidatos = ClusterExecucao.objects.filter(
            status__in=CLUSTER_STATUS_ABERTOS
        ).exclude(centroide__isnull=True)

        cutoff = None
        if self.janela_agregacao_dias > 0:
            cutoff = timezone.now() - timedelta(days=self.janela_agregacao_dias)

        for cluster in candidatos:
            if cutoff is not None and cluster.atualizado_em < cutoff:
                continue
            if not self._mesmo_servico(demanda, cluster):
                continue
            if not self._geo_compativel(demanda, cluster):
                continue
            centroide = _embedding_list(cluster.centroide)
            if centroide and cosine_similarity(vetor, centroide) >= self.semantic_threshold:
                count += 1

        count += self._contar_soltas_compatíveis(demanda, vetor)

        return count

    def _contar_soltas_compatíveis(
        self, demanda: Demanda, vetor: list[float]
    ) -> int:
        count = 0
        for outra in self._iter_soltas_par_formacao(demanda):
            if self._demandas_geo_compatíveis(demanda, outra):
                score = cosine_similarity(vetor, _embedding_list(outra.embedding))
                if score >= self.semantic_threshold:
                    count += 1
        return count

    def _iter_soltas_par_formacao(self, demanda: Demanda):
        return (
            Demanda.objects.filter(
                sinapse_servico_id=demanda.sinapse_servico_id,
                status__in=DEMANDA_STATUS_PAR_FORMACAO,
                cluster__isnull=True,
            )
            .exclude(pk=demanda.pk)
            .exclude(embedding__isnull=True)
        )

    def _buscar_cluster_compativel(
        self, demanda: Demanda, vetor: list[float]
    ) -> ClusterExecucao | None:
        candidatos = ClusterExecucao.objects.filter(
            status__in=CLUSTER_STATUS_ABERTOS
        ).exclude(centroide__isnull=True)

        cutoff = None
        if self.janela_agregacao_dias > 0:
            cutoff = timezone.now() - timedelta(days=self.janela_agregacao_dias)

        melhor: ClusterExecucao | None = None
        melhor_score = -1.0

        for cluster in candidatos:
            if cutoff is not None and cluster.atualizado_em < cutoff:
                continue
            if not self._mesmo_servico(demanda, cluster):
                continue
            centroide = _embedding_list(cluster.centroide)
            if not centroide:
                continue
            score = cosine_similarity(vetor, centroide)
            if score < self.semantic_threshold:
                continue
            if not self._geo_compativel(demanda, cluster):
                continue
            if score > melhor_score:
                melhor_score = score
                melhor = cluster

        return melhor

    def _mesmo_servico(self, demanda: Demanda, cluster: ClusterExecucao) -> bool:
        if not self.requer_mesmo_servico:
            return True
        sid_dem = demanda.sinapse_servico_id
        sid_cluster = self._servico_id_do_cluster(cluster)
        if not sid_dem or not sid_cluster:
            return False
        return int(sid_dem) == int(sid_cluster)

    def _servico_id_do_cluster(self, cluster: ClusterExecucao) -> int | None:
        if cluster.sinapse_servico_id:
            return int(cluster.sinapse_servico_id)
        sid = (
            Demanda.objects.filter(cluster=cluster)
            .exclude(sinapse_servico_id__isnull=True)
            .values_list("sinapse_servico_id", flat=True)
            .first()
        )
        return int(sid) if sid else None

    def _geo_compativel(self, demanda: Demanda, cluster: ClusterExecucao) -> bool:
        servico_id = demanda.sinapse_servico_id or self._servico_id_do_cluster(cluster)
        if servico_id and not sinapse_catalog.servico_requer_localizacao(int(servico_id)):
            return True

        dems_geo = (
            Demanda.objects.filter(cluster=cluster)
            .exclude(latitude__isnull=True)
            .exclude(longitude__isnull=True)
        )

        lat = demanda.latitude
        lon = demanda.longitude
        if lat is not None and lon is not None:
            lat_f, lon_f = float(lat), float(lon)
            for outra in dems_geo:
                if outra.pk == demanda.pk:
                    continue
                dist = haversine_metros(
                    lat_f,
                    lon_f,
                    float(outra.latitude),
                    float(outra.longitude),
                )
                if dist <= self.radius_m:
                    return True
            if dems_geo.exists():
                return False
            return self._mesmo_bairro(demanda.bairro, cluster.bairro_referencia)

        return self._mesmo_bairro(demanda.bairro, cluster.bairro_referencia) or not dems_geo.exists()

    def _demandas_geo_compatíveis(self, a: Demanda, b: Demanda) -> bool:
        servico_id = a.sinapse_servico_id or b.sinapse_servico_id
        if servico_id and not sinapse_catalog.servico_requer_localizacao(int(servico_id)):
            return True

        if (
            a.latitude is not None
            and a.longitude is not None
            and b.latitude is not None
            and b.longitude is not None
        ):
            dist = haversine_metros(
                float(a.latitude),
                float(a.longitude),
                float(b.latitude),
                float(b.longitude),
            )
            return dist <= self.radius_m
        return self._mesmo_bairro(a.bairro, b.bairro)

    @staticmethod
    def _mesmo_bairro(bairro_a: str | None, bairro_b: str | None) -> bool:
        a = (bairro_a or "").strip().lower()
        b = (bairro_b or "").strip().lower()
        return bool(a and b and a == b)

    def _criar_cluster(self, demanda: Demanda, vetor: list[float]) -> ClusterExecucao:
        titulo = (demanda.titulo or "Agrupamento de demandas")[:200]
        orgao_nome = ""
        if demanda.sinapse_orgao_id:
            orgao_nome = sinapse_catalog.get_orgao_nome(demanda.sinapse_orgao_id) or ""

        return ClusterExecucao.objects.create(
            titulo=titulo,
            descricao_resumo=(demanda.descricao or "")[:2000],
            status="ABERTO",
            secretaria_responsavel=(orgao_nome or "")[:150],
            bairro_referencia=(demanda.bairro or "")[:100],
            sinapse_servico_id=demanda.sinapse_servico_id,
            centroide=vetor,
        )

    def _recalcular_centroide(self, cluster: ClusterExecucao) -> None:
        vetores: list[list[float]] = []
        for emb in (
            Demanda.objects.filter(cluster=cluster)
            .exclude(embedding__isnull=True)
            .values_list("embedding", flat=True)
        ):
            lista = _embedding_list(emb)
            if lista:
                vetores.append(lista)

        if not vetores:
            return

        cluster.centroide = _media_embeddings(vetores)
        cluster.save(update_fields=["centroide", "atualizado_em"])

    def _reavaliar_cluster_apos_desvinculo(self, cluster: ClusterExecucao) -> None:
        restantes = Demanda.objects.filter(cluster=cluster).count()
        if restantes == 0:
            cluster.delete()
            return
        if restantes < CLUSTER_MIN_DEMANDAS:
            Demanda.objects.filter(cluster=cluster).update(cluster=None)
            cluster.delete()
            return
        self._recalcular_centroide(cluster)

    def _dissolver_cluster_insuficiente(self, cluster_id: int) -> None:
        try:
            cluster = ClusterExecucao.objects.get(pk=cluster_id)
        except ClusterExecucao.DoesNotExist:
            return
        if Demanda.objects.filter(cluster=cluster).count() < CLUSTER_MIN_DEMANDAS:
            Demanda.objects.filter(cluster=cluster).update(cluster=None)
            cluster.delete()

    def purgar_clusters_unitarios(self) -> int:
        """Remove clusters com menos de CLUSTER_MIN_DEMANDAS demandas (legado)."""
        removidos = 0
        for cluster in ClusterExecucao.objects.annotate(
            demandas_count=Count("demandas")
        ).filter(demandas_count__lt=CLUSTER_MIN_DEMANDAS):
            Demanda.objects.filter(cluster=cluster).update(cluster=None)
            cluster.delete()
            removidos += 1
        return removidos

    def _buscar_demanda_solta_compativel(
        self, demanda: Demanda, vetor: list[float]
    ) -> Demanda | None:
        melhor: Demanda | None = None
        melhor_score = -1.0
        for outra in self._iter_soltas_par_formacao(demanda):
            if not self._demandas_geo_compatíveis(demanda, outra):
                continue
            score = cosine_similarity(vetor, _embedding_list(outra.embedding))
            if score >= self.semantic_threshold and score > melhor_score:
                melhor_score = score
                melhor = outra
        return melhor

    def resumo_clusters_abertos(
        self,
        *,
        limit: int = 50,
        sinapse_orgao_id: int | None = None,
    ) -> list[dict[str, Any]]:
        self.purgar_clusters_unitarios()
        qs = (
            ClusterExecucao.objects.filter(status__in=CLUSTER_STATUS_ABERTOS)
            .annotate(demandas_count=Count("demandas"))
            .filter(demandas_count__gte=CLUSTER_MIN_DEMANDAS)
            .order_by("-demandas_count", "-atualizado_em")
        )
        out: list[dict[str, Any]] = []
        for c in qs:
            demandas_cluster = Demanda.objects.filter(cluster=c)
            if sinapse_orgao_id and not demandas_cluster.filter(
                sinapse_orgao_id=int(sinapse_orgao_id)
            ).exists():
                continue
            autores = demandas_cluster.values_list("autor_id", flat=True).distinct()
            pendentes = demandas_cluster.filter(status="AGUARDANDO_PROTOCOLO").count()
            lider_id = (
                demandas_cluster.order_by("pk").values_list("pk", flat=True).first()
            )
            servico_nome = None
            if c.sinapse_servico_id:
                svc = sinapse_catalog.get_servico(int(c.sinapse_servico_id))
                servico_nome = (svc.titulo or "").strip() if svc else None
            out.append(
                {
                    "id": c.id,
                    "titulo": c.titulo,
                    "status": c.status,
                    "bairro_referencia": c.bairro_referencia,
                    "secretaria_responsavel": c.secretaria_responsavel,
                    "sinapse_servico_id": c.sinapse_servico_id,
                    "servico_nome": servico_nome,
                    "protocolo_super_os": c.protocolo_super_os,
                    "demandas_count": c.demandas_count,
                    "pendentes_protocolo": pendentes,
                    "autores_distintos": len(set(autores)),
                    "lider_demanda_id": lider_id,
                    "atualizado_em": c.atualizado_em,
                }
            )
            if len(out) >= limit:
                break
        return out
