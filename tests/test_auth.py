"""Autenticação: login (SEM registro público), esqueci a senha, tokens e
proteção de TODOS os endpoints.

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


class TestSemRegistro:
    """REQUISITO central da refatoração: NÃO existe criação manual de conta."""

    def test_endpoint_de_registro_nao_existe(self):
        _, code = _req("POST", "/auth/register",
                       {"email": _new_email(), "password": "senha123"})
        assert code in (404, 405)

    def test_conta_nasce_da_compra(self):
        """A única porta de entrada: compra → conta automática → login."""
        email, senha, codigo = apiauth.buy_user("pro", "mensal")
        assert codigo.startswith("ZS-")
        resp, code = _req("POST", "/auth/login", {"email": email, "password": senha})
        assert code == 200 and resp["token"]
        me, code = _req("GET", "/billing/me",
                        headers={"Authorization": f"Bearer {resp['token']}"})
        assert code == 200
        assert me["status"] == "active"
        assert me["plan"] == "pro"
        assert me["has_access"] is True
        assert me["usage"]["limit"] is None  # Pro: ilimitado


class TestLogin:
    def test_login_ok(self):
        email, senha, _ = apiauth.buy_user()
        resp, code = _req("POST", "/auth/login", {"email": email, "password": senha})
        assert code == 200 and resp["token"]

    def test_senha_errada_401(self):
        email, _, _ = apiauth.buy_user()
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


class TestEsqueciMinhaSenha:
    def test_resposta_generica_para_qualquer_email(self):
        """Não pode revelar se o e-mail existe (enumeração de contas)."""
        email, _, _ = apiauth.buy_user()
        r1, c1 = _req("POST", "/auth/forgot-password", {"email": email})
        r2, c2 = _req("POST", "/auth/forgot-password", {"email": _new_email()})
        assert c1 == c2 == 200
        assert r1["message"] == r2["message"]

    def test_forgot_NAO_tranca_a_conta_da_vitima(self):
        """Correção de segurança: pedir 'esqueci a senha' NÃO troca a senha —
        senão qualquer um trancaria a conta de outro só sabendo o e-mail."""
        email, senha, _ = apiauth.buy_user()
        _req("POST", "/auth/forgot-password", {"email": email})
        # A senha ORIGINAL continua valendo (só o link do e-mail pode trocá-la)
        _, code = _req("POST", "/auth/login", {"email": email, "password": senha})
        assert code == 200

    def test_reset_por_token_troca_a_senha_e_e_single_use(self):
        email, senha, _ = apiauth.buy_user()
        r, _ = _req("POST", "/auth/forgot-password", {"email": email})
        token = r.get("dev_reset_token")
        assert token, "servidor precisa de ZS_DEV_BILLING=1 para devolver o token"

        nova = "NovaSenhaForte#2026"
        _, code = _req("POST", "/auth/reset-password",
                       {"token": token, "password": nova})
        assert code == 200
        # Antiga morre, nova funciona
        _, code = _req("POST", "/auth/login", {"email": email, "password": senha})
        assert code == 401
        _, code = _req("POST", "/auth/login", {"email": email, "password": nova})
        assert code == 200
        # Token é de uso único
        _, code = _req("POST", "/auth/reset-password",
                       {"token": token, "password": "OutraSenha#2026"})
        assert code == 400

    def test_reset_token_invalido_400(self):
        _, code = _req("POST", "/auth/reset-password",
                       {"token": "nao-existe", "password": "QualquerSenha#1"})
        assert code == 400

    def test_reset_senha_curta_422(self):
        email, _, _ = apiauth.buy_user()
        r, _ = _req("POST", "/auth/forgot-password", {"email": email})
        _, code = _req("POST", "/auth/reset-password",
                       {"token": r.get("dev_reset_token"), "password": "curta"})
        assert code == 422


class TestRevogacaoDeSessao:
    """Reset/troca de senha invalida tokens JWT emitidos antes (token_version)."""

    def test_reset_derruba_token_antigo(self):
        email, senha, _ = apiauth.buy_user()
        login, _ = _req("POST", "/auth/login", {"email": email, "password": senha})
        token_antigo = login["token"]
        # Sessão antiga funciona
        _, code = _req("GET", "/auth/me",
                       headers={"Authorization": f"Bearer {token_antigo}"})
        assert code == 200
        # Redefine a senha por token
        r, _ = _req("POST", "/auth/forgot-password", {"email": email})
        _req("POST", "/auth/reset-password",
             {"token": r["dev_reset_token"], "password": "NovaSenha#2026"})
        # O token antigo agora é recusado
        _, code = _req("GET", "/auth/me",
                       headers={"Authorization": f"Bearer {token_antigo}"})
        assert code == 401


class TestAdminSeed:
    """Conta do dono (bootstrap.py): ADMIN_EMAIL/ADMIN_PASSWORD do ambiente
    criam admin do painel E conta de cliente Pro. Skip se o ambiente de teste
    não tiver as credenciais (devem bater com as do servidor alvo)."""

    def _creds(self):
        email = os.environ.get("ADMIN_EMAIL")
        password = os.environ.get("ADMIN_PASSWORD")
        if not email or not password:
            pytest.skip("ADMIN_EMAIL/ADMIN_PASSWORD não definidos no ambiente")
        return email, password

    def test_admin_login_cliente_e_pro_ativo(self):
        email, password = self._creds()
        resp, code = _req("POST", "/auth/login", {"email": email, "password": password})
        assert code == 200 and resp["token"]
        hdrs = {"Authorization": f"Bearer {resp['token']}"}
        me, code = _req("GET", "/billing/me", headers=hdrs)
        assert code == 200
        assert me["plan"] == "pro" and me["status"] == "active"
        assert me["has_access"] is True

    def test_admin_login_painel(self):
        email, password = self._creds()
        resp, code = _req("POST", "/admin/login", {"email": email, "password": password})
        assert code == 200 and resp["token"]
        assert resp["admin"]["role"] == "owner"


class TestProtecaoEndpoints:
    """TODOS os endpoints de malha/exportação/billing/admin exigem token."""

    @pytest.mark.parametrize("method,path,body", [
        ("POST", "/suggest-cuts", {"session_id": "x", "part_idx": 0, "n_results": 3}),
        ("POST", "/cut", {"session_id": "x", "part_idx": 0, "axis": "z", "position": 0}),
        ("POST", "/cut-from-painted", {"session_id": "x", "part_idx": 0, "painted_face_indices": [1]}),
        ("GET", "/session/qualquer", None),
        ("GET", "/mesh/qualquer/0", None),
        ("GET", "/export/qualquer/0/stl", None),
        ("GET", "/billing/me", None),
        ("GET", "/admin/users", None),
    ])
    def test_sem_token_401(self, method, path, body):
        _, code = _req(method, path, body)
        assert code == 401

    def test_token_invalido_401(self):
        _, code = _req("GET", "/auth/me", headers={"Authorization": "Bearer abc.def.ghi"})
        assert code == 401

    def test_token_de_cliente_nao_abre_o_admin(self):
        """Separação de permissões: JWT de cliente ≠ JWT de admin."""
        token = apiauth.get_token()
        _, code = _req("GET", "/admin/users",
                       headers={"Authorization": f"Bearer {token}"})
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
