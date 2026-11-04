"""Motor de avaliação inicial: regras R01–R05, precedência e justificativas."""

import time
from datetime import timedelta

import pytest
from django.utils import timezone

from cadastros.models import VinculoMotoristaTransportadora
from liberacoes import regras, services
from liberacoes.models import (
    AcaoRegra,
    AvaliacaoRegra,
    EstadoLiberacao,
    EstadoSolicitacao,
    Liberacao,
    Regra,
    ResultadoAutomatico,
)

from . import factories as f


def avaliar(usuario, cenario, **extra):
    return services.solicitar_liberacao(usuario=usuario, **f.dados_solicitacao(cenario, **extra))


def resultado_por_regra(solicitacao):
    return {a.regra.codigo: a for a in solicitacao.avaliacoes.select_related("regra")}


def test_todas_as_regras_atendidas_aprovam_automaticamente(solicitante_a, cenario_a):
    s = avaliar(solicitante_a, cenario_a)
    assert s.estado == EstadoSolicitacao.APROVADA
    assert s.resultado_automatico == ResultadoAutomatico.APROVACAO
    assert set(resultado_por_regra(s)) == {"R01", "R02", "R03", "R04", "R05"}
    assert all(a.atendida for a in s.avaliacoes.all())
    liberacao = Liberacao.objects.get(solicitacao=s)
    assert liberacao.estado == EstadoLiberacao.VIGENTE
    assert (liberacao.valida_de, liberacao.valida_ate) == (s.janela_inicio, s.janela_fim)


def test_motorista_inativo_reprova_automaticamente(solicitante_a, org_a):
    c = f.criar_cenario(org_a, motorista_ativo=False)
    s = avaliar(solicitante_a, c)
    r = resultado_por_regra(s)
    assert s.estado == EstadoSolicitacao.REPROVADA
    assert s.resultado_automatico == ResultadoAutomatico.REPROVACAO
    assert not r["R01"].atendida and "inativo" in r["R01"].justificativa
    assert not Liberacao.objects.filter(solicitacao=s).exists()


def test_ausencia_de_vinculo_reprova(solicitante_a, org_a):
    c = f.criar_cenario(org_a, vinculo=False)
    s = avaliar(solicitante_a, c)
    r = resultado_por_regra(s)
    assert s.estado == EstadoSolicitacao.REPROVADA
    assert not r["R02"].atendida and "Não há vínculo" in r["R02"].justificativa


def test_vinculo_encerrado_antes_do_fim_da_janela_reprova(solicitante_a, org_a):
    c = f.criar_cenario(org_a, vinculo=False)
    hoje = timezone.localdate()
    VinculoMotoristaTransportadora.objects.create(
        organizacao=org_a,
        motorista=c["motorista"],
        transportadora=c["transportadora"],
        inicio=hoje - timedelta(days=10),
        fim=hoje - timedelta(days=1),
    )
    s = avaliar(solicitante_a, c)
    r = resultado_por_regra(s)
    assert s.estado == EstadoSolicitacao.REPROVADA
    assert not r["R02"].atendida and "não está vigente" in r["R02"].justificativa


def test_vinculo_com_outra_transportadora_nao_vale(solicitante_a, org_a):
    c = f.criar_cenario(org_a, vinculo=False)
    outra = f.criar_cenario(org_a)  # cria vínculo do motorista 'outra' com a transportadora 'outra'
    VinculoMotoristaTransportadora.objects.create(
        organizacao=org_a,
        motorista=c["motorista"],
        transportadora=outra["transportadora"],
        inicio=timezone.localdate() - timedelta(days=1),
    )
    assert avaliar(solicitante_a, c).estado == EstadoSolicitacao.REPROVADA


def test_veiculo_inativo_reprova(solicitante_a, org_a):
    s = avaliar(solicitante_a, f.criar_cenario(org_a, veiculo_ativo=False))
    r = resultado_por_regra(s)
    assert s.estado == EstadoSolicitacao.REPROVADA
    assert not r["R03"].atendida and "inativo" in r["R03"].justificativa


def test_cnh_vencendo_antes_do_fim_da_janela_exige_analise_manual(solicitante_a, org_a):
    c = f.criar_cenario(org_a, validade_cnh=timezone.localdate() - timedelta(days=1))
    s = avaliar(solicitante_a, c)
    r = resultado_por_regra(s)
    assert s.estado == EstadoSolicitacao.PENDENTE_ANALISE
    assert s.resultado_automatico == ResultadoAutomatico.PENDENCIA
    assert not r["R05"].atendida and "CNH vence" in r["R05"].justificativa
    assert all(r[c_].atendida for c_ in ("R01", "R02", "R03", "R04"))
    assert not Liberacao.objects.filter(solicitacao=s).exists()


