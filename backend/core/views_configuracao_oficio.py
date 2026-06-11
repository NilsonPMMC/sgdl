"""API da configuração institucional de ofícios (P6 — painel formatação)."""

from __future__ import annotations

from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models_config import ConfiguracaoOficio
from core.serializers import ConfiguracaoOficioSerializer
from core.services.oficio_config_preview import clonar_config_para_preview, limpar_imagem_preview_temp
from core.services.oficio_service import OficioService

_PERFIS_GESTAO = frozenset({"GESTOR"})

_CAMPOS_PREVIEW = frozenset(
    {
        "municipio",
        "uf",
        "orgao_destinatario",
        "destinatario_tratamento",
        "destinatario_nome",
        "destinatario_cargo",
        "titulo_instituicao",
        "cabecalho_layout",
        "brasao_largura_cm",
        "pagina_formato",
        "pagina_orientacao",
        "margem_superior_cm",
        "margem_inferior_cm",
        "margem_esquerda_cm",
        "margem_direita_cm",
        "rodape_protocolo_altura_cm",
    }
)


def _pode_gestao_config_oficio(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and (getattr(user, "perfil", None) in _PERFIS_GESTAO or user.is_staff)
    )


def _payload_preview(request) -> dict:
    data = request.data
    payload: dict = {}
    for key in _CAMPOS_PREVIEW:
        valor = None
        if hasattr(data, "getlist"):
            values = data.getlist(key)
            if values:
                valor = values[-1]
        if valor is None and key in data:
            valor = data.get(key)
        if valor is not None:
            payload[key] = valor
    return payload


def _gerar_pdf_preview(request):
    base = ConfiguracaoOficio.carregar()
    data = request.data.copy()
    remover_imagem = str(data.get("remover_imagem_cabecalho", "")).lower() in {"1", "true", "yes"}
    payload = _payload_preview(request)


    serializer = ConfiguracaoOficioSerializer(
        base,
        data=payload,
        partial=True,
        context={"request": request},
    )
    serializer.is_valid(raise_exception=True)

    imagem_arquivo = request.FILES.get("imagem_cabecalho")
    preview_cfg, temp_path = clonar_config_para_preview(
        base,
        serializer.validated_data,
        imagem_arquivo=imagem_arquivo,
        remover_imagem=remover_imagem and imagem_arquivo is None,
    )
    if "cabecalho_layout" in payload:
        preview_cfg.cabecalho_layout = serializer.validated_data.get(
            "cabecalho_layout", payload["cabecalho_layout"]
        )
    
    
    try:
        return OficioService(config=preview_cfg).render_amostra_pdf_bytes(autor=request.user)
    finally:
        limpar_imagem_preview_temp(temp_path)


class ConfiguracaoOficioAPIView(APIView):
    """Singleton GET/PATCH — formatação institucional do PDF de ofício."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _pode_gestao_config_oficio(request.user):
            return Response(
                {"detail": "Sem permissão para consultar a configuração de ofício."},
                status=status.HTTP_403_FORBIDDEN,
            )
        cfg = ConfiguracaoOficio.carregar()
        return Response(ConfiguracaoOficioSerializer(cfg, context={"request": request}).data)

    def patch(self, request):
        if not _pode_gestao_config_oficio(request.user):
            return Response(
                {"detail": "Sem permissão para alterar a configuração de ofício."},
                status=status.HTTP_403_FORBIDDEN,
            )
        cfg = ConfiguracaoOficio.carregar()
        data = request.data.copy()
        if data.get("remover_imagem_cabecalho") in (True, "true", "1", "True"):
            if cfg.imagem_cabecalho:
                cfg.imagem_cabecalho.delete(save=False)
            data.pop("remover_imagem_cabecalho", None)
            data["imagem_cabecalho"] = None

        serializer = ConfiguracaoOficioSerializer(
            cfg,
            data=data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ConfiguracaoOficioPreviewPDFAPIView(APIView):
    """Gera PDF de amostra — POST com valores do formulário (sem salvar)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Compatibilidade: usa configuração salva no banco."""
        if not _pode_gestao_config_oficio(request.user):
            return Response(
                {"detail": "Sem permissão para pré-visualizar o ofício."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            pdf_bytes = OficioService().render_amostra_pdf_bytes(autor=request.user)
        except Exception:
            return Response(
                {"detail": "Não foi possível gerar a pré-visualização do PDF."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = 'inline; filename="oficio_amostra_sgdl.pdf"'
        return response

    def post(self, request):
        if not _pode_gestao_config_oficio(request.user):
            return Response(
                {"detail": "Sem permissão para pré-visualizar o ofício."},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        try:
            pdf_bytes = _gerar_pdf_preview(request)
        except Exception:
            return Response(
                {"detail": "Não foi possível gerar a pré-visualização do PDF."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = 'inline; filename="oficio_amostra_sgdl.pdf"'
        return response
