"""Gestão de organizações (Superadministrador) e de usuários (Administrador)."""

import pytest
from django.db import DatabaseError
from django.urls import reverse

from accounts.models import Organizacao, Papel, Usuario

from . import factories as f


def test_superadmin_cria_organizacao_com_primeiro_administrador(logar, db):
    client = logar(f.criar_superadmin())
    resposta = client.post(
        reverse("organizacao_nova"),
        {
            "nome": "Empresa Fictícia",
            "admin_username": "admin_ficticio",
            "admin_nome": "Admin Fictício",
            "admin_senha": "Senh@-bem-forte-2026",
        },
    )
    assert resposta.status_code == 302
    org = Organizacao.objects.get(nome="Empresa Fictícia")
    admin = Usuario.objects.get(username="admin_ficticio")
    assert admin.organizacao == org and admin.papel == Papel.ADMINISTRADOR


def test_senha_fraca_e_rejeitada_na_criacao_da_organizacao(logar, db):
    client = logar(f.criar_superadmin())
    resposta = client.post(
        reverse("organizacao_nova"),
        {"nome": "X", "admin_username": "adm", "admin_nome": "Adm", "admin_senha": "123"},
    )
    assert resposta.status_code == 200
    assert not Organizacao.objects.filter(nome="X").exists()


def test_superadmin_edita_e_inativa_organizacao(logar, org_a):
    client = logar(f.criar_superadmin())
    client.post(reverse("organizacao_editar", args=[org_a.pk]), {"nome": "Novo Nome"})
    org_a.refresh_from_db()
    assert org_a.nome == "Novo Nome" and org_a.ativa is False  # checkbox ausente = inativa


def test_administrador_cria_usuario_na_propria_organizacao(logar, admin_a, org_a):
    client = logar(admin_a)
    resposta = client.post(
        reverse("usuario_novo"),
        {
            "username": "novo_user",
            "first_name": "Novo",
            "last_name": "User",
            "email": "",
            "papel": Papel.ANALISTA,
            "senha": "Senh@-bem-forte-2026",
        },
    )
    assert resposta.status_code == 302
    novo = Usuario.objects.get(username="novo_user")
    assert novo.organizacao == org_a and novo.papel == Papel.ANALISTA
    assert novo.check_password("Senh@-bem-forte-2026")


def test_administrador_nao_cria_superadministrador(logar, admin_a):
    client = logar(admin_a)
    resposta = client.post(
        reverse("usuario_novo"),
        {"username": "hack", "papel": Papel.SUPERADMINISTRADOR, "senha": "Senh@-bem-forte-2026"},
    )
    assert resposta.status_code == 200
    assert not Usuario.objects.filter(username="hack").exists()


def test_administrador_edita_usuario_da_organizacao(logar, admin_a, solicitante_a):
    client = logar(admin_a)
    client.post(
        reverse("usuario_editar", args=[solicitante_a.pk]),
        {"first_name": "Maria", "last_name": "Teste", "email": "", "papel": Papel.GESTOR, "is_active": "on"},
    )
    solicitante_a.refresh_from_db()
    assert solicitante_a.papel == Papel.GESTOR and solicitante_a.first_name == "Maria"


def test_administrador_nao_desativa_a_si_mesmo(logar, admin_a):
    client = logar(admin_a)
    client.post(
        reverse("usuario_editar", args=[admin_a.pk]),
        {"first_name": "A", "papel": Papel.ADMINISTRADOR},  # is_active ausente
    )
    admin_a.refresh_from_db()
    assert admin_a.is_active


def test_banco_nao_deixa_organizacao_sem_admin_ativo(admin_a):
    with pytest.raises(DatabaseError, match="pelo menos um administrador ativo"):
        Usuario.objects.filter(pk=admin_a.pk).update(is_active=False)


def test_home_exibe_cartoes_conforme_o_papel(logar, equipe_a):
    for papel, usuario in equipe_a.items():
        resposta = logar(usuario).get(reverse("home"))
        assert resposta.status_code == 200
        assert len(resposta.context["cartoes"]) >= 1, papel
