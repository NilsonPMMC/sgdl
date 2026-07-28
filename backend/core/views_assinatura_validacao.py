"""APIs de validação assíncrona de assinaturas pelo gestor."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from core.models_assinatura_eletronica import AssinaturaValidacaoGestor
from core.services.assinatura_eletronica_service import AssinaturaEletronicaService


class AssinaturasValidacaoPendentesAPIView(APIView):
    """GET /api/assinaturas-validacao/pendentes/ — fila do gestor."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        perfil = getattr(request.user, "perfil", None)
        if perfil not in ("GESTOR", "PROTOCOLO") and not request.user.is_staff:
            return Response(
                {"detail": "Acesso restrito a gestores."},
                status=status.HTTP_403_FORBIDDEN,
            )
        itens = AssinaturaEletronicaService().listar_validacoes_pendentes(request.user)
        return Response({"results": itens, "total": len(itens)})


class PreviewValidacaoGestorAPIView(APIView):
    """POST /api/assinaturas-validacao/<id>/preview/ — prévia para gestor assinar."""

    permission_classes = [IsAuthenticated]

    def post(self, request, validacao_id=None):
        try:
            validacao = AssinaturaValidacaoGestor.objects.select_related(
                "demanda", "operador", "tramitacao"
            ).get(pk=int(validacao_id))
        except (AssinaturaValidacaoGestor.DoesNotExist, TypeError, ValueError):
            return Response({"detail": "Validação não encontrada."}, status=status.HTTP_404_NOT_FOUND)

        svc = AssinaturaEletronicaService()
        try:
            preview = svc.obter_preview_validacao_gestor(validacao, request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if validacao.tipo_gestor == AssinaturaValidacaoGestor.TIPO_GESTOR_PROTOCOLO:
            preview["gestores_protocolo"] = svc.listar_gestores_protocolo()
        else:
            preview["gestores_setor"] = svc.listar_gestores_setor(
                unidade_administrativa_id=validacao.unidade_administrativa_id,
                sinapse_orgao_id=validacao.sinapse_orgao_id,
            )
        return Response(preview)


class ValidarAssinaturaGestorAPIView(APIView):
    """POST /api/assinaturas-validacao/<id>/validar/ — gestor atesta assinatura."""

    permission_classes = [IsAuthenticated]

    def post(self, request, validacao_id=None):
        try:
            validacao = AssinaturaValidacaoGestor.objects.select_related("demanda").get(
                pk=int(validacao_id)
            )
        except (AssinaturaValidacaoGestor.DoesNotExist, TypeError, ValueError):
            return Response({"detail": "Validação não encontrada."}, status=status.HTTP_404_NOT_FOUND)

        svc = AssinaturaEletronicaService()
        try:
            assinatura = svc.registrar_validacao_gestor(
                validacao,
                request.user,
                hash_documento=request.data.get("hash_documento"),
                declaracao_gestor=request.data.get("declaracao_gestor")
                or request.data.get("declaracao"),
                request=request,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "validacao_id": validacao.pk,
                "demanda_id": validacao.demanda_id,
                "assinatura_registrada": {
                    "codigo_validacao": assinatura.codigo_validacao,
                    "papel": assinatura.papel,
                    "etapa": assinatura.etapa,
                },
            }
        )
