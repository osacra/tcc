from django.urls import include, path

from accounts.admin_site import tcc_admin_site

urlpatterns = [
    path("admin/", tcc_admin_site.urls),
    path("", include("accounts.urls")),
    path("cadastros/", include("cadastros.urls")),
    path("", include("liberacoes.urls")),
]
