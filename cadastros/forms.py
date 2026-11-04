from django import forms

from .models import Motorista, Transportadora, Veiculo, VinculoMotoristaTransportadora
from .validators import normalizar_placa, somente_digitos


class FormularioDaOrganizacao(forms.ModelForm):
    """Base dos formulários de cadastro: associa a organização do usuário ao registro."""

    def __init__(self, *args, organizacao, **kwargs):
        super().__init__(*args, **kwargs)
        self.organizacao = organizacao
        self.instance.organizacao = organizacao
        # Campos de relacionamento só listam registros da própria organização.
        for campo in self.fields.values():
            queryset = getattr(campo, "queryset", None)
            if queryset is not None and hasattr(queryset, "da_organizacao"):
                campo.queryset = queryset.da_organizacao(organizacao)

    def _validar_unico(self, campo, valor, mensagem):
        existentes = self._meta.model.objects.da_organizacao(self.organizacao).filter(**{campo: valor})
        if self.instance.pk:
            existentes = existentes.exclude(pk=self.instance.pk)
        if existentes.exists():
            raise forms.ValidationError(mensagem)


class TransportadoraForm(FormularioDaOrganizacao):
    cnpj = forms.CharField(label="CNPJ", max_length=18, required=False)

    class Meta:
        model = Transportadora
        fields = ["nome", "cnpj", "ativa"]

    def clean_nome(self):
        nome = self.cleaned_data["nome"].strip()
        self._validar_unico("nome", nome, "Já existe uma transportadora com este nome.")
        return nome

    def clean_cnpj(self):
        return somente_digitos(self.cleaned_data["cnpj"])


class MotoristaForm(FormularioDaOrganizacao):
    cpf = forms.CharField(label="CPF", max_length=14)
    numero_cnh = forms.CharField(label="Número da CNH", max_length=11)
    validade_cnh = forms.DateField(
        label="Validade da CNH", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )

    class Meta:
        model = Motorista
        fields = ["nome", "cpf", "numero_cnh", "categoria_cnh", "validade_cnh", "telefone", "ativo"]

    def clean_cpf(self):
        cpf = somente_digitos(self.cleaned_data["cpf"])
        self._validar_unico("cpf", cpf, "Já existe um motorista com este CPF.")
        return cpf


class VeiculoForm(FormularioDaOrganizacao):
    placa = forms.CharField(label="Placa", max_length=8)

    class Meta:
        model = Veiculo
        fields = ["placa", "transportadora", "ativo"]

    def clean_placa(self):
        placa = normalizar_placa(self.cleaned_data["placa"])
        self._validar_unico("placa", placa, "Já existe um veículo com esta placa.")
        return placa


class VinculoForm(FormularioDaOrganizacao):
    inicio = forms.DateField(
        label="Início da vigência", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )
    fim = forms.DateField(
        label="Fim da vigência (vazio = indeterminado)",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )

    class Meta:
        model = VinculoMotoristaTransportadora
        fields = ["motorista", "transportadora", "inicio", "fim"]

    def clean(self):
        dados = super().clean()
        if dados.get("inicio") and dados.get("fim") and dados["fim"] < dados["inicio"]:
            self.add_error("fim", "O fim da vigência não pode ser anterior ao início.")
        return dados
