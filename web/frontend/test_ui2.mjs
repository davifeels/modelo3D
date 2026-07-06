import { chromium } from "playwright";

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1280, height: 800 });

  page.on('console', msg => console.log('CONSOLE:', msg.text()));
  page.on('pageerror', err => console.log('ERROR:', err.message));

  await page.goto("http://localhost:5173");
  await page.waitForTimeout(1000);

  // Upload STL
  const fileInput = page.locator("input[type=file]");
  await fileInput.setInputFiles("C:/Users/davif/Downloads/figura_teste.stl");
  await page.waitForTimeout(5000);
  await page.screenshot({ path: "C:/Users/davif/AppData/Local/Temp/ss_10_loaded.png" });
  console.log("Modelo carregado");

  // Clica em "Ir para pintura"
  await page.click("text=Ir para pintura");
  await page.waitForTimeout(1000);
  await page.screenshot({ path: "C:/Users/davif/AppData/Local/Temp/ss_11_paint.png" });
  console.log("Modo pintura ativo");

  // Seleciona modo fill (conta-gotas)
  const fillBtn = page.locator("button:has-text('Conta-gotas')");
  await fillBtn.click();
  await page.waitForTimeout(300);

  // Clica no centro do canvas (no modelo)
  const canvas = page.locator("canvas");
  const box = await canvas.boundingBox();
  const cx = box.x + box.width * 0.58;
  const cy = box.y + box.height * 0.45;

  await page.mouse.click(cx, cy);
  await page.waitForTimeout(3000);
  await page.screenshot({ path: "C:/Users/davif/AppData/Local/Temp/ss_12_fill.png" });

  // Verifica se houve erro
  const errorVisible = await page.locator(".toast").isVisible().catch(() => false);
  const toastText = errorVisible ? await page.locator(".toast").textContent() : 'sem erro';
  console.log(`Resultado fill: ${errorVisible ? 'ERRO: ' + toastText : 'OK'}`);

  // Checa contador de faces
  const counter = await page.locator(".paint-counter").textContent().catch(() => '');
  console.log(`Faces selecionadas: ${counter}`);

  await browser.close();
})();
