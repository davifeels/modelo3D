"""Interface do gateway de pagamento — o ponto ÚNICO a implementar para cobrar de verdade.

Como plugar um gateway real (Stripe, Mercado Pago, Hotmart, Kiwify):
  1. Crie uma classe que herde de PaymentGateway e implemente os 3 métodos.
  2. Registre-a em get_gateway() sob um nome (ex.: 'stripe').
  3. Defina PAYMENT_GATEWAY=stripe no ambiente (docker-compose).
O resto do sistema (checkout, webhook, cancelamento, ativação de plano no banco)
já está pronto e não precisa mudar.

Enquanto nenhum gateway está configurado:
  - POST /api/billing/checkout responde 501 (o frontend mostra aviso amigável);
  - o webhook aceita eventos assinados com WEBHOOK_SECRET (header X-Webhook-Secret),
    o que permite testar a ativação/cancelamento de ponta a ponta sem gateway.
"""
import hashlib
import hmac
import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod


class GatewayNotConfigured(Exception):
    pass


class WebhookInvalid(Exception):
    pass


class GatewayError(Exception):
    """Falha ao falar com o gateway (rede/HTTP) — vira 5xx no endpoint."""


class PaymentGateway(ABC):
    @abstractmethod
    def create_checkout(self, *, user_id: str, email: str, plan: str, periodo: str,
                        pay_method: str, amount_cents: int) -> dict:
        """Cria a sessão de pagamento e retorna {'checkout_url': str, 'gateway_ref': str}.

        Stripe:       stripe.checkout.Session.create(mode='subscription'|'payment', ...)
        Mercado Pago: preapproval (mensal) / preference (anual à vista)
        """

    @abstractmethod
    def cancel(self, gateway_subscription_id: str) -> None:
        """Cancela a assinatura recorrente no gateway (no-op para cobrança única anual)."""

    @abstractmethod
    def verify_webhook(self, headers: dict, body: bytes) -> dict:
        """Valida assinatura e NORMALIZA o evento para o formato interno:
            {
              'event_id': str,                 # p/ idempotência
              'type': 'subscription.activated' | 'subscription.canceled' | 'payment.failed',
              'user_id': str,
              'plan': 'essencial' | 'pro',     # nos eventos de ativação
              'periodo': 'mensal' | 'anual',
              'gateway_customer_id': str | None,
              'gateway_subscription_id': str | None,
            }
        Levante WebhookInvalid se a assinatura não bater.
        Stripe: stripe.Webhook.construct_event(body, headers['stripe-signature'], secret)
        """


class NullGateway(PaymentGateway):
    """Sem gateway: checkout indisponível; webhook aceita apenas eventos internos
    assinados com WEBHOOK_SECRET (útil para testes e homologação)."""

    def create_checkout(self, **kwargs) -> dict:
        raise GatewayNotConfigured()

    def cancel(self, gateway_subscription_id: str) -> None:
        return None

    def verify_webhook(self, headers: dict, body: bytes) -> dict:
        secret = os.environ.get("WEBHOOK_SECRET", "")
        if not secret:
            raise GatewayNotConfigured()
        got = headers.get("x-webhook-secret", "")
        if not hmac.compare_digest(got, secret):
            raise WebhookInvalid()
        try:
            evt = json.loads(body)
        except json.JSONDecodeError:
            raise WebhookInvalid()
        for field in ("event_id", "type", "user_id"):
            if field not in evt:
                raise WebhookInvalid()
        return evt


# ── Mercado Pago (Checkout Pro) ──────────────────────────────────────────────

_MP_API = "https://api.mercadopago.com"


def _mp_payment_to_event(payment: dict) -> dict:
    """Normaliza um pagamento do Mercado Pago para o evento interno.

    Função pura (sem rede) para ser testável isoladamente. O user_id/plan/
    periodo vêm do external_reference "user_id|plan|periodo" (com fallback no
    metadata). O event_id inclui o status para que ativação e reembolso do
    MESMO pagamento não colidam na idempotência (WebhookEvent)."""
    status = payment.get("status")
    ext = (payment.get("external_reference") or "").split("|")
    meta = payment.get("metadata") or {}
    has_ext = len(ext) == 3
    user_id = meta.get("user_id") or (ext[0] if has_ext else None)
    plan = meta.get("plan") or (ext[1] if has_ext else None)
    periodo = meta.get("periodo") or (ext[2] if has_ext else None)

    if status == "approved":
        etype = "subscription.activated"
    elif status in ("refunded", "cancelled", "charged_back"):
        etype = "subscription.canceled"
    else:  # rejected, in_process, pending, etc.
        etype = "payment.failed"

    payer_id = (payment.get("payer") or {}).get("id")
    return {
        "event_id": f"mp:{payment.get('id')}:{status}",
        "type": etype,
        "user_id": user_id,
        "plan": plan,
        "periodo": periodo,
        "gateway_customer_id": str(payer_id) if payer_id else None,
        "gateway_subscription_id": None,
    }


