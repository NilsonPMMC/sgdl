"""Registros admin complementares — modelos que não estavam expostos no painel."""

from django.contrib import admin
from django.utils.html import format_html

from integrations import sinapse_catalog

from ..models import (
    ChatSessaoAnexo,
    CopilotoFaqPadraoRegex,
    TendenciaOcorrencia,
)
from ..models_assinatura_eletronica import AssinaturaPendingAcao
from ..models_assunto_carta import AssuntoCarta
from ..models_texto_padrao_despacho import TextoPadraoDespacho
from ..models_carta_metadata import (
    EstatisticasOtimizacaoCarta,
    HistoricoOtimizacaoServico,
    ServicoMetadataRico,
)
from ..models_config import ConfiguracaoCarta
from ..models_depara_rm import DeParaRmSinapse
from ..models_encerramento_legislativo import EncerramentoLegislativo
from ..models_unidade_administrativa import UnidadeAdministrativaResponsavel


# --- Assinatura eletrônica (pendências) --------------------------------------


@admin.register(AssinaturaPendingAcao)
class AssinaturaPendingAcaoAdmin(admin.ModelAdmin):
    list_display = ("demanda", "etapa", "hash_curto", "criado_em")
    list_filter = ("etapa",)
    search_fields = (
        "demanda__protocolo_legislativo",
        "demanda__titulo",
        "hash_documento",
    )
    readonly_fields = ("payload_preview", "criado_em")
    autocomplete_fields = ("demanda",)
    ordering = ("-criado_em",)

    @admin.display(description="Hash")
    def hash_curto(self, obj: AssinaturaPendingAcao) -> str:
        return (obj.hash_documento or "")[:12] + "…"

    @admin.display(description="Payload (JSON)")
    def payload_preview(self, obj: AssinaturaPendingAcao) -> str:
        import json

        try:
            texto = json.dumps(obj.payload, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            texto = str(obj.payload)
        if len(texto) > 8000:
            texto = texto[:8000] + "\n…"
        return format_html("<pre style='max-height:400px;overflow:auto'>{}</pre>", texto)


# --- FAQ Copiloto — padrões regex (consulta avulsa) --------------------------


@admin.register(CopilotoFaqPadraoRegex)
class CopilotoFaqPadraoRegexAdmin(admin.ModelAdmin):
    list_display = ("expressao_curta", "faq", "ativo", "ordem", "fonte", "criado_em")
    list_filter = ("ativo", "fonte")
    search_fields = ("expressao", "faq__titulo", "faq__categoria_orientacao", "notas")
    autocomplete_fields = ("faq",)
    ordering = ("ordem", "id")

    @admin.display(description="Expressão")
    def expressao_curta(self, obj: CopilotoFaqPadraoRegex) -> str:
        return (obj.expressao or "")[:70]


# --- Configuração carta (SLA) ------------------------------------------------


@admin.register(ConfiguracaoCarta)
class ConfiguracaoCartaAdmin(admin.ModelAdmin):
    list_display = ("politica_prazo", "prazo_padrao_dias", "atualizado_em")
    readonly_fields = ("pk_fixo", "atualizado_em")

    def has_add_permission(self, request):
        return not ConfiguracaoCarta.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


# --- Assuntos temáticos da carta ---------------------------------------------


@admin.register(AssuntoCarta)
class AssuntoCartaAdmin(admin.ModelAdmin):
    list_display = (
        "nome",
        "slug",
        "modo_utilizacao_sgdl",
        "ordem",
        "ativo",
        "atualizado_em",
    )
    list_filter = ("ativo", "modo_utilizacao_sgdl")
    search_fields = ("nome", "slug", "mensagem_orientacao")
    prepopulated_fields = {"slug": ("nome",)}
    ordering = ("ordem", "nome")


@admin.register(TextoPadraoDespacho)
class TextoPadraoDespachoAdmin(admin.ModelAdmin):
    list_display = (
        "titulo",
        "categoria",
        "escopo_tipo",
        "sinapse_orgao_id",
        "ativo",
        "ordem",
        "criado_por",
        "atualizado_em",
    )
    list_filter = ("ativo", "categoria", "escopo_tipo")
    search_fields = ("titulo", "corpo")
    autocomplete_fields = ("criado_por",)
    filter_horizontal = ("unidades",)
    ordering = ("ordem", "titulo")


# --- De-para RM ↔ Sinapse ----------------------------------------------------


@admin.register(DeParaRmSinapse)
class DeParaRmSinapseAdmin(admin.ModelAdmin):
    list_display = (
        "cod_rm",
        "sinapse_orgao_rotulo",
        "ativo",
        "observacao",
        "atualizado_em",
    )
    list_filter = ("ativo",)
    search_fields = ("cod_rm", "observacao")
    ordering = ("cod_rm",)

    @admin.display(description="Órgão Sinapse")
    def sinapse_orgao_rotulo(self, obj: DeParaRmSinapse) -> str:
        if not obj.sinapse_orgao_id:
            return "pendente"
        nome = sinapse_catalog.get_orgao_nome(obj.sinapse_orgao_id)
        return nome or f"ID {obj.sinapse_orgao_id}"


# --- Encerramento legislativo ------------------------------------------------


@admin.register(EncerramentoLegislativo)
class EncerramentoLegislativoAdmin(admin.ModelAdmin):
    list_display = (
        "demanda",
        "ciencia_em",
        "ciencia_por",
        "encerrado_em",
        "atualizado_em",
    )
    list_filter = ("encerrado_em", "ciencia_em")
    search_fields = (
        "demanda__protocolo_legislativo",
        "demanda__titulo",
        "texto_resposta_cidadao",
    )
    autocomplete_fields = ("demanda", "ciencia_por")
    readonly_fields = ("criado_em", "atualizado_em")
    date_hierarchy = "criado_em"


# --- Metadados ricos da carta (legado / complementar) ------------------------


class HistoricoOtimizacaoServicoInline(admin.TabularInline):
    model = HistoricoOtimizacaoServico
    extra = 0
    fields = (
        "tipo_otimizacao",
        "score_qualidade_antes",
        "score_qualidade_depois",
        "aplicado_automaticamente",
        "timestamp_aplicacao",
    )
    readonly_fields = ("timestamp_aplicacao",)
    ordering = ("-timestamp_aplicacao",)


@admin.register(ServicoMetadataRico)
class ServicoMetadataRicoAdmin(admin.ModelAdmin):
    list_display = (
        "sinapse_servico_id",
        "tipo_processo",
        "prazo_categoria",
        "score_qualidade_texto",
        "necessita_revisao",
        "atualizado_em",
    )
    list_filter = (
        "tipo_processo",
        "prazo_categoria",
        "necessita_revisao",
        "tem_problemas_html",
    )
    search_fields = ("sinapse_servico_id", "texto_rag_otimizado")
    readonly_fields = ("criado_em", "atualizado_em")
    inlines = [HistoricoOtimizacaoServicoInline]


@admin.register(HistoricoOtimizacaoServico)
class HistoricoOtimizacaoServicoAdmin(admin.ModelAdmin):
    list_display = (
        "servico_metadata",
        "tipo_otimizacao",
        "score_qualidade_antes",
        "score_qualidade_depois",
        "aplicado_automaticamente",
        "timestamp_aplicacao",
    )
    list_filter = ("tipo_otimizacao", "aplicado_automaticamente")
    search_fields = ("servico_metadata__sinapse_servico_id", "descricao_mudanca")
    readonly_fields = ("timestamp_aplicacao",)
    autocomplete_fields = ("servico_metadata", "usuario_aplicou")


@admin.register(EstatisticasOtimizacaoCarta)
class EstatisticasOtimizacaoCartaAdmin(admin.ModelAdmin):
    list_display = (
        "data_referencia",
        "total_servicos_carta",
        "total_servicos_otimizados",
        "score_qualidade_medio_atual",
        "processado_em",
    )
    list_filter = (("data_referencia", admin.DateFieldListFilter),)
    readonly_fields = ("processado_em",)
    ordering = ("-data_referencia",)


# --- Vínculos e anexos (consulta avulsa) -------------------------------------


@admin.register(ChatSessaoAnexo)
class ChatSessaoAnexoAdmin(admin.ModelAdmin):
    list_display = ("session", "descricao", "indice_demanda", "arquivo", "criado_em")
    list_filter = ("criado_em",)
    search_fields = ("descricao", "session__id", "session__autor__username")
    autocomplete_fields = ("session",)
    readonly_fields = ("criado_em",)


@admin.register(TendenciaOcorrencia)
class TendenciaOcorrenciaAdmin(admin.ModelAdmin):
    list_display = ("tendencia", "demanda", "session", "criado_em")
    list_filter = ("criado_em",)
    search_fields = ("tendencia__titulo", "demanda__titulo")
    autocomplete_fields = ("tendencia", "demanda", "session")
    readonly_fields = ("criado_em",)


@admin.register(UnidadeAdministrativaResponsavel)
class UnidadeAdministrativaResponsavelAdmin(admin.ModelAdmin):
    list_display = ("usuario", "unidade", "ativo", "criado_em")
    list_filter = ("ativo",)
    search_fields = (
        "usuario__username",
        "usuario__email",
        "unidade__nome",
        "unidade__sigla",
    )
    autocomplete_fields = ("usuario", "unidade")
