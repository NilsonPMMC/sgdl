# /var/www/sgdl/backend/core/serializers.py

from datetime import datetime, timedelta
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import serializers
from django.conf import settings
from django.utils import timezone
import logging

from .models import (
    ClusterExecucao,
    Demanda,
    Usuario,
    Anexo,
    Tramitacao,
    AnexoTramitacao,
    Notificacao,
    Tendencia,
    TendenciaOcorrencia,
)
from .models_fluxo_protocolo import ServicoFluxoProtocolo
from .models_unidade_administrativa import (
    UnidadeAdministrativa,
    UnidadeAdministrativaResponsavel,
)
from .models_depara_rm import DeParaRmSinapse
from .models_assunto_carta import AssuntoCarta
from .models_copiloto_faq import CopilotoFaqOrientacao, CopilotoFaqPadraoRegex
from .models_config import ConfiguracaoCarta, ConfiguracaoOficio
from integrations.models import SinapseServiceSync
from integrations import sinapse_catalog

logger = logging.getLogger(__name__)


class UserProfileSerializer(serializers.ModelSerializer):
    secretaria = serializers.SerializerMethodField()
    vinculo_secretaria = serializers.SerializerMethodField()
    vinculo_gestor = serializers.SerializerMethodField()
    atuacao_sgdl = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = [
            'id', 'username', 'first_name', 'last_name', 'email',
            'avatar', 'cargo', 'telefone', 'ramal',
            'assinatura', 'assinatura_imagem', 'perfil', 'secretaria', 'sinapse_orgao_id',
            'vinculo_secretaria', 'vinculo_gestor', 'is_staff', 'is_superuser',
            'atuacao_sgdl',
        ]
        read_only_fields = [
            'username', 'perfil', 'secretaria', 'sinapse_orgao_id',
            'vinculo_secretaria', 'vinculo_gestor', 'is_staff', 'is_superuser',
            'atuacao_sgdl',
        ]

    def get_secretaria(self, obj: Usuario):
        return sinapse_catalog.orgao_to_dict(
            sinapse_catalog.get_orgao(obj.sinapse_orgao_id)
        )

    def get_vinculo_secretaria(self, obj: Usuario) -> dict:
        from core.services.usuario_vinculo_service import UsuarioVinculoService

        return UsuarioVinculoService().status_vinculo_secretaria(obj)

    def get_vinculo_gestor(self, obj: Usuario) -> dict:
        from core.services.usuario_vinculo_service import UsuarioVinculoService

        return UsuarioVinculoService().status_vinculo_gestor(obj)

    def get_atuacao_sgdl(self, obj: Usuario) -> dict:
        from core.services.usuario_vinculo_service import UsuarioVinculoService

        return UsuarioVinculoService().atuacao_sgdl(obj)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)


class UsuarioSerializer(serializers.ModelSerializer):
    secretaria = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = [
            'id', 'username', 'first_name', 'last_name',
            'perfil', 'secretaria', 'sinapse_orgao_id', 'avatar',
            'cargo', 'telefone', 'ramal', 'assinatura',
        ]

    def get_secretaria(self, obj: Usuario):
        orgao = sinapse_catalog.get_orgao(obj.sinapse_orgao_id)
        if not orgao:
            return obj.sinapse_orgao_id
        return orgao.id


class SecretariaSerializer(serializers.Serializer):
    """Órgão do catálogo Sinapse (compatível com API legada `secretarias/`)."""

    id = serializers.IntegerField()
    nome = serializers.CharField()


class ServicoSerializer(serializers.Serializer):
    """Serviço do catálogo Sinapse (compatível com API legada `servicos/`)."""

    id = serializers.IntegerField()
    nome = serializers.CharField()
    tipo = serializers.CharField()
    prazo = serializers.IntegerField(allow_null=True)
    secretaria_responsavel = SecretariaSerializer(allow_null=True)


class AnexoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Anexo
        fields = '__all__'
        read_only_fields = ['id', 'data_upload']

    def validate(self, attrs):
        arquivo = attrs.get("arquivo") or getattr(self.instance, "arquivo", None)
        demanda = attrs.get("demanda") or getattr(self.instance, "demanda", None)
        if arquivo and demanda:
            from pathlib import Path

            from core.services.anexo_validacao_service import (
                coletar_nomes_anexos_demanda,
                normalizar_nome_arquivo,
                validar_nome_arquivo_novo,
            )

            nomes = coletar_nomes_anexos_demanda(demanda)
            if self.instance and self.instance.pk and self.instance.arquivo:
                nomes.discard(normalizar_nome_arquivo(Path(self.instance.arquivo.name).name))
            validar_nome_arquivo_novo(nomes, getattr(arquivo, "name", ""))
        return attrs


class AnexoTramitacaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnexoTramitacao
        fields = ['id', 'arquivo']


class TramitacaoSerializer(serializers.ModelSerializer):
    responsavel = UsuarioSerializer(read_only=True)
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    anexos = AnexoTramitacaoSerializer(many=True, read_only=True)
    arquivos_anexos = serializers.ListField(
        child=serializers.FileField(), write_only=True, required=False
    )
    unidade_destino_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    unidade_destino = serializers.SerializerMethodField()
    acao_no = serializers.SerializerMethodField()
    orgao_id = serializers.SerializerMethodField()
    orgao_nome = serializers.SerializerMethodField()
    setor_nome = serializers.SerializerMethodField()
    no_id = serializers.SerializerMethodField()
    destinos = serializers.SerializerMethodField()

    class Meta:
        model = Tramitacao
        fields = [
            'id',
            'demanda',
            'responsavel',
            'tipo',
            'tipo_display',
            'descricao',
            'timestamp',
            'anexos',
            'arquivos_anexos',
            'unidade_destino_id',
            'unidade_destino',
            'acao_no',
            'orgao_id',
            'orgao_nome',
            'setor_nome',
            'no_id',
            'destinos',
        ]
        extra_kwargs = {
            'demanda': {'write_only': True},
        }

    def _meta_tramitacao(self, obj: Tramitacao) -> dict:
        raw = obj.metadata
        return raw if isinstance(raw, dict) else {}

    def get_acao_no(self, obj: Tramitacao):
        return self._meta_tramitacao(obj).get("acao_no")

    def get_orgao_id(self, obj: Tramitacao):
        meta = self._meta_tramitacao(obj)
        oid = meta.get("orgao_id")
        return int(oid) if oid not in (None, "") else None

    def get_orgao_nome(self, obj: Tramitacao):
        return self._meta_tramitacao(obj).get("orgao_nome")

    def get_setor_nome(self, obj: Tramitacao):
        meta = self._meta_tramitacao(obj)
        sid = meta.get("setor_id")
        if sid in (None, ""):
            return None
        from core.models_unidade_administrativa import UnidadeAdministrativa

        ua = UnidadeAdministrativa.objects.filter(pk=int(sid)).first()
        if ua:
            return ua.sigla or ua.nome
        return meta.get("setor_nome")

    def get_no_id(self, obj: Tramitacao):
        meta = self._meta_tramitacao(obj)
        nid = meta.get("no_id")
        return int(nid) if nid not in (None, "") else None

    def get_destinos(self, obj: Tramitacao):
        from core.services.scatter_gather_service import _enriquecer_destinos_scatter

        destinos = self._meta_tramitacao(obj).get("destinos")
        if not isinstance(destinos, list) or not destinos:
            return []
        return _enriquecer_destinos_scatter(destinos)

    def get_unidade_destino(self, obj: Tramitacao):
        unidade = obj.unidade_destino
        if not unidade:
            return None
        return {
            "id": unidade.pk,
            "nome": unidade.nome,
            "sigla": unidade.sigla,
        }


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    remember_me = serializers.BooleanField(write_only=True, required=False)
    portal = serializers.CharField(write_only=True, required=False, allow_blank=True)

    @classmethod
    def get_token(cls, user):
        return super().get_token(user)

    def validate(self, attrs):
        data = super().validate(attrs)
        from core.services.auth_portal_service import assert_portal_permitido

        portal = self.initial_data.get("portal") or attrs.get("portal")
        assert_portal_permitido(portal, self.user)
        remember_me = self.initial_data.get('remember_me', False)
        if remember_me:
            logger.debug("Autenticação com remember_me habilitado.")
            refresh = self.get_token(self.user)
            refresh.set_exp(
                lifetime=settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME_REMEMBER_ME']
            )
            data['refresh'] = str(refresh)
        return data


