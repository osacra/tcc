import pytest

from accounts.models import Papel

from . import factories as f


@pytest.fixture(autouse=True)
def hash_rapido(settings, request):
    """Hash leve nos testes para acelerar a suíte (testes com @pytest.mark.hash_real usam PBKDF2)."""
    if request.node.get_closest_marker("hash_real") is None:
        settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture
def org_a(db):
    organizacao = f.criar_organizacao("Organização A")
    from liberacoes.regras import garantir_regras_iniciais

    garantir_regras_iniciais(organizacao)
    return organizacao


@pytest.fixture
def org_b(db):
    organizacao = f.criar_organizacao("Organização B")
    from liberacoes.regras import garantir_regras_iniciais

    garantir_regras_iniciais(organizacao)
    return organizacao


@pytest.fixture
def equipe_a(org_a):
    return f.criar_equipe(org_a)


@pytest.fixture
def equipe_b(org_b):
    return f.criar_equipe(org_b)


@pytest.fixture
def cenario_a(org_a):
    return f.criar_cenario(org_a)


@pytest.fixture
def cenario_b(org_b):
    return f.criar_cenario(org_b)


@pytest.fixture
def solicitante_a(equipe_a):
    return equipe_a[Papel.SOLICITANTE]


@pytest.fixture
def analista_a(equipe_a):
    return equipe_a[Papel.ANALISTA]


@pytest.fixture
def gestor_a(equipe_a):
    return equipe_a[Papel.GESTOR]


@pytest.fixture
def admin_a(equipe_a):
    return equipe_a[Papel.ADMINISTRADOR]


@pytest.fixture
def logar(client):
    def _logar(usuario):
        client.force_login(usuario)
        return client

    return _logar


@pytest.fixture
def pendente_a(solicitante_a, org_a):
    """Solicitação pendente de análise (CNH vence antes do fim da janela -> R05 não atendida)."""
    from datetime import timedelta

    from django.utils import timezone

    from liberacoes import services

    cenario = f.criar_cenario(org_a, validade_cnh=timezone.localdate())
    inicio, fim = f.janela(horas_inicio=1, duracao_horas=48)
    dados = f.dados_solicitacao(cenario, janela_inicio=inicio, janela_fim=fim + timedelta(days=1))
    return services.solicitar_liberacao(usuario=solicitante_a, **dados)


@pytest.fixture
def aprovada_a(solicitante_a, cenario_a):
    from liberacoes import services

    return services.solicitar_liberacao(usuario=solicitante_a, **f.dados_solicitacao(cenario_a))
