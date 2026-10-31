"""T0.5 - Claim extraction per document, with deterministic quote verification.

Usage:
    python extract.py [pages_dir] [out_dir]
Defaults: out/pages -> out   (needs LLM_API_KEY; see llm_client.py)

Rule: only claims whose quote is found in the document text are `accepted`.
Quote verification is done by code (verify_quotes.py), never by the LLM.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import ValidationError

from llm import LLMClient
from pipeline import verify_extraction
from schemas import ExtractionOutput

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "extract_claims.md"
PAGES_PER_CHUNK = 5
SCHEMA = ExtractionOutput.model_json_schema()


def load_prompt(path: Path = PROMPT_PATH) -> tuple[str, str]:
    """Parse the versioned prompt file into (system, user_template)."""
    sections: dict[str, list[str]] = {}
    current = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            current = line[3:].strip().lower()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    system = "\n".join(sections.get("system") or []).strip()
    user = "\n".join(sections.get("user (template)") or sections.get("contexto fornecido") or []).strip()
    return system, user


def chunk_ranges(n_pages: int, size: int = PAGES_PER_CHUNK) -> list[tuple[int, int]]:
    """1-based inclusive (start, end) page ranges."""
    return [(s, min(s + size - 1, n_pages)) for s in range(1, n_pages + 1, size)]


def build_user_prompt(template: str, title: str, year: str, pages: list[str], start: int, end: int) -> str:
    text = "\n\n".join(f"[Página {n}]\n{pages[n - 1]}" for n in range(start, end + 1))
    return (
        template.replace("{title}", title)
        .replace("{year}", year)
        .replace("{page_start}", str(start))
        .replace("{page_end}", str(end))
        .replace("{pages_text_with_page_markers}", text)
    )


def extract_document(
    doc: dict,
    client: LLMClient,
    pages_per_chunk: int = PAGES_PER_CHUNK,
    prompt: tuple[str, str] | None = None,
) -> dict:
    """Extract and verify claims for one ingested document (`ingest.py` JSON)."""
    system, template = prompt or load_prompt()
    pages: list[str] = doc["pages"]
    title = doc.get("title") or doc["doc_id"]
    year = str(doc.get("year") or "s.d.")
    accepted: list[dict] = []
    rejected: list[dict] = []
    errors: list[dict] = []
    for start, end in chunk_ranges(len(pages), pages_per_chunk):
        user = build_user_prompt(template, title, year, pages, start, end)
        try:
            raw = client.complete_json(system, user, SCHEMA)
            output = ExtractionOutput.model_validate(raw)
        except (ValidationError, RuntimeError) as exc:  # LLMError is a RuntimeError
            errors.append({"pages": [start, end], "error": f"{type(exc).__name__}: {str(exc)[:200]}"})
            continue
        # verify against the WHOLE document: LLMs often misreport pages
        acc, rej = verify_extraction(output, pages)
        accepted += [c.model_dump(mode="json") for c in acc]
        rejected += [c.model_dump(mode="json") for c in rej]
    total = len(accepted) + len(rejected)
    return {
        "doc_id": doc["doc_id"],
        "n_pages": len(pages),
        "accepted": accepted,
        "rejected": rejected,
        "errors": errors,
        "n_chunks": len(chunk_ranges(len(pages), pages_per_chunk)),
        "approval_rate": (len(accepted) / total) if total else None,
    }


def main(argv: list[str]) -> int:
    from llm_client import GeminiClient, LLMError

    base = Path(__file__).parent
    pages_dir = Path(argv[1]) if len(argv) > 1 else base / "out" / "pages"
    out_dir = Path(argv[2]) if len(argv) > 2 else base / "out"
    files = sorted(pages_dir.glob("*.json"))
    if not files:
        print(f"Nenhum JSON de páginas em {pages_dir}. Rode ingest.py primeiro.")
        return 1
    try:
        client = GeminiClient()
    except LLMError as exc:
        print(exc)
        return 1
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in files:
        doc = json.loads(f.read_text(encoding="utf-8"))
        result = extract_document(doc, client)
        (out_dir / f"{doc['doc_id']}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        rate = result["approval_rate"]
        rate_txt = "n/d" if rate is None else f"{rate:.0%}"
        print(f"{doc['doc_id']}: {len(result['accepted'])} aceitos, {len(result['rejected'])} rejeitados "
              f"(aprovação {rate_txt}), {len(result['errors'])} blocos com erro")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
