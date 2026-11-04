from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import LoginForm

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html", authentication_form=LoginForm),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("organizacoes/", views.OrganizacaoListView.as_view(), name="organizacao_lista"),
    path("organizacoes/nova/", views.OrganizacaoCreateView.as_view(), name="organizacao_nova"),
    path("organizacoes/<int:pk>/editar/", views.OrganizacaoUpdateView.as_view(), name="organizacao_editar"),
    path("usuarios/", views.UsuarioListView.as_view(), name="usuario_lista"),
    path("usuarios/novo/", views.UsuarioCreateView.as_view(), name="usuario_novo"),
    path("usuarios/<int:pk>/editar/", views.UsuarioUpdateView.as_view(), name="usuario_editar"),
]
