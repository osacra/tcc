# Plataforma de liberação de motoristas (TCC — ADS / IFSP Guarulhos)

Primeira entrega funcional (≈ 20 %) do projeto descrito no Relatório Técnico: plataforma web
multiorganização para controlar a **liberação de motoristas** com foco em segurança patrimonial,
com avaliação automática inicial, análise manual, revogação e trilha de auditoria.

Stack: Python, Django 5.2 (ORM, templates, autenticação nativa com usuário customizado),
PostgreSQL, Bootstrap 5 (CDN), pytest + pytest-django, coverage, Ruff e Black, Docker Compose.
**Somente dados fictícios** são usados (CPF/CNPJ de teste gerados com dígitos verificadores válidos).

## O que está implementado

| Módulo | Situação |
|---|---|
| Fundação: organizações, usuários vinculados a organização, login/logout, RBAC, isolamento por organização no backend | ✔ |
| Cadastros: Transportadora, Motorista, Veículo, Vínculo motorista–transportadora (com vigência) | ✔ |
| Solicitação de liberação (preencher → revisar → enviar) com validações | ✔ |
| Avaliação automática inicial (5 regras fixas) com justificativa por regra | ✔ |
| Análise manual (aprovar/reprovar com justificativa obrigatória) | ✔ |
| Histórico/auditoria imutável (aplicação **e** gatilho no PostgreSQL) | ✔ |
| Revogação de liberação vigente (justificativa obrigatória) | ✔ |
| Expiração de liberações vencidas (transição automática, registrada no histórico) | ✔ |
| Integridade multiempresa no modelo e em gatilhos PostgreSQL | ✔ |
| Admin técnico restrito ao Superadministrador e proteção do último Administrador ativo | ✔ |

Papéis: Solicitante, Analista de Segurança, Gestor, Administrador da organização e
Superadministrador da plataforma (sem organização; cria organizações).

## Como executar

### Opção 1 — Docker Compose
```bash
docker compose up --build          # sobe PostgreSQL e a aplicação (migrações automáticas)
docker compose exec web python manage.py seed_demo          # dados fictícios (opcional)
docker compose exec web python manage.py createsuperuser    # superadministrador
```
Acesse http://localhost:8000. *(O `docker-compose.yml` não pôde ser executado no ambiente em que
o código foi desenvolvido, que não tinha Docker; o projeto foi verificado com PostgreSQL local.)*

