"""Organização, usuário (modelo customizado) e base de isolamento por organização."""

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.db.models import Q


class Organizacao(models.Model):
    """Empresa cliente. Delimita o isolamento dos dados (RNF01)."""

    nome = models.CharField(max_length=150, unique=True)
    ativa = models.BooleanField(default=True)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "organização"
        verbose_name_plural = "organizações"

    def __str__(self):
        return self.nome


class Papel(models.TextChoices):
    SOLICITANTE = "solicitante", "Solicitante"
    ANALISTA = "analista", "Analista de Segurança"
    GESTOR = "gestor", "Gestor"
    ADMINISTRADOR = "administrador", "Administrador da organização"
    SUPERADMINISTRADOR = "superadministrador", "Superadministrador da plataforma"


class UsuarioManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        # O superusuário criado por linha de comando é o Superadministrador da plataforma,
        # que não pertence a nenhuma organização.
        extra_fields.setdefault("papel", Papel.SUPERADMINISTRADOR)
        return super().create_superuser(username, email, password, **extra_fields)


class Usuario(AbstractUser):
    """Usuário do sistema, com papel e organização (exceto o Superadministrador)."""

    organizacao = models.ForeignKey(
        Organizacao, null=True, blank=True, on_delete=models.PROTECT, related_name="usuarios"
    )
    papel = models.CharField(max_length=20, choices=Papel.choices, default=Papel.SOLICITANTE)

    objects = UsuarioManager()

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(papel="superadministrador", organizacao__isnull=True)
                    | (~Q(papel="superadministrador") & Q(organizacao__isnull=False))
                ),
                name="usuario_papel_organizacao_consistentes",
            )
        ]

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def eh_superadministrador(self):
        return self.papel == Papel.SUPERADMINISTRADOR

    @property
    def eh_administrador(self):
        return self.papel == Papel.ADMINISTRADOR

    @property
    def eh_solicitante(self):
        return self.papel == Papel.SOLICITANTE

    @property
    def eh_analista(self):
        return self.papel == Papel.ANALISTA

    @property
    def eh_gestor(self):
        return self.papel == Papel.GESTOR


class OrganizacaoQuerySet(models.QuerySet):
    """Consultas sempre restritas a uma organização (isolamento no backend, RNF01)."""

    def da_organizacao(self, organizacao):
        if organizacao is None:
            return self.none()
        return self.filter(organizacao=organizacao)


class ModeloDaOrganizacao(models.Model):
    """Base abstrata das tabelas de negócio: coluna ``organizacao`` + gerenciador filtrado.

    Todo acesso a dados de negócio nas views e serviços deve partir de
    ``Modelo.objects.da_organizacao(usuario.organizacao)``.
    """

    organizacao = models.ForeignKey(Organizacao, on_delete=models.PROTECT, related_name="+")

    objects = OrganizacaoQuerySet.as_manager()

    class Meta:
        abstract = True
