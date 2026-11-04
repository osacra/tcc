"""Validadores e utilitários de documentos.

As funções ``gerar_*`` produzem documentos *fictícios*, porém com dígitos verificadores válidos,
para testes e demonstrações. Nenhum dado pessoal real é utilizado no projeto.
"""

import re

from django.core.exceptions import ValidationError

CATEGORIAS_CNH = ["A", "B", "C", "D", "E", "AB", "AC", "AD", "AE"]
REGEX_PLACA = re.compile(r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$")  # modelo antigo e Mercosul


def somente_digitos(valor):
    return re.sub(r"\D", "", valor or "")


def _dv_cpf(digitos, tamanho):
    soma = sum(int(digitos[n]) * (tamanho + 1 - n) for n in range(tamanho))
    return (soma * 10) % 11 % 10


def validar_cpf(valor):
    d = somente_digitos(valor)
    if len(d) != 11 or d == d[0] * 11:
        raise ValidationError("CPF inválido.", code="cpf_invalido")
    if _dv_cpf(d, 9) != int(d[9]) or _dv_cpf(d, 10) != int(d[10]):
        raise ValidationError("CPF inválido.", code="cpf_invalido")


def _dv_cnpj(digitos):
    pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos = pesos[len(pesos) - len(digitos) :]
    resto = sum(int(x) * p for x, p in zip(digitos, pesos, strict=True)) % 11
    return 0 if resto < 2 else 11 - resto


def validar_cnpj(valor):
    d = somente_digitos(valor)
    if len(d) != 14 or d == d[0] * 14:
        raise ValidationError("CNPJ inválido.", code="cnpj_invalido")
    if _dv_cnpj(d[:12]) != int(d[12]) or _dv_cnpj(d[:13]) != int(d[13]):
        raise ValidationError("CNPJ inválido.", code="cnpj_invalido")


def validar_cnh(valor):
    if len(somente_digitos(valor)) != 11 or not valor.isdigit():
        raise ValidationError("O número da CNH deve ter 11 dígitos.", code="cnh_invalida")


def normalizar_placa(valor):
    return re.sub(r"[^A-Za-z0-9]", "", valor or "").upper()


def validar_placa(valor):
    if not REGEX_PLACA.match(valor or ""):
        raise ValidationError("Placa inválida (ex.: ABC1D23 ou ABC1234).", code="placa_invalida")


def gerar_cpf_ficticio(base9):
    """Gera um CPF fictício válido a partir de um número de até 9 dígitos."""
    d = str(int(base9) % 10**9).zfill(9)
    if d == d[0] * 9:
        d = d[:-1] + str((int(d[-1]) + 1) % 10)
    d += str(_dv_cpf(d, 9))
    d += str(_dv_cpf(d, 10))
    return d


def gerar_cnpj_ficticio(base8):
    """Gera um CNPJ fictício válido (filial 0001) a partir de um número de até 8 dígitos."""
    d = str(int(base8) % 10**8).zfill(8) + "0001"
    d += str(_dv_cnpj(d))
    d += str(_dv_cnpj(d))
    return d
