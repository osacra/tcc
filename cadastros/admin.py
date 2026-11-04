from django.contrib import admin

from .models import Motorista, Transportadora, Veiculo, VinculoMotoristaTransportadora


@admin.register(Transportadora)
class TransportadoraAdmin(admin.ModelAdmin):
    list_display = ("nome", "organizacao", "ativa")
    list_filter = ("organizacao",)


@admin.register(Motorista)
class MotoristaAdmin(admin.ModelAdmin):
    list_display = ("nome", "cpf_mascarado", "organizacao", "validade_cnh", "ativo")
    list_filter = ("organizacao",)
    exclude = ("cpf",)  # o CPF completo não é exibido no admin; use as telas do sistema

    def has_add_permission(self, request):
        return False  # cadastro de motoristas apenas pelas telas do sistema


@admin.register(Veiculo)
class VeiculoAdmin(admin.ModelAdmin):
    list_display = ("placa", "transportadora", "organizacao", "ativo")
    list_filter = ("organizacao",)


@admin.register(VinculoMotoristaTransportadora)
class VinculoAdmin(admin.ModelAdmin):
    list_display = ("motorista", "transportadora", "inicio", "fim", "organizacao")
    list_filter = ("organizacao",)
