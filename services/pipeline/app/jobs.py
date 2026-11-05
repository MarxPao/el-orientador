"""Document processing as a staged pipeline, plus the queues that run it.

Stages (each one idempotent, so a retry after a crash is always safe):
  parse     PDF -> pages. Pages without a text layer (scans) go through OCR, page by page.
  index     pages -> searchable chunks (no LLM needed: keyword search works as soon as this ends).
  embed     chunks -> vectors for semantic search (needs an embedding model; a failure here is not fatal).
  extract   pages -> claims with verified quotes (needs an LLM; without one the document stays `parsed`).
  summarize whole document -> AI summary by blocks of pages, labelled as AI-generated (needs an LLM; not fatal).

`run_stage` executes one stage and returns the next stage name (or None when the pipeline is over).
Queues:
  InlineQueue   runs the whole chain immediately (tests).
  ThreadQueue   one in-process worker thread (dev with InMemoryRepo).
  PgJobQueue    persistent Postgres queue with retries and crash recovery: see app/pgqueue.py.

Privacy: document text is never logged; errors carry only the exception type.
"""
from __future__ import annotations

import logging
import os
import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from .llm_gateway import call_json, text_schema
from .pipeline.extract import extract_claims
from .pipeline.llm import LLMClient
from .repo import Repo
from .search import chunk_pages

log = logging.getLogger("orientador.jobs")

MIN_TEXT_CHARS = 200  # fewer characters in the whole document (after OCR): nothing usable to analyse
MIN_PAGE_CHARS = 50  # a page with less text than this, but with an image, is treated as a scan
OCR_LANGS = os.environ.get("OCR_LANG", "por+eng")
OCR_DPI = int(os.environ.get("OCR_DPI", "200"))
PROGRESS_EVERY_SECONDS = 2.0

STAGE_PARSE = "parse"
STAGE_INDEX = "index"
STAGE_EMBED = "embed"
STAGE_EXTRACT = "extract"
STAGE_SUMMARIZE = "summarize"

EMBED_BATCH = 50
SUMMARY_PAGES_PER_BLOCK = 12
SUMMARY_MAX_BLOCKS = 60  # a 700-page book still costs at most 61 calls: longer books get bigger blocks
SUMMARY_BLOCK_CHARS = 14000
SUMMARY_VERSION = "summary_v1"
SUMMARIZE_ENABLED = os.environ.get("SUMMARIZE_DOCS", "1") != "0"  # AI summaries cost ~1 call per 12 pages
SUMMARY_SYSTEM = (
    "Você resume trechos de textos acadêmicos para um estudante. Use SOMENTE o que está no texto fornecido: não "
    "acrescente fatos, autores, números ou conclusões que não apareçam nele. Escreva em português, em 3 a 5 frases "
    "corridas, descrevendo o que o trecho trata e o que afirma. Se o trecho for ilegível ou sem conteúdo, diga isso."
)
SUMMARY_OVERVIEW_SYSTEM = (
    "Você recebe resumos sequenciais de partes de uma mesma obra. Escreva um panorama da obra inteira em um "
    "parágrafo de 4 a 7 frases, em português, usando SOMENTE o que consta nesses resumos. Não invente nada."
)

LLMFactory = Callable[[], LLMClient | None]  # returns None when no LLM is configured
Heartbeat = Callable[[], None]


class RetryableJobError(RuntimeError):
    """A transient failure (e.g. the LLM is down for every chunk). The queue retries with backoff."""


@dataclass(frozen=True)
class PageText:
    text: str
    source: str  # "native" | "ocr"


# ----------------------------------------------------------------------------- OCR
_ocr_lang_cache: tuple[str | None] | None = None


def ocr_language() -> str | None:
    """The installed subset of OCR_LANG (e.g. "por+eng"), or None when OCR cannot run at all."""
    global _ocr_lang_cache
    if _ocr_lang_cache is None:
        lang: str | None = None
        try:
            import pymupdf

            tessdata = Path(pymupdf.get_tessdata())
            present = [x for x in OCR_LANGS.split("+") if (tessdata / f"{x}.traineddata").exists()]
            lang = "+".join(present) or None
        except Exception:  # no tesseract data on this machine: OCR is simply unavailable
            lang = None
        _ocr_lang_cache = (lang,)
    return _ocr_lang_cache[0]


def reset_ocr_cache() -> None:
    global _ocr_lang_cache
    _ocr_lang_cache = None


