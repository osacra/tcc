from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView

from accounts.models import Papel
from accounts.permissions import OrganizacaoQuerysetMixin, PapelRequeridoMixin

from . import services
from .estados import TransicaoInvalida
from .forms import DecisaoForm, RevogacaoForm, SolicitacaoForm
from .models import EstadoLiberacao, EstadoSolicitacao, Liberacao, ResultadoAutomatico, SolicitacaoLiberacao

PAPEIS_CONSULTA = (Papel.SOLICITANTE, Papel.ANALISTA, Papel.GESTOR)
PAPEIS_ANALISE = (Papel.ANALISTA, Papel.GESTOR)


def _mensagens_de_erro(erro):
    if isinstance(erro, ValidationError):
        return list(erro.messages)
    return [str(erro)]


class SolicitacaoQuerysetMixin(OrganizacaoQuerysetMixin):
    """Solicitações da organização; o Solicitante enxerga somente as próprias."""

    model = SolicitacaoLiberacao

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related("motorista", "veiculo", "transportadora", "solicitante", "decidida_por")
        )
        if self.request.user.eh_solicitante:
            queryset = queryset.filter(solicitante=self.request.user)
        return queryset


class SolicitacaoListView(PapelRequeridoMixin, SolicitacaoQuerysetMixin, ListView):
    papeis_permitidos = PAPEIS_CONSULTA
    template_name = "liberacoes/solicitacao_lista.html"
    context_object_name = "solicitacoes"
    paginate_by = 25

    def get_queryset(self):
        queryset = super().get_queryset()
        estado = self.request.GET.get("estado")
        if estado in EstadoSolicitacao.values:
            queryset = queryset.filter(estado=estado)
        return queryset

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["estados"] = EstadoSolicitacao.choices
        contexto["estado_atual"] = self.request.GET.get("estado", "")
        contexto["titulo"] = "Minhas solicitações" if self.request.user.eh_solicitante else "Solicitações"
        return contexto


class AnaliseListView(PapelRequeridoMixin, SolicitacaoQuerysetMixin, ListView):
    """Fila de pendências do Analista de Segurança."""

    papeis_permitidos = (Papel.ANALISTA,)
    template_name = "liberacoes/solicitacao_lista.html"
    context_object_name = "solicitacoes"
    paginate_by = 25

    def get_queryset(self):
        return super().get_queryset().filter(estado=EstadoSolicitacao.PENDENTE_ANALISE).order_by("criada_em")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["titulo"] = "Solicitações pendentes de análise"
        contexto["sem_filtro"] = True
        return contexto


class SolicitacaoCreateView(PapelRequeridoMixin, View):
    """Fluxo do Solicitante: preencher → revisar → enviar."""

    papeis_permitidos = (Papel.SOLICITANTE,)

    def _formulario(self, request, dados=None):
        return SolicitacaoForm(dados, organizacao=request.user.organizacao)

    def get(self, request):
        return render(request, "liberacoes/solicitacao_form.html", {"form": self._formulario(request)})

    def post(self, request):
        form = self._formulario(request, request.POST)
        if not form.is_valid():
            return render(request, "liberacoes/solicitacao_form.html", {"form": form})
        if request.POST.get("etapa") != "enviar":
            return render(
                request, "liberacoes/solicitacao_revisao.html", {"form": form, "dados": form.cleaned_data}
            )
        try:
            solicitacao = services.solicitar_liberacao(usuario=request.user, **form.cleaned_data)
        except ValidationError as erro:
            for mensagem in erro.messages:
                messages.error(request, mensagem)
            return render(request, "liberacoes/solicitacao_form.html", {"form": form})
        textos = {
            ResultadoAutomatico.APROVACAO: "Solicitação aprovada automaticamente.",
            ResultadoAutomatico.REPROVACAO: "Solicitação reprovada automaticamente. Veja os motivos abaixo.",
            ResultadoAutomatico.PENDENCIA: "Solicitação encaminhada para análise manual.",
        }
        nivel = {
            ResultadoAutomatico.APROVACAO: messages.success,
            ResultadoAutomatico.REPROVACAO: messages.error,
            ResultadoAutomatico.PENDENCIA: messages.warning,
        }[solicitacao.resultado_automatico]
        nivel(request, textos[solicitacao.resultado_automatico])
        return redirect("solicitacao_detalhe", pk=solicitacao.pk)


