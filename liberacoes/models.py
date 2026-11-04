"""Modelos do processo de liberação (SolicitacaoLiberacao, Liberacao, Regra, AvaliacaoRegra,
HistoricoEvento)."""

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from accounts.models import ModeloDaOrganizacao, OrganizacaoQuerySet
from cadastros.models import Motorista, Transportadora, Veiculo

from .estados import EstadoLiberacao, EstadoSolicitacao  # noqa: F401 (reexportados)


class ResultadoAutomatico(models.TextChoices):
    APROVACAO = "aprovacao_automatica", "Aprovação automática"
    REPROVACAO = "reprovacao_automatica", "Reprovação automática"
    PENDENCIA = "pendencia_analise", "Pendência de análise manual"


class SolicitacaoLiberacao(ModeloDaOrganizacao):
    solicitante = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="solicitacoes"
    )
    motorista = models.ForeignKey(Motorista, on_delete=models.PROTECT, related_name="solicitacoes")
    veiculo = models.ForeignKey(Veiculo, on_delete=models.PROTECT, related_name="solicitacoes")
    transportadora = models.ForeignKey(Transportadora, on_delete=models.PROTECT, related_name="solicitacoes")
    finalidade = models.CharField(max_length=255)
    janela_inicio = models.DateTimeField("início da janela de acesso")
    janela_fim = models.DateTimeField("fim da janela de acesso")
    estado = models.CharField(
        max_length=20, choices=EstadoSolicitacao.choices, default=EstadoSolicitacao.RASCUNHO
    )
    resultado_automatico = models.CharField(max_length=25, choices=ResultadoAutomatico.choices, blank=True)
    decidida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="decisoes",
    )
    decidida_em = models.DateTimeField(null=True, blank=True)
    justificativa_decisao = models.TextField(blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criada_em"]
        verbose_name = "solicitação de liberação"
        verbose_name_plural = "solicitações de liberação"
        constraints = [
            models.CheckConstraint(
                condition=Q(janela_fim__gt=models.F("janela_inicio")), name="solicitacao_janela_valida"
            )
        ]

    def __str__(self):
        return f"Solicitação #{self.pk} — {self.motorista}"


class LiberacaoQuerySet(OrganizacaoQuerySet):
    def vigentes(self):
        return self.filter(estado=EstadoLiberacao.VIGENTE)


class Liberacao(ModeloDaOrganizacao):
    """Resultado de uma solicitação aprovada, com validade definida pela janela de acesso."""

    solicitacao = models.OneToOneField(
        SolicitacaoLiberacao, on_delete=models.PROTECT, related_name="liberacao"
    )
    estado = models.CharField(max_length=20, choices=EstadoLiberacao.choices, default=EstadoLiberacao.VIGENTE)
    valida_de = models.DateTimeField()
    valida_ate = models.DateTimeField()
    criada_em = models.DateTimeField(auto_now_add=True)
    revogada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="revogacoes",
    )
    revogada_em = models.DateTimeField(null=True, blank=True)
    justificativa_revogacao = models.TextField(blank=True)

    objects = LiberacaoQuerySet.as_manager()

    class Meta:
        ordering = ["-criada_em"]
        verbose_name = "liberação"
        verbose_name_plural = "liberações"

    def __str__(self):
        return f"Liberação #{self.pk} ({self.get_estado_display()})"

    @property
    def vencida(self):
        return self.valida_ate <= timezone.now()


class AcaoRegra(models.TextChoices):
    REPROVAR = "reprovar", "Reprovar automaticamente"
    ANALISE_MANUAL = "analise_manual", "Exigir análise manual"


