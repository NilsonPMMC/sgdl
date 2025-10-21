from django.contrib import admin
from django.contrib.auth.admin import UserAdmin 
from .models import Secretaria, Servico, Demanda, Usuario, Anexo, Tramitacao, AnexoTramitacao

class AnexoTramitacaoInline(admin.TabularInline):
    model = AnexoTramitacao
    extra = 1

@admin.register(Tramitacao)
class TramitacaoAdmin(admin.ModelAdmin):
    list_display = ('demanda', 'tipo', 'responsavel', 'timestamp')
    list_filter = ('tipo',)
    inlines = [AnexoTramitacaoInline]

class TramitacaoInline(admin.TabularInline):
    model = Tramitacao
    extra = 0
    readonly_fields = ('tipo', 'descricao', 'responsavel', 'timestamp') 
    can_delete = False
    def has_add_permission(self, request, obj=None):
        return False

@admin.register(Demanda)
class DemandaAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'status', 'secretaria_destino', 'data_criacao')
    list_filter = ('status', 'secretaria_destino')
    readonly_fields = ('protocolo_legislativo', 'protocolo_executivo', 'data_criacao')
    inlines = [TramitacaoInline]

class UsuarioCustomAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'perfil', 'secretaria')
    fieldsets = UserAdmin.fieldsets + (
        ('Vínculos', {'fields': ('perfil', 'secretaria')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': ('perfil', 'secretaria')}),
    )

admin.site.register(Secretaria)
admin.site.register(Servico)
admin.site.register(Anexo)
admin.site.register(AnexoTramitacao)
admin.site.register(Usuario, UsuarioCustomAdmin)