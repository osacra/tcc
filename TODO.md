# TODO da reformulação

- [x] Preservar isolamento por organização, RBAC, transições, auditoria imutável e fail-closed sem regras ativas.
- [ ] Entregar layout responsivo e navegação contextual aos cinco papéis, sem expor ações não autorizadas.
- [ ] Transformar o dashboard em painel operacional com contexto, próximos passos e indicadores por perfil.
- [ ] Melhorar listagens e formulários com estados, filtros, mensagens, empty states e orientação de próxima ação.
- [ ] Garantir que relacionamentos de cadastro sejam limitados à organização; validar explicitamente veículo–transportadora e vínculo motorista–transportadora na janela.
- [ ] Tornar `seed_demo` idempotente, previsível e seguro, preservando senhas existentes e sem inserir dados fictícios fora da organização de demonstração.
- [ ] Criar cenários de aprovação, pendência, reprovação, inatividade, revogação, utilização e expiração para demonstração.
- [ ] Adicionar testes de seed idempotente, compatibilidade, isolamento, menus por perfil e fail-closed.
- [ ] Executar migrations/check, Django check, pytest, Ruff, Black, coverage e Docker Compose quando disponíveis; registrar resultados reais.
- [ ] Fazer commits claros na branch `feat/mvp-demo-ux` e publicar somente essa branch em `origin`.
- [ ] Atualizar README com credenciais e operação do seed após a implementação.
