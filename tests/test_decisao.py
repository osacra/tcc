"""Análise manual: aprovação, reprovação, justificativa obrigatória e permissões."""

from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from accounts.models import Papel
from liberacoes import services
from liberacoes.estados import TransicaoInvalida
from liberacoes.models import EstadoLiberacao, EstadoSolicitacao, HistoricoEvento, Liberacao


def decidir(client, solicitacao, acao="aprovar", justificativa="Documentos conferidos."):
    return client.post(
        reverse("solicitacao_decidir", args=[solicitacao.pk]), {"acao": acao, "justificativa": justificativa}
    )


def test_pendencias_aparecem_na_fila_do_analista(logar, analista_a, pendente_a, aprovada_a):
    fila = list(logar(analista_a).get(reverse("analise_lista")).context["solicitacoes"])
    assert fila == [pendente_a]


def test_tela_de_analise_mostra_dados_e_resultado_da_avaliacao(logar, analista_a, pendente_a):
    html = logar(analista_a).get(reverse("solicitacao_detalhe", args=[pendente_a.pk])).content.decode()
    assert pendente_a.motorista.nome in html
    assert pendente_a.veiculo.placa in html
    assert pendente_a.transportadora.nome in html
    assert "R05" in html and "Não atendida" in html
    assert "Registrar decisão" in html


def test_aprovacao_manual_gera_liberacao_vigente_com_validade_da_janela(logar, analista_a, pendente_a):
    resposta = decidir(logar(analista_a), pendente_a)
    assert resposta.status_code == 302
    pendente_a.refresh_from_db()
    assert pendente_a.estado == EstadoSolicitacao.APROVADA
    assert pendente_a.decidida_por == analista_a and pendente_a.decidida_em
    assert pendente_a.justificativa_decisao == "Documentos conferidos."
    liberacao = Liberacao.objects.get(solicitacao=pendente_a)
    assert liberacao.estado == EstadoLiberacao.VIGENTE
    assert (liberacao.valida_de, liberacao.valida_ate) == (pendente_a.janela_inicio, pendente_a.janela_fim)


def test_reprovacao_manual_nao_gera_liberacao(logar, analista_a, pendente_a):
    decidir(logar(analista_a), pendente_a, acao="reprovar", justificativa="CNH vencida.")
    pendente_a.refresh_from_db()
    assert pendente_a.estado == EstadoSolicitacao.REPROVADA
    assert not Liberacao.objects.filter(solicitacao=pendente_a).exists()


@pytest.mark.parametrize("justificativa", ["", "   ", "\n\t"])
def test_justificativa_e_obrigatoria(logar, analista_a, pendente_a, justificativa):
    resposta = decidir(logar(analista_a), pendente_a, justificativa=justificativa)
    assert resposta.status_code == 302
    pendente_a.refresh_from_db()
    assert pendente_a.estado == EstadoSolicitacao.PENDENTE_ANALISE
    assert not Liberacao.objects.exists()


def test_mensagem_de_erro_para_justificativa_ausente(logar, analista_a, pendente_a):
    resposta = logar(analista_a).post(
        reverse("solicitacao_decidir", args=[pendente_a.pk]),
        {"acao": "aprovar", "justificativa": ""},
        follow=True,
    )
    assert (
        "obrigatório" in resposta.content.decode().lower() or "required" in resposta.content.decode().lower()
    )


def test_servico_exige_justificativa(analista_a, pendente_a):
    with pytest.raises(ValidationError):
        services.decidir_manualmente(
            solicitacao_id=pendente_a.pk, usuario=analista_a, aprovar=True, justificativa="  "
        )


def test_acao_invalida_e_rejeitada(logar, analista_a, pendente_a):
    decidir(logar(analista_a), pendente_a, acao="talvez")
    pendente_a.refresh_from_db()
    assert pendente_a.estado == EstadoSolicitacao.PENDENTE_ANALISE


