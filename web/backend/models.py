"""Modelos do banco: usuários, assinaturas, uso mensal e eventos de webhook."""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, UniqueConstraint

from db import Base


def _uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(120), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Subscription(Base):
    """Uma assinatura por usuário (a mais recente vale).

    status: trialing | active | canceled | expired
      - trialing: 7 dias de Pro grátis criados no registro (sem cartão)
      - active:   pagamento confirmado pelo gateway (webhook)
      - canceled: cancelada — acesso segue até current_period_end
      - expired:  sem acesso (paywall); projetos em modo leitura até read_only_until
    """
    __tablename__ = "subscriptions"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, index=True, nullable=False)
    plan = Column(String(20), nullable=False)              # 'essencial' | 'pro'
    periodo = Column(String(10), nullable=True)            # 'mensal' | 'anual' | None (trial)
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
