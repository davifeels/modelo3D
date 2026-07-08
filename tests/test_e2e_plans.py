"""Testes E2E da página de planos (/planos) e do checkout (/checkout).

Pré-requisitos:
    Frontend rodando em http://localhost:5173
    Backend rodando em http://localhost:8000 (tudo exige login desde 2026-07-07)

Cobertura (briefing de planos, 2026-07-07):
  - Toggle mensal/anual atualiza preços dinamicamente + pílula de economia 25%
  - Diferencial principal: Essencial até 25 fatiamentos/mês, Pro ilimitado
  - CTA leva ao checkout com ?plano=&periodo= pré-selecionados
  - Tabela comparativa com preços no rodapé
  - FAQ acordeão com apenas uma pergunta aberta por vez
  - Regra de negócio: PIX/boleto apenas no plano anual
"""
import pytest

BASE_URL = "http://localhost:5173"


# `browser` (session-scoped, único por sessão pytest) vem de tests/conftest.py.

@pytest.fixture
def page(browser):
    import apiauth
    token = apiauth.get_token()
    ctx = browser.new_context()
    ctx.add_init_script(f"localStorage.setItem('zs_token', '{token}')")
    pg = ctx.new_page()
    yield pg
    ctx.close()


def _goto_planos(page):
    page.goto(f"{BASE_URL}/planos", wait_until="networkidle")
    page.wait_for_selector('[data-testid="pl-card-pro"]', timeout=10000)


# ── Página de planos ──────────────────────────────────────────────────────────

class TestPaginaPlanos:
    def test_renderiza_cards_e_precos_mensais(self, page):
        _goto_planos(page)
        assert "R$ 19,90" in page.locator('[data-testid="pl-price-essencial"]').inner_text()
        assert "R$ 49,90" in page.locator('[data-testid="pl-price-pro"]').inner_text()
        # Badge "Popular" no card Pro
        assert page.locator('[data-testid="pl-card-pro"] .pl-popular').is_visible()

    def test_diferencial_fatiamentos_25_vs_ilimitado(self, page):
        """A maior diferença entre os planos: 25 fatiamentos/mês vs ilimitado."""
        _goto_planos(page)
        essencial = page.locator('[data-testid="pl-card-essencial"]').inner_text()
        pro = page.locator('[data-testid="pl-card-pro"]').inner_text()
        assert "até 25/mês" in essencial
        assert "ilimitado" in pro
        # Também destacado na tabela comparativa
        linha = page.locator('[data-testid="pl-table"] tr.hl').inner_text()
        assert "Fatiamentos por mês" in linha
        assert "25" in linha and "ilimitado" in linha

    def test_toggle_anual_atualiza_precos_sem_recarregar(self, page):
        _goto_planos(page)
        page.locator('[data-testid="pl-toggle-anual"]').click()
        # Preços anuais à vista
        assert "R$ 179,90" in page.locator('[data-testid="pl-price-essencial"]').inner_text()
        assert "R$ 449,90" in page.locator('[data-testid="pl-price-pro"]').inner_text()
        # Equivalente mensal
        assert "R$ 14,99" in page.locator('[data-testid="pl-equiv-essencial"]').inner_text()
        assert "R$ 37,49" in page.locator('[data-testid="pl-equiv-pro"]').inner_text()
        # Pílula de economia de 25%
        assert "25%" in page.locator('[data-testid="pl-save-pill"]').inner_text()
        # Voltar para mensal esconde a pílula e restaura o preço
        page.locator('[data-testid="pl-toggle-mensal"]').click()
        assert page.locator('[data-testid="pl-save-pill"]').count() == 0
        assert "R$ 19,90" in page.locator('[data-testid="pl-price-essencial"]').inner_text()

    def test_tabela_comparativa_com_precos_no_rodape(self, page):
        _goto_planos(page)
        tabela = page.locator('[data-testid="pl-table"]')
        # 13 recursos no corpo da tabela
        assert tabela.locator("tbody tr").count() == 13
        assert "R$ 19,90" in tabela.locator('[data-testid="pl-table-price-essencial"]').inner_text()
        # No modo anual o rodapé mostra o equivalente mensal + valor à vista
        page.locator('[data-testid="pl-toggle-anual"]').click()
        rodape_pro = tabela.locator('[data-testid="pl-table-price-pro"]').inner_text()
        assert "R$ 37,49" in rodape_pro and "R$ 449,90" in rodape_pro

    def test_faq_acordeao_uma_pergunta_por_vez(self, page):
        _goto_planos(page)
        faq = page.locator('[data-testid="pl-faq"]')
        # Nenhuma aberta inicialmente
        assert faq.locator(".pl-faq-item.open").count() == 0
        page.locator('[data-testid="pl-faq-faq_limit"] button').click()
        assert "open" in page.locator('[data-testid="pl-faq-faq_limit"]').get_attribute("class")
        # Abrir a segunda fecha a primeira — apenas uma aberta por vez
        page.locator('[data-testid="pl-faq-faq_change"] button').click()
        assert faq.locator(".pl-faq-item.open").count() == 1
        assert "open" in page.locator('[data-testid="pl-faq-faq_change"]').get_attribute("class")

    def test_rota_direta_planos(self, page):
        """/planos é roteável direto (paywall pós-login usa a mesma página)."""
        page.goto(f"{BASE_URL}/planos", wait_until="networkidle")
        page.wait_for_selector('[data-testid="pl-card-pro"]', timeout=10000)
        assert page.url.endswith("/planos")


# ── Compra (a compra acontece FORA do app: /comprar) ─────────────────────────

class TestCtaCompra:
    def test_cta_do_paywall_leva_a_compra_com_plano_e_periodo(self, page):
        _goto_planos(page)
        page.locator('[data-testid="pl-toggle-anual"]').click()
        page.locator('[data-testid="pl-cta-pro"]').click()
        page.wait_for_selector('[data-testid="buy-form"]', timeout=10000)
        assert "plano=pro" in page.url and "periodo=anual" in page.url
        # Pré-seleção refletida no total
        assert "R$ 449,90" in page.locator('[data-testid="buy-total"]').inner_text()

    def test_url_direta_preseleciona_essencial_mensal(self, page):
        page.goto(f"{BASE_URL}/comprar?plano=essencial&periodo=mensal", wait_until="networkidle")
        page.wait_for_selector('[data-testid="buy-form"]', timeout=10000)
        assert "R$ 19,90" in page.locator('[data-testid="buy-total"]').inner_text()

    def test_parametros_invalidos_caem_no_padrao(self, page):
        page.goto(f"{BASE_URL}/comprar?plano=xyz&periodo=abc", wait_until="networkidle")
        page.wait_for_selector('[data-testid="buy-form"]', timeout=10000)
        # Padrão: Pro mensal
        assert "R$ 49,90" in page.locator('[data-testid="buy-total"]').inner_text()
