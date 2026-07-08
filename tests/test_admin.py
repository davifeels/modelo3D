"""Painel administrativo: login separado, listagem/busca de clientes, senhas,
envio de credenciais (com log de e-mail), bloqueio e histórico.

Requer ADMIN_EMAIL/ADMIN_PASSWORD no ambiente do pytest (iguais aos do
servidor) e servidor com ZS_DEV_BILLING=1 — auto-skip caso contrário.
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
    data = json.dumps(body).encode() if body is not None else None
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


@pytest.fixture(scope="module")
def admin_headers():
    _skip_if_no_server()
    email = os.environ.get("ADMIN_EMAIL")
    password = os.environ.get("ADMIN_PASSWORD")
    if not email or not password:
        pytest.skip("ADMIN_EMAIL/ADMIN_PASSWORD não definidos no ambiente")
    resp, code = _req("POST", "/admin/login", {"email": email, "password": password})
    if code != 200:
        pytest.skip("Login admin falhou — credenciais do ambiente diferem do servidor")
    return {"Authorization": f"Bearer {resp['token']}"}


def _new_client():
    """Compra um acesso e devolve (user_id_admin_row, email, senha)."""
    email, senha, _ = apiauth.buy_user("essencial", "mensal")
    return email, senha


def _find_user(admin_headers, email):
    res, code = _req("GET", f"/admin/users?q={email}&field=email",
                     headers=admin_headers)
    assert code == 200 and res["total"] == 1, f"cliente {email} não encontrado"
    return res["users"][0]


class TestAdminAuth:
    def test_login_errado_401(self):
        _, code = _req("POST", "/admin/login",
                       {"email": "x@x.com", "password": "errada"})
        assert code == 401

    def test_me(self, admin_headers):
        me, code = _req("GET", "/admin/me", headers=admin_headers)
        assert code == 200 and me["admin"]["role"] in ("owner", "admin")

    def test_token_admin_nao_abre_endpoints_de_cliente(self, admin_headers):
        """Separação de permissões nos dois sentidos."""
        _, code = _req("GET", "/auth/me", headers=admin_headers)
        assert code == 401


class TestListagemEBusca:
    def test_lista_clientes_com_todas_as_colunas(self, admin_headers):
        email, _ = _new_client()
        row = _find_user(admin_headers, email)
        # Colunas exigidas pelo briefing do painel
        for col in ("nome", "email", "telefone", "plano", "data_compra",
                    "status", "codigo_acesso", "temp_password",
                    "ultimo_login", "data_envio_acesso"):
            assert col in row

    def test_busca_por_nome_email_telefone(self, admin_headers):
        from urllib.parse import quote
        email, _ = _new_client()
        # por e-mail (campo específico)
        assert _find_user(admin_headers, email)["email"] == email
        # por nome (todos os campos; nome tem acento → percent-encoding)
        res, _ = _req("GET", f"/admin/users?q={quote('Usuário de Teste')}",
                      headers=admin_headers)
        assert res["total"] >= 1
        # por telefone
        res, _ = _req("GET", "/admin/users?q=99999-0000&field=telefone",
                      headers=admin_headers)
        assert res["total"] >= 1

    def test_busca_sem_resultado(self, admin_headers):
        res, code = _req("GET", f"/admin/users?q=inexistente-{uuid.uuid4().hex}",
                         headers=admin_headers)
        assert code == 200 and res["total"] == 0


class TestCriarUsuario:
    """Criação manual de cliente pelo painel (POST /admin/users) — exceção
    controlada à regra 'acesso só nasce da compra'."""

    def _payload(self, **extra):
        return {"nome": "Cliente Manual",
                "email": f"manual-{uuid.uuid4().hex[:10]}@teste.zefiro",
                "telefone": "(11) 98888-7777", **extra}

    def test_criar_gera_credenciais_e_login_funciona(self, admin_headers):
        body = self._payload()
        res, code = _req("POST", "/admin/users", body, headers=admin_headers)
        assert code == 200 and res["ok"]
        assert res["temp_password"]
        assert res["user"]["codigo_acesso"].startswith("ZS-")

        # Aparece na listagem do painel
        row = _find_user(admin_headers, body["email"])
        assert row["nome"] == "Cliente Manual"

        # Credenciais geradas funcionam no login de cliente
        _, code = _req("POST", "/auth/login",
                       {"email": body["email"], "password": res["temp_password"]})
        assert code == 200

    def test_criar_com_plano_ativa_assinatura(self, admin_headers):
        body = self._payload(plano="pro", periodo="mensal")
        res, code = _req("POST", "/admin/users", body, headers=admin_headers)
        assert code == 200

        login, _ = _req("POST", "/auth/login",
                        {"email": body["email"], "password": res["temp_password"]})
        me, code = _req("GET", "/billing/me",
                        headers={"Authorization": f"Bearer {login['token']}"})
        assert code == 200
        assert me["plan"] == "pro" and me["status"] == "active"

    def test_sem_plano_cai_no_paywall(self, admin_headers):
        body = self._payload()
        res, _ = _req("POST", "/admin/users", body, headers=admin_headers)
        login, _ = _req("POST", "/auth/login",
                        {"email": body["email"], "password": res["temp_password"]})
        me, code = _req("GET", "/billing/me",
                        headers={"Authorization": f"Bearer {login['token']}"})
        assert code == 200
        assert me["status"] in (None, "none", "expired", "canceled") or not me.get("plan")

    def test_email_duplicado_409(self, admin_headers):
        body = self._payload()
        _, code = _req("POST", "/admin/users", body, headers=admin_headers)
        assert code == 200
        _, code = _req("POST", "/admin/users", body, headers=admin_headers)
        assert code == 409

    def test_validacoes_422(self, admin_headers):
        _, code = _req("POST", "/admin/users", self._payload(email="invalido"),
                       headers=admin_headers)
        assert code == 422
        _, code = _req("POST", "/admin/users", self._payload(telefone="abc"),
                       headers=admin_headers)
        assert code == 422
        _, code = _req("POST", "/admin/users", self._payload(plano="mega"),
                       headers=admin_headers)
        assert code == 422

    def test_sem_token_admin_401(self):
        _, code = _req("POST", "/admin/users",
                       {"nome": "X Y", "email": "x@y.com"})
        assert code == 401

    def test_acao_no_log_administrativo(self, admin_headers):
        _req("POST", "/admin/users", self._payload(), headers=admin_headers)
        logs, _ = _req("GET", "/admin/logs", headers=admin_headers)
        assert "criar_usuario" in [l["acao"] for l in logs["logs"]]


class TestSenhas:
    def test_resetar_gera_temporaria_que_funciona(self, admin_headers):
        email, senha_antiga = _new_client()
        row = _find_user(admin_headers, email)
        res, code = _req("POST", f"/admin/users/{row['id']}/password", {},
                         headers=admin_headers)
        assert code == 200 and res["temp_password"]

        # Antiga morre, nova funciona
        _, code = _req("POST", "/auth/login", {"email": email, "password": senha_antiga})
        assert code == 401
        _, code = _req("POST", "/auth/login",
                       {"email": email, "password": res["temp_password"]})
        assert code == 200

    def test_definir_senha_especifica(self, admin_headers):
        email, _ = _new_client()
        row = _find_user(admin_headers, email)
        _, code = _req("POST", f"/admin/users/{row['id']}/password",
                       {"password": "NovaSenha#2026"}, headers=admin_headers)
        assert code == 200
        _, code = _req("POST", "/auth/login",
                       {"email": email, "password": "NovaSenha#2026"})
        assert code == 200

    def test_senha_curta_422(self, admin_headers):
        email, _ = _new_client()
        row = _find_user(admin_headers, email)
        _, code = _req("POST", f"/admin/users/{row['id']}/password",
                       {"password": "123"}, headers=admin_headers)
        assert code == 422


class TestEnviarAcesso:
    def test_envia_e_registra_log(self, admin_headers):
        """Botão "Enviar acesso": e-mail + log em email_logs + histórico."""
        email, _ = _new_client()
        row = _find_user(admin_headers, email)
        res, code = _req("POST", f"/admin/users/{row['id']}/send-access",
                         headers=admin_headers)
        assert code == 200
        assert res["email_status"] in ("enviado", "simulado")

        # Histórico: envio aparece com assunto e status
        hist, _ = _req("GET", f"/admin/users/{row['id']}/history",
                       headers=admin_headers)
        assert len(hist["emails"]) >= 1
        assert "acesso" in hist["emails"][0]["assunto"].lower()
        # E a data do envio aparece na listagem
        row2 = _find_user(admin_headers, email)
        assert row2["data_envio_acesso"] is not None

    def test_acao_fica_no_log_administrativo(self, admin_headers):
        email, _ = _new_client()
        row = _find_user(admin_headers, email)
        _req("POST", f"/admin/users/{row['id']}/send-access", headers=admin_headers)
        logs, code = _req("GET", "/admin/logs", headers=admin_headers)
        assert code == 200
        acoes = [l["acao"] for l in logs["logs"]]
        assert "enviar_acesso" in acoes


class TestBloqueio:
    def test_bloquear_impede_login_e_desbloquear_restaura(self, admin_headers):
        email, senha = _new_client()
        row = _find_user(admin_headers, email)

        _, code = _req("POST", f"/admin/users/{row['id']}/status",
                       {"status": "bloqueado"}, headers=admin_headers)
        assert code == 200
        _, code = _req("POST", "/auth/login", {"email": email, "password": senha})
        assert code == 403

        _, code = _req("POST", f"/admin/users/{row['id']}/status",
                       {"status": "ativo"}, headers=admin_headers)
        assert code == 200
        _, code = _req("POST", "/auth/login", {"email": email, "password": senha})
        assert code == 200

    def test_status_invalido_422(self, admin_headers):
        email, _ = _new_client()
        row = _find_user(admin_headers, email)
        _, code = _req("POST", f"/admin/users/{row['id']}/status",
                       {"status": "banido"}, headers=admin_headers)
        assert code == 422


class TestHistorico:
    def test_historico_completo(self, admin_headers):
        """Histórico exigido: compra, envio de acesso, último login, status."""
        email, senha = _new_client()
        row = _find_user(admin_headers, email)
        _req("POST", f"/admin/users/{row['id']}/send-access", headers=admin_headers)
        _req("POST", "/auth/login", {"email": email, "password": senha})

        hist, code = _req("GET", f"/admin/users/{row['id']}/history",
                          headers=admin_headers)
        assert code == 200
        assert len(hist["compras"]) == 1
        assert hist["compras"][0]["plano"] == "essencial"
        assert hist["compras"][0]["status_pagamento"] in ("aprovado", "aprovado_simulado")
        assert len(hist["emails"]) >= 1
        assert hist["user"]["ultimo_login"] is not None
        assert hist["assinatura"]["status"] == "active"

    def test_cliente_inexistente_404(self, admin_headers):
        _, code = _req("GET", "/admin/users/nao-existe/history",
                       headers=admin_headers)
        assert code == 404
