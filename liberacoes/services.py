"""Serviços do processo de liberação.

Toda mudança de estado do processo passa por aqui, dentro de transações, de modo que solicitação,
avaliações, decisão, liberação e histórico sejam gravados de forma consistente (tudo ou nada).
"""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.models import Papel
from cadastros.models import Motorista, Transportadora, Veiculo

from . import regras
from .estados import (
    TRANSICOES_LIBERACAO,
    TRANSICOES_SOLICITACAO,
    TransicaoInvalida,
    validar_transicao,
)
from .models import (
    AvaliacaoRegra,
    EstadoLiberacao,
    EstadoSolicitacao,
    HistoricoEvento,
    Liberacao,
    ResultadoAutomatico,
    SolicitacaoLiberacao,
    TipoEvento,
)


def registrar_evento(
    solicitacao, tipo, descricao, *, usuario=None, justificativa="", liberacao=None, dados=None
):
    if liberacao is not None and liberacao.solicitacao_id != solicitacao.pk:
        raise ValidationError("A liberação do evento não pertence à solicitação informada.")
    if usuario is not None and usuario.organizacao_id != solicitacao.organizacao_id:
        raise PermissionDenied("Usuário de outra organização.")
    return HistoricoEvento.objects.create(
        organizacao=solicitacao.organizacao,
        solicitacao=solicitacao,
        liberacao=liberacao,
        tipo=tipo,
        usuario=usuario,
        descricao=descricao,
        justificativa=justificativa,
        dados=dados or {},
    )


def _exigir_papel(usuario, papel):
    if (
        not usuario.is_authenticated
        or not usuario.is_active
        or usuario.papel != papel
        or usuario.organizacao_id is None
    ):
        raise PermissionDenied("Usuário sem permissão para esta ação.")
    if not usuario.organizacao.ativa:
        raise PermissionDenied("Usuário sem permissão para esta ação.")


def _transicionar_solicitacao(solicitacao, novo_estado):
    validar_transicao(solicitacao.estado, novo_estado, TRANSICOES_SOLICITACAO)
    solicitacao.estado = novo_estado
    solicitacao.save(update_fields=["estado", "atualizada_em"])


def _transicionar_liberacao(liberacao, novo_estado):
    validar_transicao(liberacao.estado, novo_estado, TRANSICOES_LIBERACAO)
    liberacao.estado = novo_estado


def _justificativa_obrigatoria(texto):
    texto = (texto or "").strip()
    if not texto:
        raise ValidationError("A justificativa é obrigatória.")
    return texto


def _criar_liberacao(solicitacao, usuario, agora):
    liberacao = Liberacao.objects.create(
        organizacao=solicitacao.organizacao,
        solicitacao=solicitacao,
        estado=EstadoLiberacao.VIGENTE,
        valida_de=solicitacao.janela_inicio,
        valida_ate=solicitacao.janela_fim,
    )
    registrar_evento(
        solicitacao,
        TipoEvento.LIBERACAO_CRIADA,
        f"Liberação #{liberacao.pk} criada, válida de "
        f"{timezone.localtime(liberacao.valida_de):%d/%m/%Y %H:%M} "
        f"até {timezone.localtime(liberacao.valida_ate):%d/%m/%Y %H:%M}.",
        usuario=usuario,
        liberacao=liberacao,
    )
    return liberacao


# --- Solicitação e avaliação automática -----------------------------------------------------


