from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.urls import path
from django.utils.html import format_html

from integrations import sinapse_catalog

from core.forms import DemandaAdminForm, UsuarioAdminForm, UsuarioCreationAdminForm
from core.models import (
    Anexo,
    AnexoTramitacao,
    ChatSession,
    ChatSessaoAnexo,
    ClusterExecucao,
    CopilotoFaqOrientacao,
    CopilotoFaqPadraoRegex,
    Demanda,
    Notificacao,
    Tendencia,
    TendenciaOcorrencia,
    Tramitacao,
    Usuario,
)
from core.models_config import ConfiguracaoOficio
from core.models_fluxo_protocolo import ServicoFluxoProtocolo
from core.models_assinatura_eletronica import AssinaturaEletronica
from core.models_unidade_administrativa import (
    UnidadeAdministrativa,
    UnidadeAdministrativaResponsavel,
)
from core.models_carta_otimizada import ServicoOtimizado, LogOtimizacao, EstatisticasBaseOtimizada
from core.models_estudo_viabilidade import RegistroEstudoViabilidade
from core.admin.servico_otimizado_export import servico_otimizado_csv_response


# =============================================================================
# Operação · Demandas, tramitações, anexos, clusters, notificações
# Copiloto · Chat, FAQ orientação, tendências
# Carta · Base otimizada, fluxo protocolo, assinaturas eletrônicas
# Usuários · Perfis SGDL, unidades administrativas
# Configuração · Ofício institucional (singleton)
# =============================================================================


# --- Inlines -------------------------------------------------------------------


class AnexoInline(admin.TabularInline):
    model = Anexo
    extra = 0
    fields = ("descricao", "arquivo", "data_upload")
    readonly_fields = ("data_upload",)


class AnexoTramitacaoInline(admin.TabularInline):
    model = AnexoTramitacao
    extra = 0


class TramitacaoInline(admin.TabularInline):
    model = Tramitacao
    extra = 0
    fields = ("tipo", "responsavel", "descricao", "timestamp")
    readonly_fields = ("timestamp",)
    autocomplete_fields = ("responsavel",)


# --- Demanda (copiloto, Sinapse, geo, IA) --------------------------------------