class SolicitacaoDetailView(PapelRequeridoMixin, SolicitacaoQuerysetMixin, DetailView):
    papeis_permitidos = PAPEIS_CONSULTA
    template_name = "liberacoes/solicitacao_detalhe.html"
    context_object_name = "solicitacao"

    def get_object(self, queryset=None):
        services.expirar_liberacoes_vencidas(self.request.user.organizacao)
        return super().get_object(queryset)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        solicitacao = self.object
        usuario = self.request.user
        liberacao = (
            Liberacao.objects.da_organizacao(usuario.organizacao).filter(solicitacao=solicitacao).first()
        )
        contexto["liberacao"] = liberacao
        contexto["avaliacoes"] = solicitacao.avaliacoes.select_related("regra")
        contexto["eventos"] = solicitacao.eventos.select_related("usuario")
        if usuario.eh_analista:
            if solicitacao.estado == EstadoSolicitacao.PENDENTE_ANALISE:
                contexto["form_decisao"] = DecisaoForm()
            if liberacao and liberacao.estado == EstadoLiberacao.VIGENTE:
                contexto["form_revogacao"] = RevogacaoForm()
        return contexto


class DecidirView(PapelRequeridoMixin, View):
    papeis_permitidos = (Papel.ANALISTA,)
    http_method_names = ["post"]

    def post(self, request, pk):
        form = DecisaoForm(request.POST)
        destino = redirect("solicitacao_detalhe", pk=pk)
        if not form.is_valid():
            for erros in form.errors.values():
                for erro in erros:
                    messages.error(request, erro)
            return destino
        try:
            services.decidir_manualmente(
                solicitacao_id=pk,
                usuario=request.user,
                aprovar=form.cleaned_data["acao"] == "aprovar",
                justificativa=form.cleaned_data["justificativa"],
            )
        except ObjectDoesNotExist as erro:
            raise Http404 from erro
        except (ValidationError, TransicaoInvalida) as erro:
            for mensagem in _mensagens_de_erro(erro):
                messages.error(request, mensagem)
            return destino
        messages.success(request, "Decisão registrada.")
        return destino


class LiberacaoListView(PapelRequeridoMixin, OrganizacaoQuerysetMixin, ListView):
    papeis_permitidos = PAPEIS_ANALISE
    model = Liberacao
    template_name = "liberacoes/liberacao_lista.html"
    context_object_name = "liberacoes"
    paginate_by = 25

    def get_queryset(self):
        services.expirar_liberacoes_vencidas(self.request.user.organizacao)
        queryset = (
            super()
            .get_queryset()
            .select_related("solicitacao__motorista", "solicitacao__veiculo", "solicitacao__transportadora")
        )
        estado = self.request.GET.get("estado")
        if estado in EstadoLiberacao.values:
            queryset = queryset.filter(estado=estado)
        return queryset

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["estados"] = EstadoLiberacao.choices
        contexto["estado_atual"] = self.request.GET.get("estado", "")
        return contexto


class RevogarView(PapelRequeridoMixin, View):
    papeis_permitidos = (Papel.ANALISTA,)
    http_method_names = ["post"]

    def post(self, request, pk):
        form = RevogacaoForm(request.POST)
        liberacao = Liberacao.objects.da_organizacao(request.user.organizacao).filter(pk=pk).first()
        if liberacao is None:
            raise Http404
        destino = redirect(reverse("solicitacao_detalhe", args=[liberacao.solicitacao_id]))
        if not form.is_valid():
            for erros in form.errors.values():
                for erro in erros:
                    messages.error(request, erro)
            return destino
        try:
            services.revogar_liberacao(
                liberacao_id=pk, usuario=request.user, justificativa=form.cleaned_data["justificativa"]
            )
        except (ValidationError, TransicaoInvalida) as erro:
            for mensagem in _mensagens_de_erro(erro):
                messages.error(request, mensagem)
            return destino
        messages.success(request, "Liberação revogada.")
        return destino