def parse_pdf_detailed(
    path: Path,
    ocr: bool = True,
    on_page: Callable[[int, int, int], None] | None = None,
) -> list[PageText]:
    """Extract text page by page. `on_page(done, total, ocr_pages_so_far)` is called after each page.

    A page is OCR'd only when its text layer is (almost) empty AND it contains an image, so blank
    separator pages cost nothing. An OCR failure on one page never fails the document.
    """
    import pymupdf

    lang = ocr_language() if ocr else None
    pages: list[PageText] = []
    ocr_pages = 0
    with pymupdf.open(path) as doc:
        total = len(doc)
        for i, page in enumerate(doc, start=1):
            text = page.get_text("text")
            source = "native"
            if lang and len(text.strip()) < MIN_PAGE_CHARS and page.get_images():
                try:
                    tp = page.get_textpage_ocr(language=lang, dpi=OCR_DPI, full=True)
                    ocr_text = page.get_text("text", textpage=tp)
                    if len(ocr_text.strip()) > len(text.strip()):
                        text, source = ocr_text, "ocr"
                        ocr_pages += 1
                except Exception as exc:
                    log.warning("ocr failed on page %d: %s", i, type(exc).__name__)
            pages.append(PageText(text, source))
            if on_page:
                on_page(i, total, ocr_pages)
    return pages


def parse_pdf(path: Path) -> list[str]:
    return [p.text for p in parse_pdf_detailed(path)]


# ----------------------------------------------------------------------------- stages
class _Progress:
    """Throttled progress writer: at most one DB write every couple of seconds."""

    def __init__(self, repo: Repo, document_id: str, stage: str, heartbeat: Heartbeat | None) -> None:
        self.repo, self.document_id, self.stage, self.heartbeat = repo, document_id, stage, heartbeat
        self._last = 0.0

    def update(self, phase: str, done: int, total: int, force: bool = False, **extra) -> None:
        if self.heartbeat:
            self.heartbeat()
        now = time.monotonic()
        if not force and now - self._last < PROGRESS_EVERY_SECONDS:
            return
        self._last = now
        self.repo.update_document(
            self.document_id, stage=self.stage, progress={"phase": phase, "done": done, "total": total, **extra}
        )


def stage_parse(
    repo: Repo,
    storage_dir: Path,
    document_id: str,
    llm_factory: LLMFactory,
    heartbeat: Heartbeat | None = None,
) -> str | None:
    doc = repo.get_document(document_id)
    if not doc or not doc.get("storage_path"):
        return None
    prog = _Progress(repo, document_id, STAGE_PARSE, heartbeat)
    try:
        pages = parse_pdf_detailed(
            storage_dir / doc["storage_path"],
            on_page=lambda done, total, n_ocr: prog.update("ocr" if n_ocr else "parse", done, total, ocr_pages=n_ocr),
        )
    except Exception as exc:  # corrupted / encrypted PDF: permanent, retrying cannot help
        log.warning("parse failed for %s: %s", document_id, type(exc).__name__)
        repo.update_document(document_id, status="failed", stage=None, progress=None)
        return None
    repo.save_pages(document_id, [p.text for p in pages], sources=[p.source for p in pages])
    total_chars = sum(len(p.text) for p in pages)
    if total_chars < MIN_TEXT_CHARS:
        repo.update_document(document_id, status="failed", parse_quality=0.0, stage=None, progress=None)
        return None
    with_text = sum(1 for p in pages if len(p.text.strip()) >= MIN_PAGE_CHARS)
    n_ocr = sum(1 for p in pages if p.source == "ocr")
    if doc.get("metadata_source") == "filename":  # the student gave no title: read it from the PDF itself
        from .pdfmeta import extract_metadata

        meta = extract_metadata(storage_dir / doc["storage_path"])
        found = {k: v for k, v in meta.items() if k in ("title", "authors", "year") and v}
        if found.get("title"):
            repo.update_document(document_id, metadata_source="pdf", **found)
    nxt = STAGE_INDEX  # indexing needs no LLM, so every parsed document becomes searchable
    repo.update_document(
        document_id,
        status="parsed",
        parse_quality=round(with_text / len(pages), 3),
        stage=nxt,  # the next stage is queued: the UI keeps showing "in progress" until it finishes
        progress={"phase": "parsed", "done": len(pages), "total": len(pages), "ocr_pages": n_ocr},
    )
    return nxt


def _can_embed(client) -> bool:
    flag = getattr(client, "can_embed", None)  # LLMGateway exposes it (and honours the circuit breaker)
    return bool(flag) if flag is not None else callable(getattr(client, "embed", None))


def _embedder(client):
    """The active embedder (local model by default, or the LLM client when EMBED_PROVIDER=gemini), or None."""
    from .embeddings import resolve

    return resolve(client)