class PasswordResetConfirmSerializer(serializers.Serializer):
    uidb64 = serializers.CharField(required=True)
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, write_only=True)


class ClusterResumoSerializer(serializers.ModelSerializer):
    """Resumo leve para listagem de demandas."""

    demandas_count = serializers.SerializerMethodField()

    class Meta:
        model = ClusterExecucao
        fields = (
            "id",
            "titulo",
            "status",
            "protocolo_super_os",
            "bairro_referencia",
            "demandas_count",
        )

    def get_demandas_count(self, obj: ClusterExecucao) -> int:
        cached = getattr(obj, "demandas_count", None)
        if cached is not None:
            return int(cached)
        return Demanda.objects.filter(cluster=obj).count()


class ClusterExecucaoSerializer(serializers.ModelSerializer):
    demandas_count = serializers.SerializerMethodField()
    autores_distintos = serializers.SerializerMethodField()
    pendentes_protocolo = serializers.SerializerMethodField()
    servico_nome = serializers.SerializerMethodField()
    tipo = serializers.SerializerMethodField()
    tipo_display = serializers.SerializerMethodField()
    orgaos_envolvidos = serializers.SerializerMethodField()
    orgao_competente_id = serializers.SerializerMethodField()
    orgao_competente_nome = serializers.SerializerMethodField()
    lider_demanda_id = serializers.SerializerMethodField()
    protocolados_count = serializers.SerializerMethodField()

    class Meta:
        model = ClusterExecucao
        fields = (
            "id",
            "titulo",
            "descricao_resumo",
            "status",
            "secretaria_responsavel",
            "bairro_referencia",
            "sinapse_servico_id",
            "servico_nome",
            "protocolo_super_os",
            "despachado_em",
            "demandas_count",
            "pendentes_protocolo",
            "protocolados_count",
            "autores_distintos",
            "tipo",
            "tipo_display",
            "orgaos_envolvidos",
            "orgao_competente_id",
            "orgao_competente_nome",
            "lider_demanda_id",
            "criado_em",
            "atualizado_em",
        )
        read_only_fields = fields

    def _metadata(self, obj: ClusterExecucao) -> dict:
        cache = self.context.setdefault("_cluster_meta_cache", {})
        key = obj.pk
        if key not in cache:
            from core.services.cluster_service import ClusterService

            cache[key] = ClusterService().metadata_cluster(obj)
        return cache[key]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        meta = self._metadata(instance)
        if not (data.get("descricao_resumo") or "").strip():
            data["descricao_resumo"] = meta["descricao_resumo"]
        if not (data.get("secretaria_responsavel") or "").strip():
            data["secretaria_responsavel"] = meta["secretaria_responsavel"]
        if not (data.get("bairro_referencia") or "").strip():
            data["bairro_referencia"] = meta["bairro_referencia"]
        return data

    def get_tipo(self, obj: ClusterExecucao) -> str:
        return self._metadata(obj)["tipo"]

    def get_tipo_display(self, obj: ClusterExecucao) -> str:
        return self._metadata(obj)["tipo_display"]

    def get_orgaos_envolvidos(self, obj: ClusterExecucao) -> list:
        return self._metadata(obj)["orgaos_envolvidos"]

    def get_orgao_competente_id(self, obj: ClusterExecucao) -> int | None:
        return self._metadata(obj)["orgao_competente_id"]

    def get_orgao_competente_nome(self, obj: ClusterExecucao) -> str | None:
        return self._metadata(obj)["orgao_competente_nome"]

    def get_lider_demanda_id(self, obj: ClusterExecucao) -> int | None:
        return self._metadata(obj)["lider_demanda_id"]

    def get_protocolados_count(self, obj: ClusterExecucao) -> int:
        return self._metadata(obj)["protocolados_count"]

    def get_pendentes_protocolo(self, obj: ClusterExecucao) -> int:
        return Demanda.objects.filter(
            cluster=obj, status="AGUARDANDO_PROTOCOLO"
        ).count()

    def get_servico_nome(self, obj: ClusterExecucao) -> str | None:
        if not obj.sinapse_servico_id:
            return None
        from integrations import sinapse_catalog

        svc = sinapse_catalog.get_servico(int(obj.sinapse_servico_id))
        return (svc.titulo or "").strip() if svc else None

    def get_demandas_count(self, obj: ClusterExecucao) -> int:
        return Demanda.objects.filter(cluster=obj).count()

    def get_autores_distintos(self, obj: ClusterExecucao) -> int:
        return (
            Demanda.objects.filter(cluster=obj)
            .values("autor_id")
            .distinct()
            .count()
        )


class TendenciaResumoSerializer(serializers.ModelSerializer):
    sinapse_orgao_nome = serializers.SerializerMethodField()

    class Meta:
        model = Tendencia
        fields = (
            "id",
            "titulo",
            "status",
            "volume_total",
            "sinapse_orgao_id",
            "sinapse_orgao_nome",
        )

    def get_sinapse_orgao_nome(self, obj: Tendencia):
        if not obj.sinapse_orgao_id:
            return None
        return sinapse_catalog.get_orgao_nome(obj.sinapse_orgao_id)