@transaction.atomic
def solicitar_liberacao(
    *, usuario, motorista, veiculo, transportadora, finalidade, janela_inicio, janela_fim, agora=None
):
    """Cria a solicitação, envia para avaliação e executa as regras iniciais (tudo em uma transação).

    Rejeita (``ValidationError``) solicitações estruturalmente inconsistentes: entidades de outra
    organização, janela inválida ou veículo de outra transportadora. A ausência de vínculo
    vigente e o motorista/veículo inativos NÃO são bloqueados aqui: são avaliados pelas regras,
    resultando em reprovação automática registrada e justificada.
    """
    _exigir_papel(usuario, Papel.SOLICITANTE)
    agora = agora or timezone.now()
    organizacao = usuario.organizacao

    for objeto, modelo, nome in (
        (motorista, Motorista, "Motorista"),
        (veiculo, Veiculo, "Veículo"),
        (transportadora, Transportadora, "Transportadora"),
    ):
        if objeto is None or not modelo.objects.da_organizacao(organizacao).filter(pk=objeto.pk).exists():
            raise ValidationError(f"{nome} inexistente ou de outra organização.")
    if veiculo.transportadora_id != transportadora.pk:
        raise ValidationError("O veículo informado não pertence à transportadora informada.")
    if not (finalidade or "").strip():
        raise ValidationError("Informe a finalidade da liberação.")
    if not janela_inicio or not janela_fim or janela_fim <= janela_inicio:
        raise ValidationError("O fim da janela de acesso deve ser posterior ao início.")
    if janela_fim <= agora:
        raise ValidationError("A janela de acesso já está encerrada.")
    regras.exigir_regras_ativas(organizacao)

    solicitacao = SolicitacaoLiberacao.objects.create(
        organizacao=organizacao,
        solicitante=usuario,
        motorista=motorista,
        veiculo=veiculo,
        transportadora=transportadora,
        finalidade=finalidade.strip(),
        janela_inicio=janela_inicio,
        janela_fim=janela_fim,
        estado=EstadoSolicitacao.RASCUNHO,
    )
    registrar_evento(
        solicitacao,
        TipoEvento.SOLICITACAO_CRIADA,
        f"Solicitação criada para o motorista {motorista.nome}, veículo {veiculo.placa}, "
        f"transportadora {transportadora.nome}.",
        usuario=usuario,
    )
    _transicionar_solicitacao(solicitacao, EstadoSolicitacao.SOLICITADA)
    registrar_evento(
        solicitacao, TipoEvento.ENVIADA_PARA_AVALIACAO, "Solicitação enviada para avaliação.", usuario=usuario
    )
    solicitacao = avaliar_solicitacao(solicitacao, usuario=usuario, agora=agora)
    return solicitacao


def avaliar_solicitacao(solicitacao, *, usuario=None, agora=None):
    """Executa regras ativas e aplica o resultado, bloqueando configuração ausente."""
    agora = agora or timezone.now()
    with transaction.atomic():
        solicitacao = SolicitacaoLiberacao.objects.select_for_update().get(pk=solicitacao.pk)
        regras_ativas = regras.exigir_regras_ativas(solicitacao.organizacao)
        _transicionar_solicitacao(solicitacao, EstadoSolicitacao.EM_AVALIACAO)

        resumo = []
        for regra in regras_ativas:
            atendida, justificativa = regras.executar_regra(regra, solicitacao, agora)
            AvaliacaoRegra.objects.create(
                organizacao=solicitacao.organizacao,
                solicitacao=solicitacao,
                regra=regra,
                atendida=atendida,
                acao_aplicada=regra.acao_se_nao_atendida,
                justificativa=justificativa,
            )
            registrar_evento(
                solicitacao,
                TipoEvento.REGRA_AVALIADA,
                f"{regra.codigo} — {regra.nome}: "
                f"{'atendida' if atendida else 'NÃO atendida'}. {justificativa}",
                dados={"regra": regra.codigo, "atendida": atendida, "acao": regra.acao_se_nao_atendida},
            )
            resumo.append((regra.acao_se_nao_atendida, atendida))

        resultado = regras.decidir_resultado(resumo)
        solicitacao.resultado_automatico = resultado
        if resultado == ResultadoAutomatico.REPROVACAO:
            _transicionar_solicitacao(solicitacao, EstadoSolicitacao.REPROVADA)
            registrar_evento(
                solicitacao,
                TipoEvento.REPROVADA_AUTOMATICAMENTE,
                "Solicitação reprovada automaticamente: há condição impeditiva (ver regras avaliadas).",
            )
        elif resultado == ResultadoAutomatico.PENDENCIA:
            _transicionar_solicitacao(solicitacao, EstadoSolicitacao.PENDENTE_ANALISE)
            registrar_evento(
                solicitacao,
                TipoEvento.ENCAMINHADA_ANALISE,
                "Solicitação encaminhada para análise manual do Analista de Segurança.",
            )
        else:
            _transicionar_solicitacao(solicitacao, EstadoSolicitacao.APROVADA)
            registrar_evento(
                solicitacao,
                TipoEvento.APROVADA_AUTOMATICAMENTE,
                "Solicitação aprovada automaticamente: todas as regras foram atendidas.",
            )
            _criar_liberacao(solicitacao, None, agora)
        solicitacao.save(update_fields=["resultado_automatico", "atualizada_em"])
    return solicitacao


# --- Decisão manual -------------------------------------------------------------------------


