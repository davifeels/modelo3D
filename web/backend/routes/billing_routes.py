"""Endpoints de billing: catálogo, assinatura do usuário, checkout, webhook,
cancelamento e troca de plano.

O que já funciona sem gateway:
  - trial de 7 dias no registro, paywall quando expira;
  - contagem/limite de 25 fatiamentos/mês do Essencial (quota.py);
  - webhook interno assinado com WEBHOOK_SECRET (ativa/cancela de verdade);
  - endpoints /dev/* (apenas com ZS_DEV_BILLING=1) para simular ativação em
    dev e testes.
O que falta é SÓ o gateway real — ver gateway.py.
"""
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

import billing
import subscriptions
from db import get_db
from gateway import GatewayNotConfigured, WebhookInvalid, get_gateway
from models import SliceUsage, Subscription, User, WebhookEvent
from routes.auth import get_current_user

router = APIRouter(prefix="/api/billing", tags=["billing"])


def _dev_enabled() -> bool:
    return os.environ.get("ZS_DEV_BILLING", "0") == "1"


def _get_sub(db: Session, user_id: str) -> Subscription | None:
    return db.query(Subscription).filter(Subscription.user_id == user_id).first()


def _usage(db: Session, user_id: str, now: datetime) -> dict:
    period = billing.period_key(now)
    used = db.query(SliceUsage).filter(
        SliceUsage.user_id == user_id, SliceUsage.period == period).count()
    return {"period": period, "used": used}


def _sub_payload(db: Session, user: User) -> dict:
    now = datetime.utcnow()
    sub = _get_sub(db, user.id)
    usage = _usage(db, user.id, now)
    limit = billing.slice_limit(sub) if billing.has_access(sub, now) else 0
    usage["limit"] = limit
    usage["remaining"] = None if limit is None else max(0, limit - usage["used"])
    return {
        "has_access": billing.has_access(sub, now),
        "plan": sub.plan if sub else None,
        "periodo": sub.periodo if sub else None,
        "status": sub.status if sub else None,
        "trial_end": sub.trial_end.isoformat() if sub and sub.trial_end else None,
        "current_period_end": sub.current_period_end.isoformat()
            if sub and sub.current_period_end else None,
        "read_only_until": sub.read_only_until.isoformat()
            if sub and sub.read_only_until else None,
        "usage": usage,
    }


# Ativação/renovação vive em subscriptions.activate (compartilhada com a compra)
_activate = subscriptions.activate


# ── Catálogo (público) ────────────────────────────────────────────────────────

@router.get("/plans")
def plans():
    return {"plans": billing.PLANS, "trial_days": billing.TRIAL_DAYS,
            "annual_refund_window_days": billing.ANNUAL_REFUND_WINDOW_DAYS,
            "read_only_days": billing.READ_ONLY_DAYS}


# ── Assinatura do usuário logado ─────────────────────────────────────────────

