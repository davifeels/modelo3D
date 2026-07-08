# Refatoração — Landing, Compra de Acesso e Área Administrativa (2026-07-07)

Reestruturação do ZefiroSplit em **3 áreas**: Landing Page (pública), Compra de
Acesso (módulo próprio) e Área Administrativa (autenticação separada). O acesso
ao sistema passa a existir **somente via compra** — não há criação manual de
conta em lugar nenhum.

## Fluxo final

```
Visitante
  → Landing Page (/)
  → Comprar Acesso (/comprar)          [nome, e-mail, telefone + plano]
  → Pagamento                          [gateway real OU aprovação simulada]
  → Registro AUTOMÁTICO do cliente     [senha temporária + código de acesso]
  → Cliente aparece no painel (/admin)
  → Admin envia credenciais            [e-mail com login/senha/código/link]
  → Cliente entra em /login            [e-mail + senha; sem "criar conta"]
```

## Áreas e rotas (frontend)

| Rota | Área | Acesso |
|---|---|---|
| `/` | Landing page (hero, benefícios, funcionalidades, planos, FAQ, depoimentos, rodapé, CTA "Comprar Acesso") | pública; logado cai direto no app |
| `/comprar` | Compra de acesso: produtos, preços, formulário (nome/e-mail/telefone) | pública |
| `/login` | Login (e-mail, senha, Entrar, Esqueci minha senha — **sem** registro) | pública |
| `/admin` | Painel administrativo (login PRÓPRIO, tabela de clientes, busca, senhas, envio de acesso, histórico) | admin_users |
| `/planos`, `/conta` | Paywall/área do cliente logado | cliente autenticado |
| app (raiz logada) | Fatiador 3D | cliente com assinatura ativa |

Componentes novos: `LandingPage.jsx`, `PurchasePage.jsx`, `AdminPage.jsx`;
`LoginPage.jsx` reescrito sem cadastro. `CheckoutPage.jsx` foi removido (a
compra saiu do app principal).

## Backend — endpoints novos/alterados

- `POST /api/purchase` (público, rate-limited): valida plano/período/e-mail/
  telefone, cria o cliente automaticamente (senha temporária + código
  `ZS-XXXX-XXXX`), registra a compra e ativa a assinatura. E-mail repetido =
  **renovação** (sem novas credenciais). Com `ZS_DEV_BILLING=1` a resposta
  inclui `dev_credentials` (uso exclusivo de teste).
- `GET /api/purchase/products` (público): catálogo.
- `POST /api/auth/login`: registra `last_login_at`; conta bloqueada → 403.
- `POST /api/auth/forgot-password`: gera senha temporária nova e envia por
  e-mail; resposta sempre genérica (não revela se o e-mail existe).
- `POST /api/auth/register`: **REMOVIDO** (404).
- `POST /api/admin/login`: autenticação separada (tabela `admin_users`), JWT
  com `typ=admin` e TTL de 12h. Tokens de cliente NÃO abrem o admin e
  vice-versa.
- `GET /api/admin/users?q=&field=nome|email|telefone`: tabela com nome,
  e-mail, telefone, plano, data da compra, status, código de acesso, senha
  temporária, último login e data do último envio de acesso.
- `POST /api/admin/users/{id}/password`: define senha específica ou gera
  temporária (reset).
- `POST /api/admin/users/{id}/send-access`: envia e-mail com login, senha,
  código de acesso e link do sistema (`APP_URL`); registra em `email_logs`.
- `POST /api/admin/users/{id}/status`: ativo/bloqueado.
- `GET /api/admin/users/{id}/history`: compras, e-mails, último login, status.
- `GET /api/admin/logs`: auditoria das ações administrativas.

## Banco de dados

Tabelas novas: `purchases` (user_id, plano, período, valor_cents,
status_pagamento, data_compra), `email_logs` (user_id, destinatário, assunto,
status, data_envio), `admin_users` (nome, email, senha hash, role),
`admin_logs` (auditoria). `users` ganhou: telefone, codigo_acesso, status,
plano, temp_password, last_login_at, updated_at.

Migração: `web/backend/migrations.py` roda no startup (idempotente —
`ADD COLUMN IF NOT EXISTS` no Postgres, try/except no SQLite) após o
`create_all`. Bancos existentes são migrados automaticamente.

> **Decisão consciente:** `users.temp_password` guarda a senha temporária EM
> CLARO enquanto vigente, porque o painel exibe a coluna "Senha temporária" e
> o botão "Enviar acesso" precisa incluí-la no e-mail (requisito). O login
> valida SEMPRE contra `password_hash` (bcrypt). Quando existir o fluxo de
> "trocar senha" do cliente, a coluna deve ser limpa na troca.

## Segurança

- **bcrypt** para hashes novos; hashes PBKDF2 legados continuam verificáveis
  (migração transparente no próximo reset).
- **JWT HS256** com `typ` (`user`/`admin`) — controle de permissões dos dois
  lados; admin com TTL menor (12h).
- **Rate limit** em memória por IP+rota: login 15/min, compra 10/min,
  esqueci-senha 5/min, login admin 10/min (com `ZS_DEV_BILLING=1` os limites
  são ×100 para a suíte de testes).
- **Proteção de rotas**: malha/export/billing exigem cliente; `/api/admin/*`
  exige admin. Validação de formulários no backend (Pydantic + regex de
  e-mail/telefone) e no frontend (required/minLength).
- **Logs administrativos** (`admin_logs`) + **logs de e-mail** (`email_logs`).

## E-mail

`web/backend/emailer.py`: com `SMTP_HOST` configurado envia de verdade
(STARTTLS, credenciais via `SMTP_*`); sem SMTP o envio é **simulado** e
registrado em `email_logs` com status `simulado` — o fluxo completo do painel
funciona em dev/homologação. `APP_URL` define o link do sistema no e-mail.

## Pagamento

`gateway.py` continua sendo o ponto único de integração (Stripe/Mercado
Pago/…). Com gateway configurado, `POST /api/purchase` devolve `checkout_url`
e grava a compra como `pendente` (webhook ativa depois). **Sem gateway** a
compra é aprovada como `aprovado_simulado` e o acesso ativa na hora — troque
isso ao plugar o gateway real.

## Seed do administrador

`bootstrap.py` (startup) lê `ADMIN_EMAIL`/`ADMIN_PASSWORD` e garante duas
contas com as mesmas credenciais: **AdminUser** (painel `/admin`, role
`owner`) e **User** cliente com Pro ativo (para usar o app). Trocar a senha =
editar o env e reiniciar.

## Testes

- `tests/test_purchase.py` — compra cria conta, renovação, validações, fluxo
  compra→painel.
- `tests/test_admin.py` — login separado, listagem/busca, senhas, envio de
  acesso com log, bloqueio, histórico, separação de permissões.
- `tests/test_auth.py` — reescrito: sem registro (404), login, esqueci-senha,
  proteção de endpoints.
- `tests/test_e2e_auth.py` — landing, compra pela UI, login sem "criar conta",
  paywall, conta, painel admin no navegador.
- `tests/apiauth.py` — usuários de teste agora nascem via compra
  (`dev_credentials`, requer `ZS_DEV_BILLING=1`).
