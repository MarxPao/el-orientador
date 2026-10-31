import json
import sys
from pathlib import Path

import pymupdf
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from ingest import ingest_dir, ingest_pdf  # noqa: E402

LONG = "A aprendizagem significativa ocorre quando o conteÃºdo se relaciona ao que o aluno jÃ¡ sabe. " * 5


def make_pdf(path: Path, pages: list[str]) -> None:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        if text:
            page.insert_textbox(pymupdf.Rect(50, 50, 550, 780), text, fontsize=10)
    doc.save(path)
    doc.close()


def test_extracts_pages_and_saves_json(tmp_path: Path):
    pdf = tmp_path / "a.pdf"
    make_pdf(pdf, [LONG, LONG])
    r = ingest_pdf(pdf, tmp_path / "out")
    assert r.ok and r.has_text and len(r.pages) == 2
    data = json.loads((tmp_path / "out" / "a.json").read_text(encoding="utf-8"))
    assert data["n_pages"] == 2 and data["doc_id"] == "a"


def test_reports_pdf_without_text(tmp_path: Path):
    pdf = tmp_path / "scan.pdf"
    make_pdf(pdf, ["", ""])
    r = ingest_pdf(pdf, tmp_path / "out")
    assert r.ok and not r.has_text


def test_corrupted_pdf_does_not_raise(tmp_path: Path):
    pdf = tmp_path / "bad.pdf"
    pdf.write_bytes(b"not a pdf")
    r = ingest_pdf(pdf, tmp_path / "out")
    assert not r.ok and r.error


def test_ingest_dir_processes_all(tmp_path: Path):
    make_pdf(tmp_path / "a.pdf", [LONG])
    (tmp_path / "bad.pdf").write_bytes(b"x")
    results = ingest_dir(tmp_path, tmp_path / "out")
    assert [r.pdf for r in results] == ["a.pdf", "bad.pdf"]