class DemandaSerializer(serializers.ModelSerializer):
    autor = UsuarioSerializer(read_only=True)
    servico = serializers.SerializerMethodField()
    secretaria_destino = serializers.SerializerMethodField()
    tendencia = TendenciaResumoSerializer(read_only=True)
    anexos = AnexoSerializer(many=True, read_only=True)
    tramitacoes = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    protocolo_executivo = serializers.SerializerMethodField()
    servico_carta_sinapse = serializers.SerializerMethodField()
    oficio_url = serializers.SerializerMethodField()
    pacote_devolutiva = serializers.SerializerMethodField()
    cluster = ClusterResumoSerializer(read_only=True)
    super_os = serializers.SerializerMethodField()
    orgaos_integrados = serializers.SerializerMethodField()
    prazo_resolvido = serializers.SerializerMethodField()
    assinaturas = serializers.SerializerMethodField()
    assinaturas_resumo = serializers.SerializerMethodField()
    devolutiva_alerta_leitura = serializers.SerializerMethodField()
    acompanhando = serializers.SerializerMethodField()
    pode_acompanhar = serializers.SerializerMethodField()
    somente_acompanhamento = serializers.SerializerMethodField()
    resultado_operacional_label = serializers.SerializerMethodField()
    motivo_nao_execucao_label = serializers.SerializerMethodField()
    registro_estudo_viabilidade = serializers.SerializerMethodField()
    referencias_stand_by = serializers.SerializerMethodField()
    sinapse_servico_id = serializers.IntegerField(required=False, allow_null=True)
    servico_id = serializers.IntegerField(
        write_only=True,
        required=False,
        allow_null=True,
        help_text="Alias de sinapse_servico_id (ID CatalogServico).",
    )

    class Meta:
        model = Demanda
        fields = [
            'id', 'protocolo_legislativo', 'protocolo_executivo', 'titulo', 'descricao',
            'cep', 'logradouro', 'numero', 'complemento', 'bairro', 'latitude', 'longitude',
            'status', 'status_display', 'data_criacao', 'autor', 'servico', 'secretaria_destino',
            'servico_id', 'sinapse_servico_id', 'sinapse_orgao_id',
            'unidade_administrativa_id',
            'origem_vinculo', 'tendencia',
            'fluxo_roteamento', 'sinapse_orgao_lider_id',
            'modo_entrada_processo', 'orquestrador_conclusao', 'inicio_execucao_automatico',
            'nos_ativos',
            'modo_entrada_processo', 'orquestrador_conclusao', 'inicio_execucao_automatico',
            'nos_ativos',
            'servico_carta_sinapse', 'oficio_url',
            'pacote_devolutiva',
            'anexos', 'tramitacoes',
            'data_inicio_prazo',
            'ia_categoria', 'ia_sentimento', 'ia_processado',
            'cluster',
            'super_os',
            'orgaos_integrados',
            'prazo_efetivo_dias',
            'prazo_origem',
            'prazo_resolvido',
            'assinaturas',
            'assinaturas_resumo',
            'devolutiva_alerta_leitura',
            'acompanhando',
            'pode_acompanhar',
            'somente_acompanhamento',
            'resultado_operacional',
            'resultado_operacional_label',
            'motivo_nao_execucao',
            'motivo_nao_execucao_label',
            'escopo_geografico',
            'stand_by_estudo_viabilidade',
            'registro_estudo_viabilidade',
            'referencias_stand_by',
        ]
        read_only_fields = [
            'protocolo_legislativo', 'protocolo_executivo', 'status', 'status_display',
            'data_criacao', 'secretaria_destino', 'anexos', 'tramitacoes', 'autor',
            'data_inicio_prazo',
            'ia_categoria', 'ia_sentimento', 'ia_processado',
            'servico_carta_sinapse', 'oficio_url', 'sinapse_orgao_id',
            'unidade_administrativa_id',
            'fluxo_roteamento', 'sinapse_orgao_lider_id',
            'modo_entrada_processo', 'orquestrador_conclusao', 'inicio_execucao_automatico',
            'nos_ativos',
            'pacote_devolutiva',
            'cluster',
            'super_os',
            'orgaos_integrados',
            'prazo_efetivo_dias',
            'prazo_origem',
            'prazo_resolvido',
            'assinaturas',
            'assinaturas_resumo',
            'devolutiva_alerta_leitura',
            'acompanhando',
            'pode_acompanhar',
            'somente_acompanhamento',
            'resultado_operacional',
            'resultado_operacional_label',
            'motivo_nao_execucao',
            'motivo_nao_execucao_label',
            'escopo_geografico',
            'stand_by_estudo_viabilidade',
            'registro_estudo_viabilidade',
            'referencias_stand_by',
        ]

    def get_protocolo_executivo(self, obj: Demanda) -> str | None:
        from core.services.cluster_aderencia_service import protocolo_executivo_efetivo

        return protocolo_executivo_efetivo(obj)

    def get_prazo_resolvido(self, obj: Demanda) -> dict:
        return obj.prazo_resolvido_dict()

    def get_devolutiva_alerta_leitura(self, obj: Demanda) -> bool:
        request = self.context.get("request")
        if not request or not getattr(request.user, "is_authenticated", False):
            return False
        from core.services.devolutiva_alerta_service import usuario_tem_alerta_devolutiva_leitura

        return usuario_tem_alerta_devolutiva_leitura(request.user, obj)

    def _acompanhamento_svc(self):
        from core.services.acompanhamento_demanda_service import AcompanhamentoDemandaService

        return AcompanhamentoDemandaService()

    def get_acompanhando(self, obj: Demanda) -> bool:
        request = self.context.get("request")
        if not request or not getattr(request.user, "is_authenticated", False):
            return False
        return self._acompanhamento_svc().usuario_acompanha_ativo(request.user, obj.pk)

    def get_pode_acompanhar(self, obj: Demanda) -> bool:
        request = self.context.get("request")
        if not request or not getattr(request.user, "is_authenticated", False):
            return False
        return self._acompanhamento_svc().pode_acompanhar(request.user, obj)

    def get_somente_acompanhamento(self, obj: Demanda) -> bool:
        request = self.context.get("request")
        if not request or not getattr(request.user, "is_authenticated", False):
            return False
        return self._acompanhamento_svc().somente_acompanhamento(request.user, obj)

    def get_resultado_operacional_label(self, obj: Demanda) -> str:
        from core.models_estudo_viabilidade import ResultadoOperacional

        valor = (obj.resultado_operacional or "").strip()
        if not valor:
            return ""
        try:
            return ResultadoOperacional(valor).label
        except ValueError:
            return valor

    def get_motivo_nao_execucao_label(self, obj: Demanda) -> str:
        from core.models_estudo_viabilidade import MotivoNaoExecucao

        valor = (obj.motivo_nao_execucao or "").strip()
        if not valor:
            return ""
        try:
            return MotivoNaoExecucao(valor).label
        except ValueError:
            return valor

    def _estudo_viabilidade_svc(self):
        from core.services.estudo_viabilidade_service import EstudoViabilidadeService

        return EstudoViabilidadeService()

    def get_registro_estudo_viabilidade(self, obj: Demanda) -> dict | None:
        request = self.context.get("request")
        if not request or not getattr(request.user, "is_authenticated", False):
            return None
        if not self._estudo_viabilidade_svc().usuario_ve_stand_by(request.user):
            return None
        from core.models_estudo_viabilidade import RegistroEstudoViabilidade

        try:
            registro = RegistroEstudoViabilidade.objects.get(demanda_id=obj.pk)
        except RegistroEstudoViabilidade.DoesNotExist:
            return None
        return self._estudo_viabilidade_svc().serializar_registro(registro, demanda=obj)

    def get_referencias_stand_by(self, obj: Demanda) -> list:
        request = self.context.get("request")
        if not request or not getattr(request.user, "is_authenticated", False):
            return []
        svc = self._estudo_viabilidade_svc()
        if not svc.usuario_ve_stand_by(request.user):
            return []
        lat = float(obj.latitude) if obj.latitude is not None else None
        lon = float(obj.longitude) if obj.longitude is not None else None
        return svc.buscar_referencias_stand_by(
            request.user,
            sinapse_servico_id=obj.sinapse_servico_id,
            latitude=lat,
            longitude=lon,
            bairro=obj.bairro,
            excluir_demanda_id=obj.pk,
            limite=3,
        )

    def get_super_os(self, obj: Demanda) -> dict:
        from core.services.cluster_service import ClusterService

        return ClusterService().info_operacional_super_os(obj)

    def get_orgaos_integrados(self, obj: Demanda) -> list:
        from core.services.demanda_despacho_destinos import orgaos_integrados_demanda

        return orgaos_integrados_demanda(obj)

    def get_assinaturas(self, obj: Demanda) -> list:
        from core.services.assinatura_eletronica_service import AssinaturaEletronicaService

        return AssinaturaEletronicaService().serializar_assinaturas_demanda(obj)

    def get_assinaturas_resumo(self, obj: Demanda) -> dict:
        from core.services.assinatura_eletronica_service import AssinaturaEletronicaService

        return AssinaturaEletronicaService().resumo_assinaturas_demanda(obj)

    def get_tramitacoes(self, obj: Demanda):
        from core.services.tramitacao_visibilidade_service import (
            filtrar_tramitacoes_para_usuario,
            perfil_usuario,
            serializar_tramitacao_para_vereador,
        )

        request = self.context.get("request")
        usuario = request.user if request else None
        qs = (
            obj.tramitacoes.select_related(
                "responsavel",
                "unidade_destino",
                "unidade_origem",
            )
            .prefetch_related("anexos")
            .order_by("timestamp")
        )
        from core.services.scatter_gather_visibilidade import queryset_excluir_scatter_sistema

        qs = queryset_excluir_scatter_sistema(qs)
        qs = filtrar_tramitacoes_para_usuario(qs, usuario, demanda=obj)
        tram_list = list(qs)
        data = TramitacaoSerializer(tram_list, many=True, context=self.context).data
        if perfil_usuario(usuario) == "VEREADOR":
            return [
                serializar_tramitacao_para_vereador(
                    item, demanda=obj, tramitacao_obj=tram
                )
                for item, tram in zip(data, tram_list)
            ]
        return data

    def get_servico(self, obj: Demanda):
        return sinapse_catalog.servico_to_dict(
            sinapse_catalog.get_servico(obj.sinapse_servico_id)
        )

    def get_secretaria_destino(self, obj: Demanda):
        return sinapse_catalog.orgao_to_dict(
            sinapse_catalog.get_orgao(obj.sinapse_orgao_id)
        )

    def get_servico_carta_sinapse(self, obj: Demanda) -> dict | None:
        if not obj.sinapse_servico_id:
            return None
        sync = SinapseServiceSync.objects.filter(
            sinapse_service_id=str(obj.sinapse_servico_id)
        ).first()
        titulo_carta = None
        if sync and isinstance(sync.payload, dict):
            titulo_carta = sync.payload.get("titulo") or sync.payload.get("nome") or sync.payload.get("service_name")
        catalog = sinapse_catalog.get_servico(obj.sinapse_servico_id)
        return {
            "sinapse_servico_id": obj.sinapse_servico_id,
            "titulo_carta": titulo_carta or (catalog.titulo if catalog else None),
            "servico_catalogo": catalog.titulo[:80] if catalog else None,
        }

    def get_oficio_url(self, obj: Demanda) -> str | None:
        anexo = (
            obj.anexos.filter(descricao__icontains="ofício")
            .order_by("-data_upload")
            .first()
        )
        if not anexo or not anexo.arquivo:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(anexo.arquivo.url)
        return anexo.arquivo.url

    def get_pacote_devolutiva(self, obj: Demanda):
        from core.services.tramitacao_visibilidade_service import (
            perfil_usuario,
            status_permite_pacote_devolutiva_vereador,
        )

        request = self.context.get("request")
        usuario = request.user if request else None

        if perfil_usuario(usuario) == "VEREADOR" and not status_permite_pacote_devolutiva_vereador(obj.status):
            return None
        if obj.status not in (
            "DEVOLVIDO_VEREADOR",
            "FINALIZADO",
            "AGUARDANDO_DEVOLUTIVA_PROTOCOLO",
        ):
            return None
        from core.services.encerramento_legislativo_service import EncerramentoLegislativoService

        return EncerramentoLegislativoService().montar_pacote_devolutiva(obj)

    def validate(self, attrs):
        servico_id = attrs.pop("servico_id", None)
        instance: Demanda | None = getattr(self, "instance", None)
        is_tendencia = (
            attrs.get("origem_vinculo") == Demanda.ORIGEM_VINCULO_TENDENCIA
            or (instance is not None and instance.tendencia_id is not None)
            or (
                instance is not None
                and instance.origem_vinculo == Demanda.ORIGEM_VINCULO_TENDENCIA
            )
        )
        if is_tendencia:
            attrs["sinapse_servico_id"] = None
            attrs["origem_vinculo"] = Demanda.ORIGEM_VINCULO_TENDENCIA
            return attrs

        sinapse_id = attrs.get("sinapse_servico_id") or servico_id
        if sinapse_id is not None:
            sinapse_id = int(sinapse_id)
            if not sinapse_catalog.servico_existe(sinapse_id):
                raise serializers.ValidationError(
                    {"sinapse_servico_id": "Serviço não encontrado no catálogo Sinapse."}
                )
            attrs["sinapse_servico_id"] = sinapse_id
        return attrs


class NotificacaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notificacao
        fields = [
            'id',
            'destinatario',
            'mensagem',
            'lida',
            'data_criacao',
            'link',
            'tipo',
        ]
        read_only_fields = ['data_criacao']


class DemandaAutorResumoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ("id", "first_name", "last_name", "username")


class DemandaListSerializer(serializers.ModelSerializer):
    criado_por_id = serializers.ReadOnlyField(source='autor_id')
    servico = serializers.SerializerMethodField()
    servico_nome = serializers.SerializerMethodField()
    secretaria_destino_nome = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    protocolo_executivo = serializers.SerializerMethodField()
    cluster = ClusterResumoSerializer(read_only=True)
    titulo = serializers.CharField(read_only=True)

    class Meta:
        model = Demanda
        fields = [
            'id', 'titulo', 'protocolo_legislativo', 'protocolo_executivo',
            'criado_por_id',
            'secretaria_destino_nome', 'status',
            'status_display', 'data_criacao',
            'servico', 'servico_nome', 'sinapse_servico_id',
            'data_inicio_prazo', 'cluster',
        ]

    def get_servico(self, obj: Demanda):
        return sinapse_catalog.servico_to_dict(
            sinapse_catalog.get_servico(obj.sinapse_servico_id)
        )

    def get_protocolo_executivo(self, obj: Demanda) -> str | None:
        from core.services.cluster_aderencia_service import protocolo_executivo_efetivo

        return protocolo_executivo_efetivo(obj)

    def get_servico_nome(self, obj: Demanda):
        catalog = sinapse_catalog.get_servico(obj.sinapse_servico_id)
        return catalog.titulo if catalog else ""

    def get_secretaria_destino_nome(self, obj):
        nome = sinapse_catalog.get_orgao_nome(obj.sinapse_orgao_id)
        return nome or "Aguardando Protocolo"


class ServicoFluxoProtocoloSerializer(serializers.ModelSerializer):
    servico_nome = serializers.SerializerMethodField()
    orgao_nome = serializers.SerializerMethodField()
    despacho_automatico = serializers.BooleanField(read_only=True)

    class Meta:
        model = ServicoFluxoProtocolo
        fields = (
            "id",
            "sinapse_servico_id",
            "servico_nome",
            "orgao_nome",
            "modo",
            "ativo",
            "despacho_automatico",
            "observacoes",
            "atualizado_em",
        )
        read_only_fields = ("id", "atualizado_em", "despacho_automatico")

    def get_servico_nome(self, obj: ServicoFluxoProtocolo) -> str | None:
        svc = sinapse_catalog.get_servico(obj.sinapse_servico_id)
        return (svc.titulo or "").strip() if svc else None

    def get_orgao_nome(self, obj: ServicoFluxoProtocolo) -> str | None:
        orgao_id = sinapse_catalog.get_orgao_id_for_servico(int(obj.sinapse_servico_id))
        return sinapse_catalog.get_orgao_nome(orgao_id) if orgao_id else None


class UnidadeAdministrativaResponsavelSerializer(serializers.ModelSerializer):
    usuario_nome = serializers.SerializerMethodField()
    usuario_perfil = serializers.CharField(source="usuario.perfil", read_only=True)

    class Meta:
        model = UnidadeAdministrativaResponsavel
        fields = (
            "id",
            "usuario_id",
            "usuario_nome",
            "usuario_perfil",
            "pode_tramitar",
            "ativo",
            "criado_em",
        )
        read_only_fields = fields

    def get_usuario_nome(self, obj: UnidadeAdministrativaResponsavel) -> str:
        u = obj.usuario
        return u.get_full_name() or u.username