@admin.register(Demanda)
class DemandaAdmin(admin.ModelAdmin):
    form = DemandaAdminForm
    list_display = (
        "id",
        "titulo_curto",
        "status",
        "sinapse_servico_rotulo",
        "sinapse_orgao_rotulo",
        "bairro",
        "tem_coordenadas",
        "ia_processado",
        "data_criacao",
    )
    list_filter = (
        "status",
        "sinapse_orgao_id",
        "ia_processado",
        "cluster",
    )
    search_fields = (
        "titulo",
        "descricao",
        "logradouro",
        "bairro",
        "cep",
        "protocolo_legislativo",
        "protocolo_executivo",
    )
    readonly_fields = (
        "protocolo_legislativo",
        "protocolo_executivo",
        "data_criacao",
        "data_inicio_prazo",
        "endereco_resumo",
    )
    autocomplete_fields = ("autor", "cluster")
    inlines = [TramitacaoInline, AnexoInline]
    date_hierarchy = "data_criacao"
    fieldsets = (
        (
            "Identificação",
            {
                "fields": (
                    "titulo",
                    "descricao",
                    "status",
                    "autor",
                    "protocolo_legislativo",
                    "protocolo_executivo",
                )
            },
        ),
        (
            "Serviço e Sinapse",
            {
                "fields": (
                    "sinapse_servico_id",
                    "sinapse_orgao_id",
                )
            },
        ),
        (
            "Endereço",
            {
                "fields": (
                    "endereco_resumo",
                    "cep",
                    "logradouro",
                    "numero",
                    "complemento",
                    "bairro",
                    "latitude",
                    "longitude",
                )
            },
        ),
        (
            "IA e agrupamento",
            {
                "fields": (
                    "ia_processado",
                    "ia_categoria",
                    "ia_sentimento",
                    "cluster",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Prazos",
            {
                "fields": (
                    "data_criacao",
                    "data_finalizacao",
                    "data_inicio_prazo",
                    "notificacao_atraso_enviada",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="Título")
    def titulo_curto(self, obj: Demanda) -> str:
        return (obj.titulo or "")[:50]

    @admin.display(description="Serviço (Sinapse)")
    def sinapse_servico_rotulo(self, obj: Demanda) -> str:
        if not obj.sinapse_servico_id:
            return "—"
        catalog = sinapse_catalog.get_servico(obj.sinapse_servico_id)
        if catalog:
            return (catalog.titulo or "")[:60]
        return f"ID {obj.sinapse_servico_id}"

    @admin.display(description="Órgão (Sinapse)")
    def sinapse_orgao_rotulo(self, obj: Demanda) -> str:
        if not obj.sinapse_orgao_id:
            return "—"
        nome = sinapse_catalog.get_orgao_nome(obj.sinapse_orgao_id)
        return nome or f"ID {obj.sinapse_orgao_id}"

    @admin.display(description="Geo", boolean=True)
    def tem_coordenadas(self, obj: Demanda) -> bool:
        return obj.latitude is not None and obj.longitude is not None

    @admin.display(description="Endereço (resumo)")
    def endereco_resumo(self, obj: Demanda) -> str:
        partes = [
            obj.logradouro,
            obj.numero and f"nº {obj.numero}",
            obj.bairro and f"bairro {obj.bairro}",
            obj.cep and f"CEP {obj.cep}",
        ]
        txt = ", ".join(p for p in partes if p)
        if obj.latitude and obj.longitude:
            txt += f" | {obj.latitude}, {obj.longitude}"
        return txt or "—"


@admin.register(RegistroEstudoViabilidade)
class RegistroEstudoViabilidadeAdmin(admin.ModelAdmin):
    list_display = (
        "demanda",
        "resultado_operacional",
        "motivo_nao_execucao",
        "escopo_resumo",
        "sinapse_orgao_id",
        "pode_retomar",
        "criado_em",
    )
    list_filter = ("resultado_operacional", "motivo_nao_execucao", "pode_retomar")
    search_fields = (
        "demanda__titulo",
        "demanda__protocolo_executivo",
        "demanda__protocolo_legislativo",
        "escopo_geografico",
    )
    autocomplete_fields = ("demanda", "unidade_administrativa", "registrado_por")
    readonly_fields = ("criado_em", "atualizado_em")
    ordering = ("-criado_em",)

    @admin.display(description="Escopo")
    def escopo_resumo(self, obj: RegistroEstudoViabilidade) -> str:
        return (obj.escopo_geografico or "")[:80] or "—"


# --- Tramitação / Anexos ------------------------------------------------------


@admin.register(Tramitacao)
class TramitacaoAdmin(admin.ModelAdmin):
    list_display = ("demanda", "tipo", "responsavel", "timestamp")
    list_filter = ("tipo",)
    search_fields = ("descricao", "demanda__titulo")
    autocomplete_fields = ("demanda", "responsavel")
    inlines = [AnexoTramitacaoInline]


@admin.register(Anexo)
class AnexoAdmin(admin.ModelAdmin):
    list_display = ("demanda", "descricao", "arquivo", "data_upload")
    list_filter = ("data_upload",)
    search_fields = ("descricao", "demanda__titulo")
    autocomplete_fields = ("demanda",)


@admin.register(AnexoTramitacao)
class AnexoTramitacaoAdmin(admin.ModelAdmin):
    list_display = ("tramitacao", "arquivo")
    autocomplete_fields = ("tramitacao",)


# --- Notificações -------------------------------------------------------------


@admin.register(Notificacao)
class NotificacaoAdmin(admin.ModelAdmin):
    list_display = ("destinatario", "tipo", "mensagem_curta", "lida", "data_criacao")
    list_filter = ("lida", "tipo", "destinatario__perfil")
    search_fields = ("mensagem", "destinatario__username")
    autocomplete_fields = ("destinatario",)
    date_hierarchy = "data_criacao"
    ordering = ("-data_criacao",)

    @admin.display(description="Mensagem")
    def mensagem_curta(self, obj: Notificacao) -> str:
        return (obj.mensagem or "")[:60]


# --- Configuração institucional (ofício) ---------------------------------------


@admin.register(ConfiguracaoOficio)
class ConfiguracaoOficioAdmin(admin.ModelAdmin):
    fieldsets = (
        (
            "Destinatário (Prefeitura)",
            {
                "fields": (
                    "municipio",
                    "uf",
                    "orgao_destinatario",
                    "destinatario_tratamento",
                    "destinatario_nome",
                    "destinatario_cargo",
                )
            },
        ),
        (
            "Layout PDF (Câmara)",
            {
                "fields": (
                    "titulo_instituicao",
                    "cabecalho_layout",
                    "imagem_cabecalho",
                    "brasao_largura_cm",
                    "pagina_formato",
                    "pagina_orientacao",
                    "margem_superior_cm",
                    "margem_inferior_cm",
                    "margem_esquerda_cm",
                    "margem_direita_cm",
                    "rodape_protocolo_altura_cm",
                )
            },
        ),
        ("Atualização", {"fields": ("atualizado_em",)}),
    )
    readonly_fields = ("atualizado_em",)

    def has_add_permission(self, request):
        return not ConfiguracaoOficio.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ServicoFluxoProtocolo)
class ServicoFluxoProtocoloAdmin(admin.ModelAdmin):
    list_display = ("sinapse_servico_id", "modo", "ativo", "atualizado_em")
    list_filter = ("modo", "ativo")
    search_fields = ("sinapse_servico_id", "observacoes")
    readonly_fields = ("criado_em", "atualizado_em")


@admin.register(AssinaturaEletronica)
class AssinaturaEletronicaAdmin(admin.ModelAdmin):
    list_display = (
        "demanda",
        "tramitacao",
        "etapa",
        "papel",
        "usuario",
        "codigo_validacao",
        "assinado_em",
    )
    list_filter = ("etapa", "papel")
    search_fields = ("codigo_validacao", "hash_assinatura", "demanda__protocolo_legislativo")
    readonly_fields = (
        "hash_documento",
        "hash_assinatura",
        "codigo_validacao",
        "ip_origem",
        "user_agent",
        "declaracao",
        "assinado_em",
    )


class ChatSessaoAnexoInline(admin.TabularInline):
    model = ChatSessaoAnexo
    extra = 0
    fields = ("arquivo", "descricao", "indice_demanda", "criado_em")
    readonly_fields = ("criado_em",)


# --- Copiloto -----------------------------------------------------------------


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "autor",
        "estado_atual",
        "qtd_mensagens",
        "qtd_rascunhos",
        "atualizado_em",
    )
    list_filter = ("estado_atual",)
    search_fields = ("autor__username", "id")
    readonly_fields = (
        "id",
        "criado_em",
        "atualizado_em",
        "historico_preview",
        "rascunho_preview",
    )
    autocomplete_fields = ("autor",)
    inlines = [ChatSessaoAnexoInline]
    fieldsets = (
        (None, {"fields": ("id", "autor", "estado_atual", "criado_em", "atualizado_em")}),
        (
            "Conversa",
            {
                "fields": ("historico_mensagens", "historico_preview"),
                "classes": ("collapse",),
            },
        ),
        (
            "Rascunhos extraídos",
            {
                "fields": ("demandas_rascunho", "rascunho_preview"),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="Mensagens")
    def qtd_mensagens(self, obj: ChatSession) -> int:
        hist = obj.historico_mensagens
        return len(hist) if isinstance(hist, list) else 0

    @admin.display(description="Rascunhos")
    def qtd_rascunhos(self, obj: ChatSession) -> int:
        dems = obj.demandas_rascunho
        return len(dems) if isinstance(dems, list) else 0

    def _json_preview(self, data) -> str:
        import json

        try:
            texto = json.dumps(data, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            texto = str(data)
        if len(texto) > 6000:
            texto = texto[:6000] + "\n…"
        return format_html("<pre style='max-height:400px;overflow:auto'>{}</pre>", texto)

    @admin.display(description="Histórico (leitura)")
    def historico_preview(self, obj: ChatSession) -> str:
        return self._json_preview(obj.historico_mensagens)

    @admin.display(description="Rascunhos (leitura)")
    def rascunho_preview(self, obj: ChatSession) -> str:
        return self._json_preview(obj.demandas_rascunho)


# --- Clusters IA --------------------------------------------------------------


class DemandaClusterInline(admin.TabularInline):
    model = Demanda
    fk_name = "cluster"
    extra = 0
    fields = (
        "demanda_link",
        "protocolo_executivo",
        "protocolo_legislativo",
        "status",
        "orgao_rotulo",
        "nos_ativos",
        "autor_rotulo",
    )
    readonly_fields = fields
    show_change_link = False
    verbose_name = "Demanda"
    verbose_name_plural = "Demandas do cluster"
    ordering = ("pk",)
    can_delete = False
    max_num = 50

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("autor", "cluster").order_by("pk")

    @admin.display(description="Demanda")
    def demanda_link(self, obj: Demanda) -> str:
        from django.urls import reverse
        from django.utils.html import format_html

        url = reverse("admin:core_demanda_change", args=[obj.pk])
        return format_html('<a href="{}">#{}</a>', url, obj.pk)

    @admin.display(description="Autor")
    def autor_rotulo(self, obj: Demanda) -> str:
        if not obj.autor:
            return "—"
        return obj.autor.get_full_name() or obj.autor.username

    @admin.display(description="Órgão")
    def orgao_rotulo(self, obj: Demanda) -> str:
        if not obj.sinapse_orgao_id:
            return "—"
        return sinapse_catalog.get_orgao_nome(int(obj.sinapse_orgao_id)) or str(obj.sinapse_orgao_id)


@admin.register(ClusterExecucao)
class ClusterExecucaoAdmin(admin.ModelAdmin):
    inlines = [DemandaClusterInline]
    list_display = (
        "titulo",
        "status",
        "secretaria_responsavel",
        "bairro_referencia",
        "qtd_demandas",
        "atualizado_em",
    )
    list_filter = ("status",)
    search_fields = ("titulo", "bairro_referencia")
    readonly_fields = ("criado_em", "atualizado_em", "demandas_vinculadas_resumo")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "titulo",
                    "status",
                    "secretaria_responsavel",
                    "bairro_referencia",
                    "sinapse_servico_id",
                    "protocolo_super_os",
                    "descricao_resumo",
                )
            },
        ),
        (
            "Demandas vinculadas",
            {"fields": ("demandas_vinculadas_resumo",), "classes": ("wide",)},
        ),
        (
            "Auditoria",
            {"fields": ("criado_em", "atualizado_em"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description="Demandas vinculadas")
    def demandas_vinculadas_resumo(self, obj: ClusterExecucao) -> str:
        if not obj.pk:
            return "—"
        from django.utils.html import escape
        from django.utils.safestring import mark_safe

        linhas = []
        for d in obj.demandas.select_related("autor").order_by("pk"):
            orgao = (
                sinapse_catalog.get_orgao_nome(int(d.sinapse_orgao_id))
                if d.sinapse_orgao_id
                else "—"
            )
            linhas.append(
                escape(
                    f"#{d.pk} — exec: {d.protocolo_executivo or '—'} — "
                    f"{d.get_status_display()} — {orgao} — nós: {d.nos_ativos}"
                )
            )
        if not linhas:
            return "Nenhuma demanda vinculada."
        return mark_safe("<br>".join(linhas))

    @admin.display(description="Demandas")
    def qtd_demandas(self, obj: ClusterExecucao) -> int:
        return obj.demandas.count()


# --- Usuários -----------------------------------------------------------------


class UsuarioSetorResponsavelInline(admin.TabularInline):
    """Setor (UA) onde o usuário atua — complementa sinapse_orgao_id."""

    model = UnidadeAdministrativaResponsavel
    fk_name = "usuario"
    extra = 1
    autocomplete_fields = ("unidade",)
    verbose_name = "Setor (UA)"
    verbose_name_plural = "Setores — onde atua (Órgão › Setor)"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "unidade":
            object_id = request.resolver_match.kwargs.get("object_id") if request.resolver_match else None
            if object_id:
                usuario = Usuario.objects.filter(pk=object_id).first()
                if usuario and usuario.sinapse_orgao_id:
                    kwargs["queryset"] = UnidadeAdministrativa.objects.filter(
                        ativo=True,
                        sinapse_orgao_id=usuario.sinapse_orgao_id,
                    ).order_by("nome")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class UsuarioCustomAdmin(UserAdmin):
    form = UsuarioAdminForm
    add_form = UsuarioCreationAdminForm
    add_form_template = "admin/auth/user/add_form.html"
    inlines = [UsuarioSetorResponsavelInline]

    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "perfil",
        "sinapse_orgao_rotulo",
        "atuacao_resumo",
        "is_staff",
        "is_active",
    )
    list_filter = ("perfil", "is_staff", "is_active")
    search_fields = ("username", "email", "first_name", "last_name")

    @admin.display(description="Órgão (Sinapse)")
    def sinapse_orgao_rotulo(self, obj: Usuario) -> str:
        if not obj.sinapse_orgao_id:
            return "—"
        nome = sinapse_catalog.get_orgao_nome(obj.sinapse_orgao_id)
        return nome or f"ID {obj.sinapse_orgao_id}"

    @admin.display(description="Onde atua no SGDL")
    def atuacao_resumo(self, obj: Usuario) -> str:
        from core.services.usuario_vinculo_service import UsuarioVinculoService

        return UsuarioVinculoService().atuacao_sgdl(obj).get("resumo") or "—"

    fieldsets = UserAdmin.fieldsets + (
        (
            "Perfil SGDL — papel",
            {
                "fields": ("perfil",),
                "description": "Define menus e permissões no frontend.",
            },
        ),
        (
            "Onde atua — Órgão (Sinapse) › Setor (UA)",
            {
                "fields": ("sinapse_orgao_id",),
                "description": (
                    "Órgão Sinapse no nível superior. Setor(es) UA na seção inline abaixo "
                    "(obrigatório para Secretaria). Hub: /gestao-usuarios"
                ),
            },
        ),
        (
            "Perfil SGDL — dados complementares",
            {
                "fields": (
                    "cargo",
                    "telefone",
                    "ramal",
                    "assinatura",
                    "assinatura_imagem",
                    "avatar",
                )
            },
        ),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "Perfil SGDL — papel",
            {"fields": ("perfil",)},
        ),
        (
            "Onde atua — Órgão (Sinapse)",
            {"fields": ("sinapse_orgao_id",)},
        ),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        from core.services.usuario_vinculo_service import UsuarioVinculoService

        if obj.perfil == "PROTOCOLO":
            UsuarioVinculoService().sincronizar_protocolo(obj)
        elif obj.perfil == "GESTOR":
            UsuarioVinculoService().sincronizar_gestor(obj)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        from core.services.usuario_vinculo_service import UsuarioVinculoService

        user = form.instance
        service = UsuarioVinculoService()
        unidade_ids = service.ids_unidades_ativas(user)
        if user.perfil == "SECRETARIA" and user.sinapse_orgao_id and unidade_ids:
            service.sincronizar_secretaria(
                user,
                sinapse_orgao_id=int(user.sinapse_orgao_id),
                unidade_ids=unidade_ids,
            )
        elif user.perfil == "GESTOR":
            service.sincronizar_gestor(
                user,
                sinapse_orgao_id=user.sinapse_orgao_id,
                unidade_ids=unidade_ids,
            )


class TendenciaOcorrenciaInline(admin.TabularInline):
    model = TendenciaOcorrencia
    extra = 0
    readonly_fields = ("criado_em",)
    autocomplete_fields = ("demanda", "session")


class CopilotoFaqPadraoRegexInline(admin.TabularInline):
    model = CopilotoFaqPadraoRegex
    extra = 1
    fields = ("expressao", "ativo", "ordem", "fonte", "notas")
    ordering = ("ordem", "id")


@admin.register(CopilotoFaqOrientacao)
class CopilotoFaqOrientacaoAdmin(admin.ModelAdmin):
    list_display = (
        "titulo",
        "categoria_orientacao",
        "municipio_referencia",
        "ativo",
        "ordem",
        "fonte",
        "ultima_sincronizacao_llm",
        "atualizado_em",
    )
    list_filter = ("ativo", "fonte", "municipio_referencia")
    search_fields = (
        "titulo",
        "slug",
        "categoria_orientacao",
        "mensagem",
        "orgao_hint",
        "notas_internas",
    )
    prepopulated_fields = {"slug": ("titulo",)}
    readonly_fields = ("criado_em", "atualizado_em", "ultima_sincronizacao_llm")
    inlines = [CopilotoFaqPadraoRegexInline]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "slug",
                    "categoria_orientacao",
                    "titulo",
                    "ativo",
                    "ordem",
                    "fonte",
                )
            },
        ),
        (
            "Conteúdo ao cidadão",
            {"fields": ("mensagem", "orgao_hint")},
        ),
        (
            "Contexto Mogi das Cruzes / IA",
            {
                "fields": (
                    "municipio_referencia",
                    "notas_internas",
                    "ultima_sincronizacao_llm",
                    "revisado_por",
                )
            },
        ),
        (
            "Auditoria",
            {"fields": ("criado_em", "atualizado_em"), "classes": ("collapse",)},
        ),
    )


