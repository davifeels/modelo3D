"""Autenticação de CLIENTES: login e a dependency que protege os endpoints.

NÃO existe registro público — a conta nasce exclusivamente da compra
(routes/purchase.py) e as credenciais são enviadas pelo painel administrativo.

- Token: JWT HS256 (security.py), enviado como `Authorization: Bearer <token>`.
  Endpoints de download (links <a href>) também aceitam `?token=` na query.
- "Esqueci minha senha": NÃO troca a senha — gera um token de uso único e
  envia por e-mail o link de redefinição. A senha só muda quando o usuário
  abre o link e escolhe a nova (`/reset-password`). Resposta sempre genérica.
"""
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import emailer
from db import get_db
from models import PasswordResetToken, User
from ratelimit import (account_locked, clear_login_failures, rate_limit,
                       register_login_failure)
from security import (RESET_TOKEN_TTL_SECONDS, create_token, decode_token,
                      generate_reset_token, hash_password, hash_reset_token,
                      verify_password)

router = APIRouter(prefix="/api/auth", tags=["auth"])

APP_URL = os.environ.get("APP_URL", "http://localhost:5173")


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
    decoded = decode_token(raw)
    if not decoded:
        raise HTTPException(401, "token_invalido")
    user_id, ver = decoded
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(401, "usuario_inexistente")
    # Revogação: troca/reset de senha ou bloqueio incrementa token_version,
    # derrubando tokens emitidos antes (mesmo válidos por assinatura).
    if ver != user.token_version:
        raise HTTPException(401, "sessao_expirada")
    if user.status == "bloqueado":
        raise HTTPException(403, "conta_bloqueada")
    return user


# ── Schemas ───────────────────────────────────────────────────────────────────

class LoginReq(BaseModel):
    email: str
    password: str


class ForgotReq(BaseModel):
    email: str


class ResetReq(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


def _user_payload(user: User) -> dict:
    return {"id": user.id, "email": user.email, "name": user.name}


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/login", dependencies=[Depends(rate_limit("login", 15))])
def login(req: LoginReq, db: Session = Depends(get_db)):
    email = req.email.strip().lower()
    # Bloqueio por conta (defesa contra brute-force distribuído por IP)
    if account_locked(email):
        raise HTTPException(429, "conta_temporariamente_bloqueada")
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(req.password, user.password_hash):
        register_login_failure(email)
        raise HTTPException(401, "credenciais_invalidas")
    if user.status == "bloqueado":
        raise HTTPException(403, "conta_bloqueada")
    clear_login_failures(email)
    user.last_login_at = datetime.utcnow()
    db.commit()
    return {"token": create_token(user.id, user.token_version),
            "user": _user_payload(user)}


@router.post("/forgot-password", dependencies=[Depends(rate_limit("forgot", 5))])
def forgot_password(req: ForgotReq, db: Session = Depends(get_db)):
    """Envia um LINK de redefinição (token single-use). NÃO troca a senha aqui —
    assim ninguém tranca a conta de outro só sabendo o e-mail. Resposta genérica."""
    email = req.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if user and user.status != "bloqueado":
        # Invalida tokens de reset pendentes desta conta e emite um novo
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None)).delete()
        raw = generate_reset_token()
        db.add(PasswordResetToken(
            user_id=user.id, token_hash=hash_reset_token(raw),
            expires_at=datetime.utcnow() + timedelta(seconds=RESET_TOKEN_TTL_SECONDS)))
        db.commit()
        link = f"{APP_URL}/reset-password?token={raw}"
        subject, body = emailer.reset_email(nome=user.name, link=link)
        emailer.send_email(db, to=user.email, subject=subject, body=body,
                           user_id=user.id)
        # Só em dev/teste (ZS_DEV_BILLING=1): devolve o token para a suíte
        # exercitar o fluxo sem ler o e-mail. NUNCA habilitar em produção.
        if os.environ.get("ZS_DEV_BILLING") == "1":
            return {"ok": True, "dev_reset_token": raw,
                    "message": "Se o e-mail estiver cadastrado, enviaremos as instruções."}
    return {"ok": True,
            "message": "Se o e-mail estiver cadastrado, enviaremos as instruções."}


@router.post("/reset-password", dependencies=[Depends(rate_limit("reset", 10))])
def reset_password(req: ResetReq, db: Session = Depends(get_db)):
    """Consome o token do e-mail e define a nova senha. Invalida sessões antigas."""
    now = datetime.utcnow()
    row = (db.query(PasswordResetToken)
           .filter(PasswordResetToken.token_hash == hash_reset_token(req.token))
           .first())
    if not row or row.used_at is not None or row.expires_at < now:
        raise HTTPException(400, "token_invalido_ou_expirado")
    user = db.get(User, row.user_id)
    if not user:
        raise HTTPException(400, "token_invalido_ou_expirado")
    user.password_hash = hash_password(req.password)
    user.temp_password = None            # senha reversível deixa de existir
    user.token_version += 1              # derruba tokens/sessões anteriores
    row.used_at = now
    clear_login_failures(user.email)
    db.commit()
    return {"ok": True, "message": "Senha redefinida. Faça login com a nova senha."}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"user": _user_payload(user)}
