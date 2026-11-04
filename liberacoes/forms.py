from django import forms
from django.utils import timezone

from cadastros.models import Motorista, Transportadora, Veiculo

FORMATOS_DATA_HORA = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M"]


def _campo_data_hora(rotulo):
    return forms.DateTimeField(
        label=rotulo,
        input_formats=FORMATOS_DATA_HORA,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
    )


class SolicitacaoForm(forms.Form):
    """Formulário do Solicitante. Só oferece (e só aceita) registros da própria organização."""

    motorista = forms.ModelChoiceField(queryset=Motorista.objects.none(), label="Motorista")
    veiculo = forms.ModelChoiceField(queryset=Veiculo.objects.none(), label="Veículo")
    transportadora = forms.ModelChoiceField(queryset=Transportadora.objects.none(), label="Transportadora")
    finalidade = forms.CharField(label="Finalidade da liberação", max_length=255)
    janela_inicio = _campo_data_hora("Início da janela de acesso")
    janela_fim = _campo_data_hora("Fim da janela de acesso")

    def __init__(self, *args, organizacao, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["motorista"].queryset = Motorista.objects.da_organizacao(organizacao)
        self.fields["veiculo"].queryset = Veiculo.objects.da_organizacao(organizacao).select_related(
            "transportadora"
        )
        self.fields["transportadora"].queryset = Transportadora.objects.da_organizacao(organizacao)

    def clean_finalidade(self):
        finalidade = self.cleaned_data["finalidade"].strip()
        if len(finalidade) < 3:
            raise forms.ValidationError("Descreva a finalidade (mínimo de 3 caracteres).")
        return finalidade

    def clean(self):
        dados = super().clean()
        inicio, fim = dados.get("janela_inicio"), dados.get("janela_fim")
        if inicio and fim:
            if fim <= inicio:
                self.add_error("janela_fim", "O fim da janela deve ser posterior ao início.")
            elif fim <= timezone.now():
                self.add_error("janela_fim", "A janela de acesso já está encerrada.")
        veiculo, transportadora = dados.get("veiculo"), dados.get("transportadora")
        if veiculo and transportadora and veiculo.transportadora_id != transportadora.pk:
            self.add_error("veiculo", "Este veículo não pertence à transportadora selecionada.")
        return dados


class DecisaoForm(forms.Form):
    ACOES = [("aprovar", "Aprovar"), ("reprovar", "Reprovar")]
    acao = forms.ChoiceField(choices=ACOES, widget=forms.RadioSelect, label="Decisão")
    justificativa = forms.CharField(
        label="Justificativa (obrigatória)", widget=forms.Textarea(attrs={"rows": 3}), strip=True
    )


class RevogacaoForm(forms.Form):
    justificativa = forms.CharField(
        label="Justificativa da revogação (obrigatória)", widget=forms.Textarea(attrs={"rows": 3}), strip=True
    )