@admin.register(Tendencia)
class TendenciaAdmin(admin.ModelAdmin):
    list_display = (
        "titulo",
        "status",
        "volume_total",
        "sinapse_orgao_id",
        "sinapse_servico_id",
        "ultima_ocorrencia",
    )
    list_filter = ("status",)
    search_fields = ("titulo", "slug", "descricao_resumo")
    readonly_fields = ("slug", "volume_total", "primeira_ocorrencia", "ultima_ocorrencia")
    inlines = [TendenciaOcorrenciaInline]


admin.site.register(Usuario, UsuarioCustomAdmin)


# --- Base Otimizada da Carta de Serviços -----------------------------------


class LogOtimizacaoInline(admin.TabularInline):
    model = LogOtimizacao
    extra = 0
    fields = ("operacao", "timestamp", "usuario", "resumo_detalhes")
    readonly_fields = ("operacao", "timestamp", "usuario", "resumo_detalhes")
    
    def resumo_detalhes(self, obj):
        if obj.detalhes:
            detalhes = obj.detalhes
            resumo = []
            if 'score_depois' in detalhes:
                resumo.append(f"Score: {detalhes.get('score_antes', '?')} → {detalhes['score_depois']}")
            if 'melhorias' in detalhes:
                resumo.append(f"Melhorias: {len(detalhes['melhorias'])}")
            if 'embedding_gerado' in detalhes:
                resumo.append(f"Embedding: {'✅' if detalhes['embedding_gerado'] else '❌'}")
            return " | ".join(resumo) or str(detalhes)[:100]
        return "-"
    resumo_detalhes.short_description = "Resumo"


