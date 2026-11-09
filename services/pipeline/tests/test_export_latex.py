"""Unit and integration tests for ABNT LaTeX & Overleaf package generator (T7.3)."""
import io
import os
import sys
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-with-enough-length-32bytes")
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.export_latex import (
    build_latex_package,
    escape_latex,
    slugify_cite_key,
    tiptap_to_latex,
)
from app.main import create_app
from app.repo import InMemoryRepo


def test_escape_latex():
    raw = "Análise de 50% dos dados & resultados: $100 #tag _sub_ {chave} ~til ^circ \\barra"
    escaped = escape_latex(raw)
    assert r"\%" in escaped
    assert r"\&" in escaped
    assert r"\$" in escaped
    assert r"\#" in escaped
    assert r"\_" in escaped
    assert r"\{" in escaped
    assert r"\}" in escaped
    assert r"\textasciitilde{}" in escaped
    assert r"\textasciicircum{}" in escaped
    assert r"\textbackslash{}" in escaped


def test_tiptap_to_latex_structures():
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "heading",
                "attrs": {"level": 1},
                "content": [{"type": "text", "text": "Metodologia Proposta"}],
            },
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Este texto contém "},
                    {"type": "text", "marks": [{"type": "bold"}], "text": "negrito"},
                    {"type": "text", "text": " e "},
                    {"type": "text", "marks": [{"type": "italic"}], "text": "itálico"},
                    {"type": "text", "text": "."},
                ],
            },
            {
                "type": "blockquote",
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "Citação direta longa com recuo de 4cm da margem esquerda."}]}
                ],
            },
            {
                "type": "bulletList",
                "content": [
                    {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Item 1"}]}]},
                    {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Item 2"}]}]},
                ],
            },
        ],
    }

    latex = tiptap_to_latex(doc, base_heading_level=1)
    assert r"\section{Metodologia Proposta}" in latex
    assert r"\textbf{negrito}" in latex
    assert r"\textit{itálico}" in latex
    assert r"\begin{citacao}" in latex
    assert r"\end{citacao}" in latex
    assert r"\begin{itemize}" in latex
    assert r"\item Item 1" in latex
    assert r"\end{itemize}" in latex


def test_slugify_cite_key():
    doc = {"authors": ["José da Silva", "Maria Santos"], "year": 2021}
    key = slugify_cite_key(doc, 1)
    assert key == "silva2021"

    doc_anon = {"authors": [], "year": 2019}
    key_anon = slugify_cite_key(doc_anon, 3)
    assert key_anon == "anon2019"


def test_build_latex_package_zip_contents():
    repo = InMemoryRepo()
    u = repo.create_user("pesquisador@usp.br", "Pesquisador USP", "hash")
    p = repo.create_project(u["id"], {
        "title": "Redes Neurais na Educação",
        "work": "dissertacao",
        "institution": "Universidade de São Paulo",
    })
    pid = p["id"]

    # Add section and document
    sec = repo.create_section(pid, "Introdução", None, 1)
    repo.update_section(pid, sec["id"], content={
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Contextualização da pesquisa."}]}],
    })

    doc = repo.create_document(pid, {
        "title": "Machine Learning in Higher Ed",
        "authors": ["John Doe", "Jane Smith"],
        "year": 2022,
        "venue": "Computers & Education",
        "doi": "10.1016/j.compedu.2022.01",
    })

    zip_bytes = build_latex_package(repo, pid, include_approval=True, include_ai_declaration=True)
    assert isinstance(zip_bytes, io.BytesIO)

    with zipfile.ZipFile(zip_bytes, "r") as zf:
        namelist = zf.namelist()
        assert "main.tex" in namelist
        assert "referencias.bib" in namelist
        assert "INSTRUCOES_OVERLEAF.md" in namelist
        assert "elementos_pre_textuais/folha_aprovacao.tex" in namelist
        assert "elementos_pre_textuais/declaracao_ia.tex" in namelist
        assert any(n.startswith("capitulos/") and n.endswith(".tex") for n in namelist)

        # Inspect main.tex
        main_tex = zf.read("main.tex").decode("utf-8")
        assert r"\documentclass" in main_tex
        assert "abntex2" in main_tex
        assert "Redes Neurais na Educação" in main_tex
        assert r"\tableofcontents*" in main_tex
        assert r"\bibliography{referencias}" in main_tex

        # Inspect referencias.bib
        bib = zf.read("referencias.bib").decode("utf-8")
        assert "@article" in bib or "@misc" in bib
        assert "Machine Learning in Higher Ed" in bib
        assert "smith2022" in bib or "doe2022" in bib

        # Inspect declaracao_ia.tex (Rule 5)
        decl = zf.read("elementos_pre_textuais/declaracao_ia.tex").decode("utf-8")
        assert "Declaração de Uso de Ferramentas de Inteligência Artificial" in decl
        assert "Prisma de Autoria" in decl


def test_export_latex_api_endpoint():
    repo = InMemoryRepo()
    app = create_app(repo=repo, client=None)
    client = TestClient(app)

    # Auth & project
    r_auth = client.post("/auth/register", json={"email": "autor@unicamp.br", "password": "senha-segura-123", "name": "Autor Unicamp"})
    assert r_auth.status_code == 201
    token = r_auth.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    r_proj = client.post("/projects", json={"title": "Física Quântica Aplicada", "work": "tese"}, headers=headers)
    assert r_proj.status_code == 201
    pid = r_proj.json()["id"]

    # Call export endpoint
    r_exp = client.get(f"/projects/{pid}/export/latex", headers=headers)
    assert r_exp.status_code == 200
    assert r_exp.headers["Content-Type"] == "application/zip"
    assert "attachment; filename=" in r_exp.headers["Content-Disposition"]
    assert "overleaf.zip" in r_exp.headers["Content-Disposition"]

    # Verify returned bytes are a valid zip archive
    zip_bytes = io.BytesIO(r_exp.content)
    with zipfile.ZipFile(zip_bytes, "r") as zf:
        namelist = zf.namelist()
        assert "main.tex" in namelist
        assert "referencias.bib" in namelist
        main_text = zf.read("main.tex").decode("utf-8")
        assert "Física Quântica Aplicada" in main_text
