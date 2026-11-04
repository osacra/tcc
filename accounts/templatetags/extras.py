"""Filtros de template compartilhados."""

from django import template

register = template.Library()


@register.filter
def valor(objeto, atributo):
    """Obtém um atributo (ou método sem argumentos) e formata booleanos."""
    resultado = getattr(objeto, atributo, "")
    if callable(resultado):
        resultado = resultado()
    if resultado is True:
        return "Sim"
    if resultado is False:
        return "Não"
    if resultado is None:
        return "—"
    return resultado


@register.filter
def classe_estado(estado):
    """Classe Bootstrap para o selo de estado de solicitação/liberação."""
    return {
        "rascunho": "secondary",
        "solicitada": "info",
        "em_avaliacao": "info",
        "pendente_analise": "warning",
        "aprovada": "success",
        "reprovada": "danger",
        "vigente": "success",
        "expirada": "secondary",
        "revogada": "danger",
        "utilizada": "primary",
    }.get(estado, "secondary")


@register.filter
def campo_bootstrap(campo):
    """Renderiza o widget do campo com as classes do Bootstrap."""
    css = "form-control"
    if campo.errors:
        css += " is-invalid"
    return campo.as_widget(attrs={"class": css})
