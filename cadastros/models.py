"""Cadastros mestres: Transportadora, Motorista, Veiculo e VinculoMotoristaTransportadora."""

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from accounts.models import ModeloDaOrganizacao, OrganizacaoQuerySet

from .validators import (
    CATEGORIAS_CNH,
    validar_cnh,
    validar_cnpj,
    validar_cpf,
    validar_placa,
)


class Transportadora(ModeloDaOrganizacao):
    nome = models.CharField(max_length=150)
    cnpj = models.CharField("CNPJ", max_length=14, blank=True, validators=[validar_cnpj])
    ativa = models.BooleanField(default=True)

    class Meta:
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(fields=["organizacao", "nome"], name="transportadora_nome_unico_por_org")
        ]

    def __str__(self):
        return self.nome


class Motorista(ModeloDaOrganizacao):
    nome = models.CharField(max_length=150)
    cpf = models.CharField("CPF", max_length=11, validators=[validar_cpf])
    numero_cnh = models.CharField("número da CNH", max_length=11, validators=[validar_cnh])
    categoria_cnh = models.CharField(
        "categoria da CNH", max_length=2, choices=[(c, c) for c in CATEGORIAS_CNH]
    )
    validade_cnh = models.DateField("validade da CNH")
    telefone = models.CharField(max_length=20, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(fields=["organizacao", "cpf"], name="motorista_cpf_unico_por_org")
        ]

    def __str__(self):
        return self.nome

    @property
    def cpf_mascarado(self):
        """CPF mascarado para listagens (minimização de dados, RNF04)."""
        d = self.cpf
        return f"***.{d[3:6]}.{d[6:9]}-**" if len(d) == 11 else "***"

    @property
    def cpf_formatado(self):
        d = self.cpf
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}" if len(d) == 11 else d


class Veiculo(ModeloDaOrganizacao):
    placa = models.CharField(max_length=7, validators=[validar_placa])
    transportadora = models.ForeignKey(Transportadora, on_delete=models.PROTECT, related_name="veiculos")
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["placa"]
        verbose_name = "veículo"
        verbose_name_plural = "veículos"
        constraints = [
            models.UniqueConstraint(fields=["organizacao", "placa"], name="veiculo_placa_unica_por_org")
        ]

    def __str__(self):
        return self.placa

    def clean(self):
        super().clean()
        if self.transportadora_id and self.transportadora.organizacao_id != self.organizacao_id:
            raise ValidationError({"transportadora": "Transportadora de outra organização."})


class VinculoQuerySet(OrganizacaoQuerySet):
    def cobrindo_periodo(self, data_inicio, data_fim):
        """Vínculos vigentes durante todo o período [data_inicio, data_fim]."""
        return self.filter(inicio__lte=data_inicio).filter(Q(fim__isnull=True) | Q(fim__gte=data_fim))


class VinculoMotoristaTransportadora(ModeloDaOrganizacao):
    """Relação, com período de vigência, entre motorista e transportadora."""

    motorista = models.ForeignKey(Motorista, on_delete=models.PROTECT, related_name="vinculos")
    transportadora = models.ForeignKey(Transportadora, on_delete=models.PROTECT, related_name="vinculos")
    inicio = models.DateField("início da vigência")
    fim = models.DateField("fim da vigência", null=True, blank=True)

    objects = VinculoQuerySet.as_manager()

    class Meta:
        ordering = ["-inicio"]
        verbose_name = "vínculo motorista–transportadora"
        verbose_name_plural = "vínculos motorista–transportadora"
        constraints = [
            models.CheckConstraint(
                condition=Q(fim__isnull=True) | Q(fim__gte=F("inicio")),
                name="vinculo_fim_apos_inicio",
            )
        ]

    def clean(self):
        super().clean()
        if self.fim and self.inicio and self.fim < self.inicio:
            raise ValidationError({"fim": "O fim da vigência não pode ser anterior ao início."})
        for campo in ("motorista", "transportadora"):
            objeto = getattr(self, campo, None) if getattr(self, f"{campo}_id") else None
            if objeto is not None and objeto.organizacao_id != self.organizacao_id:
                raise ValidationError({campo: "Registro de outra organização."})

    def __str__(self):
        return f"{self.motorista} → {self.transportadora}"
