"""Document processing job and the queue that runs it.

process_document: PDF -> pages -> claims with verified quotes -> persisted. Never logs document text.
Queues: ThreadQueue (one background worker, used by the API) and InlineQueue (runs immediately, for tests).
A Postgres-backed queue can replace these later behind the same `enqueue(document_id)` interface.
"""
from __future__ import annotations

import logging
import queue
import threading
from pathlib import Path
from typing import Callable, Protocol

from .pipeline.extract import extract_claims
from .pipeline.llm import LLMClient
from .repo import Repo

log = logging.getLogger("orientador.jobs")
MIN_TEXT_CHARS = 200  # fewer characters in total: probably a scanned PDF (no OCR in the MVP)

LLMFactory = Callable[[], LLMClient | None]  # returns None when no LLM is configured


def parse_pdf(path: Path) -> list[str]:
    import pymupdf

    with pymupdf.open(path) as doc:
        return [page.get_text("text") for page in doc]


def process_document(repo: Repo, storage_dir: Path, document_id: str, llm_factory: LLMFactory) -> str:
    """Run the pipeline for one document and return its final status."""
    doc = repo.get_document(document_id)
    if not doc or not doc.get("storage_path"):
        return "failed"
    try:
        pages = parse_pdf(storage_dir / doc["storage_path"])
    except Exception as exc:  # corrupted / encrypted PDF
        log.warning("parse failed for %s: %s", document_id, type(exc).__name__)
        repo.update_document(document_id, status="failed")
        return "failed"
    repo.save_pages(document_id, pages)
    total_chars = sum(len(p) for p in pages)
    if total_chars < MIN_TEXT_CHARS:
        repo.update_document(document_id, status="failed", parse_quality=0.0)
        return "failed"
    repo.update_document(document_id, status="parsed", parse_quality=1.0)

    client = llm_factory()
    if client is None:  # no LLM configured: keep the parsed text, extraction waits
        return "parsed"
    result = extract_claims(pages, doc["title"], doc.get("year"), client)
    model = getattr(client, "model", None)
    repo.log_ai_usage(doc["project_id"], "extract", document_id, model, result["prompt_version"])
    if result["errors"] and len(result["errors"]) == result["n_chunks"]:
        repo.update_document(document_id, status="failed")  # every chunk failed: nothing to trust
        return "failed"
    # only verified claims are persisted; rejected ones are discarded (counts only)
    repo.add_claims(document_id, [c.model_dump(mode="json") for c in result["accepted"]], model,
                    result["prompt_version"])
    repo.update_document(document_id, status="extracted")
    return "extracted"


class JobQueue(Protocol):
    def enqueue(self, document_id: str) -> None: ...


class InlineQueue:
    def __init__(self, repo: Repo, storage_dir: Path, llm_factory: LLMFactory) -> None:
        self._args = (repo, storage_dir, llm_factory)

    def enqueue(self, document_id: str) -> None:
        process_document(*self._args[:2], document_id, self._args[2])


class ThreadQueue:
    def __init__(self, repo: Repo, storage_dir: Path, llm_factory: LLMFactory) -> None:
        self._repo, self._storage, self._llm = repo, storage_dir, llm_factory
        self._q: queue.Queue[str] = queue.Queue()
        threading.Thread(target=self._run, daemon=True, name="pipeline-worker").start()

    def enqueue(self, document_id: str) -> None:
        self._q.put(document_id)

    def _run(self) -> None:
        while True:
            document_id = self._q.get()
            try:
                process_document(self._repo, self._storage, document_id, self._llm)
            except Exception as exc:  # a bad job must never kill the worker
                log.error("job failed for %s: %s", document_id, type(exc).__name__)
                try:
                    self._repo.update_document(document_id, status="failed")
                except Exception:
                    pass
            finally:
                self._q.task_done()

    def join(self) -> None:
        self._q.join()
