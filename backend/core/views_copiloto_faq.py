"""API da base de conhecimento FAQ do Copiloto (gestão + enriquecimento LLM)."""

from __future__ import annotations

import logging

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .models_copiloto_faq import CopilotoFaqOrientacao, CopilotoFaqPadraoRegex
from .serializers import (
    CopilotoFaqEnriquecerLlmSerializer,
    CopilotoFaqOrientacaoSerializer,
    CopilotoFaqOrientacaoWriteSerializer,
    CopilotoFaqPadraoRegexSerializer,
)
from .services.copiloto_faq_enriquecimento_llm import CopilotoFaqEnriquecimentoLlmService
from .services.copiloto_faq_service import (
    aplicar_sugestao_llm,
    listar_categorias_para_prompt,
)
logger = logging.getLogger(__name__)


def _usuario_pode_gestao_faq(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and (getattr(user, "perfil", None) == "GESTOR" or user.is_staff)
    )


def _enriquecer_item_atualizacao(item: dict) -> dict:
    """Preenche título/mensagem/órgão a partir do FAQ existente quando o LLM só sugere padrões."""
    cat = (item.get("categoria_orientacao") or "").strip()
    if not cat:
        return item
    try:
        faq = CopilotoFaqOrientacao.objects.get(categoria_orientacao=cat)
    except CopilotoFaqOrientacao.DoesNotExist:
        return item
    return {
        **item,
        "titulo": (item.get("titulo") or faq.titulo or "").strip(),
        "mensagem": (item.get("mensagem") or faq.mensagem or "").strip(),
        "orgao_hint": (item.get("orgao_hint") or faq.orgao_hint or "").strip(),
        "municipio_referencia": item.get("municipio_referencia") or faq.municipio_referencia,
    }


