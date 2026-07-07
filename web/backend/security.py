"""Hash de senha (PBKDF2, stdlib) e tokens JWT HS256 (stdlib, sem dependências).

JWT_SECRET DEVE ser definido em produção (docker-compose já define um valor —
troque antes de expor publicamente). O formato do token é JWT padrão, então
migrar para PyJWT/jose depois é plug-and-play.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-troque-em-producao")
TOKEN_TTL_SECONDS = 7 * 24 * 3600  # 7 dias

_PBKDF2_ITERS = 200_000


# ── Senhas ────────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _PBKDF2_ITERS)
    return f"pbkdf2${_PBKDF2_ITERS}${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt, expected = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iters))
        return hmac.compare_digest(dk.hex(), expected)
    except (ValueError, AttributeError):
        return False


# ── JWT HS256 ────────────────────────────────────────────────────────────────

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_dec(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def create_token(user_id: str) -> str:
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url(json.dumps({"sub": user_id, "exp": int(time.time()) + TOKEN_TTL_SECONDS}).encode())
    signing_input = f"{header}.{payload}".encode()
    sig = _b64url(hmac.new(JWT_SECRET.encode(), signing_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"


def decode_token(token: str):
    """Retorna o user_id ou None (assinatura inválida/expirado/malformado)."""
    try:
        header, payload, sig = token.split(".")
        signing_input = f"{header}.{payload}".encode()
        expected = _b64url(hmac.new(JWT_SECRET.encode(), signing_input, hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(_b64url_dec(payload))
        if data.get("exp", 0) < time.time():
            return None
        return data.get("sub")
    except Exception:
        return None