@router.get("/me")
def my_subscription(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _sub_payload(db, user)


# ── Checkout ─────────────────────────────────────────────────────────────────

class CheckoutReq(BaseModel):
    plano: str
    periodo: str
    payment_method: str = "card"


@router.post("/checkout")
def checkout(req: CheckoutReq, user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    err = billing.validate_selection(req.plano, req.periodo, req.payment_method)
    if err:
        raise HTTPException(422, err)
    amount = billing.price_cents(req.plano, req.periodo)
    try:
        result = get_gateway().create_checkout(
            user_id=user.id, email=user.email, plan=req.plano,
            periodo=req.periodo, pay_method=req.payment_method, amount_cents=amount)
    except GatewayNotConfigured:
        raise HTTPException(501, "gateway_nao_configurado")
    return {"checkout_url": result["checkout_url"], "amount_cents": amount}


# ── Webhook do gateway ───────────────────────────────────────────────────────

@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    try:
        evt = get_gateway().verify_webhook(dict(request.headers), body)
    except GatewayNotConfigured:
        raise HTTPException(501, "gateway_nao_configurado")
    except WebhookInvalid:
        raise HTTPException(401, "assinatura_webhook_invalida")

    # Idempotência: cada event_id processa uma única vez
    if db.get(WebhookEvent, evt["event_id"]):
        return {"ok": True, "duplicate": True}
    db.add(WebhookEvent(event_id=evt["event_id"]))

    etype = evt["type"]
    if etype == "subscription.activated":
        if evt.get("plan") not in billing.PLANS or evt.get("periodo") not in billing.PERIODOS:
            raise HTTPException(422, "evento_invalido")
        _activate(db, evt["user_id"], evt["plan"], evt["periodo"],
                  evt.get("gateway_customer_id"), evt.get("gateway_subscription_id"))
    elif etype == "subscription.canceled":
        sub = _get_sub(db, evt["user_id"])
        if sub:
            now = datetime.utcnow()
            sub.status = "canceled"
            sub.canceled_at = now
            end = sub.current_period_end or now
            sub.read_only_until = billing.period_end(end, "mensal")  # +30 dias de leitura
    elif etype == "payment.failed":
        pass  # espaço para dunning/notificação — acesso cai sozinho no fim do período
    else:
        raise HTTPException(422, "tipo_de_evento_desconhecido")

    db.commit()
    return {"ok": True}


# ── Cancelamento e troca de plano ────────────────────────────────────────────

@router.post("/cancel")
def cancel(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = datetime.utcnow()
    sub = _get_sub(db, user.id)
    if sub is None or sub.status not in ("trialing", "active"):
        raise HTTPException(409, "sem_assinatura_ativa")

    refund = billing.refund_cents(sub, now)
    if sub.gateway_subscription_id:
        get_gateway().cancel(sub.gateway_subscription_id)

    if sub.status == "trialing" or refund > 0:
        # Trial ou anual reembolsado: acesso encerra agora
        sub.status = "expired" if refund == 0 else "canceled"
        sub.trial_end = None
        sub.current_period_end = now
    else:
        sub.status = "canceled"  # acesso segue até o fim do período pago
    sub.canceled_at = now
    end = sub.current_period_end or now
    sub.read_only_until = billing.period_end(end, "mensal")  # +30 dias de leitura
    db.commit()
    return {"ok": True, "refund_cents": refund,
            "access_until": sub.current_period_end.isoformat() if sub.current_period_end else None}


class ChangePlanReq(BaseModel):
    plano: str
    periodo: str


@router.post("/change-plan")
def change_plan(req: ChangePlanReq, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    """Upgrade/downgrade com proração. Sem gateway, devolve a simulação do valor;
    com gateway, é aqui que a cobrança da diferença deve ser disparada."""
    err = billing.validate_selection(req.plano, req.periodo)
    if err:
        raise HTTPException(422, err)
    now = datetime.utcnow()
    sub = _get_sub(db, user.id)
    if sub is None or sub.status != "active":
        raise HTTPException(409, "sem_assinatura_ativa")
    charge = billing.change_plan_charge_cents(sub, req.plano, req.periodo, now)
    credit = billing.proration_credit_cents(sub, now)
    # TODO(gateway): cobrar `charge` antes de aplicar. Hoje aplica direto (dev).
    _activate(db, user.id, req.plano, req.periodo)
    db.commit()
    return {"ok": True, "charged_cents": charge, "prorated_credit_cents": credit}


# ── Endpoints de desenvolvimento (ZS_DEV_BILLING=1) ──────────────────────────

class DevActivateReq(BaseModel):
    plano: str
    periodo: str = "mensal"


@router.post("/dev/activate")
def dev_activate(req: DevActivateReq, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """Simula a ativação que o webhook do gateway fará em produção."""
    if not _dev_enabled():
        raise HTTPException(404, "nao_encontrado")
    err = billing.validate_selection(req.plano, req.periodo)
    if err:
        raise HTTPException(422, err)
    _activate(db, user.id, req.plano, req.periodo)
    db.commit()
    return _sub_payload(db, user)


class DevUsageReq(BaseModel):
    count: int


@router.post("/dev/set-usage")
def dev_set_usage(req: DevUsageReq, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """Preenche o contador mensal (para testar o limite de 25 sem 25 uploads)."""
    if not _dev_enabled():
        raise HTTPException(404, "nao_encontrado")
    now = datetime.utcnow()
    period = billing.period_key(now)
    db.query(SliceUsage).filter(SliceUsage.user_id == user.id,
                                SliceUsage.period == period).delete()
    for i in range(max(0, req.count)):
        db.add(SliceUsage(user_id=user.id, period=period, session_id=f"dev-{i}"))
    db.commit()
    return _usage(db, user.id, now)


class DevExpireReq(BaseModel):
    pass


@router.post("/dev/expire")
def dev_expire(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Expira a assinatura/trial (para testar o paywall)."""
    if not _dev_enabled():
        raise HTTPException(404, "nao_encontrado")
    sub = _get_sub(db, user.id)
    if sub:
        sub.status = "expired"
        sub.trial_end = None
        sub.current_period_end = None
        db.commit()
    return _sub_payload(db, user)
