"""E2E do fluxo da refatoração: landing pública, compra com cadastro
automático, login SEM registro, paywall, conta e painel administrativo.

Pré-requisitos: frontend em :5173 e backend em :8000 com ZS_DEV_BILLING=1
(auto-skip sem eles). Painel admin requer ADMIN_EMAIL/ADMIN_PASSWORD no
ambiente do pytest.
"""
import json
import os
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


class TestLanding:
    def test_visitante_ve_landing_na_raiz(self, page):
        """Sem login, a raiz mostra a LANDING (não o app, não o login)."""
        page.goto(BASE_URL, wait_until="networkidle")
        page.wait_for_selector('[data-testid="landing"]', timeout=10000)
        assert page.locator('[data-testid="ld-title"]').is_visible()
        assert page.locator(".drop-zone, .app-header").count() == 0

    def test_botao_comprar_acesso_leva_a_compra(self, page):
        """Requisito: botão "Comprar Acesso" ao final da página → /comprar."""
        page.goto(BASE_URL, wait_until="networkidle")
        page.wait_for_selector('[data-testid="ld-buy-final"]', timeout=10000)
        page.locator('[data-testid="ld-buy-final"]').click()
        page.wait_for_selector('[data-testid="buy-form"]', timeout=10000)
        assert page.url.rstrip("/").endswith("/comprar")

    def test_landing_tem_secoes_obrigatorias(self, page):
        page.goto(BASE_URL, wait_until="networkidle")
        page.wait_for_selector('[data-testid="landing"]', timeout=10000)
        body = page.locator('[data-testid="landing"]').inner_text()
        assert "Por que o ZefiroSplit" in body        # benefícios
        assert "Funcionalidades principais" in body   # funcionalidades
        assert "Perguntas frequentes" in body         # FAQ
        assert "Quem usa, recomenda" in body          # depoimentos
        assert page.locator("footer.ld-footer").is_visible()  # rodapé

    def test_link_entrar_leva_ao_login(self, page):
        page.goto(BASE_URL, wait_until="networkidle")
        page.wait_for_selector('[data-testid="ld-login"]', timeout=10000)
        page.locator('[data-testid="ld-login"]').click()
        page.wait_for_selector('[data-testid="login-card"]', timeout=10000)


class TestCompraUI:
    def test_compra_pela_ui_cria_acesso(self, page):
        """Fluxo completo: formulário → confirmação → conta criada no backend."""
        email = f"ui-{uuid.uuid4().hex[:10]}@zefiro.test"
        page.goto(f"{BASE_URL}/comprar?plano=pro&periodo=mensal", wait_until="networkidle")
        page.wait_for_selector('[data-testid="buy-form"]', timeout=10000)
        assert "R$ 49,90" in page.locator('[data-testid="buy-total"]').inner_text()

        page.locator('[data-testid="buy-nome"]').fill("Cliente E2E")
        page.locator('[data-testid="buy-email"]').fill(email)
        page.locator('[data-testid="buy-telefone"]').fill("(11) 91234-5678")
        page.locator('[data-testid="buy-submit"]').click()
        page.wait_for_selector('[data-testid="buy-success"]', timeout=15000)

        # Botão leva ao login (cliente entra com as credenciais do e-mail)
        page.locator('[data-testid="buy-go-login"]').click()
        page.wait_for_selector('[data-testid="login-card"]', timeout=10000)

    def test_toggle_e_selecao_de_produto(self, page):
        page.goto(f"{BASE_URL}/comprar", wait_until="networkidle")
        page.wait_for_selector('[data-testid="buy-form"]', timeout=10000)
        # Pro pré-selecionado por padrão
        assert "R$ 49,90" in page.locator('[data-testid="buy-total"]').inner_text()
        # Muda para Essencial anual
        page.locator('[data-testid="buy-toggle-anual"]').click()
        page.locator('[data-testid="buy-plan-essencial"]').click()
        assert "R$ 179,90" in page.locator('[data-testid="buy-total"]').inner_text()


