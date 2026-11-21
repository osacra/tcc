from django.core.management import call_command
from django.test import TestCase

from accounts.models import Organizacao, Papel, Usuario
from liberacoes.models import EstadoSolicitacao, SolicitacaoLiberacao


class SeedDemoTests(TestCase):
    def test_seed_e_idempotente_e_cria_cenarios_operacionais(self):
        call_command("seed_demo", senha="senha-inicial-demo")
        usuario = Usuario.objects.get(username="demo_solicitante")
        senha_hash = usuario.password
        primeira_contagem = SolicitacaoLiberacao.objects.filter(
            organizacao__nome="Organização Demonstração"
        ).count()

        call_command("seed_demo", senha="senha-diferente-na-repeticao")

        self.assertEqual(Organizacao.objects.filter(nome="Organização Demonstração").count(), 1)
        self.assertEqual(
            SolicitacaoLiberacao.objects.filter(organizacao__nome="Organização Demonstração").count(),
            primeira_contagem,
        )
        usuario.refresh_from_db()
        self.assertEqual(usuario.password, senha_hash)
        estados = set(
            SolicitacaoLiberacao.objects.filter(organizacao__nome="Organização Demonstração").values_list(
                "estado", flat=True
            )
        )
        self.assertIn(EstadoSolicitacao.APROVADA, estados)
        self.assertIn(EstadoSolicitacao.PENDENTE_ANALISE, estados)
        self.assertIn(EstadoSolicitacao.REPROVADA, estados)

    def test_seed_cria_usuarios_nos_papeis_da_demonstracao(self):
        call_command("seed_demo")
        self.assertEqual(
            set(Usuario.objects.filter(username__startswith="demo_").values_list("papel", flat=True)),
            {Papel.ADMINISTRADOR, Papel.SOLICITANTE, Papel.ANALISTA, Papel.GESTOR},
        )
