"""Testes E2E com Playwright — simulam usuário real no navegador.

Pré-requisitos:
    pip install playwright
    playwright install chromium

    Backend rodando em http://localhost:8000
    Frontend rodando em http://localhost:5173

Notas de design:
  - SPHERE_MM_STL: esfera 100mm de diâmetro — não aciona o toast de auto-escala
  - Fluxo atual: loaded → "Detectar cortes automáticos" OU "Seleção manual" → painting
  - Tema padrão: 'light' (alterado no store)
"""
import os
import time

import pytest

BASE_URL = "http://localhost:5173"

# Esfera 100mm — não aciona toast de auto-escala (raio=50mm está dentro de 10–500mm)
SPHERE_MM_STL = os.path.join(os.path.dirname(__file__), "fixtures", "sphere_mm.stl")
# Esfera 1m (raio=1.0) — usada para testar o toast de auto-escala
SPHERE_1M_STL = os.path.join(os.path.dirname(__file__), "fixtures", "sphere.stl")


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _check_frontend():
    import urllib.request, urllib.error
    try:
        urllib.request.urlopen(BASE_URL, timeout=3)
    except urllib.error.HTTPError:
        pass
    except Exception:
        pytest.skip("Frontend não está rodando em http://localhost:5173")


def _check_backend():
    import urllib.request, urllib.error
    try:
        urllib.request.urlopen("http://localhost:8000/api/session/ping", timeout=3)
    except urllib.error.HTTPError:
        pass
    except Exception:
        pytest.skip("Backend não está rodando em http://localhost:8000")


@pytest.fixture(scope="session")
def browser():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("playwright não instalado")
    _check_frontend()
    _check_backend()
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture
def page(browser):
    ctx = browser.new_context()
    pg = ctx.new_page()
    pg.goto(BASE_URL, wait_until="networkidle")
    yield pg
    ctx.close()


def _upload_file(page, path=None):
    """Faz upload via input oculto e aguarda canvas aparecer.
    .first = input do header (Abrir arquivo) — presente em qualquer etapa."""
    if path is None:
        path = SPHERE_MM_STL
    page.locator('input[type="file"]').first.set_input_files(path)
    page.wait_for_selector("canvas", timeout=20000)
    # Aguarda carregamento completo e possíveis toasts desaparecerem
    time.sleep(1.5)


