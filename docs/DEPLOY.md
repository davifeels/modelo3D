# Deploy na VPS (Hostinger) com domínio + subdomínios + HTTPS

Arquitetura em produção: **Caddy** (borda, HTTPS automático) → **frontend**
(nginx servindo a SPA + proxy `/api`) → **backend** (FastAPI) → **Postgres**.
A MESMA SPA atende os três subdomínios e escolhe a tela pelo hostname:

| Endereço | Tela |
|---|---|
| `seudominio.com` / `www.seudominio.com` | Site público (landing, comprar) |
| `app.seudominio.com` | App do cliente (login, fatiador, conta) |
| `admin.seudominio.com` | Painel administrativo |

## 1. DNS (painel da Hostinger)

Aponte tudo para o **IP da sua VPS** (hPanel → VPS → Overview mostra o IP):

| Tipo | Nome | Value | TTL |
|---|---|---|---|
| A | `@` | IP_DA_VPS | 14400 |
| A | `www` | IP_DA_VPS | 14400 |
| A | `app` | IP_DA_VPS | 14400 |
| A | `admin` | IP_DA_VPS | 14400 |

DNS pode levar de minutos a algumas horas para propagar.

## 2. Preparar a VPS (Ubuntu)

```bash
ssh root@IP_DA_VPS
# Docker + Compose (se ainda não tiver)
curl -fsSL https://get.docker.com | sh
# Firewall: abra 22, 80 e 443
ufw allow 22 && ufw allow 80 && ufw allow 443 && ufw --force enable
```

## 3. Subir o código e configurar segredos

```bash
git clone <seu-repo> zefiro && cd zefiro
cp .env.example .env
nano .env        # preencha os valores REAIS (ver abaixo)
```

No `.env` (nunca vai para o git), preencha:

```
DOMAIN=seudominio.com.br
ACME_EMAIL=voce@email.com
POSTGRES_PASSWORD=<senha forte>
JWT_SECRET=<openssl rand -hex 32>
WEBHOOK_SECRET=<aleatório>
ADMIN_EMAIL=voce@email.com
ADMIN_PASSWORD=<senha forte do painel>
PAYMENT_GATEWAY=mercadopago
MP_ACCESS_TOKEN=APP_USR-...     # token de PRODUÇÃO do Mercado Pago
MP_WEBHOOK_SECRET=              # painel MP → Webhooks (recomendado)
```

## 4. Subir em produção (com HTTPS)

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

O Caddy emite os certificados sozinho no primeiro acesso (precisa do DNS já
apontando e das portas 80/443 abertas). Acompanhe:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f caddy
```

Pronto: `https://seudominio.com`, `https://app.seudominio.com` e
`https://admin.seudominio.com` no ar.

## 5. Webhook do Mercado Pago

No painel do Mercado Pago (Suas integrações → sua aplicação → **Webhooks**),
cadastre a URL:

```
https://app.seudominio.com/api/billing/webhook
```

Selecione o evento **Pagamentos**. Copie o **segredo de assinatura** para
`MP_WEBHOOK_SECRET` no `.env` e reinicie (`docker compose ... up -d`). Sem o
webhook chegando, a compra fica **pendente** para sempre — é ele que ativa a
assinatura após o pagamento aprovado.

## Atualizar o sistema depois

```bash
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## Notas

- **Dev local** continua `docker compose up` (navega em `localhost:5173`, banco
  persistente, gateway simulado). **Testes**: `./scripts/test.sh` (stack isolado,
  banco efêmero). Nada disso afeta a produção.
- Trocar a senha do admin = editar `ADMIN_PASSWORD` no `.env` e reiniciar.
- Backup do banco: `docker compose exec db pg_dump -U zefiro zefiro > backup.sql`.
