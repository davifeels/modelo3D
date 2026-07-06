import { chromium } from "playwright";

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1280, height: 800 });

  // 1. Tela inicial
  await page.goto("http://localhost:5173");
  await page.waitForTimeout(1500);
  await page.screenshot({ path: "C:/Users/davif/AppData/Local/Temp/ss_01_inicial.png" });
  console.log("SS1: tela inicial capturada");

  // 2. Upload do STL
  const fileInput = page.locator("input[type=file]");
  await fileInput.setInputFiles("C:/Users/davif/Downloads/figura_teste.stl");

  // Aguarda carregamento (backend processa + Three.js renderiza)
  await page.waitForTimeout(5000);
  await page.screenshot({ path: "C:/Users/davif/AppData/Local/Temp/ss_02_loaded.png" });
  console.log("SS2: apos upload capturada");

  // Checa texto na página
  const bodyText = await page.textContent("body");
  const hasFaces = bodyText.includes("face") || bodyText.includes("Face");
  const hasError = bodyText.toLowerCase().includes("erro") || bodyText.toLowerCase().includes("error");
  console.log(`Faces: ${hasFaces}, Erro: ${hasError}`);

  await browser.close();
})();
