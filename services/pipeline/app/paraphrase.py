"""Suggest paragraphs that look like a rewrite of an AI draft the system itself produced.

This is NOT a style detector and it never decides anything alone. It compares the author's current paragraphs
only with AI text that is in the ledger, by meaning (embeddings) plus a small lexical anchor, and returns
*suggestions*. A suggestion counts in the Prism only after the author confirms it (recorded as `ai_paraphrase`).

Why a suggestion and not a verdict: two texts about the same topic are close in meaning even when one was written
without the other. The similarity thresholds are therefore conservative, configurable and uncalibrated for any
particular model until you measure them on your own texts (see tests/test_local_embeddings.py real-model test).
"""
from __future__ import annotations

import math
import os
import re
from typing import Callable, Sequence

from .provenance import AI_DRAFT_KINDS, attribute, section_blocks
from .search import tokens

MIN_BLOCK_WORDS = 25        # shorter paragraphs say too little to compare by meaning
MIN_HUMAN_SHARE = 0.8       # only paragraphs the ledger still reads as the author's are candidates
CHUNK_WORDS = 70            # AI drafts are compared sentence-window by sentence-window
LEXICAL_MIN = 0.10          # shared content words (Jaccard) that must back up the semantic match
MAX_SUGGESTIONS = 8


def min_similarity() -> float:
    try:
        return float(os.environ.get("PARAPHRASE_MIN_SIMILARITY", "0.88"))
    except ValueError:
        return 0.88


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb) if na and nb else 0.0


def ai_chunks(events: Sequence[dict]) -> list[tuple[str, str]]:
    """[(event id, text window)] from the AI drafts in the ledger: paragraphs, long ones cut at sentence ends."""
    out: list[tuple[str, str]] = []
    for e in events:
        if e.get("kind") not in AI_DRAFT_KINDS or not e.get("text"):
            continue
        for para in re.split(r"\n\s*\n|\n", e["text"]):
            sentences = re.split(r"(?<=[.!?])\s+", para.strip())
            cur: list[str] = []
            for s in sentences:
                cur.append(s)
                if sum(len(x.split()) for x in cur) >= CHUNK_WORDS:
                    out.append((e["id"], " ".join(cur)))
                    cur = []
            if cur and sum(len(x.split()) for x in cur) >= 12:
                out.append((e["id"], " ".join(cur)))
    return out


def _jaccard(a: str, b: str) -> float:
    sa, sb = set(tokens(a)), set(tokens(b))
    return len(sa & sb) / len(sa | sb) if sa and sb else 0.0


def candidate_blocks(content, events, verified_quotes: Sequence[str] = ()) -> list[str]:
    """Paragraphs long enough to compare that the ledger still reads (almost entirely) as the author's own."""
    out = []
    dismissed = {" ".join((e.get("text") or "").split()) for e in events if e.get("kind") == "paraphrase_dismissed"}
    for block in section_blocks(content):
        if len(block.split()) < MIN_BLOCK_WORDS or " ".join(block.split()) in dismissed:
            continue
        single = {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": block}]}]}
        w = attribute(single, events, verified_quotes)
        if w["total_words"] and w["human_words"] / w["total_words"] >= MIN_HUMAN_SHARE:
            out.append(block)
    return out


def find(
    content,
    events: Sequence[dict],
    embed: Callable[[list[str], str], list[list[float]]],
    verified_quotes: Sequence[str] = (),
) -> list[dict]:
    """Suggestions [{text, similarity, event_id, ai_excerpt}], most similar first. `embed(texts, task)` is the
    active embedder; the same call embeds both sides so they share one vector space."""
    chunks = ai_chunks(events)
    blocks = candidate_blocks(content, events, verified_quotes)
    if not chunks or not blocks:
        return []
    vecs = embed([c[1] for c in chunks] + blocks, "document")
    cv, bv = vecs[: len(chunks)], vecs[len(chunks):]
    threshold = min_similarity()
    found = []
    for block, v in zip(blocks, bv):
        best_i = max(range(len(chunks)), key=lambda i: _cosine(v, cv[i]))
        sim = _cosine(v, cv[best_i])
        if sim >= threshold and _jaccard(block, chunks[best_i][1]) >= LEXICAL_MIN:
            found.append({"text": block, "similarity": round(sim, 3), "event_id": chunks[best_i][0],
                          "ai_excerpt": chunks[best_i][1][:240]})
    found.sort(key=lambda x: -x["similarity"])
    return found[:MAX_SUGGESTIONS]
