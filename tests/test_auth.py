"""Autenticação: registro, login, tokens e proteção de TODOS os endpoints.

Servidor deve estar rodando em localhost:8000 (auto-skip caso contrário).
"""
import json
import os
import urllib.error
import urllib.request
import uuid

import pytest

import apiauth

BASE = "http://localhost:8000/api"


def _req(method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body else None
    hdrs = {"Content-Type": "application/json"} if data else {}
    hdrs.update(headers or {})
    rq = urllib.request.Request(BASE + path, data=data, method=method, headers=hdrs)
    try:
        resp = urllib.request.urlopen(rq, timeout=30)
        raw = resp.read()
        return (json.loads(raw) if raw else {}), resp.status
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return json.loads(raw), e.code
        except Exception:
            return {}, e.code


def _skip_if_no_server():
    try:
        urllib.request.urlopen("http://localhost:8000/health", timeout=2)
    except urllib.error.HTTPError:
        pass
    except Exception:
        pytest.skip("Servidor não está rodando em localhost:8000")


@pytest.fixture(autouse=True)
def require_server():
    _skip_if_no_server()


def _new_email():
    return f"auth-{uuid.uuid4().hex[:12]}@zefiro.test"


class TestRegistro:
    def test_registro_devolve_token_e_usuario(self):
        email = _new_email()
        resp, code = _req("POST", "/auth/register", {"email": email, "password": "senha123"})
        assert code == 200
        assert resp["token"]
        assert resp["user"]["email"] == email

    def test_email_duplicado_409(self):
        email = _new_email()
        _req("POST", "/auth/register", {"email": email, "password": "senha123"})
        _, code = _req("POST", "/auth/register", {"email": email, "password": "outra456"})
        assert code == 409

    def test_email_invalido_422(self):
        _, code = _req("POST", "/auth/register", {"email": "nao-e-email", "password": "senha123"})
        assert code == 422

    def test_senha_curta_422(self):
        _, code = _req("POST", "/auth/register", {"email": _new_email(), "password": "123"})
        assert code == 422

    def test_registro_inicia_trial_pro_7_dias(self):
        """Regra de negócio: usuário novo ganha 7 dias de Pro sem cartão."""
        token, _, _ = apiauth.register_user()
        me, code = _req("GET", "/billing/me", headers={"Authorization": f"Bearer {token}"})
        assert code == 200
        assert me["status"] == "trialing"
        assert me["plan"] == "pro"
        assert me["has_access"] is True
        assert me["usage"]["limit"] is None  # Pro: ilimitado


class TestLogin:
    def test_login_ok(self):
        email = _new_email()
        _req("POST", "/auth/register", {"email": email, "password": "senha123"})
        resp, code = _req("POST", "/auth/login", {"email": email, "password": "senha123"})
        assert code == 200 and resp["token"]

    def test_senha_errada_401(self):
        email = _new_email()
        _req("POST", "/auth/register", {"email": email, "password": "senha123"})
        _, code = _req("POST", "/auth/login", {"email": email, "password": "errada!"})
        assert code == 401

    def test_email_inexistente_401(self):
        _, code = _req("POST", "/auth/login", {"email": _new_email(), "password": "qualquer"})
        assert code == 401

    def test_me_com_token(self):
        token, email, _ = apiauth.register_user()
        me, code = _req("GET", "/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert code == 200
        assert me["user"]["email"] == email


class TestAdminSeed:
    """Conta do dono (bootstrap.py): ADMIN_EMAIL/ADMIN_PASSWORD do ambiente
    criam a conta no startup com Pro ativo. Skip se o ambiente de teste não
    tiver as credenciais (elas devem bater com as do servidor alvo)."""

    def test_admin_login_e_pro_ativo(self):
        email = os.environ.get("ADMIN_EMAIL")
        password = os.environ.get("ADMIN_PASSWORD")
        if not email or not password:
            pytest.skip("ADMIN_EMAIL/ADMIN_PASSWORD não definidos no ambiente")
        resp, code = _req("POST", "/auth/login", {"email": email, "password": password})
        assert code == 200 and resp["token"]
        hdrs = {"Authorization": f"Bearer {resp['token']}"}
        me, code = _req("GET", "/billing/me", headers=hdrs)
        assert code == 200
        assert me["plan"] == "pro" and me["status"] == "active"
        assert me["has_access"] is True
        assert me["usage"]["limit"] is None  # ilimitado


class TestProtecaoEndpoints:
    """TODOS os endpoints de malha/exportação exigem token."""

    @pytest.mark.parametrize("method,path,body", [
        ("POST", "/suggest-cuts", {"session_id": "x", "part_idx": 0, "n_results": 3}),
        ("POST", "/cut", {"session_id": "x", "part_idx": 0, "axis": "z", "position": 0}),
        ("POST", "/cut-from-painted", {"session_id": "x", "part_idx": 0, "painted_face_indices": [1]}),
        ("GET", "/session/qualquer", None),
        ("GET", "/mesh/qualquer/0", None),
        ("GET", "/export/qualquer/0/stl", None),
        ("GET", "/billing/me", None),
        ("POST", "/billing/checkout", {"plano": "pro", "periodo": "anual"}),
    ])
    def test_sem_token_401(self, method, path, body):
        _, code = _req(method, path, body)
        assert code == 401

    def test_token_invalido_401(self):
        _, code = _req("GET", "/auth/me", headers={"Authorization": "Bearer abc.def.ghi"})
        assert code == 401

    def test_upload_sem_token_401(self):
        body = b"--b\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a.stl\"\r\n\r\nxx\r\n--b--\r\n"
        rq = urllib.request.Request(
            BASE + "/upload", data=body,
            headers={"Content-Type": "multipart/form-data; boundary=b"})
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(rq, timeout=10)
        assert exc.value.code == 401

    def test_export_aceita_token_na_query(self):
        """Links <a href> de download não enviam headers — ?token= deve valer."""
        token = apiauth.get_token()
        # Sessão inexistente: com token válido na query o erro deve ser 404 (não 401)
        _, code = _req("GET", f"/session/nao-existe?token={token}")
        assert code == 404
