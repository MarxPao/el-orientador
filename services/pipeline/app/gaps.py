"""Research gaps: concept pairs with no link, checked against external bibliographic searches (T2.4).

Pure code, no LLM. A gap is NOT a claim that nothing exists: the note always says what was searched
("não encontrei estudos nas buscas feitas"), never "não existem estudos" (AGENTS.md rule 4).
"""
from __future__ import annotations

import urllib.parse
from collections import Counter
from itertools import combinations

from .metadata import FetchJson, LookupFailed, NotFound
from .pipeline.relate import _cosine, _tokens

MAX_GAPS_PER_ROUND = 5
MAX_RESULTS_KEPT = 5


def concept_text(concept_id: str, claims: list[dict]) -> Counter:
    return Counter(t for c in claims if c["concept_id"] == concept_id for t in _tokens(c["statement"]))


def find_gap_pairs(
    concepts: list[dict], claims: list[dict], linked: set[frozenset], known_gaps: set[frozenset],
    limit: int = MAX_GAPS_PER_ROUND,
) -> list[tuple[dict, dict]]:
    """Concept pairs with no edge (any status) and no gap yet, most related first (a related-but-unlinked pair)."""
    texts = {c["id"]: concept_text(c["id"], claims) for c in concepts}
    scored = []
    for a, b in combinations(concepts, 2):
        pair = frozenset((a["id"], b["id"]))
        if pair in linked or pair in known_gaps:
            continue
        scored.append((-_cosine(texts[a["id"]], texts[b["id"]]), a["label"].casefold(), b["label"].casefold(), a, b))
    scored.sort(key=lambda t: t[:3])
    return [(a, b) for *_, a, b in scored[:limit]]


def _search_openalex(a: str, b: str, fetch: FetchJson) -> dict:
    query = f'"{a}" AND "{b}"'
    url = ("https://api.openalex.org/works?search=" + urllib.parse.quote(query) +
           "&per-page=5&select=title,publication_year,doi")
    data = fetch(url)
    results = [{"title": w.get("title"), "year": w.get("publication_year"), "doi": w.get("doi")}
               for w in data.get("results", [])[:MAX_RESULTS_KEPT]]
    return {"source": "openalex", "query": query, "total": int((data.get("meta") or {}).get("count", len(results))),
            "results": results, "status": "ok"}


def _search_semantic_scholar(a: str, b: str, fetch: FetchJson) -> dict:
    query = f"{a} {b}"
    url = ("https://api.semanticscholar.org/graph/v1/paper/search?query=" + urllib.parse.quote(query) +
           "&limit=5&fields=title,year,externalIds")
    data = fetch(url)
    results = [{"title": p.get("title"), "year": p.get("year"), "doi": (p.get("externalIds") or {}).get("DOI")}
               for p in data.get("data", [])[:MAX_RESULTS_KEPT]]
    return {"source": "semantic_scholar", "query": query, "total": int(data.get("total", len(results))),
            "results": results, "status": "ok"}


def run_searches(label_a: str, label_b: str, fetch: FetchJson) -> list[dict]:
    """Search each source; a source that fails is recorded as failed (it never counts as 'found nothing')."""
    searches = []
    for fn, name, query in ((_search_openalex, "openalex", f'"{label_a}" AND "{label_b}"'),
                            (_search_semantic_scholar, "semantic_scholar", f"{label_a} {label_b}")):
        try:
            searches.append(fn(label_a, label_b, fetch))
        except (LookupFailed, NotFound, KeyError, TypeError, ValueError):
            searches.append({"source": name, "query": query, "total": None, "results": [], "status": "failed"})
    return searches


def build_note(searches: list[dict]) -> str:
    """Careful wording: report what was searched, never claim that studies do not exist."""
    ok = [s for s in searches if s["status"] == "ok"]
    names = ", ".join(f"{s['source']} ({s['query']})" for s in searches)
    if len(ok) < len(searches):
        return f"Busca incompleta: pelo menos uma base não respondeu. Buscas tentadas: {names}. Nada pode ser concluído ainda."
    found = sum(s["total"] or 0 for s in ok)
    if found == 0:
        return f"Não encontrei estudos nas buscas feitas: {names}."
    return (f"Encontrei {found} resultado(s) nas buscas feitas: {names}. Podem tratar da relação; "
            "revise antes de adotar como lacuna.")


def detect_gaps(concepts, claims, linked, known_gaps, fetch: FetchJson, limit: int = MAX_GAPS_PER_ROUND) -> list[dict]:
    out = []
    for a, b in find_gap_pairs(concepts, claims, linked, known_gaps, limit):
        searches = run_searches(a["label"], b["label"], fetch)
        found = [r for s in searches for r in s["results"]]
        out.append({"concept_a": a["id"], "concept_b": b["id"], "searches": searches, "found_links": found,
                    "note": build_note(searches), "status": "open"})
    return out
