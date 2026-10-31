"""Bibliographic metadata from real databases (Crossref, fallback OpenAlex). Never from an LLM."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable

FetchJson = Callable[[str], dict]  # url -> parsed JSON; raises NotFound / LookupFailed

_DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")


class InvalidDOI(ValueError):
    pass


class NotFound(Exception):
    pass


class LookupFailed(Exception):
    pass


def normalize_doi(raw: str) -> str:
    doi = raw.strip()
    doi = re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
    doi = re.sub(r"^doi:\s*", "", doi, flags=re.IGNORECASE).lower()
    if not _DOI_RE.match(doi):
        raise InvalidDOI(raw)
    return doi


def http_fetch_json(url: str) -> dict:
    contact = os.environ.get("CONTACT_EMAIL", "")
    ua = f"ElOrientador/0.1 (mailto:{contact})" if contact else "ElOrientador/0.1"
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise NotFound(url) from None
        raise LookupFailed(f"HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise LookupFailed(type(exc).__name__) from None


def _crossref(doi: str, fetch: FetchJson) -> dict:
    msg = fetch(f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='/')}")["message"]
    authors = [" ".join(p for p in (a.get("given"), a.get("family")) if p) or a.get("name", "") for a in msg.get("author", [])]
    parts = (msg.get("issued") or {}).get("date-parts") or [[None]]
    updates = msg.get("updated-by") or []
    return {
        "title": (msg.get("title") or [""])[0],
        "authors": [a for a in authors if a],
        "year": parts[0][0] if parts and parts[0] else None,
        "venue": (msg.get("container-title") or [None])[0],
        "retracted": any(str(u.get("type", "")).lower() == "retraction" for u in updates),
        "metadata_source": "crossref",
    }


def _openalex(doi: str, fetch: FetchJson) -> dict:
    w = fetch(f"https://api.openalex.org/works/https://doi.org/{urllib.parse.quote(doi, safe='/')}")
    source = ((w.get("primary_location") or {}).get("source") or {}).get("display_name")
    return {
        "title": w.get("title") or w.get("display_name") or "",
        "authors": [a["author"]["display_name"] for a in w.get("authorships", []) if a.get("author", {}).get("display_name")],
        "year": w.get("publication_year"),
        "venue": source,
        "retracted": bool(w.get("is_retracted")),
        "metadata_source": "openalex",
    }


def lookup_doi(doi: str, fetch: FetchJson = http_fetch_json) -> dict:
    """Return metadata for a normalized DOI. Raises NotFound (no base knows it) or LookupFailed (bases unreachable)."""
    not_found = 0
    for source in (_crossref, _openalex):
        try:
            meta = source(doi, fetch)
        except NotFound:
            not_found += 1
            continue
        except (LookupFailed, KeyError, TypeError, IndexError):
            continue
        if meta["title"]:
            return {"doi": doi, **meta}
    if not_found == 2:
        raise NotFound(doi)
    raise LookupFailed(doi)