class UnidadeAdministrativaSerializer(serializers.ModelSerializer):
    orgao_nome = serializers.SerializerMethodField()
    responsaveis = serializers.SerializerMethodField()

    class Meta:
        model = UnidadeAdministrativa
        fields = (
            "id",
            "sinapse_orgao_id",
            "orgao_nome",
            "nome",
            "sigla",
            "email_contato",
            "cod_rm_orgao",
            "ativo",
            "sinapse_unidade_id",
            "responsaveis",
            "criado_em",
            "atualizado_em",
        )
        read_only_fields = ("id", "criado_em", "atualizado_em", "orgao_nome", "responsaveis")

    def get_orgao_nome(self, obj: UnidadeAdministrativa) -> str | None:
        return sinapse_catalog.get_orgao_nome(obj.sinapse_orgao_id)

    def get_responsaveis(self, obj: UnidadeAdministrativa):
        qs = obj.responsaveis.filter(ativo=True).select_related("usuario")
        return UnidadeAdministrativaResponsavelSerializer(qs, many=True).data


class DeParaRmSinapseSerializer(serializers.ModelSerializer):
    orgao_nome = serializers.SerializerMethodField()

    class Meta:
        model = DeParaRmSinapse
        fields = (
            "id",
            "cod_rm",
            "sinapse_orgao_id",
            "orgao_nome",
            "observacao",
            "ativo",
            "criado_em",
            "atualizado_em",
        )
        read_only_fields = ("id", "criado_em", "atualizado_em", "orgao_nome")

    def get_orgao_nome(self, obj: DeParaRmSinapse) -> str | None:
        if not obj.sinapse_orgao_id:
            return None
        return sinapse_catalog.get_orgao_nome(obj.sinapse_orgao_id)

    def validate_cod_rm(self, value: str) -> str:
        cod = (value or "").strip().upper()
        if not cod:
            raise serializers.ValidationError("cod_rm é obrigatório.")
        return cod


class AssuntoCartaSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssuntoCarta
        fields = (
            "id",
            "nome",
            "slug",
            "ordem",
            "modo_utilizacao_sgdl",
            "mensagem_orientacao",
            "ativo",
            "criado_em",
            "atualizado_em",
        )
        read_only_fields = ("id", "slug", "criado_em", "atualizado_em")


class DemandaPainelListListSerializer(serializers.ListSerializer):
    """Pré-carrega encaminhamento pós-encerramento para listagem da secretaria."""

    def to_representation(self, data):
        request = self.context.get("request")
        from core.services.demanda_listagem_secretaria import (
            listagem_secretaria_encerrado,
            map_encaminhamento_pos_encerramento,
        )

        if listagem_secretaria_encerrado(request):
            orgao_id = getattr(request.user, "sinapse_orgao_id", None)
            demanda_ids = [int(item.pk) for item in data]
            self.context["encerramento_listagem_map"] = map_encaminhamento_pos_encerramento(
                int(orgao_id), demanda_ids
            )
            self.context.pop("localizacao_operacional_map", None)
        else:
            self.context.pop("encerramento_listagem_map", None)
            from core.services.demanda_localizacao_operacional_service import (
                map_localizacao_operacional_aberta,
            )

            demanda_ids = [int(item.pk) for item in data]
            self.context["localizacao_operacional_map"] = map_localizacao_operacional_aberta(
                demanda_ids
            )
        return super().to_representation(data)


class DemandaPainelListSerializer(serializers.ModelSerializer):
    """Lista enxuta para painéis do Protocolo (FIFO + temporizador)."""

    autor = DemandaAutorResumoSerializer(read_only=True)
    servico = serializers.SerializerMethodField()
    secretaria_destino = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    protocolo_executivo = serializers.SerializerMethodField()
    cluster = ClusterResumoSerializer(read_only=True)
    tempo_parado_segundos = serializers.SerializerMethodField()
    tempo_execucao_segundos = serializers.SerializerMethodField()
    cluster_acao_visivel = serializers.SerializerMethodField()
    fluxo_automatico = serializers.SerializerMethodField()
    unidade_administrativa = serializers.SerializerMethodField()
    setores_operacionais_abertos = serializers.SerializerMethodField()
    super_os = serializers.SerializerMethodField()
    prazo_resolvido = serializers.SerializerMethodField()
    assinaturas_resumo = serializers.SerializerMethodField()
    acompanhando = serializers.SerializerMethodField()
    pode_acompanhar = serializers.SerializerMethodField()

    class Meta:
        model = Demanda
        list_serializer_class = DemandaPainelListListSerializer
        fields = [
            'id',
            'titulo',
            'protocolo_legislativo',
            'protocolo_executivo',
            'status',
            'status_display',
            'data_criacao',
            'data_entrada_etapa',
            'data_inicio_prazo',
            'data_finalizacao',
            'tempo_parado_segundos',
            'tempo_execucao_segundos',
            'prazo_efetivo_dias',
            'prazo_origem',
            'prazo_resolvido',
            'autor',
            'servico',
            'secretaria_destino',
            'sinapse_servico_id',
            'origem_vinculo',
            'tendencia_id',
            'cluster',
            'cluster_acao_visivel',
            'fluxo_automatico',
            'unidade_administrativa',
            'setores_operacionais_abertos',
            'super_os',
            'assinaturas_resumo',
            'acompanhando',
            'pode_acompanhar',
        ]

    def get_acompanhando(self, obj: Demanda) -> bool:
        request = self.context.get("request")
        if not request or not getattr(request.user, "is_authenticated", False):
            return False
        from core.services.acompanhamento_demanda_service import AcompanhamentoDemandaService

        return AcompanhamentoDemandaService().usuario_acompanha_ativo(request.user, obj.pk)

    def get_pode_acompanhar(self, obj: Demanda) -> bool:
        request = self.context.get("request")
        if not request or not getattr(request.user, "is_authenticated", False):
            return False
        from core.services.acompanhamento_demanda_service import AcompanhamentoDemandaService

        return AcompanhamentoDemandaService().pode_acompanhar(request.user, obj)

    def get_prazo_resolvido(self, obj: Demanda) -> dict:
        return obj.prazo_resolvido_dict()

    def get_protocolo_executivo(self, obj: Demanda) -> str | None:
        from core.services.cluster_aderencia_service import protocolo_executivo_efetivo

        return protocolo_executivo_efetivo(obj)

    def get_assinaturas_resumo(self, obj: Demanda) -> dict:
        from core.services.assinatura_eletronica_service import AssinaturaEletronicaService

        return AssinaturaEletronicaService().resumo_assinaturas_demanda(obj)

    def get_super_os(self, obj: Demanda) -> dict:
        from core.services.cluster_service import ClusterService

        return ClusterService().info_operacional_super_os(obj)

    def get_servico(self, obj: Demanda):
        return sinapse_catalog.servico_to_dict(
            sinapse_catalog.get_servico(obj.sinapse_servico_id)
        )

    def _contexto_encerrado_listagem(self, obj: Demanda) -> dict | None:
        return (self.context.get("encerramento_listagem_map") or {}).get(int(obj.pk))

    def get_secretaria_destino(self, obj: Demanda):
        ctx = self._contexto_encerrado_listagem(obj)
        if ctx and ctx.get("secretaria_destino"):
            return ctx["secretaria_destino"]
        return sinapse_catalog.orgao_to_dict(
            sinapse_catalog.get_orgao(obj.sinapse_orgao_id)
        )

    def get_tempo_parado_segundos(self, obj: Demanda) -> int | None:
        referencia = obj.data_entrada_etapa or obj.data_criacao
        if not referencia:
            return None
        delta = timezone.now() - referencia
        return max(0, int(delta.total_seconds()))

    def get_tempo_execucao_segundos(self, obj: Demanda) -> int | None:
        if obj.status != "FINALIZADO" or not obj.data_finalizacao:
            return None
        inicio = obj.data_inicio_prazo or obj.data_criacao
        if not inicio:
            return None
        delta = obj.data_finalizacao - inicio
        return max(0, int(delta.total_seconds()))

    def get_cluster_acao_visivel(self, obj: Demanda) -> bool:
        from core.services.cluster_service import ClusterService

        return bool(ClusterService().demanda_elegivel_cluster(obj).get("elegivel"))

    def get_fluxo_automatico(self, obj: Demanda) -> bool:
        from core.services.fluxo_protocolo_service import FluxoProtocoloService

        return FluxoProtocoloService().despacho_automatico_habilitado(obj)

    def get_unidade_administrativa(self, obj: Demanda):
        ctx = self._contexto_encerrado_listagem(obj)
        if ctx and ctx.get("unidade_administrativa"):
            return ctx["unidade_administrativa"]
        unidade = obj.unidade_administrativa
        if not unidade:
            return None
        return {
            "id": unidade.pk,
            "nome": unidade.nome,
            "sigla": unidade.sigla,
            "sinapse_orgao_id": unidade.sinapse_orgao_id,
        }

    def get_setores_operacionais_abertos(self, obj: Demanda) -> list[dict]:
        ctx_enc = self._contexto_encerrado_listagem(obj)
        if ctx_enc:
            return []
        itens = (self.context.get("localizacao_operacional_map") or {}).get(int(obj.pk), [])
        return itens or []


