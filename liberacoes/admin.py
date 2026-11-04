from django.contrib import admin

from .models import AvaliacaoRegra, HistoricoEvento, Liberacao, Regra, SolicitacaoLiberacao


class SomenteLeituraAdmin(admin.ModelAdmin):
    """Registros de auditoria/decisão: consulta apenas (sem criar, editar ou excluir)."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(HistoricoEvento)
class HistoricoEventoAdmin(SomenteLeituraAdmin):
    list_display = ("criado_em", "tipo", "solicitacao", "usuario", "organizacao")
    list_filter = ("tipo", "organizacao")


@admin.register(SolicitacaoLiberacao)
class SolicitacaoAdmin(SomenteLeituraAdmin):
    list_display = ("id", "motorista", "veiculo", "estado", "organizacao", "criada_em")
    list_filter = ("estado", "organizacao")


@admin.register(Liberacao)
class LiberacaoAdmin(SomenteLeituraAdmin):
    list_display = ("id", "solicitacao", "estado", "valida_de", "valida_ate", "organizacao")
    list_filter = ("estado", "organizacao")


@admin.register(AvaliacaoRegra)
class AvaliacaoRegraAdmin(SomenteLeituraAdmin):
    list_display = ("solicitacao", "regra", "atendida", "organizacao")


@admin.register(Regra)
class RegraAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome", "organizacao", "acao_se_nao_atendida", "ativa", "demonstrativa")
    list_filter = ("organizacao",)