@admin.register(ServicoOtimizado)
class ServicoOtimizadoAdmin(admin.ModelAdmin):
    change_list_template = "admin/core/servicootimizado/change_list.html"
    actions = ("exportar_csv_selecionados",)
    list_display = (
        "sinapse_servico_id",
        "titulo_otimizado",
        "prazo_dias",
        "qtd_documentos",
        "score_qualidade_otimizado",
        "tem_embedding",
        "status_dados",
        "versao_otimizacao",
        "otimizado_em",
    )
    list_filter = (
        "versao_otimizacao",
        "ativo",
        "score_qualidade_otimizado",
        ("otimizado_em", admin.DateFieldListFilter)
    )
    search_fields = (
        "sinapse_servico_id",
        "titulo_otimizado", 
        "descricao_objetiva",
        "intencao_servico"
    )
    readonly_fields = (
        "sinapse_servico_id",
        "otimizado_em", 
        "atualizado_em",
        "tem_embedding",
        "preview_embedding",
        "preview_texto_rag",
        "descricao_objetiva_status",
        "intencao_servico_status",
        "status_dados"
    )
    
    fieldsets = (
        ("Identificação", {
            "fields": ("sinapse_servico_id", "ativo", "versao_otimizacao")
        }),
        ("📝 Conteúdo Otimizado", {
            "fields": ("titulo_otimizado", "descricao_objetiva_status", "intencao_servico_status")
        }),
        ("🏢 Atendimento e Sistemas", {
            "fields": ("tipos_atendimento", "sistema_solicitacao", "link_sistema")
        }),
        ("Problemas e Soluções", {
            "fields": ("problemas_resolve", "palavras_chave"),
            "classes": ("collapse",)
        }),
        ("Gestão Operacional (Sinapse)", {
            "fields": (
                "tipo_processo", "prazo_dias", "prazo_categoria", "prazo_observacoes",
                "dependencias_documentos",
                "dependencias_pagamentos",
                "dependencias_realizacao",
            ),
        }),
        ("RAG e Embedding", {
            "fields": ("preview_texto_rag", "preview_embedding"),
            "classes": ("collapse",)
        }),
        ("Qualidade e Validação", {
            "fields": (
                "score_qualidade_original", "score_qualidade_otimizado",
                "problemas_identificados", "melhorias_aplicadas",
                "validado_humano", "precisa_revisao"
            )
        }),
        ("Timestamps", {
            "fields": ("otimizado_em", "atualizado_em"),
            "classes": ("collapse",)
        })
    )
    
    inlines = [LogOtimizacaoInline]
    
    def prazo_dias(self, obj):
        if obj.prazo_dias is not None:
            return f"{obj.prazo_dias}d"
        if obj.prazo_observacoes:
            return obj.prazo_observacoes[:20]
        return "—"

    prazo_dias.short_description = "Prazo"
    prazo_dias.admin_order_field = "prazo_dias"

    def qtd_documentos(self, obj):
        n = len(obj.dependencias_documentos or [])
        return n if n else "—"

    qtd_documentos.short_description = "Docs"

    def tem_embedding(self, obj):
        return "✅" if obj.embedding_otimizado is not None else "❌"
    tem_embedding.short_description = "Embedding"
    tem_embedding.admin_order_field = "embedding_otimizado"
    
    def preview_embedding(self, obj):
        if obj.embedding_otimizado is not None:
            import numpy as np
            emb = np.array(obj.embedding_otimizado)
            norma = np.linalg.norm(emb)
            return f"✅ Vetor {emb.shape[0]}D | Norma: {norma:.3f} | Range: [{emb.min():.3f}, {emb.max():.3f}]"
        return "❌ Sem embedding"
    preview_embedding.short_description = "🔢 Status Embedding"
    
    def preview_texto_rag(self, obj):
        """Mostra texto RAG completo com formatação melhorada."""
        from django.utils.safestring import mark_safe
        if obj.texto_rag_otimizado:
            texto = obj.texto_rag_otimizado
            # Detectar problemas de codificação
            problemas_html = ['&oacute;', '&aacute;', '&eacute;', '&ccedil;', '&atilde;', '&nbsp;', '&ordm;']
            tem_problemas = any(prob in texto for prob in problemas_html)
            
            status = "⚠️ CONTÉM ENTIDADES HTML" if tem_problemas else "✅ TEXTO LIMPO"
            
            # Retornar textarea com texto completo
            texto_escaped = texto.replace('"', '&quot;').replace("'", "&#x27;")
            return mark_safe(f'''
                <div>
                    <strong style="color: {'red' if tem_problemas else 'green'};">{status}</strong><br>
                    <textarea rows="12" cols="100" readonly style="font-family: monospace; font-size: 12px; width: 100%; margin-top: 5px;">{texto_escaped}</textarea>
                </div>
            ''')
        return mark_safe('<span style="color: red;">❌ Sem texto RAG</span>')
    preview_texto_rag.short_description = "📄 Texto RAG COMPLETO"
    
    def descricao_objetiva_status(self, obj):
        """Mostra status da descrição objetiva."""
        from django.utils.safestring import mark_safe
        desc = obj.descricao_objetiva or ""
        
        # Verificar problemas de codificação
        problemas_html = ['&oacute;', '&aacute;', '&eacute;', '&ccedil;', '&atilde;', '&nbsp;', '&ordm;']
        tem_problemas = any(prob in desc for prob in problemas_html)
        
        if tem_problemas:
            return mark_safe(f'<span style="color: red;">⚠️ CONTÉM HTML</span><br>{desc[:100]}...')
        elif desc.strip():
            return mark_safe(f'<span style="color: green;">✅ LIMPA</span><br>{desc[:100]}...')
        else:
            return mark_safe('<span style="color: orange;">⚠️ VAZIA</span>')
    descricao_objetiva_status.short_description = "📝 Descrição Objetiva"
    
    def intencao_servico_status(self, obj):
        """Mostra status da intenção do serviço."""
        from django.utils.safestring import mark_safe
        intencao = obj.intencao_servico or ""
        
        if not intencao.strip():
            return mark_safe('<span style="color: red;">❌ NÃO PREENCHIDA</span>')
        elif len(intencao.strip()) < 20:
            return mark_safe(f'<span style="color: orange;">⚠️ MUITO CURTA</span><br>{intencao}')
        else:
            return mark_safe(f'<span style="color: green;">✅ PREENCHIDA</span><br>{intencao[:80]}...')
    intencao_servico_status.short_description = "🎯 Intenção do Serviço"
    
    def status_dados(self, obj):
        """Resumo geral do status dos dados."""
        from django.utils.safestring import mark_safe
        
        # Verificar completude
        checks = []
        
        # Descrição limpa
        desc = obj.descricao_objetiva or ""
        problemas_html = ['&oacute;', '&aacute;', '&eacute;', '&ccedil;', '&atilde;', '&nbsp;']
        desc_ok = desc and not any(prob in desc for prob in problemas_html)
        checks.append(("Descrição", desc_ok))
        
        # Intenção preenchida
        intencao_ok = obj.intencao_servico and len(obj.intencao_servico.strip()) > 20
        checks.append(("Intenção", intencao_ok))
        
        # Problemas estruturados
        problemas_ok = obj.problemas_resolve and len(obj.problemas_resolve) > 0
        checks.append(("Problemas", problemas_ok))
        
        # Sistema/atendimento
        sistema_ok = obj.sistema_solicitacao or obj.tipos_atendimento
        checks.append(("Sistema", sistema_ok))
        
        total_ok = sum(1 for _, ok in checks if ok)
        percent = (total_ok / len(checks)) * 100
        
        if percent >= 75:
            color, icon = "green", "✅"
        elif percent >= 50:
            color, icon = "orange", "⚠️"
        else:
            color, icon = "red", "❌"
            
        return mark_safe(f'<span style="color: {color};">{icon} {percent:.0f}%</span>')
    status_dados.short_description = "📊 Status Dados"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "unidade_administrativa",
            "assunto",
        )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "export-csv/",
                self.admin_site.admin_view(self.export_csv_view),
                name="core_servicootimizado_export_csv",
            ),
        ]
        return custom + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["has_export_csv_permission"] = self.has_export_csv_permission(
            request
        )
        return super().changelist_view(request, extra_context=extra_context)

    def has_export_csv_permission(self, request) -> bool:
        opts = self.model._meta
        return request.user.has_perm(f"{opts.app_label}.view_{opts.model_name}")

    @admin.action(description="Exportar selecionados para CSV")
    def exportar_csv_selecionados(self, request, queryset):
        if not self.has_export_csv_permission(request):
            self.message_user(request, "Sem permissão para exportar.", level="error")
            return None
        return servico_otimizado_csv_response(
            queryset,
            filename="servicos_otimizados_selecionados.csv",
        )

    def export_csv_view(self, request):
        if not self.has_export_csv_permission(request):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        cl = self.get_changelist_instance(request)
        return servico_otimizado_csv_response(cl.get_queryset(request))


