"""Isolamento entre organizações, aplicado no backend (RNF01)."""

import pytest
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.urls import reverse

from cadastros.models import Motorista, Transportadora, Veiculo, VinculoMotoristaTransportadora
from liberacoes import services
from liberacoes.models import HistoricoEvento, Liberacao, SolicitacaoLiberacao

from . import factories as f


def test_manager_sem_organizacao_nao_retorna_nada(cenario_a):
    assert Motorista.objects.da_organizacao(None).count() == 0


def test_listagens_mostram_apenas_a_propria_organizacao(logar, admin_a, cenario_a, cenario_b):
    html = logar(admin_a).get(reverse("motorista_lista")).content.decode()
    assert cenario_a["motorista"].nome in html
    assert cenario_b["motorista"].nome not in html


@pytest.mark.parametrize(
    ("modelo", "chave", "slug"),
    [
        (Transportadora, "transportadora", "transportadora"),
        (Motorista, "motorista", "motorista"),
        (Veiculo, "veiculo", "veiculo"),
    ],
)
def test_nao_edita_nem_exclui_cadastro_de_outra_organizacao(logar, admin_a, cenario_b, modelo, chave, slug):
    alvo = cenario_b[chave]
    client = logar(admin_a)
    assert client.get(reverse(f"{slug}_editar", args=[alvo.pk])).status_code == 404
    assert client.post(reverse(f"{slug}_editar", args=[alvo.pk]), {"nome": "invadido"}).status_code == 404
    assert client.post(reverse(f"{slug}_excluir", args=[alvo.pk])).status_code == 404
    assert modelo.objects.filter(pk=alvo.pk).exists()


def test_nao_edita_nem_exclui_vinculo_de_outra_organizacao(logar, admin_a, cenario_b):
    v = VinculoMotoristaTransportadora.objects.get(motorista=cenario_b["motorista"])
    client = logar(admin_a)
    assert client.get(reverse("vinculo_editar", args=[v.pk])).status_code == 404
    assert client.post(reverse("vinculo_excluir", args=[v.pk])).status_code == 404
    assert VinculoMotoristaTransportadora.objects.filter(pk=v.pk).exists()


def test_nao_edita_usuario_de_outra_organizacao(logar, admin_a, equipe_b):
    alvo = equipe_b["solicitante"]
    resposta = logar(admin_a).post(
        reverse("usuario_editar", args=[alvo.pk]), {"papel": "gestor", "is_active": "on"}
    )
    assert resposta.status_code == 404
    alvo.refresh_from_db()
    assert alvo.papel == "solicitante"


def test_lista_de_usuarios_nao_vaza_outra_organizacao(logar, admin_a, equipe_b):
    html = logar(admin_a).get(reverse("usuario_lista")).content.decode()
    assert equipe_b["solicitante"].username not in html


def test_formulario_de_solicitacao_so_oferece_registros_da_propria_organizacao(
    logar, solicitante_a, cenario_a, cenario_b
):
    resposta = logar(solicitante_a).get(reverse("solicitacao_nova"))
    form = resposta.context["form"]
    assert list(form.fields["motorista"].queryset) == [cenario_a["motorista"]]
    assert list(form.fields["veiculo"].queryset) == [cenario_a["veiculo"]]
    assert list(form.fields["transportadora"].queryset) == [cenario_a["transportadora"]]


def test_solicitacao_com_entidades_de_outra_organizacao_e_rejeitada_na_view(
    logar, solicitante_a, cenario_a, cenario_b
):
    dados = f.post_solicitacao(cenario_b)
    resposta = logar(solicitante_a).post(reverse("solicitacao_nova"), {**dados, "etapa": "enviar"})
    assert resposta.status_code == 200
    assert SolicitacaoLiberacao.objects.count() == 0


@pytest.mark.parametrize("campo", ["motorista", "veiculo", "transportadora"])
def test_servico_rejeita_entidade_de_outra_organizacao(solicitante_a, cenario_a, cenario_b, campo):
    dados = f.dados_solicitacao(cenario_a, **{campo: cenario_b[campo]})
    with pytest.raises(ValidationError):
        services.solicitar_liberacao(usuario=solicitante_a, **dados)
    assert SolicitacaoLiberacao.objects.count() == 0


def test_nao_ve_solicitacao_de_outra_organizacao(logar, equipe_b, aprovada_a):
    for papel in ("solicitante", "analista", "gestor"):
        resposta = logar(equipe_b[papel]).get(reverse("solicitacao_detalhe", args=[aprovada_a.pk]))
        assert resposta.status_code == 404


def test_listas_de_solicitacoes_e_liberacoes_nao_vazam(logar, equipe_b, aprovada_a):
    assert list(logar(equipe_b["analista"]).get(reverse("solicitacao_lista")).context["solicitacoes"]) == []
    assert list(logar(equipe_b["gestor"]).get(reverse("liberacao_lista")).context["liberacoes"]) == []


def test_nao_decide_nem_revoga_em_outra_organizacao(logar, equipe_b, pendente_a, aprovada_a):
    client = logar(equipe_b["analista"])
    r = client.post(
        reverse("solicitacao_decidir", args=[pendente_a.pk]), {"acao": "aprovar", "justificativa": "x"}
    )
    assert r.status_code == 404
    pendente_a.refresh_from_db()
    assert pendente_a.estado == "pendente_analise"
    r = client.post(reverse("liberacao_revogar", args=[aprovada_a.liberacao.pk]), {"justificativa": "x"})
    assert r.status_code == 404
    aprovada_a.liberacao.refresh_from_db()
    assert aprovada_a.liberacao.estado == "vigente"


def test_servicos_nao_operam_em_outra_organizacao(equipe_b, pendente_a, aprovada_a):
    with pytest.raises(ObjectDoesNotExist):
        services.decidir_manualmente(
            solicitacao_id=pendente_a.pk, usuario=equipe_b["analista"], aprovar=True, justificativa="x"
        )
    with pytest.raises(ObjectDoesNotExist):
        services.revogar_liberacao(
            liberacao_id=aprovada_a.liberacao.pk, usuario=equipe_b["analista"], justificativa="x"
        )


def test_solicitante_ve_apenas_as_proprias_solicitacoes(logar, org_a, equipe_a, aprovada_a):
    outro = f.criar_usuario(org_a, "solicitante")
    assert list(logar(outro).get(reverse("solicitacao_lista")).context["solicitacoes"]) == []
    assert logar(outro).get(reverse("solicitacao_detalhe", args=[aprovada_a.pk])).status_code == 404
    assert (
        logar(equipe_a["gestor"]).get(reverse("solicitacao_detalhe", args=[aprovada_a.pk])).status_code == 200
    )


def test_historico_e_liberacoes_ficam_na_organizacao(aprovada_a, org_b):
    assert HistoricoEvento.objects.da_organizacao(org_b).count() == 0
    assert Liberacao.objects.da_organizacao(org_b).count() == 0
    assert HistoricoEvento.objects.da_organizacao(aprovada_a.organizacao).count() > 0
