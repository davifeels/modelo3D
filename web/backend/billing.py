"""Regras de negócio dos planos (fonte única no backend).

Espelha web/frontend/src/plans.js — preços em CENTAVOS para aritmética exata.

Regras (briefing 2026-07-07):
  - Essencial: até 25 arquivos fatiados/mês. Pro: ilimitado.
  - Trial: 7 dias de Pro no registro, sem cartão.
  - Upgrade/downgrade a qualquer momento com proração.
  - Anual: reembolso proporcional nos primeiros 30 dias.
  - Pós-cancelamento: projetos em leitura por 30 dias.
  - PIX/boleto: apenas no plano anual.
"""
from datetime import datetime, timedelta

PLANS = {
    "essencial": {
        "id": "essencial",
        "monthly_cents": 1990,
        "annual_cents": 17990,
        "slice_limit": 25,        # arquivos fatiados/mês
        "trial_days": 0,
    },
    "pro": {
        "id": "pro",
        "monthly_cents": 4990,
        "annual_cents": 44990,
        "slice_limit": None,      # ilimitado
        "trial_days": 7,
    },
}

PERIODOS = ("mensal", "anual")
TRIAL_DAYS = 7
ANNUAL_REFUND_WINDOW_DAYS = 30
READ_ONLY_DAYS = 30
PAY_METHODS = ("card", "pix", "boleto")


def price_cents(plan_id: str, periodo: str) -> int:
    p = PLANS[plan_id]
    return p["annual_cents"] if periodo == "anual" else p["monthly_cents"]


def validate_selection(plan_id: str, periodo: str, pay_method: str = "card"):
    """Retorna mensagem de erro ou None. PIX/boleto só no anual (cobrança única)."""
    if plan_id not in PLANS:
        return "plano_invalido"
    if periodo not in PERIODOS:
        return "periodo_invalido"
    if pay_method not in PAY_METHODS:
        return "pagamento_invalido"
    if pay_method in ("pix", "boleto") and periodo != "anual":
        return "pix_boleto_apenas_anual"
    return None


def period_key(now: datetime) -> str:
    """Chave do contador mensal de fatiamentos: '2026-07'."""
    return now.strftime("%Y-%m")


def cycle_days(periodo: str) -> int:
    return 365 if periodo == "anual" else 30


def period_end(start: datetime, periodo: str) -> datetime:
    return start + timedelta(days=cycle_days(periodo))


def has_access(sub, now: datetime) -> bool:
    """Assinatura dá acesso ao app? (trial vigente, ativa, ou cancelada dentro do período pago)."""
    if sub is None:
        return False
    if sub.status == "trialing":
        return sub.trial_end is not None and now <= sub.trial_end
    if sub.status in ("active", "canceled"):
        return sub.current_period_end is not None and now <= sub.current_period_end
    return False


def slice_limit(sub) -> int | None:
    """Limite de fatiamentos/mês do plano vigente (None = ilimitado)."""
    if sub is None:
        return 0
    return PLANS.get(sub.plan, {}).get("slice_limit", 0)


def refund_cents(sub, now: datetime) -> int:
    """Reembolso proporcional do plano ANUAL nos primeiros 30 dias; senão 0."""
    if sub is None or sub.periodo != "anual" or sub.status != "active":
        return 0
    if sub.current_period_start is None:
        return 0
    days_in = (now - sub.current_period_start).days
    if days_in > ANNUAL_REFUND_WINDOW_DAYS:
        return 0
    total = price_cents(sub.plan, "anual")
    remaining = max(0, 365 - days_in)
    return total * remaining // 365


def proration_credit_cents(sub, now: datetime) -> int:
    """Crédito do tempo não usado da assinatura atual (para upgrade/downgrade)."""
    if sub is None or sub.status not in ("active",) or sub.current_period_end is None:
        return 0
    total_days = cycle_days(sub.periodo or "mensal")
    remaining = (sub.current_period_end - now).days
    if remaining <= 0:
        return 0
    return price_cents(sub.plan, sub.periodo or "mensal") * remaining // total_days


def change_plan_charge_cents(sub, new_plan: str, new_periodo: str, now: datetime) -> int:
    """Valor a cobrar hoje na troca de plano (novo preço menos crédito proporcional)."""
    return max(0, price_cents(new_plan, new_periodo) - proration_credit_cents(sub, now))