@admin.register(LogOtimizacao)
class LogOtimizacaoAdmin(admin.ModelAdmin):
    list_display = ("servico_id", "operacao", "timestamp", "usuario", "resumo_detalhes")
    list_filter = ("operacao", ("timestamp", admin.DateFieldListFilter), "usuario")
    search_fields = ("servico_otimizado__titulo_otimizado", "servico_otimizado__sinapse_servico_id")
    readonly_fields = ("timestamp", "detalhes_formatados")
    
    fieldsets = (
        (None, {
            "fields": ("servico_otimizado", "operacao", "usuario", "timestamp")
        }),
        ("Detalhes", {
            "fields": ("detalhes_formatados",),
            "classes": ("collapse",)
        })
    )
    
    def servico_id(self, obj):
        return obj.servico_otimizado.sinapse_servico_id
    servico_id.short_description = "Serviço ID"
    servico_id.admin_order_field = "servico_otimizado__sinapse_servico_id"
    
    def resumo_detalhes(self, obj):
        if obj.detalhes:
            detalhes = obj.detalhes
            resumo = []
            if 'score_depois' in detalhes:
                resumo.append(f"Score: {detalhes.get('score_antes', '?')} → {detalhes['score_depois']}")
            if 'melhorias' in detalhes:
                resumo.append(f"Melhorias: {len(detalhes['melhorias'])}")
            return " | ".join(resumo) or str(detalhes)[:50]
        return "-"
    resumo_detalhes.short_description = "Resumo"
    
    def detalhes_formatados(self, obj):
        if obj.detalhes:
            import json
            return format_html("<pre>{}</pre>", json.dumps(obj.detalhes, indent=2, ensure_ascii=False))
        return "Nenhum"
    detalhes_formatados.short_description = "Detalhes (JSON)"


