from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .admin_site import tcc_admin_site
from .models import Organizacao, Usuario


@admin.register(Organizacao, site=tcc_admin_site)
class OrganizacaoAdmin(admin.ModelAdmin):
    list_display = ("nome", "ativa", "criada_em")


@admin.register(Usuario, site=tcc_admin_site)
class UsuarioAdmin(UserAdmin):
    list_display = ("username", "first_name", "papel", "organizacao", "is_active")
    list_filter = ("papel", "organizacao", "is_active")
    fieldsets = UserAdmin.fieldsets + (("Organização e papel", {"fields": ("organizacao", "papel")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Organização e papel", {"fields": ("organizacao", "papel")}),)
