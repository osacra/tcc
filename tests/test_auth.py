"""Autenticação e autorização por papéis."""

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.urls import reverse

from accounts.models import Papel

from . import factories as f

Usuario = get_user_model()


def test_login_com_credenciais_validas(client, solicitante_a):
    resposta = client.post(
        reverse("login"), {"username": solicitante_a.username, "password": "senha-forte-123"}
    )
    assert resposta.status_code == 302
    assert resposta.url == reverse("home")
    assert "_auth_user_id" in client.session


def test_login_com_senha_errada(client, solicitante_a):
    resposta = client.post(reverse("login"), {"username": solicitante_a.username, "password": "errada"})
    assert resposta.status_code == 200
    assert "_auth_user_id" not in client.session


def test_login_bloqueado_para_organizacao_inativa(client, org_a, solicitante_a):
    org_a.ativa = False
    org_a.save()
    resposta = client.post(
        reverse("login"), {"username": solicitante_a.username, "password": "senha-forte-123"}
    )
    assert resposta.status_code == 200
    assert "_auth_user_id" not in client.session
    assert "inativa" in resposta.content.decode()


def test_logout_encerra_a_sessao(logar, solicitante_a):
    client = logar(solicitante_a)
    resposta = client.post(reverse("logout"))
    assert resposta.status_code == 302
    assert "_auth_user_id" not in client.session


def test_logout_exige_post(logar, solicitante_a):
    client = logar(solicitante_a)
    assert client.get(reverse("logout")).status_code == 405


@pytest.mark.hash_real
def test_senha_armazenada_com_hash_seguro(org_a):
    solicitante_a = f.criar_usuario(org_a, Papel.SOLICITANTE)
    assert solicitante_a.password.startswith("pbkdf2_sha256$")
    assert "senha-forte-123" not in solicitante_a.password


@pytest.mark.parametrize(
    "rota",
    [
        "home",
        "solicitacao_lista",
        "solicitacao_nova",
        "analise_lista",
        "liberacao_lista",
        "motorista_lista",
        "usuario_lista",
        "organizacao_lista",
    ],
)
def test_anonimo_e_redirecionado_ao_login(client, rota, db):
    resposta = client.get(reverse(rota))
    assert resposta.status_code == 302
    assert resposta.url.startswith(reverse("login"))


# rota -> papéis autorizados
MATRIZ = {
    "solicitacao_lista": {Papel.SOLICITANTE, Papel.ANALISTA, Papel.GESTOR},
    "solicitacao_nova": {Papel.SOLICITANTE},
    "analise_lista": {Papel.ANALISTA},
    "liberacao_lista": {Papel.ANALISTA, Papel.GESTOR},
    "motorista_lista": {Papel.ADMINISTRADOR},
    "transportadora_lista": {Papel.ADMINISTRADOR},
    "veiculo_lista": {Papel.ADMINISTRADOR},
    "vinculo_lista": {Papel.ADMINISTRADOR},
    "usuario_lista": {Papel.ADMINISTRADOR},
}


@pytest.mark.parametrize("rota", list(MATRIZ))
@pytest.mark.parametrize("papel", [Papel.SOLICITANTE, Papel.ANALISTA, Papel.GESTOR, Papel.ADMINISTRADOR])
def test_acesso_conforme_o_papel(logar, equipe_a, rota, papel):
    client = logar(equipe_a[papel])
    resposta = client.get(reverse(rota))
    esperado = 200 if papel in MATRIZ[rota] else 403
    assert resposta.status_code == esperado


def test_organizacoes_somente_para_superadministrador(logar, equipe_a, db):
    for usuario in equipe_a.values():
        assert logar(usuario).get(reverse("organizacao_lista")).status_code == 403
    super_ = f.criar_superadmin()
    assert logar(super_).get(reverse("organizacao_lista")).status_code == 200


def test_superadministrador_nao_acessa_dados_de_negocio(logar, db):
    super_ = f.criar_superadmin()
    client = logar(super_)
    assert client.get(reverse("motorista_lista")).status_code == 403
    assert client.get(reverse("solicitacao_lista")).status_code == 403


def test_usuario_inativo_nao_autentica(client, solicitante_a):
    solicitante_a.is_active = False
    solicitante_a.save()
    client.post(reverse("login"), {"username": solicitante_a.username, "password": "senha-forte-123"})
    assert "_auth_user_id" not in client.session


def test_organizacao_inativa_bloqueia_usuario_ja_logado(logar, org_a, solicitante_a):
    client = logar(solicitante_a)
    org_a.ativa = False
    org_a.save()
    assert client.get(reverse("solicitacao_lista")).status_code == 403


def test_create_superuser_define_papel_superadministrador(db):
    s = Usuario.objects.create_superuser("root", "r@example.com", "senha-forte-123")
    assert s.papel == Papel.SUPERADMINISTRADOR and s.organizacao is None and s.is_superuser


def test_restricao_de_banco_papel_organizacao(org_a, db):
    with pytest.raises(IntegrityError), transaction.atomic():
        Usuario.objects.create_user(
            "x", password="senha-forte-123", papel=Papel.SOLICITANTE, organizacao=None
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        Usuario.objects.create_user(
            "y", password="senha-forte-123", papel=Papel.SUPERADMINISTRADOR, organizacao=org_a
        )


def test_csrf_e_exigido_nos_posts(db, solicitante_a):
    from django.test import Client

    client = Client(enforce_csrf_checks=True)
    client.force_login(solicitante_a)
    assert client.post(reverse("logout")).status_code == 403
