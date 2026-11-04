from django.urls import path

from . import views

urlpatterns = [
    path("solicitacoes/", views.SolicitacaoListView.as_view(), name="solicitacao_lista"),
    path("solicitacoes/nova/", views.SolicitacaoCreateView.as_view(), name="solicitacao_nova"),
    path("solicitacoes/<int:pk>/", views.SolicitacaoDetailView.as_view(), name="solicitacao_detalhe"),
    path("solicitacoes/<int:pk>/decidir/", views.DecidirView.as_view(), name="solicitacao_decidir"),
    path("analise/", views.AnaliseListView.as_view(), name="analise_lista"),
    path("liberacoes/", views.LiberacaoListView.as_view(), name="liberacao_lista"),
    path("liberacoes/<int:pk>/revogar/", views.RevogarView.as_view(), name="liberacao_revogar"),
]