def stage_index(
    repo: Repo,
    document_id: str,
    llm_factory: LLMFactory,
    heartbeat: Heartbeat | None = None,
) -> str | None:
    doc = repo.get_document(document_id)
    if not doc:
        return None
    pages = repo.get_pages(document_id)
    chunks = chunk_pages(pages)
    repo.replace_chunks(document_id, chunks)  # replaces, so a retry or a reindex never duplicates
    if heartbeat:
        heartbeat()
    client = llm_factory()
    if _embedder(client) is not None:
        nxt = STAGE_EMBED
    else:
        nxt = STAGE_EXTRACT if client is not None else None
    repo.update_document(
        document_id,
        stage=nxt,
        progress={**(doc.get("progress") or {}), "phase": "indexed", "done": len(pages), "total": len(pages),
                  "chunks": len(chunks)},
    )
    return nxt


def stage_embed(
    repo: Repo,
    document_id: str,
    llm_factory: LLMFactory,
    heartbeat: Heartbeat | None = None,
) -> str | None:
    """Embed every chunk that has no vector from the current model. A provider failure ends the stage early and
    the pipeline moves on: the document stays searchable by keyword and a reindex finishes the job."""
    doc = repo.get_document(document_id)
    if not doc:
        return None
    client = llm_factory()
    nxt = STAGE_EXTRACT if client is not None else None
    embedder = _embedder(client)
    if embedder is None:
        repo.update_document(document_id, stage=nxt)
        return nxt
    model = getattr(embedder, "embed_model", None) or "embedding"
    done = 0
    try:
        while True:
            batch = repo.chunks_to_embed(document_id, model, EMBED_BATCH)
            if not batch:
                break
            vectors = embedder.embed([b["text"] for b in batch], task="document")
            repo.save_embeddings([(b["id"], v) for b, v in zip(batch, vectors)], model)
            done += len(batch)
            if heartbeat:
                heartbeat()
    except Exception as exc:  # not fatal: keyword search already works
        log.warning("embed stopped for %s after %d chunks: %s", document_id, done, type(exc).__name__)
    if done:
        repo.log_ai_usage(doc["project_id"], "embed", document_id, model, "embed_v1")
    repo.update_document(document_id, stage=nxt)
    return nxt


