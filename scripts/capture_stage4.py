import time
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT_DIR = Path("screenshots/depois")
OUT_DIR.mkdir(parents=True, exist_ok=True)
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def hide_dev_indicator(page):
    page.add_style_tag(content="nextjs-portal { display: none !important; }")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
        )
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 940},
            device_scale_factor=1.5,
            locale="pt-BR",
        )
        page = ctx.new_page()

        print("1. Capturando 01_login.png...")
        page.goto("http://localhost:3000/entrar", wait_until="networkidle")
        page.evaluate("() => document.fonts.ready")
        hide_dev_indicator(page)
        time.sleep(0.8)
        page.screenshot(path=str(OUT_DIR / "01_login.png"))

        print("2. Capturando 02_cadastro.png...")
        page.click("button:has-text('Não tenho conta')")
        time.sleep(0.5)
        page.screenshot(path=str(OUT_DIR / "02_cadastro.png"))

        print("3. Capturando 03_projetos.png...")
        page.click("button:has-text('Já tenho conta')")
        time.sleep(0.3)
        page.fill("input[name='email']", "demo@exemplo.com")
        page.fill("input[name='password']", "demo-senha-1")
        page.click("button:has-text('Entrar')")
        page.wait_for_selector("text=Próxima etapa:", timeout=15000)
        page.evaluate("() => document.fonts.ready")
        hide_dev_indicator(page)
        time.sleep(0.8)
        page.screenshot(path=str(OUT_DIR / "03_projetos.png"))

        browser.close()
        print("Capturas da Etapa 4 concluídas em:", OUT_DIR.resolve())


if __name__ == "__main__":
    main()
