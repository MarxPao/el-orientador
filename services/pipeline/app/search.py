"""Passage search over the whole library: chunking, keyword scoring, rank fusion, snippets.

Pure functions, no I/O. The index is made of *chunks*: pieces of one page (so every hit has an exact page
number to cite). Search is hybrid:
  keyword   always available (no LLM needed); accent-insensitive, prefix-matching terms
  semantic  when an embedding model is configured and the chunks have been embedded
The two ranked lists are fused with Reciprocal Rank Fusion, which needs no score calibration.
"""
from __future__ import annotations

import math
import os
import re
import unicodedata
from typing import Any, Sequence

def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name) or default)
    except ValueError:
        return default


# The default embedding model reads about 128 tokens (~500 characters of Portuguese) per passage; a longer chunk
# would be silently truncated and its tail never searched by meaning. Raise these when you switch to a long-context
# model (e.g. CHUNK_TARGET_CHARS=1000 CHUNK_MAX_CHARS=1400 CHUNK_OVERLAP_CHARS=150 with e5-large).
CHUNK_TARGET_CHARS = _env_int("CHUNK_TARGET_CHARS", 450)
CHUNK_MAX_CHARS = _env_int("CHUNK_MAX_CHARS", 600)
CHUNK_OVERLAP_CHARS = _env_int("CHUNK_OVERLAP_CHARS", 80)
MIN_CHUNK_CHARS = 40
RRF_K = 60

_STOPWORDS = set(
    "a o as os um uma uns umas de da do das dos em na no nas nos por para com sem sob sobre entre ate ao aos "
    "e ou mas que se como mais menos muito muita ja nao sim foi sao ser ter tem sua seu suas seus este esta "
    "estes estas esse essa isso isto aquele aquela the of and or to in on for with is are was be by an at as it".split()
)


def fold(s: str) -> str:
    """Lowercase, accent-free text: the form stored in `search_text` and used to match queries."""
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").lower()


def tokens(s: str) -> list[str]:
    """Search terms of a text: folded, alphanumeric, no stopwords, at least 2 characters."""
    return [t for t in re.findall(r"[a-z0-9]+", fold(s)) if len(t) >= 2 and t not in _STOPWORDS]


# ----------------------------------------------------------------------------- chunking
def _split_long(text: str) -> list[str]:
    """Split a long page into pieces near CHUNK_TARGET_CHARS, on paragraph then sentence boundaries."""
    pieces: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        para = re.sub(r"\s+", " ", para).strip()
        if not para:
            continue
        if len(para) <= CHUNK_MAX_CHARS:
            pieces.append(para)
            continue
        pieces.extend(s for s in re.split(r"(?<=[.!?;:])\s+", para) if s.strip())
    out: list[str] = []
    cur = ""
    for p in pieces:
        while len(p) > CHUNK_MAX_CHARS:  # a "sentence" without punctuation: cut hard on a space
            cut = p.rfind(" ", 0, CHUNK_TARGET_CHARS)
            cut = cut if cut > 200 else CHUNK_TARGET_CHARS
            if cur:
                out.append(cur)
                cur = ""
            out.append(p[:cut].strip())
            p = p[cut:].strip()
        if cur and len(cur) + 1 + len(p) > CHUNK_TARGET_CHARS:
            out.append(cur)
            tail = cur[-CHUNK_OVERLAP_CHARS:]
            cur = (tail[tail.find(" ") + 1:] + " " + p).strip() if " " in tail else p
        else:
            cur = f"{cur} {p}".strip()
    if cur:
        out.append(cur)
    return out


BOILERPLATE_MIN_PAGES = 5      # a line must repeat on at least this many pages...
BOILERPLATE_MIN_SHARE = 0.10   # ...and on this share of the document to count as a running header/footer
_EDGE_LINES = 2