@pytest.mark.parametrize("papel", [Papel.SOLICITANTE, Papel.GESTOR, Papel.ADMINISTRADOR])
def test_usuarios_sem_permissao_nao_decidem(logar, equipe_a, pendente_a, papel):
    assert decidir(logar(equipe_a[papel]), pendente_a).status_code == 403
    pendente_a.refresh_from_db()
    assert pendente_a.estado == EstadoSolicitacao.PENDENTE_ANALISE


def test_anonimo_nao_decide(client, pendente_a):
    resposta = decidir(client, pendente_a)
    assert resposta.status_code == 302 and resposta.url.startswith(reverse("login"))


def test_servico_bloqueia_usuario_sem_permissao(solicitante_a, pendente_a):
    with pytest.raises(PermissionDenied):
        services.decidir_manualmente(
            solicitacao_id=pendente_a.pk, usuario=solicitante_a, aprovar=True, justificativa="x"
        )


def test_so_decide_solicitacao_pendente(analista_a, aprovada_a):
    with pytest.raises(TransicaoInvalida):
        services.decidir_manualmente(
            solicitacao_id=aprovada_a.pk, usuario=analista_a, aprovar=False, justificativa="x"
        )
    aprovada_a.refresh_from_db()
    assert aprovada_a.estado == EstadoSolicitacao.APROVADA


def test_nao_decide_duas_vezes(logar, analista_a, pendente_a):
    client = logar(analista_a)
    decidir(client, pendente_a, acao="reprovar")
    decidir(client, pendente_a, acao="aprovar")
    pendente_a.refresh_from_db()
    assert pendente_a.estado == EstadoSolicitacao.REPROVADA
    assert not Liberacao.objects.exists()


def test_nao_aprova_com_janela_encerrada_mas_pode_reprovar(analista_a, pendente_a):
    depois = pendente_a.janela_fim + timedelta(minutes=1)
    with pytest.raises(ValidationError):
        services.decidir_manualmente(
            solicitacao_id=pendente_a.pk, usuario=analista_a, aprovar=True, justificativa="x", agora=depois
        )
    pendente_a.refresh_from_db()
    assert pendente_a.estado == EstadoSolicitacao.PENDENTE_ANALISE
    services.decidir_manualmente(
        solicitacao_id=pendente_a.pk, usuario=analista_a, aprovar=False, justificativa="x", agora=depois
    )
    pendente_a.refresh_from_db()
    assert pendente_a.estado == EstadoSolicitacao.REPROVADA


def test_decisao_e_atomica_em_caso_de_falha(analista_a, pendente_a, monkeypatch):
    def falha(*args, **kwargs):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(services, "_criar_liberacao", falha)
    eventos_antes = HistoricoEvento.objects.count()
    with pytest.raises(RuntimeError):
        services.decidir_manualmente(
            solicitacao_id=pendente_a.pk, usuario=analista_a, aprovar=True, justificativa="x"
        )
    pendente_a.refresh_from_db()
    assert pendente_a.estado == EstadoSolicitacao.PENDENTE_ANALISE
    assert pendente_a.decidida_por is None
    assert HistoricoEvento.objects.count() == eventos_antes


def test_formulario_de_decisao_so_aparece_para_analista_e_se_pendente(
    logar, equipe_a, pendente_a, aprovada_a
):
    url_pendente = reverse("solicitacao_detalhe", args=[pendente_a.pk])
    assert "Registrar decisão" in logar(equipe_a[Papel.ANALISTA]).get(url_pendente).content.decode()
    assert "Registrar decisão" not in logar(equipe_a[Papel.GESTOR]).get(url_pendente).content.decode()
    url_aprovada = reverse("solicitacao_detalhe", args=[aprovada_a.pk])
    assert "Registrar decisão" not in logar(equipe_a[Papel.ANALISTA]).get(url_aprovada).content.decode()


def test_decisao_via_get_nao_e_permitida(logar, analista_a, pendente_a):
    assert logar(analista_a).get(reverse("solicitacao_decidir", args=[pendente_a.pk])).status_code == 405


def test_aprovacao_automatica_nao_registra_decisor_manual(aprovada_a):
    assert aprovada_a.decidida_por is None and aprovada_a.resultado_automatico == "aprovacao_automatica"
    assert aprovada_a.janela_fim > timezone.now()
