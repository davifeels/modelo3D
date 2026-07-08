"""Painel administrativo: autenticação SEPARADA (admin_users) e gestão de
clientes — listar/buscar, senhas, envio de credenciais, bloqueio e histórico.

Toda ação administrativa gera uma linha em admin_logs (auditoria).
O admin inicial é seedado no startup via ADMIN_EMAIL/ADMIN_PASSWORD
(bootstrap.py).
"""
import re
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

import billing
import emailer
import subscriptions
from db import get_db
from models import AdminLog, AdminUser, EmailLog, Purchase, Subscription, User
from ratelimit import rate_limit
from security import (create_admin_token, decode_admin_token,
                      generate_access_code, generate_temp_password,
                      hash_password, verify_password)

router = APIRouter(prefix="/api/admin", tags=["admin"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^[\d\s()+\-]{8,20}$")


# ── Autenticação do admin ─────────────────────────────────────────────────────

def get_current_admin(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AdminUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "nao_autenticado")
    admin_id = decode_admin_token(authorization[7:].strip())
    if not admin_id:
        raise HTTPException(401, "token_invalido")
    admin = db.get(AdminUser, admin_id)
    if not admin:
        raise HTTPException(401, "admin_inexistente")
    return admin


class AdminLoginReq(BaseModel):
    email: str
    password: str


@router.post("/login", dependencies=[Depends(rate_limit("admin_login", 10))])
def admin_login(req: AdminLoginReq, db: Session = Depends(get_db)):
    admin = db.query(AdminUser).filter(
        AdminUser.email == req.email.strip().lower()).first()
    if not admin or not verify_password(req.password, admin.password_hash):
        raise HTTPException(401, "credenciais_invalidas")
    return {"token": create_admin_token(admin.id),
            "admin": {"id": admin.id, "nome": admin.nome,
                      "email": admin.email, "role": admin.role}}


@router.get("/me")
def admin_me(admin: AdminUser = Depends(get_current_admin)):
    return {"admin": {"id": admin.id, "nome": admin.nome,
                      "email": admin.email, "role": admin.role}}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _log(db: Session, admin: AdminUser, acao: str,
         alvo: User | None = None, detalhe: str | None = None):
    db.add(AdminLog(admin_id=admin.id, acao=acao,
                    alvo_user_id=alvo.id if alvo else None, detalhe=detalhe))


def _iso(dt):
    return dt.isoformat() if dt else None


def _get_user_or_404(db: Session, user_id: str) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "cliente_nao_encontrado")
    return user


def _user_row(db: Session, u: User) -> dict:
    last_purchase = (db.query(Purchase).filter(Purchase.user_id == u.id)
                     .order_by(Purchase.data_compra.desc()).first())
    last_send = (db.query(EmailLog).filter(EmailLog.user_id == u.id)
                 .order_by(EmailLog.data_envio.desc()).first())
    return {
        "id": u.id, "nome": u.name, "email": u.email, "telefone": u.telefone,
        "plano": u.plano, "status": u.status,
        "codigo_acesso": u.codigo_acesso, "temp_password": u.temp_password,
        "data_compra": _iso(last_purchase.data_compra) if last_purchase else None,
        "data_envio_acesso": _iso(last_send.data_envio) if last_send else None,
        "ultimo_login": _iso(u.last_login_at),
        "created_at": _iso(u.created_at),
    }


# ── Clientes: listagem e busca ────────────────────────────────────────────────

@router.get("/users")
def list_users(
    q: str | None = Query(default=None),
    field: str | None = Query(default=None),  # nome | email | telefone
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(User)
    if q:
        like = f"%{q.strip()}%"
        if field == "nome":
            query = query.filter(User.name.ilike(like))
        elif field == "email":
            query = query.filter(User.email.ilike(like))
        elif field == "telefone":
            query = query.filter(User.telefone.ilike(like))
        else:
            query = query.filter(or_(User.name.ilike(like),
                                     User.email.ilike(like),
                                     User.telefone.ilike(like)))
    users = query.order_by(User.created_at.desc()).limit(500).all()
    return {"users": [_user_row(db, u) for u in users], "total": len(users)}


@router.get("/users/{user_id}/history")
def user_history(user_id: str, admin: AdminUser = Depends(get_current_admin),
                 db: Session = Depends(get_db)):
    user = _get_user_or_404(db, user_id)
    purchases = (db.query(Purchase).filter(Purchase.user_id == user.id)
                 .order_by(Purchase.data_compra.desc()).all())
    emails = (db.query(EmailLog).filter(EmailLog.user_id == user.id)
              .order_by(EmailLog.data_envio.desc()).all())
    sub = db.query(Subscription).filter(Subscription.user_id == user.id).first()
    return {
        "user": _user_row(db, user),
        "compras": [{"plano": p.plano, "periodo": p.periodo,
                     "valor_cents": p.valor_cents,
                     "status_pagamento": p.status_pagamento,
                     "data_compra": _iso(p.data_compra)} for p in purchases],
        "emails": [{"assunto": e.assunto, "status": e.status,
                    "data_envio": _iso(e.data_envio)} for e in emails],
        "assinatura": {
            "status": sub.status if sub else None,
            "fim_periodo": _iso(sub.current_period_end) if sub else None,
        },
    }


# ── Criação manual de cliente ─────────────────────────────────────────────────
# Exceção controlada à regra "acesso só nasce da compra": o ADMIN pode criar
# uma conta direto no painel (cortesia, suporte, venda por fora). Gera as
# mesmas credenciais da compra (senha temporária + código ZS-XXXX-XXXX) e,
# se um plano for informado, ativa a assinatura na hora (sem registro de
# compra — não houve pagamento).

class CreateUserReq(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    email: str
    telefone: str = ""
    plano: str | None = None      # None → conta sem plano (cai no paywall)
    periodo: str = "mensal"


@router.post("/users")
def create_user(req: CreateUserReq, admin: AdminUser = Depends(get_current_admin),
                db: Session = Depends(get_db)):
    email = req.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(422, "email_invalido")
    telefone = req.telefone.strip()
    if telefone and not _PHONE_RE.match(telefone):
        raise HTTPException(422, "telefone_invalido")
    if req.plano:
        err = billing.validate_selection(req.plano, req.periodo)
        if err:
            raise HTTPException(422, err)
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "email_ja_cadastrado")

    senha = generate_temp_password()
    user = User(
        email=email, name=req.nome.strip(), telefone=telefone or None,
        password_hash=hash_password(senha), temp_password=senha,
        codigo_acesso=generate_access_code(), status="ativo", plano=req.plano,
    )
    db.add(user)
    db.flush()
    if req.plano:
        subscriptions.activate(db, user.id, req.plano, req.periodo)
    _log(db, admin, "criar_usuario", user,
         detalhe=f"plano:{req.plano or 'nenhum'}")
    db.commit()
    return {"ok": True, "user": _user_row(db, user), "temp_password": senha}


# ── Senhas ────────────────────────────────────────────────────────────────────

class SetPasswordReq(BaseModel):
    # Sem password → gera senha temporária nova (reset)
    password: str | None = Field(default=None, min_length=6, max_length=128)


@router.post("/users/{user_id}/password")
def set_password(user_id: str, req: SetPasswordReq,
                 admin: AdminUser = Depends(get_current_admin),
                 db: Session = Depends(get_db)):
    user = _get_user_or_404(db, user_id)
    nova = req.password or generate_temp_password()
    user.password_hash = hash_password(nova)
    # Mantida em claro para o painel exibir/enviar — some quando o cliente
    # redefine a própria senha (/reset-password); login valida só o hash.
    user.temp_password = nova
    user.token_version += 1  # derruba sessões/tokens ativos do cliente
    _log(db, admin, "reset_senha" if req.password is None else "definir_senha", user)
    db.commit()
    return {"ok": True, "temp_password": nova}


# ── Envio de credenciais ──────────────────────────────────────────────────────

@router.post("/users/{user_id}/send-access")
def send_access(user_id: str, admin: AdminUser = Depends(get_current_admin),
                db: Session = Depends(get_db)):
    user = _get_user_or_404(db, user_id)
    if not user.temp_password:
        raise HTTPException(409, "sem_senha_temporaria_gere_uma_primeiro")
    subject, body = emailer.credentials_email(
        nome=user.name, email=user.email, senha=user.temp_password,
        codigo=user.codigo_acesso or "—")
    status = emailer.send_email(db, to=user.email, subject=subject, body=body,
                                user_id=user.id)
    _log(db, admin, "enviar_acesso", user, detalhe=f"email:{status}")
    db.commit()
    return {"ok": True, "email_status": status,
            "data_envio": datetime.utcnow().isoformat()}


# ── Status da conta ───────────────────────────────────────────────────────────

class SetStatusReq(BaseModel):
    status: str  # 'ativo' | 'bloqueado'


@router.post("/users/{user_id}/status")
def set_status(user_id: str, req: SetStatusReq,
               admin: AdminUser = Depends(get_current_admin),
               db: Session = Depends(get_db)):
    if req.status not in ("ativo", "bloqueado"):
        raise HTTPException(422, "status_invalido")
    user = _get_user_or_404(db, user_id)
    user.status = req.status
    _log(db, admin, f"status_{req.status}", user)
    db.commit()
    return {"ok": True, "status": user.status}


# ── Logs administrativos ──────────────────────────────────────────────────────

@router.get("/logs")
def admin_logs(admin: AdminUser = Depends(get_current_admin),
               db: Session = Depends(get_db)):
    logs = db.query(AdminLog).order_by(AdminLog.created_at.desc()).limit(200).all()
    return {"logs": [{"acao": l.acao, "alvo_user_id": l.alvo_user_id,
                      "detalhe": l.detalhe, "data": _iso(l.created_at)}
                     for l in logs]}
