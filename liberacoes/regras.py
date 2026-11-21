"""Regras de avaliação automática desta primeira entrega.

São funções determinísticas, sem motor de expressões e sem configuração pelo usuário. Cada função
recebe a solicitação e o instante da avaliação e devolve ``(atendida, justificativa)``.

As regras R01–R04 são os critérios iniciais; **R05 é demonstrativa**: ela existe para demonstrar o
caminho de "pendência de análise manual", usando um critério documental do catálogo do relatório
(validade da CNH). Nenhuma delas reproduz regras de organizações reais.
"""

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.utils import timezone

from cadastros.models import VinculoMotoristaTransportadora

from .models import AcaoRegra, Regra, ResultadoAutomatico


@dataclass(frozen=True)
class DefinicaoRegra:
    codigo: str
    nome: str
    descricao: str
    acao_se_nao_atendida: str
    demonstrativa: bool = False


REGRAS_INICIAIS = [
    DefinicaoRegra(
        "R01",
        "Motorista cadastrado e ativo",
        "O motorista informado deve existir na organização e estar ativo.",
        AcaoRegra.REPROVAR,
    ),
    DefinicaoRegra(
        "R02",
        "Vínculo vigente com a transportadora",
        "Deve existir vínculo entre o motorista e a transportadora, vigente durante toda a janela de acesso.",
        AcaoRegra.REPROVAR,
    ),
    DefinicaoRegra(
        "R03",
        "Veículo cadastrado, ativo e da transportadora",
        "O veículo deve existir na organização, estar ativo e pertencer à transportadora informada.",
        AcaoRegra.REPROVAR,
    ),
    DefinicaoRegra(
        "R04",
        "Dados obrigatórios da solicitação",
        "Finalidade preenchida e janela de acesso válida (fim posterior ao início e ainda não encerrada).",
        AcaoRegra.REPROVAR,
    ),
    DefinicaoRegra(
        "R05",
        "CNH válida durante a janela de acesso (demonstrativa)",
        "A validade da CNH do motorista deve cobrir toda a janela de acesso; caso contrário, "
        "a solicitação exige análise manual.",
        AcaoRegra.ANALISE_MANUAL,
        demonstrativa=True,
    ),
]


def _data_local(instante):
    return timezone.localtime(instante).date()


def r01_motorista_ativo(solicitacao, agora):
    motorista = solicitacao.motorista
    if motorista.organizacao_id != solicitacao.organizacao_id:
        return False, "Motorista não pertence à organização da solicitação."
    if not motorista.ativo:
        return False, f"O motorista {motorista.nome} está inativo."
    return True, f"O motorista {motorista.nome} está cadastrado e ativo."


def r02_vinculo_vigente(solicitacao, agora):
    inicio = _data_local(solicitacao.janela_inicio)
    fim = _data_local(solicitacao.janela_fim)
    vinculos = VinculoMotoristaTransportadora.objects.da_organizacao(solicitacao.organizacao).filter(
        motorista=solicitacao.motorista, transportadora=solicitacao.transportadora
    )
    if not vinculos.exists():
        return False, (
            f"Não há vínculo entre {solicitacao.motorista.nome} e {solicitacao.transportadora.nome}."
        )
    if not vinculos.cobrindo_periodo(inicio, fim).exists():
        return False, (
            f"O vínculo entre {solicitacao.motorista.nome} e {solicitacao.transportadora.nome} "
            f"não está vigente durante toda a janela ({inicio:%d/%m/%Y} a {fim:%d/%m/%Y})."
        )
    return True, "Há vínculo vigente durante toda a janela de acesso."


def r03_veiculo_ativo(solicitacao, agora):
    veiculo = solicitacao.veiculo
    if veiculo.organizacao_id != solicitacao.organizacao_id:
        return False, "Veículo não pertence à organização da solicitação."
    if not veiculo.ativo:
        return False, f"O veículo {veiculo.placa} está inativo."
    if not solicitacao.transportadora.ativa:
        return False, f"A transportadora {solicitacao.transportadora.nome} está inativa."
    if veiculo.transportadora_id != solicitacao.transportadora_id:
        return False, (
            f"O veículo {veiculo.placa} pertence a {veiculo.transportadora.nome}, "
            f"e não a {solicitacao.transportadora.nome}."
        )
    return True, f"O veículo {veiculo.placa} está cadastrado, ativo e associado à transportadora."


def r04_dados_obrigatorios(solicitacao, agora):
    if len((solicitacao.finalidade or "").strip()) < 3:
        return False, "A finalidade da liberação não foi informada."
    if not solicitacao.janela_inicio or not solicitacao.janela_fim:
        return False, "A janela de acesso não foi informada."
    if solicitacao.janela_fim <= solicitacao.janela_inicio:
        return False, "O fim da janela de acesso deve ser posterior ao início."
    if solicitacao.janela_fim <= agora:
        return False, "A janela de acesso já está encerrada."
    return True, "Finalidade e janela de acesso válidas."


def r05_cnh_valida(solicitacao, agora):
    validade = solicitacao.motorista.validade_cnh
    fim = _data_local(solicitacao.janela_fim)
    if validade < fim:
        return False, (f"A CNH vence em {validade:%d/%m/%Y}, antes do fim da janela ({fim:%d/%m/%Y}).")
    return True, f"A CNH é válida até {validade:%d/%m/%Y}, cobrindo toda a janela de acesso."


FUNCOES = {
    "R01": r01_motorista_ativo,
    "R02": r02_vinculo_vigente,
    "R03": r03_veiculo_ativo,
    "R04": r04_dados_obrigatorios,
    "R05": r05_cnh_valida,
}


def garantir_regras_iniciais(organizacao):
    """Cria (idempotentemente) as regras iniciais da organização."""
    for definicao in REGRAS_INICIAIS:
        Regra.objects.get_or_create(
            organizacao=organizacao,
            codigo=definicao.codigo,
            defaults={
                "nome": definicao.nome,
                "descricao": definicao.descricao,
                "acao_se_nao_atendida": definicao.acao_se_nao_atendida,
                "demonstrativa": definicao.demonstrativa,
            },
        )


def regras_ativas(organizacao):
    """Retorna as regras ativas configuradas para a organização."""
    return Regra.objects.da_organizacao(organizacao).filter(ativa=True)


def exigir_regras_ativas(organizacao):
    """Impede a avaliação quando a organização não possui regra ativa."""
    regras_organizacao = regras_ativas(organizacao)
    if not regras_organizacao.exists():
        raise ValidationError(
            "A solicitação não pode ser avaliada: a organização não possui regras ativas configuradas."
        )
    return regras_organizacao


def executar_regra(regra, solicitacao, agora):
    funcao = FUNCOES.get(regra.codigo)
    if funcao is None:
        raise LookupError(f"Não há implementação para a regra {regra.codigo}.")
    return funcao(solicitacao, agora)


def decidir_resultado(avaliacoes):
    """Precedência: reprovação > análise manual > aprovação.

    ``avaliacoes`` é uma lista de ``(acao_se_nao_atendida, atendida)``. Devolve o
    ``ResultadoAutomatico`` correspondente.
    """
    if not avaliacoes:
        raise ValidationError("Não é possível decidir uma avaliação sem regras executadas.")

    nao_atendidas = [acao for acao, atendida in avaliacoes if not atendida]
    if AcaoRegra.REPROVAR in nao_atendidas:
        return ResultadoAutomatico.REPROVACAO
    if AcaoRegra.ANALISE_MANUAL in nao_atendidas:
        return ResultadoAutomatico.PENDENCIA
    return ResultadoAutomatico.APROVACAO
