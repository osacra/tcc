"""Fluxo ponta a ponta pela interface web (passos 1 a 13 do cenário de demonstração)."""

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from accounts.models import Organizacao, Papel, Usuario
from cadastros.models import Motorista, Transportadora, Veiculo
from cadastros.validators import gerar_cnpj_ficticio, gerar_cpf_ficticio
from liberacoes.models import EstadoLiberacao, EstadoSolicitacao, Liberacao, SolicitacaoLiberacao, TipoEvento
from liberacoes.regras import garantir_regras_iniciais

from . import factories as f

SENHA = "Senh@-bem-forte-2026"


def entrar(client, username):
    client.logout()
    assert client.post(reverse("login"), {"username": username, "password": SENHA}).status_code == 302


def cadastrar_base(client, org, validade_cnh, nome="Motorista Demo", cpf_base=4242):
    """Passos 3 a 5: transportadora, motorista, veículo e vínculo (pelo Administrador)."""
    n = cpf_base
    assert (
        client.post(
            reverse("transportadora_novo"),
            {"nome": f"Transp {n}", "cnpj": gerar_cnpj_ficticio(n), "ativa": "on"},
        ).status_code
        == 302
    )
    transp = Transportadora.objects.get(nome=f"Transp {n}")
    assert (
        client.post(
            reverse("motorista_novo"),
            {
                "nome": nome,
                "cpf": gerar_cpf_ficticio(n),
                "numero_cnh": "12345678901",
                "categoria_cnh": "E",
                "validade_cnh": validade_cnh.isoformat(),
                "telefone": "",
                "ativo": "on",
            },
        ).status_code
        == 302
    )
    motorista = Motorista.objects.get(nome=nome)
    assert (
        client.post(
            reverse("veiculo_novo"),
            {"placa": f"DEM{n % 10}A{n % 90 + 10}", "transportadora": transp.pk, "ativo": "on"},
        ).status_code
        == 302
    )
    veiculo = Veiculo.objects.get(transportadora=transp)
    assert (
        client.post(
            reverse("vinculo_novo"),
            {
                "motorista": motorista.pk,
                "transportadora": transp.pk,
                "inicio": (timezone.localdate() - timedelta(days=5)).isoformat(),
            },
        ).status_code
        == 302
    )
    return transp, motorista, veiculo


def solicitar(client, transp, motorista, veiculo, finalidade="Carga de demonstração"):
    inicio = timezone.now() + timedelta(hours=1)
    dados = {
        "motorista": motorista.pk,
        "veiculo": veiculo.pk,
        "transportadora": transp.pk,
        "finalidade": finalidade,
        "janela_inicio": f.formatar_data_hora(inicio),
        "janela_fim": f.formatar_data_hora(inicio + timedelta(hours=6)),
    }
    revisao = client.post(reverse("solicitacao_nova"), dados)  # passo de revisão
    assert "Confirmar e enviar" in revisao.content.decode()
    resposta = client.post(reverse("solicitacao_nova"), {**dados, "etapa": "enviar"})
    assert resposta.status_code == 302
    return SolicitacaoLiberacao.objects.get(finalidade=finalidade)


