"""Citation consistency: every in-text citation has a reference, every reference is cited, no duplicate DOIs.

Deterministic, no LLM. In-text citations are recognised in the two usual shapes:
  parenthetical  (Moran, 2015)  (MORAN; SILVA, 2015, p. 12)  (Moran, 2015; Silva, 2020)
  narrative      Moran (2015)   Moran e Silva (2015)   Moran et al. (2015)
A citation matches a reference when one of the reference's author surnames appears in the citation
and the years agree (a reference without a year matches on surname alone). Lenient on purpose: it
flags what is clearly missing, not stylistic variants.
"""
from __future__ import annotations

import re
from typing import Any

from .bibliography import ascii_fold, family_name
from .coherence import extract_plain_text
from .repo import Repo

_YEAR = r"(?:19|20)\d{2}"
_PAREN_GROUP = re.compile(r"\(([^()]{3,300})\)")
_PAREN_CITE = re.compile(rf"(?P<who>[A-ZÀ-Ý][^;()]*?),\s*(?P<year>{_YEAR})[a-z]?\b")
_NARRATIVE = re.compile(
    rf"(?P<who>[A-ZÀ-Ý][\w'\-À-ÿ]+(?:\s+(?:e|and|&)\s+[A-ZÀ-Ý][\w'\-À-ÿ]+|\s+et al\.?)?)\s*\((?P<year>{_YEAR})[a-z]?[^)]*\)"
)
_STOP = {"cf", "ver", "veja", "apud", "segundo", "conforme", "por", "exemplo", "e", "and", "et", "al", "in", "de", "da", "do"}


def _tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z]+", ascii_fold(s).lower()) if t not in _STOP and len(t) > 1}


def _surnames(doc: dict[str, Any]) -> set[str]:
    authors = [a for a in (doc.get("authors") or []) if isinstance(a, str) and a.strip()]
    if authors:
        return {t for a in authors for t in _tokens(family_name(a))}
    return _tokens((doc.get("title") or "").split(" ")[0])  # same fallback the draft generator cites by


def find_citations(text: str) -> list[tuple[str, int]]:
    """(who, year) for each in-text citation, in order, without duplicates."""
    found: list[tuple[str, int]] = []
    for g in _PAREN_GROUP.finditer(text):
        for m in _PAREN_CITE.finditer(g.group(1)):
            found.append((m.group("who").strip(), int(m.group("year"))))
    for m in _NARRATIVE.finditer(text):
        found.append((m.group("who").strip(), int(m.group("year"))))
    seen: set[tuple[str, int]] = set()
    out = []
    for who, year in found:
        k = (" ".join(sorted(_tokens(who))), year)
        if k not in seen and k[0]:
            seen.add(k)
            out.append((who, year))
    return out


def _match(who: str, year: int, docs: list[dict[str, Any]], names: dict[str, set[str]]) -> dict[str, Any] | None:
    toks = _tokens(who)
    for d in docs:
        if names[d["id"]] & toks and (d.get("year") is None or d["year"] == year):
            return d
    return None


def _norm_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    return re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", doi.strip().lower()) or None


def check_consistency(repo: Repo, project_id: str) -> dict[str, Any]:
    docs = repo.list_documents(project_id)
    sections = repo.list_sections(project_id)
    names = {d["id"]: _surnames(d) for d in docs}
    issues: list[dict[str, Any]] = []
    cited: set[str] = set()

    for sec in sections:
        title_l = sec["title"].lower()
        if "referência" in title_l or "referencia" in title_l or "bibliograf" in title_l:
            continue  # the list itself is not an in-text citation
        for who, year in find_citations(extract_plain_text(sec.get("content"))):
            doc = _match(who, year, docs, names)
            if doc:
                cited.add(doc["id"])
            else:
                issues.append({
                    "type": "citacao_sem_referencia",
                    "severity": "error",
                    "message": f"A citação \"{who}, {year}\" na seção \"{sec['title']}\" não corresponde a nenhuma referência da biblioteca.",
                    "section_id": sec["id"],
                    "section_title": sec["title"],
                })

    for d in docs:
        if d["id"] not in cited:
            issues.append({
                "type": "referencia_nao_citada",
                "severity": "warning",
                "message": f"A referência \"{d.get('title')}\" está na biblioteca, mas não é citada em nenhuma seção.",
                "document_id": d["id"],
                "document_title": d.get("title"),
            })

    by_doi: dict[str, list[dict[str, Any]]] = {}
    for d in docs:
        key = _norm_doi(d.get("doi"))
        if key:
            by_doi.setdefault(key, []).append(d)
    for key, group in by_doi.items():
        for d in group[1:]:
            issues.append({
                "type": "doi_duplicado",
                "severity": "warning",
                "message": f"O DOI {key} aparece mais de uma vez na biblioteca (\"{d.get('title')}\").",
                "document_id": d["id"],
                "document_title": d.get("title"),
            })

    return {
        "issues": issues,
        "total_documents": len(docs),
        "total_sections": len(sections),
        "cited_document_ids": [d["id"] for d in docs if d["id"] in cited],
        "uncited_document_ids": [d["id"] for d in docs if d["id"] not in cited],
        "ok": not issues,
    }
