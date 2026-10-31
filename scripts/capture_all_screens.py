"""Capture high-resolution screenshots of all screens in El Orientador using Playwright and local Chrome."""
from __future__ import annotations

import time
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path(__file__).parent.parent / "screenshots"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BASE_URL = "http://localhost:3000"
API_URL = "http://127.0.0.1:8000"


def setup_demo_data() -> tuple[str, str]:
    """Login and ensure demo project has rich, realistic data for screenshots."""
    client = httpx.Client(base_url=API_URL, timeout=15)
    r = client.post("/auth/login", json={"email": "demo@exemplo.com", "password": "demo-senha-1"})
    token = r.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Get project
    projects = client.get("/projects", headers=headers).json()
    demo_proj = next((p for p in projects if "demonstração" in p["title"].lower()), projects[0])
    pid = demo_proj["id"]

    # 1. Complete one node, skip one node
    try:
        client.post(
            f"/projects/{pid}/tree/nodes/tema_delimitacao/gate",
            json={
                "user_input": "Delimitação do papel das metodologias ativas e mediação pedagógica no ensino médio brasileiro com mais de oitenta caracteres.",
                "history": [],
            },
            headers=headers,
        )
        client.post(
            f"/projects/{pid}/tree/nodes/problema_pesquisa/gate",
            json={"skip": True, "skip_reason": "Problema alinhado previamente com o orientador em projeto de iniciação científica."},
            headers=headers,
        )
    except Exception as e:
        print("Note on gate setup:", e)

    # 2. Enrich first section in editor
    try:
        sections = client.get(f"/projects/{pid}/sections", headers=headers).json()
        if sections:
            sec0 = sections[0]
            content = {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": "A aprendizagem significativa ocorre quando o novo conhecimento se relaciona de forma substantiva aos saberes prévios do estudante. Ao articular os conceitos prévios à mediação pedagógica estruturada, o aluno desenvolve autonomia reflexiva e capacidade crítica de resolução de problemas acadêmicos complexos."
                            }
                        ]
                    },
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": "Neste panorama, a motivação intrínseca desponta como alavanca fundamental para a sustentação do engajamento em projetos de pesquisa de fôlego longo, a exemplo do Trabalho de Conclusão de Curso (TCC)."
                            }
                        ]
                    }
                ]
            }
            client.patch(f"/projects/{pid}/sections/{sec0['id']}", json={"content": content}, headers=headers)
            
            # Add advisor comment
            client.post(
                f"/projects/{pid}/sections/{sec0['id']}/comments",
                json={"content": "Excelente fundamentação teórica inicial. No próximo parágrafo, explicite como a motivação afeta os índices de evasão observados."},
                headers=headers
            )
    except Exception as e:
        print("Note on section setup:", e)

    # 3. Generate advisor progress report
    try:
        reps = client.get(f"/projects/{pid}/reports", headers=headers).json()
        if not reps:
            client.post(f"/projects/{pid}/reports", headers=headers)
    except Exception as e:
        print("Note on report setup:", e)

    return token, pid


