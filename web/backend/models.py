"""Modelos do banco: clientes, compras, e-mails, admins e billing.

Clientes NÃO se cadastram: a conta nasce na compra (routes/purchase.py) com
senha temporária + código de acesso, e as credenciais são enviadas pelo admin.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, UniqueConstraint

from db import Base


def _uuid():
    return str(uuid.uuid4())


class User(Base):
    """Cliente do sistema (criado automaticamente pela compra).

    status: ativo | bloqueado
    temp_password: senha temporária EM CLARO enquanto vigente — o admin precisa
    vê-la na tabela e enviá-la por e-mail (requisito do painel). É apagada se o
    admin definir uma senha manual; o login sempre valida contra password_hash.
    """
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(120), nullable=True)
    telefone = Column(String(40), nullable=True)
    codigo_acesso = Column(String(20), unique=True, nullable=True)
    status = Column(String(20), nullable=False, default="ativo")
    plano = Column(String(20), nullable=True)              # espelho da Subscription
    temp_password = Column(String(64), nullable=True)
    # Incrementado a cada troca/reset de senha e bloqueio: os tokens JWT
    # carregam `ver` e são recusados quando não batem — invalida sessões antigas.
    token_version = Column(Integer, nullable=False, default=0)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Purchase(Base):
    """Uma linha por compra/renovação (histórico do cliente no painel)."""
    __tablename__ = "purchases"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    plano = Column(String(20), nullable=False)             # 'essencial' | 'pro'
    periodo = Column(String(10), nullable=False)           # 'mensal' | 'anual'
    valor_cents = Column(Integer, nullable=False)
    status_pagamento = Column(String(30), nullable=False)  # 'aprovado' | 'aprovado_simulado' | 'pendente'
    data_compra = Column(DateTime, default=datetime.utcnow, nullable=False)


class EmailLog(Base):
    """Log de todo e-mail disparado (envio de acesso, esqueci a senha)."""
    __tablename__ = "email_logs"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=True)
    destinatario = Column(String(255), nullable=False)
    assunto = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False)            # 'enviado' | 'simulado' | 'falhou'
    data_envio = Column(DateTime, default=datetime.utcnow, nullable=False)


class AdminUser(Base):
    """Administradores do painel — autenticação SEPARADA dos clientes."""
    __tablename__ = "admin_users"

    id = Column(String(36), primary_key=True, default=_uuid)
    nome = Column(String(120), nullable=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="admin")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AdminLog(Base):
    """Auditoria: uma linha por ação administrativa (reset de senha, envio…)."""
    __tablename__ = "admin_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_id = Column(String(36), ForeignKey("admin_users.id"), index=True, nullable=False)
    acao = Column(String(60), nullable=False)
    alvo_user_id = Column(String(36), nullable=True)
    detalhe = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Subscription(Base):
    """Uma assinatura por usuário (a mais recente vale).

    status: trialing | active | canceled | expired
      - trialing: legado (trial não é mais criado — acesso nasce da compra)
      - active:   compra confirmada
      - canceled: cancelada — acesso segue até current_period_end
      - expired:  sem acesso (paywall); projetos em modo leitura até read_only_until
    """
    __tablename__ = "subscriptions"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, index=True, nullable=False)
    plan = Column(String(20), nullable=False)              # 'essencial' | 'pro'
    periodo = Column(String(10), nullable=True)            # 'mensal' | 'anual' | None
    status = Column(String(20), nullable=False, default="trialing")
    trial_end = Column(DateTime, nullable=True)
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    canceled_at = Column(DateTime, nullable=True)
    read_only_until = Column(DateTime, nullable=True)      # 30 dias de leitura pós-cancelamento
    # Preenchidos pela integração real do gateway (Stripe/Mercado Pago/…)
    gateway_customer_id = Column(String(120), nullable=True)
    gateway_subscription_id = Column(String(120), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class SliceUsage(Base):
    """Um registro por ARQUIVO fatiado no mês (dedupe por session_id).

    Regra de negócio: Essencial fatia até 25 arquivos/mês; re-cortes do mesmo
    arquivo (mesma sessão de upload) não contam de novo.
    """
    __tablename__ = "slice_usage"
    __table_args__ = (UniqueConstraint("user_id", "period", "session_id", name="uq_usage"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    period = Column(String(7), index=True, nullable=False)   # 'YYYY-MM'
    session_id = Column(String(36), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class WebhookEvent(Base):
    """Idempotência de webhooks: um event_id só é processado uma vez."""
    __tablename__ = "webhook_events"

    event_id = Column(String(120), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PasswordResetToken(Base):
    """Token de recuperação de senha (single-use, expira).

    Guardamos só o HASH do token (nunca o valor cru) — quem só tem acesso ao
    banco não consegue redefinir senhas. "Esqueci a senha" gera um destes e
    envia o link por e-mail; a senha só muda quando o usuário abre o link.
    """
    __tablename__ = "password_reset_tokens"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
