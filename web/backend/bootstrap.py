"""Seed inicial via ambiente (ADMIN_EMAIL + ADMIN_PASSWORD), rodado no startup.

Cria/atualiza DUAS contas com as mesmas credenciais:
  1. AdminUser  → login do PAINEL administrativo (/admin), role 'owner'
  2. User       → conta de CLIENTE do dono, com Pro ativo (~10 anos), para
                  usar o app em si sem passar pela compra

O ambiente é a fonte da senha — trocar ADMIN_PASSWORD e reiniciar redefine.
"""
import os
from datetime import datetime, timedelta

from db import SessionLocal
from models import AdminUser, Subscription, User
from security import generate_access_code, hash_password, verify_password

_ADMIN_ACCESS_DAYS = 3650  # ~10 anos


def _sync_password(obj, password: str):
    if not verify_password(password, obj.password_hash):
        obj.password_hash = hash_password(password)


def seed_admin():
    email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not email or not password:
        return

    db = SessionLocal()
    try:
        # 1) Admin do painel
        admin = db.query(AdminUser).filter(AdminUser.email == email).first()
        if admin is None:
            admin = AdminUser(email=email, nome="Admin",
                              password_hash=hash_password(password), role="owner")
            db.add(admin)
        else:
            _sync_password(admin, password)

        # 2) Conta de cliente do dono (Pro ativo, sem passar pela compra)
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(email=email, password_hash=hash_password(password),
                        name="Admin", status="ativo", plano="pro",
                        codigo_acesso=generate_access_code())
            db.add(user)
            db.flush()
        else:
            _sync_password(user, password)
            user.status = "ativo"
            user.plano = "pro"
            if not user.codigo_acesso:
                user.codigo_acesso = generate_access_code()

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
