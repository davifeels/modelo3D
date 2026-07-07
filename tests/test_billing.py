"""Billing: catálogo, trial, quota de 25 fatiamentos/mês, webhook e cancelamento.

Servidor em localhost:8000. Os testes de quota usam os endpoints /billing/dev/*
(habilitados com ZS_DEV_BILLING=1 — padrão no docker-compose e no dev local);
sem eles, os testes que dependem disso auto-skippam.
"""
import json
import os
import tempfile
import urllib.error
import urllib.request
import uuid

import pytest
import trimesh

import apiauth

BASE = "http://localhost:8000/api"


def _req(method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body else None
    hdrs = {"Content-Type": "application/json"} if data else {}
    hdrs.update(headers or {})
    rq = urllib.request.Request(BASE + path, data=data, method=method, headers=hdrs)
    try:
        resp = urllib.request.urlopen(rq, timeout=60)
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


def _hdrs(token):
    return {"Authorization": f"Bearer {token}"}


def _dev_or_skip(resp, code):
    if code == 404:
        pytest.skip("ZS_DEV_BILLING desabilitado no servidor")
    return resp, code


def _upload_sphere(token) -> str:
    mesh = trimesh.creation.icosphere(subdivisions=2)
    with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as f:
        mesh.export(f.name, file_type="stl")
        tmp = f.name
    stl = open(tmp, "rb").read()
    os.unlink(tmp)
    bd = b'Content-Disposition: form-data; name="file"; filename="quota.stl"'
    body = b"--b\r\n" + bd + b"\r\n\r\n" + stl + b"\r\n--b--\r\n"
    rq = urllib.request.Request(
        BASE + "/upload", data=body,
        headers={"Content-Type": "multipart/form-data; boundary=b", **_hdrs(token)})
    return json.loads(urllib.request.urlopen(rq, timeout=60).read())["session_id"]


def _cut(token, sid):
    return _req("POST", "/cut", {"session_id": sid, "part_idx": 0, "axis": "z", "position": 0.0},
                headers=_hdrs(token))


class TestCatalogo:
    def test_plans_publico(self):
        resp, code = _req("GET", "/billing/plans")
        assert code == 200
        assert resp["plans"]["essencial"]["slice_limit"] == 25
        assert resp["plans"]["pro"]["slice_limit"] is None
        assert resp["plans"]["essencial"]["monthly_cents"] == 1990
        assert resp["plans"]["pro"]["annual_cents"] == 44990
        assert resp["trial_days"] == 7


class TestCheckout:
    def test_sem_gateway_501(self):
        token, _, _ = apiauth.register_user()
        _, code = _req("POST", "/billing/checkout",
                       {"plano": "pro", "periodo": "anual", "payment_method": "card"},
                       headers=_hdrs(token))
        assert code == 501  # gateway_nao_configurado — frontend mostra aviso

    def test_pix_apenas_no_anual(self):
        token, _, _ = apiauth.register_user()
        resp, code = _req("POST", "/billing/checkout",
                          {"plano": "pro", "periodo": "mensal", "payment_method": "pix"},
                          headers=_hdrs(token))
        assert code == 422
        assert "pix_boleto_apenas_anual" in json.dumps(resp)

    def test_plano_invalido_422(self):
        token, _, _ = apiauth.register_user()
        _, code = _req("POST", "/billing/checkout",
                       {"plano": "mega", "periodo": "mensal"}, headers=_hdrs(token))
        assert code == 422


class TestQuotaEssencial:
    """A regra central: Essencial fatia 25 arquivos/mês; Pro é ilimitado."""

    def test_limite_25_bloqueia_e_upgrade_libera(self):
        token, _, _ = apiauth.register_user()
        # Vira Essencial (simula ativação do gateway) e enche o contador do mês
        resp, code = _req("POST", "/billing/dev/activate",
                          {"plano": "essencial", "periodo": "mensal"}, headers=_hdrs(token))
        _dev_or_skip(resp, code)
        assert code == 200 and resp["plan"] == "essencial"
        assert resp["usage"]["limit"] == 25

        _req("POST", "/billing/dev/set-usage", {"count": 25}, headers=_hdrs(token))

        sid = _upload_sphere(token)
        resp, code = _cut(token, sid)
        assert code == 402
        assert "limite_de_fatiamentos_atingido" in json.dumps(resp)

        # Upgrade para Pro → mesmo corte passa
        _req("POST", "/billing/dev/activate", {"plano": "pro", "periodo": "mensal"},
             headers=_hdrs(token))
        _, code = _cut(token, sid)
        assert code == 200

    def test_recorte_do_mesmo_arquivo_nao_consome_quota(self):
        token, _, _ = apiauth.register_user()
        resp, code = _req("POST", "/billing/dev/activate",
                          {"plano": "essencial", "periodo": "mensal"}, headers=_hdrs(token))
        _dev_or_skip(resp, code)
        _req("POST", "/billing/dev/set-usage", {"count": 24}, headers=_hdrs(token))

        sid = _upload_sphere(token)
        _, code = _cut(token, sid)            # 25º arquivo do mês — permitido
        assert code == 200
        me, _ = _req("GET", "/billing/me", headers=_hdrs(token))
        assert me["usage"]["used"] == 25

        # Re-cortar o MESMO arquivo não conta como 26º
        _, code = _req("POST", "/cut", {"session_id": sid, "part_idx": 0,
                                        "axis": "x", "position": 0.0}, headers=_hdrs(token))
        assert code == 200

        # Mas um arquivo NOVO é bloqueado
        sid2 = _upload_sphere(token)
        _, code = _cut(token, sid2)
        assert code == 402

    def test_sem_assinatura_402(self):
        token, _, _ = apiauth.register_user()
        resp, code = _req("POST", "/billing/dev/expire", {}, headers=_hdrs(token))
        _dev_or_skip(resp, code)
        assert resp["has_access"] is False

        sid = _upload_sphere(token)   # upload ainda funciona (leitura)
        _, code = _cut(token, sid)    # fatiar não
        assert code == 402


class TestWebhook:
    def test_webhook_ativa_assinatura(self):
        secret = "test-secret"
        token, _, uid = apiauth.register_user()
        evt = {"event_id": f"evt-{uuid.uuid4().hex[:10]}", "type": "subscription.activated",
               "user_id": uid, "plan": "essencial", "periodo": "anual"}
        resp, code = _req("POST", "/billing/webhook", evt,
                          headers={"X-Webhook-Secret": secret})
        if code == 501:
            pytest.skip("WEBHOOK_SECRET não configurado no servidor")
        assert code == 200
        me, _ = _req("GET", "/billing/me", headers=_hdrs(token))
        assert me["status"] == "active"
        assert me["plan"] == "essencial" and me["periodo"] == "anual"

    def test_webhook_assinatura_errada_401(self):
        _, _, uid = apiauth.register_user()
        evt = {"event_id": "evt-x", "type": "subscription.activated",
               "user_id": uid, "plan": "pro", "periodo": "mensal"}
        _, code = _req("POST", "/billing/webhook", evt,
                       headers={"X-Webhook-Secret": "segredo-errado"})
        if code == 501:
            pytest.skip("WEBHOOK_SECRET não configurado no servidor")
        assert code == 401

    def test_webhook_idempotente(self):
        token, _, uid = apiauth.register_user()
        eid = f"evt-{uuid.uuid4().hex[:10]}"
        evt = {"event_id": eid, "type": "subscription.activated",
               "user_id": uid, "plan": "pro", "periodo": "mensal"}
        resp, code = _req("POST", "/billing/webhook", evt, headers={"X-Webhook-Secret": "test-secret"})
        if code == 501:
            pytest.skip("WEBHOOK_SECRET não configurado no servidor")
        assert code == 200 and not resp.get("duplicate")
        resp, code = _req("POST", "/billing/webhook", evt, headers={"X-Webhook-Secret": "test-secret"})
        assert code == 200 and resp.get("duplicate") is True


class TestCancelamento:
    def test_cancelar_trial_encerra_acesso(self):
        token, _, _ = apiauth.register_user()
        resp, code = _req("POST", "/billing/cancel", {}, headers=_hdrs(token))
        assert code == 200
        me, _ = _req("GET", "/billing/me", headers=_hdrs(token))
        assert me["has_access"] is False
        assert me["read_only_until"] is not None  # 30 dias de leitura

    def test_cancelar_anual_no_inicio_tem_reembolso(self):
        token, _, _ = apiauth.register_user()
        resp, code = _req("POST", "/billing/dev/activate",
                          {"plano": "pro", "periodo": "anual"}, headers=_hdrs(token))
        _dev_or_skip(resp, code)
        resp, code = _req("POST", "/billing/cancel", {}, headers=_hdrs(token))
        assert code == 200
        # Ativado agora mesmo → reembolso ~integral (proporcional a 365 dias)
        assert resp["refund_cents"] > 40000

    def test_cancelar_mensal_mantem_acesso_ate_fim_do_periodo(self):
        token, _, _ = apiauth.register_user()
        resp, code = _req("POST", "/billing/dev/activate",
                          {"plano": "essencial", "periodo": "mensal"}, headers=_hdrs(token))
        _dev_or_skip(resp, code)
        resp, code = _req("POST", "/billing/cancel", {}, headers=_hdrs(token))
        assert code == 200
        assert resp["refund_cents"] == 0
        me, _ = _req("GET", "/billing/me", headers=_hdrs(token))
        assert me["status"] == "canceled"
        assert me["has_access"] is True  # acesso segue até current_period_end

    def test_cancelar_sem_assinatura_409(self):
        token, _, _ = apiauth.register_user()
        _req("POST", "/billing/cancel", {}, headers=_hdrs(token))
        _, code = _req("POST", "/billing/cancel", {}, headers=_hdrs(token))
        assert code == 409


class TestTrocaDePlano:
    def test_upgrade_com_proracao(self):
        token, _, _ = apiauth.register_user()
        resp, code = _req("POST", "/billing/dev/activate",
                          {"plano": "essencial", "periodo": "mensal"}, headers=_hdrs(token))
        _dev_or_skip(resp, code)
        resp, code = _req("POST", "/billing/change-plan",
                          {"plano": "pro", "periodo": "mensal"}, headers=_hdrs(token))
        assert code == 200
        # Crédito do Essencial recém-pago abate o preço do Pro
        assert 0 < resp["charged_cents"] <= 4990
        assert resp["prorated_credit_cents"] > 0
        me, _ = _req("GET", "/billing/me", headers=_hdrs(token))
        assert me["plan"] == "pro"
