"""Controle de acesso por papéis e isolamento por organização para as views."""

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied

from .models import Papel


class UsuarioAtivoMixin(LoginRequiredMixin):
    """Permite acesso somente a contas ativas em organizações ativas."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not self.test_func():
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def test_func(self):
        usuario = self.request.user
        if not usuario.is_authenticated or not usuario.is_active:
            return False
        if usuario.papel == Papel.SUPERADMINISTRADOR:
            return True
        return usuario.organizacao_id is not None and usuario.organizacao.ativa


class PapelRequeridoMixin(UserPassesTestMixin):
    """Permite acesso apenas aos papéis em ``papeis_permitidos``.

    Anônimo -> redireciona ao login. Autenticado sem permissão -> HTTP 403.
    Usuário de organização inativa também é bloqueado.
    """

    papeis_permitidos: tuple = ()

    def test_func(self):
        usuario = self.request.user
        if not (usuario.is_authenticated and usuario.is_active):
            return False
        if usuario.papel not in self.papeis_permitidos:
            return False
        if usuario.papel == Papel.SUPERADMINISTRADOR:
            return True
        return usuario.organizacao_id is not None and usuario.organizacao.ativa


class OrganizacaoQuerysetMixin:
    """Restringe o queryset à organização do usuário autenticado.

    Como ``get_object`` usa ``get_queryset``, um registro de outra organização resulta em 404,
    tanto para leitura quanto para edição e exclusão.
    """

    model = None

    def get_queryset(self):
        return self.model.objects.da_organizacao(self.request.user.organizacao)
