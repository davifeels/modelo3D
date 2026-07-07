"""E2E do fluxo de autenticação: login antes de tudo, registro com trial,
paywall quando o plano expira e área da conta.

Pré-requisitos: frontend em :5173 e backend em :8000 (auto-skip sem eles).
"""
import json
import urllib.error
import urllib.request
import uuid

import pytest

import apiauth

BASE_URL = "http://localhost:5173"
API = "http://localhost:8000/api"


# `browser` (session-scoped, único por sessão pytest) vem de tests/conftest.py.

@pytest.fixture
def page(browser):
    ctx = browser.new_context()
    pg = ctx.new_page()
    yield pg
    ctx.close()


def _api(method, path, body=None, token=None):
    data = json.dumps(body).encode() if body else None
    hdrs = {"Content-Type": "application/json"} if data else {}
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    rq = urllib.request.Request(API + path, data=data, method=method, headers=hdrs)
    return json.loads(urllib.request.urlopen(rq, timeout=30).read())


class TestLoginGate:
    def test_app_sem_token_mostra_login(self, page):
        page.goto(BASE_URL, wait_until="networkidle")
        page.wait_for_selector('[data-testid="login-card"]', timeout=10000)
        # O app (dropzone) NÃO aparece sem login
        assert page.locator(".drop-zone, .app-header").count() == 0

    def test_registro_pela_ui_entra_no_app(self, page):
        page.goto(BASE_URL, wait_until="networkidle")
        page.wait_for_selector('[data-testid="login-card"]', timeout=10000)
        page.locator('[data-testid="tab-signup"]').click()
        email = f"ui-{uuid.uuid4().hex[:10]}@zefiro.test"
        page.locator('[data-testid="login-email"]').fill(email)
        page.locator('[data-testid="login-password"]').fill("senha123")
        page.locator('[data-testid="login-submit"]').click()
        # Trial do Pro é criado no registro → entra direto no app
        page.wait_for_selector(".app-header", timeout=15000)

    def test_senha_errada_mostra_erro(self, page):
        token, email, _ = apiauth.register_user()
        page.goto(BASE_URL, wait_until="networkidle")
        page.wait_for_selector('[data-testid="login-card"]', timeout=10000)
        page.locator('[data-testid="login-email"]').fill(email)
        page.locator('[data-testid="login-password"]').fill("senha-errada")
        page.locator('[data-testid="login-submit"]').click()
        page.wait_for_selector('[data-testid="login-error"]', timeout=10000)

    def test_login_ok_entra_no_app(self, page):
        _, email, _ = apiauth.register_user()
        page.goto(BASE_URL, wait_until="networkidle")
        page.wait_for_selector('[data-testid="login-card"]', timeout=10000)
        page.locator('[data-testid="login-email"]').fill(email)
        page.locator('[data-testid="login-password"]').fill("senha123")
        page.locator('[data-testid="login-submit"]').click()
        page.wait_for_selector(".app-header", timeout=15000)


class TestPaywall:
    def test_plano_expirado_cai_no_paywall(self, browser):
        token, _, _ = apiauth.register_user()
        try:
            _api("POST", "/billing/dev/expire", {}, token=token)
        except urllib.error.HTTPError:
            pytest.skip("ZS_DEV_BILLING desabilitado no servidor")
        ctx = browser.new_context()
        ctx.add_init_script(f"localStorage.setItem('zs_token', '{token}')")
        pg = ctx.new_page()
        pg.goto(BASE_URL, wait_until="networkidle")
        # Sem acesso → página de planos como paywall, com aviso e sem "voltar ao app"
        pg.wait_for_selector('[data-testid="paywall-banner"]', timeout=10000)
        assert pg.locator('[data-testid="pl-card-pro"]').is_visible()
        assert pg.locator(".pl-back").count() == 0
        ctx.close()


class TestConta:
    def test_conta_mostra_trial_e_uso(self, browser):
        token, email, _ = apiauth.register_user()
        ctx = browser.new_context()
        ctx.add_init_script(f"localStorage.setItem('zs_token', '{token}')")
        pg = ctx.new_page()
        pg.goto(f"{BASE_URL}/conta", wait_until="networkidle")
        pg.wait_for_selector('[data-testid="acct-card"]', timeout=10000)
        assert pg.locator('[data-testid="acct-plan"]').inner_text() == "Pro"
        assert "∞" in pg.locator('[data-testid="acct-usage"]').inner_text()
        ctx.close()

    def test_logout_volta_para_login(self, browser):
        token, _, _ = apiauth.register_user()
        ctx = browser.new_context()
        ctx.add_init_script(f"localStorage.setItem('zs_token', '{token}')")
        pg = ctx.new_page()
        pg.goto(f"{BASE_URL}/conta", wait_until="networkidle")
        pg.wait_for_selector('[data-testid="acct-logout"]', timeout=10000)
        pg.locator('[data-testid="acct-logout"]').click()
        pg.wait_for_selector('[data-testid="login-card"]', timeout=10000)
