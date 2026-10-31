import io
import os
import sys
from pathlib import Path

from docx import Document
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-with-enough-length-32bytes")
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import create_app
from app.repo import InMemoryRepo


def make_client():
    repo = InMemoryRepo()
    app = create_app(repo=repo)
    return TestClient(app), repo


def register_and_create_project(c, title="TCC Editor"):
    r = c.post("/auth/register", json={"email": "editor@usp.br", "password": "password123", "name": "Aluno Editor"})
    token = r.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    p = c.post(
        "/projects",
        json={"title": title, "work": "tcc", "research_problem": "Como aplicar redes convolucionais em pequenas lavouras?"},
        headers=headers,
    ).json()
    return headers, p["id"]


def test_sections_lifecycle():
    c, repo = make_client()
    headers, pid = register_and_create_project(c)

    # 1. GET auto-seeds default sections
    r_list = c.get(f"/projects/{pid}/sections", headers=headers)
    assert r_list.status_code == 200
    sections = r_list.json()
    assert len(sections) == 5
    intro = sections[0]
    assert "Introdução" in intro["title"]

    # 2. POST create a new subsection
    r_create = c.post(
        f"/projects/{pid}/sections",
        json={"title": "1.1 Justificativa Prática", "parent_id": intro["id"], "position": 1},
        headers=headers,
    )
    assert r_create.status_code == 200
    sub_id = r_create.json()["id"]

    # 3. PATCH update content
    r_patch = c.patch(
        f"/projects/{pid}/sections/{sub_id}",
        json={"content": {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Texto elaborado."}]}]}},
        headers=headers,
    )
    assert r_patch.status_code == 200
    assert r_patch.json()["content"]["type"] == "doc"

    # 4. DELETE subsection
    r_del = c.delete(f"/projects/{pid}/sections/{sub_id}", headers=headers)
    assert r_del.status_code == 200
    sections_after = c.get(f"/projects/{pid}/sections", headers=headers).json()
    assert len(sections_after) == 5


def test_coherence_checks():
    c, repo = make_client()
    headers, pid = register_and_create_project(c)

    # Fetch initial sections
    sections = c.get(f"/projects/{pid}/sections", headers=headers).json()
    teorico = next(s for s in sections if "Referencial" in s["title"])

    # Update section with substantive text (> 40 words) but no sources linked
    long_text = "Esta pesquisa aborda a complexidade de algoritmos de aprendizado profundo aplicados ao reconhecimento " \
                "de padrões agronômicos. O desenvolvimento histórico dessas abordagens remonta a meados do século vinte " \
                "com os primeiros perceptrons e avançou até os modelos contemporâneos de atenção e transformadores neurais."
    c.patch(
        f"/projects/{pid}/sections/{teorico['id']}",
        json={"content": {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": long_text}]}]}},
        headers=headers,
    )

    # Check coherence
    r_coh = c.get(f"/projects/{pid}/coherence", headers=headers)
    assert r_coh.status_code == 200
    warnings = r_coh.json()

    # Should detect 'secao_sem_fonte' on the theoretical section
    sem_fonte = next((w for w in warnings if w["type"] == "secao_sem_fonte"), None)
    assert sem_fonte is not None
    assert sem_fonte["section_id"] == teorico["id"]


def test_export_docx_with_abnt_and_ai_declaration():
    c, repo = make_client()
    headers, pid = register_and_create_project(c, title="Monografia sobre Visão Computacional")

    # Add an AI log action
    repo.log_ai_usage(pid, "gate", "node-1", "gemini-2.0-flash", "socratic_gate_v0.1")

    # Request DOCX export
    r_export = c.get(f"/projects/{pid}/export/docx", headers=headers)
    assert r_export.status_code == 200
    assert "wordprocessingml.document" in r_export.headers["content-type"]
    assert len(r_export.content) > 1000

    # Parse DOCX with python-docx to verify content
    docx_file = io.BytesIO(r_export.content)
    doc = Document(docx_file)

    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "DECLARAÇÃO DE USO DE FERRAMENTAS DE INTELIGÊNCIA ARTIFICIAL" in full_text
    assert "El Orientador" in full_text
    assert "SUMÁRIO" in full_text
    assert "REFERÊNCIAS" in full_text

    # Verify AI usage table exists in document
    assert len(doc.tables) >= 1
    table_text = "\n".join(cell.text for row in doc.tables[0].rows for cell in row.cells)
    assert "gate" in table_text or "socratic_gate" in table_text