class ChatInteracaoSerializer(serializers.Serializer):
    session_id = serializers.UUIDField(required=False, allow_null=True)
    mensagem = serializers.CharField(required=True, allow_blank=False, max_length=50_000)


class TendenciaOcorrenciaSerializer(serializers.ModelSerializer):
    demanda_titulo = serializers.CharField(source="demanda.titulo", read_only=True)

    class Meta:
        model = TendenciaOcorrencia
        fields = (
            "id",
            "demanda",
            "demanda_titulo",
            "session",
            "indice_demanda",
            "score_triagem_max",
            "texto_origem",
            "criado_em",
        )
        read_only_fields = fields


class TendenciaSerializer(serializers.ModelSerializer):
    sinapse_orgao_nome = serializers.SerializerMethodField()
    sinapse_servico_nome = serializers.SerializerMethodField()

    class Meta:
        model = Tendencia
        fields = (
            "id",
            "slug",
            "titulo",
            "texto_canonico",
            "descricao_resumo",
            "status",
            "volume_total",
            "sinapse_orgao_id",
            "sinapse_orgao_nome",
            "sinapse_servico_id",
            "sinapse_servico_nome",
            "primeira_ocorrencia",
            "ultima_ocorrencia",
            "criado_por",
        )
        read_only_fields = (
            "id",
            "slug",
            "volume_total",
            "primeira_ocorrencia",
            "ultima_ocorrencia",
            "criado_por",
            "sinapse_orgao_nome",
            "sinapse_servico_nome",
        )

    def get_sinapse_orgao_nome(self, obj: Tendencia):
        if not obj.sinapse_orgao_id:
            return None
        return sinapse_catalog.get_orgao_nome(obj.sinapse_orgao_id) or None

    def get_sinapse_servico_nome(self, obj: Tendencia):
        catalog = sinapse_catalog.get_servico(obj.sinapse_servico_id)
        return catalog.titulo if catalog else None


class TendenciaUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tendencia
        fields = (
            "titulo",
            "descricao_resumo",
            "status",
            "sinapse_orgao_id",
        )


class TendenciaBuscarSimilaresSerializer(serializers.Serializer):
    texto = serializers.CharField(max_length=5000)
    limite = serializers.IntegerField(min_value=1, max_value=20, default=5, required=False)


class TendenciaPromoverCartaSerializer(serializers.Serializer):
    sinapse_servico_id = serializers.IntegerField(min_value=1)


class ChatConfirmarTendenciaSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    indice_demanda = serializers.IntegerField(min_value=0)
    titulo = serializers.CharField(max_length=200, required=False, allow_blank=True)
    descricao_resumo = serializers.CharField(max_length=5000, required=False, allow_blank=True)
    sinapse_orgao_id = serializers.IntegerField(required=False, allow_null=True)
    tendencia_id = serializers.IntegerField(required=False, allow_null=True)


class CopilotoFaqPadraoRegexSerializer(serializers.ModelSerializer):
    class Meta:
        model = CopilotoFaqPadraoRegex
        fields = [
            "id",
            "faq",
            "expressao",
            "ativo",
            "ordem",
            "fonte",
            "notas",
            "criado_em",
        ]
        read_only_fields = ["criado_em"]


class CopilotoFaqOrientacaoSerializer(serializers.ModelSerializer):
    padroes = CopilotoFaqPadraoRegexSerializer(many=True, read_only=True)

    class Meta:
        model = CopilotoFaqOrientacao
        fields = [
            "id",
            "slug",
            "categoria_orientacao",
            "titulo",
            "mensagem",
            "orgao_hint",
            "municipio_referencia",
            "ativo",
            "ordem",
            "fonte",
            "notas_internas",
            "ultima_sincronizacao_llm",
            "revisado_por",
            "criado_em",
            "atualizado_em",
            "padroes",
        ]
        read_only_fields = [
            "criado_em",
            "atualizado_em",
            "ultima_sincronizacao_llm",
        ]


class CopilotoFaqOrientacaoWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CopilotoFaqOrientacao
        fields = [
            "slug",
            "categoria_orientacao",
            "titulo",
            "mensagem",
            "orgao_hint",
            "municipio_referencia",
            "ativo",
            "ordem",
            "fonte",
            "notas_internas",
        ]


class CopilotoFaqEnriquecerLlmSerializer(serializers.Serializer):
    """Payload da automação de IA para criar/atualizar FAQ."""

    categoria_orientacao = serializers.CharField(max_length=64)
    titulo = serializers.CharField(max_length=200)
    mensagem = serializers.CharField()
    orgao_hint = serializers.CharField(max_length=255)
    padroes_regex = serializers.ListField(
        child=serializers.CharField(max_length=500),
        allow_empty=False,
    )
    slug = serializers.SlugField(max_length=80, required=False, allow_blank=True)
    municipio_referencia = serializers.CharField(
        max_length=120, required=False, default="Mogi das Cruzes"
    )
    ativo = serializers.BooleanField(required=False, default=True)
    ordem = serializers.IntegerField(required=False, min_value=0, max_value=9999)
    notas_internas = serializers.CharField(required=False, allow_blank=True, default="")
    substituir_padroes = serializers.BooleanField(required=False, default=False)
    ordem_padrao_base = serializers.IntegerField(required=False, min_value=0, default=10)


class ConfiguracaoOficioSerializer(serializers.ModelSerializer):
    """Layout PDF da Câmara Municipal e destinatário padrão (singleton)."""

    imagem_cabecalho_url = serializers.SerializerMethodField()
    instituicao_nome = serializers.CharField(read_only=True)

    class Meta:
        model = ConfiguracaoOficio
        fields = [
            "municipio",
            "uf",
            "orgao_destinatario",
            "destinatario_tratamento",
            "destinatario_nome",
            "destinatario_cargo",
            "titulo_instituicao",
            "cabecalho_layout",
            "imagem_cabecalho",
            "imagem_cabecalho_url",
            "brasao_largura_cm",
            "instituicao_nome",
            "pagina_formato",
            "pagina_orientacao",
            "margem_superior_cm",
            "margem_inferior_cm",
            "margem_esquerda_cm",
            "margem_direita_cm",
            "rodape_protocolo_altura_cm",
            "atualizado_em",
        ]
        read_only_fields = ["atualizado_em", "imagem_cabecalho_url", "instituicao_nome"]
        extra_kwargs = {
            "municipio": {"required": False, "allow_blank": True},
            "uf": {"required": False, "allow_blank": True},
            "titulo_instituicao": {"required": False, "allow_blank": True},
        }

    def get_imagem_cabecalho_url(self, obj: ConfiguracaoOficio) -> str | None:
        if not obj.imagem_cabecalho:
            return None
        request = self.context.get("request")
        url = obj.imagem_cabecalho.url
        if request is not None:
            return request.build_absolute_uri(url)
        return url


