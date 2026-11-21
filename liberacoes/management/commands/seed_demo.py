"""Popula dados fictícios, seguros e repetíveis para demonstração do fluxo completo."""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import Organizacao, Papel, Usuario
from cadastros.models import Motorista, Transportadora, Veiculo, VinculoMotoristaTransportadora
from cadastros.validators import gerar_cnpj_ficticio, gerar_cpf_ficticio
from liberacoes import services
from liberacoes.models import Liberacao, SolicitacaoLiberacao
from liberacoes.regras import garantir_regras_iniciais

SENHA_PADRAO = "demo-Senha-2026"
NOME_ORGANIZACAO = "Organização Demonstração"


class Command(BaseCommand):
    help = "Cria ou atualiza controladamente dados fictícios da demonstração, sem duplicações."

    def add_arguments(self, parser):
        parser.add_argument(
            "--senha", default=SENHA_PADRAO, help="Senha apenas para usuários novos de demonstração."
        )

    def _usuario(self, org, papel, senha):
        username = f"demo_{papel}"
        usuario, criado = Usuario.objects.get_or_create(
            username=username,
            defaults={
                "password": "",
                "first_name": {
                    Papel.ADMINISTRADOR: "Marina",
                    Papel.SOLICITANTE: "Rafael",
                    Papel.ANALISTA: "Camila",
                    Papel.GESTOR: "Eduardo",
                }[papel],
                "last_name": {
                    Papel.ADMINISTRADOR: "Almeida",
                    Papel.SOLICITANTE: "Nogueira",
                    Papel.ANALISTA: "Ferreira",
                    Papel.GESTOR: "Barbosa",
                }[papel],
                "organizacao": org,
                "papel": papel,
                "is_active": True,
            },
        )
        if criado:
            usuario.set_password(senha)
            usuario.save(update_fields=["password"])
        elif usuario.organizacao_id != org.pk:
            raise CommandError(
                f"O usuário {username} já pertence a outra organização; seed abortado por segurança."
            )
        return usuario

    def _solicitacao(self, org, solicitante, dados, marcador):
        existente = SolicitacaoLiberacao.objects.filter(organizacao=org, finalidade=marcador).first()
        if existente:
            return existente, False
        return services.solicitar_liberacao(usuario=solicitante, **dados), True

    @transaction.atomic
    def handle(self, *args, **opcoes):
        senha = opcoes["senha"]
        hoje = timezone.localdate()
        agora = timezone.now()
        org, _ = Organizacao.objects.get_or_create(nome=NOME_ORGANIZACAO, defaults={"ativa": True})
        usuarios = {
            papel: self._usuario(org, papel, senha)
            for papel in (Papel.ADMINISTRADOR, Papel.SOLICITANTE, Papel.ANALISTA, Papel.GESTOR)
        }
        transportadoras = {}
        for nome, base in (("Rota Norte Logística", 301), ("Expresso Vale Transporte", 302)):
            transportadoras[nome], _ = Transportadora.objects.get_or_create(
                organizacao=org, nome=nome, defaults={"cnpj": gerar_cnpj_ficticio(base), "ativa": True}
            )
        rota_norte = transportadoras["Rota Norte Logística"]
        expresso_vale = transportadoras["Expresso Vale Transporte"]

        def motorista(nome, base, validade, ativo=True):
            return Motorista.objects.get_or_create(
                organizacao=org,
                cpf=gerar_cpf_ficticio(base),
                defaults={
                    "nome": nome,
                    "numero_cnh": str(30000000000 + base),
                    "categoria_cnh": "E",
                    "validade_cnh": validade,
                    "telefone": "(11) 98888-0000",
                    "ativo": ativo,
                },
            )[0]

        motoristas = {
            "aprovado": motorista("Mariana Costa", 301, hoje + timedelta(days=500)),
            "pendente": motorista("João Pedro Ribeiro", 302, hoje - timedelta(days=1)),
            "sem_vinculo": motorista("Beatriz Martins", 303, hoje + timedelta(days=500)),
            "inativo": motorista("Lucas Andrade", 304, hoje + timedelta(days=500), False),
        }
        for mot, transp in (
            (motoristas["aprovado"], rota_norte),
            (motoristas["pendente"], rota_norte),
            (motoristas["inativo"], rota_norte),
        ):
            VinculoMotoristaTransportadora.objects.get_or_create(
                organizacao=org, motorista=mot, transportadora=transp, inicio=hoje - timedelta(days=90)
            )

        veiculos = {}
        for placa, transp, ativo in (
            ("RNL3A21", rota_norte, True),
            ("RNL4B32", rota_norte, False),
            ("EVT5C43", expresso_vale, True),
        ):
            veiculos[placa], _ = Veiculo.objects.get_or_create(
                organizacao=org, placa=placa, defaults={"transportadora": transp, "ativo": ativo}
            )

        garantir_regras_iniciais(org)
        inicio = agora + timedelta(hours=2)
        fim = inicio + timedelta(hours=4)
        comum = {
            "veiculo": veiculos["RNL3A21"],
            "transportadora": rota_norte,
            "finalidade": "",
            "janela_inicio": inicio,
            "janela_fim": fim,
        }
        cenarios = [
            (
                "Solicitação demonstrativa · aprovação automática",
                motoristas["aprovado"],
            ),
            (
                "Solicitação demonstrativa · pendência de análise",
                motoristas["pendente"],
            ),
            (
                "Solicitação demonstrativa · reprovação por vínculo",
                motoristas["sem_vinculo"],
            ),
            (
                "Solicitação demonstrativa · motorista inativo",
                motoristas["inativo"],
            ),
        ]
        criadas = 0
        for marcador, mot in cenarios:
            dados = {**comum, "motorista": mot, "finalidade": marcador}
            _, criada = self._solicitacao(org, usuarios[Papel.SOLICITANTE], dados, marcador)
            criadas += criada

        # Três liberações em estados operacionais diferentes, criadas somente na primeira execução.
        if not SolicitacaoLiberacao.objects.filter(
            organizacao=org, finalidade="Solicitação demonstrativa · revogação"
        ).exists():
            solic = services.solicitar_liberacao(
                usuario=usuarios[Papel.SOLICITANTE],
                motorista=motoristas["aprovado"],
                veiculo=veiculos["RNL3A21"],
                transportadora=rota_norte,
                finalidade="Solicitação demonstrativa · revogação",
                janela_inicio=inicio,
                janela_fim=fim,
            )
            services.revogar_liberacao(
                liberacao_id=solic.liberacao.pk,
                usuario=usuarios[Papel.ANALISTA],
                justificativa="Revogação registrada para demonstrar resposta a uma ocorrência operacional.",
            )
        if not SolicitacaoLiberacao.objects.filter(
            organizacao=org, finalidade="Solicitação demonstrativa · utilização"
        ).exists():
            solic = services.solicitar_liberacao(
                usuario=usuarios[Papel.SOLICITANTE],
                motorista=motoristas["aprovado"],
                veiculo=veiculos["RNL3A21"],
                transportadora=rota_norte,
                finalidade="Solicitação demonstrativa · utilização",
                janela_inicio=inicio,
                janela_fim=fim,
            )
            services.utilizar_liberacao(liberacao_id=solic.liberacao.pk, organizacao=org)
        if not SolicitacaoLiberacao.objects.filter(
            organizacao=org, finalidade="Solicitação demonstrativa · expiração"
        ).exists():
            solic = services.solicitar_liberacao(
                usuario=usuarios[Papel.SOLICITANTE],
                motorista=motoristas["aprovado"],
                veiculo=veiculos["RNL3A21"],
                transportadora=rota_norte,
                finalidade="Solicitação demonstrativa · expiração",
                janela_inicio=inicio,
                janela_fim=fim,
            )
            Liberacao.objects.filter(pk=solic.liberacao.pk).update(
                valida_de=agora - timedelta(minutes=2), valida_ate=agora - timedelta(minutes=1)
            )
            services.expirar_liberacoes_vencidas(org, agora=agora)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed idempotente concluído para '{NOME_ORGANIZACAO}'. Solicitações novas: {criadas}."
            )
        )
        self.stdout.write(
            "Usuários: demo_administrador, demo_solicitante, demo_analista, demo_gestor "
            f"(senha aplicada somente em contas novas: {senha})"
        )