class Regra(ModeloDaOrganizacao):
    """Regra de negócio da organização.

    Nesta primeira entrega o conjunto de regras é fixo (criado a partir de ``regras.REGRAS_INICIAIS``)
    e não é configurável pela interface; a configuração pelo Administrador é o incremento 3.
    """

    codigo = models.CharField(max_length=40)
    nome = models.CharField(max_length=120)
    descricao = models.TextField()
    acao_se_nao_atendida = models.CharField(max_length=20, choices=AcaoRegra.choices)
    ativa = models.BooleanField(default=True)
    demonstrativa = models.BooleanField(default=False)

    class Meta:
        ordering = ["codigo"]
        constraints = [
            models.UniqueConstraint(fields=["organizacao", "codigo"], name="regra_codigo_unico_por_org")
        ]

    def __str__(self):
        return f"{self.codigo} — {self.nome}"


class AvaliacaoRegra(ModeloDaOrganizacao):
    """Resultado da aplicação de uma regra a uma solicitação (explicabilidade)."""

    solicitacao = models.ForeignKey(SolicitacaoLiberacao, on_delete=models.PROTECT, related_name="avaliacoes")
    regra = models.ForeignKey(Regra, on_delete=models.PROTECT, related_name="avaliacoes")
    atendida = models.BooleanField()
    acao_aplicada = models.CharField(max_length=20, choices=AcaoRegra.choices)
    justificativa = models.TextField()
    avaliada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["regra__codigo"]
        verbose_name = "avaliação de regra"
        verbose_name_plural = "avaliações de regra"


class ImutavelQuerySet(OrganizacaoQuerySet):
    def update(self, **kwargs):
        raise PermissionError("O histórico de eventos é imutável.")

    def delete(self):
        raise PermissionError("O histórico de eventos é imutável.")

    def bulk_update(self, *args, **kwargs):
        raise PermissionError("O histórico de eventos é imutável.")


class TipoEvento(models.TextChoices):
    SOLICITACAO_CRIADA = "solicitacao_criada", "Solicitação criada"
    ENVIADA_PARA_AVALIACAO = "enviada_para_avaliacao", "Enviada para avaliação"
    REGRA_AVALIADA = "regra_avaliada", "Regra avaliada"
    ENCAMINHADA_ANALISE = "encaminhada_analise", "Encaminhada para análise manual"
    APROVADA_AUTOMATICAMENTE = "aprovada_automaticamente", "Aprovada automaticamente"
    REPROVADA_AUTOMATICAMENTE = "reprovada_automaticamente", "Reprovada automaticamente"
    APROVADA_MANUALMENTE = "aprovada_manualmente", "Aprovada manualmente"
    REPROVADA_MANUALMENTE = "reprovada_manualmente", "Reprovada manualmente"
    LIBERACAO_CRIADA = "liberacao_criada", "Liberação criada"
    LIBERACAO_REVOGADA = "liberacao_revogada", "Liberação revogada"
    LIBERACAO_EXPIRADA = "liberacao_expirada", "Liberação expirada"


class HistoricoEvento(ModeloDaOrganizacao):
    """Trilha de auditoria. Imutável: sem edição nem exclusão (RNF03).

    Além da proteção na aplicação (abaixo), uma migração cria gatilhos no PostgreSQL que
    rejeitam UPDATE e DELETE nesta tabela.
    """

    solicitacao = models.ForeignKey(SolicitacaoLiberacao, on_delete=models.PROTECT, related_name="eventos")
    liberacao = models.ForeignKey(
        Liberacao, null=True, blank=True, on_delete=models.PROTECT, related_name="eventos"
    )
    tipo = models.CharField(max_length=30, choices=TipoEvento.choices)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="eventos",
        help_text="Vazio quando o evento foi gerado automaticamente pelo sistema.",
    )
    descricao = models.TextField()
    justificativa = models.TextField(blank=True)
    dados = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(default=timezone.now, db_index=True)

    objects = ImutavelQuerySet.as_manager()

    class Meta:
        ordering = ["criado_em", "pk"]
        verbose_name = "evento do histórico"
        verbose_name_plural = "histórico de eventos"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionError("O histórico de eventos é imutável.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("O histórico de eventos é imutável.")

    @property
    def responsavel(self):
        return self.usuario or "Sistema"