@transaction.atomic
def decidir_manualmente(*, solicitacao_id, usuario, aprovar, justificativa, agora=None):
    """Aprovação ou reprovação manual pelo Analista de Segurança, com justificativa obrigatória."""
    _exigir_papel(usuario, Papel.ANALISTA)
    justificativa = _justificativa_obrigatoria(justificativa)
    agora = agora or timezone.now()
    # DoesNotExist se a solicitação não existir ou for de outra organização.
    solicitacao = (
        SolicitacaoLiberacao.objects.da_organizacao(usuario.organizacao)
        .select_for_update()
        .get(pk=solicitacao_id)
    )
    if solicitacao.estado != EstadoSolicitacao.PENDENTE_ANALISE:
        raise TransicaoInvalida("Somente solicitações pendentes de análise podem ser decididas.")
    if aprovar and solicitacao.janela_fim <= agora:
        raise ValidationError("A janela de acesso já está encerrada: a solicitação não pode ser aprovada.")

    novo_estado = EstadoSolicitacao.APROVADA if aprovar else EstadoSolicitacao.REPROVADA
    _transicionar_solicitacao(solicitacao, novo_estado)
    solicitacao.decidida_por = usuario
    solicitacao.decidida_em = agora
    solicitacao.justificativa_decisao = justificativa
    solicitacao.save(update_fields=["decidida_por", "decidida_em", "justificativa_decisao", "atualizada_em"])
    registrar_evento(
        solicitacao,
        TipoEvento.APROVADA_MANUALMENTE if aprovar else TipoEvento.REPROVADA_MANUALMENTE,
        f"Solicitação {'aprovada' if aprovar else 'reprovada'} manualmente por {usuario}.",
        usuario=usuario,
        justificativa=justificativa,
    )
    if aprovar:
        _criar_liberacao(solicitacao, usuario, agora)
    return solicitacao


# --- Revogação e expiração ------------------------------------------------------------------


def expirar_liberacoes_vencidas(organizacao, agora=None):
    """Move para Expirada as liberações vigentes cuja validade terminou. Devolve a quantidade."""
    agora = agora or timezone.now()
    quantidade = 0
    with transaction.atomic():
        vencidas = (
            Liberacao.objects.da_organizacao(organizacao)
            .vigentes()
            .filter(valida_ate__lte=agora)
            .select_for_update()
            .select_related("solicitacao")
        )
        for liberacao in list(vencidas):
            _transicionar_liberacao(liberacao, EstadoLiberacao.EXPIRADA)
            liberacao.save(update_fields=["estado"])
            registrar_evento(
                liberacao.solicitacao,
                TipoEvento.LIBERACAO_EXPIRADA,
                f"Liberação #{liberacao.pk} expirou (fim da validade).",
                liberacao=liberacao,
            )
            quantidade += 1
    return quantidade


@transaction.atomic
def utilizar_liberacao(*, liberacao_id, organizacao, agora=None):
    """Marca uma liberação vigente como utilizada uma única vez."""
    agora = agora or timezone.now()
    liberacao = (
        Liberacao.objects.da_organizacao(organizacao)
        .select_for_update()
        .select_related("solicitacao")
        .get(pk=liberacao_id)
    )
    if liberacao.valida_ate <= agora:
        expirar_liberacoes_vencidas(organizacao, agora)
        liberacao.refresh_from_db()
    _transicionar_liberacao(liberacao, EstadoLiberacao.UTILIZADA)
    liberacao.save(update_fields=["estado"])
    registrar_evento(
        liberacao.solicitacao,
        TipoEvento.LIBERACAO_UTILIZADA,
        f"Liberação #{liberacao.pk} utilizada.",
        liberacao=liberacao,
    )
    return liberacao


def revogar_liberacao(*, liberacao_id, usuario, justificativa, agora=None):
    """Revoga uma liberação vigente (Analista de Segurança), com justificativa obrigatória."""
    _exigir_papel(usuario, Papel.ANALISTA)
    justificativa = _justificativa_obrigatoria(justificativa)
    agora = agora or timezone.now()
    expirar_liberacoes_vencidas(usuario.organizacao, agora)
    with transaction.atomic():
        liberacao = (
            Liberacao.objects.da_organizacao(usuario.organizacao)
            .select_for_update()
            .select_related("solicitacao")
            .get(pk=liberacao_id)
        )
        _transicionar_liberacao(liberacao, EstadoLiberacao.REVOGADA)
        liberacao.revogada_por = usuario
        liberacao.revogada_em = agora
        liberacao.justificativa_revogacao = justificativa
        liberacao.save(update_fields=["estado", "revogada_por", "revogada_em", "justificativa_revogacao"])
        registrar_evento(
            liberacao.solicitacao,
            TipoEvento.LIBERACAO_REVOGADA,
            f"Liberação #{liberacao.pk} revogada por {usuario}.",
            usuario=usuario,
            justificativa=justificativa,
            liberacao=liberacao,
        )
    return liberacao