class ConfiguracaoCartaSerializer(serializers.ModelSerializer):
    politica_prazo_display = serializers.CharField(
        source="get_politica_prazo_display", read_only=True
    )

    class Meta:
        model = ConfiguracaoCarta
        fields = [
            "prazo_padrao_dias",
            "politica_prazo",
            "politica_prazo_display",
            "atualizado_em",
        ]
        read_only_fields = ["atualizado_em", "politica_prazo_display"]


class UsuarioGestaoSerializer(serializers.ModelSerializer):
    secretaria_nome = serializers.SerializerMethodField()
    unidade_ids = serializers.SerializerMethodField()
    unidades = serializers.SerializerMethodField()
    vinculo_secretaria = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "perfil",
            "is_active",
            "sinapse_orgao_id",
            "secretaria_nome",
            "unidade_ids",
            "unidades",
            "vinculo_secretaria",
        ]
        read_only_fields = fields

    def get_secretaria_nome(self, obj: Usuario) -> str | None:
        if not obj.sinapse_orgao_id:
            return None
        return sinapse_catalog.get_orgao_nome(obj.sinapse_orgao_id)

    def get_unidade_ids(self, obj: Usuario) -> list[int]:
        from core.services.usuario_vinculo_service import UsuarioVinculoService

        status = UsuarioVinculoService().status_vinculo_secretaria(obj)
        return status.get("unidade_ids") or []

    def get_unidades(self, obj: Usuario) -> list[dict]:
        ids = self.get_unidade_ids(obj)
        if not ids:
            return []
        qs = UnidadeAdministrativa.objects.filter(pk__in=ids).order_by("nome")
        return [
            {
                "id": u.pk,
                "nome": u.nome,
                "sigla": u.sigla,
                "sinapse_orgao_id": u.sinapse_orgao_id,
            }
            for u in qs
        ]

    def get_vinculo_secretaria(self, obj: Usuario) -> dict:
        from core.services.usuario_vinculo_service import UsuarioVinculoService

        return UsuarioVinculoService().status_vinculo_secretaria(obj)


class UsuarioSecretariaWriteSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True, default="")
    last_name = serializers.CharField(required=False, allow_blank=True, default="")
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    is_active = serializers.BooleanField(required=False, default=True)
    sinapse_orgao_id = serializers.IntegerField()
    unidade_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False,
        min_length=1,
    )

    def validate_username(self, value: str) -> str:
        username = (value or "").strip()
        if not username:
            raise serializers.ValidationError("Username é obrigatório.")
        qs = Usuario.objects.filter(username__iexact=username)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Username já está em uso.")
        return username

    def validate_sinapse_orgao_id(self, value: int) -> int:
        orgao_id = int(value)
        if sinapse_catalog.catalog_disponivel() and not sinapse_catalog.orgao_existe(orgao_id):
            raise serializers.ValidationError("Órgão não encontrado no catálogo Sinapse.")
        return orgao_id

    def validate(self, attrs):
        attrs = _normalizar_senha_opcional(attrs)
        if not self.instance and not attrs.get("password"):
            raise serializers.ValidationError({"password": "Senha é obrigatória na criação."})
        return attrs

    def create(self, validated_data):
        from core.services.usuario_vinculo_service import UsuarioVinculoService

        unidade_ids = validated_data.pop("unidade_ids")
        password = validated_data.pop("password")
        validated_data.pop("is_active", True)
        user = Usuario.objects.create_user(
            password=password,
            perfil="SECRETARIA",
            **validated_data,
        )
        UsuarioVinculoService().sincronizar_secretaria(
            user,
            sinapse_orgao_id=validated_data["sinapse_orgao_id"],
            unidade_ids=unidade_ids,
        )
        return user

    def update(self, instance: Usuario, validated_data):
        from core.services.usuario_vinculo_service import UsuarioVinculoService

        unidade_ids = validated_data.pop("unidade_ids", None)
        password = validated_data.pop("password", None)
        for field in ("first_name", "last_name", "email", "is_active"):
            if field in validated_data:
                setattr(instance, field, validated_data[field])
        if password:
            instance.set_password(password)
        instance.save()

        if unidade_ids is not None:
            orgao_id = validated_data.get("sinapse_orgao_id", instance.sinapse_orgao_id)
            UsuarioVinculoService().sincronizar_secretaria(
                instance,
                sinapse_orgao_id=int(orgao_id),
                unidade_ids=unidade_ids,
            )
        elif "sinapse_orgao_id" in validated_data:
            UsuarioVinculoService().sincronizar_secretaria(
                instance,
                sinapse_orgao_id=int(validated_data["sinapse_orgao_id"]),
                unidade_ids=UsuarioVinculoService().ids_unidades_ativas(instance) or [],
            )
        return instance


class UsuarioGestorSerializer(serializers.ModelSerializer):
    secretaria_nome = serializers.SerializerMethodField()
    unidade_ids = serializers.SerializerMethodField()
    unidades = serializers.SerializerMethodField()
    vinculo_gestor = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "perfil",
            "is_active",
            "is_staff",
            "is_superuser",
            "sinapse_orgao_id",
            "secretaria_nome",
            "unidade_ids",
            "unidades",
            "vinculo_gestor",
        ]
        read_only_fields = fields

    def get_secretaria_nome(self, obj: Usuario) -> str | None:
        if not obj.sinapse_orgao_id:
            return None
        return sinapse_catalog.get_orgao_nome(obj.sinapse_orgao_id)

    def get_unidade_ids(self, obj: Usuario) -> list[int]:
        from core.services.usuario_vinculo_service import UsuarioVinculoService

        return UsuarioVinculoService().status_vinculo_gestor(obj).get("unidade_ids") or []

    def get_unidades(self, obj: Usuario) -> list[dict]:
        ids = self.get_unidade_ids(obj)
        if not ids:
            return []
        qs = UnidadeAdministrativa.objects.filter(pk__in=ids).order_by("nome")
        return [
            {
                "id": u.pk,
                "nome": u.nome,
                "sigla": u.sigla,
                "sinapse_orgao_id": u.sinapse_orgao_id,
            }
            for u in qs
        ]

    def get_vinculo_gestor(self, obj: Usuario) -> dict:
        from core.services.usuario_vinculo_service import UsuarioVinculoService

        return UsuarioVinculoService().status_vinculo_gestor(obj)


class UsuarioGestorWriteSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True, default="")
    last_name = serializers.CharField(required=False, allow_blank=True, default="")
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    is_active = serializers.BooleanField(required=False, default=True)
    sinapse_orgao_id = serializers.IntegerField(required=False, allow_null=True)
    unidade_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
        default=list,
    )
    limpar_referencia = serializers.BooleanField(required=False, default=False)

    def validate_username(self, value: str) -> str:
        username = (value or "").strip()
        if not username:
            raise serializers.ValidationError("Username é obrigatório.")
        qs = Usuario.objects.filter(username__iexact=username)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Username já está em uso.")
        return username

    def validate_sinapse_orgao_id(self, value):
        if value in (None, ""):
            return None
        orgao_id = int(value)
        if sinapse_catalog.catalog_disponivel() and not sinapse_catalog.orgao_existe(orgao_id):
            raise serializers.ValidationError("Órgão não encontrado no catálogo Sinapse.")
        return orgao_id

    def validate(self, attrs):
        attrs = _normalizar_senha_opcional(attrs)
        if not self.instance and not attrs.get("password"):
            raise serializers.ValidationError({"password": "Senha é obrigatória na criação."})
        unidade_ids = attrs.get("unidade_ids") or []
        orgao = attrs.get("sinapse_orgao_id")
        if unidade_ids and orgao is None and not attrs.get("limpar_referencia"):
            if self.instance and self.instance.sinapse_orgao_id:
                pass
            else:
                raise serializers.ValidationError(
                    {"sinapse_orgao_id": "Informe o órgão de referência ao vincular setor(es)."}
                )
        return attrs

    def create(self, validated_data):
        from core.services.usuario_vinculo_service import UsuarioVinculoService

        unidade_ids = validated_data.pop("unidade_ids", [])
        limpar_referencia = validated_data.pop("limpar_referencia", False)
        password = validated_data.pop("password")
        sinapse_orgao_id = validated_data.pop("sinapse_orgao_id", None)
        user = Usuario.objects.create_user(
            password=password,
            perfil="GESTOR",
            sinapse_orgao_id=sinapse_orgao_id,
            **validated_data,
        )
        UsuarioVinculoService().sincronizar_gestor(
            user,
            sinapse_orgao_id=sinapse_orgao_id,
            unidade_ids=unidade_ids if unidade_ids else None,
            limpar_referencia=limpar_referencia,
        )
        return user

    def update(self, instance: Usuario, validated_data):
        from core.services.usuario_vinculo_service import UsuarioVinculoService

        unidade_ids = validated_data.pop("unidade_ids", None)
        limpar_referencia = validated_data.pop("limpar_referencia", False)
        password = validated_data.pop("password", None)
        sinapse_orgao_id = validated_data.pop("sinapse_orgao_id", None)
        orgao_in_payload = "sinapse_orgao_id" in self.initial_data

        for field in ("first_name", "last_name", "email", "is_active"):
            if field in validated_data:
                setattr(instance, field, validated_data[field])
        if password:
            instance.set_password(password)
        instance.save()

        kwargs = {}
        if orgao_in_payload:
            kwargs["sinapse_orgao_id"] = sinapse_orgao_id
        if unidade_ids is not None:
            kwargs["unidade_ids"] = unidade_ids
        if limpar_referencia:
            kwargs["limpar_referencia"] = True
        if kwargs:
            UsuarioVinculoService().sincronizar_gestor(instance, **kwargs)
        else:
            UsuarioVinculoService().sincronizar_gestor(instance)
        return instance


def _validar_username_unico(username: str, instance: Usuario | None = None) -> str:
    username = (username or "").strip()
    if not username:
        raise serializers.ValidationError("Username é obrigatório.")
    qs = Usuario.objects.filter(username__iexact=username)
    if instance:
        qs = qs.exclude(pk=instance.pk)
    if qs.exists():
        raise serializers.ValidationError("Username já está em uso.")
    return username


def _normalizar_senha_opcional(attrs: dict) -> dict:
    """Em edição, ignora senha vazia ou só espaços (H3-14)."""
    if "password" not in attrs:
        return attrs
    pwd = (attrs.get("password") or "").strip()
    if not pwd:
        attrs.pop("password")
    else:
        attrs["password"] = pwd
    return attrs


class UsuarioVereadorWriteSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True, default="")
    last_name = serializers.CharField(required=False, allow_blank=True, default="")
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    cargo = serializers.CharField(required=False, allow_blank=True, default="")
    telefone = serializers.CharField(required=False, allow_blank=True, default="")
    ramal = serializers.CharField(required=False, allow_blank=True, default="")
    is_active = serializers.BooleanField(required=False, default=True)

    def validate_username(self, value: str) -> str:
        return _validar_username_unico(value, self.instance)

    def validate(self, attrs):
        attrs = _normalizar_senha_opcional(attrs)
        if not self.instance and not attrs.get("password"):
            raise serializers.ValidationError({"password": "Senha é obrigatória na criação."})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        return Usuario.objects.create_user(password=password, perfil="VEREADOR", **validated_data)

    def update(self, instance: Usuario, validated_data):
        password = validated_data.pop("password", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class UsuarioProtocoloWriteSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True, default="")
    last_name = serializers.CharField(required=False, allow_blank=True, default="")
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    is_active = serializers.BooleanField(required=False, default=True)

    def validate_username(self, value: str) -> str:
        return _validar_username_unico(value, self.instance)

    def validate(self, attrs):
        attrs = _normalizar_senha_opcional(attrs)
        if not self.instance and not attrs.get("password"):
            raise serializers.ValidationError({"password": "Senha é obrigatória na criação."})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        return Usuario.objects.create_user(password=password, perfil="PROTOCOLO", **validated_data)

    def update(self, instance: Usuario, validated_data):
        password = validated_data.pop("password", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class UsuarioGestaoUnificadoSerializer(serializers.ModelSerializer):
    perfil_display = serializers.CharField(source="get_perfil_display", read_only=True)
    secretaria_nome = serializers.SerializerMethodField()
    unidade_ids = serializers.SerializerMethodField()
    unidades = serializers.SerializerMethodField()
    vinculo_secretaria = serializers.SerializerMethodField()
    vinculo_gestor = serializers.SerializerMethodField()
    vinculo_protocolo = serializers.SerializerMethodField()
    vinculo_status = serializers.SerializerMethodField()
    atuacao_sgdl = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "perfil",
            "perfil_display",
            "is_active",
            "is_staff",
            "is_superuser",
            "sinapse_orgao_id",
            "secretaria_nome",
            "cargo",
            "telefone",
            "ramal",
            "unidade_ids",
            "unidades",
            "vinculo_secretaria",
            "vinculo_gestor",
            "vinculo_protocolo",
            "vinculo_status",
            "atuacao_sgdl",
        ]
        read_only_fields = fields

    def get_secretaria_nome(self, obj: Usuario) -> str | None:
        if not obj.sinapse_orgao_id:
            return None
        return sinapse_catalog.get_orgao_nome(obj.sinapse_orgao_id)

    def _service(self):
        from core.services.usuario_vinculo_service import UsuarioVinculoService

        return UsuarioVinculoService()

    def get_unidade_ids(self, obj: Usuario) -> list[int]:
        return self._service().ids_unidades_ativas(obj)

    def get_unidades(self, obj: Usuario) -> list[dict]:
        ids = self.get_unidade_ids(obj)
        if not ids:
            return []
        return [
            {
                "id": u.pk,
                "nome": u.nome,
                "sigla": u.sigla,
                "sinapse_orgao_id": u.sinapse_orgao_id,
            }
            for u in UnidadeAdministrativa.objects.filter(pk__in=ids).order_by("nome")
        ]

    def get_vinculo_secretaria(self, obj: Usuario) -> dict:
        return self._service().status_vinculo_secretaria(obj)

    def get_vinculo_gestor(self, obj: Usuario) -> dict:
        return self._service().status_vinculo_gestor(obj)

    def get_vinculo_protocolo(self, obj: Usuario) -> dict:
        return self._service().status_vinculo_protocolo(obj)

    def get_vinculo_status(self, obj: Usuario) -> str:
        perfil = getattr(obj, "perfil", None)
        if perfil == "VEREADOR":
            return "ok"
        if perfil == "SECRETARIA":
            return "completo" if self.get_vinculo_secretaria(obj).get("completo") else "incompleto"
        if perfil == "PROTOCOLO":
            return "completo" if self.get_vinculo_protocolo(obj).get("completo") else "incompleto"
        if perfil == "GESTOR":
            v = self.get_vinculo_gestor(obj)
            if v.get("tipo_gestor") == "SETORIAL":
                return "completo"
            if not v.get("admin_pleno"):
                return "incompleto"
            return "completo"
        return "ok"

    def get_atuacao_sgdl(self, obj: Usuario) -> dict:
        return self._service().atuacao_sgdl(obj)

