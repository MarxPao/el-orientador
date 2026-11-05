"""Provenance ledger: who wrote which words, from what was RECORDED, never from how the text sounds.

Why not a style detector: burstiness, vocabulary variety and "AI clichés" cannot tell a student from a model.
They flag formal, non-native and careful writers, they miss a lightly paraphrased draft, and a verdict
"X% AI" built on them is a guess presented as a measurement. This module only states what the system saw:

  ai_draft / ai_coauthor / ai_polish   the server inserted text produced by the assistant (it keeps the text)
  ai_paraphrase                        the author confirmed a paragraph is a rewrite of an AI draft
  paste                                the editor reported a paste from outside the document
  legacy_counters                      word counts kept before the ledger existed (no text)

Attribution matches the CURRENT section text against the recorded texts with word 5-grams, so:
  - text the student rewrote leaves the ledger (it is the student's words now);
  - a paragraph clearly derived from an AI draft but edited is reported separately as `ai_revised`;
  - nothing is inferred about text that was never recorded. `LIMITS` says so in the output.

Pure functions, no I/O.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Sequence

from .search import fold

K = 5  # word n-gram length for exact coverage
DERIVED_K = 3  # n-gram length for "this paragraph descends from that draft"
DERIVED_MIN_SHARE = 0.25  # share of a paragraph's 3-grams found in a draft for it to count as derived
MIN_EVENT_WORDS = 4
MIN_PASTE_WORDS = 15  # the editor ignores (and the server refuses) smaller pastes: they are not authorship events

AI_DRAFT_KINDS = {"ai_draft", "ai_coauthor"}
AI_POLISH_KINDS = {"ai_polish"}
# the author confirmed that a paragraph is a rewrite of an AI draft (suggested by app/paraphrase.py, never automatic)
REVISED_KINDS = {"ai_paraphrase"}
# the author said "this paragraph is not a rewrite": recorded, but never part of the Prism (not in EVENT_KINDS)
DISMISSED_KIND = "paraphrase_dismissed"
EVENT_KINDS = AI_DRAFT_KINDS | AI_POLISH_KINDS | REVISED_KINDS | {"paste", "legacy_counters"}

LIMITS = [
    "O registro mostra o que o editor viu: texto gerado pela IA dentro do El Orientador e colagens que o editor "
    "informou. Texto escrito fora e digitado à mão aqui não deixa rastro.",
    "Não há análise de estilo: nenhuma nota de “probabilidade de IA” é calculada, porque estilo não prova autoria.",
]


def _norm(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", fold(word))


def section_blocks(content: Any) -> list[str]:
    """Text of each top-level block (paragraph, heading, list...) of a TipTap document, without `_authorship`."""

    def text_of(node: Any) -> str:
        if isinstance(node, dict):
            if node.get("type") == "text":
                return str(node.get("text", ""))
            return "".join(text_of(c) for c in node.get("content") or [])
        return ""

    if isinstance(content, str):
        return [content] if content.strip() else []
    if not isinstance(content, dict):
        return []
    blocks = [text_of(b) for b in content.get("content") or []]
    return [b for b in blocks if b.strip()]


def _words(text: str) -> tuple[list[str], list[str]]:
    words = re.findall(r"\S+", text)
    return words, [_norm(w) for w in words]


def _grams(norms: Sequence[str], k: int) -> list[tuple[int, tuple[str, ...]]]:
    """(index into the word list of the first word, n-gram) over the words that have letters or digits."""
    seq = [(i, n) for i, n in enumerate(norms) if n]
    return [(seq[j][0], tuple(n for _, n in seq[j : j + k])) for j in range(len(seq) - k + 1)] if len(seq) >= k else []


def _gram_set(norms: Sequence[str], k: int) -> set[tuple[str, ...]]:
    return {g for _, g in _grams(norms, k)}


def _covered(norms: Sequence[str], grams: set[tuple[str, ...]], k: int) -> set[int]:
    """Indexes of the words of a block that sit inside some n-gram of `grams`."""
    seq = [i for i, n in enumerate(norms) if n]
    out: set[int] = set()
    for j in range(len(seq) - k + 1):
        if tuple(norms[i] for i in seq[j : j + k]) in grams:
            out.update(seq[j : j + k])
    return out


class _Event:
    def __init__(self, ev: dict[str, Any]) -> None:
        self.ev = ev
        self.kind = ev["kind"]
        self.declared = (ev.get("declared") or None) if self.kind == "paste" else None
        text = ev.get("text") or ""
        _, norms = _words(text)
        self.k = min(K, max(3, sum(1 for n in norms if n)))
        self.grams = _gram_set(norms, self.k) if sum(1 for n in norms if n) >= MIN_EVENT_WORDS else set()
        self.derived = _gram_set(norms, DERIVED_K) if self.kind in AI_DRAFT_KINDS else set()
        meta = ev.get("meta") or {}
        self.ai_words = int(meta.get("ai_words", 0) or 0)
        self.student_words = int(meta.get("student_words", 0) or 0)


def attribute(
    content: Any,
    events: Iterable[dict[str, Any]],
    verified_quotes: Sequence[str] = (),
) -> dict[str, Any]:
    """Word counts per origin for the current content of one section."""
    evs = [_Event(e) for e in events if e.get("kind") in EVENT_KINDS]
    textual = [e for e in evs if e.grams]
    legacy_ai = sum(int((e.ev.get("meta") or {}).get("ai_words", 0) or 0) for e in evs if e.kind == "legacy_counters")
    legacy_polish = sum(int((e.ev.get("meta") or {}).get("polished_words", 0) or 0) for e in evs if e.kind == "legacy_counters")

    quote_sets = []
    for q in verified_quotes:
        _, qn = _words(q or "")
        if sum(1 for n in qn if n) >= 4:
            k = min(K, sum(1 for n in qn if n))
            quote_sets.append((_gram_set(qn, k), k))

    counts = {"human": 0, "polished": 0, "ai_drafted": 0, "ai_revised": 0, "pasted": 0, "quoted": 0, "declared_own": 0}
    # coauthor events mix the student's premise with the model's expansion; split their covered words by the
    # recorded proportion, in document order (the premise comes first)
    split_budget: dict[int, list[int]] = {}
    labels_per_block: list[list[str]] = []

    for block in section_blocks(content):
        words, norms = _words(block)
        labels = ["human"] * len(words)
        cover = {id(e): _covered(norms, e.grams, e.k) for e in textual}
        quoted: set[int] = set()
        for gs, k in quote_sets:
            quoted |= _covered(norms, gs, k)
        block3 = _gram_set(norms, DERIVED_K)
        derived_from_ai = any(
            e.derived and block3 and len(block3 & e.derived) / len(block3) >= DERIVED_MIN_SHARE for e in textual
        )
        for i in range(len(words)):
            drafted = [e for e in textual if e.kind in AI_DRAFT_KINDS and i in cover[id(e)]]
            polished = [e for e in textual if e.kind in AI_POLISH_KINDS and i in cover[id(e)]]
            revised = [e for e in textual if e.kind in REVISED_KINDS and i in cover[id(e)]]
            pasted = [e for e in textual if e.kind == "paste" and i in cover[id(e)]]
            if drafted:
                e = drafted[0]
                labels[i] = "ai_drafted"
                if e.kind == "ai_coauthor" and e.student_words and e.ai_words:
                    split_budget.setdefault(id(e), []).append((len(labels_per_block), i))  # type: ignore[arg-type]
            elif polished:
                labels[i] = "polished"
            elif revised:
                labels[i] = "ai_revised"
            elif pasted and i not in quoted:
                if pasted[0].declared == "own_text":
                    labels[i] = "declared_own"
                else:
                    labels[i] = "pasted"
            elif i in quoted:
                labels[i] = "quoted"
            elif derived_from_ai:
                labels[i] = "ai_revised"
        labels_per_block.append(labels)

    # coauthor split: the first share of the covered words is the student's premise (light polish)
    by_id = {id(e): e for e in textual}
    for eid, positions in split_budget.items():
        e = by_id[eid]
        n_student = round(len(positions) * e.student_words / (e.ai_words + e.student_words))
        for b, i in positions[:n_student]:
            labels_per_block[b][i] = "polished"

    for labels in labels_per_block:
        for lab in labels:
            counts[lab] += 1

    # words counted before the ledger existed (no text to match): taken out of the human words, never invented
    take = min(legacy_ai, counts["human"])
    counts["ai_drafted"] += take
    counts["human"] -= take
    take = min(legacy_polish, counts["human"])
    counts["polished"] += take
    counts["human"] -= take

    total = sum(counts.values())
    return {"total_words": total, **{f"{k}_words": v for k, v in counts.items()}}


def percentages(words: dict[str, int], total: int) -> dict[str, int]:
    """Whole-number percentages that always add up to 100 (largest remainder), 100% human when empty."""
    keys = ["ai_drafted", "ai_revised", "pasted", "polished", "quoted", "declared_own", "human"]
    if total <= 0:
        return {f"{k}_pct": (100 if k == "human" else 0) for k in keys}
    raw = {k: words.get(f"{k}_words", 0) * 100 / total for k in keys}
    floor = {k: int(v) for k, v in raw.items()}
    left = 100 - sum(floor.values())
    for k in sorted(keys, key=lambda k: raw[k] - floor[k], reverse=True)[:left]:
        floor[k] += 1
    return {f"{k}_pct": v for k, v in floor.items()}
