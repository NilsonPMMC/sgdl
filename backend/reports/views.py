# Em /var/www/sgdl/backend/reports/views.py

import csv
import logging
from datetime import timedelta

from django.db.models import Count
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Demanda
from core.services.demanda_visibilidade import aplicar_escopo_demanda
from integrations import sinapse_catalog

from .filters import DemandaReportFilter
from .pagination import ReportDemandaPagination
from .serializers import DemandaRelatorioSerializer, STATUS_ABERTO_RELATORIO
from .services import (
    agregar_comparativo_vereador,
    agregar_funil_status,
    agregar_por_setor,
    calcular_metricas_sla,
)

logger = logging.getLogger(__name__)

STATUS_ABERTO = STATUS_ABERTO_RELATORIO


class BaseReportView(APIView):
    """View base para relatórios que usa o DemandaReportFilter."""

    permission_classes = [permissions.IsAuthenticated]

    def get_filtered_queryset(self, request):
        logger.debug("Filtros recebidos para relatórios: %s", request.GET)
        base = aplicar_escopo_demanda(Demanda.objects.all(), request.user)
        filterset = DemandaReportFilter(request.GET, queryset=base)
        return filterset.qs


class DemandasPorStatusView(BaseReportView):
    def get(self, request, *args, **kwargs):
        qs_filtrado = self.get_filtered_queryset(request)
        dados_agregados = qs_filtrado.values('status').annotate(
            total=Count('id')
        ).order_by('status')
        return Response(dados_agregados)


class DemandasPorSecretariaView(BaseReportView):
    def get(self, request, *args, **kwargs):
        qs_filtrado = self.get_filtered_queryset(request)
        status_aberto = STATUS_ABERTO

        por_orgao: dict[int, dict] = {}
        for row in qs_filtrado.filter(sinapse_orgao_id__isnull=False).values(
            "sinapse_orgao_id", "status"
        ):
            oid = row["sinapse_orgao_id"]
            bucket = por_orgao.setdefault(oid, {"total": 0, "abertas": 0})
            bucket["total"] += 1
            if row["status"] in status_aberto:
                bucket["abertas"] += 1

        dados = sorted(
            [
                {
                    "secretaria": sinapse_catalog.get_orgao_nome(oid) or str(oid),
                    "total": vals["total"],
                    "abertas": vals["abertas"],
                }
                for oid, vals in por_orgao.items()
            ],
            key=lambda x: x["total"],
            reverse=True,
        )
        return Response(dados)


class DemandasPorVereadorView(BaseReportView):
    def get(self, request, *args, **kwargs):
        qs_filtrado = self.get_filtered_queryset(request)
        qs_com_autor = qs_filtrado.filter(autor__isnull=False)

        dados_agregados = qs_com_autor.values(
            'autor_id',
            'autor__first_name',
            'autor__last_name',
            'autor__username',
        ).annotate(total=Count('id')).order_by('-total')

        total_sem_autor = qs_filtrado.filter(autor__isnull=True).count()

        dados = []
        for item in dados_agregados:
            nome = f"{item['autor__first_name'] or ''} {item['autor__last_name'] or ''}".strip()
            if not nome:
                nome = item['autor__username']
            dados.append({'vereador': nome, 'total': item['total']})

        if total_sem_autor > 0:
            dados.append({'vereador': 'Sem Autor (Sistema/Antigo)', 'total': total_sem_autor})

        return Response(dados)


class HeatmapView(BaseReportView):
    def get(self, request, *args, **kwargs):
        qs_filtrado = self.get_filtered_queryset(request)
        dados_geo = qs_filtrado.filter(
            latitude__isnull=False,
            longitude__isnull=False,
        ).values('latitude', 'longitude')
        dados = [{'lat': item['latitude'], 'lng': item['longitude']} for item in dados_geo]
        return Response(dados)


class DemandasFiltradasView(generics.ListAPIView):
    queryset = Demanda.objects.exclude(status='RASCUNHO').select_related(
        'autor', 'unidade_administrativa', 'cluster',
    )
    serializer_class = DemandaRelatorioSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_class = DemandaReportFilter
    pagination_class = ReportDemandaPagination

    def get_queryset(self):
        logger.debug("Filtros recebidos para tabela: %s", self.request.GET)
        base = aplicar_escopo_demanda(Demanda.objects.all(), self.request.user)
        filterset = DemandaReportFilter(self.request.GET, queryset=base)
        return filterset.qs.order_by('-data_criacao')


