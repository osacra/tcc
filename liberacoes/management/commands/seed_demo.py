"""Popula o banco com dados FICTÍCIOS para demonstração do fluxo completo."""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import Organizacao, Papel, Usuario
from cadastros.models import Motorista, Transportadora, Veiculo, VinculoMotoristaTransportadora
from cadastros.validators import gerar_cnpj_ficticio, gerar_cpf_ficticio
from liberacoes.regras import garantir_regras_iniciais

SENHA_PADRAO = "demo-Senha-2026"


class Command(BaseCommand):
    help = "Cria uma organização de demonstração, usuários de cada papel, cadastros e regras iniciais."

    def add_arguments(self, parser):
        parser.add_argument("--senha", default=SENHA_PADRAO, help="Senha dos usuários de demonstração.")

    @transaction.atomic
    def handle(self, *args, **opcoes):
        nome = "Organização Demonstração"
        if Organizacao.objects.filter(nome=nome).exists():
            raise CommandError("A organização de demonstração já existe.")
        hoje = timezone.localdate()
        org = Organizacao.objects.create(nome=nome)
        for papel in (Papel.ADMINISTRADOR, Papel.SOLICITANTE, Papel.ANALISTA, Papel.GESTOR):
            Usuario.objects.create_user(
                username=f"demo_{papel}",
                password=opcoes["senha"],
                first_name=papel.title(),
                last_name="Demo",
                organizacao=org,
                papel=papel,
            )
        transp = Transportadora.objects.create(
            organizacao=org, nome="Transportes Fictícios Ltda", cnpj=gerar_cnpj_ficticio(1)
        )
        outra = Transportadora.objects.create(
            organizacao=org, nome="Logística Exemplo S.A.", cnpj=gerar_cnpj_ficticio(2)
        )
        Veiculo.objects.create(organizacao=org, placa="DEM1A11", transportadora=transp)
        Veiculo.objects.create(organizacao=org, placa="DEM2B22", transportadora=transp, ativo=False)
        Veiculo.objects.create(organizacao=org, placa="DEM3C33", transportadora=outra)

        casos = [
            # nome, cpf-base, validade da CNH, ativo, vinculado?  -> resultado esperado
            ("Ana Aprovada (aprovação automática)", 101, hoje + timedelta(days=400), True, True),
            ("Pedro Pendente (CNH vence antes da janela)", 102, hoje - timedelta(days=2), True, True),
            ("Rita Reprovada (sem vínculo)", 103, hoje + timedelta(days=400), True, False),
            ("Ivo Inativo (motorista inativo)", 104, hoje + timedelta(days=400), False, True),
        ]
        for nome_m, base, validade, ativo, vinculado in casos:
            motorista = Motorista.objects.create(
                organizacao=org,
                nome=nome_m,
                cpf=gerar_cpf_ficticio(base),
                numero_cnh=str(20000000000 + base),
                categoria_cnh="E",
                validade_cnh=validade,
                telefone="(11) 90000-0000",
                ativo=ativo,
            )
            if vinculado:
                VinculoMotoristaTransportadora.objects.create(
                    organizacao=org,
                    motorista=motorista,
                    transportadora=transp,
                    inicio=hoje - timedelta(days=60),
                )
        garantir_regras_iniciais(org)
        self.stdout.write(self.style.SUCCESS(f"Organização '{nome}' criada com dados fictícios."))
        senha = opcoes["senha"]
        self.stdout.write(
            f"Usuários: demo_administrador, demo_solicitante, demo_analista, demo_gestor (senha: {senha})"
        )
