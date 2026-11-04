from django.urls import path

from . import views


def rotas(slug, plural, conjunto):
    lista, novo, editar, excluir = conjunto
    return [
        path(f"{plural}/", lista.as_view(), name=f"{slug}_lista"),
        path(f"{plural}/novo/", novo.as_view(), name=f"{slug}_novo"),
        path(f"{plural}/<int:pk>/editar/", editar.as_view(), name=f"{slug}_editar"),
        path(f"{plural}/<int:pk>/excluir/", excluir.as_view(), name=f"{slug}_excluir"),
    ]


urlpatterns = (
    rotas("transportadora", "transportadoras", views.TransportadoraViews)
    + rotas("motorista", "motoristas", views.MotoristaViews)
    + rotas("veiculo", "veiculos", views.VeiculoViews)
    + rotas("vinculo", "vinculos", views.VinculoViews)
)