class ReportProcessMiningSetorView(BaseReportView):
    def get(self, request, *args, **kwargs):
        qs = self.get_filtered_queryset(request)
        return Response(agregar_por_setor(qs))


class ReportFunilStatusView(BaseReportView):
    def get(self, request, *args, **kwargs):
        qs = self.get_filtered_queryset(request)
        return Response(agregar_funil_status(qs))


class ReportComparativoVereadorView(BaseReportView):
    def get(self, request, *args, **kwargs):
        qs = self.get_filtered_queryset(request)
        return Response(agregar_comparativo_vereador(qs))


class ReportKPIsView(BaseReportView):
    def get(self, request, *args, **kwargs):
        try:
            queryset = self.get_filtered_queryset(request)
            metricas_sla = calcular_metricas_sla(queryset)

            total_demandas = queryset.count()
            status_aberto = STATUS_ABERTO
            demandas_abertas = queryset.filter(status__in=status_aberto).count()
            demandas_concluidas = queryset.filter(status='FINALIZADO').count()

            agora = timezone.now()
            demandas_com_vencimento = queryset.filter(
                status__in=status_aberto,
                data_inicio_prazo__isnull=False,
            )

            demandas_atrasadas = sum(
                1
                for demanda in demandas_com_vencimento
                if demanda.prazo_dias() is not None
                and demanda.data_inicio_prazo + timedelta(days=demanda.prazo_dias()) < agora
            )

            return Response({
                'total_demandas': total_demandas,
                'demandas_abertas': demandas_abertas,
                'demandas_concluidas': demandas_concluidas,
                'demandas_atrasadas': demandas_atrasadas,
                **metricas_sla,
            })

        except Exception:
            logger.exception("Falha inesperada ao gerar KPIs.")
            return Response(
                {"erro": "Erro interno ao gerar os KPIs."},
                status=500,
            )


class ReportExportCSVView(BaseReportView):
    """Exportação CSV das demandas filtradas (sem paginação)."""

    CSV_HEADERS = [
        'id', 'oficio', 'protocolo', 'autor', 'orgao', 'setor', 'servico',
        'status', 'sla', 'vencimento', 'dias_pos_protocolo', 'dias_na_etapa',
        'super_os', 'bairro', 'criado_em',
    ]

    def get(self, request, *args, **kwargs):
        qs = self.get_filtered_queryset(request).select_related(
            'autor', 'unidade_administrativa', 'cluster',
        ).order_by('-data_criacao')

        class Echo:
            def write(self, value):
                return value

        pseudo_buffer = Echo()
        writer = csv.writer(pseudo_buffer)

        def row_iter():
            yield writer.writerow(self.CSV_HEADERS)
            serializer = DemandaRelatorioSerializer()
            for demanda in qs.iterator(chunk_size=200):
                data = serializer.to_representation(demanda)
                sla = data.get('sla') or {}
                unidade = data.get('unidade_administrativa') or {}
                cluster = data.get('cluster') or {}
                tempo_etapa = sla.get('tempo_etapa_segundos')
                dias_etapa = round(tempo_etapa / 86400, 1) if tempo_etapa is not None else ''
                yield writer.writerow([
                    data.get('id'),
                    data.get('protocolo_legislativo') or '',
                    data.get('protocolo_executivo') or '',
                    data.get('autor_nome') or '',
                    data.get('secretaria_destino_nome') or '',
                    unidade.get('sigla') or unidade.get('nome') or '',
                    data.get('servico_nome') or '',
                    data.get('status_display') or data.get('status') or '',
                    sla.get('prazo_dias') if sla.get('prazo_dias') is not None else '',
                    sla.get('data_vencimento') or '',
                    sla.get('dias_pos_protocolo') if sla.get('dias_pos_protocolo') is not None else '',
                    dias_etapa,
                    cluster.get('protocolo_super_os') or '',
                    data.get('bairro') or '',
                    data.get('data_criacao') or '',
                ])

        response = StreamingHttpResponse(row_iter(), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="relatorio_demandas.csv"'
        return response
