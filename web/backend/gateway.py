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
import hmac
import json
import os
from abc import ABC, abstractmethod


class GatewayNotConfigured(Exception):
    pass


class WebhookInvalid(Exception):
    pass


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


def get_gateway() -> PaymentGateway:
    name = os.environ.get("PAYMENT_GATEWAY", "none").lower()
    # TODO(gateway): registre aqui a implementação real, ex.:
    # if name == "stripe": return StripeGateway()
    # if name == "mercadopago": return MercadoPagoGateway()
    return NullGateway()
