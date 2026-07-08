"""Rate limit em memória por IP+rota, para os endpoints públicos.

Janela deslizante simples (deque de timestamps). Suficiente para uma
instância; com múltiplas réplicas, trocar por Redis mantendo esta interface.

Com ZS_DEV_BILLING=1 os limites são multiplicados por 100: a suíte de testes
dispara centenas de logins/compras do mesmo IP em minutos.
"""
import os
import threading
import time
from collections import deque

from fastapi import HTTPException, Request

_buckets: dict[tuple[str, str], deque] = {}
_lock = threading.Lock()


def _mult() -> int:
    return 100 if os.environ.get("ZS_DEV_BILLING", "0") == "1" else 1


def rate_limit(name: str, limit: int, window_seconds: int = 60):
    """Dependency FastAPI: `Depends(rate_limit('login', 10))` → 429 no excesso."""
    def dep(request: Request):
        ip = request.client.host if request.client else "?"
        key = (name, ip)
        now = time.time()
        cap = limit * _mult()
        with _lock:
            q = _buckets.setdefault(key, deque())
            while q and q[0] < now - window_seconds:
                q.popleft()
            if len(q) >= cap:
                raise HTTPException(429, "muitas_tentativas_aguarde")
            q.append(now)
    return dep


# ── Bloqueio por CONTA (complementa o rate-limit por IP) ─────────────────────
# Rate-limit por IP não segura um atacante distribuído tentando a mesma conta.
# Aqui contamos falhas por e-mail: N erros na janela → conta trancada por um
# tempo, mesmo que cada tentativa venha de um IP diferente.

_LOCK_THRESHOLD = 8          # falhas consecutivas antes de trancar
_LOCK_WINDOW = 15 * 60       # janela de contagem (s)
_LOCK_DURATION = 15 * 60     # tempo trancado (s)
_fails: dict[str, dict] = {}
_fail_lock = threading.Lock()


def account_locked(email: str) -> bool:
    """True se a conta está no período de bloqueio por tentativas excessivas."""
    email = (email or "").strip().lower()
    now = time.time()
    with _fail_lock:
        rec = _fails.get(email)
        return bool(rec and rec.get("locked_until", 0) > now)


def register_login_failure(email: str):
    """Conta uma falha de login; tranca ao passar do limite (×mult em dev)."""
    email = (email or "").strip().lower()
    now = time.time()
    threshold = _LOCK_THRESHOLD * _mult()
    with _fail_lock:
        rec = _fails.get(email)
        if not rec or now - rec.get("first", now) > _LOCK_WINDOW:
            rec = {"first": now, "count": 0, "locked_until": 0}
        rec["count"] += 1
        if rec["count"] >= threshold:
            rec["locked_until"] = now + _LOCK_DURATION
        _fails[email] = rec


def clear_login_failures(email: str):
    """Login bem-sucedido zera o contador da conta."""
    with _fail_lock:
        _fails.pop((email or "").strip().lower(), None)
