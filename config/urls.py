from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("accounts.urls")),
    path("cadastros/", include("cadastros.urls")),
    path("", include("liberacoes.urls")),
]
