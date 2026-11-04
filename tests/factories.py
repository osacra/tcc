"""Funções auxiliares para montar cenários de teste (somente dados fictícios)."""

import itertools
from datetime import timedelta

from django.utils import timezone

from accounts.models import Organizacao, Papel, Usuario
from cadastros.models import Motorista, Transportadora, Veiculo, VinculoMotoristaTransportadora
from cadastros.validators import gerar_cnpj_ficticio, gerar_cpf_ficticio

_contador = itertools.count(1)


def proximo():
    return next(_contador)


def criar_organizacao(nome=None):
    return Organizacao.objects.create(nome=nome or f"Organização {proximo()}")


def criar_usuario(organizacao, papel, username=None, senha="senha-forte-123"):
    username = username or f"{papel}_{proximo()}"
    return Usuario.objects.create_user(
        username=username, password=senha, organizacao=organizacao, papel=papel
    )


def criar_superadmin(username="superadmin"):
    return Usuario.objects.create_superuser(
        username=username, password="senha-forte-123", email="s@example.com"
    )


def criar_equipe(organizacao):
    """Um usuário de cada papel da organização."""
    return {
        papel: criar_usuario(organizacao, papel)
        for papel in (Papel.SOLICITANTE, Papel.ANALISTA, Papel.GESTOR, Papel.ADMINISTRADOR)
    }


def criar_cenario(organizacao, *, vinculo=True, validade_cnh=None, motorista_ativo=True, veiculo_ativo=True):
    """Transportadora, motorista, veículo e (opcionalmente) vínculo vigente."""
    n = proximo()
    hoje = timezone.localdate()
    transportadora = Transportadora.objects.create(
        organizacao=organizacao, nome=f"Transportadora {n}", cnpj=gerar_cnpj_ficticio(n)
    )
    motorista = Motorista.objects.create(
        organizacao=organizacao,
        nome=f"Motorista {n}",
        cpf=gerar_cpf_ficticio(100000 + n),
        numero_cnh=str(10000000000 + n),
        categoria_cnh="E",
        validade_cnh=validade_cnh or hoje + timedelta(days=365),
        ativo=motorista_ativo,
    )
    veiculo = Veiculo.objects.create(
        organizacao=organizacao,
        placa=f"ABC{n % 10}D{n % 90 + 10}",
        transportadora=transportadora,
        ativo=veiculo_ativo,
    )
    if vinculo:
        VinculoMotoristaTransportadora.objects.create(
            organizacao=organizacao,
            motorista=motorista,
            transportadora=transportadora,
            inicio=hoje - timedelta(days=30),
        )
    return {"transportadora": transportadora, "motorista": motorista, "veiculo": veiculo}


def janela(horas_inicio=1, duracao_horas=4):
    inicio = timezone.now() + timedelta(hours=horas_inicio)
    return inicio, inicio + timedelta(hours=duracao_horas)


def dados_solicitacao(cenario, **extra):
    inicio, fim = janela()
    dados = {
        "motorista": cenario["motorista"],
        "veiculo": cenario["veiculo"],
        "transportadora": cenario["transportadora"],
        "finalidade": "Entrega de mercadorias",
        "janela_inicio": inicio,
        "janela_fim": fim,
    }
    dados.update(extra)
    return dados


def formatar_data_hora(instante):
    return timezone.localtime(instante).strftime("%Y-%m-%dT%H:%M")


def post_solicitacao(cenario, **extra):
    """Dados de POST do formulário de solicitação."""
    d = dados_solicitacao(cenario, **extra)
    return {
        "motorista": d["motorista"].pk,
        "veiculo": d["veiculo"].pk,
        "transportadora": d["transportadora"].pk,
        "finalidade": d["finalidade"],
        "janela_inicio": formatar_data_hora(d["janela_inicio"]),
        "janela_fim": formatar_data_hora(d["janela_fim"]),
    }
