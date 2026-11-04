from django.contrib import admin

from accounts.admin_site import tcc_admin_site

from .models import AvaliacaoRegra, HistoricoEvento, Liberacao, Regra, SolicitacaoLiberacao


class SomenteLeituraAdmin(admin.ModelAdmin):
    """Registros de auditoria/decisão: consulta apenas (sem criar, editar ou excluir)."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(HistoricoEvento, site=tcc_admin_site)
class HistoricoEventoAdmin(SomenteLeituraAdmin):
    list_display = ("criado_em", "tipo", "solicitacao", "usuario", "organizacao")
    list_filter = ("tipo", "organizacao")


@admin.register(SolicitacaoLiberacao, site=tcc_admin_site)
class SolicitacaoAdmin(SomenteLeituraAdmin):
    list_display = ("id", "motorista", "veiculo", "estado", "organizacao", "criada_em")
    list_filter = ("estado", "organizacao")


@admin.register(Liberacao, site=tcc_admin_site)
class LiberacaoAdmin(SomenteLeituraAdmin):
    list_display = ("id", "solicitacao", "estado", "valida_de", "valida_ate", "organizacao")
    list_filter = ("estado", "organizacao")


@admin.register(AvaliacaoRegra, site=tcc_admin_site)
class AvaliacaoRegraAdmin(SomenteLeituraAdmin):
    list_display = ("solicitacao", "regra", "atendida", "organizacao")


@admin.register(Regra, site=tcc_admin_site)
class RegraAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome", "organizacao", "acao_se_nao_atendida", "ativa", "demonstrativa")
    list_filter = ("organizacao",)
