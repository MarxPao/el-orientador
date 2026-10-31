"""Claim extraction for one document, with deterministic quote verification (ported from prototype/extract.py).

Only claims whose quote is found in the document text are `accepted`; the LLM never confirms its own evidence.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from pydantic import ValidationError

from .llm import LLMClient
from .schemas import ExtractionOutput, VerifiedClaim
from .verify_quotes import verify_quote

PROMPTS_DIR = Path(os.environ.get("PROMPTS_DIR", Path(__file__).resolve().parents[4] / "prompts"))
PAGES_PER_CHUNK = 5
SCHEMA = ExtractionOutput.model_json_schema()
_TITLE_VERSION = re.compile(r"^#\s+\S+\s+[-\u2013\u2014]\s+(v[\w.]+)\s*$")


def load_prompt(name: str = "extract_claims.md") -> tuple[str, str, str]:
    """Parse a versioned prompt into (version, system, user_template). Version comes from the `# name - vX` title."""
    sections: dict[str, list[str]] = {}
    current = None
    version = "unknown"
    for line in (PROMPTS_DIR / name).read_text(encoding="utf-8").splitlines():
        m = _TITLE_VERSION.match(line)
        if m:
            version = m.group(1)
        elif line.startswith("## "):
            current = line[3:].strip().lower()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    user_text = "\n".join(sections.get("user (template)") or sections.get("contexto fornecido") or []).strip()
    system_text = "\n".join(sections.get("system") or []).strip()
    return version, system_text, user_text


def chunk_ranges(n_pages: int, size: int = PAGES_PER_CHUNK) -> list[tuple[int, int]]:
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


def extract_claims(
    pages: list[str], title: str, year: int | None, client: LLMClient, pages_per_chunk: int = PAGES_PER_CHUNK
) -> dict:
    """Return {accepted, rejected, errors, n_chunks, prompt_version}. `accepted` are VerifiedClaim objects."""
    version, system, template = load_prompt()
    accepted: list[VerifiedClaim] = []
    rejected: list[VerifiedClaim] = []
    errors: list[dict] = []
    ranges = chunk_ranges(len(pages), pages_per_chunk)
    for start, end in ranges:
        user = build_user_prompt(template, title, str(year or "s.d."), pages, start, end)
        try:
            output = ExtractionOutput.model_validate(client.complete_json(system, user, SCHEMA))
        except (ValidationError, RuntimeError) as exc:  # LLMError is a RuntimeError
            errors.append({"pages": [start, end], "error": type(exc).__name__})  # no content in logs
            continue
        for c in output.claims:
            r = verify_quote(c.quote, pages, expected_page=c.page)  # against the WHOLE document
            vc = VerifiedClaim(**c.model_dump(), quote_verified=r.found, verify_method=r.method,
                               page_verified=r.page, char_start=r.start, char_end=r.end)
            (accepted if r.found else rejected).append(vc)
    return {"accepted": accepted, "rejected": rejected, "errors": errors, "n_chunks": len(ranges),
            "prompt_version": version}