@admin.register(EstatisticasBaseOtimizada)
class EstatisticasBaseOtimizadaAdmin(admin.ModelAdmin):
    list_display = (
        "data_referencia", 
        "total_servicos_otimizados",
        "score_medio_otimizado", 
        "melhoria_media",
        "gerado_em"
    )
    list_filter = (("data_referencia", admin.DateFieldListFilter),)
    readonly_fields = ("gerado_em", "percentual_cobertura", "dados_formatados")
    
    fieldsets = (
        ("Resumo", {
            "fields": (
                "data_referencia", "total_servicos_otimizados", "score_medio_otimizado",
                "percentual_cobertura", "melhoria_media", "gerado_em"
            )
        }),
        ("Dados Detalhados", {
            "fields": ("dados_formatados",),
            "classes": ("collapse",)
        })
    )
    
    def percentual_cobertura(self, obj):
        if obj.total_servicos_sinapse > 0:
            pct = (obj.total_servicos_otimizados / obj.total_servicos_sinapse) * 100
            return f"{pct:.1f}%"
        return "0%"
    percentual_cobertura.short_description = "Cobertura Embedding"
    
    def dados_formatados(self, obj):
        # Este campo não existe no modelo atual, remover ou adaptar conforme necessário
        return "Estatísticas calculadas automaticamente"
    dados_formatados.short_description = "Observações"


class UnidadeAdministrativaResponsavelInline(admin.TabularInline):
    model = UnidadeAdministrativaResponsavel
    extra = 0
    autocomplete_fields = ("usuario",)


@admin.register(UnidadeAdministrativa)
class UnidadeAdministrativaAdmin(admin.ModelAdmin):
    list_display = ("sigla", "nome", "sinapse_orgao_rotulo", "ativo", "atualizado_em")
    list_filter = ("ativo", "sinapse_orgao_id")
    search_fields = ("nome", "sigla")
    inlines = [UnidadeAdministrativaResponsavelInline]

    @admin.display(description="Órgão")
    def sinapse_orgao_rotulo(self, obj: UnidadeAdministrativa) -> str:
        if not obj.sinapse_orgao_id:
            return "—"
        nome = sinapse_catalog.get_orgao_nome(obj.sinapse_orgao_id)
        return nome or f"ID {obj.sinapse_orgao_id}"
