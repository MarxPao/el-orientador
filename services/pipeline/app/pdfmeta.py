"""Title, authors and year read from the PDF itself (embedded metadata first, then the look of the first page).

Used only when the student gave no title: a library full of "ref1", "scan_0042" is useless in citations. The result
is a best effort and is always editable; anything doubtful is left empty rather than guessed.
"""
from __future__ import annotations

import re
from pathlib import Path

_JUNK_TITLE = re.compile(
    r"^(untitled|sem t[ií]tulo|microsoft word|document\d*|scan\w*|img[_\d]*|page\s*\d+|new document|ficha catalogr[áa]fica)",
    re.I,
)
_YEAR = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")
_NOT_A_NAME = re.compile(r"\b(universidade|faculdade|instituto|departamento|revista|journal|programa|curso|resumo|abstract|"
                         r"sum[áa]rio|isbn|issn|doi|www|http|editora|vol\.|n\.|p[áa]g)\b", re.I)


def _clean(s: str) -> str:
    return " ".join((s or "").replace("\x00", " ").split())


def _plausible_title(t: str) -> bool:
    t = _clean(t)
    return 6 <= len(t) <= 300 and not _JUNK_TITLE.match(t) and not re.fullmatch(r"[\d\W_]+", t) and not t.lower().endswith(".pdf")


def _authors_from(s: str) -> list[str]:
    parts = re.split(r"\s*(?:;|,\s(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ])|\s+e\s+|\s+and\s+|&)\s*", _clean(s))
    return [p for p in parts if 3 <= len(p) <= 80 and " " in p and not _NOT_A_NAME.search(p)][:8]


def _looks_like_name(line: str) -> bool:
    line = _clean(line)
    words = line.split()
    if not (2 <= len(words) <= 5) or _NOT_A_NAME.search(line) or any(ch.isdigit() for ch in line):
        return False
    return all(w[0].isupper() or w.lower() in {"de", "da", "do", "dos", "das", "e", "van", "von", "di"} for w in words)


def extract_metadata(path: Path) -> dict:
    """{title?, authors?, year?}: only the keys that were found with reasonable confidence."""
    import pymupdf

    out: dict = {}
    try:
        with pymupdf.open(path) as doc:
            md = doc.metadata or {}
            if _plausible_title(md.get("title") or ""):
                out["title"] = _clean(md["title"])
            if md.get("author"):
                names = _authors_from(md["author"])
                if names:
                    out["authors"] = names
            m = re.search(r"(19|20)\d\d", md.get("creationDate") or "")
            if len(doc) == 0:
                return out
            first = doc[0]
            lines: list[tuple[float, str]] = []  # (font size, text) per line, top to bottom
            for block in first.get_text("dict").get("blocks", []):
                for ln in block.get("lines", []):
                    spans = [s for s in ln.get("spans", []) if s.get("text", "").strip()]
                    if spans:
                        lines.append((max(s["size"] for s in spans), _clean(" ".join(s["text"] for s in spans))))
            if "title" not in out and lines:
                top = max(sz for sz, _ in lines)
                body = sorted(sz for sz, _ in lines)[len(lines) // 2]
                if top - body < 1.0:  # no line stands out: a plain page is not a title page
                    top = None
                # the title is the run of consecutive lines in the largest font
                run: list[str] = []
                for sz, text in lines if top is not None else []:
                    if abs(sz - top) < 0.6:
                        run.append(text)
                    elif run:
                        break
                cand = _clean(" ".join(run))
                if _plausible_title(cand) and len(run) <= 4:
                    out["title"] = cand
                    if "authors" not in out:  # the lines right below the title that look like personal names
                        after = lines[[t for _, t in lines].index(run[-1]) + 1:][:4]
                        names = [t for _, t in after if _looks_like_name(t)]
                        if names:
                            out["authors"] = names[:6]
            head = " ".join(t for _, t in lines)[:1500]
            if len(doc) > 1:
                head += " " + _clean(doc[1].get_text("text"))[:600]
            years = _YEAR.findall(head)
            if years:
                out["year"] = int(max(set(years), key=years.count)) if len(set(years)) == 1 else int(years[0])
            elif m and 1950 <= int(m.group(0)) <= 2049:
                pass  # file creation date says nothing reliable about the publication year
    except Exception:  # a metadata read must never fail the pipeline
        return {}
    return out
