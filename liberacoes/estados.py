"""Estados e transições permitidas.

O relatório define dez estados. No modelo, eles se distribuem entre a solicitação (do rascunho
até a decisão) e a liberação concedida (da vigência ao encerramento):

    SolicitacaoLiberacao: Rascunho, Solicitada, Em avaliação, Pendente de análise, Aprovada, Reprovada
    Liberacao:            Vigente, Expirada, Revogada, Utilizada
"""

from django.db import models


class EstadoSolicitacao(models.TextChoices):
    RASCUNHO = "rascunho", "Rascunho"
    SOLICITADA = "solicitada", "Solicitada"
    EM_AVALIACAO = "em_avaliacao", "Em avaliação"
    PENDENTE_ANALISE = "pendente_analise", "Pendente de análise"
    APROVADA = "aprovada", "Aprovada"
    REPROVADA = "reprovada", "Reprovada"


class EstadoLiberacao(models.TextChoices):
    VIGENTE = "vigente", "Vigente"
    EXPIRADA = "expirada", "Expirada"
    REVOGADA = "revogada", "Revogada"
    UTILIZADA = "utilizada", "Utilizada"


TRANSICOES_SOLICITACAO = {
    EstadoSolicitacao.RASCUNHO: {EstadoSolicitacao.SOLICITADA},
    EstadoSolicitacao.SOLICITADA: {EstadoSolicitacao.EM_AVALIACAO},
    EstadoSolicitacao.EM_AVALIACAO: {
        EstadoSolicitacao.APROVADA,
        EstadoSolicitacao.REPROVADA,
        EstadoSolicitacao.PENDENTE_ANALISE,
    },
    EstadoSolicitacao.PENDENTE_ANALISE: {EstadoSolicitacao.APROVADA, EstadoSolicitacao.REPROVADA},
    EstadoSolicitacao.APROVADA: set(),
    EstadoSolicitacao.REPROVADA: set(),
}

TRANSICOES_LIBERACAO = {
    EstadoLiberacao.VIGENTE: {
        EstadoLiberacao.EXPIRADA,
        EstadoLiberacao.REVOGADA,
        EstadoLiberacao.UTILIZADA,
    },
    EstadoLiberacao.EXPIRADA: set(),
    EstadoLiberacao.REVOGADA: set(),
    EstadoLiberacao.UTILIZADA: set(),
}


class TransicaoInvalida(Exception):
    """Mudança de estado não prevista na máquina de estados."""


def validar_transicao(atual, novo, tabela):
    if novo not in tabela.get(atual, set()):
        raise TransicaoInvalida(f"Transição inválida: {atual} → {novo}.")
