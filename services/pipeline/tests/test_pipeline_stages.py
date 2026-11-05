"""Phase 1: staged pipeline, OCR for scanned pages, progress and idempotent retries (no Postgres needed)."""
import os
import sys
from pathlib import Path

import pymupdf
import pytest

os.environ.setdefault("JWT_SECRET", "test-secret-with-enough-length-32bytes")
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import jobs  # noqa: E402
from app.jobs import (  # noqa: E402
    RetryableJobError,
    parse_pdf_detailed,
    process_document,
    run_stage,
)
from app.pipeline.llm_client import LLMError  # noqa: E402
from app.repo import InMemoryRepo  # noqa: E402

SENTENCE = "A aprendizagem significativa ocorre quando o novo conteúdo se ancora em conhecimentos prévios."
NATIVE = (SENTENCE + " ") * 4

needs_ocr = pytest.mark.skipif(jobs.ocr_language() is None, reason="tesseract/tessdata not installed")


def make_mixed_pdf(path: Path, kinds: list[str]) -> Path:
    """kinds: 'text' (native layer), 'scan' (image only, no text layer), 'blank'."""
    out = pymupdf.open()
    for kind in kinds:
        page = out.new_page()
        if kind == "text":
            page.insert_textbox(pymupdf.Rect(40, 40, 560, 800), NATIVE, fontsize=11)
        elif kind == "scan":
            tmp = pymupdf.open()
            tp = tmp.new_page()
            tp.insert_textbox(pymupdf.Rect(40, 40, 560, 800), NATIVE, fontsize=16)
            pix = tp.get_pixmap(dpi=200)
            page.insert_image(page.rect, pixmap=pix)  # an image and no text layer: exactly a scan
    out.save(path)
    out.close()
    return path


class OneClaimLLM:
    model = "fake"

    def complete_json(self, system, user, schema, temperature=0.1):
        return {"claims": [{"concept": "Aprendizagem", "statement": "Ancoragem em conhecimentos prévios.",
                            "quote": SENTENCE, "page": 1}]}


def seed(tmp_path, kinds):
    repo = InMemoryRepo()
    storage = tmp_path / "st"
    (storage / "p").mkdir(parents=True)
    make_mixed_pdf(storage / "p" / "a.pdf", kinds)
    doc = repo.create_document("proj-1", {"title": "Artigo", "year": 2020, "storage_path": "p/a.pdf", "status": "pending"})
    return repo, storage, doc["id"]


@needs_ocr
def test_ocr_reads_scanned_pages_and_leaves_native_and_blank_pages_alone(tmp_path):
    pdf = make_mixed_pdf(tmp_path / "m.pdf", ["text", "scan", "blank"])
    pages = parse_pdf_detailed(pdf)
    assert [p.source for p in pages] == ["native", "ocr", "native"]
    assert "aprendizagem significativa" in pages[1].text.lower()  # OCR found the real text
    assert pages[2].text.strip() == ""  # a blank page is not sent to OCR


def test_ocr_can_be_disabled(tmp_path):
    pdf = make_mixed_pdf(tmp_path / "m.pdf", ["scan"])
    assert [p.source for p in parse_pdf_detailed(pdf, ocr=False)] == ["native"]


@needs_ocr
def test_scanned_book_becomes_analyzable_and_reports_ocr_pages(tmp_path):
    repo, storage, doc_id = seed(tmp_path, ["scan", "scan", "text"])
    status = process_document(repo, storage, doc_id, lambda: OneClaimLLM())
    doc = repo.get_document(doc_id)
    assert status == "extracted" and doc["status"] == "extracted"
    assert doc["progress"]["ocr_pages"] == 2
    assert repo.page_sources[doc_id] == ["ocr", "ocr", "native"]
    assert len(repo.claims) == 1


def test_scan_without_ocr_available_still_fails_cleanly(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "ocr_language", lambda: None)
    repo, storage, doc_id = seed(tmp_path, ["scan", "scan"])
    assert process_document(repo, storage, doc_id, lambda: OneClaimLLM()) == "failed"


def test_parse_quality_is_the_share_of_pages_with_text(tmp_path):
    repo, storage, doc_id = seed(tmp_path, ["text", "text", "blank", "text"])
    run_stage(repo, storage, doc_id, "parse", lambda: None)
    assert repo.get_document(doc_id)["parse_quality"] == 0.75
    assert repo.get_document(doc_id)["status"] == "parsed"


def test_parse_always_chains_to_index_and_index_to_extract_only_when_llm_exists(tmp_path):
    repo, storage, doc_id = seed(tmp_path, ["text"])
    assert run_stage(repo, storage, doc_id, "parse", lambda: None) == "index"  # indexing needs no LLM
    assert run_stage(repo, storage, doc_id, "index", lambda: None) is None
    assert repo.get_document(doc_id)["stage"] is None  # nothing else is coming
    assert repo.chunks  # searchable without any LLM

    repo2, storage2, doc2 = seed(tmp_path / "b", ["text"])
    assert run_stage(repo2, storage2, doc2, "parse", lambda: OneClaimLLM()) == "index"
    assert run_stage(repo2, storage2, doc2, "index", lambda: OneClaimLLM()) == "extract"  # LLM without embeddings
    assert repo2.get_document(doc2)["stage"] == "extract"  # queued: the UI keeps polling
    assert run_stage(repo2, storage2, doc2, "extract", lambda: OneClaimLLM()) == "summarize"
    assert run_stage(repo2, storage2, doc2, "summarize", lambda: OneClaimLLM()) is None
    assert repo2.get_document(doc2)["stage"] is None


def test_extract_stage_is_idempotent(tmp_path):
    repo, storage, doc_id = seed(tmp_path, ["text"])
    run_stage(repo, storage, doc_id, "parse", lambda: OneClaimLLM())
    run_stage(repo, storage, doc_id, "extract", lambda: OneClaimLLM())
    run_stage(repo, storage, doc_id, "extract", lambda: OneClaimLLM())  # a retry after a crash
    assert len(repo.claims) == 1


def test_extract_raises_retryable_when_every_chunk_fails(tmp_path):
    class Down:
        model = "down"

        def complete_json(self, *a, **k):
            raise LLMError("fora do ar")

    repo, storage, doc_id = seed(tmp_path, ["text"])
    run_stage(repo, storage, doc_id, "parse", lambda: Down())
    with pytest.raises(RetryableJobError):
        run_stage(repo, storage, doc_id, "extract", lambda: Down())
    assert repo.get_document(doc_id)["status"] == "parsed"  # honest: parsed, not falsely failed yet
    assert repo.claims == []


def test_progress_is_reported_per_phase(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "PROGRESS_EVERY_SECONDS", 0.0)
    repo, storage, doc_id = seed(tmp_path, ["text", "text", "text"])
    seen = []
    orig = repo.update_document
    repo.update_document = lambda d, **f: (seen.append(f.get("progress")), orig(d, **f))[1]
    run_stage(repo, storage, doc_id, "parse", lambda: None)
    parse_steps = [p for p in seen if p and p.get("phase") == "parse"]
    assert [p["done"] for p in parse_steps] == [1, 2, 3] and parse_steps[0]["total"] == 3


def test_heartbeat_is_called_during_long_stages(tmp_path):
    repo, storage, doc_id = seed(tmp_path, ["text", "text", "text"])
    beats = []
    run_stage(repo, storage, doc_id, "parse", lambda: None, heartbeat=lambda: beats.append(1))
    assert len(beats) >= 3
