"""Histórico e auditoria: registro dos eventos, responsável e imutabilidade (RNF03)."""

import pytest
from django.db import DatabaseError, connection, transaction
from django.urls import reverse

from liberacoes import services
from liberacoes.models import HistoricoEvento, TipoEvento

from . import factories as f

T = TipoEvento


def tipos(solicitacao):
    return [e.tipo for e in solicitacao.eventos.all()]


def test_eventos_da_aprovacao_automatica(aprovada_a):
    t = tipos(aprovada_a)
    assert t[0] == T.SOLICITACAO_CRIADA and t[1] == T.ENVIADA_PARA_AVALIACAO
    assert t.count(T.REGRA_AVALIADA) == 5
    assert t[-2:] == [T.APROVADA_AUTOMATICAMENTE, T.LIBERACAO_CRIADA]


def test_eventos_da_reprovacao_automatica(solicitante_a, org_a):
    s = services.solicitar_liberacao(
        usuario=solicitante_a, **f.dados_solicitacao(f.criar_cenario(org_a, motorista_ativo=False))
    )
    assert tipos(s)[-1] == T.REPROVADA_AUTOMATICAMENTE
    assert T.LIBERACAO_CRIADA not in tipos(s)


def test_eventos_do_encaminhamento_e_da_decisao_manual(analista_a, pendente_a):
    assert tipos(pendente_a)[-1] == T.ENCAMINHADA_ANALISE
    services.decidir_manualmente(
        solicitacao_id=pendente_a.pk, usuario=analista_a, aprovar=True, justificativa="Conferido."
    )
    t = tipos(pendente_a)
    assert t[-2:] == [T.APROVADA_MANUALMENTE, T.LIBERACAO_CRIADA]
    decisao = pendente_a.eventos.get(tipo=T.APROVADA_MANUALMENTE)
    assert decisao.usuario == analista_a and decisao.justificativa == "Conferido."


def test_responsavel_data_e_hora_de_cada_evento(solicitante_a, aprovada_a):
    criada = aprovada_a.eventos.get(tipo=T.SOLICITACAO_CRIADA)
    assert criada.usuario == solicitante_a and criada.criado_em is not None
    automatico = aprovada_a.eventos.get(tipo=T.APROVADA_AUTOMATICAMENTE)
    assert automatico.usuario is None and automatico.responsavel == "Sistema"


def test_resultado_de_cada_regra_fica_no_historico(aprovada_a):
    eventos = aprovada_a.eventos.filter(tipo=T.REGRA_AVALIADA)
    assert {e.dados["regra"] for e in eventos} == {"R01", "R02", "R03", "R04", "R05"}
    assert all(e.dados["atendida"] is True for e in eventos)
    assert all(e.descricao.startswith("R0") for e in eventos)


def test_eventos_em_ordem_cronologica(aprovada_a):
    instantes = [e.criado_em for e in aprovada_a.eventos.all()]
    assert instantes == sorted(instantes)


def test_gestor_consulta_o_historico_na_tela(logar, gestor_a, aprovada_a):
    html = logar(gestor_a).get(reverse("solicitacao_detalhe", args=[aprovada_a.pk])).content.decode()
    assert "Histórico" in html and "Solicitação criada" in html and "Aprovada automaticamente" in html


def test_historico_nao_pode_ser_alterado_pela_aplicacao(aprovada_a):
    evento = aprovada_a.eventos.first()
    evento.descricao = "adulterado"
    with pytest.raises(PermissionError):
        evento.save()
    with pytest.raises(PermissionError):
        evento.delete()
    with pytest.raises(PermissionError):
        HistoricoEvento.objects.all().update(descricao="x")
    with pytest.raises(PermissionError):
        HistoricoEvento.objects.all().delete()
    with pytest.raises(PermissionError):
        HistoricoEvento.objects.bulk_update([evento], ["descricao"])


def test_historico_e_imutavel_no_banco_de_dados(aprovada_a):
    """Mesmo contornando o ORM, o gatilho do PostgreSQL rejeita UPDATE e DELETE."""
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("UPDATE liberacoes_historicoevento SET descricao = 'adulterado'")
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("DELETE FROM liberacoes_historicoevento")
    with pytest.raises(DatabaseError), transaction.atomic():
        HistoricoEvento._base_manager.filter(pk=aprovada_a.eventos.first().pk).update(descricao="x")
    assert aprovada_a.eventos.exclude(descricao="adulterado").count() == aprovada_a.eventos.count()


def test_nao_existe_rota_para_alterar_o_historico(logar, equipe_a, aprovada_a):
    url = reverse("solicitacao_detalhe", args=[aprovada_a.pk])
    for usuario in equipe_a.values():
        assert logar(usuario).post(url, {"descricao": "x"}).status_code in (403, 404, 405)
    assert not any(
        "historico" in str(p.pattern) for p in __import__("liberacoes.urls", fromlist=["x"]).urlpatterns
    )


def test_historico_nao_e_editavel_no_admin(db):
    from accounts.admin_site import tcc_admin_site

    modelo_admin = tcc_admin_site._registry[HistoricoEvento]
    assert not modelo_admin.has_add_permission(None)
    assert not modelo_admin.has_change_permission(None)
    assert not modelo_admin.has_delete_permission(None)
