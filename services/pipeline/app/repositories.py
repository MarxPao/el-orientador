"""Federated search across open academic repositories (T7.1):
OpenAlex (global), SciELO (Latin America), and CAPES/BDTD (Brazilian theses & dissertations).

Pure code, no LLM (AGENTS.md rule 3).
"""
from __future__ import annotations

import io
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable

from .metadata import FetchJson, LookupFailed, NotFound, http_fetch_json

MAX_SEARCH_LIMIT = 25
DEFAULT_SEARCH_LIMIT = 10
MAX_PDF_BYTES = 50 * 1024 * 1024  # 50 MB safety ceiling


def _reconstruct_abstract(inverted_index: dict | None, max_chars: int = 400) -> str | None:
    """Reconstruct plain abstract text from OpenAlex abstract_inverted_index."""
    if not inverted_index or not isinstance(inverted_index, dict):
        return None
    try:
        word_positions: list[tuple[int, str]] = []
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        word_positions.sort(key=lambda x: x[0])
        full = " ".join(w for _, w in word_positions)
        if len(full) > max_chars:
            return full[:max_chars].rstrip() + "..."
        return full
    except Exception:
        return None


def _format_authors(authorships: list[dict] | None) -> list[str]:
    if not authorships:
        return []
    names = []
    for a in authorships:
        author = a.get("author") or {}
        name = author.get("display_name")
        if name:
            names.append(name)
    return names


def search_openalex(
    query: str,
    limit: int = DEFAULT_SEARCH_LIMIT,
    oa_only: bool = False,
    extra_filter: str | None = None,
    source_label: str = "openalex",
    fetch: FetchJson = http_fetch_json,
) -> dict:
    """Query OpenAlex works API with optional filters."""
    limit = min(max(1, limit), MAX_SEARCH_LIMIT)
    q = urllib.parse.quote(query.strip())

    filters = []
    if oa_only:
        filters.append("is_oa:true")
    if extra_filter:
        filters.append(extra_filter)

    filter_param = f"&filter={','.join(filters)}" if filters else ""
    url = (
        f"https://api.openalex.org/works?search={q}{filter_param}&per-page={limit}"
        "&select=id,doi,title,display_name,publication_year,authorships,primary_location,open_access,cited_by_count,abstract_inverted_index"
    )

    try:
        data = fetch(url)
    except Exception as exc:
        return {
            "source": source_label,
            "query": query,
            "total": 0,
            "results": [],
            "status": "failed",
            "error": str(exc),
        }

    meta = data.get("meta") or {}
    total = int(meta.get("count", 0))
    raw_results = data.get("results") or []

    formatted = []
    for w in raw_results:
        prim_loc = w.get("primary_location") or {}
        src = prim_loc.get("source") or {}
        venue = src.get("display_name")
        oa = w.get("open_access") or {}
        is_oa = bool(oa.get("is_oa") or prim_loc.get("is_oa"))
        pdf_url = oa.get("oa_url") or prim_loc.get("pdf_url")
        doi_raw = w.get("doi")
        doi = None
        if doi_raw:
            doi = re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", str(doi_raw), flags=re.IGNORECASE).strip().lower()

        formatted.append({
            "id": w.get("id") or f"openalex-{doi or len(formatted)}",
            "source": source_label,
            "title": w.get("title") or w.get("display_name") or "Sem título",
            "authors": _format_authors(w.get("authorships")),
            "year": w.get("publication_year"),
            "venue": venue,
            "doi": doi,
            "abstract": _reconstruct_abstract(w.get("abstract_inverted_index")),
            "citation_count": int(w.get("cited_by_count") or 0),
            "is_open_access": is_oa,
            "pdf_url": pdf_url if (pdf_url and pdf_url.startswith("http")) else None,
            "landing_page_url": prim_loc.get("landing_page_url") or (f"https://doi.org/{doi}" if doi else None),
        })

    return {
        "source": source_label,
        "query": query,
        "total": total,
        "results": formatted,
        "status": "ok",
    }