def _line_key(line: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\d+", "#", line)).strip().lower()


def clean_pages(pages: Sequence[str]) -> list[str]:
    """Text as it should be searched, not as the PDF encodes it:
      - soft hyphens (and the line break after them) are removed, so "des-\\nsa" is read as "dessa";
      - a lowercase word broken by "-" at the end of a line is joined;
      - running headers/footers (the first/last lines that repeat across the document, page numbers aside) are dropped.
    The stored pages stay untouched: quote verification still sees the PDF's own text."""
    lines_per_page = [[ln for ln in (text or "").split("\n")] for text in pages]
    counts: dict[str, int] = {}
    for lines in lines_per_page:
        nonempty = [ln for ln in lines if ln.strip()]
        edge = nonempty[:_EDGE_LINES] + nonempty[-_EDGE_LINES:]
        for key in {_line_key(ln) for ln in edge if _line_key(ln)}:
            counts[key] = counts.get(key, 0) + 1
    need = max(BOILERPLATE_MIN_PAGES, math.ceil(BOILERPLATE_MIN_SHARE * len(pages)))
    boiler = {k for k, n in counts.items() if n >= need}
    out = []
    for lines in lines_per_page:
        nonempty_idx = [i for i, ln in enumerate(lines) if ln.strip()]
        edge_idx = set(nonempty_idx[:_EDGE_LINES] + nonempty_idx[-_EDGE_LINES:])
        kept = [ln for i, ln in enumerate(lines) if not (i in edge_idx and _line_key(ln) in boiler)]
        text = "\n".join(kept)
        text = re.sub("\u00ad[ \t]*\n?[ \t]*", "", text)
        text = re.sub(r"(?<=[a-zà-ÿ])-[ \t]*\n[ \t]*(?=[a-zà-ÿ])", "", text)
        out.append(text)
    return out


def chunk_pages(pages: Sequence[str]) -> list[dict[str, Any]]:
    """[{chunk_no, page_no (1-based), text, search_text}] for a document's pages. A chunk never crosses a page."""
    chunks: list[dict[str, Any]] = []
    for page_no, text in enumerate(clean_pages(pages), start=1):
        for piece in _split_long(text or ""):
            if len(piece) < MIN_CHUNK_CHARS:
                continue
            chunks.append({"chunk_no": len(chunks), "page_no": page_no, "text": piece, "search_text": fold(piece)})
    return chunks


# ----------------------------------------------------------------------------- keyword
def tsquery(query: str) -> str | None:
    """A Postgres `to_tsquery('simple', ...)` string: terms OR-ed, longer ones as prefixes. Only [a-z0-9] reaches
    it, so a query can never inject tsquery syntax. None when the query has no usable term."""
    terms = list(dict.fromkeys(tokens(query)))[:12]
    if not terms:
        return None
    return " | ".join(f"{t}:*" if len(t) >= 4 else t for t in terms)


def bm25_rank(query: str, chunks: Sequence[dict[str, Any]], k1: float = 1.4, b: float = 0.75) -> list[tuple[dict, float]]:
    """In-memory keyword ranking (BM25 with prefix matching), the reference behaviour for InMemoryRepo."""
    terms = list(dict.fromkeys(tokens(query)))[:12]
    if not terms or not chunks:
        return []
    docs = [re.findall(r"[a-z0-9]+", c["search_text"]) for c in chunks]
    avg = sum(len(d) for d in docs) / len(docs) or 1.0
    n = len(docs)

    def matches(term: str, word: str) -> bool:
        return word.startswith(term) if len(term) >= 4 else word == term

    df = {t: sum(1 for d in docs if any(matches(t, w) for w in d)) for t in terms}
    scored = []
    for c, d in zip(chunks, docs):
        s = 0.0
        for t in terms:
            if not df[t]:
                continue
            tf = sum(1 for w in d if matches(t, w))
            if not tf:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            s += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * len(d) / avg))
        if s > 0:
            scored.append((c, s))
    scored.sort(key=lambda x: -x[1])
    return scored


# ----------------------------------------------------------------------------- vectors / fusion
def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def rrf(lists: dict[str, Sequence[str]], k: int = RRF_K) -> list[tuple[str, float, list[str]]]:
    """Fuse ranked id lists. Returns [(id, score, [list names that contained it])], best first."""
    score: dict[str, float] = {}
    seen: dict[str, list[str]] = {}
    for name, ids in lists.items():
        for rank, cid in enumerate(ids, start=1):
            score[cid] = score.get(cid, 0.0) + 1.0 / (k + rank)
            seen.setdefault(cid, []).append(name)
    return [(cid, s, seen[cid]) for cid, s in sorted(score.items(), key=lambda x: -x[1])]


def snippet(text: str, query: str, width: int = 320) -> str:
    """A window of the chunk around the first query term, trimmed to word boundaries."""
    if len(text) <= width:
        return text
    folded = fold(text)  # fold() keeps lengths for Latin text, so offsets line up
    pos = -1
    if len(folded) == len(text):
        for t in tokens(query):
            pos = folded.find(t)
            if pos >= 0:
                break
    start = max(0, (pos if pos >= 0 else 0) - width // 4)
    end = min(len(text), start + width)
    start = text.rfind(" ", 0, start) + 1 if start > 0 else 0
    if end < len(text):
        end = text.rfind(" ", start, end) if text.rfind(" ", start, end) > start else end
    return ("… " if start > 0 else "") + text[start:end].strip() + (" …" if end < len(text) else "")
