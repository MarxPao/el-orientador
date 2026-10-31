"""Relation suggestions between verified claims of different concepts (ported from prototype/relate.py).

Rules (AGENTS.md / docs/03-AI-PIPELINE.md): evidence verified on BOTH sides, second check with verify_relation.md
(verdict != "implica" => low confidence and hidden by default), at most MAX_SUGGESTIONS per round, edges are born
`suggested`, and a concept pair that already has an edge (any status, so rejections too) is never suggested again.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from itertools import combinations

from .extract import load_prompt
from .llm import LLMClient
from .verify_quotes import verify_quote

MAX_SUGGESTIONS = 5
MAX_LLM_PAIRS = MAX_SUGGESTIONS * 3
MIN_CANDIDATE_SCORE = 0.05
LOW_CONFIDENCE_FACTOR = 0.5

RELATIONS = ["apoia", "contrasta", "estende", "aplica", "critica", "nenhuma"]
CLASSIFY_SCHEMA = {
    "type": "object",
    "required": ["relation", "rationale", "confidence"],
    "properties": {
        "relation": {"enum": RELATIONS},
        "rationale": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}
VERIFY_SCHEMA = {
    "type": "object",
    "required": ["verdict", "reason"],
    "properties": {
        "verdict": {"enum": ["implica", "implica_parcialmente", "nao_implica"]},
        "reason": {"type": "string"},
    },
}
_TOKEN = re.compile(r"\w+", re.UNICODE)


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.casefold()) if len(t) > 3]


def _cosine(a: Counter, b: Counter) -> float:
    dot = sum(a[t] * b[t] for t in a.keys() & b.keys())
    na, nb = math.sqrt(sum(v * v for v in a.values())), math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def candidate_score(a: dict, b: dict) -> float:
    ca, cb = set(_tokens(a["concept"])), set(_tokens(b["concept"]))
    overlap = len(ca & cb) / len(ca | cb) if ca | cb else 0.0
    return 0.6 * overlap + 0.4 * _cosine(Counter(_tokens(a["statement"])), Counter(_tokens(b["statement"])))


def find_candidates(claims: list[dict], existing_pairs: set[frozenset], limit: int = MAX_LLM_PAIRS):
    """Top pairs of claims from DIFFERENT concepts with no edge yet, best first."""
    scored = []
    for a, b in combinations(claims, 2):
        if a["concept_id"] == b["concept_id"] or frozenset((a["concept_id"], b["concept_id"])) in existing_pairs:
            continue
        s = candidate_score(a, b)
        if s >= MIN_CANDIDATE_SCORE:
            scored.append((s, a, b))
    scored.sort(key=lambda t: t[0], reverse=True)
    return scored[:limit]


def _fill(template: str, **values) -> str:
    for k, v in values.items():
        template = template.replace("{" + k + "}", str(v))
    return template


def _evidence_ok(claim: dict, pages_by_doc: dict[str, list[str]] | None) -> bool:
    if not claim.get("quote_verified"):
        return False
    pages = (pages_by_doc or {}).get(claim["document_id"])
    return True if pages is None else verify_quote(claim["quote"], pages, claim.get("page_no")).found


def suggest_edges(
    claims: list[dict],
    client: LLMClient,
    existing_pairs: set[frozenset] | None = None,
    pages_by_doc: dict[str, list[str]] | None = None,
    max_suggestions: int = MAX_SUGGESTIONS,
) -> list[dict]:
    """Return up to `max_suggestions` edges (status `suggested`). Claims need id, document_id, concept_id, concept, ..."""
    _, c_sys, c_tpl = load_prompt("classify_relation.md")
    _, v_sys, v_tpl = load_prompt("verify_relation.md")
    usable = [c for c in claims if _evidence_ok(c, pages_by_doc)]
    edges: list[dict] = []
    used_pairs = set(existing_pairs or ())
    for score, a, b in find_candidates(usable, used_pairs):
        if len(edges) >= max_suggestions:
            break
        pair = frozenset((a["concept_id"], b["concept_id"]))
        if pair in used_pairs:
            continue
        base = dict(concept_a=a["concept"], concept_b=b["concept"], quote_a=a["quote"], quote_b=b["quote"],
                    doc_a=a["document_id"], doc_b=b["document_id"], page_a=a.get("page_no"), page_b=b.get("page_no"))
        try:
            cls = client.complete_json(c_sys, _fill(c_tpl, **base), CLASSIFY_SCHEMA)
            if cls["relation"] == "nenhuma":
                continue
            ver = client.complete_json(v_sys, _fill(v_tpl, relation=cls["relation"], **base), VERIFY_SCHEMA)
        except RuntimeError:  # LLMError: skip this pair
            continue
        implied = ver["verdict"] == "implica"
        used_pairs.add(pair)
        edges.append({
            "source_concept": a["concept_id"], "target_concept": b["concept_id"],
            "relation": cls["relation"], "rationale": cls["rationale"],
            "confidence": cls["confidence"] if implied else round(cls["confidence"] * LOW_CONFIDENCE_FACTOR, 3),
            "display_by_default": implied, "status": "suggested",
            "evidence": [{"claim_id": a["id"], "side": "source"}, {"claim_id": b["id"], "side": "target"}],
            "candidate_score": round(score, 3),
        })
    return edges
