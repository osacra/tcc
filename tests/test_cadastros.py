"""Cadastros essenciais: persistência, validações e vínculo com período de vigência."""

from datetime import date, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from cadastros.models import Motorista, Transportadora, Veiculo, VinculoMotoristaTransportadora
from cadastros.validators import (
    gerar_cnpj_ficticio,
    gerar_cpf_ficticio,
    normalizar_placa,
    validar_cnpj,
    validar_cpf,
    validar_placa,
)
from liberacoes import services

from . import factories as f


def test_cpf_e_cnpj_ficticios_sao_validos():
    for n in (1, 2, 12345, 987654321):
        validar_cpf(gerar_cpf_ficticio(n))
        validar_cnpj(gerar_cnpj_ficticio(n))


@pytest.mark.parametrize("cpf", ["", "123", "11111111111", "12345678900", "abcdefghijk"])
def test_cpf_invalido(cpf):
    with pytest.raises(ValidationError):
        validar_cpf(cpf)


def test_cnpj_invalido():
    for valor in ("", "00000000000000", "12345678000100"):
        with pytest.raises(ValidationError):
            validar_cnpj(valor)


def test_placas():
    for ok in ("ABC1234", "ABC1D23"):
        validar_placa(ok)
    for ruim in ("AB12345", "ABCD123", "", "ABC12"):
        with pytest.raises(ValidationError):
            validar_placa(ruim)
    assert normalizar_placa("abc-1d23") == "ABC1D23"


def test_cria_transportadora(logar, admin_a, org_a):
    resposta = logar(admin_a).post(
        reverse("transportadora_novo"),
        {"nome": "  Rápido Fictício  ", "cnpj": gerar_cnpj_ficticio(7), "ativa": "on"},
    )
    assert resposta.status_code == 302
    t = Transportadora.objects.get(nome="Rápido Fictício")
    assert t.organizacao == org_a and t.ativa


def test_rejeita_cnpj_invalido(logar, admin_a):
    resposta = logar(admin_a).post(reverse("transportadora_novo"), {"nome": "X", "cnpj": "12345678000100"})
    assert resposta.status_code == 200
    assert not Transportadora.objects.filter(nome="X").exists()


def test_cria_motorista_com_cpf_formatado_e_valida_unicidade_por_organizacao(logar, admin_a, org_a, org_b):
    cpf = gerar_cpf_ficticio(555)
    cpf_fmt = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
    dados = {
        "nome": "João Fictício",
        "cpf": cpf_fmt,
        "numero_cnh": "12345678901",
        "categoria_cnh": "E",
        "validade_cnh": (date.today() + timedelta(days=100)).isoformat(),
        "telefone": "",
        "ativo": "on",
    }
    client = logar(admin_a)
    assert client.post(reverse("motorista_novo"), dados).status_code == 302
    assert Motorista.objects.get(nome="João Fictício").cpf == cpf  # armazenado só com dígitos
    # duplicado na mesma organização
    assert client.post(reverse("motorista_novo"), dados).status_code == 200
    assert Motorista.objects.filter(cpf=cpf).count() == 1
    # o mesmo CPF pode existir em outra organização
    Motorista.objects.create(
        organizacao=org_b,
        nome="Outro",
        cpf=cpf,
        numero_cnh="12345678901",
        categoria_cnh="B",
        validade_cnh=date.today(),
    )
    assert Motorista.objects.filter(cpf=cpf).count() == 2


def test_rejeita_motorista_invalido(logar, admin_a):
    dados = {
        "nome": "Z",
        "cpf": "111.111.111-11",
        "numero_cnh": "123",
        "categoria_cnh": "E",
        "validade_cnh": "2030-01-01",
        "ativo": "on",
    }
    resposta = logar(admin_a).post(reverse("motorista_novo"), dados)
    assert resposta.status_code == 200
    assert not Motorista.objects.filter(nome="Z").exists()


def test_cpf_aparece_mascarado_na_listagem(logar, admin_a, cenario_a):
    cpf = cenario_a["motorista"].cpf
    html = logar(admin_a).get(reverse("motorista_lista")).content.decode()
    assert f"***.{cpf[3:6]}.{cpf[6:9]}-**" in html
    assert cpf not in html


def test_cria_veiculo_normaliza_placa(logar, admin_a, cenario_a):
    resposta = logar(admin_a).post(
        reverse("veiculo_novo"),
        {"placa": "xyz-9a88", "transportadora": cenario_a["transportadora"].pk, "ativo": "on"},
    )
    assert resposta.status_code == 302
    assert Veiculo.objects.filter(placa="XYZ9A88").exists()


def test_veiculo_nao_aceita_transportadora_de_outra_organizacao(logar, admin_a, cenario_b):
    resposta = logar(admin_a).post(
        reverse("veiculo_novo"), {"placa": "XYZ9A88", "transportadora": cenario_b["transportadora"].pk}
    )
    assert resposta.status_code == 200
    assert not Veiculo.objects.filter(placa="XYZ9A88").exists()


def test_cria_vinculo_com_vigencia(logar, admin_a, org_a):
    c = f.criar_cenario(org_a, vinculo=False)
    resposta = logar(admin_a).post(
        reverse("vinculo_novo"),
        {
            "motorista": c["motorista"].pk,
            "transportadora": c["transportadora"].pk,
            "inicio": "2026-01-01",
            "fim": "2026-12-31",
        },
    )
    assert resposta.status_code == 302
    v = VinculoMotoristaTransportadora.objects.get(motorista=c["motorista"])
    assert v.inicio == date(2026, 1, 1) and v.fim == date(2026, 12, 31)


def test_vinculo_com_fim_anterior_ao_inicio_e_rejeitado(logar, admin_a, org_a):
    c = f.criar_cenario(org_a, vinculo=False)
    resposta = logar(admin_a).post(
        reverse("vinculo_novo"),
        {
            "motorista": c["motorista"].pk,
            "transportadora": c["transportadora"].pk,
            "inicio": "2026-06-01",
            "fim": "2026-01-01",
        },
    )
    assert resposta.status_code == 200
    assert not VinculoMotoristaTransportadora.objects.filter(motorista=c["motorista"]).exists()


def test_vinculo_sem_fim_e_vigente_indefinidamente(cenario_a, org_a):
    hoje = timezone.localdate()
    qs = VinculoMotoristaTransportadora.objects.da_organizacao(org_a)
    assert qs.cobrindo_periodo(hoje, hoje + timedelta(days=3650)).exists()


def test_edita_cadastro(logar, admin_a, cenario_a):
    t = cenario_a["transportadora"]
    logar(admin_a).post(
        reverse("transportadora_editar", args=[t.pk]), {"nome": "Renomeada", "cnpj": "", "ativa": "on"}
    )
    t.refresh_from_db()
    assert t.nome == "Renomeada"


def test_exclui_cadastro_sem_uso(logar, admin_a, org_a):
    c = f.criar_cenario(org_a, vinculo=False)
    resposta = logar(admin_a).post(reverse("veiculo_excluir", args=[c["veiculo"].pk]))
    assert resposta.status_code == 302
    assert not Veiculo.objects.filter(pk=c["veiculo"].pk).exists()


def test_nao_exclui_cadastro_em_uso(logar, admin_a, solicitante_a, cenario_a):
    services.solicitar_liberacao(usuario=solicitante_a, **f.dados_solicitacao(cenario_a))
    m = cenario_a["motorista"]
    resposta = logar(admin_a).post(reverse("motorista_excluir", args=[m.pk]), follow=True)
    assert Motorista.objects.filter(pk=m.pk).exists()
    assert "não pode ser excluído" in resposta.content.decode()
