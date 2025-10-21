# /var/www/sgdl/backend/core/views.py

from datetime import datetime, timedelta
from rest_framework import viewsets, mixins, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView
from django.db.models import Count, Q
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models.functions import TruncMonth
from django.utils import timezone
from .models import Demanda, Servico, Anexo, Secretaria, Tramitacao, AnexoTramitacao, Usuario
from .serializers import DemandaSerializer, ServicoSerializer, AnexoSerializer, SecretariaSerializer, TramitacaoSerializer, AnexoTramitacaoSerializer, UsuarioSerializer, UserProfileSerializer, ChangePasswordSerializer
from .filters import DemandaFilter
from rest_framework.permissions import IsAuthenticated


class DemandaViewSet(viewsets.ModelViewSet):
    queryset = Demanda.objects.all().order_by('-data_criacao')
    serializer_class = DemandaSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = DemandaFilter

    def perform_create(self, serializer):
        """Associa o usuário logado como autor da nova demanda."""
        serializer.save(autor=self.request.user)

    @action(detail=True, methods=['post'])
    def enviar(self, request, pk=None):
        demanda = self.get_object()
        
        if demanda.status != 'RASCUNHO':
            return Response({'error': 'Esta demanda já foi enviada.'}, status=status.HTTP_400_BAD_REQUEST)

        servico = demanda.servico
        secretaria_destino = servico.secretaria_responsavel if servico else None
        
        ano_atual = timezone.now().year
        total_ano = Demanda.objects.filter(protocolo_legislativo__startswith=f'OFICIO-{ano_atual}').count()
        novo_numero = total_ano + 1
        protocolo_leg = f'OFICIO-{ano_atual}-{novo_numero:04d}'

        demanda.secretaria_destino = servico.secretaria_responsavel if servico else None
        demanda.protocolo_legislativo = protocolo_leg
        demanda.status = 'AGUARDANDO_PROTOCOLO'
        demanda.save()

        Tramitacao.objects.create(
            demanda=demanda,
            responsavel=request.user,
            tipo='ENVIO_OFICIAL',
            descricao=f'Demanda enviada oficialmente. Protocolo do Legislativo gerado: {protocolo_leg}.'
        )

        serializer = self.get_serializer(demanda)
        return Response(serializer.data)
    
    def perform_update(self, serializer):
        demanda = self.get_object()
        if demanda.status != 'RASCUNHO' and self.action != 'partial_update':
             raise PermissionDenied("Apenas rascunhos podem ser editados completamente.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.status != 'RASCUNHO':
            raise PermissionDenied("Apenas rascunhos podem ser excluídos.")
        super().perform_destroy(instance)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def despachar(self, request, pk=None):
        demanda = self.get_object()

        if not request.user.perfil == 'PROTOCOLO':
            return Response({'detail': 'Você não tem permissão para despachar demandas.'}, status=status.HTTP_403_FORBIDDEN)
        
        if demanda.status != 'AGUARDANDO_PROTOCOLO':
            return Response({'detail': 'Apenas demandas aguardando protocolo podem ser despachadas.'}, status=status.HTTP_400_BAD_REQUEST)

        secretaria_id = request.data.get('secretaria_id')
        if not secretaria_id:
            return Response({'detail': 'O ID da secretaria de destino é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            secretaria = Secretaria.objects.get(pk=secretaria_id)
        except Secretaria.DoesNotExist:
            return Response({'detail': 'Secretaria não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        ano_atual = datetime.now().year
        ultimo_protocolo = Demanda.objects.filter(protocolo_executivo__startswith=f'{ano_atual}-').count()
        novo_numero = ultimo_protocolo + 1
        protocolo_exec = f'{ano_atual}-{novo_numero:04d}'

        demanda.secretaria_destino = secretaria
        demanda.protocolo_executivo = protocolo_exec
        demanda.status = 'PROTOCOLADO'
        demanda.save()

        Tramitacao.objects.create(
            demanda=demanda,
            responsavel=request.user,
            tipo='DESPACHO',
            descricao=f'Demanda despachada para a secretaria: {secretaria.nome}. Protocolo do Executivo gerado: {protocolo_exec}.'
        )

        serializer = self.get_serializer(demanda)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def atualizar_status(self, request, pk=None):
        demanda = self.get_object()
        novo_status = request.data.get('status')
        status_permitidos = ['EM_EXECUCAO', 'FINALIZADO']

        if not novo_status or novo_status.upper() not in status_permitidos:
            return Response(
                {'error': f'O status fornecido é inválido. Válidos: {status_permitidos}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        status_antigo = demanda.get_status_display()
        demanda.status = novo_status.upper()
        demanda.save()
        status_novo = demanda.get_status_display()

        Tramitacao.objects.create(
            demanda=demanda,
            responsavel=request.user,
            tipo='STATUS_UPDATE',
            descricao=f'Status alterado de "{status_antigo}" para "{status_novo}".'
        )

        serializer = self.get_serializer(demanda)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def solicitar_transferencia(self, request, pk=None):
        demanda = self.get_object()
        if not request.user.perfil == 'SECRETARIA' or demanda.secretaria_destino != request.user.secretaria:
            return Response({'detail': 'Apenas a secretaria de destino pode solicitar transferência.'}, status=status.HTTP_403_FORBIDDEN)

        demanda.status = 'AGUARDANDO_TRANSFERENCIA'
        demanda.save()

        Tramitacao.objects.create(
            demanda=demanda,
            responsavel=request.user,
            tipo='TRANSFERENCIA',
            descricao=f"A secretaria {demanda.secretaria_destino.nome} solicitou a transferência desta demanda."
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
            nova_secretaria = Secretaria.objects.get(id=nova_secretaria_id)
        except Secretaria.DoesNotExist:
            return Response({'detail': 'Nova secretaria não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        
        secretaria_antiga_nome = demanda.secretaria_destino.nome
        demanda.secretaria_destino = nova_secretaria
        demanda.status = 'PROTOCOLADO'
        demanda.save()

        Tramitacao.objects.create(
            demanda=demanda,
            responsavel=request.user,
            tipo='TRANSFERENCIA',
            descricao=f"Transferência aprovada. Demanda movida da secretaria {secretaria_antiga_nome} para {nova_secretaria.nome}."
        )
        return Response({'status': f'Demanda transferida para {nova_secretaria.nome}.'})


class ServicoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Servico.objects.all().order_by('nome')
    serializer_class = ServicoSerializer

class AnexoViewSet(viewsets.ModelViewSet):
    queryset = Anexo.objects.all()
    serializer_class = AnexoSerializer
    parser_classes = (MultiPartParser, FormParser)
    http_method_names = ['post', 'delete']

class SecretariaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Secretaria.objects.all().order_by('nome')
    serializer_class = SecretariaSerializer

class TramitacaoViewSet(viewsets.ModelViewSet):
    queryset = Tramitacao.objects.all().order_by('-timestamp')
    serializer_class = TramitacaoSerializer
    parser_classes = (MultiPartParser, FormParser)
    http_method_names = ['post']

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        arquivos = serializer.validated_data.pop('arquivos_anexos', [])
        tramitacao = serializer.save(responsavel=request.user)

        for arquivo in arquivos:
            AnexoTramitacao.objects.create(tramitacao=tramitacao, arquivo=arquivo)
            
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
class DashboardStatsAPIView(APIView):
    def get(self, request, *args, **kwargs):
        demandas_validas = Demanda.objects.exclude(status='RASCUNHO')
        status_aberto = ['AGUARDANDO_PROTOCOLO', 'PROTOCOLADO', 'EM_EXECUCAO', 'AGUARDANDO_TRANSFERENCIA'] # Adicionado novo status
        autor_id = request.query_params.get('autor')
        secretaria_id = request.query_params.get('secretaria_destino')

        if autor_id:
            demandas_validas = demandas_validas.filter(autor_id=autor_id)
        
        if secretaria_id:
            demandas_validas = demandas_validas.filter(secretaria_destino_id=secretaria_id)

        total_demandas = demandas_validas.count()
        demandas_abertas = demandas_validas.filter(status__in=status_aberto).count()
        demandas_concluidas = demandas_validas.filter(status='FINALIZADO').count()
        data_limite = timezone.now() - timedelta(days=30)
        demandas_atrasadas = demandas_validas.filter(status__in=status_aberto, data_criacao__lt=data_limite).count()

        demandas_por_secretaria = list(
            demandas_validas.filter(secretaria_destino__isnull=False)
            .values('secretaria_destino__nome')
            .annotate(
                total=Count('id'),
                abertas=Count('id', filter=Q(status__in=status_aberto))
            ).order_by('-total')
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

        data = {
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
        return Response(data)

class DemandaLocationsAPIView(APIView):
    def get(self, request, *args, **kwargs):
        queryset = Demanda.objects.exclude(status='RASCUNHO').filter(
            latitude__isnull=False, 
            longitude__isnull=False
        )

        tipo_servico = request.query_params.get('tipo_servico')
        if tipo_servico:
            queryset = queryset.filter(servico__tipo=tipo_servico)

        servico_id = request.query_params.get('servico_id')
        if servico_id:
            queryset = queryset.filter(servico_id=servico_id)
            
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
            elif request.user.perfil == 'SECRETARIA':
                queryset = queryset.filter(secretaria_destino=request.user.secretaria)

        locations_data = []
        data_limite_atraso = timezone.now() - timedelta(days=30)

        for demanda in queryset:
            is_atrasada = (
                demanda.status not in ['FINALIZADO', 'CANCELADO'] and 
                demanda.data_criacao < data_limite_atraso
            )
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
    
    def get_queryset(self):
        queryset = super().get_queryset()
        perfil = self.request.query_params.get('perfil')
        if perfil:
            queryset = queryset.filter(perfil=perfil)
        return queryset
    
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