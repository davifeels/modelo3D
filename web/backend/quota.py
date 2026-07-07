"""Enforcement do limite de fatiamentos por mês (Essencial: 25, Pro: ilimitado).

"Arquivo fatiado" = sessão de upload que recebeu ao menos um corte no mês.
Re-cortar o mesmo arquivo (mesma sessão) não consome quota de novo.

BILLING_ENFORCE=0 desliga o bloqueio (o uso continua sendo contado) — útil
em desenvolvimento; o padrão é ligado.
"""
import os
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import billing
from models import SliceUsage, Subscription


def _enforce() -> bool:
    return os.environ.get("BILLING_ENFORCE", "1") == "1"


def _get_sub(db: Session, user_id: str) -> Subscription | None:
    return db.query(Subscription).filter(Subscription.user_id == user_id).first()


def ensure_slice_allowed(db: Session, user_id: str, session_id: str):
    """Chamar ANTES de cortar. Levanta 402 se sem plano ativo ou quota esgotada."""
    if not _enforce():
        return
    now = datetime.utcnow()
    sub = _get_sub(db, user_id)
    if not billing.has_access(sub, now):
        raise HTTPException(402, "assinatura_necessaria")
    limit = billing.slice_limit(sub)
    if limit is None:
        return  # Pro: ilimitado
    period = billing.period_key(now)
    already = db.query(SliceUsage).filter(
        SliceUsage.user_id == user_id, SliceUsage.period == period,
        SliceUsage.session_id == session_id).first()
    if already:
        return  # este arquivo já contou neste mês
    used = db.query(SliceUsage).filter(
        SliceUsage.user_id == user_id, SliceUsage.period == period).count()
    if used >= limit:
        raise HTTPException(402, "limite_de_fatiamentos_atingido")


def record_slice(db: Session, user_id: str, session_id: str):
    """Chamar APÓS um corte bem-sucedido. Idempotente por (user, mês, sessão)."""
    now = datetime.utcnow()
    db.add(SliceUsage(user_id=user_id, period=billing.period_key(now),
                      session_id=session_id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # corrida benigna: outro corte da mesma sessão já registrou
