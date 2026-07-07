"""Seed da conta admin via ambiente (ADMIN_EMAIL + ADMIN_PASSWORD).

Rodado no startup: garante que a conta do dono do produto exista com plano
Pro ativo (ilimitado, sem expirar na prática). O ambiente é a fonte da senha —
trocar ADMIN_PASSWORD e reiniciar redefine a senha. O login é o normal
(POST /api/auth/login) e devolve o mesmo token JWT dos demais usuários.
"""
import os
from datetime import datetime, timedelta

from db import SessionLocal
from models import Subscription, User
from security import hash_password, verify_password

_ADMIN_ACCESS_DAYS = 3650  # ~10 anos


def seed_admin():
    email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not email or not password:
        return

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(email=email, password_hash=hash_password(password), name="Admin")
            db.add(user)
            db.flush()
        elif not verify_password(password, user.password_hash):
            user.password_hash = hash_password(password)

        now = datetime.utcnow()
        sub = db.query(Subscription).filter(Subscription.user_id == user.id).first()
        if sub is None:
            sub = Subscription(user_id=user.id, plan="pro")
            db.add(sub)
        sub.plan = "pro"
        sub.periodo = "anual"
        sub.status = "active"
        sub.trial_end = None
        sub.current_period_start = now
        sub.current_period_end = now + timedelta(days=_ADMIN_ACCESS_DAYS)
        sub.canceled_at = None
        sub.read_only_until = None
        db.commit()
    finally:
        db.close()
