"""T0.6 - Relation suggestions between verified claims of different documents.

Usage:
    python relate.py [out_dir]        (reads out/<doc>.json and out/pages/<doc>.json)

Rules (AGENTS.md / docs/03-AI-PIPELINE.md):
  - both sides need a quote verified by code (re-checked here against page text when available)
  - second pass with verify_relation.md; verdict != "implica" => low confidence, hidden by default
  - at most MAX_SUGGESTIONS new suggestions per round; all edges are born `suggested`
  - relations the user already rejected are never suggested again
"""
from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

from llm import LLMClient
from extract import load_prompt
from verify_quotes import verify_quote

MAX_SUGGESTIONS = 5
MAX_LLM_PAIRS = MAX_SUGGESTIONS * 3  # cap on classify calls per round (many pairs return "nenhuma")
MIN_CANDIDATE_SCORE = 0.05
LOW_CONFIDENCE_FACTOR = 0.5
PROMPTS = Path(__file__).parent.parent / "prompts"

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
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def candidate_score(a: dict, b: dict) -> float:
    """Lexical stand-in for embeddings: concept token overlap (co-occurrence) + statement similarity."""
    ca, cb = set(_tokens(a["concept"])), set(_tokens(b["concept"]))
    overlap = len(ca & cb) / len(ca | cb) if ca | cb else 0.0
    sim = _cosine(Counter(_tokens(a["statement"])), Counter(_tokens(b["statement"])))
    return 0.6 * overlap + 0.4 * sim


def pair_key(a: dict, b: dict) -> tuple:
    return tuple(sorted([(a["doc_id"], a["concept"].casefold()), (b["doc_id"], b["concept"].casefold())]))


def find_candidates(
    claims: list[dict], rejected: set[tuple] | None = None, limit: int = MAX_LLM_PAIRS
) -> list[tuple[float, dict, dict]]:
    """Top pairs of claims from DIFFERENT documents, best first. `claims` must carry doc_id."""
    rejected = rejected or set()
    scored = []
    for a, b in combinations(claims, 2):
        if a["doc_id"] == b["doc_id"] or pair_key(a, b) in rejected:
            continue
        s = candidate_score(a, b)
        if s >= MIN_CANDIDATE_SCORE:
            scored.append((s, a, b))
    scored.sort(key=lambda t: t[0], reverse=True)
    return scored[:limit]


def _fill(template: str, **values: str) -> str:
    for k, v in values.items():
        template = template.replace("{" + k + "}", str(v))
    return template


def _evidence_ok(claim: dict, pages_by_doc: dict[str, list[str]] | None) -> bool:
    if not claim.get("quote_verified"):
        return False
    pages = (pages_by_doc or {}).get(claim["doc_id"])
    if pages is None:
        return True  # already verified at extraction time
    return verify_quote(claim["quote"], pages, claim.get("page_verified")).found


def suggest_edges(
    claims: list[dict],
    client: LLMClient,
    pages_by_doc: dict[str, list[str]] | None = None,
    rejected: set[tuple] | None = None,
    max_suggestions: int = MAX_SUGGESTIONS,
) -> list[dict]:
    """Return up to `max_suggestions` edges with status `suggested`."""
    c_sys, c_tpl = load_prompt(PROMPTS / "classify_relation.md")
    v_sys, v_tpl = load_prompt(PROMPTS / "verify_relation.md")
    usable = [c for c in claims if _evidence_ok(c, pages_by_doc)]
    edges: list[dict] = []
    for score, a, b in find_candidates(usable, rejected):
        if len(edges) >= max_suggestions:
            break
        base = dict(
            concept_a=a["concept"], concept_b=b["concept"],
            quote_a=a["quote"], quote_b=b["quote"],
            doc_a=a["doc_id"], doc_b=b["doc_id"],
            page_a=a.get("page_verified"), page_b=b.get("page_verified"),
        )
        try:
            cls = client.complete_json(c_sys, _fill(c_tpl, **base), CLASSIFY_SCHEMA)
            if cls["relation"] == "nenhuma":
                continue
            ver = client.complete_json(v_sys, _fill(v_tpl, relation=cls["relation"], **base), VERIFY_SCHEMA)
        except RuntimeError:  # LLMError: skip this pair, keep going
            continue
        implied = ver["verdict"] == "implica"
        edges.append(
            {
                "concept_a": a["concept"], "concept_b": b["concept"],
                "doc_a": a["doc_id"], "doc_b": b["doc_id"],
                "relation": cls["relation"],
                "rationale": cls["rationale"],
                "evidence_a": {"quote": a["quote"], "page": a.get("page_verified")},
                "evidence_b": {"quote": b["quote"], "page": b.get("page_verified")},
                "confidence": cls["confidence"] if implied else round(cls["confidence"] * LOW_CONFIDENCE_FACTOR, 3),
                "second_check": {"verdict": ver["verdict"], "reason": ver["reason"]},
                "display_by_default": implied,
                "candidate_score": round(score, 3),
                "status": "suggested",
            }
        )
    return edges


def load_claims(out_dir: Path) -> list[dict]:
    claims = []
    for f in sorted(out_dir.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        for c in data.get("accepted", []):
            claims.append({**c, "doc_id": data["doc_id"]})
    return claims


def load_pages(out_dir: Path) -> dict[str, list[str]]:
    return {
        (d := json.loads(f.read_text(encoding="utf-8")))["doc_id"]: d["pages"]
        for f in sorted((out_dir / "pages").glob("*.json"))
    }


def main(argv: list[str]) -> int:
    from llm_client import GeminiClient, LLMError

    out_dir = Path(argv[1]) if len(argv) > 1 else Path(__file__).parent / "out"
    claims = load_claims(out_dir)
    if len({c["doc_id"] for c in claims}) < 2:
        print("São necessários claims aceitos de pelo menos 2 documentos. Rode extract.py primeiro.")
        return 1
    try:
        client = GeminiClient()
    except LLMError as exc:
        print(exc)
        return 1
    rej_file = out_dir / "rejected_edges.json"  # filled by the app/user later; list of [[doc, concept], [doc, concept]]
    rejected = {tuple(map(tuple, p)) for p in json.loads(rej_file.read_text(encoding="utf-8"))} if rej_file.exists() else set()
    edges = suggest_edges(claims, client, load_pages(out_dir), rejected)
    (out_dir / "edges.json").write_text(json.dumps(edges, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(edges)} sugestões gravadas em {out_dir / 'edges.json'} "
          f"({sum(e['display_by_default'] for e in edges)} exibidas por padrão).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
