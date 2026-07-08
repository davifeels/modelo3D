"""Hash de senha (bcrypt; verifica legado PBKDF2) e tokens JWT HS256 (stdlib).

JWT_SECRET DEVE ser definido em produção (docker-compose já define um valor —
troque antes de expor publicamente). O formato do token é JWT padrão, então
migrar para PyJWT/jose depois é plug-and-play.

Tokens carregam `typ`: 'user' (clientes) ou 'admin' (painel administrativo).
Tokens antigos sem `typ` valem como 'user' — contas existentes não deslogam.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import string
import time

import bcrypt

# Sem default utilizável: se JWT_SECRET não vier do ambiente em produção, o
# app aborta no import (fail-closed) em vez de assinar tokens com um segredo
# público conhecido. Em dev/teste, ZS_DEV_BILLING=1 libera um fallback fixo.
JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    if os.environ.get("ZS_DEV_BILLING") == "1":
        JWT_SECRET = "dev-only-insecure-secret"
    else:
        raise RuntimeError(
            "JWT_SECRET não definido — defina no ambiente (.env) antes de subir.")

TOKEN_TTL_SECONDS = 7 * 24 * 3600       # 7 dias (clientes)
ADMIN_TOKEN_TTL_SECONDS = 12 * 3600     # 12 horas (admin: sessão mais curta)
RESET_TOKEN_TTL_SECONDS = 60 * 60       # 1 hora (link de "esqueci a senha")

_PBKDF2_ITERS = 200_000  # apenas para VERIFICAR hashes antigos


# ── Senhas ────────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_pbkdf2(password: str, stored: str) -> bool:
    try:
        _, iters, salt, expected = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iters))
        return hmac.compare_digest(dk.hex(), expected)
    except (ValueError, AttributeError):
        return False


def verify_password(password: str, stored: str) -> bool:
    if not stored:
        return False
    if stored.startswith("pbkdf2$"):          # hash legado (pré-bcrypt)
        return _verify_pbkdf2(password, stored)
    try:
        return bcrypt.checkpw(password.encode(), stored.encode())
    except ValueError:
        return False


# ── Credenciais geradas (compra / reset pelo admin) ──────────────────────────

_PW_ALPHABET = string.ascii_letters + string.digits  # sem símbolos ambíguos


def generate_temp_password(length: int = 10) -> str:
    return "".join(secrets.choice(_PW_ALPHABET) for _ in range(length))


def generate_access_code() -> str:
    """Código de acesso do cliente, ex.: ZS-4F2A-9C1B."""
    raw = secrets.token_hex(4).upper()
    return f"ZS-{raw[:4]}-{raw[4:]}"


# ── Token de recuperação de senha (single-use, guardado como hash) ───────────

def generate_reset_token() -> str:
    """Valor cru enviado no link do e-mail — nunca é persistido em claro."""
    return secrets.token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    """SHA-256 do token; é isto que vai para o banco (comparação por igualdade)."""
    return hashlib.sha256(token.encode()).hexdigest()


# ── JWT HS256 ────────────────────────────────────────────────────────────────

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_dec(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _make_token(sub: str, typ: str, ttl: int, ver: int = 0) -> str:
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url(json.dumps(
        {"sub": sub, "typ": typ, "ver": ver,
         "exp": int(time.time()) + ttl}).encode())
    signing_input = f"{header}.{payload}".encode()
    sig = _b64url(hmac.new(JWT_SECRET.encode(), signing_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"


def create_token(user_id: str, token_version: int = 0) -> str:
    return _make_token(user_id, "user", TOKEN_TTL_SECONDS, token_version)


def create_admin_token(admin_id: str) -> str:
    return _make_token(admin_id, "admin", ADMIN_TOKEN_TTL_SECONDS)


def _decode(token: str):
    """Retorna o payload (dict) ou None (assinatura inválida/expirado/malformado)."""
    try:
        header, payload, sig = token.split(".")
        signing_input = f"{header}.{payload}".encode()
        expected = _b64url(hmac.new(JWT_SECRET.encode(), signing_input, hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(_b64url_dec(payload))
        if data.get("exp", 0) < time.time():
            return None
        return data
    except Exception:
        return None


def decode_token(token: str):
    """(user_id, token_version) de um token de CLIENTE, ou None.

    Tokens antigos sem `typ` valem como user; sem `ver` valem como versão 0.
    """
    data = _decode(token)
    if data is None or data.get("typ", "user") != "user":
        return None
    return data.get("sub"), int(data.get("ver", 0))


def decode_admin_token(token: str):
    """admin_id de um token de ADMIN; None para token de cliente ou inválido."""
    data = _decode(token)
    if data is None or data.get("typ") != "admin":
        return None
    return data.get("sub")