### Opção 2 — Local
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env               # e exporte as variáveis (ou defina-as no shell)
# PostgreSQL rodando, com o banco/usuário informados nas variáveis abaixo
python manage.py migrate
python manage.py expirar_liberacoes  # rotina operacional idempotente (opcional)
python manage.py seed_demo         # opcional: organização de demonstração
python manage.py createsuperuser   # cria o Superadministrador (papel definido automaticamente)
python manage.py runserver
```

### Variáveis de ambiente
| Variável | Padrão | Função |
|---|---|---|
| `DJANGO_ENV` | `development` | use `production` fora do desenvolvimento |
| `DJANGO_SECRET_KEY` | chave local | obrigatória em produção |
| `DJANGO_DEBUG` | `1` em desenvolvimento | modo debug |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | hosts permitidos |
| `DJANGO_COOKIES_SEGUROS` | `0` | cookies `Secure` (usar `1` com HTTPS) |
| `POSTGRES_DB` / `_USER` / `_PASSWORD` | `liberacao` | credenciais do banco |
| `POSTGRES_HOST` / `POSTGRES_PORT` | `127.0.0.1` / `5432` | endereço do banco |

### Migrações e primeiro superusuário
`python manage.py migrate` aplica as migrações. Além do gatilho de imutabilidade do histórico,
as migrations criam gatilhos para coerência multiempresa, liberação somente após aprovação e
preservação do último administrador ativo. `python manage.py createsuperuser` cria o **Superadministrador**: ele não
pertence a nenhuma organização e usa a tela **Organizações** para criar cada organização junto com o
seu primeiro Administrador.

### Demonstração (`seed_demo`)
Cria a "Organização Demonstração" com os usuários `demo_administrador`, `demo_solicitante`,
`demo_analista` e `demo_gestor` (senha `demo-Senha-2026`, alterável com `--senha`) e quatro motoristas
que exercitam cada resultado: aprovação automática, pendência de análise (CNH vencida), reprovação
por falta de vínculo e reprovação por motorista inativo. Use o veículo **DEM1A11** (ativo, da
transportadora com vínculo) nas solicitações.

## Regras de avaliação implementadas
Funções determinísticas em `liberacoes/regras.py`, sem motor genérico e sem configuração pela
interface (o catálogo configurável é o Incremento 3). Cada avaliação grava regra, resultado,
ação aplicada e justificativa (`AvaliacaoRegra`) e um evento no histórico.

| Código | Regra | Se não atendida |
|---|---|---|
| R01 | Motorista cadastrado na organização e ativo | reprova |
| R02 | Vínculo motorista–transportadora vigente durante **toda** a janela de acesso | reprova |
| R03 | Veículo cadastrado, ativo e pertencente à transportadora informada | reprova |
| R04 | Finalidade preenchida e janela válida (fim > início e ainda não encerrada) | reprova |
| **R05 (demonstrativa)** | Validade da CNH cobre toda a janela de acesso | **exige análise manual** |

Precedência (conforme o relatório): reprovação > análise manual > aprovação. **R05 é demonstrativa**:
existe para demonstrar o caminho de "pendência de análise manual" com um critério documental do
catálogo do relatório; não reproduz regra de nenhuma organização real.

## Estados
O relatório lista dez estados. No código eles se dividem entre as duas entidades:
- `SolicitacaoLiberacao`: Rascunho → Solicitada → Em avaliação → (Aprovada | Reprovada | Pendente de análise); Pendente → (Aprovada | Reprovada).
- `Liberacao` (criada na aprovação, já Vigente): Vigente → (Expirada | Revogada | Utilizada).

Transições inválidas lançam `TransicaoInvalida` (`liberacoes/estados.py`). Uma solicitação reprovada
nunca gera `Liberacao`. A validade da liberação é a janela de acesso informada.

## Arquitetura
- `accounts`: `Organizacao`, `Usuario` (modelo customizado, papel + organização, restrição de banco), RBAC (`PapelRequeridoMixin`), gestão de organizações/usuários.
- `cadastros`: entidades mestres e validadores (CPF/CNPJ/CNH/placa).
- `liberacoes`: modelos do processo, máquina de estados, regras, **serviços transacionais** (`services.py`), formulários, views.
- **Isolamento (RNF01):** todas as tabelas de negócio herdam `ModeloDaOrganizacao` (coluna `organizacao` + `objects.da_organizacao(org)`); as views usam `OrganizacaoQuerysetMixin`, então um registro de outra organização resulta em **404** na leitura, edição ou exclusão; os serviços revalidam a organização; gatilhos PostgreSQL rejeitam relações cross-tenant.
- **Auditoria (RNF03):** `HistoricoEvento` recusa `save` de registro existente, `delete`, `update` e `bulk_update` na aplicação; além disso, gatilhos do PostgreSQL rejeitam `UPDATE`/`DELETE` mesmo fora do ORM.
- Segurança: hash PBKDF2, CSRF, autoescape de templates (XSS), ORM parametrizado, cookies HttpOnly, `X-Frame-Options: DENY`, CPF mascarado em listagens.
- Transações: solicitação + avaliações + decisão + liberação + histórico são gravados em `transaction.atomic` (com `select_for_update` nas avaliações, decisões, revogações e expiração).

## Testes e qualidade
```bash
python -m pytest                                  # PostgreSQL; cria o banco test_*
make coverage                                    # exige cobertura mínima de 90 %
make quality
python -m ruff check . && python -m black --check .
```
Última execução: a suíte e os quality gates devem ser executados no PostgreSQL local ou via Compose;
o quality gate exige cobertura total mínima de 90 %. Além dos testes, o fluxo foi percorrido
contra o servidor HTTP real (login com CSRF, os três resultados da avaliação, decisão, revogação, histórico).

## Decisões de projeto a confirmar
1. **Vínculo ausente/vencido e cadastros inativos não bloqueiam o formulário**: a solicitação é registrada
   e **reprovada automaticamente com justificativa** (R01–R03), o que dá rastreabilidade e demonstra o
   resultado "reprovação automática". O formulário bloqueia apenas inconsistências estruturais
   (entidade inexistente ou de outra organização, veículo de outra transportadora, datas inválidas).
2. `Veiculo` pertence a **uma** `Transportadora` (obrigatória). `Motorista` e `Veiculo` têm `ativo`;
   `Transportadora` tem `ativa`.
3. Cadastros são gerenciados pelo **Administrador**; Solicitante, Analista e Gestor consultam o que o fluxo exige.
4. R05 (CNH) é demonstrativa e leva a análise manual.

## Fora desta entrega (próximos incrementos)
Catálogo de regras **configurável** pelo Administrador (RF10), regras de histórico/frequência/horário,
`Ocorrencia` (RF11), painel de indicadores (RF13), exportação CSV (RF14), tela de registro de entrada/saída
(o serviço transacional do estado *Utilizada* está disponível), política de retenção/anonimização
(RNF04 parcial: minimização e mascaramento implementados) e avaliação com especialista.

## Limitações conhecidas
- `docker-compose.yml` não foi executado (sem Docker no ambiente de desenvolvimento).
- Bootstrap é carregado de CDN (precisa de internet no navegador).
- A expiração pode ser executada sob demanda nas telas relevantes ou pelo comando idempotente
  `python manage.py expirar_liberacoes`, que deve ser agendado pelo ambiente operacional.
- Sem testes de interface em navegador; a interface foi verificada por HTTP e por testes de view.
