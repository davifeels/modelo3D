"""Ativação/renovação de assinatura no banco — usada pela compra, pelo
webhook do gateway e pelos endpoints /dev/* (única fonte dessa lógica)."""
from datetime import datetime

from sqlalchemy.orm import Session

import billing
from models import Subscription, User


def activate(db: Session, user_id: str, plan: str, periodo: str,
             gateway_customer_id: str | None = None,
             gateway_subscription_id: str | None = None) -> Subscription:
    now = datetime.utcnow()
    sub = db.query(Subscription).filter(Subscription.user_id == user_id).first()
    if sub is None:
        sub = Subscription(user_id=user_id, plan=plan)
        db.add(sub)
    sub.plan = plan
    sub.periodo = periodo
    sub.status = "active"
    sub.trial_end = None
    sub.current_period_start = now
    sub.current_period_end = billing.period_end(now, periodo)
    sub.canceled_at = None
    sub.read_only_until = None
    if gateway_customer_id:
        sub.gateway_customer_id = gateway_customer_id
    if gateway_subscription_id:
        sub.gateway_subscription_id = gateway_subscription_id
    # Espelho no cadastro do cliente (coluna exibida no painel admin)
    user = db.get(User, user_id)
    if user:
        user.plano = plan
    return sub
