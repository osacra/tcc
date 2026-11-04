from django.core.management.base import BaseCommand, CommandError

from accounts.models import Organizacao
from liberacoes.services import expirar_liberacoes_vencidas


class Command(BaseCommand):
    help = "Expira liberações vigentes cuja validade terminou."

    def add_arguments(self, parser):
        parser.add_argument("--organizacao", type=int, help="ID da organização a processar")

    def handle(self, *args, **options):
        organizacao_id = options.get("organizacao")
        if organizacao_id:
            try:
                organizacoes = [Organizacao.objects.get(pk=organizacao_id)]
            except Organizacao.DoesNotExist as exc:
                raise CommandError("Organização não encontrada.") from exc
        else:
            organizacoes = Organizacao.objects.all()

        total = sum(expirar_liberacoes_vencidas(organizacao) for organizacao in organizacoes)
        self.stdout.write(self.style.SUCCESS(f"{total} liberação(ões) expirada(s)."))
