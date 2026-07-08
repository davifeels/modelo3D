"""Compra de acesso (POST /api/purchase): cadastro automático, renovação,
validações e catálogo público.

Servidor em localhost:8000 com ZS_DEV_BILLING=1 (auto-skip caso contrário).
"""
import json
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
    return f"buy-{uuid.uuid4().hex[:12]}@zefiro.test"


def _buy(email, plano="essencial", periodo="mensal", nome="Cliente Compra",
         telefone="(11) 98888-7777"):
    return _req("POST", "/purchase", {"nome": nome, "email": email,
                                      "telefone": telefone, "plano": plano,
                                      "periodo": periodo})


class TestCatalogo:
    def test_products_publico(self):
        resp, code = _req("GET", "/purchase/products")
        assert code == 200
        assert resp["plans"]["essencial"]["slice_limit"] == 25
        assert resp["plans"]["pro"]["slice_limit"] is None
        assert set(resp["periodos"]) == {"mensal", "anual"}


class TestCompraNova:
    def test_compra_cria_conta_automaticamente(self):
        """Requisito: registro automático com senha temporária + código."""
        email = _new_email()
        resp, code = _buy(email, "essencial", "mensal")
        assert code == 200
        assert resp["ok"] is True and resp["renewed"] is False
        assert resp["amount_cents"] == 1990
        creds = resp["dev_credentials"]  # exige ZS_DEV_BILLING=1
        assert creds["email"] == email
        assert len(creds["senha"]) >= 8
        assert creds["codigo_acesso"].startswith("ZS-")

        # As credenciais geradas FUNCIONAM no login
        login, code = _req("POST", "/auth/login",
                           {"email": email, "password": creds["senha"]})
        assert code == 200
        hdrs = {"Authorization": f"Bearer {login['token']}"}
        me, _ = _req("GET", "/billing/me", headers=hdrs)
        assert me["plan"] == "essencial" and me["status"] == "active"
        assert me["usage"]["limit"] == 25

    def test_compra_anual_pro(self):
        resp, code = _buy(_new_email(), "pro", "anual")
        assert code == 200
        assert resp["amount_cents"] == 44990

    def test_email_repetido_e_renovacao_sem_novas_credenciais(self):
        """Comprar de novo com o mesmo e-mail renova o acesso — a senha
        existente continua valendo e nenhuma credencial nova é gerada."""
        email = _new_email()
        r1, _ = _buy(email, "essencial", "mensal")
        senha = r1["dev_credentials"]["senha"]

        r2, code = _buy(email, "pro", "anual")
        assert code == 200
        assert r2["renewed"] is True
        assert "dev_credentials" not in r2

        login, code = _req("POST", "/auth/login", {"email": email, "password": senha})
        assert code == 200
        me, _ = _req("GET", "/billing/me",
                     headers={"Authorization": f"Bearer {login['token']}"})
        assert me["plan"] == "pro" and me["periodo"] == "anual"


class TestValidacoes:
    def test_plano_invalido_422(self):
        _, code = _buy(_new_email(), plano="mega")
        assert code == 422

    def test_periodo_invalido_422(self):
        _, code = _buy(_new_email(), periodo="semanal")
        assert code == 422

    def test_email_invalido_422(self):
        _, code = _buy("nao-e-email")
        assert code == 422

    def test_telefone_invalido_422(self):
        _, code = _buy(_new_email(), telefone="abc")
        assert code == 422

    def test_nome_curto_422(self):
        _, code = _buy(_new_email(), nome="A")
        assert code == 422


class TestHistoricoDeCompras:
    def test_compras_aparecem_no_historico_do_admin(self):
        """Fluxo final: compra → cliente aparece no painel administrativo."""
        import os
        admin_email = os.environ.get("ADMIN_EMAIL")
        admin_pass = os.environ.get("ADMIN_PASSWORD")
        if not admin_email or not admin_pass:
            pytest.skip("ADMIN_EMAIL/ADMIN_PASSWORD não definidos no ambiente")
        email = _new_email()
        _buy(email, "pro", "mensal")

        login, _ = _req("POST", "/admin/login",
                        {"email": admin_email, "password": admin_pass})
        hdrs = {"Authorization": f"Bearer {login['token']}"}
        res, code = _req("GET", f"/admin/users?q={email}&field=email", headers=hdrs)
        assert code == 200 and res["total"] == 1
        row = res["users"][0]
        assert row["email"] == email
        assert row["plano"] == "pro"
        assert row["telefone"] == "(11) 98888-7777"
        assert row["status"] == "ativo"
        assert row["codigo_acesso"].startswith("ZS-")
        assert row["temp_password"]      # senha temporária visível ao admin
        assert row["data_compra"] is not None
