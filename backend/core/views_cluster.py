"""API de leitura para clusters de execução (Protocolo / Gestor)."""

from django.conf import settings
from django.db.models import Count
from django.http import Http404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ClusterExecucao, Demanda
from .serializers import ClusterExecucaoSerializer, DemandaListSerializer
from .services.cluster_despacho_service import ClusterDespachoService
from .services.cluster_service import CLUSTER_MIN_DEMANDAS, ClusterService
from .services.gestor_escopo import TIPO_SETORIAL, orgaos_escopo_gestor, tipo_gestor

_PERFIS = frozenset({"PROTOCOLO", "GESTOR"})
_PERFIS_RESUMO_SUPER_OS = frozenset({"PROTOCOLO", "GESTOR", "SECRETARIA"})


def _pode_ver_clusters(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and (getattr(user, "perfil", None) in _PERFIS or user.is_staff)
    )


def _pode_ver_resumo_super_os(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and (
            getattr(user, "perfil", None) in _PERFIS_RESUMO_SUPER_OS or user.is_staff
        )
    )


class ClusterExecucaoViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/clusters/ — Super Ordens de Serviço abertas/em andamento."""

    permission_classes = [IsAuthenticated]
    serializer_class = ClusterExecucaoSerializer
    queryset = ClusterExecucao.objects.all().order_by("-atualizado_em")

    def get_queryset(self):
        ClusterService().purgar_clusters_unitarios()
        qs = super().get_queryset().annotate(demandas_count=Count("demandas"))
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        else:
            qs = qs.filter(status__in=("ABERTO", "EM_ANDAMENTO"))
        qs = qs.filter(demandas_count__gte=CLUSTER_MIN_DEMANDAS)
        cluster_id = self.request.query_params.get("id")
        if cluster_id:
            try:
                qs = qs.filter(pk=int(cluster_id))
            except (TypeError, ValueError):
                pass
        user = self.request.user
        if getattr(user, "perfil", None) == "GESTOR" and tipo_gestor(user) == TIPO_SETORIAL:
            orgaos = orgaos_escopo_gestor(user)
            if orgaos:
                qs = qs.filter(demandas__sinapse_orgao_id__in=orgaos).distinct()
            else:
                qs = qs.none()
        return qs

    def get_object(self):
        """Deep-link /clusters/:id — permite detalhe mesmo fora dos filtros da listagem."""
        if self.action == "retrieve":
            ClusterService().purgar_clusters_unitarios()
            pk = self.kwargs.get(self.lookup_field or "pk")
            try:
                return (
                    ClusterExecucao.objects.annotate(demandas_count=Count("demandas"))
                    .get(pk=int(pk))
                )
            except (ClusterExecucao.DoesNotExist, TypeError, ValueError):
                raise Http404 from None
        return super().get_object()

    def list(self, request, *args, **kwargs):
        if not _pode_ver_clusters(request.user):
            return Response(
                {"detail": "Acesso restrito a Protocolo ou Gestor."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        if not _pode_ver_clusters(request.user):
            return Response(
                {"detail": "Acesso restrito a Protocolo ou Gestor."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().retrieve(request, *args, **kwargs)

    @action(detail=True, methods=["get"])
    def demandas(self, request, pk=None):
        if not _pode_ver_clusters(request.user):
            return Response(
                {"detail": "Acesso restrito a Protocolo ou Gestor."},
                status=status.HTTP_403_FORBIDDEN,
            )
        cluster = self.get_object()
        qs = Demanda.objects.filter(cluster=cluster).select_related("autor").order_by(
            "-data_criacao"
        )
        return Response(DemandaListSerializer(qs, many=True).data)

    @action(detail=False, methods=["get"], url_path="resumo-operacional")
    def resumo_operacional(self, request):
        if not _pode_ver_resumo_super_os(request.user):
            return Response(
                {"detail": "Acesso restrito a Protocolo, Secretaria ou Gestor."},
                status=status.HTTP_403_FORBIDDEN,
            )
        limite = int(request.query_params.get("limit", 30))
        perfil = getattr(request.user, "perfil", None)
        orgao_id = None
        if perfil == "SECRETARIA" and getattr(request.user, "sinapse_orgao_id", None):
            orgao_id = int(request.user.sinapse_orgao_id)
        return Response(
            {
                "clusters": ClusterService().resumo_clusters_abertos(
                    limit=limite,
                    sinapse_orgao_id=orgao_id,
                ),
                "semantic_threshold": getattr(settings, "CLUSTER_SEMANTIC_THRESHOLD", 0.7),
                "radius_meters": getattr(settings, "CLUSTER_RADIUS_METERS", 300),
                "janela_agregacao_dias": getattr(
                    settings, "CLUSTER_JANELA_AGREGACAO_DIAS", 90
                ),
            }
        )

    @action(detail=True, methods=["post"])
    def despachar(self, request, pk=None):
        """Despacha em lote todas as demandas AGUARDANDO_PROTOCOLO do cluster."""
        if getattr(request.user, "perfil", None) != "PROTOCOLO":
            return Response(
                {"detail": "Apenas o Protocolo pode despachar Super OS."},
                status=status.HTTP_403_FORBIDDEN,
            )
        cluster = self.get_object()
        secretaria_id = request.data.get("secretaria_id")
        if not secretaria_id:
            return Response(
                {"detail": "secretaria_id é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            orgao_id = int(secretaria_id)
        except (TypeError, ValueError):
            return Response(
                {"detail": "secretaria_id inválido."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            resultado = ClusterDespachoService().despachar_super_os(
                cluster,
                secretaria_id=orgao_id,
                usuario=request.user,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        cluster.refresh_from_db()
        return Response(
            {
                **resultado,
                "cluster": ClusterExecucaoSerializer(cluster).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def vincular(self, request, pk=None):
        """Vincula manualmente uma demanda ao cluster (mesmo serviço + geo)."""
        if getattr(request.user, "perfil", None) != "PROTOCOLO":
            return Response(
                {"detail": "Apenas o Protocolo pode gerenciar clusters."},
                status=status.HTTP_403_FORBIDDEN,
            )
        cluster = self.get_object()
        demanda_id = request.data.get("demanda_id")
        if not demanda_id:
            return Response(
                {"detail": "demanda_id é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            demanda = Demanda.objects.get(pk=int(demanda_id))
        except (Demanda.DoesNotExist, TypeError, ValueError):
            return Response(
                {"detail": "Demanda não encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            ClusterService().vincular_demanda_manual(
                demanda, cluster, usuario=request.user
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        cluster.refresh_from_db()
        demanda.refresh_from_db()
        return Response(
            {
                "cluster": ClusterExecucaoSerializer(cluster).data,
                "demanda": DemandaListSerializer(demanda).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def desvincular(self, request, pk=None):
        """Remove uma demanda do cluster manualmente."""
        if getattr(request.user, "perfil", None) != "PROTOCOLO":
            return Response(
                {"detail": "Apenas o Protocolo pode gerenciar clusters."},
                status=status.HTTP_403_FORBIDDEN,
            )
        cluster = self.get_object()
        demanda_id = request.data.get("demanda_id")
        if not demanda_id:
            return Response(
                {"detail": "demanda_id é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            demanda = Demanda.objects.get(pk=int(demanda_id), cluster=cluster)
        except (Demanda.DoesNotExist, TypeError, ValueError):
            return Response(
                {"detail": "Demanda não encontrada neste cluster."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            ClusterService().desvincular_demanda_manual(demanda, usuario=request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"ok": True, "demanda_id": int(demanda_id)}, status=status.HTTP_200_OK)
