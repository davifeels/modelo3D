"""Integração com o Mercado Pago (gateway.py).

- create_checkout roda contra a API REAL do MP (criar preferência não cobra
  nada) — requer MP_ACCESS_TOKEN no ambiente do pytest; auto-skip sem ele.
- A normalização de pagamento e a validação de assinatura são funções puras,
  testadas sem rede.

Rodar com o token:
    MP_ACCESS_TOKEN=APP_USR-... pytest tests/test_gateway_mp.py
"""
import hashlib
import hmac
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "web", "backend"))

import gateway as gw  # noqa: E402

MP_TOKEN = os.environ.get("MP_ACCESS_TOKEN")
requires_token = pytest.mark.skipif(not MP_TOKEN, reason="MP_ACCESS_TOKEN não definido")


# ── Funções puras (sem rede) ──────────────────────────────────────────────────

class TestNormalizacaoPagamento:
    def _payment(self, status):
        return {
            "id": 123456789, "status": status,
            "external_reference": "user-abc|pro|anual",
            "metadata": {}, "payer": {"id": 555},
        }

    def test_aprovado_ativa_assinatura(self):
        ev = gw._mp_payment_to_event(self._payment("approved"))
        assert ev["type"] == "subscription.activated"
        assert ev["user_id"] == "user-abc"
        assert ev["plan"] == "pro" and ev["periodo"] == "anual"
        assert ev["event_id"] == "mp:123456789:approved"
        assert ev["gateway_customer_id"] == "555"

    def test_reembolso_cancela(self):
        for st in ("refunded", "cancelled", "charged_back"):
            assert gw._mp_payment_to_event(self._payment(st))["type"] == "subscription.canceled"

    def test_rejeitado_e_pendente_falham(self):
        for st in ("rejected", "in_process", "pending"):
            assert gw._mp_payment_to_event(self._payment(st))["type"] == "payment.failed"

    def test_metadata_tem_prioridade_sobre_external_reference(self):
        p = self._payment("approved")
        p["metadata"] = {"user_id": "u2", "plan": "essencial", "periodo": "mensal"}
        ev = gw._mp_payment_to_event(p)
        assert ev["user_id"] == "u2" and ev["plan"] == "essencial"

    def test_event_id_difere_por_status(self):
        """Ativação e reembolso do mesmo pagamento não colidem na idempotência."""
        a = gw._mp_payment_to_event(self._payment("approved"))["event_id"]
        r = gw._mp_payment_to_event(self._payment("refunded"))["event_id"]
        assert a != r


class TestAssinaturaWebhook:
    def _gw(self, secret):
        os.environ["MP_ACCESS_TOKEN"] = "x"  # só para o __init__ não pular
        os.environ["MP_WEBHOOK_SECRET"] = secret
        return gw.MercadoPagoGateway()

    def test_assinatura_valida_passa(self):
        g = self._gw("segredo-teste")
        data_id, rid, ts = "999", "req-1", "1700000000"
        manifest = f"id:{data_id};request-id:{rid};ts:{ts};"
        v1 = hmac.new(b"segredo-teste", manifest.encode(), hashlib.sha256).hexdigest()
        headers = {"x-signature": f"ts={ts},v1={v1}", "x-request-id": rid}
        assert g._valid_signature(headers, data_id) is True

    def test_assinatura_errada_reprova(self):
        g = self._gw("segredo-teste")
        headers = {"x-signature": "ts=1700000000,v1=deadbeef", "x-request-id": "req-1"}
        assert g._valid_signature(headers, "999") is False

    def test_sem_secret_confia_no_lookup(self):
        g = self._gw("")
        assert g._valid_signature({}, "999") is True

    def teardown_method(self):
        os.environ.pop("MP_WEBHOOK_SECRET", None)


# ── Contra a API real do Mercado Pago ─────────────────────────────────────────

@requires_token
class TestCheckoutReal:
    def _gw(self):
        os.environ["MP_ACCESS_TOKEN"] = MP_TOKEN
        os.environ.pop("MP_WEBHOOK_SECRET", None)
        return gw.MercadoPagoGateway()

    def test_create_checkout_devolve_url(self):
        res = self._gw().create_checkout(
            user_id="user-teste", email="comprador@zefiro.test",
            plan="pro", periodo="mensal", pay_method="card", amount_cents=4990)
        assert res["checkout_url"].startswith("http")
        assert "mercadopago" in res["checkout_url"]
        assert res["gateway_ref"]

    def test_essencial_anual_tambem(self):
        res = self._gw().create_checkout(
            user_id="u", email="c@zefiro.test", plan="essencial",
            periodo="anual", pay_method="card", amount_cents=17990)
        assert res["checkout_url"].startswith("http")

    def test_webhook_pagamento_inexistente_400(self):
        """Notificação de payment com id que não existe → WebhookInvalid/erro."""
        import json
        g = self._gw()
        body = json.dumps({"type": "payment", "data": {"id": "1"}}).encode()
        with pytest.raises((gw.WebhookInvalid, gw.GatewayError)):
            g.verify_webhook({}, body)

    def test_webhook_topico_ignorado(self):
        import json
        g = self._gw()
        body = json.dumps({"type": "merchant_order", "data": {"id": "1"}}).encode()
        with pytest.raises(gw.WebhookInvalid):
            g.verify_webhook({}, body)