def capture_all():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Diretório de saída: {OUTPUT_DIR}")

    print("Configurando dados de demonstração...")
    token, pid = setup_demo_data()
    print(f"Token obtido com sucesso. Projeto ID: {pid}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
        )

        context = browser.new_context(
            viewport={"width": 1440, "height": 940},
            device_scale_factor=1.5,
            locale="pt-BR"
        )

        page = context.new_page()

        # ---------------------------------------------------------------------
        # 1. Tela de Login (/entrar)
        # ---------------------------------------------------------------------
        print("1. Capturando 01_login.png...")
        page.goto(f"{BASE_URL}/entrar", wait_until="networkidle")
        page.wait_for_selector("text=El Orientador")
        time.sleep(0.5)
        page.screenshot(path=str(OUTPUT_DIR / "01_login.png"))

        # ---------------------------------------------------------------------
        # 2. Tela de Cadastro (/entrar com modo Criar conta)
        # ---------------------------------------------------------------------
        print("2. Capturando 02_cadastro.png...")
        page.click("button:has-text('Não tenho conta')")
        time.sleep(0.5)
        page.screenshot(path=str(OUTPUT_DIR / "02_cadastro.png"))

        # Voltar para o modo de login e logar pelo formulário
        page.click("button:has-text('Já tenho conta')")
        time.sleep(0.3)
        page.fill("input[name='email']", "demo@exemplo.com")
        page.fill("input[name='password']", "demo-senha-1")
        page.click("button:has-text('Entrar')")
        page.wait_for_selector("text=Seus projetos", timeout=15000)
        time.sleep(0.8)

        # ---------------------------------------------------------------------
        # 3. Painel de Projetos (/projetos)
        # ---------------------------------------------------------------------
        print("3. Capturando 03_projetos.png...")
        page.screenshot(path=str(OUTPUT_DIR / "03_projetos.png"))

        # ---------------------------------------------------------------------
        # 4. Árvore de Progresso (/projetos/[id]/arvore)
        # ---------------------------------------------------------------------
        print("4. Capturando 04_arvore_progresso.png...")
        page.goto(f"{BASE_URL}/projetos/{pid}/arvore", wait_until="networkidle")
        page.wait_for_selector("text=Árvore de Progresso", timeout=15000)
        time.sleep(1.2)
        page.screenshot(path=str(OUTPUT_DIR / "04_arvore_progresso.png"))

        # ---------------------------------------------------------------------
        # 5. Gate Socrático Modal Dialog
        # ---------------------------------------------------------------------
        print("5. Capturando 05_gate_socratico.png...")
        gate_btn = page.query_selector("button:has-text('Passar pelo Gate Socrático')")
        if gate_btn:
            gate_btn.click()
            time.sleep(1.0)
            page.screenshot(path=str(OUTPUT_DIR / "05_gate_socratico.png"))
            close_btn = page.query_selector("button[aria-label='Fechar']")
            if close_btn:
                close_btn.click()
                time.sleep(0.8)

        # ---------------------------------------------------------------------
        # 6. Painel de Cronograma & Fila de Pesquisa
        # ---------------------------------------------------------------------
        print("6. Capturando 06_cronograma_painel.png...")
        expand_btn = page.query_selector("button:has-text('Visualizar projeção')")
        if expand_btn:
            expand_btn.click()
            time.sleep(0.5)
        
        schedule_header = page.query_selector("text=Cronograma & Prazos")
        if schedule_header:
            schedule_header.scroll_into_view_if_needed()
            time.sleep(0.5)
        page.screenshot(path=str(OUTPUT_DIR / "06_cronograma_painel.png"))

        # ---------------------------------------------------------------------
        # 7. Mapa de Conhecimento (/projetos/[id]/mapa)
        # ---------------------------------------------------------------------
        print("7. Capturando 07_mapa_conhecimento.png...")
        page.goto(f"{BASE_URL}/projetos/{pid}/mapa", wait_until="networkidle")
        time.sleep(2.0)  # Aguardar React Flow estabilizar renderização do grafo
        page.screenshot(path=str(OUTPUT_DIR / "07_mapa_conhecimento.png"))

        # ---------------------------------------------------------------------
        # 8. Painel de Evidência com Trecho Literal no Mapa
        # ---------------------------------------------------------------------
        print("8. Capturando 08_painel_evidencia.png...")
        evidence_btn = page.query_selector("button:has-text('Ver evidência')")
        if evidence_btn:
            evidence_btn.scroll_into_view_if_needed()
            evidence_btn.click()
            time.sleep(1.2)
            page.screenshot(path=str(OUTPUT_DIR / "08_painel_evidencia.png"))

        # ---------------------------------------------------------------------
        # 9. Editor Acadêmico (/projetos/[id]/editor)
        # ---------------------------------------------------------------------
        print("9. Capturando 09_manuscrito_editor.png...")
        page.goto(f"{BASE_URL}/projetos/{pid}/editor", wait_until="networkidle")
        page.wait_for_selector(".tiptap, [contenteditable='true']", timeout=15000)
        time.sleep(1.5)
        page.screenshot(path=str(OUTPUT_DIR / "09_manuscrito_editor.png"))

        # ---------------------------------------------------------------------
        # 10. Editor com Aba de Comentários do Orientador
        # ---------------------------------------------------------------------
        print("10. Capturando 10_editor_comentarios.png...")
        comments_tab = page.query_selector("button:has-text('Comentários')")
        if comments_tab:
            comments_tab.click()
            time.sleep(0.8)
            page.screenshot(path=str(OUTPUT_DIR / "10_editor_comentarios.png"))

        # ---------------------------------------------------------------------
        # 11. Relatório de Progresso para o Orientador Humano (/projetos/[id]/relatorio)
        # ---------------------------------------------------------------------
        print("11. Capturando 11_relatorio_orientador.png...")
        page.goto(f"{BASE_URL}/projetos/{pid}/relatorio", wait_until="networkidle")
        page.wait_for_selector("text=Relatório de Progresso", timeout=15000)
        time.sleep(1.5)
        page.screenshot(path=str(OUTPUT_DIR / "11_relatorio_orientador.png"), full_page=True)

        browser.close()
        print("\nTodas as 11 capturas foram geradas com sucesso em:", OUTPUT_DIR)


if __name__ == "__main__":
    capture_all()
