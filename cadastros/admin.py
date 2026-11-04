from django.contrib import admin

from accounts.admin_site import tcc_admin_site

from .models import Motorista, Transportadora, Veiculo, VinculoMotoristaTransportadora


@admin.register(Transportadora, site=tcc_admin_site)
class TransportadoraAdmin(admin.ModelAdmin):
    list_display = ("nome", "organizacao", "ativa")
    list_filter = ("organizacao",)


@admin.register(Motorista, site=tcc_admin_site)
class MotoristaAdmin(admin.ModelAdmin):
    list_display = ("nome", "cpf_mascarado", "organizacao", "validade_cnh", "ativo")
    list_filter = ("organizacao",)
    exclude = ("cpf",)  # o CPF completo não é exibido no admin; use as telas do sistema

    def has_add_permission(self, request):
        return False  # cadastro de motoristas apenas pelas telas do sistema


@admin.register(Veiculo, site=tcc_admin_site)
class VeiculoAdmin(admin.ModelAdmin):
    list_display = ("placa", "transportadora", "organizacao", "ativo")
    list_filter = ("organizacao",)


@admin.register(VinculoMotoristaTransportadora, site=tcc_admin_site)
class VinculoAdmin(admin.ModelAdmin):
    list_display = ("motorista", "transportadora", "inicio", "fim", "organizacao")
    list_filter = ("organizacao",)
