"""Solicitação de liberação: fluxo em duas etapas (revisar → enviar) e validações."""

from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from accounts.models import Papel
from liberacoes import services
from liberacoes.models import SolicitacaoLiberacao

from . import factories as f

URL = "solicitacao_nova"


def test_formulario_inicial_e_exibido(logar, solicitante_a, cenario_a):
    resposta = logar(solicitante_a).get(reverse(URL))
    assert resposta.status_code == 200
    assert "Revisar dados" in resposta.content.decode()


def test_primeira_etapa_mostra_revisao_sem_gravar(logar, solicitante_a, cenario_a):
    resposta = logar(solicitante_a).post(reverse(URL), f.post_solicitacao(cenario_a))
    assert resposta.status_code == 200
    assert "Confirmar e enviar" in resposta.content.decode()
    assert SolicitacaoLiberacao.objects.count() == 0


def test_envio_cria_solicitacao_vinculada_a_organizacao_e_ao_solicitante(
    logar, solicitante_a, org_a, cenario_a
):
    dados = f.post_solicitacao(cenario_a)
    resposta = logar(solicitante_a).post(reverse(URL), {**dados, "etapa": "enviar"})
    assert resposta.status_code == 302
    s = SolicitacaoLiberacao.objects.get()
    assert s.organizacao == org_a and s.solicitante == solicitante_a
    assert (s.motorista, s.veiculo, s.transportadora) == (
        cenario_a["motorista"],
        cenario_a["veiculo"],
        cenario_a["transportadora"],
    )
    assert s.finalidade == "Entrega de mercadorias"
    assert resposta.url == reverse("solicitacao_detalhe", args=[s.pk])


def test_envio_mostra_resultado_da_avaliacao_na_tela(logar, solicitante_a, cenario_a):
    client = logar(solicitante_a)
    resposta = client.post(reverse(URL), {**f.post_solicitacao(cenario_a), "etapa": "enviar"}, follow=True)
    html = resposta.content.decode()
    assert "aprovada automaticamente" in html
    for codigo in ("R01", "R02", "R03", "R04", "R05"):
        assert codigo in html


@pytest.mark.parametrize(
    "alteracao",
    [
        {"finalidade": "  "},
        {"finalidade": "ab"},
        {"janela_fim": "2000-01-01T10:00"},
        {"janela_inicio": "2999-01-01T10:00", "janela_fim": "2999-01-01T09:00"},
        {"janela_inicio": "isso-nao-e-data"},
        {"motorista": 999999},
        {"veiculo": 999999},
        {"transportadora": 999999},
    ],
)
def test_dados_invalidos_sao_bloqueados(logar, solicitante_a, cenario_a, alteracao):
    dados = {**f.post_solicitacao(cenario_a), **alteracao, "etapa": "enviar"}
    resposta = logar(solicitante_a).post(reverse(URL), dados)
    assert resposta.status_code == 200
    assert SolicitacaoLiberacao.objects.count() == 0


def test_veiculo_de_outra_transportadora_e_bloqueado(logar, solicitante_a, org_a, cenario_a):
    outro = f.criar_cenario(org_a)
    dados = f.post_solicitacao(cenario_a, veiculo=outro["veiculo"])
    resposta = logar(solicitante_a).post(reverse(URL), {**dados, "etapa": "enviar"})
    assert resposta.status_code == 200
    assert "não pertence à transportadora" in resposta.content.decode()
    assert SolicitacaoLiberacao.objects.count() == 0


def test_somente_solicitante_cria(logar, equipe_a, cenario_a):
    for papel in (Papel.ANALISTA, Papel.GESTOR, Papel.ADMINISTRADOR):
        resposta = logar(equipe_a[papel]).post(
            reverse(URL), {**f.post_solicitacao(cenario_a), "etapa": "enviar"}
        )
        assert resposta.status_code == 403
    assert SolicitacaoLiberacao.objects.count() == 0


def test_servico_exige_papel_solicitante(analista_a, cenario_a):
    with pytest.raises(PermissionDenied):
        services.solicitar_liberacao(usuario=analista_a, **f.dados_solicitacao(cenario_a))


def test_servico_rejeita_janela_invalida(solicitante_a, cenario_a):
    inicio = timezone.now() + timedelta(hours=2)
    for kwargs in (
        {"janela_inicio": inicio, "janela_fim": inicio - timedelta(hours=1)},
        {"janela_inicio": inicio, "janela_fim": inicio},
        {"janela_inicio": inicio - timedelta(days=3), "janela_fim": inicio - timedelta(days=2)},
    ):
        with pytest.raises(ValidationError):
            services.solicitar_liberacao(usuario=solicitante_a, **f.dados_solicitacao(cenario_a, **kwargs))
    assert SolicitacaoLiberacao.objects.count() == 0


def test_servico_rejeita_finalidade_vazia_e_veiculo_de_outra_transportadora(solicitante_a, org_a, cenario_a):
    with pytest.raises(ValidationError):
        services.solicitar_liberacao(usuario=solicitante_a, **f.dados_solicitacao(cenario_a, finalidade=" "))
    outro = f.criar_cenario(org_a)
    with pytest.raises(ValidationError):
        services.solicitar_liberacao(
            usuario=solicitante_a, **f.dados_solicitacao(cenario_a, veiculo=outro["veiculo"])
        )
    assert SolicitacaoLiberacao.objects.count() == 0


def test_finalidade_e_escapada_na_tela_contra_xss(logar, solicitante_a, cenario_a):
    dados = {**f.post_solicitacao(cenario_a, finalidade="<script>alert(1)</script>"), "etapa": "enviar"}
    resposta = logar(solicitante_a).post(reverse(URL), dados, follow=True)
    html = resposta.content.decode()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_sql_injection_na_finalidade_e_tratada_como_texto(solicitante_a, cenario_a):
    texto = "x'); DROP TABLE liberacoes_solicitacaoliberacao;--"
    s = services.solicitar_liberacao(
        usuario=solicitante_a, **f.dados_solicitacao(cenario_a, finalidade=texto)
    )
    s.refresh_from_db()
    assert s.finalidade == texto
    assert SolicitacaoLiberacao.objects.count() == 1


def test_lista_e_filtro_por_estado(logar, solicitante_a, aprovada_a):
    client = logar(solicitante_a)
    ok = client.get(reverse("solicitacao_lista"), {"estado": "aprovada"}).context["solicitacoes"]
    vazio = client.get(reverse("solicitacao_lista"), {"estado": "reprovada"}).context["solicitacoes"]
    assert list(ok) == [aprovada_a] and list(vazio) == []
