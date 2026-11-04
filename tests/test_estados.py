"""Máquina de estados: transições válidas e inválidas."""

import pytest

from liberacoes.estados import (
    TRANSICOES_LIBERACAO,
    TRANSICOES_SOLICITACAO,
    EstadoLiberacao,
    EstadoSolicitacao,
    TransicaoInvalida,
    validar_transicao,
)

E = EstadoSolicitacao
L = EstadoLiberacao


def test_os_dez_estados_do_relatorio_estao_representados():
    nomes = {e.label for e in E} | {e.label for e in L}
    assert nomes == {
        "Rascunho",
        "Solicitada",
        "Em avaliação",
        "Pendente de análise",
        "Aprovada",
        "Reprovada",
        "Vigente",
        "Expirada",
        "Revogada",
        "Utilizada",
    }


@pytest.mark.parametrize(
    ("de", "para"),
    [
        (E.RASCUNHO, E.SOLICITADA),
        (E.SOLICITADA, E.EM_AVALIACAO),
        (E.EM_AVALIACAO, E.APROVADA),
        (E.EM_AVALIACAO, E.REPROVADA),
        (E.EM_AVALIACAO, E.PENDENTE_ANALISE),
        (E.PENDENTE_ANALISE, E.APROVADA),
        (E.PENDENTE_ANALISE, E.REPROVADA),
    ],
)
def test_transicoes_validas_da_solicitacao(de, para):
    validar_transicao(de, para, TRANSICOES_SOLICITACAO)


@pytest.mark.parametrize(
    ("de", "para"),
    [
        (E.RASCUNHO, E.APROVADA),
        (E.SOLICITADA, E.APROVADA),
        (E.EM_AVALIACAO, E.SOLICITADA),
        (E.REPROVADA, E.APROVADA),
        (E.APROVADA, E.REPROVADA),
        (E.PENDENTE_ANALISE, E.EM_AVALIACAO),
        (E.PENDENTE_ANALISE, E.PENDENTE_ANALISE),
    ],
)
def test_transicoes_invalidas_da_solicitacao(de, para):
    with pytest.raises(TransicaoInvalida):
        validar_transicao(de, para, TRANSICOES_SOLICITACAO)


@pytest.mark.parametrize("para", [L.EXPIRADA, L.REVOGADA, L.UTILIZADA])
def test_vigente_pode_encerrar_de_tres_formas(para):
    validar_transicao(L.VIGENTE, para, TRANSICOES_LIBERACAO)


@pytest.mark.parametrize("de", [L.EXPIRADA, L.REVOGADA, L.UTILIZADA])
@pytest.mark.parametrize("para", list(L))
def test_estados_finais_da_liberacao_nao_mudam(de, para):
    with pytest.raises(TransicaoInvalida):
        validar_transicao(de, para, TRANSICOES_LIBERACAO)


def test_solicitacao_reprovada_nunca_vira_liberacao_vigente():
    assert TRANSICOES_SOLICITACAO[E.REPROVADA] == set()
    assert L.VIGENTE not in {s.value for alvos in TRANSICOES_SOLICITACAO.values() for s in alvos}


def test_servico_nao_permite_pular_estados(aprovada_a):
    from liberacoes.services import _transicionar_solicitacao

    with pytest.raises(TransicaoInvalida):
        _transicionar_solicitacao(aprovada_a, E.REPROVADA)