def test_reprovacao_prevalece_sobre_analise_manual(solicitante_a, org_a):
    c = f.criar_cenario(org_a, motorista_ativo=False, validade_cnh=timezone.localdate() - timedelta(days=1))
    s = avaliar(solicitante_a, c)
    r = resultado_por_regra(s)
    assert not r["R01"].atendida and not r["R05"].atendida
    assert s.estado == EstadoSolicitacao.REPROVADA


def test_cada_avaliacao_registra_regra_resultado_e_justificativa(solicitante_a, cenario_a):
    s = avaliar(solicitante_a, cenario_a)
    for a in AvaliacaoRegra.objects.filter(solicitacao=s):
        assert a.regra.codigo and a.justificativa.strip()
        assert a.acao_aplicada == a.regra.acao_se_nao_atendida


def test_regras_iniciais_sao_criadas_uma_unica_vez_por_organizacao(solicitante_a, org_a, cenario_a):
    avaliar(solicitante_a, cenario_a)
    avaliar(solicitante_a, cenario_a)
    assert Regra.objects.filter(organizacao=org_a).count() == len(regras.REGRAS_INICIAIS) == 5
    regras.garantir_regras_iniciais(org_a)
    assert Regra.objects.filter(organizacao=org_a).count() == 5


def test_apenas_r05_e_demonstrativa(org_a):
    regras.garantir_regras_iniciais(org_a)
    assert list(
        Regra.objects.filter(organizacao=org_a, demonstrativa=True).values_list("codigo", flat=True)
    ) == ["R05"]


def test_regra_inativa_nao_e_avaliada(solicitante_a, org_a, cenario_a):
    regras.garantir_regras_iniciais(org_a)
    Regra.objects.filter(organizacao=org_a, codigo="R05").update(ativa=False)
    s = avaliar(solicitante_a, cenario_a)
    assert "R05" not in resultado_por_regra(s)


def test_regra_sem_implementacao_gera_erro_explicito(org_a, aprovada_a):
    regra = Regra(
        organizacao=org_a, codigo="R99", nome="x", descricao="x", acao_se_nao_atendida=AcaoRegra.REPROVAR
    )
    with pytest.raises(LookupError):
        regras.executar_regra(regra, aprovada_a, timezone.now())


@pytest.mark.parametrize(
    ("entradas", "esperado"),
    [
        ([], ResultadoAutomatico.APROVACAO),
        ([(AcaoRegra.REPROVAR, True), (AcaoRegra.ANALISE_MANUAL, True)], ResultadoAutomatico.APROVACAO),
        ([(AcaoRegra.ANALISE_MANUAL, False)], ResultadoAutomatico.PENDENCIA),
        ([(AcaoRegra.REPROVAR, False)], ResultadoAutomatico.REPROVACAO),
        ([(AcaoRegra.ANALISE_MANUAL, False), (AcaoRegra.REPROVAR, False)], ResultadoAutomatico.REPROVACAO),
    ],
)
def test_precedencia_do_resultado(entradas, esperado):
    assert regras.decidir_resultado(entradas) == esperado


def test_r04_detecta_dados_obrigatorios_ausentes(aprovada_a):
    agora = timezone.now()
    aprovada_a.finalidade = " "
    assert not regras.r04_dados_obrigatorios(aprovada_a, agora)[0]
    aprovada_a.finalidade = "ok ok"
    aprovada_a.janela_fim = aprovada_a.janela_inicio
    assert not regras.r04_dados_obrigatorios(aprovada_a, agora)[0]
    aprovada_a.janela_fim = agora - timedelta(minutes=1)
    aprovada_a.janela_inicio = agora - timedelta(hours=1)
    assert "encerrada" in regras.r04_dados_obrigatorios(aprovada_a, agora)[1]


def test_r01_e_r03_detectam_entidade_de_outra_organizacao(aprovada_a, cenario_b):
    agora = timezone.now()
    aprovada_a.motorista = cenario_b["motorista"]
    aprovada_a.veiculo = cenario_b["veiculo"]
    assert not regras.r01_motorista_ativo(aprovada_a, agora)[0]
    assert not regras.r03_veiculo_ativo(aprovada_a, agora)[0]


def test_veiculo_de_outra_transportadora_reprova_na_regra_r03(aprovada_a, org_a):
    outro = f.criar_cenario(org_a)
    aprovada_a.veiculo = outro["veiculo"]
    ok, texto = regras.r03_veiculo_ativo(aprovada_a, timezone.now())
    assert not ok and "pertence a" in texto


def test_avaliacao_em_menos_de_2_segundos(solicitante_a, cenario_a):  # RNF06
    inicio = time.perf_counter()
    avaliar(solicitante_a, cenario_a)
    assert time.perf_counter() - inicio < 2
