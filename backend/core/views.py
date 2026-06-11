# /var/www/sgdl/backend/core/views.py

import logging
import uuid
from datetime import datetime, timedelta
from rest_framework import viewsets, mixins, status, permissions
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.permissions import AllowAny
from django.db.models import Count, Q
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.exceptions import ValidationError
from django.conf import settings
from .models import Demanda, Anexo, Tramitacao, AnexoTramitacao, Usuario, Notificacao
from integrations import sinapse_catalog
from .services.vector_service import VectorService
from .services.chatbot_service import ChatbotService
from .serializers import ( DemandaSerializer, DemandaPainelListSerializer, ServicoSerializer, AnexoSerializer, SecretariaSerializer, CustomTokenObtainPairSerializer, PasswordResetConfirmSerializer,
    TramitacaoSerializer, AnexoTramitacaoSerializer, UsuarioSerializer, UserProfileSerializer, ChangePasswordSerializer, NotificacaoSerializer,
    ChatInteracaoSerializer,
)
from .filters import DemandaFilter, UsuarioFilter
from rest_framework.permissions import IsAuthenticated

logger = logging.getLogger(__name__)


class ChatRetriagemCartaAPIView(APIView):
    """POST /api/v1/chat/retriagem-carta/ — nova busca semântica na carta para um item do rascunho."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        session_id = request.data.get("session_id")
        indice = request.data.get("indice_demanda")
        if not session_id:
            return Response({"detail": "session_id é obrigatório."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            indice_i = int(indice)
        except (TypeError, ValueError):
            return Response({"detail": "indice_demanda inválido."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            payload = ChatbotService().retriagem_carta_demanda(
                usuario=request.user,
                session_id=str(session_id),
                indice_demanda=indice_i,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError:
            return Response(
                {"detail": "Sessão inexistente ou não pertence ao usuário."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(payload, status=status.HTTP_200_OK)


class ChatIgnorarServicoAPIView(APIView):
    """POST /api/v1/chat/ignorar-servico/ — descarta sugestões da carta para um item."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        session_id = request.data.get("session_id")
        indice = request.data.get("indice_demanda")
        if not session_id:
            return Response({"detail": "session_id é obrigatório."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            indice_i = int(indice)
        except (TypeError, ValueError):
            return Response({"detail": "indice_demanda inválido."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            payload = ChatbotService().ignorar_servico_sugerido_demanda(
                usuario=request.user,
                session_id=str(session_id),
                indice_demanda=indice_i,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError:
            return Response(
                {"detail": "Sessão inexistente ou não pertence ao usuário."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(payload, status=status.HTTP_200_OK)


class ChatAtualizarLocalizacaoAPIView(APIView):
    """POST /api/v1/chat/atualizar-localizacao/ — GPS do dispositivo no rascunho."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        session_id = request.data.get("session_id")
        indice = request.data.get("indice_demanda")
        lat = request.data.get("latitude")
        lng = request.data.get("longitude")
        if not session_id:
            return Response({"detail": "session_id é obrigatório."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            indice_i = int(indice)
            lat_f = float(lat)
            lng_f = float(lng)
        except (TypeError, ValueError):
            return Response(
                {"detail": "indice_demanda, latitude e longitude são obrigatórios."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            payload = ChatbotService().atualizar_localizacao_demanda(
                usuario=request.user,
                session_id=str(session_id),
                indice_demanda=indice_i,
                latitude=lat_f,
                longitude=lng_f,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError:
            return Response(
                {"detail": "Sessão inexistente ou não pertence ao usuário."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(payload, status=status.HTTP_200_OK)


class ChatMarcarDemandaRascunhoAPIView(APIView):
    """POST /api/v1/chat/marcar-demanda/ — aprovar ou descartar item antes de finalizar."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        session_id = request.data.get("session_id")
        indice = request.data.get("indice_demanda")
        if not session_id:
            return Response({"detail": "session_id é obrigatório."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            indice_i = int(indice)
        except (TypeError, ValueError):
            return Response({"detail": "indice_demanda inválido."}, status=status.HTTP_400_BAD_REQUEST)
        aprovado = request.data.get("aprovado_final")
        descartada = request.data.get("descartada")
        aprovado_bool = None if aprovado in (None, "") else str(aprovado).lower() in ("1", "true", "sim", "yes")
        descartada_bool = None if descartada in (None, "") else str(descartada).lower() in ("1", "true", "sim", "yes")
        try:
            payload = ChatbotService().marcar_demanda_rascunho(
                usuario=request.user,
                session_id=str(session_id),
                indice_demanda=indice_i,
                aprovado_final=aprovado_bool,
                descartada=descartada_bool,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError:
            return Response(
                {"detail": "Sessão inexistente ou não pertence ao usuário."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(payload, status=status.HTTP_200_OK)


class ChatConfirmarServicoAPIView(APIView):
    """POST /api/v1/chat/confirmar-servico/ — vínculo explícito demanda ↔ serviço da carta."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        session_id = request.data.get("session_id")
        indice = request.data.get("indice_demanda")
        servico_id = request.data.get("sinapse_servico_id")
        if not session_id:
            return Response({"detail": "session_id é obrigatório."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            indice_i = int(indice)
            servico_i = int(servico_id)
        except (TypeError, ValueError):
            return Response(
                {"detail": "indice_demanda e sinapse_servico_id devem ser inteiros."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            payload = ChatbotService().confirmar_servico_demanda(
                usuario=request.user,
                session_id=str(session_id),
                indice_demanda=indice_i,
                sinapse_servico_id=servico_i,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError:
            return Response(
                {"detail": "Sessão inexistente ou não pertence ao usuário."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(payload, status=status.HTTP_200_OK)


class ChatInteragirAPIView(APIView):
    """
    POST /api/v1/chat/interagir/

    Copiloto com memória (`ChatSession`): slot filling, triagem Sinapse e rascunhos.
  Aceita JSON ou multipart (campo `anexos` para arquivos).
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        mensagem = (request.data.get("mensagem") or "").strip()
        anexos = request.FILES.getlist("anexos")
        if not mensagem and not anexos:
            return Response(
                {"detail": "Informe uma mensagem e/ou anexos."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sid_raw = request.data.get("session_id")
        sid = None
        if sid_raw not in (None, ""):
            try:
                sid = str(uuid.UUID(str(sid_raw)))
            except (ValueError, TypeError):
                return Response(
                    {"session_id": "Identificador de sessão inválido."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        anexo_indices_raw = request.data.get("anexo_demanda_indices")
        anexo_indices: list[int | None] = []
        if anexo_indices_raw not in (None, ""):
            for parte in str(anexo_indices_raw).split(","):
                parte = parte.strip()
                if parte == "":
                    anexo_indices.append(None)
                else:
                    try:
                        anexo_indices.append(int(parte))
                    except ValueError:
                        anexo_indices.append(None)

        indices_aprovados: list[int] | None = None
        raw_aprov = request.data.get("indices_aprovados")
        if raw_aprov not in (None, ""):
            indices_aprovados = []
            for parte in str(raw_aprov).split(","):
                parte = parte.strip()
                if parte.isdigit():
                    indices_aprovados.append(int(parte))

        try:
            payload = ChatbotService().interagir(
                usuario=request.user,
                session_id=sid,
                mensagem=mensagem,
                anexos_upload=anexos,
                anexo_demanda_indices=anexo_indices or None,
                indices_aprovados=indices_aprovados,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError:
            return Response(
                {"detail": "Sessão inexistente ou não pertence ao usuário."},
                status=status.HTTP_403_FORBIDDEN,
            )
        except Exception as exc:
            logger.exception("Falha no copiloto (chat/interagir): %s", exc)
            return Response(
                {"detail": "Não foi possível processar a mensagem. Tente novamente em instantes."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        if payload.get("erro"):
            return Response(payload, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload, status=status.HTTP_200_OK)


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    View customizada para usar o serializer de token customizado.
    """
    serializer_class = CustomTokenObtainPairSerializer

def _demanda_trilha_tendencia(demanda: Demanda) -> bool:
    return bool(
        demanda.tendencia_id
        or demanda.origem_vinculo == Demanda.ORIGEM_VINCULO_TENDENCIA
    )


def _orgao_id_para_envio_demanda(demanda: Demanda) -> int | None:
    if demanda.sinapse_orgao_id:
        return int(demanda.sinapse_orgao_id)
    tendencia = demanda.tendencia
    if tendencia and tendencia.sinapse_orgao_id:
        return int(tendencia.sinapse_orgao_id)
    if demanda.sinapse_servico_id:
        return sinapse_catalog.get_orgao_id_for_servico(int(demanda.sinapse_servico_id))
    return None


class DemandaViewSet(viewsets.ModelViewSet):
    queryset = Demanda.objects.select_related(
        "tendencia", "autor", "cluster"
    ).order_by("-data_criacao")
    serializer_class = DemandaSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = DemandaFilter

    _DESC_SIMILARES_MAX = 280

    def get_serializer_class(self):
        if self.action == "list":
            fila = (self.request.query_params.get("fila") or "").strip().lower()
            if fila in ("protocolados", "operacionais", "devolutivas"):
                return DemandaPainelListSerializer
        return DemandaSerializer

    def get_serializer_context(self):
        return super().get_serializer_context()

    def get_queryset(self):
        qs = Demanda.objects.select_related(
            "tendencia", "autor", "cluster", "unidade_administrativa"
        )
        fila = (self.request.query_params.get("fila") or "").strip().lower()
        if fila in ("protocolados", "operacionais", "devolutivas"):
            qs = qs.order_by("data_entrada_etapa", "data_criacao")
            if fila == "operacionais":
                unidade_id = self.request.query_params.get("unidade_administrativa")
                if unidade_id:
                    try:
                        qs = qs.filter(unidade_administrativa_id=int(unidade_id))
                    except (TypeError, ValueError):
                        pass
                elif self.request.query_params.get("minha_unidade") in ("1", "true", "True"):
                    from core.services.tramitacao_setor_service import (
                        UnidadeAdministrativaService,
                    )

                    ids = UnidadeAdministrativaService().ids_unidades_do_usuario(
                        self.request.user
                    )
                    if ids:
                        qs = qs.filter(unidade_administrativa_id__in=ids)
            if getattr(self.request.user, "perfil", None) == "SECRETARIA":
                from core.services.cluster_service import ClusterService

                qs = ClusterService().filtrar_listagem_apenas_lideres(qs)
            return qs
        qs = qs.order_by("-data_criacao")
        if getattr(self.request.user, "perfil", None) == "SECRETARIA":
            from core.services.cluster_service import ClusterService

            qs = ClusterService().filtrar_listagem_apenas_lideres(qs)
        return qs

    @action(
        detail=False,
        methods=['get'],
        url_path='similares',
        permission_classes=[IsAuthenticated],
    )
    def similares(self, request):
        """Busca semantica em demandas ja indexadas (embedding no SGDL).

        Query params:
            q (str): texto da busca (obrigatorio para retornar matches).
            top (int): quantidade maxima de resultados (default 5, max 50).

        Degradacao elegante: se o Kernel de embeddings estiver indisponivel
        ou nao houver vetor/query, retorna HTTP 200 com ``resultados`` vazio.
        """
        q = (request.query_params.get('q') or '').strip()
        try:
            top = int(request.query_params.get('top', 5))
        except (TypeError, ValueError):
            top = 5
        top = max(1, min(top, 50))

        if not q:
            return Response({'resultados': []}, status=status.HTTP_200_OK)

        vetor = VectorService().generate_embedding(q)
        if not vetor:
            logger.info(
                "demandas/similares: embedding vazio (Kernel indisponivel ou query sem vetor); q_len=%s",
                len(q),
            )
            return Response({'resultados': []}, status=status.HTTP_200_OK)

        qs = VectorService.find_similar_demanda(vetor, threshold=0.7)[:top]

        resultados = []
        max_len = self._DESC_SIMILARES_MAX
        for d in qs:
            texto = d.descricao or ''
            if len(texto) > max_len:
                desc_resumida = texto[:max_len].rstrip() + '…'
            else:
                desc_resumida = texto

            dist = getattr(d, 'distancia', None)
            if dist is not None:
                dist = round(float(dist), 3)

            resultados.append({
                'id': d.id,
                'titulo': d.titulo,
                'descricao': desc_resumida,
                'status': d.status,
                'bairro': d.bairro,
                'distancia': dist,
            })

        return Response({'resultados': resultados}, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["get"],
        url_path="cluster-elegibilidade",
        permission_classes=[IsAuthenticated],
    )
    def cluster_elegibilidade(self, request, pk=None):
        """Indica se a demanda pode entrar em cluster (mesmo serviço + geo)."""
        from core.services.cluster_service import ClusterService

        demanda = self.get_object()
        return Response(ClusterService().demanda_elegivel_cluster(demanda))

    @action(
        detail=True,
        methods=["get"],
        url_path="preview-envio-oficial",
        permission_classes=[IsAuthenticated],
    )
    def preview_envio_oficial(self, request, pk=None):
        """Pré-visualiza o PDF do ofício e retorna hash para assinatura eletrônica."""
        from core.services.assinatura_eletronica_service import AssinaturaEletronicaService

        demanda = self.get_object()
        if demanda.status != "RASCUNHO":
            return Response(
                {"detail": "Apenas rascunhos podem ser pré-visualizados."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if demanda.autor_id != request.user.pk and getattr(request.user, "perfil", None) != "GESTOR":
            return Response(
                {"detail": "Sem permissão para este ofício."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            preview = AssinaturaEletronicaService().preparar_preview_envio(demanda)
        except Exception:
            logger.exception("Falha preview envio oficial demanda %s", pk)
            return Response(
                {"detail": "Não foi possível gerar a pré-visualização do ofício."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(preview)

    @action(
        detail=True,
        methods=["get"],
        url_path="preview-envio-oficial-pdf",
        permission_classes=[IsAuthenticated],
    )
    def preview_envio_oficial_pdf(self, request, pk=None):
        """Stream do PDF de pré-visualização (sem anexo persistente)."""
        from django.http import HttpResponse

        from core.services.assinatura_eletronica_service import AssinaturaEletronicaService

        demanda = self.get_object()
        if demanda.status != "RASCUNHO":
            return Response(
                {"detail": "Apenas rascunhos podem ser pré-visualizados."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if demanda.autor_id != request.user.pk and getattr(request.user, "perfil", None) != "GESTOR":
            return Response(
                {"detail": "Sem permissão para este ofício."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            pdf_bytes = AssinaturaEletronicaService().obter_preview_pdf_bytes(demanda)
        except Exception:
            logger.exception("Falha stream preview PDF demanda %s", pk)
            return Response(
                {"detail": "Não foi possível gerar a pré-visualização do ofício."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        if not pdf_bytes:
            return Response(
                {"detail": "Pré-visualização indisponível."},
                status=status.HTTP_404_NOT_FOUND,
            )
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'inline; filename="oficio_demanda_{demanda.pk}_preview.pdf"'
        )
        return response

    def perform_create(self, serializer):
        """Associa o usuário logado como autor da nova demanda."""
        serializer.save(autor=self.request.user)

    @action(detail=True, methods=['post'])
    def enviar(self, request, pk=None):
        try:
            demanda = self.get_object()
            from core.services.envio_oficial_service import EnvioOficialService

            try:
                resultado = EnvioOficialService().enviar_demanda(
                    demanda,
                    request.user,
                    hash_documento=request.data.get("hash_documento"),
                    declaracao=request.data.get("declaracao"),
                    request=request,
                )
            except ValueError as exc:
                return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

            demanda.refresh_from_db()
            serializer = self.get_serializer(demanda)
            data = serializer.data
            data["assinatura_eletronica"] = resultado["assinatura_eletronica"]
            return Response(data)

        except Exception:
            logger.exception("Falha inesperada ao enviar demanda %s.", pk)
            return Response(
                {"erro": "Erro interno ao tentar enviar a demanda."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(
        detail=False,
        methods=["post"],
        url_path="preview-envio-lote",
        permission_classes=[IsAuthenticated],
    )
    def preview_envio_lote(self, request):
        from core.services.envio_oficial_service import EnvioOficialService

        ids_raw = request.data.get("demanda_ids") or []
        if not isinstance(ids_raw, list):
            return Response(
                {"detail": "demanda_ids deve ser uma lista."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            payload = EnvioOficialService().preparar_preview_lote(ids_raw, request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Falha preview envio lote")
            return Response(
                {"detail": "Não foi possível gerar a pré-visualização do lote."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(payload)

    @action(
        detail=False,
        methods=["post"],
        url_path="enviar-lote",
        permission_classes=[IsAuthenticated],
    )
    def enviar_lote(self, request):
        from core.services.envio_oficial_service import EnvioOficialService

        ids_raw = request.data.get("demanda_ids") or []
        if not isinstance(ids_raw, list):
            return Response(
                {"detail": "demanda_ids deve ser uma lista."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            resultado = EnvioOficialService().enviar_lote(
                request.user,
                demanda_ids=ids_raw,
                declaracao=request.data.get("declaracao"),
                hashes=request.data.get("hashes"),
                request=request,
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Falha envio lote")
            return Response(
                {"erro": "Erro interno ao tentar enviar o lote."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(resultado)

    def perform_update(self, serializer):
        instance = serializer.instance
        demanda = self.get_object()
        perfil = getattr(self.request.user, "perfil", None)

        if perfil == "VEREADOR":
            if demanda.autor_id != self.request.user.pk:
                raise PermissionDenied("Sem permissão para editar este rascunho.")
        elif demanda.status != "RASCUNHO" and self.action != "partial_update":
            raise PermissionDenied("Apenas rascunhos podem ser editados completamente.")

        serializer.save()
        instance.refresh_from_db()

        if instance.status == "RASCUNHO":
            from core.services.assinatura_eletronica_service import AssinaturaEletronicaService

            AssinaturaEletronicaService().invalidar_preview_envio(int(instance.pk))

    def perform_destroy(self, instance):
        if instance.status != 'RASCUNHO':
            raise PermissionDenied("Apenas rascunhos podem ser excluídos.")
        super().perform_destroy(instance)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def despachar(self, request, pk=None):
        try:
            demanda = self.get_object()

            if not request.user.perfil == 'PROTOCOLO':
                return Response({'detail': 'Você não tem permissão para despachar demandas.'}, status=status.HTTP_403_FORBIDDEN)

            if demanda.status != 'AGUARDANDO_PROTOCOLO':
                return Response({'detail': 'Apenas demandas aguardando protocolo podem ser despachadas.'}, status=status.HTTP_400_BAD_REQUEST)

            secretaria_id = request.data.get('secretaria_id')
            if not secretaria_id:
                return Response({'detail': 'O ID da secretaria de destino é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

            unidade_id = request.data.get('unidade_administrativa_id')

            try:
                orgao_id = int(secretaria_id)
            except (TypeError, ValueError):
                return Response({'detail': 'ID de secretaria inválido.'}, status=status.HTTP_400_BAD_REQUEST)

            from core.services.demanda_despacho_service import DemandaDespachoService

            try:
                DemandaDespachoService().despachar(
                    demanda,
                    secretaria_id=orgao_id,
                    usuario=request.user,
                    automatico=False,
                    unidade_administrativa_id=unidade_id,
                )
            except ValueError as exc:
                return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

            demanda.refresh_from_db()
            serializer = self.get_serializer(demanda)
            return Response(serializer.data)

        except Exception:
            logger.exception("Falha inesperada ao despachar demanda %s.", pk)
            return Response(
                {"erro": "Erro interno ao tentar despachar a demanda."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'], url_path='encaminhar-setor', permission_classes=[IsAuthenticated])
    def encaminhar_setor(self, request, pk=None):
        demanda = self.get_object()
        unidade_destino_id = request.data.get('unidade_administrativa_id')
        if not unidade_destino_id:
            return Response(
                {'detail': 'unidade_administrativa_id é obrigatório.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from core.services.tramitacao_setor_service import TramitacaoSetorService

        try:
            TramitacaoSetorService().encaminhar(
                demanda,
                unidade_destino_id=unidade_destino_id,
                usuario=request.user,
                observacao=str(request.data.get('observacao') or ''),
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        demanda.refresh_from_db()
        serializer = self.get_serializer(demanda)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def atualizar_status(self, request, pk=None):
        demanda = self.get_object()
        novo_status = request.data.get('status')
        status_permitidos = ['EM_EXECUCAO']

        if not novo_status or novo_status.upper() not in status_permitidos:
            return Response(
                {
                    'error': (
                        f'O status fornecido é inválido. Válidos: {status_permitidos}. '
                        'Para concluir a operação, use solicitar-devolutiva.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if getattr(request.user, 'perfil', None) != 'SECRETARIA':
            return Response(
                {'error': 'Apenas a secretaria responsável pode atualizar para em execução.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        from core.services.cluster_service import ClusterService

        cluster_svc = ClusterService()
        try:
            cluster_svc.exigir_lider_super_os(demanda)
        except ValueError as exc:
            info = cluster_svc.info_operacional_super_os(demanda)
            return Response(
                {'error': str(exc), 'super_os': info},
                status=status.HTTP_400_BAD_REQUEST,
            )

        status_antigo = demanda.get_status_display()
        demanda.status = novo_status.upper()
        demanda.save()
        status_novo = demanda.get_status_display()

        tramitacao = Tramitacao.objects.create(
            demanda=demanda,
            responsavel=request.user,
            tipo='STATUS_UPDATE',
            descricao=f'Status alterado de "{status_antigo}" para "{status_novo}".'
        )
        cluster_svc.propagar_tramitacao_no_cluster(tramitacao, usuario=request.user)

        serializer = self.get_serializer(demanda)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='solicitar-devolutiva', permission_classes=[IsAuthenticated])
    def solicitar_devolutiva(self, request, pk=None):
        demanda = self.get_object()
        from core.services.devolutiva_protocolo_service import DevolutivaProtocoloService

        try:
            DevolutivaProtocoloService().solicitar_devolutiva(
                demanda,
                request.user,
                parecer_operacional=str(request.data.get('parecer_operacional') or request.data.get('descricao') or ''),
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        demanda.refresh_from_db()
        return Response(self.get_serializer(demanda).data)

    @action(detail=True, methods=['post'], url_path='despachar-devolutiva', permission_classes=[IsAuthenticated])
    def despachar_devolutiva(self, request, pk=None):
        demanda = self.get_object()
        if getattr(request.user, 'perfil', None) not in ('PROTOCOLO', 'GESTOR') and not request.user.is_staff:
            return Response({'detail': 'Apenas o Protocolo pode despachar devolutiva.'}, status=status.HTTP_403_FORBIDDEN)

        from core.services.devolutiva_protocolo_service import DevolutivaProtocoloService

        try:
            DevolutivaProtocoloService().despachar_devolutiva(
                demanda,
                request.user,
                parecer_resposta=str(request.data.get('parecer_resposta') or request.data.get('descricao') or ''),
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        demanda.refresh_from_db()
        return Response(self.get_serializer(demanda).data)

    @action(detail=True, methods=['post'], url_path='encerrar-devolutiva', permission_classes=[IsAuthenticated])
    def encerrar_devolutiva(self, request, pk=None):
        demanda = self.get_object()
        perfil = getattr(request.user, 'perfil', None)
        if perfil == 'VEREADOR':
            return Response(
                {
                    'detail': (
                        'Use confirmar-ciencia para registrar ciência, gerar resposta ao cidadão '
                        'e encerrar.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        from core.services.devolutiva_protocolo_service import DevolutivaProtocoloService

        try:
            DevolutivaProtocoloService().encerrar_devolutiva(demanda, request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        demanda.refresh_from_db()
        return Response(self.get_serializer(demanda).data)

    @action(detail=True, methods=['get'], url_path='pacote-devolutiva', permission_classes=[IsAuthenticated])
    def pacote_devolutiva(self, request, pk=None):
        demanda = self.get_object()
        if demanda.status not in ('DEVOLVIDO_VEREADOR', 'FINALIZADO', 'AGUARDANDO_DEVOLUTIVA_PROTOCOLO'):
            return Response(
                {'detail': 'Pacote disponível apenas após devolutiva operacional.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from core.services.encerramento_legislativo_service import EncerramentoLegislativoService

        return Response(EncerramentoLegislativoService().montar_pacote_devolutiva(demanda))

    @action(detail=True, methods=['get'], url_path='preview-resposta-cidadao', permission_classes=[IsAuthenticated])
    def preview_resposta_cidadao(self, request, pk=None):
        demanda = self.get_object()
        if demanda.status != 'DEVOLVIDO_VEREADOR':
            return Response(
                {'detail': 'Pré-visualização disponível com devolutiva pendente ao vereador.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if demanda.autor_id != request.user.pk and getattr(request.user, 'perfil', None) not in ('GESTOR', 'PROTOCOLO'):
            return Response({'detail': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

        from core.services.encerramento_legislativo_service import EncerramentoLegislativoService

        texto = request.query_params.get('texto') or request.query_params.get('texto_resposta_cidadao') or ''
        pdf_bytes = EncerramentoLegislativoService().render_resposta_cidadao_pdf(
            demanda, texto_resposta=str(texto)
        )
        from django.http import HttpResponse

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="resposta_cidadao_{pk}.pdf"'
        return response

    @action(detail=True, methods=['post'], url_path='confirmar-ciencia', permission_classes=[IsAuthenticated])
    def confirmar_ciencia(self, request, pk=None):
        demanda = self.get_object()
        from core.services.encerramento_legislativo_service import EncerramentoLegislativoService

        try:
            EncerramentoLegislativoService().confirmar_ciencia(
                demanda,
                request.user,
                texto_resposta_cidadao=str(
                    request.data.get('texto_resposta_cidadao')
                    or request.data.get('texto')
                    or ''
                ),
                gerar_oficio=bool(request.data.get('gerar_oficio', True)),
                encerrar=bool(request.data.get('encerrar', True)),
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        demanda.refresh_from_db()
        return Response(self.get_serializer(demanda).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def solicitar_transferencia(self, request, pk=None):
        demanda = self.get_object()
        if (
            request.user.perfil != 'SECRETARIA'
            or not request.user.sinapse_orgao_id
            or demanda.sinapse_orgao_id != request.user.sinapse_orgao_id
        ):
            return Response({'detail': 'Apenas a secretaria de destino pode solicitar transferência.'}, status=status.HTTP_403_FORBIDDEN)

        demanda.status = 'AGUARDANDO_TRANSFERENCIA'
        demanda.save()

        orgao_nome = sinapse_catalog.get_orgao_nome(demanda.sinapse_orgao_id) or "Secretaria"
        Tramitacao.objects.create(
            demanda=demanda,
            responsavel=request.user,
            tipo='TRANSFERENCIA',
            descricao=f"A secretaria {orgao_nome} solicitou a transferência desta demanda."
        )
        return Response({'status': 'Solicitação de transferência enviada para o Protocolo.'})

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def aprovar_transferencia(self, request, pk=None):
        demanda = self.get_object()
        if not request.user.perfil == 'PROTOCOLO':
            return Response({'detail': 'Apenas o Protocolo pode aprovar transferências.'}, status=status.HTTP_403_FORBIDDEN)
        
        if demanda.status != 'AGUARDANDO_TRANSFERENCIA':
            return Response({'detail': 'Esta demanda não está aguardando transferência.'}, status=status.HTTP_400_BAD_REQUEST)

        nova_secretaria_id = request.data.get('nova_secretaria_id')
        if not nova_secretaria_id:
            return Response({'detail': 'O ID da nova secretaria é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            novo_orgao_id = int(nova_secretaria_id)
        except (TypeError, ValueError):
            return Response({'detail': 'ID da nova secretaria inválido.'}, status=status.HTTP_400_BAD_REQUEST)
        if not sinapse_catalog.orgao_existe(novo_orgao_id):
            return Response({'detail': 'Nova secretaria não encontrada no catálogo Sinapse.'}, status=status.HTTP_404_NOT_FOUND)

        secretaria_antiga_nome = sinapse_catalog.get_orgao_nome(demanda.sinapse_orgao_id) or "—"
        nova_nome = sinapse_catalog.get_orgao_nome(novo_orgao_id) or str(novo_orgao_id)
        demanda.sinapse_orgao_id = novo_orgao_id
        demanda.status = 'PROTOCOLADO'
        demanda.save()

        Tramitacao.objects.create(
            demanda=demanda,
            responsavel=request.user,
            tipo='TRANSFERENCIA',
            descricao=f"Transferência aprovada. Demanda movida da secretaria {secretaria_antiga_nome} para {nova_nome}."
        )
        return Response({'status': f'Demanda transferida para {nova_nome}.'})


class ServicoViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        orgao_id = request.query_params.get("orgao_id") or request.query_params.get("secretaria_id")
        orgao_filter = int(orgao_id) if orgao_id else None
        data = sinapse_catalog.list_servicos_api(orgao_id=orgao_filter)
        return Response(data)

    def retrieve(self, request, pk=None):
        servico = sinapse_catalog.servico_to_dict(sinapse_catalog.get_servico(int(pk)))
        if not servico:
            return Response({"detail": "Serviço não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        return Response(servico)


class AnexoViewSet(viewsets.ModelViewSet):
    queryset = Anexo.objects.all()
    serializer_class = AnexoSerializer
    parser_classes = (MultiPartParser, FormParser)
    http_method_names = ['post', 'delete']

class SecretariaViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        return Response(sinapse_catalog.list_orgaos_api())

    def retrieve(self, request, pk=None):
        orgao = sinapse_catalog.orgao_to_dict(sinapse_catalog.get_orgao(int(pk)))
        if not orgao:
            return Response({"detail": "Órgão não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        return Response(orgao)

class TramitacaoViewSet(viewsets.ModelViewSet):
    queryset = Tramitacao.objects.all().order_by('-timestamp')
    serializer_class = TramitacaoSerializer
    parser_classes = (MultiPartParser, FormParser)
    http_method_names = ['post']

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        arquivos = serializer.validated_data.pop('arquivos_anexos', [])
        unidade_destino_id = serializer.validated_data.pop('unidade_destino_id', None)

        demanda_id = serializer.validated_data.get("demanda")
        if demanda_id is not None:
            from core.models import Demanda
            from core.services.cluster_service import ClusterService

            try:
                demanda_alvo = (
                    demanda_id
                    if isinstance(demanda_id, Demanda)
                    else Demanda.objects.get(pk=demanda_id)
                )
            except Demanda.DoesNotExist:
                demanda_alvo = None
            if demanda_alvo is not None:
                cluster_svc = ClusterService()
                try:
                    cluster_svc.exigir_lider_super_os(demanda_alvo)
                except ValueError as exc:
                    return Response(
                        {
                            "detail": str(exc),
                            "super_os": cluster_svc.info_operacional_super_os(demanda_alvo),
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        tramitacao = serializer.save(responsavel=request.user)

        if unidade_destino_id:
            from core.models_unidade_administrativa import UnidadeAdministrativa
            from core.services.tramitacao_setor_service import TramitacaoSetorService

            try:
                unidade = UnidadeAdministrativa.objects.get(
                    pk=int(unidade_destino_id), ativo=True
                )
            except (UnidadeAdministrativa.DoesNotExist, TypeError, ValueError):
                tramitacao.delete()
                return Response(
                    {"detail": "Setor de destino não encontrado ou inativo."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            demanda = tramitacao.demanda
            origem = demanda.unidade_administrativa
            if origem and origem.pk == unidade.pk:
                tramitacao.unidade_destino = unidade
                tramitacao.save(update_fields=["unidade_destino"])
            else:
                svc = TramitacaoSetorService()
                if not svc.usuario_pode_tramitar(request.user, origem) and not svc.usuario_pode_tramitar(
                    request.user, unidade
                ):
                    if getattr(request.user, "perfil", None) == "SECRETARIA":
                        if request.user.sinapse_orgao_id != demanda.sinapse_orgao_id:
                            tramitacao.delete()
                            return Response(
                                {"detail": "Sem permissão para encaminhar demandas de outro órgão."},
                                status=status.HTTP_403_FORBIDDEN,
                            )
                    else:
                        tramitacao.delete()
                        return Response(
                            {"detail": "Sem permissão para encaminhar para este setor."},
                            status=status.HTTP_403_FORBIDDEN,
                        )
                orgao_novo = unidade.sinapse_orgao_id
                if orgao_novo and not sinapse_catalog.orgao_existe(int(orgao_novo)):
                    tramitacao.delete()
                    return Response(
                        {"detail": "Órgão do setor de destino não encontrado no catálogo Sinapse."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                tramitacao.unidade_origem = origem
                tramitacao.unidade_destino = unidade
                demanda.unidade_administrativa = unidade
                update_fields = ["unidade_administrativa"]
                if orgao_novo and orgao_novo != demanda.sinapse_orgao_id:
                    demanda.sinapse_orgao_id = orgao_novo
                    update_fields.append("sinapse_orgao_id")
                demanda.save(update_fields=update_fields)
                tramitacao.save(update_fields=["unidade_origem", "unidade_destino"])

        for arquivo in arquivos:
            AnexoTramitacao.objects.create(tramitacao=tramitacao, arquivo=arquivo)

        from core.services.cluster_service import ClusterService

        ClusterService().propagar_tramitacao_no_cluster(
            tramitacao, usuario=request.user
        )

        tramitacao.refresh_from_db()
        headers = self.get_success_headers(serializer.data)
        return Response(
            TramitacaoSerializer(tramitacao).data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )
    
class DashboardStatsAPIView(APIView):
    def get(self, request, *args, **kwargs):
        demandas_validas = Demanda.objects.exclude(status='RASCUNHO')
        status_aberto = [
            'AGUARDANDO_PROTOCOLO',
            'PROTOCOLADO',
            'EM_EXECUCAO',
            'AGUARDANDO_TRANSFERENCIA',
            'AGUARDANDO_DEVOLUTIVA_PROTOCOLO',
            'DEVOLVIDO_VEREADOR',
        ]
        autor_id = request.query_params.get('autor')
        secretaria_id = request.query_params.get('secretaria_destino')

        if autor_id:
            demandas_validas = demandas_validas.filter(autor_id=autor_id)
        
        if secretaria_id:
            demandas_validas = demandas_validas.filter(sinapse_orgao_id=secretaria_id)

        total_demandas = demandas_validas.count()
        demandas_abertas = demandas_validas.filter(status__in=status_aberto).count()
        demandas_concluidas = demandas_validas.filter(status='FINALIZADO').count()
        agora = timezone.now()
        demandas_com_vencimento = demandas_validas.filter(
            status__in=status_aberto,
            data_inicio_prazo__isnull=False,
        )
        demandas_atrasadas = sum(
            1
            for demanda in demandas_com_vencimento
            if demanda.prazo_dias() is not None
            and demanda.data_inicio_prazo + timedelta(days=demanda.prazo_dias()) < agora
        )

        por_orgao: dict[int, dict] = {}
        for row in demandas_validas.filter(sinapse_orgao_id__isnull=False).values(
            "sinapse_orgao_id", "status"
        ):
            oid = row["sinapse_orgao_id"]
            bucket = por_orgao.setdefault(oid, {"total": 0, "abertas": 0})
            bucket["total"] += 1
            if row["status"] in status_aberto:
                bucket["abertas"] += 1
        demandas_por_secretaria = sorted(
            [
                {
                    "secretaria_destino__nome": sinapse_catalog.get_orgao_nome(oid) or str(oid),
                    "total": vals["total"],
                    "abertas": vals["abertas"],
                }
                for oid, vals in por_orgao.items()
            ],
            key=lambda x: x["total"],
            reverse=True,
        )

        demandas_por_vereador = list(
            demandas_validas.filter(autor__perfil='VEREADOR')
            .values('autor__first_name', 'autor__last_name')
            .annotate(
                total=Count('id'),
                abertas=Count('id', filter=Q(status__in=status_aberto))
            ).order_by('-total')
        )

        status_protocolado = demandas_validas.filter(status='PROTOCOLADO').count()
        status_em_aberto_real = demandas_validas.filter(status__in=['AGUARDANDO_PROTOCOLO', 'EM_EXECUCAO', 'AGUARDANDO_TRANSFERENCIA']).count()
        demandas_por_status_agrupado = [
            {'status': 'Protocolado', 'total': status_protocolado},
            {'status': 'Em Aberto', 'total': status_em_aberto_real},
            {'status': 'Concluído', 'total': demandas_concluidas},
        ]

        demandas_mensais = list(
            demandas_validas.annotate(mes=TruncMonth('data_criacao'))
            .values('mes')
            .annotate(
                total=Count('id'),
                abertas=Count('id', filter=Q(status__in=status_aberto))
            ).order_by('mes')
        )

        for item in demandas_mensais:
            item['mes'] = item['mes'].strftime('%Y-%m')

        payload = {
            'kpis': {
                'total_demandas': total_demandas,
                'demandas_abertas': demandas_abertas,
                'demandas_concluidas': demandas_concluidas,
                'demandas_atrasadas': demandas_atrasadas
            },
            'por_secretaria': demandas_por_secretaria,
            'por_vereador': demandas_por_vereador,
            'por_status_agrupado': demandas_por_status_agrupado,
            'mensal': demandas_mensais,
        }

        perfil = getattr(request.user, 'perfil', None)
        if request.user.is_authenticated and perfil in ('GESTOR', 'PROTOCOLO'):
            from core.services.dashboard_trilha_service import DashboardTrilhaService

            trilha_svc = DashboardTrilhaService()
            autor_trilha = int(autor_id) if autor_id else None
            payload['trilhas'] = trilha_svc.calcular(
                demandas_qs=demandas_validas,
                autor_id=autor_trilha,
                data_inicio=request.query_params.get('data_inicio'),
                data_fim=request.query_params.get('data_fim'),
            )
            payload['trilhas_mensal'] = trilha_svc.mensal_por_trilha(demandas_validas)

        return Response(payload)


class CopilotoRecusasListAPIView(APIView):
    """GET /api/copiloto/recusas/ — itens bloqueados no Copiloto (Protocolo/Gestor)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        perfil = getattr(request.user, "perfil", None)
        if perfil not in ("GESTOR", "PROTOCOLO"):
            return Response(
                {"detail": "Sem permissão para consultar recusas do Copiloto."},
                status=status.HTTP_403_FORBIDDEN,
            )

        from core.services.dashboard_trilha_service import DashboardTrilhaService

        autor_id = request.query_params.get("autor")
        svc = DashboardTrilhaService()
        rows = svc.listar_recusas(
            autor_id=int(autor_id) if autor_id else None,
            motivo=request.query_params.get("motivo"),
            data_inicio=request.query_params.get("data_inicio"),
            data_fim=request.query_params.get("data_fim"),
        )
        return Response({"total": len(rows), "recusas": rows})


class DemandaLocationsAPIView(APIView):
    def get(self, request, *args, **kwargs):
        queryset = Demanda.objects.exclude(status='RASCUNHO').filter(
            latitude__isnull=False, 
            longitude__isnull=False
        )

        servico_id = request.query_params.get('servico_id')
        if servico_id:
            queryset = queryset.filter(sinapse_servico_id=servico_id)
            
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        data_inicio = request.query_params.get('data_inicio')
        if data_inicio:
            data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d')
            queryset = queryset.filter(data_criacao__gte=data_inicio_obj)
        
        data_fim = request.query_params.get('data_fim')
        if data_fim:
            data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1)
            queryset = queryset.filter(data_criacao__lt=data_fim_obj)
        
        if request.user.is_authenticated:
            if request.user.perfil == 'VEREADOR':
                queryset = queryset.filter(autor=request.user)
            elif request.user.perfil == 'SECRETARIA' and request.user.sinapse_orgao_id:
                queryset = queryset.filter(sinapse_orgao_id=request.user.sinapse_orgao_id)

        locations_data = []
        agora = timezone.now()
        status_aberto = [
            'AGUARDANDO_PROTOCOLO',
            'PROTOCOLADO',
            'EM_EXECUCAO',
            'AGUARDANDO_TRANSFERENCIA',
            'AGUARDANDO_DEVOLUTIVA_PROTOCOLO',
            'DEVOLVIDO_VEREADOR',
        ]

        for demanda in queryset:
            is_atrasada = False
            prazo = demanda.prazo_dias()
            if (
                demanda.status in status_aberto
                and demanda.data_inicio_prazo
                and prazo is not None
            ):
                is_atrasada = demanda.data_inicio_prazo + timedelta(days=prazo) < agora

            locations_data.append({
                'id': demanda.id,
                'lat': demanda.latitude,
                'lng': demanda.longitude,
                'titulo': demanda.titulo,
                'protocolo': demanda.protocolo_executivo or demanda.protocolo_legislativo,
                'status': demanda.status,
                'is_atrasada': is_atrasada
            })

        return Response(locations_data)
    
class CurrentUserAPIView(APIView):
    def get(self, request):
        serializer = UsuarioSerializer(request.user, context={'request': request})
        return Response(serializer.data)
    
class UsuarioViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Endpoint para listar usuários. Permite filtrar por perfil.
    """
    queryset = Usuario.objects.all().order_by('first_name', 'last_name')
    serializer_class = UsuarioSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    filter_backends = [DjangoFilterBackend]
    filterset_class = UsuarioFilter
    
class UserProfileView(APIView):
    """
    View para visualizar (GET) e atualizar (PATCH) o perfil do usuário logado.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Retorna os dados do perfil do usuário logado."""
        serializer = UserProfileSerializer(request.user, context={'request': request})
        return Response(serializer.data)

    def patch(self, request):
        """Atualiza os dados do perfil do usuário logado."""
        serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ChangePasswordView(APIView):
    """
    View para a troca de senha do usuário logado.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Action para trocar a senha do usuário."""
        serializer = ChangePasswordSerializer(data=request.data)

        if serializer.is_valid():
            user = request.user
            # Verifica a senha antiga
            if not user.check_password(serializer.validated_data['old_password']):
                return Response({'old_password': ['Senha antiga incorreta.']}, status=status.HTTP_400_BAD_REQUEST)
            
            # Define a nova senha
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response({'status': 'senha alterada com sucesso'}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class NotificacaoViewSet(viewsets.ModelViewSet):
    serializer_class = NotificacaoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Retorna apenas as notificações do usuário logado."""
        return Notificacao.objects.filter(destinatario=self.request.user)

    @action(detail=False, methods=['post'])
    def marcar_todas_como_lidas(self, request):
        """Marca todas as notificações do usuário como lidas."""
        self.get_queryset().update(lida=True)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def marcar_como_lida(self, request, pk=None):
        """Marca uma notificação específica como lida."""
        notificacao = self.get_object()
        notificacao.lida = True
        notificacao.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
class PasswordResetRequestView(APIView):
    """
    View pública para solicitar a redefinição de senha.
    Recebe um e-mail e envia um link de redefinição se o usuário existir.
    """
    permission_classes = [AllowAny] # <-- Torna este endpoint público

    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        
        if not email:
            return Response({'error': 'E-mail é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Lembre-se que seu model é Usuario
            user = Usuario.objects.get(email=email) 
        except Usuario.DoesNotExist:
            # Por segurança, não informamos que o e-mail não foi encontrado.
            return Response(status=status.HTTP_200_OK)

        # Gerar token de redefinição
        token_generator = PasswordResetTokenGenerator()
        token = token_generator.make_token(user)
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))

        FRONTEND_URL = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
        reset_link = f'{FRONTEND_URL}/resetar-senha/{uidb64}/{token}/'

        try:
            send_mail(
                subject='[SGDL] Redefinição de Senha',
                message=f'Olá {user.first_name},\n\n'
                        f'Você solicitou uma redefinição de senha. Clique no link abaixo para criar uma nova senha:\n\n'
                        f'{reset_link}\n\n'
                        f'Se você não solicitou isso, por favor ignore este e-mail.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
        except Exception:
            logger.exception("Falha ao enviar e-mail de redefinição para usuário %s.", user.id)
            return Response({'error': 'Não foi possível enviar o e-mail.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(status=status.HTTP_200_OK)
    
class PasswordResetConfirmView(APIView):
    """
    View pública para confirmar a redefinição de senha.
    Recebe uidb64, token e a nova senha.
    """
    permission_classes = [AllowAny]
    serializer_class = PasswordResetConfirmSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        uidb64 = serializer.validated_data['uidb64']
        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = Usuario.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, Usuario.DoesNotExist):
            return Response({'error': 'Link de redefinição inválido.'}, status=status.HTTP_400_BAD_REQUEST)

        token_generator = PasswordResetTokenGenerator()
        if not token_generator.check_token(user, token):
            return Response({'error': 'Link de redefinição inválido ou expirado.'}, status=status.HTTP_400_BAD_REQUEST)

        # Token é válido, redefinir a senha
        user.set_password(new_password)
        user.save()
        return Response({'status': 'Senha redefinida com sucesso.'}, status=status.HTTP_200_OK)