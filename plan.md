# Plano de reformulação do MVP

## Diagnóstico

O MVP já possui a arquitetura central correta: entidades de negócio isoladas por `Organizacao`, RBAC aplicado no backend, serviços transacionais para mudanças de estado, regras explicáveis, histórico imutável e validações de compatibilidade entre veículo e transportadora. O principal débito atual está na experiência: a navegação é extensa, os dashboards são apenas contadores, as listas não orientam a próxima ação e o seed não é repetível nem demonstra o fluxo completo.

A relação motorista–transportadora permanecerá temporal em `VinculoMotoristaTransportadora`. Não será criada uma FK direta em `Motorista`, pois isso eliminaria vínculos históricos, transferências e vigências. A compatibilidade operacional continuará sendo validada pela janela da solicitação e pela regra R02; o formulário filtra por organização e o serviço revalida tudo no servidor.

## Organização proposta

- `accounts`: identidade, organizações, papéis, dashboard e gestão de usuários.
- `cadastros`: transportadoras, motoristas, veículos e vínculos temporais.
- `liberacoes`: solicitações, regras, avaliações, liberações, histórico, serviços e seed demonstrativo.
- `templates/`: layout, navegação por papel, componentes de formulário, cartões, tabelas e fluxo de solicitação.
- `tests/`: contratos de isolamento, compatibilidade, estados, seed, permissões e fluxo ponta a ponta.

## Experiência por perfil

- **Superadministrador:** visão de organizações e acesso técnico, sem exposição de operações de uma organização.
- **Administrador:** visão de saúde dos cadastros e ações de manutenção de usuários, transportadoras, motoristas, veículos e vínculos.
- **Solicitante:** ação primária para criar uma solicitação, acompanhamento das próprias solicitações e estados legíveis.
- **Analista de Segurança:** fila priorizada de pendências, decisões justificadas, liberações vigentes e revogação.
- **Gestor:** visão consolidada de solicitações e liberações, sem ações de cadastro ou decisão indevidas.

## Integridade e segurança

Todos os querysets de relacionamento serão limitados à organização do usuário. O serviço continuará rejeitando registros de outra organização, veículo de transportadora incompatível, janela inválida e configuração sem regras ativas. A ausência de vínculo, motorista inativo ou veículo inativo permanece uma reprovação automática explicável, preservando rastreabilidade e o cenário demonstrativo.

## Estratégia de seed

`seed_demo` usará chaves naturais estáveis para organização, usuários, transportadoras, motoristas, veículos, vínculos e solicitações. O comando será seguro para repetição: cria o que falta, preserva contas e senhas existentes e não duplica solicitações demonstrativas. Os cenários cobrirão aprovação automática, pendência manual, reprovação por vínculo, reprovação por inatividade e registros de liberação em estados vigentes, revogada, utilizada e expirada.

## Design

### Estilos considerados

- **Painel operacional editorial** (0,06): alta clareza, hierarquia tipográfica e foco em filas de trabalho.
- **Admin SaaS neutro** (0,07): cartões compactos, navegação lateral e densidade informacional.
- **Console institucional** (0,04): contraste forte, tabelas técnicas e microcopy objetiva.

Foi escolhido o **Painel operacional editorial**.

- **Movimento:** dashboard de operação segura, com cabeçalho contextual, ação primária evidente e conteúdo em trilhas de decisão.
- **Princípios:** clareza antes de decoração; estados sempre visíveis; uma ação principal por tela; densidade responsiva.
- **Cores:** azul-petróleo para confiança e navegação, verde apenas para sucesso, âmbar para análise e vermelho para bloqueios; fundo cinza-azulado para separar superfície e conteúdo.
- **Layout:** cabeçalho compacto e blocos assimétricos de resumo, fila e atalhos; tabelas entram depois do contexto e não como primeira coisa da página.
- **Assinaturas:** marcador vertical de estado, cartões com borda superior de prioridade e microcopy de próxima ação.
- **Interação:** formulários orientam antes de submeter; erros aparecem junto ao campo; ações destrutivas pedem justificativa e ficam visualmente separadas.
- **Animação:** somente transições curtas de colapso e foco; sem movimento decorativo em fluxo operacional.
- **Tipografia:** `Inter`/system sans para interface, títulos em peso 650, números em peso 700 e textos auxiliares curtos.
- **Essência:** liberação segura de motoristas com decisão rastreável; profissional, direto e confiável.
- **Tom:** “A próxima decisão está clara.” e “Cada liberação tem contexto, regra e histórico.”
- **Marca:** wordmark textual com símbolo de passagem formado por duas barras verticais e um ponto de verificação.
- **Cor proprietária:** azul-petróleo `#0f4c5c`.