def _executar_consulta_sugestoes_llm(request):
    foco = (request.query_params.get("foco") or "").strip() or None
    municipio = (request.query_params.get("municipio") or "").strip() or None
    try:
        max_novas = int(request.query_params.get("max_novas") or 5)
    except (TypeError, ValueError):
        max_novas = 5
    max_novas = max(1, min(max_novas, 15))

    svc = CopilotoFaqEnriquecimentoLlmService()
    resultado = svc.executar(
        municipio=municipio,
        max_novas=max_novas,
        dry_run=True,
        foco=foco,
    )

    if resultado.erros:
        return Response(
            {"detail": resultado.erros[0], "erros": resultado.erros},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return Response(_serializar_sugestoes_llm(resultado))


def _serializar_sugestoes_llm(resultado) -> dict:
    """Normaliza saída do dry-run para a UI de curadoria."""
    raw = resultado.sugestoes_brutas if isinstance(resultado.sugestoes_brutas, dict) else {}
    sugestoes: list[dict] = []

    for i, item in enumerate(raw.get("novas_entradas") or []):
        if not isinstance(item, dict):
            continue
        sugestoes.append(
            {
                **item,
                "tipo": "nova",
                "id": f"nova-{i}",
                "padroes_regex": item.get("padroes_regex") or [],
            }
        )

    for i, item in enumerate(raw.get("atualizacoes") or []):
        if not isinstance(item, dict):
            continue
        item = _enriquecer_item_atualizacao(item)
        sugestoes.append(
            {
                **item,
                "tipo": "atualizacao",
                "id": f"atualizacao-{i}",
                "padroes_regex": item.get("padroes_regex_novos") or item.get("padroes_regex") or [],
            }
        )

    return {
        "municipio": resultado.municipio,
        "observacoes": resultado.observacoes,
        "sugestoes": sugestoes,
        "novas_entradas": raw.get("novas_entradas") or [],
        "atualizacoes": raw.get("atualizacoes") or [],
        "erros": resultado.erros,
    }


class CopilotoFaqSugestoesLlmAPIView(APIView):
    """
    GET /api/v1/copiloto-faq/sugestoes-llm/?foco=...
    Consulta Groq sem persistir (equivalente a enriquecer_faq_llm --dry-run).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _usuario_pode_gestao_faq(request.user):
            return Response(
                {"detail": "Acesso restrito a Protocolo ou Gestor."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return _executar_consulta_sugestoes_llm(request)


class CopilotoFaqAprovarLlmAPIView(APIView):
    """POST /api/v1/copiloto-faq/enriquecer-llm/ — alias v1 para aprovação na curadoria web."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _usuario_pode_gestao_faq(request.user):
            return Response(
                {"detail": "Acesso restrito a Protocolo ou Gestor."},
                status=status.HTTP_403_FORBIDDEN,
            )
        ser = CopilotoFaqEnriquecerLlmSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            faq = aplicar_sugestao_llm(ser.validated_data, usuario=request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        out = CopilotoFaqOrientacao.objects.prefetch_related("padroes").get(pk=faq.pk)
        return Response(
            CopilotoFaqOrientacaoSerializer(out).data,
            status=status.HTTP_201_CREATED,
        )


class CopilotoFaqOrientacaoViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    CRUD da FAQ Copiloto (Protocolo / Gestor).

    POST .../enriquecer-llm/ — entrada estruturada da automação de IA (futuro job/agendamento).
    GET  .../catalogo-llm/   — categorias ativas para montagem de prompt.
    """

    permission_classes = [IsAuthenticated]
    queryset = CopilotoFaqOrientacao.objects.prefetch_related("padroes").all()
    serializer_class = CopilotoFaqOrientacaoSerializer
    filterset_fields = ["ativo", "fonte", "municipio_referencia"]
    search_fields = ["titulo", "slug", "categoria_orientacao", "orgao_hint", "mensagem"]
    ordering_fields = ["ordem", "titulo", "atualizado_em"]
    ordering = ["ordem", "titulo"]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return CopilotoFaqOrientacaoWriteSerializer
        return CopilotoFaqOrientacaoSerializer

    def _negar(self):
        return Response(
            {"detail": "Acesso restrito a Protocolo ou Gestor."},
            status=status.HTTP_403_FORBIDDEN,
        )

    def list(self, request, *args, **kwargs):
        if not _usuario_pode_gestao_faq(request.user):
            return self._negar()
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        if not _usuario_pode_gestao_faq(request.user):
            return self._negar()
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        if not _usuario_pode_gestao_faq(request.user):
            return self._negar()
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not _usuario_pode_gestao_faq(request.user):
            return self._negar()
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if not _usuario_pode_gestao_faq(request.user):
            return self._negar()
        return super().partial_update(request, *args, **kwargs)

    @action(detail=False, methods=["get"], url_path="catalogo-llm")
    def catalogo_llm(self, request):
        """Lista categorias ativas para a automação de enriquecimento (prompt)."""
        if not _usuario_pode_gestao_faq(request.user):
            return self._negar()
        return Response(
            {
                "municipio_referencia_padrao": "Mogi das Cruzes",
                "categorias": listar_categorias_para_prompt(),
            }
        )

    @action(detail=False, methods=["get"], url_path="sugestoes-llm")
    def sugestoes_llm(self, request):
        """GET .../sugestoes-llm/?foco= — preview Groq sem gravar."""
        if not _usuario_pode_gestao_faq(request.user):
            return self._negar()
        return _executar_consulta_sugestoes_llm(request)

    @action(detail=False, methods=["post"], url_path="enriquecer-llm")
    def enriquecer_llm(self, request):
        """
        Aplica sugestão da automação LLM (cria/atualiza FAQ + padrões regex).
        Corpo validado por CopilotoFaqEnriquecerLlmSerializer.
        """
        if not _usuario_pode_gestao_faq(request.user):
            return self._negar()
        ser = CopilotoFaqEnriquecerLlmSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            faq = aplicar_sugestao_llm(ser.validated_data, usuario=request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        out = CopilotoFaqOrientacao.objects.prefetch_related("padroes").get(pk=faq.pk)
        return Response(
            CopilotoFaqOrientacaoSerializer(out).data,
            status=status.HTTP_200_OK,
        )


class CopilotoFaqPadraoRegexViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Gestão de padrões regex avulsos (vinculados a uma FAQ)."""

    permission_classes = [IsAuthenticated]
    queryset = CopilotoFaqPadraoRegex.objects.select_related("faq").all()
    serializer_class = CopilotoFaqPadraoRegexSerializer
    filterset_fields = ["ativo", "faq", "fonte"]

    def _negar(self):
        return Response(
            {"detail": "Acesso restrito a Protocolo ou Gestor."},
            status=status.HTTP_403_FORBIDDEN,
        )

    def list(self, request, *args, **kwargs):
        if not _usuario_pode_gestao_faq(request.user):
            return self._negar()
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        if not _usuario_pode_gestao_faq(request.user):
            return self._negar()
        return super().create(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if not _usuario_pode_gestao_faq(request.user):
            return self._negar()
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not _usuario_pode_gestao_faq(request.user):
            return self._negar()
        return super().destroy(request, *args, **kwargs)
