"""Deterministic verification that a quote really exists in a document.

The LLM never confirms its own evidence: this code does.
Methods:
  exact -> match after safe normalization (case, spacing, quotes, ligatures, line-break hyphenation)
  loose -> match comparing only letters and digits (tolerates hyphen/space/punctuation differences)
  none  -> not found
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass

MIN_QUOTE_CHARS = 20  # shorter quotes match too easily and prove nothing

_HYPHENS = "-\u2010\u2011"
_TRANS = str.maketrans(
    {
        "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
        "\u201c": '"', "\u201d": '"', "\u201e": '"',
        "\u2013": "-", "\u2014": "-", "\u2212": "-",
    }
)


def normalize_with_map(text: str, loose: bool = False) -> tuple[str, list[int]]:
    """Return (normalized_text, index_map). index_map[i] is the original offset of char i."""
    out: list[str] = []
    idx: list[int] = []
    n = len(text)
    i = 0
    prev_space = True
    while i < n:
        ch = text[i]
        if ch == "\u00ad":  # soft hyphen
            i += 1
            continue
        if not loose and ch in _HYPHENS and i > 0 and text[i - 1].isalpha() and i + 1 < n and text[i + 1] in "\r\n":
            j = i + 1
            while j < n and text[j].isspace():
                j += 1
            if j < n and text[j].isalpha():  # word broken across lines: join it
                i = j
                continue
        if ch.isspace():
            if not loose and not prev_space:
                out.append(" ")
                idx.append(i)
                prev_space = True
            i += 1
            continue
        piece = unicodedata.normalize("NFKC", ch).translate(_TRANS).casefold()
        for c in piece:
            if loose and not c.isalnum():
                continue
            out.append(c)
            idx.append(i)
        prev_space = False
        i += 1
    return "".join(out), idx


@dataclass(frozen=True)
class VerifyResult:
    found: bool
    method: str  # exact | loose | none | too_short
    page: int | None = None  # 1-based
    start: int | None = None  # offset in the ORIGINAL page text
    end: int | None = None


def _search(quote: str, pages: list[str], loose: bool) -> VerifyResult | None:
    q, _ = normalize_with_map(quote, loose=loose)
    if len(q) < (MIN_QUOTE_CHARS if not loose else MIN_QUOTE_CHARS - 4):
        return None
    for page_no, page_text in enumerate(pages, start=1):
        norm, idx = normalize_with_map(page_text, loose=loose)
        pos = norm.find(q)
        if pos != -1:
            return VerifyResult(True, "loose" if loose else "exact", page_no, idx[pos], idx[pos + len(q) - 1] + 1)
    return None


def verify_quote(quote: str, pages: list[str], expected_page: int | None = None) -> VerifyResult:
    """Check `quote` against `pages` (list of page texts, page 1 first).

    If `expected_page` is given it is tried first, but a match on another page is still
    returned (with the real page), because LLMs often misreport page numbers.
    """
    q_exact, _ = normalize_with_map(quote)
    if len(q_exact.strip()) < MIN_QUOTE_CHARS:
        return VerifyResult(False, "too_short")
    ordered = pages
    if expected_page and 1 <= expected_page <= len(pages):
        # try the expected page first; page numbers in the result stay absolute
        for loose in (False, True):
            r = _search(quote, [pages[expected_page - 1]], loose)
            if r:
                return VerifyResult(True, r.method, expected_page, r.start, r.end)
    for loose in (False, True):
        r = _search(quote, ordered, loose)
        if r:
            return r
    return VerifyResult(False, "none")
