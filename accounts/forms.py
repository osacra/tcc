from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm

from .models import Organizacao, Papel, Usuario

PAPEIS_DA_ORGANIZACAO = [p for p in Papel.choices if p[0] != Papel.SUPERADMINISTRADOR]


class LoginForm(AuthenticationForm):
    """Bloqueia o login de usuários cuja organização esteja inativa."""

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if user.organizacao_id and not user.organizacao.ativa:
            raise forms.ValidationError(
                "A organização deste usuário está inativa.", code="organizacao_inativa"
            )


class OrganizacaoForm(forms.ModelForm):
    class Meta:
        model = Organizacao
        fields = ["nome", "ativa"]


class OrganizacaoNovaForm(OrganizacaoForm):
    """Cria a organização e, junto, o primeiro Administrador (fluxo do Superadministrador)."""

    admin_username = forms.CharField(label="Usuário do administrador", max_length=150)
    admin_nome = forms.CharField(label="Nome do administrador", max_length=150)
    admin_senha = forms.CharField(label="Senha do administrador", widget=forms.PasswordInput, strip=False)

    class Meta(OrganizacaoForm.Meta):
        fields = ["nome"]

    def clean_admin_username(self):
        username = self.cleaned_data["admin_username"]
        if Usuario.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Já existe um usuário com este nome.")
        return username

    def clean(self):
        dados = super().clean()
        senha = dados.get("admin_senha")
        if senha:
            usuario_provisorio = Usuario(
                username=dados.get("admin_username", ""), first_name=dados.get("admin_nome", "")
            )
            try:
                password_validation.validate_password(senha, usuario_provisorio)
            except forms.ValidationError as erro:
                self.add_error("admin_senha", erro)
        return dados

    def save(self, commit=True):
        organizacao = super().save(commit=commit)
        if commit:
            Usuario.objects.create_user(
                username=self.cleaned_data["admin_username"],
                password=self.cleaned_data["admin_senha"],
                first_name=self.cleaned_data["admin_nome"],
                organizacao=organizacao,
                papel=Papel.ADMINISTRADOR,
            )
        return organizacao


class UsuarioCriarForm(forms.ModelForm):
    senha = forms.CharField(label="Senha", widget=forms.PasswordInput, strip=False)
    papel = forms.ChoiceField(label="Papel", choices=PAPEIS_DA_ORGANIZACAO)

    class Meta:
        model = Usuario
        fields = ["username", "first_name", "last_name", "email", "papel"]
        labels = {"username": "Usuário", "first_name": "Nome", "last_name": "Sobrenome"}

    def __init__(self, *args, organizacao, **kwargs):
        super().__init__(*args, **kwargs)
        self.organizacao = organizacao
        self.instance.organizacao = organizacao

    def clean_senha(self):
        senha = self.cleaned_data["senha"]
        password_validation.validate_password(senha, self.instance)
        return senha

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.organizacao = self.organizacao
        usuario.set_password(self.cleaned_data["senha"])
        if commit:
            usuario.save()
        return usuario


class UsuarioEditarForm(forms.ModelForm):
    nova_senha = forms.CharField(
        label="Nova senha (opcional)", widget=forms.PasswordInput, strip=False, required=False
    )
    papel = forms.ChoiceField(label="Papel", choices=PAPEIS_DA_ORGANIZACAO)

    class Meta:
        model = Usuario
        fields = ["first_name", "last_name", "email", "papel", "is_active"]
        labels = {"first_name": "Nome", "last_name": "Sobrenome", "is_active": "Ativo"}

    def clean_nova_senha(self):
        senha = self.cleaned_data["nova_senha"]
        if senha:
            password_validation.validate_password(senha, self.instance)
        return senha

    def save(self, commit=True):
        usuario = super().save(commit=False)
        if self.cleaned_data["nova_senha"]:
            usuario.set_password(self.cleaned_data["nova_senha"])
        if commit:
            usuario.save()
        return usuario