def _summary_blocks(pages: list[str]) -> list[tuple[int, int, str]]:
    per = max(SUMMARY_PAGES_PER_BLOCK, -(-len(pages) // SUMMARY_MAX_BLOCKS))
    blocks = []
    for start in range(0, len(pages), per):
        text = "\n\n".join(p.strip() for p in pages[start : start + per] if p.strip())
        if text:
            blocks.append((start + 1, min(start + per, len(pages)), text))
    return blocks


def stage_summarize(
    repo: Repo,
    document_id: str,
    llm_factory: LLMFactory,
    heartbeat: Heartbeat | None = None,
) -> str | None:
    doc = repo.get_document(document_id)
    if not doc:
        return None
    client = llm_factory()
    if client is None or doc.get("summary") or not SUMMARIZE_ENABLED:
        repo.update_document(document_id, stage=None)
        return None
    blocks = _summary_blocks(repo.get_pages(document_id))
    sections: list[dict] = []
    try:
        for i, (p0, p1, text) in enumerate(blocks, start=1):
            out = call_json(client, SUMMARY_SYSTEM, f"Trecho (páginas {p0} a {p1}):\n\n{text[:SUMMARY_BLOCK_CHARS]}",
                            text_schema("summary"), "summarize", temperature=0.1)
            sections.append({"page_start": p0, "page_end": p1, "summary": out["summary"].strip()})
            if heartbeat:
                heartbeat()
        if not sections:
            raise ValueError("nothing to summarize")
        if len(sections) == 1:
            overview = sections[0]["summary"]
        else:
            joined = "\n\n".join(f"[p. {x['page_start']}-{x['page_end']}] {x['summary']}" for x in sections)
            overview = call_json(client, SUMMARY_OVERVIEW_SYSTEM, joined[:60000], text_schema("summary"),
                                 "summarize_overview", temperature=0.1)["summary"].strip()
    except Exception as exc:  # not fatal: the document is already searchable and extracted
        log.warning("summary skipped for %s: %s", document_id, type(exc).__name__)
        repo.update_document(document_id, stage=None)
        return None
    model = getattr(client, "model", None)
    repo.log_ai_usage(doc["project_id"], "summarize", document_id, model, SUMMARY_VERSION)
    repo.update_document(
        document_id,
        stage=None,
        summary={"overview": overview, "sections": sections, "model": model, "prompt_version": SUMMARY_VERSION,
                 "ai_generated": True},
    )
    return None


def stage_extract(
    repo: Repo,
    document_id: str,
    llm_factory: LLMFactory,
    heartbeat: Heartbeat | None = None,
) -> str | None:
    doc = repo.get_document(document_id)
    if not doc:
        return None
    if repo.list_claims(document_id):  # a previous attempt already saved them: do not duplicate
        nxt = STAGE_SUMMARIZE if llm_factory() is not None else None
        repo.update_document(document_id, status="extracted", stage=nxt)
        return nxt
    client = llm_factory()
    pages = repo.get_pages(document_id)
    if client is None or not pages:
        repo.update_document(document_id, stage=None)
        return None
    prog = _Progress(repo, document_id, STAGE_EXTRACT, heartbeat)
    n_ocr = (doc.get("progress") or {}).get("ocr_pages", 0)  # keep what the parse stage reported
    result = extract_claims(
        pages,
        doc["title"],
        doc.get("year"),
        client,
        on_chunk=lambda done, total: prog.update("extract", done, total, ocr_pages=n_ocr),
    )
    model = getattr(client, "model", None)
    repo.log_ai_usage(doc["project_id"], "extract", document_id, model, result["prompt_version"])
    if result["errors"] and len(result["errors"]) == result["n_chunks"]:
        raise RetryableJobError("every extraction chunk failed")  # nothing to trust; try again later
    # only verified claims are persisted; rejected ones are discarded (counts only)
    repo.add_claims(document_id, [c.model_dump(mode="json") for c in result["accepted"]], model,
                    result["prompt_version"])
    repo.update_document(
        document_id,
        status="extracted",
        stage=STAGE_SUMMARIZE,
        progress={"phase": "extracted", "done": len(pages), "total": len(pages), "ocr_pages": n_ocr},
    )
    return STAGE_SUMMARIZE


def run_stage(
    repo: Repo,
    storage_dir: Path,
    document_id: str,
    stage: str,
    llm_factory: LLMFactory,
    heartbeat: Heartbeat | None = None,
) -> str | None:
    """Run one stage; return the next stage name, or None when the pipeline has finished."""
    if stage == STAGE_PARSE:
        return stage_parse(repo, storage_dir, document_id, llm_factory, heartbeat)
    if stage == STAGE_INDEX:
        return stage_index(repo, document_id, llm_factory, heartbeat)
    if stage == STAGE_EMBED:
        return stage_embed(repo, document_id, llm_factory, heartbeat)
    if stage == STAGE_EXTRACT:
        return stage_extract(repo, document_id, llm_factory, heartbeat)
    if stage == STAGE_SUMMARIZE:
        return stage_summarize(repo, document_id, llm_factory, heartbeat)
    raise ValueError(f"unknown stage: {stage}")


def process_document(
    repo: Repo, storage_dir: Path, document_id: str, llm_factory: LLMFactory, start: str = STAGE_PARSE
) -> str:
    """Run the chain from `start` inline (no retries) and return the final status. Used by the simple queues."""
    stage: str | None = start
    try:
        while stage:
            stage = run_stage(repo, storage_dir, document_id, stage, llm_factory)
    except RetryableJobError:
        repo.update_document(document_id, status="failed", stage=None)
        return "failed"
    doc = repo.get_document(document_id)
    return doc["status"] if doc else "failed"


# ----------------------------------------------------------------------------- simple queues
class JobQueue(Protocol):
    def enqueue(self, document_id: str, stage: str = STAGE_PARSE) -> None: ...


class InlineQueue:
    def __init__(self, repo: Repo, storage_dir: Path, llm_factory: LLMFactory) -> None:
        self._args = (repo, storage_dir, llm_factory)

    def enqueue(self, document_id: str, stage: str = STAGE_PARSE) -> None:
        process_document(*self._args[:2], document_id, self._args[2], stage)


class ThreadQueue:
    """One background worker in this process. Jobs are lost on restart: use PgJobQueue in production."""

    def __init__(self, repo: Repo, storage_dir: Path, llm_factory: LLMFactory) -> None:
        self._repo, self._storage, self._llm = repo, storage_dir, llm_factory
        self._q: queue.Queue[tuple[str, str]] = queue.Queue()
        threading.Thread(target=self._run, daemon=True, name="pipeline-worker").start()

    def enqueue(self, document_id: str, stage: str = STAGE_PARSE) -> None:
        self._q.put((document_id, stage))

    def _run(self) -> None:
        while True:
            document_id, stage = self._q.get()
            try:
                process_document(self._repo, self._storage, document_id, self._llm, stage)
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
