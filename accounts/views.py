from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, TemplateView, UpdateView

from .forms import OrganizacaoForm, OrganizacaoNovaForm, UsuarioCriarForm, UsuarioEditarForm
from .models import Organizacao, Papel, Usuario
from .permissions import PapelRequeridoMixin, UsuarioAtivoMixin


class HomeView(UsuarioAtivoMixin, TemplateView):
    """Página inicial conforme o papel do usuário."""

    template_name = "home.html"

    def get_context_data(self, **kwargs):
        from cadastros.models import Motorista, Transportadora, Veiculo
        from liberacoes.models import EstadoSolicitacao, Liberacao, SolicitacaoLiberacao
        from liberacoes.services import expirar_liberacoes_vencidas

        contexto = super().get_context_data(**kwargs)
        usuario = self.request.user
        organizacao = usuario.organizacao
        contexto["cartoes"] = []
        if usuario.eh_superadministrador:
            contexto["cartoes"].append(("Organizações", Organizacao.objects.count(), "organizacao_lista"))
        elif organizacao is not None:
            expirar_liberacoes_vencidas(organizacao)
            solicitacoes = SolicitacaoLiberacao.objects.da_organizacao(organizacao)
            if usuario.eh_administrador:
                contexto["cartoes"] += [
                    ("Usuários", Usuario.objects.filter(organizacao=organizacao).count(), "usuario_lista"),
                    (
                        "Transportadoras",
                        Transportadora.objects.da_organizacao(organizacao).count(),
                        "transportadora_lista",
                    ),
                    ("Motoristas", Motorista.objects.da_organizacao(organizacao).count(), "motorista_lista"),
                    ("Veículos", Veiculo.objects.da_organizacao(organizacao).count(), "veiculo_lista"),
                ]
            if usuario.eh_solicitante:
                minhas = solicitacoes.filter(solicitante=usuario)
                contexto["cartoes"] += [("Minhas solicitações", minhas.count(), "solicitacao_lista")]
            if usuario.eh_analista:
                pendentes = solicitacoes.filter(estado=EstadoSolicitacao.PENDENTE_ANALISE).count()
                vigentes = Liberacao.objects.da_organizacao(organizacao).filter(estado="vigente").count()
                contexto["cartoes"] += [
                    ("Pendentes de análise", pendentes, "analise_lista"),
                    ("Liberações vigentes", vigentes, "liberacao_lista"),
                ]
            if usuario.eh_gestor:
                contexto["cartoes"] += [
                    ("Solicitações", solicitacoes.count(), "solicitacao_lista"),
                    ("Liberações", Liberacao.objects.da_organizacao(organizacao).count(), "liberacao_lista"),
                ]
        return contexto


class SuperadministradorMixin(PapelRequeridoMixin):
    papeis_permitidos = (Papel.SUPERADMINISTRADOR,)


class AdministradorMixin(PapelRequeridoMixin):
    papeis_permitidos = (Papel.ADMINISTRADOR,)


# --- Organizações (Superadministrador) ------------------------------------------------------


class OrganizacaoListView(SuperadministradorMixin, ListView):
    model = Organizacao
    template_name = "accounts/organizacao_lista.html"
    context_object_name = "organizacoes"


class OrganizacaoCreateView(SuperadministradorMixin, CreateView):
    model = Organizacao
    form_class = OrganizacaoNovaForm
    template_name = "accounts/form.html"
    success_url = reverse_lazy("organizacao_lista")
    extra_context = {"titulo": "Nova organização", "voltar": reverse_lazy("organizacao_lista")}

    @transaction.atomic
    def form_valid(self, form):
        resposta = super().form_valid(form)
        messages.success(self.request, "Organização e primeiro administrador criados.")
        return resposta


class OrganizacaoUpdateView(SuperadministradorMixin, UpdateView):
    model = Organizacao
    form_class = OrganizacaoForm
    template_name = "accounts/form.html"
    success_url = reverse_lazy("organizacao_lista")
    extra_context = {"titulo": "Editar organização", "voltar": reverse_lazy("organizacao_lista")}

    def form_valid(self, form):
        messages.success(self.request, "Organização atualizada.")
        return super().form_valid(form)


# --- Usuários da organização (Administrador) ------------------------------------------------


class UsuarioQuerysetMixin:
    """Usuários também são filtrados pela organização do administrador autenticado."""

    def get_queryset(self):
        return Usuario.objects.filter(organizacao=self.request.user.organizacao).exclude(
            papel=Papel.SUPERADMINISTRADOR
        )


class UsuarioListView(AdministradorMixin, UsuarioQuerysetMixin, ListView):
    template_name = "accounts/usuario_lista.html"
    context_object_name = "usuarios"


class UsuarioCreateView(AdministradorMixin, CreateView):
    model = Usuario
    form_class = UsuarioCriarForm
    template_name = "accounts/form.html"
    success_url = reverse_lazy("usuario_lista")
    extra_context = {"titulo": "Novo usuário", "voltar": reverse_lazy("usuario_lista")}

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organizacao"] = self.request.user.organizacao
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Usuário criado.")
        return super().form_valid(form)


class UsuarioUpdateView(AdministradorMixin, UsuarioQuerysetMixin, UpdateView):
    form_class = UsuarioEditarForm
    template_name = "accounts/form.html"
    success_url = reverse_lazy("usuario_lista")
    extra_context = {"titulo": "Editar usuário", "voltar": reverse_lazy("usuario_lista")}

    def form_valid(self, form):
        if form.instance.pk == self.request.user.pk and (
            not form.cleaned_data["is_active"] or form.cleaned_data["papel"] != Papel.ADMINISTRADOR
        ):
            messages.error(self.request, "Você não pode desativar ou rebaixar o próprio usuário.")
            return redirect("usuario_lista")
        era_administrador_ativo = form.instance.is_active and form.instance.papel == Papel.ADMINISTRADOR
        deixara_de_ser_administrador = (
            not form.cleaned_data["is_active"] or form.cleaned_data["papel"] != Papel.ADMINISTRADOR
        )
        if era_administrador_ativo and deixara_de_ser_administrador:
            restantes = Usuario.objects.filter(
                organizacao=self.request.user.organizacao,
                papel=Papel.ADMINISTRADOR,
                is_active=True,
            ).exclude(pk=form.instance.pk)
            if not restantes.exists():
                messages.error(
                    self.request, "A organização precisa manter pelo menos um administrador ativo."
                )
                return redirect("usuario_lista")
        messages.success(self.request, "Usuário atualizado.")
        return super().form_valid(form)
