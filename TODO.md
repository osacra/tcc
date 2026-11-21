# TODO da reformulação

- [x] Preservar isolamento por organização, RBAC, transições, auditoria imutável e fail-closed sem regras ativas.
- [x] Entregar layout responsivo e navegação contextual aos cinco papéis, sem expor ações não autorizadas.
- [x] Transformar o dashboard em painel operacional com contexto, próximos passos e indicadores por perfil.
- [x] Melhorar listagens e formulários com estados, filtros, mensagens, empty states e orientação de próxima ação.
- [x] Garantir que relacionamentos de cadastro sejam limitados à organização; validar explicitamente veículo–transportadora e vínculo motorista–transportadora na janela.
- [x] Tornar `seed_demo` idempotente, previsível e seguro, preservando senhas existentes e sem inserir dados fictícios fora da organização de demonstração.
- [x] Criar cenários de aprovação, pendência, reprovação, inatividade, revogação, utilização e expiração para demonstração.
- [x] Adicionar testes de seed idempotente, compatibilidade, isolamento, menus por perfil e fail-closed; a suíte total passou com 250 testes.
- [x] Executar migrations/check, Django check, pytest, Ruff, Black e coverage; cobertura aferida em 94%.
- [ ] Executar Docker Compose quando disponível; Docker não está instalado neste ambiente.
- [x] Fazer commits claros na branch `feat/mvp-demo-ux` e publicar somente essa branch em `origin`.
- [ ] Atualizar README com credenciais e operação do seed após a implementação.