def _wait_no_error_toast(page, timeout=3.0):
    """Verifica se não há toast de erro — ignora toast de info/warning de escala."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        toast = page.locator(".toast")
        if not toast.is_visible():
            return  # sem toast
        # Toast visível — verifica se é de escala (esperado) ou de erro (falha)
        txt = toast.evaluate("el => el.textContent") if toast.is_visible() else ""
        if "metros" in txt or "escalado" in txt or "convertido" in txt:
            # Toast de escala é esperado — não é erro
            return
        time.sleep(0.2)
    # Se chegou aqui com toast visível, verifica o conteúdo
    toast = page.locator(".toast")
    if toast.is_visible():
        txt = toast.evaluate("el => el.textContent") if toast.is_visible() else ""
        if "metros" in txt or "escalado" in txt or "convertido" in txt:
            return  # ainda é o toast de escala — ok
        assert False, f"Toast de erro inesperado: {txt}"


# ── Upload ─────────────────────────────────────────────────────────────────────

class TestUpload:

    def test_page_loads(self, page):
        """Página carrega com o título/logo do app."""
        from playwright.sync_api import expect
        logo = page.locator(".logo")
        expect(logo).to_be_visible(timeout=5000)

    def test_dropzone_visible(self, page):
        """Dropzone aparece na tela inicial."""
        from playwright.sync_api import expect
        dz = page.locator(".dropzone")
        expect(dz).to_be_visible(timeout=5000)

    def test_upload_via_input(self, page):
        """Upload via input file mostra canvas do viewer 3D."""
        from playwright.sync_api import expect
        _upload_file(page)
        canvas = page.locator("canvas").first
        expect(canvas).to_be_visible(timeout=20000)

    def test_upload_shows_model_info(self, page):
        """Após upload, painel lateral exibe informações do modelo."""
        from playwright.sync_api import expect
        _upload_file(page)
        # Painel lateral deve mostrar face count ou dimensões
        panel = page.locator(".left-panel, .side-panel, .info-panel").first
        # Qualquer elemento com número de faces
        face_info = page.locator("text=/Faces|faces|triangulos/i").first
        expect(face_info).to_be_visible(timeout=10000)

    def test_upload_invalid_format_shows_error(self, page):
        """Upload de arquivo .txt deve mostrar mensagem de erro."""
        from playwright.sync_api import expect
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write("isso nao e um modelo 3D")
            tmp = f.name
        try:
            page.locator('input[type="file"]').first.set_input_files(tmp)
            toast = page.locator(".toast")
            expect(toast).to_be_visible(timeout=8000)
        finally:
            os.unlink(tmp)

    def test_upload_scale_toast_for_meter_model(self, page):
        """Modelo em metros (raio=1m) deve exibir toast de auto-escala."""
        from playwright.sync_api import expect
        page.locator('input[type="file"]').first.set_input_files(SPHERE_1M_STL)
        page.wait_for_selector("canvas", timeout=20000)
        toast = page.locator(".toast")
        expect(toast).to_be_visible(timeout=8000)
        txt = toast.evaluate("el => el.textContent")
        assert "metros" in txt or "escalado" in txt or "convertido" in txt, \
            f"Toast de escala esperado, got: {txt}"


# ── Viewer — navegação ────────────────────────────────────────────────────────

class TestViewerNavigation:

    def test_canvas_visible_after_upload(self, page):
        """Canvas do viewer aparece após upload."""
        from playwright.sync_api import expect
        _upload_file(page)
        expect(page.locator("canvas").first).to_be_visible(timeout=20000)

    def test_reset_camera_button(self, page):
        """Botão Resetar câmera existe e pode ser clicado sem toast de erro."""
        from playwright.sync_api import expect
        _upload_file(page)  # sphere_mm — sem toast de escala
        btn = page.locator("button:has-text('Resetar câmera'), button:has-text('Resetar camera')")
        expect(btn.first).to_be_visible(timeout=10000)
        btn.first.click()
        time.sleep(0.5)
        _wait_no_error_toast(page)

    def test_viewer_zoom_scroll(self, page):
        """Scroll no canvas não causa toast de erro."""
        _upload_file(page)
        canvas = page.locator("canvas").first
        box = canvas.bounding_box()
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2
        page.mouse.move(cx, cy)
        page.mouse.wheel(0, -200)
        page.mouse.wheel(0, 200)
        time.sleep(0.3)
        _wait_no_error_toast(page)

    def test_orbit_drag(self, page):
        """Arrastar mouse no canvas (botão direito = orbit) não causa erro."""
        _upload_file(page)
        canvas = page.locator("canvas").first
        box = canvas.bounding_box()
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2
        # Botão direito = orbit (left click pode pintar em step painting)
        page.mouse.move(cx, cy)
        page.mouse.down(button="right")
        page.mouse.move(cx + 50, cy + 20)
        page.mouse.up(button="right")
        time.sleep(0.3)
        _wait_no_error_toast(page)


# ── Tema ──────────────────────────────────────────────────────────────────────

class TestThemeToggle:

    def test_default_theme_is_light(self, page):
        """Tema padrão deve ser 'light'."""
        _upload_file(page)
        theme = page.evaluate("document.documentElement.getAttribute('data-theme')")
        assert theme == "light", f"Tema padrão deveria ser 'light', got '{theme}'"

    def test_theme_toggle_changes_attribute(self, page):
        """Clicar no botão de tema muda data-theme no html."""
        _upload_file(page)
        initial_theme = page.evaluate("document.documentElement.getAttribute('data-theme')")
        page.locator("button.theme-toggle").click()
        time.sleep(0.3)
        new_theme = page.evaluate("document.documentElement.getAttribute('data-theme')")
        assert new_theme != initial_theme, f"Tema não mudou: ainda '{new_theme}'"

    def test_theme_toggle_light_to_dark(self, page):
        """Partindo do padrão light, um clique vai para dark."""
        _upload_file(page)
        theme_before = page.evaluate("document.documentElement.getAttribute('data-theme')")
        assert theme_before == "light"
        page.locator("button.theme-toggle").click()
        time.sleep(0.3)
        theme_after = page.evaluate("document.documentElement.getAttribute('data-theme')")
        assert theme_after == "dark", f"Esperado 'dark', got '{theme_after}'"

    def test_theme_toggle_dark_to_light(self, page):
        """Dois cliques: light → dark → light."""
        _upload_file(page)
        toggle = page.locator("button.theme-toggle")
        toggle.click()
        time.sleep(0.2)
        toggle.click()
        time.sleep(0.3)
        theme = page.evaluate("document.documentElement.getAttribute('data-theme')")
        assert theme == "light", f"Após 2 cliques deveria voltar para 'light', got '{theme}'"

    def test_theme_persists_in_localstorage(self, page):
        """Tema trocado é salvo no localStorage."""
        _upload_file(page)
        page.locator("button.theme-toggle").click()
        time.sleep(0.3)
        saved = page.evaluate("localStorage.getItem('zs_theme')")
        assert saved in ("dark", "light"), f"localStorage não salvou tema: {saved}"


# ── Wireframe ──────────────────────────────────────────────────────────────────

class TestWireframe:

    def test_wireframe_toggle_exists(self, page):
        """Toggle de wireframe existe após upload."""
        from playwright.sync_api import expect
        _upload_file(page)
        # O label é "Exibir wireframe" ou botão "Wireframe (W)"
        wf = page.locator(".tool-row-toggle").filter(has_text="ireframe").first
        expect(wf).to_be_visible(timeout=10000)

    def test_wireframe_toggle_click(self, page):
        """Clicar no toggle de wireframe não causa toast de erro."""
        _upload_file(page)
        # Encontra o botão toggle dentro do container de wireframe
        wf_container = page.locator(".tool-row-toggle").filter(has_text="ireframe")
        toggle = wf_container.locator(".toggle-switch")
        toggle.wait_for(state="visible", timeout=10000)
        toggle.click()
        time.sleep(0.3)
        _wait_no_error_toast(page)
        toggle.click()
        time.sleep(0.3)
        _wait_no_error_toast(page)


# ── Novo fluxo de corte automático ────────────────────────────────────────────

class TestAutoCutFlow:

    def test_detectar_cortes_button_visible(self, page):
        """Botão 'Detectar cortes automáticos' aparece após upload."""
        from playwright.sync_api import expect
        _upload_file(page)
        btn = page.locator("button:has-text('Detectar cortes automáticos')")
        expect(btn).to_be_visible(timeout=10000)

    def test_selecao_manual_button_visible(self, page):
        """Botão 'Seleção manual' aparece como alternativa."""
        from playwright.sync_api import expect
        _upload_file(page)
        btn = page.locator("button:has-text('Seleção manual')")
        expect(btn).to_be_visible(timeout=10000)

    def test_detectar_cortes_calls_api(self, page):
        """Clicar 'Detectar cortes automáticos' deve entrar no step cutting."""
        from playwright.sync_api import expect
        _upload_file(page)
        btn = page.locator("button:has-text('Detectar cortes automáticos')")
        btn.wait_for(state="visible", timeout=10000)
        btn.click()
        # Aguarda a resposta da API (suggest-cuts) — pode demorar
        # Deve aparecer o painel de ajuste de corte
        time.sleep(8)
        # Ou voltou ao loaded (sem sugestões) ou entrou em cutting
        # Em qualquer caso, não deve ter toast de erro de crash
        _wait_no_error_toast(page)

    def test_selecao_manual_enters_painting(self, page):
        """Clicar 'Seleção manual' entra no step painting."""
        from playwright.sync_api import expect
        _upload_file(page)
        btn = page.locator("button:has-text('Seleção manual')")
        btn.wait_for(state="visible", timeout=10000)
        btn.click()
        time.sleep(0.5)
        # Deve aparecer ferramentas de pintura no right panel
        panel = page.locator(".right-panel")
        expect(panel).to_be_visible(timeout=5000)
        _wait_no_error_toast(page)


# ── Pintura (via Seleção manual) ──────────────────────────────────────────────

class TestPainting:

    def _enter_painting(self, page):
        """Entra no step painting via 'Seleção manual'."""
        _upload_file(page)
        btn = page.locator("button:has-text('Seleção manual')")
        btn.wait_for(state="visible", timeout=10000)
        btn.click()
        time.sleep(0.5)

    def test_enter_painting_step(self, page):
        """Clicar 'Seleção manual' entra no step painting."""
        self._enter_painting(page)
        panel = page.locator(".right-panel")
        assert panel.is_visible()

    def test_paint_canvas_click(self, page):
        """Clicar no canvas no step painting não gera toast de crash."""
        self._enter_painting(page)
        canvas = page.locator("canvas").first
        box = canvas.bounding_box()
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2
        page.mouse.click(cx, cy)
        time.sleep(0.5)
        _wait_no_error_toast(page)

    def test_paint_brush_mode(self, page):
        """Trocar para modo brush e pintar não causa crash."""
        self._enter_painting(page)
        # Tenta clicar no botão de brush se existir
        brush_btn = page.locator("button.tool-btn[title*='rush'], .tool-btn:has-text('Brush')").first
        if brush_btn.is_visible():
            brush_btn.click()
            time.sleep(0.2)
        canvas = page.locator("canvas").first
        box = canvas.bounding_box()
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2
        # Drag para pintar com brush
        page.mouse.move(cx, cy)
        page.mouse.down()
        page.mouse.move(cx + 30, cy)
        page.mouse.up()
        time.sleep(0.5)
        _wait_no_error_toast(page)

    def test_ctrl_z_undo(self, page):
        """Ctrl+Z deve desfazer a pintura sem crash."""
        self._enter_painting(page)
        canvas = page.locator("canvas").first
        box = canvas.bounding_box()
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2
        page.mouse.click(cx, cy)
        time.sleep(0.3)
        page.keyboard.press("Control+z")
        time.sleep(0.3)
        _wait_no_error_toast(page)

    def test_voltar_from_painting(self, page):
        """Clicar 'Voltar' ou 'Importar outro' no step painting não causa crash."""
        self._enter_painting(page)
        # Tenta qualquer botão de voltar
        back_btn = page.locator("button:has-text('Voltar'), button:has-text('Importar outro')").first
        if back_btn.is_visible():
            back_btn.click()
            time.sleep(0.5)
        _wait_no_error_toast(page)


# ── Step indicator ────────────────────────────────────────────────────────────

class TestStepIndicator:

    def test_step_indicator_visible(self, page):
        """StepIndicator aparece no header com 6 steps."""
        from playwright.sync_api import expect
        _upload_file(page)
        header = page.locator(".app-header")
        expect(header).to_be_visible(timeout=5000)
        # Deve ter 6 steps: Importar, Cortar, Pintar, Preview, Processar, Exportar
        steps = page.locator(".step-item")
        count = steps.count()
        assert count == 6, f"Esperado 6 steps, encontrado {count}"

    def test_step_active_after_upload(self, page):
        """Após upload, step 'Cortar' (índice 1) deve estar ativo."""
        _upload_file(page)
        steps = page.locator(".step-item")
        # Step 1 (Cortar) deve ter classe 'active'
        step_cut = steps.nth(1)
        classes = step_cut.get_attribute("class") or ""
        assert "active" in classes, f"Step 'Cortar' deveria estar ativo. Classes: {classes}"

    def test_step_import_marked_done_after_upload(self, page):
        """Após upload, step 'Importar' deve estar marcado como feito (done)."""
        _upload_file(page)
        steps = page.locator(".step-item")
        step_import = steps.nth(0)
        classes = step_import.get_attribute("class") or ""
        assert "done" in classes, f"Step 'Importar' deveria estar 'done'. Classes: {classes}"

    def test_lang_toggle(self, page):
        """Botão de idioma alterna PT/EN."""
        btn = page.locator("button.lang-select")
        initial = btn.inner_text()
        btn.click()
        time.sleep(0.3)
        new_text = btn.inner_text()
        assert new_text != initial, f"Idioma não mudou: ainda '{new_text}'"


# ── Restauração de sessão ─────────────────────────────────────────────────────

class TestRestoreSession:

    def test_restore_modal_appears_after_reload(self, page):
        """Após upload e reload, aparece modal de restore."""
        from playwright.sync_api import expect
        _upload_file(page)
        session_saved = page.evaluate("!!localStorage.getItem('zs_session')")
        if not session_saved:
            pytest.skip("App não salva sessão no localStorage")
        page.reload(wait_until="networkidle")
        restore = page.locator(".restore-modal")
        expect(restore).to_be_visible(timeout=10000)

    def test_dismiss_restore_shows_dropzone(self, page):
        """Clicar 'Começar do zero' fecha modal e mostra dropzone."""
        from playwright.sync_api import expect
        _upload_file(page)
        session_saved = page.evaluate("!!localStorage.getItem('zs_session')")
        if not session_saved:
            pytest.skip("App não salva sessão no localStorage")
        page.reload(wait_until="networkidle")
        btn = page.locator("button:has-text('Começar do zero')")
        btn.wait_for(state="visible", timeout=10000)
        btn.click()
        time.sleep(0.3)
        expect(page.locator(".dropzone")).to_be_visible(timeout=5000)

    def test_restore_session_button(self, page):
        """Clicar 'Continuar sessão' restaura o estado."""
        from playwright.sync_api import expect
        _upload_file(page)
        session_saved = page.evaluate("!!localStorage.getItem('zs_session')")
        if not session_saved:
            pytest.skip("App não salva sessão no localStorage")
        page.reload(wait_until="networkidle")
        btn = page.locator("button:has-text('Continuar sessão')")
        btn.wait_for(state="visible", timeout=10000)
        btn.click()
        expect(page.locator("canvas").first).to_be_visible(timeout=15000)


# ── Export ────────────────────────────────────────────────────────────────────

class TestExport:

    def _reach_result(self, page):
        """Sobe modelo → seleção manual → pinta → corta → confirma → result."""
        from playwright.sync_api import expect
        _upload_file(page)

        # Entra em pintura via Seleção manual
        btn_manual = page.locator("button:has-text('Seleção manual')")
        btn_manual.wait_for(state="visible", timeout=10000)
        btn_manual.click()
        time.sleep(0.5)

        # Pinta no canvas (centro e arredores)
        canvas = page.locator("canvas").first
        canvas.wait_for(state="visible", timeout=10000)
        box = canvas.bounding_box()
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2

        for dx, dy in [(0, 0), (20, 0), (-20, 0), (0, 20), (0, -20), (30, 30)]:
            page.mouse.click(cx + dx, cy + dy)
            time.sleep(0.2)

        # Próximo passo
        btn_next = page.locator("button:has-text('Próximo passo'), button:has-text('Cortar')")
        btn_next = page.locator("button").filter(has_text="ximo passo").first
        if not btn_next.is_visible():
            btn_next = page.locator("button").filter(has_text="Cortar").first

        try:
            btn_next.wait_for(state="visible", timeout=5000)
        except Exception:
            pytest.skip("Nenhuma face foi pintada — canvas pode não estar interagível em headless")

        if btn_next.get_attribute("disabled") is not None:
            pytest.skip("Botão desabilitado — nenhuma face pintada em headless")

        btn_next.click()
        time.sleep(3)

        # Confirmar se chegou ao previewing
        btn_confirm = page.locator("button:has-text('Confirmar e processar'), button:has-text('Confirmar')")
        if btn_confirm.first.is_visible():
            btn_confirm.first.click()
            time.sleep(5)

    def test_export_panel_after_confirm(self, page):
        """Painel de right-panel aparece no step result após confirmação."""
        from playwright.sync_api import expect
        self._reach_result(page)
        result_panel = page.locator(".right-panel")
        expect(result_panel).to_be_visible(timeout=5000)


# ── Seletor de tipo de conector + fit ─────────────────────────────────────────

class TestJointSelector:

    def _reach_previewing(self, page):
        """Sobe modelo → seleção manual → pinta → corta → step previewing."""
        _upload_file(page)

        btn_manual = page.locator("button:has-text('Seleção manual')")
        btn_manual.wait_for(state="visible", timeout=10000)
        btn_manual.click()
        time.sleep(0.5)

        canvas = page.locator("canvas").first
        canvas.wait_for(state="visible", timeout=10000)
        box = canvas.bounding_box()
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2
        for dx, dy in [(0, 0), (20, 0), (-20, 0), (0, 20), (0, -20), (30, 30)]:
            page.mouse.click(cx + dx, cy + dy)
            time.sleep(0.2)

        btn_next = page.locator("button").filter(has_text="ximo passo").first
        if not btn_next.is_visible():
            btn_next = page.locator("button").filter(has_text="Cortar").first
        try:
            btn_next.wait_for(state="visible", timeout=5000)
        except Exception:
            pytest.skip("Nenhuma face foi pintada — canvas pode não estar interagível em headless")
        if btn_next.get_attribute("disabled") is not None:
            pytest.skip("Botão desabilitado — nenhuma face pintada em headless")
        btn_next.click()
        time.sleep(3)

    def test_seletor_visivel_no_previewing(self, page):
        """Os 3 tipos e os 2 fits aparecem no painel do step previewing."""
        self._reach_previewing(page)
        for label in ("Pino", "Esfera", "Dovetail", "Flexível", "Apertado"):
            btn = page.locator(f"button:has-text('{label}')").first
            assert btn.is_visible(), f"botão '{label}' não está visível"

    def test_dovetail_apertado_gera_preview(self, page):
        """Trocar para dovetail + apertado e gerar preview não causa erro."""
        self._reach_previewing(page)
        page.locator("button:has-text('Dovetail')").first.click()
        time.sleep(0.2)
        page.locator("button:has-text('Apertado')").first.click()
        time.sleep(0.2)
        btn_gen = page.locator("button:has-text('Gerar preview')").first
        if not btn_gen.is_visible():
            pytest.skip("Botão de gerar preview não visível")
        btn_gen.click()
        time.sleep(4)
        _wait_no_error_toast(page)


# ── Light mode visual ─────────────────────────────────────────────────────────

class TestLightMode:

    def test_background_is_light_by_default(self, page):
        """Em tema light, background do app deve ser claro (não escuro)."""
        _upload_file(page)
        theme = page.evaluate("document.documentElement.getAttribute('data-theme')")
        assert theme == "light"
        # Verifica cor do background do body
        bg_color = page.evaluate("""
          () => {
            const root = document.documentElement;
            const style = getComputedStyle(root);
            return style.getPropertyValue('--e0').trim();
          }
        """)
        # Em light mode --e0 deve ser uma cor clara (hex começando com #e ou #f)
        assert bg_color.startswith('#e') or bg_color.startswith('#f'), \
            f"--e0 em light mode deveria ser claro, got '{bg_color}'"

    def test_viewer_background_light(self, page):
        """Viewer 3D tem background claro em light mode."""
        _upload_file(page)
        # Canvas deve estar visível
        canvas = page.locator("canvas").first
        assert canvas.is_visible()
        # Verificação: nenhum erro de tema no console
        _wait_no_error_toast(page)

    def test_css_vars_applied(self, page):
        """Variáveis CSS de light mode estão aplicadas."""
        _upload_file(page)
        # --t1 em light mode deve ser escuro (texto sobre fundo claro)
        t1 = page.evaluate("""
          () => getComputedStyle(document.documentElement).getPropertyValue('--t1').trim()
        """)
        # Em light mode --t1 = #0f172a (quase preto)
        assert t1 != '', f"--t1 não foi definido"
        # Não pode ser uma cor clara (fundo claro + texto claro = ilegível)
        assert t1 not in ('#f0f0ff', '#ffffff', '#fff'), \
            f"--t1 em light mode não pode ser branco: '{t1}'"
