"""Telas de cadastro (restritas ao Administrador da organização)."""

from django.contrib import messages
from django.db.models import ProtectedError
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from accounts.models import Papel
from accounts.permissions import OrganizacaoQuerysetMixin, PapelRequeridoMixin

from .forms import MotoristaForm, TransportadoraForm, VeiculoForm, VinculoForm
from .models import Motorista, Transportadora, Veiculo, VinculoMotoristaTransportadora


class CadastroMixin(PapelRequeridoMixin, OrganizacaoQuerysetMixin):
    papeis_permitidos = (Papel.ADMINISTRADOR,)
    slug = ""
    titulo = ""

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["titulo"] = self.titulo
        contexto["slug"] = self.slug
        contexto["voltar"] = reverse(f"{self.slug}_lista")
        return contexto

    def get_success_url(self):
        return reverse(f"{self.slug}_lista")


class CadastroListView(CadastroMixin, ListView):
    template_name = "cadastros/lista.html"
    paginate_by = 25
    colunas: list = []

    def get_queryset(self):
        return super().get_queryset().select_related(*self.select_related)

    select_related: tuple = ()

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["colunas"] = self.colunas
        return contexto


class CadastroFormMixin(CadastroMixin):
    template_name = "cadastros/form.html"
    form_class = None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organizacao"] = self.request.user.organizacao
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Registro salvo.")
        return super().form_valid(form)


class CadastroCreateView(CadastroFormMixin, CreateView):
    pass


class CadastroUpdateView(CadastroFormMixin, UpdateView):
    pass


class CadastroDeleteView(CadastroMixin, DeleteView):
    template_name = "cadastros/confirmar_exclusao.html"

    def form_valid(self, form):
        try:
            resposta = super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                "Este registro já é usado em outros cadastros ou solicitações e não pode ser "
                "excluído. Inative-o, se necessário.",
            )
            return redirect(self.get_success_url())
        messages.success(self.request, "Registro excluído.")
        return resposta


def _crud(modelo, formulario, slug, titulo, colunas, relacionados=()):
    """Monta as quatro views de um cadastro a partir de sua configuração."""
    base = {"model": modelo, "slug": slug, "titulo": titulo}
    lista = type(
        f"{modelo.__name__}ListView",
        (CadastroListView,),
        {**base, "colunas": colunas, "select_related": relacionados},
    )
    novo = type(f"{modelo.__name__}CreateView", (CadastroCreateView,), {**base, "form_class": formulario})
    editar = type(f"{modelo.__name__}UpdateView", (CadastroUpdateView,), {**base, "form_class": formulario})
    excluir = type(f"{modelo.__name__}DeleteView", (CadastroDeleteView,), base)
    return lista, novo, editar, excluir


TransportadoraViews = _crud(
    Transportadora,
    TransportadoraForm,
    "transportadora",
    "Transportadoras",
    [("Nome", "nome"), ("CNPJ", "cnpj"), ("Ativa", "ativa")],
)
MotoristaViews = _crud(
    Motorista,
    MotoristaForm,
    "motorista",
    "Motoristas",
    [
        ("Nome", "nome"),
        ("CPF", "cpf_mascarado"),
        ("CNH", "categoria_cnh"),
        ("Validade da CNH", "validade_cnh"),
        ("Ativo", "ativo"),
    ],
)
VeiculoViews = _crud(
    Veiculo,
    VeiculoForm,
    "veiculo",
    "Veículos",
    [("Placa", "placa"), ("Transportadora", "transportadora"), ("Ativo", "ativo")],
    ("transportadora",),
)
VinculoViews = _crud(
    VinculoMotoristaTransportadora,
    VinculoForm,
    "vinculo",
    "Vínculos motorista–transportadora",
    [("Motorista", "motorista"), ("Transportadora", "transportadora"), ("Início", "inicio"), ("Fim", "fim")],
    ("motorista", "transportadora"),
)
