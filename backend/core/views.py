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
from .services.demanda_visibilidade import aplicar_escopo_demanda, aplicar_escopo_rascunho
from .services.chatbot_service import ChatbotService
from .serializers import ( DemandaSerializer, DemandaPainelListSerializer, ServicoSerializer, AnexoSerializer, SecretariaSerializer, CustomTokenObtainPairSerializer, PasswordResetConfirmSerializer,
    TramitacaoSerializer, AnexoTramitacaoSerializer, UsuarioSerializer, UserProfileSerializer, ChangePasswordSerializer, NotificacaoSerializer,
    ChatInteracaoSerializer,
)
from .filters import DemandaFilter, UsuarioFilter
from .pagination import DemandaListPagination
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
        fonte = request.data.get("fonte")
        confirmar_local = request.data.get("confirmar_local")
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
        if confirmar_local is not None and not isinstance(confirmar_local, bool):
            confirmar_local = str(confirmar_local).strip().lower() in {"1", "true", "yes", "sim"}
        try:
            payload = ChatbotService().atualizar_localizacao_demanda(
                usuario=request.user,
                session_id=str(session_id),
                indice_demanda=indice_i,
                latitude=lat_f,
                longitude=lng_f,
                fonte=str(fonte) if fonte else "gps_dispositivo",
                confirmar_local=confirmar_local,
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


class ChatAtualizarIndicacaoCopilotoAPIView(APIView):
    """POST /api/v1/chat/atualizar-indicacao/ — vereadores e número no rascunho (perfil CAMARA)."""

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
        raw_ids = request.data.get("vereadores_vinculados_ids")
        vereadores_ids = None
        if raw_ids is not None:
            if not isinstance(raw_ids, list):
                return Response(
                    {"detail": "vereadores_vinculados_ids deve ser uma lista."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            vereadores_ids = raw_ids
        autor_vereador_id = request.data.get("autor_vereador_id")
        numero = request.data.get("numero_indicacao")
        numero_i = None
        if numero is not None and numero != "":
            try:
                numero_i = int(numero)
            except (TypeError, ValueError):
                return Response({"detail": "numero_indicacao inválido."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            payload = ChatbotService().atualizar_metadados_indicacao_copiloto(
                usuario=request.user,
                session_id=str(session_id),
                indice_demanda=indice_i,
                vereadores_vinculados_ids=vereadores_ids,
                autor_vereador_id=autor_vereador_id,
                numero_indicacao=numero_i,
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


class ChatRevisarEtapaAPIView(APIView):
    """POST /api/v1/chat/revisar-etapa/ — reabre etapa (pedido|servico|local|anexos) para edição."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        session_id = request.data.get("session_id")
        indice = request.data.get("indice_demanda")
        etapa = request.data.get("etapa")
        if not session_id:
            return Response({"detail": "session_id é obrigatório."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            indice_i = int(indice)
        except (TypeError, ValueError):
            return Response({"detail": "indice_demanda inválido."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            payload = ChatbotService().revisar_etapa_copiloto(
                usuario=request.user,
                session_id=str(session_id),
                indice_demanda=indice_i,
                etapa=str(etapa or ""),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError:
            return Response(
                {"detail": "Sessão inexistente ou não pertence ao usuário."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(payload, status=status.HTTP_200_OK)


class ChatEditarPedidoAPIView(APIView):
    """POST /api/v1/chat/editar-pedido/ — atualiza relato/título de uma solicitação."""

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
            payload = ChatbotService().editar_pedido_demanda(
                usuario=request.user,
                session_id=str(session_id),
                indice_demanda=indice_i,
                titulo=request.data.get("titulo"),
                descricao=request.data.get("descricao"),
                pedido_integral=request.data.get("pedido_integral"),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError:
            return Response(
                {"detail": "Sessão inexistente ou não pertence ao usuário."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(payload, status=status.HTTP_200_OK)


class ChatEditarLocalAPIView(APIView):
    """POST /api/v1/chat/editar-local/ — atualiza endereço estruturado de uma solicitação."""

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
        endereco = request.data.get("endereco")
        if not isinstance(endereco, dict):
            endereco = {
                k: request.data.get(k)
                for k in ("cep", "logradouro", "numero", "bairro", "complemento")
                if request.data.get(k) not in (None, "")
            }
        try:
            payload = ChatbotService().editar_local_demanda(
                usuario=request.user,
                session_id=str(session_id),
                indice_demanda=indice_i,
                endereco=endereco or None,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError:
            return Response(
                {"detail": "Sessão inexistente ou não pertence ao usuário."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(payload, status=status.HTTP_200_OK)


class ChatRemoverAnexoSessaoAPIView(APIView):
    """POST /api/v1/chat/remover-anexo-sessao/ — remove anexo já enviado na sessão do copiloto."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        session_id = request.data.get("session_id")
        indice = request.data.get("indice_sessao")
        if not session_id:
            return Response({"detail": "session_id é obrigatório."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            indice_i = int(indice)
        except (TypeError, ValueError):
            return Response({"detail": "indice_sessao inválido."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            payload = ChatbotService().remover_anexo_sessao_copiloto(
                usuario=request.user,
                session_id=str(session_id),
                indice_sessao=indice_i,
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

        corpus_sid_raw = request.data.get("corpus_sinapse_servico_id")
        corpus_sinapse_servico_id = None
        if corpus_sid_raw not in (None, ""):
            try:
                corpus_sinapse_servico_id = int(corpus_sid_raw)
            except (TypeError, ValueError):
                return Response(
                    {"corpus_sinapse_servico_id": "Identificador de serviço inválido."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        corpus_atalho_id = (request.data.get("corpus_atalho_id") or "").strip() or None

        try:
            payload = ChatbotService().interagir(
                usuario=request.user,
                session_id=sid,
                mensagem=mensagem,
                anexos_upload=anexos,
                anexo_demanda_indices=anexo_indices or None,
                indices_aprovados=indices_aprovados,
                corpus_sinapse_servico_id=corpus_sinapse_servico_id,
                corpus_atalho_id=corpus_atalho_id,
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


def _resposta_acesso_protocolo_central(user, mensagem: str = "Acesso restrito ao Protocolo."):
    """403 se o usuário não for Protocolo, gestor SGAC ou gestor geral."""
    from core.services.gestor_escopo import usuario_pode_painel_protocolo_central

    if usuario_pode_painel_protocolo_central(user) or getattr(user, "is_staff", False):
        return None
    return Response({"detail": mensagem}, status=status.HTTP_403_FORBIDDEN)


class DemandaViewSet(viewsets.ModelViewSet):
    queryset = Demanda.objects.select_related(
        "tendencia", "autor", "cluster"
    ).order_by("-data_criacao")
    serializer_class = DemandaSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = DemandaFilter
    pagination_class = DemandaListPagination

    _DESC_SIMILARES_MAX = 280

    def get_serializer_class(self):
        if self.action == "list":
            return DemandaPainelListSerializer
        return DemandaSerializer

    def get_serializer_context(self):
        return super().get_serializer_context()

    def _aplicar_filtros_cluster_listagem(self, qs):
        """Oculta seguidoras na listagem; retrieve/detalhe mantém escopo completo."""
        perfil = getattr(self.request.user, "perfil", None)
        if perfil == "SECRETARIA":
            from core.services.cluster_service import ClusterService

            return ClusterService().filtrar_listagem_apenas_lideres(qs)
        if perfil == "PROTOCOLO":
            from core.services.cluster_service import ClusterService

            return ClusterService().filtrar_seguidoras_integradas(qs)
        return qs

    def get_queryset(self):
        qs = Demanda.objects.select_related(
            "tendencia", "autor", "cluster", "unidade_administrativa"
        )
        qs = aplicar_escopo_demanda(qs, self.request.user)
        fila = (self.request.query_params.get("fila") or "").strip().lower()
        if fila in ("protocolados", "operacionais", "devolutivas", "finalizados", "stand_by"):
            from core.services.gestor_escopo import usuario_pode_acessar_fila_demanda

            if not usuario_pode_acessar_fila_demanda(self.request.user, fila):
                return qs.none()
        if fila in ("protocolados", "operacionais", "devolutivas", "finalizados", "stand_by"):
            if fila == "finalizados":
                qs = qs.prefetch_related("assinaturas_eletronicas").order_by(
                    "-data_finalizacao", "-data_criacao"
                )
            else:
                qs = qs.prefetch_related("assinaturas_eletronicas").order_by(
                    "data_entrada_etapa", "data_criacao"
                )
            if fila == "operacionais":
                from core.services.acompanhamento_demanda_service import (
                    filtrar_demandas_acompanhando,
                )
                from core.services.demanda_visibilidade import (
                    aplicar_escopo_fila_operacional,
                    aplicar_escopo_fila_operacional_gestor_setorial,
                    filtrar_demandas_em_operacao_gestor_setorial,
                    filtrar_demandas_em_operacao_setor,
                    filtrar_demandas_encerrado_setor,
                    filtrar_demandas_minha_unidade,
                )
                from core.services.gestor_escopo import (
                    TIPO_SETORIAL,
                    tipo_gestor,
                    usuario_pode_painel_protocolo_central,
                )

                escopo_setor = (
                    self.request.query_params.get("escopo_setor") or "em_operacao"
                ).strip().lower()
                perfil = getattr(self.request.user, "perfil", None)
                painel_protocolo_central = usuario_pode_painel_protocolo_central(
                    self.request.user
                )
                gestor_setorial = (
                    perfil == "GESTOR"
                    and tipo_gestor(self.request.user) == TIPO_SETORIAL
                    and not painel_protocolo_central
                )

                if escopo_setor == "acompanhando":
                    qs = filtrar_demandas_acompanhando(qs, self.request.user)
                elif escopo_setor == "encerrado" and (
                    perfil == "SECRETARIA" or gestor_setorial
                ):
                    qs = filtrar_demandas_encerrado_setor(qs, self.request.user)
                elif escopo_setor == "em_operacao" and perfil == "SECRETARIA":
                    qs = aplicar_escopo_fila_operacional(qs, self.request.user)
                    qs = filtrar_demandas_em_operacao_setor(qs, self.request.user)
                elif escopo_setor == "em_operacao" and gestor_setorial:
                    qs = aplicar_escopo_fila_operacional_gestor_setorial(
                        qs, self.request.user
                    )
                    qs = filtrar_demandas_em_operacao_gestor_setorial(
                        qs, self.request.user
                    )
                elif perfil == "GESTOR" and not painel_protocolo_central:
                    qs = aplicar_escopo_fila_operacional(qs, self.request.user)
                    unidade_id = self.request.query_params.get("unidade_administrativa")
                    if unidade_id:
                        try:
                            qs = qs.filter(unidade_administrativa_id=int(unidade_id))
                        except (TypeError, ValueError):
                            pass
                    elif self.request.query_params.get("minha_unidade") in (
                        "1",
                        "true",
                        "True",
                    ):
                        qs = filtrar_demandas_minha_unidade(qs, self.request.user)
            if self.action == "list":
                qs = self._aplicar_filtros_cluster_listagem(qs)
            from core.services.demanda_visibilidade import (
                filtrar_demandas_por_unidades,
                parse_unidades_administrativas_request,
            )

            parsed_uas = parse_unidades_administrativas_request(self.request)
            if parsed_uas:
                qs = filtrar_demandas_por_unidades(qs, parsed_uas)
            return qs
        qs = qs.order_by("-data_criacao")
        if self.action == "list":
            qs = self._aplicar_filtros_cluster_listagem(qs)
        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
        else:
            serializer = self.get_serializer(queryset, many=True)
            response = Response(serializer.data)

        if request.query_params.get("include_resumo") in ("1", "true", "True"):
            from core.services.consulta_hub_service import ConsultaHubService
            from core.services.gestor_escopo import usuario_pode_painel_protocolo_central

            perfil = getattr(request.user, "perfil", None)
            if (
                perfil in ("PROTOCOLO", "GESTOR")
                and isinstance(response.data, dict)
                and usuario_pode_painel_protocolo_central(request.user)
            ):
                response.data["resumo_filas"] = ConsultaHubService().resumo_painel_protocolo(
                    request.user
                )
        return response

    @action(
        detail=False,
        methods=["get"],
        url_path="resumo-filas",
        permission_classes=[IsAuthenticated],
    )
    def resumo_filas(self, request):
        """Contadores das filas do painel Protocolo/Gestor (sem carregar registros)."""
        perfil = getattr(request.user, "perfil", None)
        if perfil not in ("PROTOCOLO", "GESTOR"):
            return Response(
                {"detail": "Resumo de filas disponível apenas para Protocolo e Gestor."},
                status=status.HTTP_403_FORBIDDEN,
            )
        from core.services.consulta_hub_service import ConsultaHubService
        from core.services.gestor_escopo import usuario_pode_painel_protocolo_central

        if not usuario_pode_painel_protocolo_central(request.user):
            return Response(
                {"detail": "Resumo de filas central disponível apenas para Protocolo e gestor central."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(ConsultaHubService().resumo_painel_protocolo(request.user))

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
        qs = aplicar_escopo_demanda(qs, request.user)

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
        url_path="clusters-vinculo",
        permission_classes=[IsAuthenticated],
    )
    def clusters_vinculo(self, request, pk=None):
        """Grupos Super OS ativos nos quais esta demanda pode ser vinculada manualmente."""
        from core.models import ClusterExecucao
        from core.services.cluster_service import ClusterService
        from core.views_cluster import _aplicar_escopo_clusters, _pode_gerir_cluster

        if not _pode_gerir_cluster(request.user):
            return Response(
                {"detail": "Sem permissão para vincular demandas a grupos Super OS."},
                status=status.HTTP_403_FORBIDDEN,
            )
        demanda = self.get_object()
        q = (request.query_params.get("q") or "").strip() or None
        try:
            limit = min(int(request.query_params.get("limit", 20)), 50)
        except (TypeError, ValueError):
            limit = 20
        svc = ClusterService()
        candidatos = svc.listar_clusters_para_vincular_demanda(demanda, q=q, limit=limit)
        if candidatos:
            ids = [c["id"] for c in candidatos]
            permitidos = set(
                _aplicar_escopo_clusters(
                    ClusterExecucao.objects.filter(pk__in=ids), request.user
                ).values_list("pk", flat=True)
            )
            candidatos = [c for c in candidatos if c["id"] in permitidos]
        return Response(
            {
                "demanda_id": demanda.pk,
                "demanda_titulo": demanda.titulo,
                "demanda_protocolo": demanda.protocolo_legislativo or demanda.protocolo_executivo,
                "total": len(candidatos),
                "results": candidatos,
            }
        )

    @action(
        detail=True,
        methods=["get"],
        url_path="cluster-situacao-aderencia",
        permission_classes=[IsAuthenticated],
    )
    def cluster_situacao_aderencia(self, request, pk=None):
        """Situação para decisão do Protocolo: integrar ao líder ou despacho individual."""
        if getattr(request.user, "perfil", None) != "PROTOCOLO":
            return Response(
                {"detail": "Apenas o Protocolo pode consultar aderência ao cluster."},
                status=status.HTTP_403_FORBIDDEN,
            )
        from core.services.cluster_aderencia_service import ClusterAderenciaService

        demanda = self.get_object()
        return Response(ClusterAderenciaService().situacao_aderencia(demanda))

    @action(
        detail=True,
        methods=["post"],
        url_path="cluster-aderir-lider",
        permission_classes=[IsAuthenticated],
    )
    def cluster_aderir_lider(self, request, pk=None):
        """Integra demanda seguidora ao processo líder (espelho completo)."""
        if getattr(request.user, "perfil", None) != "PROTOCOLO":
            return Response(
                {"detail": "Apenas o Protocolo pode integrar demandas ao cluster."},
                status=status.HTTP_403_FORBIDDEN,
            )
        from core.services.cluster_aderencia_service import (
            ClusterAderenciaError,
            ClusterAderenciaService,
        )

        demanda = self.get_object()
        from django.db import IntegrityError

        from django.db import IntegrityError

        try:
            demanda = ClusterAderenciaService().aderir_ao_processo_lider(
                demanda, usuario=request.user
            )
        except ClusterAderenciaError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except IntegrityError:
            return Response(
                {"detail": "Não foi possível integrar: conflito de dados do processo."},
                status=status.HTTP_409_CONFLICT,
            )
        except IntegrityError:
            return Response(
                {"detail": "Não foi possível integrar: conflito de dados do processo."},
                status=status.HTTP_409_CONFLICT,
            )

        demanda.refresh_from_db()
        serializer = self.get_serializer(demanda)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["post"],
        url_path="cluster-desvincular",
        permission_classes=[IsAuthenticated],
    )
    def cluster_desvincular(self, request, pk=None):
        """Remove demanda do cluster para despacho individual."""
        if getattr(request.user, "perfil", None) != "PROTOCOLO":
            return Response(
                {"detail": "Apenas o Protocolo pode desvincular demandas do cluster."},
                status=status.HTTP_403_FORBIDDEN,
            )
        from core.services.cluster_service import ClusterService

        demanda = self.get_object()
        try:
            ClusterService().desvincular_demanda_manual(demanda, usuario=request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        demanda.refresh_from_db()
        return Response(self.get_serializer(demanda).data)

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
            from core.services.copiloto_duplicidade_service import alertas_duplicidade_para_demanda

            preview = AssinaturaEletronicaService().preparar_preview_envio(demanda)
            preview.update(alertas_duplicidade_para_demanda(demanda, request.user))
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

    @action(
        detail=False,
        methods=["get"],
        url_path="gestores-protocolo",
        permission_classes=[IsAuthenticated],
    )
    def gestores_protocolo(self, request):
        from core.services.assinatura_eletronica_service import AssinaturaEletronicaService

        if getattr(request.user, "perfil", None) not in ("PROTOCOLO", "GESTOR") and not request.user.is_staff:
            return Response(
                {"detail": "Acesso restrito ao Protocolo."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(AssinaturaEletronicaService().listar_gestores_protocolo())

    @action(
        detail=True,
        methods=["post"],
        url_path="preview-despacho",
        permission_classes=[IsAuthenticated],
    )
    def preview_despacho(self, request, pk=None):
        from core.models_assinatura_eletronica import AssinaturaEletronica
        from core.services.assinatura_eletronica_service import AssinaturaEletronicaService
        from core.services.demanda_despacho_destinos import (
            normalizar_destinos_multi_orgao,
            resolve_destinos_despacho,
        )
        from core.services.demanda_despacho_service import proximo_protocolo_executivo
        from integrations import sinapse_catalog

        demanda = self.get_object()
        if getattr(request.user, "perfil", None) != "PROTOCOLO":
            return Response({"detail": "Apenas o Protocolo pode despachar."}, status=status.HTTP_403_FORBIDDEN)
        if demanda.status != "AGUARDANDO_PROTOCOLO":
            return Response(
                {"detail": "Demanda não está aguardando protocolo."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            destinos_raw = resolve_destinos_despacho(demanda, request.data)
            plano = normalizar_destinos_multi_orgao(demanda, destinos_raw)
            destinos = plano["destinos"]
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        primeira = destinos[0]
        unidade_id = primeira.get("unidade_administrativa_id")
        try:
            preview = AssinaturaEletronicaService().preparar_assinatura_despacho_inicial(
                demanda,
                secretaria_id=int(primeira["secretaria_id"]),
                unidade_administrativa_id=int(unidade_id) if unidade_id else None,
                protocolo_executivo=proximo_protocolo_executivo(),
                destinos=destinos,
            )
        except (TypeError, ValueError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        preview["gestores_protocolo"] = AssinaturaEletronicaService().listar_gestores_protocolo()
        preview["signatario_operador"] = AssinaturaEletronicaService().resumo_signatario(
            request.user, AssinaturaEletronica.PAPEL_OPERADOR
        )
        preview["modo_assinatura"] = AssinaturaEletronicaService().modo_assinatura_protocolo(
            request.user
        )
        if preview["modo_assinatura"] == "gestor_apenas":
            preview["signatario_gestor"] = AssinaturaEletronicaService().resumo_signatario(
                request.user, AssinaturaEletronica.PAPEL_GESTOR_PROTOCOLO
            )
        preview["destinos"] = destinos
        preview["multi_secretaria"] = len(destinos) > 1
        orgao_competente_id = plano.get("orgao_competente_id")
        preview["orgao_competente_id"] = orgao_competente_id
        preview["orgao_competente_nome"] = (
            sinapse_catalog.get_orgao_nome(orgao_competente_id) if orgao_competente_id else None
        )
        integrados = plano.get("orgaos_integrados_ids") or []
        preview["orgaos_integrados"] = [
            {
                "sinapse_orgao_id": oid,
                "orgao_nome": sinapse_catalog.get_orgao_nome(oid) or str(oid),
            }
            for oid in integrados
        ]
        return Response(preview)

    @action(
        detail=True,
        methods=["post"],
        url_path="preview-conclusao-secretaria",
        permission_classes=[IsAuthenticated],
    )
    def preview_conclusao_secretaria(self, request, pk=None):
        from core.models_assinatura_eletronica import AssinaturaEletronica
        from core.services.assinatura_eletronica_service import AssinaturaEletronicaService

        demanda = self.get_object()
        perfil = getattr(request.user, "perfil", None)
        if perfil not in ("SECRETARIA", "GESTOR"):
            return Response(
                {"detail": "Apenas Secretaria ou Gestor setorial podem assinar a conclusão operacional."},
                status=status.HTTP_403_FORBIDDEN,
            )
        assinatura_svc = AssinaturaEletronicaService()
        if not assinatura_svc.usuario_pode_assinar_conclusao(request.user, demanda):
            return Response(
                {
                    "detail": (
                        "Apenas a chefia responsável pelo setor da demanda "
                        "pode assinar a conclusão operacional."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        if demanda.status != "EM_EXECUCAO":
            return Response(
                {"detail": "A conclusão só pode ser assinada com a demanda em execução."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        parecer = str(request.data.get("parecer_operacional") or request.data.get("descricao") or "")
        try:
            preview = assinatura_svc.preparar_assinatura_conclusao_secretaria(
                demanda, parecer_operacional=parecer
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        preview["signatario_chefia"] = assinatura_svc.resumo_signatario(
            request.user, AssinaturaEletronica.PAPEL_CHEFIA_SETOR
        )
        return Response(preview)

    @action(
        detail=True,
        methods=["post"],
        url_path="preview-despacho-devolutiva",
        permission_classes=[IsAuthenticated],
    )
    def preview_despacho_devolutiva(self, request, pk=None):
        from core.models_assinatura_eletronica import AssinaturaEletronica
        from core.services.assinatura_eletronica_service import AssinaturaEletronicaService

        demanda = self.get_object()
        negado = _resposta_acesso_protocolo_central(
            request.user, "Apenas o Protocolo pode despachar devolutiva."
        )
        if negado:
            return negado
        parecer = str(request.data.get("parecer_resposta") or request.data.get("descricao") or "")
        try:
            preview = AssinaturaEletronicaService().preparar_assinatura_despacho_devolutiva(
                demanda, parecer_resposta=parecer
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        preview["gestores_protocolo"] = AssinaturaEletronicaService().listar_gestores_protocolo()
        preview["signatario_operador"] = AssinaturaEletronicaService().resumo_signatario(
            request.user, AssinaturaEletronica.PAPEL_OPERADOR
        )
        preview["modo_assinatura"] = AssinaturaEletronicaService().modo_assinatura_protocolo(
            request.user, contexto="devolutiva"
        )
        return Response(preview)

    def perform_create(self, serializer):
        """Associa o usuário logado como autor da nova demanda."""
        user = self.request.user
        extra = {}
        if getattr(user, "perfil", None) == "CAMARA":
            extra["tipo_legislativo"] = Demanda.TIPO_LEGISLATIVO_INDICACAO
        demanda = serializer.save(autor=user, **extra)
        self._sincronizar_vinculos_indicacao(demanda)

    def perform_update(self, serializer):
        demanda = serializer.save()
        self._sincronizar_vinculos_indicacao(demanda)

    def _sincronizar_vinculos_indicacao(self, demanda):
        if demanda.tipo_legislativo != Demanda.TIPO_LEGISLATIVO_INDICACAO:
            return
        from core.services.indicacao_service import sincronizar_vinculos_vereador

        data = getattr(self.request, "data", {}) or {}
        if "vereadores_vinculados_ids" not in data and "autor_vereador_id" not in data:
            return
        ids = data.get("vereadores_vinculados_ids")
        if ids is None:
            ids = list(
                demanda.vinculos_vereador.values_list("vereador_id", flat=True)
            )
        try:
            sincronizar_vinculos_vereador(
                demanda,
                ids if isinstance(ids, list) else [],
                autor_vereador_id=data.get("autor_vereador_id"),
            )
        except ValueError as exc:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"vereadores_vinculados_ids": str(exc)}) from exc

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
    
    @action(
        detail=True,
        methods=['post'],
        permission_classes=[IsAuthenticated],
        parser_classes=[MultiPartParser, FormParser, JSONParser],
    )
    def despachar(self, request, pk=None):
        try:
            demanda = self.get_object()

            if not request.user.perfil == 'PROTOCOLO':
                return Response({'detail': 'Você não tem permissão para despachar demandas.'}, status=status.HTTP_403_FORBIDDEN)

            if demanda.status != 'AGUARDANDO_PROTOCOLO':
                return Response({'detail': 'Apenas demandas aguardando protocolo podem ser despachadas.'}, status=status.HTTP_400_BAD_REQUEST)

            from core.services.assinatura_eletronica_service import AssinaturaEletronicaService
            from core.services.demanda_despacho_destinos import resolve_destinos_despacho

            try:
                destinos = resolve_destinos_despacho(demanda, request.data)
            except ValueError as exc:
                return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

            texto_despacho = str(
                request.data.get("descricao")
                or request.data.get("texto_despacho")
                or request.data.get("parecer")
                or ""
            )

            arquivos = request.FILES.getlist("arquivos_anexos") or request.FILES.getlist("anexos")

            assinatura_svc = AssinaturaEletronicaService()
            try:
                from django.db import transaction

                pending = assinatura_svc._validar_hash_pending(
                    int(demanda.pk),
                    "DESPACHO_INICIAL",
                    request.data.get("hash_documento"),
                )
                contexto = dict(pending.get("payload") or {})
                contexto["destinos"] = destinos
                contexto["texto_despacho"] = texto_despacho
                contexto["protocolo_executivo"] = contexto.get("protocolo_executivo") or pending[
                    "payload"
                ].get("protocolo_executivo")
                staging_id = assinatura_svc._criar_tramitacao_staging_anexos(
                    demanda, request.user, arquivos or None
                )
                if staging_id:
                    contexto["tramitacao_staging_id"] = staging_id

                with transaction.atomic():
                    assinaturas = assinatura_svc.registrar_assinaturas_despacho_inicial(
                        demanda,
                        request.user,
                        hash_documento=pending["hash_documento"],
                        declaracao_operador=request.data.get("declaracao")
                        or request.data.get("declaracao_operador"),
                        gestor_usuario_id=request.data.get("gestor_protocolo_id"),
                        declaracao_gestor=request.data.get("declaracao_gestor"),
                        contexto_operacao=contexto,
                        request=request,
                    )
            except ValueError as exc:
                return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

            demanda.refresh_from_db()
            serializer = self.get_serializer(demanda)
            data = serializer.data
            data["aguardando_validacao_gestor"] = False
            data["assinaturas_registradas"] = [
                {"codigo_validacao": a.codigo_validacao, "papel": a.papel} for a in assinaturas
            ]
            data["mensagem"] = "Despacho registrado e executado com sucesso."
            return Response(data)

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
        perfil = getattr(request.user, "perfil", None)
        if perfil not in ("SECRETARIA", "GESTOR"):
            return Response(
                {"detail": "Apenas Secretaria ou Gestor setorial podem solicitar devolutiva."},
                status=status.HTTP_403_FORBIDDEN,
            )
        from core.services.assinatura_eletronica_service import AssinaturaEletronicaService
        from core.services.assinatura_etapa_executor_service import (
            ACAO_CONCLUSAO_SECRETARIA_FLUXO_DIRETO,
        )

        assinatura_svc = AssinaturaEletronicaService()
        if not assinatura_svc.usuario_pode_assinar_conclusao(request.user, demanda):
            return Response(
                {
                    "detail": (
                        "Apenas a chefia responsável pelo setor da demanda "
                        "pode assinar a conclusão operacional."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        parecer = str(request.data.get('parecer_operacional') or request.data.get('descricao') or '')
        try:
            pending = assinatura_svc._validar_hash_pending(
                int(demanda.pk),
                "CONCLUSAO_SECRETARIA",
                request.data.get("hash_documento"),
            )
            from core.services.estudo_viabilidade_service import EstudoViabilidadeService
            from core.services.assinatura_etapa_executor_service import ACAO_CONCLUSAO_SECRETARIA

            estudo_payload = EstudoViabilidadeService.parse_payload_request(
                dict(request.data) if hasattr(request.data, "items") else {}
            )
            contexto = {"parecer_operacional": parecer, "acao_executiva": ACAO_CONCLUSAO_SECRETARIA}
            if estudo_payload is not None:
                contexto["resultado_operacional"] = estudo_payload

            assinatura = assinatura_svc.registrar_assinatura_conclusao_secretaria(
                demanda,
                request.user,
                hash_documento=pending["hash_documento"],
                declaracao=request.data.get("declaracao"),
                contexto_operacao=contexto,
                request=request,
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        demanda.refresh_from_db()
        data = self.get_serializer(demanda).data
        data["assinatura_registrada"] = {"codigo_validacao": assinatura.codigo_validacao}
        data["aguardando_validacao_gestor"] = True
        data["mensagem"] = (
            "Assinatura registrada. A conclusão só será encaminhada após validação do gestor "
            "do setor em Assinaturas pendentes."
        )
        return Response(data)

    @action(
        detail=True,
        methods=['post'],
        url_path='despachar-devolutiva',
        permission_classes=[IsAuthenticated],
        parser_classes=[MultiPartParser, FormParser, JSONParser],
    )
    def despachar_devolutiva(self, request, pk=None):
        demanda = self.get_object()
        negado = _resposta_acesso_protocolo_central(
            request.user, "Apenas o Protocolo pode despachar devolutiva."
        )
        if negado:
            return negado

        from django.db import transaction

        from core.services.assinatura_eletronica_service import AssinaturaEletronicaService
        from core.services.devolutiva_protocolo_service import (
            DevolutivaProtocoloService,
            _parse_destinos,
            _parse_ids,
        )

        parecer = str(request.data.get('parecer_resposta') or request.data.get('descricao') or '')
        arquivos = request.FILES.getlist("arquivos_anexos") or request.FILES.getlist("anexos")
        anexos_ids = _parse_ids(request.data.get("anexos_tramitacao_ids"))
        alerta_destinos = _parse_destinos(request.data.get("alerta_destinos"))
        assinatura_apenas_gestor = bool(request.data.get("assinatura_apenas_gestor"))
        try:
            with transaction.atomic():
                assinatura_svc = AssinaturaEletronicaService()
                contexto = {
                    "parecer_resposta": parecer,
                    "anexos_tramitacao_ids": anexos_ids,
                    "alerta_destinos": alerta_destinos,
                }
                staging_id = assinatura_svc._criar_tramitacao_staging_anexos(
                    demanda, request.user, arquivos or None
                )
                if staging_id:
                    contexto["tramitacao_staging_id"] = staging_id

                assinaturas = assinatura_svc.registrar_assinaturas_despacho_devolutiva(
                    demanda,
                    request.user,
                    hash_documento=request.data.get("hash_documento"),
                    declaracao_operador=request.data.get("declaracao") or request.data.get("declaracao_operador"),
                    gestor_usuario_id=request.data.get("gestor_protocolo_id"),
                    declaracao_gestor=request.data.get("declaracao_gestor"),
                    assinatura_apenas_gestor=assinatura_apenas_gestor,
                    validacao_id=request.data.get("validacao_id"),
                    contexto_operacao=contexto,
                    request=request,
                )
                if assinatura_apenas_gestor and not request.data.get("validacao_id"):
                    DevolutivaProtocoloService().despachar_devolutiva(
                        demanda,
                        request.user,
                        parecer_resposta=parecer,
                        arquivos_anexos=arquivos or None,
                        anexos_tramitacao_ids=anexos_ids or None,
                        alerta_destinos=alerta_destinos or None,
                    )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        demanda.refresh_from_db()
        data = self.get_serializer(demanda).data
        data["assinaturas_registradas"] = [
            {"codigo_validacao": a.codigo_validacao, "papel": a.papel} for a in assinaturas
        ]
        if not assinatura_apenas_gestor:
            data["aguardando_validacao_gestor"] = True
            data["mensagem"] = (
                "Assinatura registrada. A devolutiva só será enviada ao vereador "
                "após validação do gestor do protocolo em Assinaturas pendentes."
            )
        return Response(data)

    @action(
        detail=True,
        methods=['get'],
        url_path='anexos-operacionais',
        permission_classes=[IsAuthenticated],
    )
    def anexos_operacionais(self, request, pk=None):
        demanda = self.get_object()
        negado = _resposta_acesso_protocolo_central(
            request.user, "Apenas o Protocolo pode listar anexos operacionais."
        )
        if negado:
            return negado
        from core.services.tramitacao_anexo_service import listar_anexos_operacionais_demanda

        return Response(listar_anexos_operacionais_demanda(demanda))

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
        negado = _resposta_acesso_protocolo_central(
            request.user, "Apenas o Protocolo pode encerrar devolutiva."
        )
        if negado:
            return negado
        from core.services.devolutiva_protocolo_service import DevolutivaProtocoloService

        try:
            DevolutivaProtocoloService().encerrar_devolutiva(demanda, request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        demanda.refresh_from_db()
        return Response(self.get_serializer(demanda).data)

    @action(detail=True, methods=['post'], url_path='acompanhar', permission_classes=[IsAuthenticated])
    def acompanhar(self, request, pk=None):
        from core.services.acompanhamento_demanda_service import (
            AcompanhamentoDemandaError,
            AcompanhamentoDemandaService,
        )
        from core.models_acompanhamento import DemandaAcompanhamento

        demanda = self.get_object()
        svc = AcompanhamentoDemandaService()
        origem = (request.data.get('origem') or DemandaAcompanhamento.ORIGEM_MANUAL).strip().upper()
        if origem not in dict(DemandaAcompanhamento.ORIGEM_CHOICES):
            origem = DemandaAcompanhamento.ORIGEM_MANUAL
        no_id = request.data.get('no_operacional_id')
        try:
            no_operacional_id = int(no_id) if no_id not in (None, '') else None
        except (TypeError, ValueError):
            no_operacional_id = None
        try:
            svc.acompanhar(
                request.user,
                demanda,
                origem=origem,
                no_operacional_id=no_operacional_id,
            )
        except AcompanhamentoDemandaError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        demanda.refresh_from_db()
        return Response(self.get_serializer(demanda).data)

    @action(detail=True, methods=['post'], url_path='desacompanhar', permission_classes=[IsAuthenticated])
    def desacompanhar(self, request, pk=None):
        from core.services.acompanhamento_demanda_service import AcompanhamentoDemandaService

        demanda = self.get_object()
        svc = AcompanhamentoDemandaService()
        if not svc.desacompanhar(request.user, demanda):
            return Response(
                {'detail': 'Você não acompanha este processo.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        demanda.refresh_from_db()
        return Response(self.get_serializer(demanda).data)

    @action(detail=True, methods=['get'], url_path='pacote-devolutiva', permission_classes=[IsAuthenticated])
    def pacote_devolutiva(self, request, pk=None):
        from core.services.tramitacao_visibilidade_service import (
            status_permite_pacote_devolutiva_vereador,
        )

        demanda = self.get_object()
        perfil = getattr(request.user, "perfil", None)
        if perfil == "VEREADOR" and not status_permite_pacote_devolutiva_vereador(demanda.status):
            return Response(
                {'detail': 'Pacote disponível após devolutiva do Protocolo ao vereador.'},
                status=status.HTTP_403_FORBIDDEN,
            )
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
        if demanda.status not in ('DEVOLVIDO_VEREADOR', 'FINALIZADO'):
            return Response(
                {'detail': 'Pré-visualização disponível após devolutiva ao vereador.'},
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
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    http_method_names = ['post', 'patch', 'delete']

    def _tramitacao_com_escopo(self, pk):
        from core.services.demanda_visibilidade import usuario_pode_acessar_demanda

        tramitacao = Tramitacao.objects.select_related("demanda").filter(pk=pk).first()
        if tramitacao is None:
            return None
        if not usuario_pode_acessar_demanda(self.request.user, tramitacao.demanda):
            return None
        return tramitacao

    def partial_update(self, request, pk=None):
        from core.services.tramitacao_janela_edicao_service import TramitacaoJanelaEdicaoService

        tramitacao = self._tramitacao_com_escopo(pk)
        if tramitacao is None:
            return Response({"detail": "Tramitação não encontrada."}, status=status.HTTP_404_NOT_FOUND)
        if not TramitacaoJanelaEdicaoService.usuario_pode_corrigir(request.user, tramitacao):
            return Response(
                {"detail": "Prazo para correção expirado ou sem permissão."},
                status=status.HTTP_403_FORBIDDEN,
            )
        descricao = request.data.get("descricao")
        if descricao is None or not str(descricao).strip():
            return Response(
                {"detail": "Informe a descrição corrigida."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        tramitacao = TramitacaoJanelaEdicaoService.atualizar_descricao(
            tramitacao, str(descricao)
        )
        tramitacao.refresh_from_db()
        editavel_ate = tramitacao.editavel_ate
        return Response(
            {
                "id": tramitacao.pk,
                "descricao": tramitacao.descricao,
                "editavel_ate": editavel_ate.isoformat() if editavel_ate else None,
                "pode_editar": TramitacaoJanelaEdicaoService.usuario_pode_corrigir(
                    request.user, tramitacao
                ),
                "segundos_restantes_edicao": TramitacaoJanelaEdicaoService.segundos_restantes(
                    tramitacao
                ),
                "aguardando_validacao_gestor": TramitacaoJanelaEdicaoService.tramitacao_aguardando_gestor(
                    tramitacao
                ),
            }
        )

    def destroy(self, request, pk=None):
        import logging

        from django.db import IntegrityError

        from core.services.tramitacao_janela_edicao_service import TramitacaoJanelaEdicaoService

        logger = logging.getLogger(__name__)
        tramitacao = self._tramitacao_com_escopo(pk)
        if tramitacao is None:
            return Response({"detail": "Tramitação não encontrada."}, status=status.HTTP_404_NOT_FOUND)
        if not TramitacaoJanelaEdicaoService.usuario_pode_corrigir(request.user, tramitacao):
            return Response(
                {"detail": "Prazo para desfazer expirado ou sem permissão."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            TramitacaoJanelaEdicaoService.excluir_tramitacao(tramitacao)
        except IntegrityError:
            logger.exception("Falha ao desfazer tramitação pk=%s", pk)
            return Response(
                {"detail": "Não foi possível desfazer o andamento. Tente novamente ou contate o suporte."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

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
            TramitacaoSerializer(tramitacao, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )
    
class DashboardStatsAPIView(APIView):
    def get(self, request, *args, **kwargs):
        from core.services.indicacao_service import agregar_demandas_por_vereador

        demandas_validas = aplicar_escopo_demanda(Demanda.objects.all(), request.user)
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

        demandas_por_vereador = agregar_demandas_por_vereador(demandas_validas, status_aberto)

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
    """Pontos georreferenciados para o mapa operacional (MapaCalorView)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        from core.services.mapa_demanda_service import filtrar_demandas_mapa, serializar_locations

        super_os_only = request.query_params.get('super_os') in ('1', 'true', 'True')
        queryset = filtrar_demandas_mapa(request)
        locations_data = serializar_locations(queryset, super_os_only=super_os_only)

        return Response({
            'count': len(locations_data),
            'results': locations_data,
            'resumo': {
                'total': len(locations_data),
                'atrasadas': sum(1 for x in locations_data if x['is_atrasada']),
                'super_os': sum(1 for x in locations_data if x['super_os']['ativo']),
            },
        })


class DemandaMapAgregacaoAPIView(APIView):
    """Agregação espacial/sazonal bairro × serviço × mês (E3.2)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        from core.services.mapa_demanda_service import agregar_espacial_sazonal, filtrar_demandas_mapa

        queryset = filtrar_demandas_mapa(request)
        super_os_only = request.query_params.get('super_os') in ('1', 'true', 'True')
        return Response(agregar_espacial_sazonal(queryset, super_os_only=super_os_only))

    
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