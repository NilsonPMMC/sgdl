from django.contrib import admin
from .models import Secretaria, Servico, Demanda, Usuario, Anexo, Tramitacao, AnexoTramitacao

# Inline para os anexos da tramitação
class AnexoTramitacaoInline(admin.TabularInline):
    model = AnexoTramitacao
    extra = 1

# Customização para a Tramitação
@admin.register(Tramitacao)
class TramitacaoAdmin(admin.ModelAdmin):
    list_display = ('demanda', 'tipo', 'usuario', 'timestamp')
    list_filter = ('tipo',)
    inlines = [AnexoTramitacaoInline]

# Inline para as tramitações dentro da Demanda
class TramitacaoInline(admin.TabularInline):
    model = Tramitacao
    extra = 0
    readonly_fields = ('tipo', 'descricao', 'usuario', 'timestamp')
    can_delete = False
    def has_add_permission(self, request, obj=None):
        return False

# Customização da Demanda, agora com a nova TramitacaoInline
@admin.register(Demanda)
class DemandaAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'status', 'secretaria_destino', 'data_criacao')
    list_filter = ('status', 'secretaria_destino')
    readonly_fields = ('protocolo_legislativo', 'protocolo_executivo', 'data_criacao')
    inlines = [TramitacaoInline] # ✅ Substituímos o antigo inline pelo novo

# Registros dos outros modelos
admin.site.register(Secretaria)
admin.site.register(Servico)
admin.site.register(Usuario)
admin.site.register(Anexo)
admin.site.register(AnexoTramitacao)