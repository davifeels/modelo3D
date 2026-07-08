"""Compra de acesso — a ÚNICA porta de entrada de clientes no sistema.

Fluxo (briefing da refatoração):
  visitante → landing → /comprar → POST /api/purchase → conta criada
  automaticamente (senha temporária + código de acesso) → cliente aparece no
  painel admin → admin envia credenciais → cliente faz login.

Pagamento: com gateway real configurado (gateway.py), devolve checkout_url e
registra a compra como 'pendente' (o webhook ativa depois). Sem gateway, a
compra é aprovada de forma SIMULADA ('aprovado_simulado') e o acesso ativa na
hora — comportamento de homologação, documentado em docs/REFATORACAO.md.

Com ZS_DEV_BILLING=1 a resposta inclui `dev_credentials` (senha/código) para
a suíte de testes — NUNCA habilitar em produção.
"""
import os
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import billing
import subscriptions
from db import get_db
from gateway import GatewayNotConfigured, get_gateway
from models import Purchase, User
from ratelimit import rate_limit
from security import generate_access_code, generate_temp_password, hash_password

router = APIRouter(prefix="/api/purchase", tags=["purchase"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^[\d\s()+\-]{8,20}$")


def _dev_enabled() -> bool:
    return os.environ.get("ZS_DEV_BILLING", "0") == "1"


class PurchaseReq(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    email: str
    telefone: str
    plano: str
    periodo: str


@router.get("/products")
def products():
    """Catálogo público exibido na tela de compra."""
    return {"plans": billing.PLANS, "periodos": list(billing.PERIODOS)}


@router.post("", dependencies=[Depends(rate_limit("purchase", 10))])
def purchase(req: PurchaseReq, db: Session = Depends(get_db)):
    err = billing.validate_selection(req.plano, req.periodo)
    if err:
        raise HTTPException(422, err)
    email = req.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(422, "email_invalido")
    if not _PHONE_RE.match(req.telefone.strip()):
        raise HTTPException(422, "telefone_invalido")

    valor = billing.price_cents(req.plano, req.periodo)
    user = db.query(User).filter(User.email == email).first()
    renewed = user is not None
    credentials = None

    if user is None:
        # Cadastro AUTOMÁTICO: cliente não cria conta manualmente
        senha = generate_temp_password()
        user = User(
            email=email, name=req.nome.strip(),
            telefone=req.telefone.strip(),
            password_hash=hash_password(senha),
            temp_password=senha,
            codigo_acesso=generate_access_code(),
            status="ativo", plano=req.plano,
        )
        db.add(user)
        db.flush()
        credentials = {"email": email, "senha": senha,
                       "codigo_acesso": user.codigo_acesso}
    elif user.status == "bloqueado":
        raise HTTPException(403, "conta_bloqueada")

    # Pagamento: gateway real → checkout pendente; sem gateway → simulado
    try:
        result = get_gateway().create_checkout(
            user_id=user.id, email=email, plan=req.plano,
            periodo=req.periodo, pay_method="card", amount_cents=valor)
        db.add(Purchase(user_id=user.id, plano=req.plano, periodo=req.periodo,
                        valor_cents=valor, status_pagamento="pendente"))
        db.commit()
        return {"ok": True, "renewed": renewed, "pending_payment": True,
                "checkout_url": result["checkout_url"], "amount_cents": valor}
    except GatewayNotConfigured:
        pass

    db.add(Purchase(user_id=user.id, plano=req.plano, periodo=req.periodo,
                    valor_cents=valor, status_pagamento="aprovado_simulado"))
    subscriptions.activate(db, user.id, req.plano, req.periodo)
    db.commit()

    resp = {
        "ok": True, "renewed": renewed, "pending_payment": False,
        "amount_cents": valor,
        "message": ("Acesso renovado — use suas credenciais atuais."
                    if renewed else
                    "Compra confirmada! Você receberá login e senha por e-mail."),
    }
    if credentials and _dev_enabled():
        resp["dev_credentials"] = credentials
    return resp