def test_fluxo_completo_com_pendencia_aprovacao_e_revogacao(client, db):
    # 1. Superadministrador cria a organização (com o primeiro administrador).
    f.criar_superadmin()
    client.force_login(Usuario.objects.get(username="superadmin"))
    assert (
        client.post(
            reverse("organizacao_nova"),
            {
                "nome": "Org Demo",
                "admin_username": "admin_demo",
                "admin_nome": "Admin Demo",
                "admin_senha": SENHA,
            },
        ).status_code
        == 302
    )
    org = Organizacao.objects.get(nome="Org Demo")
    garantir_regras_iniciais(org)

    # 2. Administrador cadastra usuários e atribui papéis.
    entrar(client, "admin_demo")
    for papel in (Papel.SOLICITANTE, Papel.ANALISTA, Papel.GESTOR):
        assert (
            client.post(
                reverse("usuario_novo"),
                {
                    "username": f"{papel}_demo",
                    "first_name": papel.title(),
                    "last_name": "Demo",
                    "email": "",
                    "papel": papel,
                    "senha": SENHA,
                },
            ).status_code
            == 302
        )
    assert Usuario.objects.filter(organizacao=org).count() == 4

    # 3-5. Cadastros (CNH vencida ontem => R05 exigirá análise manual).
    transp, motorista, veiculo = cadastrar_base(client, org, timezone.localdate() - timedelta(days=1))

    # 6-8. Solicitante abre a solicitação; sistema executa as regras e mostra as justificativas.
    entrar(client, f"{Papel.SOLICITANTE}_demo")
    solicitacao = solicitar(client, transp, motorista, veiculo)
    detalhe = client.get(reverse("solicitacao_detalhe", args=[solicitacao.pk])).content.decode()
    assert solicitacao.estado == EstadoSolicitacao.PENDENTE_ANALISE
    assert "Pendência de análise manual" in detalhe and "CNH vence" in detalhe

    # 9-11. Aparece para o Analista, que consulta e aprova com justificativa.
    entrar(client, f"{Papel.ANALISTA}_demo")
    assert solicitacao in list(client.get(reverse("analise_lista")).context["solicitacoes"])
    client.post(
        reverse("solicitacao_decidir", args=[solicitacao.pk]),
        {"acao": "aprovar", "justificativa": "CNH renovada, conferido presencialmente."},
    )
    solicitacao.refresh_from_db()
    liberacao = Liberacao.objects.get(solicitacao=solicitacao)
    assert solicitacao.estado == EstadoSolicitacao.APROVADA and liberacao.estado == EstadoLiberacao.VIGENTE

    # 12. Gestor consulta o histórico.
    entrar(client, f"{Papel.GESTOR}_demo")
    historico = client.get(reverse("solicitacao_detalhe", args=[solicitacao.pk])).content.decode()
    assert "Encaminhada para análise manual" in historico and "Aprovada manualmente" in historico
    assert "CNH renovada, conferido presencialmente." in historico

    # 13. Analista revoga a liberação vigente.
    entrar(client, f"{Papel.ANALISTA}_demo")
    client.post(reverse("liberacao_revogar", args=[liberacao.pk]), {"justificativa": "Documento suspeito."})
    liberacao.refresh_from_db()
    assert liberacao.estado == EstadoLiberacao.REVOGADA
    tipos = list(solicitacao.eventos.values_list("tipo", flat=True))
    assert tipos[-1] == TipoEvento.LIBERACAO_REVOGADA
    assert tipos[0] == TipoEvento.SOLICITACAO_CRIADA


def test_fluxo_de_reprovacao_automatica_pela_interface(client, db):
    org = f.criar_organizacao("Org Reprovação")
    garantir_regras_iniciais(org)
    f.criar_usuario(org, Papel.ADMINISTRADOR, "adm", SENHA)
    f.criar_usuario(org, Papel.SOLICITANTE, "sol", SENHA)
    entrar(client, "adm")
    transp, motorista, veiculo = cadastrar_base(
        client, org, timezone.localdate() + timedelta(days=300), cpf_base=777
    )
    client.post(
        reverse("motorista_editar", args=[motorista.pk]),
        {
            "nome": motorista.nome,
            "cpf": motorista.cpf,
            "numero_cnh": motorista.numero_cnh,
            "categoria_cnh": "E",
            "validade_cnh": motorista.validade_cnh.isoformat(),
            "telefone": "",
        },
    )  # 'ativo' ausente => motorista inativo
    motorista.refresh_from_db()
    assert motorista.ativo is False

    entrar(client, "sol")
    solicitacao = solicitar(client, transp, motorista, veiculo)
    detalhe = client.get(reverse("solicitacao_detalhe", args=[solicitacao.pk])).content.decode()
    assert solicitacao.estado == EstadoSolicitacao.REPROVADA
    assert "Reprovação automática" in detalhe and "está inativo" in detalhe
    assert not Liberacao.objects.filter(solicitacao=solicitacao).exists()
    assert solicitacao in list(client.get(reverse("solicitacao_lista")).context["solicitacoes"])


def test_fluxo_de_aprovacao_automatica_pela_interface(client, db):
    org = f.criar_organizacao("Org Auto")
    garantir_regras_iniciais(org)
    f.criar_usuario(org, Papel.ADMINISTRADOR, "adm", SENHA)
    f.criar_usuario(org, Papel.SOLICITANTE, "sol", SENHA)
    entrar(client, "adm")
    transp, motorista, veiculo = cadastrar_base(
        client, org, timezone.localdate() + timedelta(days=300), cpf_base=888
    )
    entrar(client, "sol")
    solicitacao = solicitar(client, transp, motorista, veiculo)
    assert solicitacao.estado == EstadoSolicitacao.APROVADA
    assert Liberacao.objects.get(solicitacao=solicitacao).estado == EstadoLiberacao.VIGENTE
