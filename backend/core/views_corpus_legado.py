"""API read-only do corpus legado (aprendizado — não substitui fluxo operacional)."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.services.copiloto_config import corpus_legado_habilitado
from core.services.corpus_legado_service import CorpusLegadoService


class CorpusLegadoTopTrendsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not corpus_legado_habilitado():
            return Response({"detail": "Corpus legado desabilitado."}, status=404)
        limite = min(int(request.query_params.get("limite", 20)), 50)
        rel = CorpusLegadoService().relatorio()
        if not rel:
            return Response(
                {"detail": "Relatório não gerado. Execute: python manage.py analisar_corpus_legado"},
                status=404,
            )
        return Response(
            {
                "total_registros": rel.get("total_registros"),
                "periodo_referencia_meses": rel.get("periodo_referencia_meses"),
                "checksum_csv": rel.get("checksum_csv"),
                "top_trends": CorpusLegadoService().top_trends(limite=limite),
            }
        )


class CorpusLegadoTopSetoresAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not corpus_legado_habilitado():
            return Response({"detail": "Corpus legado desabilitado."}, status=404)
        limite = min(int(request.query_params.get("limite", 15)), 30)
        return Response({"top_setores": CorpusLegadoService().top_setores(limite=limite)})


class CorpusLegadoAtalhosCopilotoAPIView(APIView):
    """Atalhos de pedidos frequentes — opcional no Copiloto (não altera triagem)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not corpus_legado_habilitado():
            return Response({"detail": "Corpus legado desabilitado."}, status=404)
        limite = min(int(request.query_params.get("limite", 12)), 24)
        atalhos = CorpusLegadoService().atalhos_copiloto(limite=limite)
        if not atalhos:
            return Response(
                {"detail": "Relatório não gerado. Execute: python manage.py analisar_corpus_legado"},
                status=404,
            )
        return Response({"atalhos": atalhos})


class CorpusLegadoAtalhoDetalheAPIView(APIView):
    """Detalhamento de pedido frequente — opções da carta Sinapse."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not corpus_legado_habilitado():
            return Response({"detail": "Corpus legado desabilitado."}, status=404)
        eixo_id = (request.query_params.get("id") or "").strip()
        if not eixo_id:
            return Response({"detail": "Informe id do atalho."}, status=400)
        det = CorpusLegadoService().detalhe_atalho_copiloto(eixo_id)
        if not det:
            return Response({"detail": "Atalho não encontrado."}, status=404)
        return Response(det)


class CorpusLegadoSugerirAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not corpus_legado_habilitado():
            return Response({"detail": "Corpus legado desabilitado."}, status=404)
        texto = (request.query_params.get("q") or "").strip()
        if len(texto) < 8:
            return Response({"detail": "Informe q com ao menos 8 caracteres."}, status=400)
        sugestoes = CorpusLegadoService().sugerir_por_texto(texto)
        return Response({"texto": texto, "sugestoes": sugestoes})