class MercadoPagoGateway(PaymentGateway):
    """Checkout Pro (pagamento avulso por período). Renovação = nova compra.

    Config por ambiente:
      MP_ACCESS_TOKEN   (obrigatório) — access token do vendedor
      MP_WEBHOOK_SECRET (opcional)    — assinatura x-signature dos webhooks
      MP_WEBHOOK_URL    (opcional)    — URL pública de /api/billing/webhook
      APP_URL                          — back_urls do checkout
    """

    def __init__(self):
        self.token = os.environ.get("MP_ACCESS_TOKEN", "")
        if not self.token:
            raise GatewayNotConfigured()
        self.webhook_secret = os.environ.get("MP_WEBHOOK_SECRET", "")
        self.app_url = os.environ.get("APP_URL", "http://localhost:5173")
        self.notification_url = os.environ.get("MP_WEBHOOK_URL", "")

    def _api(self, method: str, path: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            _MP_API + path, data=data, method=method,
            headers={"Authorization": f"Bearer {self.token}",
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            raise GatewayError(f"Mercado Pago HTTP {e.code}")
        except urllib.error.URLError as e:
            raise GatewayError(f"Mercado Pago indisponível: {e.reason}")

    def create_checkout(self, *, user_id, email, plan, periodo,
                        pay_method, amount_cents) -> dict:
        pref = {
            "items": [{
                "title": f"ZefiroSplit {plan} ({periodo})",
                "quantity": 1, "currency_id": "BRL",
                "unit_price": round(amount_cents / 100, 2),
            }],
            "payer": {"email": email},
            "external_reference": f"{user_id}|{plan}|{periodo}",
            "metadata": {"user_id": user_id, "plan": plan, "periodo": periodo},
            "back_urls": {
                "success": f"{self.app_url}/conta",
                "pending": f"{self.app_url}/conta",
                "failure": f"{self.app_url}/comprar",
            },
        }
        # auto_return exige success público — o MP recusa localhost. Só liga
        # quando APP_URL é um domínio de verdade (produção).
        if not any(h in self.app_url for h in ("localhost", "127.0.0.1")):
            pref["auto_return"] = "approved"
        if self.notification_url:
            pref["notification_url"] = self.notification_url
        r = self._api("POST", "/checkout/preferences", pref)
        url = r.get("init_point") or r.get("sandbox_init_point")
        if not url:
            raise GatewayError("preferência criada sem init_point")
        return {"checkout_url": url, "gateway_ref": r.get("id")}

    def cancel(self, gateway_subscription_id: str) -> None:
        return None  # Checkout Pro é avulso — não há recorrência a cancelar

    def _valid_signature(self, headers: dict, data_id: str) -> bool:
        """Valida o header x-signature do Mercado Pago (se houver secret)."""
        if not self.webhook_secret:
            return True  # sem secret: a autenticidade vem do lookup do pagamento
        sig = headers.get("x-signature", "")
        request_id = headers.get("x-request-id", "")
        parts = dict(p.split("=", 1) for p in sig.split(",") if "=" in p)
        ts, v1 = parts.get("ts", "").strip(), parts.get("v1", "").strip()
        if not ts or not v1:
            return False
        manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
        expected = hmac.new(self.webhook_secret.encode(), manifest.encode(),
                            hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, v1)

    def verify_webhook(self, headers: dict, body: bytes) -> dict:
        headers = {k.lower(): v for k, v in headers.items()}
        try:
            evt = json.loads(body) if body else {}
        except json.JSONDecodeError:
            evt = {}
        topic = str(evt.get("type") or evt.get("topic") or
                    headers.get("x-topic", "")).lower()
        data_id = (evt.get("data") or {}).get("id") or evt.get("id")
        # Só tratamos notificações de pagamento; ignoramos merchant_order/plan…
        if "payment" not in topic or not data_id:
            raise WebhookInvalid()
        if not self._valid_signature(headers, str(data_id)):
            raise WebhookInvalid()
        # NUNCA confiar no payload: buscamos o pagamento real na API do MP,
        # autenticados com o nosso token — é isto que garante autenticidade.
        payment = self._api("GET", f"/v1/payments/{data_id}")
        return _mp_payment_to_event(payment)


def get_gateway() -> PaymentGateway:
    name = os.environ.get("PAYMENT_GATEWAY", "none").lower()
    if name in ("mercadopago", "mp"):
        try:
            return MercadoPagoGateway()
        except GatewayNotConfigured:
            return NullGateway()  # sem MP_ACCESS_TOKEN → cai no fluxo simulado
    # TODO(gateway): if name == "stripe": return StripeGateway()
    return NullGateway()
