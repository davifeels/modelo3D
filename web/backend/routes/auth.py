"""Autenticação: registro, login e a dependency que protege todos os endpoints.

- Registro cria a conta E inicia o trial de 7 dias do Pro (sem cartão) — regra
  do briefing: novo usuário entra direto no app.
- Token: JWT HS256 (security.py), enviado como `Authorization: Bearer <token>`.
  Endpoints de download (links <a href>) também aceitam `?token=` na query.
"""
import re
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import billing
from db import get_db
from models import Subscription, User
from security import create_token, decode_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ── Dependency de autenticação (usada por mesh, export e billing) ────────────

def get_current_user(
    authorization: str | None = Header(default=None),
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> User:
    raw = None
    if authorization and authorization.lower().startswith("bearer "):
        raw = authorization[7:].strip()
    elif token:
        raw = token  # downloads via <a href> não enviam headers
    if not raw:
        raise HTTPException(401, "nao_autenticado")
    user_id = decode_token(raw)
    if not user_id:
        raise HTTPException(401, "token_invalido")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(401, "usuario_inexistente")
    return user


# ── Schemas ───────────────────────────────────────────────────────────────────

class RegisterReq(BaseModel):
    email: str
    password: str = Field(min_length=6, max_length=128)
    name: str | None = None


class LoginReq(BaseModel):
    email: str
    password: str


def _user_payload(user: User) -> dict:
    return {"id": user.id, "email": user.email, "name": user.name}


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/register")
def register(req: RegisterReq, db: Session = Depends(get_db)):
    email = req.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(422, "email_invalido")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "email_ja_cadastrado")

    user = User(email=email, password_hash=hash_password(req.password),
                name=(req.name or "").strip() or None)
    db.add(user)
    db.flush()

    # Trial de 7 dias do Pro, sem cartão (briefing §regras de negócio)
    now = datetime.utcnow()
    db.add(Subscription(
        user_id=user.id, plan="pro", periodo=None, status="trialing",
        trial_end=now + timedelta(days=billing.TRIAL_DAYS),
    ))
    db.commit()
    return {"token": create_token(user.id), "user": _user_payload(user)}


@router.post("/login")
def login(req: LoginReq, db: Session = Depends(get_db)):
    email = req.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(401, "credenciais_invalidas")
    return {"token": create_token(user.id), "user": _user_payload(user)}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"user": _user_payload(user)}
