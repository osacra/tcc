"""Garantias de isolamento por organização no modelo e no PostgreSQL."""

from datetime import timedelta

import pytest
from django.db import DatabaseError
from django.utils import timezone

from liberacoes.models import AvaliacaoRegra, HistoricoEvento, Liberacao, Regra, SolicitacaoLiberacao

from . import factories as f


@pytest.mark.django_db
def test_banco_rejeita_veiculo_de_outra_organizacao(org_a):
    org_b = f.criar_organizacao("Outra organização")
    cenario_a = f.criar_cenario(org_a)
    transportadora_b = f.criar_cenario(org_b)["transportadora"]

    with pytest.raises(DatabaseError, match="mesma organização"):
        cenario_a["veiculo"].__class__.objects.create(
            organizacao=org_a,
            placa="ZZZ1A23",
            transportadora=transportadora_b,
        )


@pytest.mark.django_db
def test_banco_rejeita_vinculo_de_outra_organizacao(org_a):
    org_b = f.criar_organizacao("Outra organização")
    cenario_a = f.criar_cenario(org_a)
    cenario_b = f.criar_cenario(org_b)

    with pytest.raises(DatabaseError, match="mesma organização"):
        cenario_a["motorista"].vinculos.create(
            organizacao=org_a,
            motorista=cenario_a["motorista"],
            transportadora=cenario_b["transportadora"],
            inicio=timezone.localdate(),
        )


@pytest.mark.django_db
def test_banco_rejeita_solicitacao_com_solicitante_de_outra_organizacao(org_a):
    org_b = f.criar_organizacao("Outra organização")
    cenario = f.criar_cenario(org_a)
    usuario_b = f.criar_usuario(org_b, "solicitante")
    inicio = timezone.now() + timedelta(hours=1)

    with pytest.raises(DatabaseError, match="mesma organização"):
        SolicitacaoLiberacao.objects.create(
            organizacao=org_a,
            solicitante=usuario_b,
            motorista=cenario["motorista"],
            veiculo=cenario["veiculo"],
            transportadora=cenario["transportadora"],
            finalidade="Carga",
            janela_inicio=inicio,
            janela_fim=inicio + timedelta(hours=2),
        )


@pytest.mark.django_db
def test_banco_rejeita_avaliacao_com_regra_de_outra_organizacao(org_a):
    org_b = f.criar_organizacao("Outra organização")
    cenario = f.criar_cenario(org_a)
    solicitante = f.criar_usuario(org_a, "solicitante")
    inicio = timezone.now() + timedelta(hours=1)
    solicitacao = SolicitacaoLiberacao.objects.create(
        organizacao=org_a,
        solicitante=solicitante,
        motorista=cenario["motorista"],
        veiculo=cenario["veiculo"],
        transportadora=cenario["transportadora"],
        finalidade="Carga",
        janela_inicio=inicio,
        janela_fim=inicio + timedelta(hours=2),
    )
    regra_b = Regra.objects.create(
        organizacao=org_b,
        codigo="RB01",
        nome="Regra B",
        descricao="Regra da organização B",
        acao_se_nao_atendida="reprovar",
    )

    with pytest.raises(DatabaseError, match="mesma organização"):
        AvaliacaoRegra.objects.create(
            organizacao=org_a,
            solicitacao=solicitacao,
            regra=regra_b,
            atendida=True,
            acao_aplicada="reprovar",
            justificativa="Teste",
        )


@pytest.mark.django_db
def test_banco_rejeita_liberacao_de_solicitacao_nao_aprovada(org_a):
    cenario = f.criar_cenario(org_a)
    solicitante = f.criar_usuario(org_a, "solicitante")
    inicio = timezone.now() + timedelta(hours=1)
    solicitacao = SolicitacaoLiberacao.objects.create(
        organizacao=org_a,
        solicitante=solicitante,
        motorista=cenario["motorista"],
        veiculo=cenario["veiculo"],
        transportadora=cenario["transportadora"],
        finalidade="Carga",
        janela_inicio=inicio,
        janela_fim=inicio + timedelta(hours=2),
    )

    with pytest.raises(DatabaseError, match="solicitação aprovada"):
        Liberacao.objects.create(
            organizacao=org_a,
            solicitacao=solicitacao,
            valida_de=inicio,
            valida_ate=inicio + timedelta(hours=1),
        )


@pytest.mark.django_db
def test_banco_rejeita_historico_com_usuario_de_outra_organizacao(org_a):
    org_b = f.criar_organizacao("Outra organização")
    cenario = f.criar_cenario(org_a)
    solicitante = f.criar_usuario(org_a, "solicitante")
    usuario_b = f.criar_usuario(org_b, "analista")
    inicio = timezone.now() + timedelta(hours=1)
    solicitacao = SolicitacaoLiberacao.objects.create(
        organizacao=org_a,
        solicitante=solicitante,
        motorista=cenario["motorista"],
        veiculo=cenario["veiculo"],
        transportadora=cenario["transportadora"],
        finalidade="Carga",
        janela_inicio=inicio,
        janela_fim=inicio + timedelta(hours=2),
    )

    with pytest.raises(DatabaseError, match="mesma organização"):
        HistoricoEvento.objects.create(
            organizacao=org_a,
            solicitacao=solicitacao,
            tipo="solicitacao_criada",
            usuario=usuario_b,
            descricao="Teste",
        )
