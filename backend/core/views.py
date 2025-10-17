# /var/www/sgdl/backend/core/views.py

from datetime import timedelta
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
from .models import Demanda, Servico, Anexo, Secretaria, Tramitacao, AnexoTramitacao
from .serializers import DemandaSerializer, ServicoSerializer, AnexoSerializer, SecretariaSerializer, TramitacaoSerializer, AnexoTramitacaoSerializer, UsuarioSerializer 
from .filters import DemandaFilter 

class DemandaViewSet(viewsets.ModelViewSet):
    queryset = Demanda.objects.all().order_by('-data_criacao')
    serializer_class = DemandaSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = DemandaFilter

    @action(detail=True, methods=['post'])
    def enviar(self, request, pk=None):
        demanda = self.get_object()
        
        # Validação: só pode enviar se for um rascunho
        if demanda.status != 'RASCUNHO':
            return Response({'error': 'Esta demanda já foi enviada.'}, status=status.HTTP_400_BAD_REQUEST)

        # Lógica que antes estava no perform_create
        servico = demanda.servico
        secretaria_destino = servico.secretaria_responsavel if servico else None
        
        ano_atual = timezone.now().year
        total_ano = Demanda.objects.filter(protocolo_legislativo__startswith=f'OFICIO-{ano_atual}').count()
        novo_numero = total_ano + 1
        protocolo_leg = f'OFICIO-{ano_atual}-{novo_numero:04d}'

        # Atualiza a demanda
        demanda.secretaria_destino = servico.secretaria_responsavel if servico else None
        demanda.protocolo_legislativo = protocolo_leg
        demanda.status = 'AGUARDANDO_PROTOCOLO'
        demanda.save()

        usuario_da_acao = request.user if request.user.is_authenticated else None
        Tramitacao.objects.create(
            demanda=demanda,
            usuario=usuario_da_acao,
            tipo='ENVIO_OFICIAL',
            descricao=f'Demanda enviada oficialmente. Protocolo do Legislativo gerado: {protocolo_leg}.'
        )

        # Retorna a demanda atualizada
        serializer = self.get_serializer(demanda)
        return Response(serializer.data)
    
    def perform_update(self, serializer):
        demanda = self.get_object()
        if demanda.status != 'RASCUNHO':
            raise PermissionDenied("Apenas rascunhos podem ser editados.")
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        if instance.status != 'RASCUNHO':
            raise PermissionDenied("Apenas rascunhos podem ser excluídos.")
        super().perform_destroy(instance)
    
    @action(detail=True, methods=['post'])
    def despachar(self, request, pk=None):
        demanda = self.get_object()
        secretaria_id = request.data.get('secretaria_id')

        if not secretaria_id:
            return Response({'error': 'O ID da secretaria de destino é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)
        
        if demanda.status != 'AGUARDANDO_PROTOCOLO':
            return Response({'error': 'Apenas demandas aguardando protocolo podem ser despachadas.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            secretaria = Secretaria.objects.get(pk=secretaria_id)
        except Secretaria.DoesNotExist:
            return Response({'error': 'Secretaria não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        
        ano_atual = timezone.now().year
        total_ano = Demanda.objects.filter(protocolo_executivo__startswith=f'PROTOCOLO-{ano_atual}').count()
        novo_numero = total_ano + 1
        protocolo_exec = f'PROTOCOLO-{ano_atual}-{novo_numero:04d}'

        demanda.secretaria_destino = secretaria
        demanda.protocolo_executivo = protocolo_exec
        demanda.status = 'PROTOCOLADO'
        demanda.save()

        usuario_da_acao = request.user if request.user.is_authenticated else None
        Tramitacao.objects.create(
            demanda=demanda,
            usuario=usuario_da_acao,
            tipo='DESPACHO',
            descricao=f'Demanda despachada para a secretaria: {secretaria.nome}. Protocolo do Executivo gerado: {protocolo_exec}.'
        )

        serializer = self.get_serializer(demanda)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def atualizar_status(self, request, pk=None):
        demanda = self.get_object()
        novo_status = request.data.get('status')

        # Lista de status permitidos para atualização por esta rota
        status_permitidos = ['EM_EXECUCAO', 'FINALIZADO']

        if not novo_status or novo_status.upper() not in status_permitidos:
            return Response(
                {'error': f'O status fornecido é inválido. Válidos: {status_permitidos}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        status_antigo = demanda.get_status_display() # Pega o nome legível (ex: "Protocolado")
        demanda.status = novo_status.upper()
        demanda.save()
        status_novo = demanda.get_status_display()

        usuario_da_acao = request.user if request.user.is_authenticated else None
        Tramitacao.objects.create(
            demanda=demanda,
            usuario=usuario_da_acao,
            tipo='STATUS_UPDATE',
            descricao=f'Status alterado de "{status_antigo}" para "{status_novo}".'
        )

        serializer = self.get_serializer(demanda)
        return Response(serializer.data)
    
class ServicoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Este endpoint fornece uma lista de todos os serviços disponíveis.
    """
    queryset = Servico.objects.all().order_by('nome')
    serializer_class = ServicoSerializer

class AnexoViewSet(viewsets.ModelViewSet):
    """
    Endpoint para criar (POST) e excluir (DELETE) anexos.
    """
    queryset = Anexo.objects.all()
    serializer_class = AnexoSerializer
    parser_classes = (MultiPartParser, FormParser)
    
    http_method_names = ['post', 'delete']

class SecretariaViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Endpoint que fornece uma lista de todas as secretarias.
    """
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
        usuario_da_acao = request.user if request.user.is_authenticated else None
        tramitacao = serializer.save(usuario=usuario_da_acao)

        for arquivo in arquivos:
            AnexoTramitacao.objects.create(tramitacao=tramitacao, arquivo=arquivo)
            
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
class DashboardStatsAPIView(APIView):
    """
    Fornece dados agregados e complexos para o dashboard do gestor.
    """
    def get(self, request, *args, **kwargs):
        # Base de consulta: todas as demandas que não são mais rascunho.
        demandas_validas = Demanda.objects.exclude(status='RASCUNHO')
        status_aberto = ['AGUARDANDO_PROTOCOLO', 'PROTOCOLADO', 'EM_EXECUCAO']
        autor_id = request.query_params.get('autor')
        secretaria_id = request.query_params.get('secretaria_destino')

        if autor_id:
            demandas_validas = demandas_validas.filter(autor_id=autor_id)
        
        if secretaria_id:
            demandas_validas = demandas_validas.filter(secretaria_destino_id=secretaria_id)

        # 1. KPIs dos Cards
        total_demandas = demandas_validas.count()
        demandas_abertas = demandas_validas.filter(status__in=status_aberto).count()
        demandas_concluidas = demandas_validas.filter(status='FINALIZADO').count()
        data_limite = timezone.now() - timedelta(days=30)
        demandas_atrasadas = demandas_validas.filter(status__in=status_aberto, data_criacao__lt=data_limite).count()

        # 2. Gráfico por Secretarias (Total vs. Abertas)
        demandas_por_secretaria = list(
            demandas_validas.filter(secretaria_destino__isnull=False)
            .values('secretaria_destino__nome')
            .annotate(
                total=Count('id'),
                abertas=Count('id', filter=Q(status__in=status_aberto))
            ).order_by('-total')
        )

        # 3. Gráfico por Vereadores (Total vs. Abertas)
        demandas_por_vereador = list(
            demandas_validas.filter(autor__perfil='VEREADOR')
            .values('autor__first_name', 'autor__last_name')
            .annotate(
                total=Count('id'),
                abertas=Count('id', filter=Q(status__in=status_aberto))
            ).order_by('-total')
        )

        # 4. Gráfico por Status (Doughnut)
        status_protocolado = demandas_validas.filter(status='PROTOCOLADO').count()
        # 'Aberto' aqui significa 'Aguardando Protocolo' + 'Em Execução'
        status_em_aberto_real = demandas_validas.filter(status__in=['AGUARDANDO_PROTOCOLO', 'EM_EXECUCAO']).count()
        demandas_por_status_agrupado = [
            {'status': 'Protocolado', 'total': status_protocolado},
            {'status': 'Em Aberto', 'total': status_em_aberto_real},
            {'status': 'Concluído', 'total': demandas_concluidas},
        ]

        # 5. Gráfico Linear Mensal
        demandas_mensais = list(
            demandas_validas.annotate(mes=TruncMonth('data_criacao'))
            .values('mes')
            .annotate(
                total=Count('id'),
                abertas=Count('id', filter=Q(status__in=status_aberto))
            ).order_by('mes')
        )

        # Formata o resultado para o frontend
        # (Converte a data para uma string 'YYYY-MM')
        for item in demandas_mensais:
            item['mes'] = item['mes'].strftime('%Y-%m')

        # Monta a resposta final
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

# /backend/core/views.py
from datetime import timedelta
from django.utils import timezone

class DemandaLocationsAPIView(APIView):
    """
    Fornece dados de localização enriquecidos com status e indicador de atraso.
    """
    def get(self, request, *args, **kwargs):
        queryset = Demanda.objects.exclude(status='RASCUNHO').filter(
            latitude__isnull=False, 
            longitude__isnull=False
        )

        # --- Lógica de Filtro (Adicionando filtro de status) ---
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
        data_fim = request.query_params.get('data_fim')
        if data_inicio:
            queryset = queryset.filter(data_criacao__gte=datetime.fromisoformat(data_inicio))
        if data_fim:
            queryset = queryset.filter(data_criacao__lte=datetime.fromisoformat(data_fim))
        # --- Fim da Lógica de Filtro ---

        locations_data = []
        data_limite_atraso = timezone.now() - timedelta(days=30) # Define "atraso" como > 30 dias

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
        serializer = UsuarioSerializer(request.user)
        return Response(serializer.data)