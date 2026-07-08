"""Helper de autenticação para os testes de API/E2E.

Todos os endpoints do backend exigem `Authorization: Bearer <token>` e NÃO
existe registro público: contas nascem da COMPRA (POST /api/purchase). Este
módulo compra um acesso Pro para usuários de teste descartáveis — o servidor
precisa de ZS_DEV_BILLING=1 para devolver `dev_credentials` na resposta
(padrão no docker-compose e no dev local).

O usuário cacheado (get_token/auth_headers) é Pro mensal — fatiamento
ilimitado — então os testes de malha rodam sem esbarrar na quota do Essencial.
"""
import json
import urllib.request
import uuid

BASE = "http://localhost:8000/api"
_cache: dict = {}


def _post(path, body):
    rq = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(rq, timeout=30).read())


def _get(path, token):
    rq = urllib.request.Request(
        BASE + path, headers={"Authorization": f"Bearer {token}"})
    return json.loads(urllib.request.urlopen(rq, timeout=30).read())


def buy_user(plano="pro", periodo="mensal"):
    """Compra um acesso NOVO e retorna (email, senha, codigo_acesso)."""
    email = f"test-{uuid.uuid4().hex[:12]}@zefiro.test"
    resp = _post("/purchase", {
        "nome": "Usuário de Teste", "email": email,
        "telefone": "(11) 99999-0000", "plano": plano, "periodo": periodo})
    creds = resp.get("dev_credentials")
    if not creds:
        raise RuntimeError(
            "POST /api/purchase não devolveu dev_credentials — "
            "o servidor precisa de ZS_DEV_BILLING=1")
    return creds["email"], creds["senha"], creds["codigo_acesso"]


def register_user(plano="pro", periodo="mensal"):
    """Compra + login. Retorna (token, email, user_id) — assinatura mantida
    da era do /auth/register para não tocar nos testes antigos."""
    email, senha, _ = buy_user(plano, periodo)
    login = _post("/auth/login", {"email": email, "password": senha})
    token = login["token"]
    user_id = login["user"]["id"]
    return token, email, user_id


def get_token() -> str:
    """Token de um usuário de teste compartilhado (cacheado por sessão pytest)."""
    if "token" not in _cache:
        _cache["token"], _, _ = register_user()
    return _cache["token"]


def auth_headers() -> dict:
    return {"Authorization": f"Bearer {get_token()}"}