def search_scielo(
    query: str,
    limit: int = DEFAULT_SEARCH_LIMIT,
    fetch: FetchJson = http_fetch_json,
) -> dict:
    """Search SciELO articles via CrossRef with prefix 10.1590 (SciELO exclusive DOI prefix)."""
    limit = min(max(1, limit), MAX_SEARCH_LIMIT)
    q = urllib.parse.quote(query.strip())
    url = f"https://api.crossref.org/works?query={q}&filter=prefix:10.1590&rows={limit}"

    try:
        data = fetch(url)
    except Exception:
        # Fallback to OpenAlex scielo search
        return search_openalex(
            query,
            limit=limit,
            extra_filter="primary_location.source.display_name.search:scielo",
            source_label="scielo",
            fetch=fetch,
        )

    msg = data.get("message") or {}
    total = int(msg.get("total-results", 0))
    items = msg.get("items") or []

    results = []
    for item in items:
        doi = (item.get("DOI") or "").lower().strip()
        authors = []
        for a in item.get("author", []):
            name = " ".join(p for p in (a.get("given"), a.get("family")) if p) or a.get("name")
            if name:
                authors.append(name)
        parts = (item.get("issued") or {}).get("date-parts") or [[None]]
        year = parts[0][0] if parts and parts[0] else None
        venue = (item.get("container-title") or [None])[0]

        link_list = item.get("link") or []
        pdf_url = None
        for l in link_list:
            if "pdf" in (l.get("content-type") or "").lower():
                pdf_url = l.get("URL")
                break
        if not pdf_url and doi:
            pdf_url = f"https://doi.org/{doi}"

        abstract = item.get("abstract") or None
        if abstract:
            abstract = re.sub(r"<[^>]+>", "", str(abstract)).strip()

        results.append({
            "id": f"scielo-{doi or len(results)}",
            "source": "scielo",
            "title": (item.get("title") or ["Sem título"])[0],
            "authors": authors,
            "year": year,
            "venue": venue or "SciELO",
            "doi": doi,
            "abstract": abstract,
            "citation_count": int(item.get("is-referenced-by-count") or 0),
            "is_open_access": True,
            "pdf_url": pdf_url,
            "landing_page_url": f"https://doi.org/{doi}" if doi else None,
        })

    return {
        "source": "scielo",
        "query": query,
        "total": total,
        "results": results,
        "status": "ok",
    }


def search_bdtd(
    query: str,
    limit: int = DEFAULT_SEARCH_LIMIT,
    fetch: FetchJson = http_fetch_json,
) -> dict:
    """Search Brazilian Dissertations and Theses (CAPES/BDTD)."""
    return search_openalex(
        query=query,
        limit=limit,
        extra_filter="type:dissertation,institutions.country_code:BR",
        source_label="bdtd",
        fetch=fetch,
    )


def federated_search(
    query: str,
    source: str = "all",
    oa_only: bool = False,
    limit: int = DEFAULT_SEARCH_LIMIT,
    fetch: FetchJson = http_fetch_json,
) -> dict:
    """Federated search across configured open repositories."""
    source = (source or "all").lower().strip()
    if source == "scielo":
        return search_scielo(query, limit=limit, fetch=fetch)
    if source == "bdtd":
        return search_bdtd(query, limit=limit, fetch=fetch)
    if source == "openalex":
        return search_openalex(query, limit=limit, oa_only=oa_only, source_label="openalex", fetch=fetch)

    scielo_res = search_scielo(query, limit=min(limit, 5), fetch=fetch)
    openalex_res = search_openalex(query, limit=min(limit, 8), oa_only=oa_only, source_label="openalex", fetch=fetch)
    bdtd_res = search_bdtd(query, limit=min(limit, 5), fetch=fetch)

    seen_dois: set[str] = set()
    combined: list[dict] = []

    for r in scielo_res.get("results", []) + bdtd_res.get("results", []) + openalex_res.get("results", []):
        d = r.get("doi")
        if d and d in seen_dois:
            continue
        if d:
            seen_dois.add(d)
        combined.append(r)
        if len(combined) >= limit:
            break

    total = (scielo_res.get("total") or 0) + (openalex_res.get("total") or 0) + (bdtd_res.get("total") or 0)
    return {
        "source": "all",
        "query": query,
        "total": total,
        "results": combined,
        "status": "ok",
        "sources_searched": ["scielo", "bdtd", "openalex"],
    }


def download_open_pdf(url: str, max_bytes: int = MAX_PDF_BYTES, timeout: int = 25) -> bytes:
    """Download an open-access PDF directly from its public repository URL with security checks."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ElOrientador/0.1 (Academic Open Access Client)",
            "Accept": "application/pdf,application/octet-stream,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError("Arquivo excede o tamanho máximo permitido de 50 MB.")

        if not data.startswith(b"%PDF-"):
            if b"<html" in data[:500].lower() or b"<!doctype html" in data[:500].lower():
                raise ValueError("O repositório retornou página HTML ao invés do PDF direto.")
            raise ValueError("O arquivo baixado não é um documento PDF válido.")

        return data
