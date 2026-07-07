"""Helper de autenticação para os testes de API/E2E.

Todos os endpoints do backend exigem `Authorization: Bearer <token>` desde a
introdução do login (2026-07-07). Este módulo registra usuários de teste
descartáveis (e-mails únicos) no servidor em localhost:8000.

O usuário cacheado (get_token/auth_headers) nasce com trial Pro de 7 dias —
fatiamento ilimitado — então os testes antigos de malha rodam sem esbarrar na
quota do Essencial.
"""
import json
import urllib.request
import uuid

BASE = "http://localhost:8000/api"
_cache: dict = {}


def register_user():
    """Registra um usuário NOVO e retorna (token, email, user_id)."""
    email = f"test-{uuid.uuid4().hex[:12]}@zefiro.test"
    body = json.dumps({"email": email, "password": "senha123"}).encode()
    rq = urllib.request.Request(
        BASE + "/auth/register", data=body,
        headers={"Content-Type": "application/json"})
    resp = json.loads(urllib.request.urlopen(rq, timeout=15).read())
    return resp["token"], email, resp["user"]["id"]


def get_token() -> str:
    """Token de um usuário de teste compartilhado (cacheado por sessão pytest)."""
    if "token" not in _cache:
        _cache["token"], _, _ = register_user()
    return _cache["token"]


def auth_headers() -> dict:
    return {"Authorization": f"Bearer {get_token()}"}