class TestLoginGate:
    def test_login_nao_tem_criar_conta(self, page):
        """REQUISITO: sem Criar conta/Registrar-se/Cadastre-se/Sign Up."""
        page.goto(f"{BASE_URL}/login", wait_until="networkidle")
        page.wait_for_selector('[data-testid="login-card"]', timeout=10000)
        card = page.locator('[data-testid="login-card"]').inner_text()
        for proibido in ("Criar conta", "Registrar", "Cadastre", "Sign up", "Sign Up"):
            assert proibido not in card
        # Só: e-mail, senha, entrar, esqueci minha senha
        assert page.locator('[data-testid="login-email"]').is_visible()
        assert page.locator('[data-testid="login-password"]').is_visible()
        assert page.locator('[data-testid="login-submit"]').is_visible()
        assert page.locator('[data-testid="login-forgot"]').is_visible()

    def test_login_ok_entra_no_app(self, page):
        email, senha, _ = apiauth.buy_user()
        page.goto(f"{BASE_URL}/login", wait_until="networkidle")
        page.wait_for_selector('[data-testid="login-card"]', timeout=10000)
        page.locator('[data-testid="login-email"]').fill(email)
        page.locator('[data-testid="login-password"]').fill(senha)
        page.locator('[data-testid="login-submit"]').click()
        page.wait_for_selector(".app-header", timeout=15000)

    def test_senha_errada_mostra_erro(self, page):
        email, _, _ = apiauth.buy_user()
        page.goto(f"{BASE_URL}/login", wait_until="networkidle")
        page.wait_for_selector('[data-testid="login-card"]', timeout=10000)
        page.locator('[data-testid="login-email"]').fill(email)
        page.locator('[data-testid="login-password"]').fill("senha-errada")
        page.locator('[data-testid="login-submit"]').click()
        page.wait_for_selector('[data-testid="login-error"]', timeout=10000)

    def test_esqueci_minha_senha(self, page):
        email, _, _ = apiauth.buy_user()
        page.goto(f"{BASE_URL}/login", wait_until="networkidle")
        page.wait_for_selector('[data-testid="login-card"]', timeout=10000)
        page.locator('[data-testid="login-email"]').fill(email)
        page.locator('[data-testid="login-forgot"]').click()
        page.wait_for_selector('[data-testid="login-info"]', timeout=10000)

    def test_rota_protegida_sem_token_cai_no_login(self, page):
        page.goto(f"{BASE_URL}/conta", wait_until="networkidle")
        page.wait_for_selector('[data-testid="login-card"]', timeout=10000)


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
    def test_conta_mostra_plano_e_uso(self, browser):
        token, email, _ = apiauth.register_user()
        ctx = browser.new_context()
        ctx.add_init_script(f"localStorage.setItem('zs_token', '{token}')")
        pg = ctx.new_page()
        pg.goto(f"{BASE_URL}/conta", wait_until="networkidle")
        pg.wait_for_selector('[data-testid="acct-card"]', timeout=10000)
        assert pg.locator('[data-testid="acct-plan"]').inner_text() == "Pro"
        assert "∞" in pg.locator('[data-testid="acct-usage"]').inner_text()
        ctx.close()

    def test_logout_leva_ao_login(self, browser):
        token, _, _ = apiauth.register_user()
        ctx = browser.new_context()
        ctx.add_init_script(f"localStorage.setItem('zs_token', '{token}')")
        pg = ctx.new_page()
        pg.goto(f"{BASE_URL}/conta", wait_until="networkidle")
        pg.wait_for_selector('[data-testid="acct-logout"]', timeout=10000)
        pg.locator('[data-testid="acct-logout"]').click()
        pg.wait_for_selector('[data-testid="login-card"]', timeout=10000)
        ctx.close()


class TestPainelAdmin:
    def _admin_creds(self):
        email = os.environ.get("ADMIN_EMAIL")
        password = os.environ.get("ADMIN_PASSWORD")
        if not email or not password:
            pytest.skip("ADMIN_EMAIL/ADMIN_PASSWORD não definidos no ambiente")
        return email, password

    def test_admin_area_propria_com_login_separado(self, page):
        email, password = self._admin_creds()
        page.goto(f"{BASE_URL}/admin", wait_until="networkidle")
        page.wait_for_selector('[data-testid="adm-login-card"]', timeout=10000)
        page.locator('[data-testid="adm-email"]').fill(email)
        page.locator('[data-testid="adm-password"]').fill(password)
        page.locator('[data-testid="adm-login-submit"]').click()
        page.wait_for_selector('[data-testid="adm-table"]', timeout=10000)

    def test_busca_e_acoes_na_tabela(self, page):
        email, password = self._admin_creds()
        cliente_email, _, _ = apiauth.buy_user()
        page.goto(f"{BASE_URL}/admin", wait_until="networkidle")
        page.wait_for_selector('[data-testid="adm-login-card"]', timeout=10000)
        page.locator('[data-testid="adm-email"]').fill(email)
        page.locator('[data-testid="adm-password"]').fill(password)
        page.locator('[data-testid="adm-login-submit"]').click()
        page.wait_for_selector('[data-testid="adm-table"]', timeout=10000)

        # Busca pelo e-mail do cliente recém-comprado
        page.locator('[data-testid="adm-search"]').fill(cliente_email)
        page.wait_for_selector(f'[data-email="{cliente_email}"]', timeout=10000)
        row = page.locator(f'[data-email="{cliente_email}"]')
        assert "ZS-" in row.inner_text()          # código de acesso na tabela

        # Enviar acesso → feedback com status do e-mail
        row.locator('[data-testid="adm-send"]').click()
        page.wait_for_selector('[data-testid="adm-msg"]', timeout=10000)
        msg = page.locator('[data-testid="adm-msg"]').inner_text()
        assert "enviado" in msg.lower() or "simulado" in msg.lower()

        # Histórico expande com compras e e-mails
        row.locator('[data-testid="adm-hist-btn"]').click()
        page.wait_for_selector('[data-testid="adm-history-row"]', timeout=10000)
