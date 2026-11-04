"""Revogação e expiração de liberações."""

from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from accounts.models import Papel
from liberacoes import services
from liberacoes.estados import TransicaoInvalida
from liberacoes.models import EstadoLiberacao, HistoricoEvento, Liberacao, TipoEvento


def revogar(client, liberacao, justificativa="Motorista com restrição nova."):
    return client.post(reverse("liberacao_revogar", args=[liberacao.pk]), {"justificativa": justificativa})


def test_analista_revoga_liberacao_vigente(logar, analista_a, aprovada_a):
    liberacao = aprovada_a.liberacao
    resposta = revogar(logar(analista_a), liberacao)
    assert resposta.status_code == 302
    liberacao.refresh_from_db()
    assert liberacao.estado == EstadoLiberacao.REVOGADA
    assert liberacao.revogada_por == analista_a and liberacao.revogada_em is not None
    assert liberacao.justificativa_revogacao == "Motorista com restrição nova."


def test_revogacao_gera_evento_no_historico(logar, analista_a, aprovada_a):
    revogar(logar(analista_a), aprovada_a.liberacao)
    evento = aprovada_a.eventos.get(tipo=TipoEvento.LIBERACAO_REVOGADA)
    assert evento.usuario == analista_a
    assert evento.justificativa == "Motorista com restrição nova."
    assert evento.liberacao == aprovada_a.liberacao


@pytest.mark.parametrize("justificativa", ["", "   "])
def test_justificativa_obrigatoria_na_revogacao(logar, analista_a, aprovada_a, justificativa):
    revogar(logar(analista_a), aprovada_a.liberacao, justificativa)
    aprovada_a.liberacao.refresh_from_db()
    assert aprovada_a.liberacao.estado == EstadoLiberacao.VIGENTE
    assert not aprovada_a.eventos.filter(tipo=TipoEvento.LIBERACAO_REVOGADA).exists()


def test_servico_exige_justificativa_na_revogacao(analista_a, aprovada_a):
    with pytest.raises(ValidationError):
        services.revogar_liberacao(
            liberacao_id=aprovada_a.liberacao.pk, usuario=analista_a, justificativa=" "
        )


@pytest.mark.parametrize("papel", [Papel.SOLICITANTE, Papel.GESTOR, Papel.ADMINISTRADOR])
def test_outros_papeis_nao_revogam(logar, equipe_a, aprovada_a, papel):
    assert revogar(logar(equipe_a[papel]), aprovada_a.liberacao).status_code == 403
    aprovada_a.liberacao.refresh_from_db()
    assert aprovada_a.liberacao.estado == EstadoLiberacao.VIGENTE


def test_servico_bloqueia_papel_sem_permissao(gestor_a, aprovada_a):
    with pytest.raises(PermissionDenied):
        services.revogar_liberacao(liberacao_id=aprovada_a.liberacao.pk, usuario=gestor_a, justificativa="x")


def test_nao_revoga_duas_vezes(analista_a, aprovada_a):
    services.revogar_liberacao(liberacao_id=aprovada_a.liberacao.pk, usuario=analista_a, justificativa="x")
    with pytest.raises(TransicaoInvalida):
        services.revogar_liberacao(
            liberacao_id=aprovada_a.liberacao.pk, usuario=analista_a, justificativa="y"
        )


def test_solicitacao_reprovada_nao_tem_liberacao_vigente(solicitante_a, org_a):
    from . import factories as f

    s = services.solicitar_liberacao(
        usuario=solicitante_a, **f.dados_solicitacao(f.criar_cenario(org_a, vinculo=False))
    )
    assert s.estado == "reprovada"
    assert not Liberacao.objects.vigentes().filter(solicitacao=s).exists()


def test_expira_liberacao_vencida_e_registra_evento(org_a, aprovada_a):
    depois = aprovada_a.janela_fim + timedelta(minutes=1)
    assert services.expirar_liberacoes_vencidas(org_a, agora=depois) == 1
    aprovada_a.liberacao.refresh_from_db()
    assert aprovada_a.liberacao.estado == EstadoLiberacao.EXPIRADA
    assert aprovada_a.eventos.filter(tipo=TipoEvento.LIBERACAO_EXPIRADA, usuario=None).exists()
    assert services.expirar_liberacoes_vencidas(org_a, agora=depois) == 0  # idempotente


def test_nao_expira_liberacao_dentro_da_validade(org_a, aprovada_a):
    assert services.expirar_liberacoes_vencidas(org_a) == 0
    aprovada_a.liberacao.refresh_from_db()
    assert aprovada_a.liberacao.estado == EstadoLiberacao.VIGENTE


def test_nao_revoga_liberacao_expirada(analista_a, aprovada_a):
    depois = aprovada_a.janela_fim + timedelta(hours=1)
    with pytest.raises(TransicaoInvalida):
        services.revogar_liberacao(
            liberacao_id=aprovada_a.liberacao.pk, usuario=analista_a, justificativa="x", agora=depois
        )
    aprovada_a.liberacao.refresh_from_db()
    assert aprovada_a.liberacao.estado == EstadoLiberacao.EXPIRADA


def test_tela_mostra_botao_de_revogar_apenas_para_vigente(logar, analista_a, aprovada_a):
    url = reverse("solicitacao_detalhe", args=[aprovada_a.pk])
    client = logar(analista_a)
    assert "Revogar liberação" in client.get(url).content.decode()
    revogar(client, aprovada_a.liberacao)
    html = client.get(url).content.decode()
    assert "Revogar liberação" not in html and "Revogada" in html


def test_lista_de_liberacoes_e_filtro(logar, analista_a, aprovada_a):
    client = logar(analista_a)
    assert list(client.get(reverse("liberacao_lista"), {"estado": "vigente"}).context["liberacoes"]) == [
        aprovada_a.liberacao
    ]
    assert list(client.get(reverse("liberacao_lista"), {"estado": "revogada"}).context["liberacoes"]) == []


def test_revogacao_e_atomica(analista_a, aprovada_a, monkeypatch):
    def falha(*a, **k):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(services, "registrar_evento", falha)
    with pytest.raises(RuntimeError):
        services.revogar_liberacao(
            liberacao_id=aprovada_a.liberacao.pk, usuario=analista_a, justificativa="x"
        )
    aprovada_a.liberacao.refresh_from_db()
    assert aprovada_a.liberacao.estado == EstadoLiberacao.VIGENTE
    assert HistoricoEvento.objects.filter(tipo=TipoEvento.LIBERACAO_REVOGADA).count() == 0
