"""T0.3 - PDF ingestion: PDF -> list of page texts (PyMuPDF), saved as JSON.

Usage:
    python ingest.py [pdf_dir] [out_dir]
Defaults: data/pdfs -> out/pages

Privacy: page text is written only to the local JSON output, never to logs.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

MIN_TEXT_CHARS = 200  # fewer total characters than this => probably a scanned PDF


@dataclass
class IngestResult:
    pdf: str
    pages: list[str]
    ok: bool
    error: str | None = None

    @property
    def total_chars(self) -> int:
        return sum(len(p) for p in self.pages)

    @property
    def has_text(self) -> bool:
        return self.total_chars >= MIN_TEXT_CHARS


def extract_pages(pdf_path: Path) -> list[str]:
    """Return the text of each page (page 1 first)."""
    import pymupdf

    with pymupdf.open(pdf_path) as doc:
        return [page.get_text("text") for page in doc]


def ingest_pdf(pdf_path: Path, out_dir: Path) -> IngestResult:
    """Extract one PDF and save `<out_dir>/<stem>.json`. Never raises."""
    try:
        pages = extract_pages(pdf_path)
    except Exception as exc:  # corrupted, encrypted, etc.
        return IngestResult(pdf_path.name, [], False, f"{type(exc).__name__}: {exc}")
    result = IngestResult(pdf_path.name, pages, True)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {"doc_id": pdf_path.stem, "source": pdf_path.name, "n_pages": len(pages), "pages": pages}
    (out_dir / f"{pdf_path.stem}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return result


def ingest_dir(pdf_dir: Path, out_dir: Path) -> list[IngestResult]:
    return [ingest_pdf(p, out_dir) for p in sorted(pdf_dir.glob("*.pdf"))]


def main(argv: list[str]) -> int:
    base = Path(__file__).parent
    pdf_dir = Path(argv[1]) if len(argv) > 1 else base / "data" / "pdfs"
    out_dir = Path(argv[2]) if len(argv) > 2 else base / "out" / "pages"
    results = ingest_dir(pdf_dir, out_dir)
    if not results:
        print(f"Nenhum PDF encontrado em {pdf_dir}")
        return 1
    for r in results:
        if not r.ok:
            print(f"[ERRO]      {r.pdf}: {r.error}")
        elif not r.has_text:
            print(f"[SEM TEXTO] {r.pdf}: {len(r.pages)} pÃ¡ginas, {r.total_chars} caracteres (provÃ¡vel PDF escaneado)")
        else:
            print(f"[OK]        {r.pdf}: {len(r.pages)} pÃ¡ginas, {r.total_chars} caracteres")
    bad = [r for r in results if not r.ok or not r.has_text]
    print(f"\n{len(results) - len(bad)}/{len(results)} PDFs com texto extraÃ­do.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
