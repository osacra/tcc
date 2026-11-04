from django.contrib.admin import AdminSite

from .models import Papel


class TccAdminSite(AdminSite):
    """Admin técnico restrito ao superadministrador da aplicação."""

    site_header = "Administração técnica do sistema"
    site_title = "Administração técnica"
    index_title = "Administração técnica"

    def has_permission(self, request):
        usuario = request.user
        return bool(
            usuario.is_active
            and usuario.is_staff
            and usuario.is_superuser
            and usuario.papel == Papel.SUPERADMINISTRADOR
        )


tcc_admin_site = TccAdminSite(name="admin")
