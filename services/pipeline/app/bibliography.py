"""Bibliography: formatting (ABNT, APA, Vancouver, Chicago, MLA, BibTeX) and parsing of a pasted reference.

Deterministic, no LLM. Metadata that came from a database (Crossref/OpenAlex) is formatted as stored;
a pasted free-text reference is parsed with simple rules and stored as `metadata_source = "manual"`.
Authors are stored as "Given Family" (the form Crossref returns); formatters derive the rest.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

STYLES = ("abnt", "apa", "vancouver", "chicago", "mla", "bibtex")

_DOI_IN_TEXT = re.compile(r"10\.\d{4,9}/[^\s\"<>]+", re.IGNORECASE)
_PARTICLES = {"da", "de", "do", "das", "dos", "e", "van", "von", "der", "den", "di", "del", "la", "le"}


def ascii_fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")


# ----------------------------------------------------------------------------- names
def split_name(full: str) -> tuple[str, str]:
    """"Maria da Silva" -> ("Maria", "da Silva"); "Moran" -> ("", "Moran"). Particles stay with the family name."""
    parts = full.split()
    if len(parts) <= 1:
        return "", full.strip()
    i = len(parts) - 1
    while i > 1 and parts[i - 1].lower() in _PARTICLES:
        i -= 1
    return " ".join(parts[:i]), " ".join(parts[i:])


def family_name(full: str) -> str:
    return split_name(full)[1]


def _initials(given: str, dots: bool = True, spaced: bool = True) -> str:
    out = []
    for tok in re.split(r"[\s]+", given.strip()):
        if not tok or tok.lower() in _PARTICLES:
            continue
        for piece in tok.split("-"):
            if piece:
                out.append(piece[0].upper() + ("." if dots else ""))
    return (" " if spaced else "").join(out)


# ----------------------------------------------------------------------------- formatting
def _authors(doc: dict[str, Any]) -> list[str]:
    return [a for a in (doc.get("authors") or []) if isinstance(a, str) and a.strip()]


def _join_and(items: list[str], conj: str) -> str:
    if len(items) <= 1:
        return "".join(items)
    if len(items) == 2:
        return f"{items[0]} {conj} {items[1]}"
    return ", ".join(items[:-1]) + f", {conj} {items[-1]}"


def _end(s: str) -> str:
    s = s.strip()
    return s if s.endswith((".", "?", "!")) else s + "."


def _doi_url(doc: dict[str, Any]) -> str | None:
    return f"https://doi.org/{doc['doi']}" if doc.get("doi") else None


def format_abnt(doc: dict[str, Any]) -> str:
    names = _authors(doc)
    if not names:
        head = ""
    else:
        fmt = []
        for n in names[:3]:
            given, fam = split_name(n)
            lead = []  # Portuguese particles follow the given name in ABNT: "SILVA, Bruno da"
            words = fam.split()
            while len(words) > 1 and words[0].lower() in {"da", "de", "do", "das", "dos", "e"}:
                lead.append(words.pop(0))
            fam, given = " ".join(words), " ".join(filter(None, [given, *lead]))
            fmt.append(f"{fam.upper()}, {given}" if given else fam.upper())
        head = "; ".join(fmt) + ("; et al." if len(names) > 3 else "")
        head = _end(head) + " "
    title = _end(doc.get("title") or "Sem título")
    tail = ", ".join(x for x in (doc.get("venue"), str(doc["year"]) if doc.get("year") else "[s.d.]") if x)
    url = _doi_url(doc)
    out = f"{head}{title} {tail}."
    if url:
        out += f" Disponível em: {url}."
    return out


def format_apa(doc: dict[str, Any]) -> str:
    names = _authors(doc)
    fmt = []
    for n in names:
        given, fam = split_name(n)
        ini = _initials(given)
        fmt.append(f"{fam}, {ini}" if ini else fam)
    if len(fmt) > 20:
        fmt = fmt[:19] + ["..."] + [fmt[-1]]
    if len(fmt) > 1 and fmt[-2] != "...":
        head = ", ".join(fmt[:-1]) + f", & {fmt[-1]}"
    else:
        head = ", ".join(fmt)
    year = f"({doc['year']})" if doc.get("year") else "(s.d.)"
    parts = [f"{_end(head)} {year}." if head else f"{year}.", _end(doc.get("title") or "Sem título")]
    if doc.get("venue"):
        parts.append(_end(doc["venue"]))
    url = _doi_url(doc)
    if url:
        parts.append(url)
    return " ".join(parts)


def format_vancouver(doc: dict[str, Any]) -> str:
    names = _authors(doc)
    fmt = []
    for n in names[:6]:
        given, fam = split_name(n)
        ini = _initials(given, dots=False, spaced=False)
        fmt.append(f"{fam} {ini}".strip())
    head = ", ".join(fmt) + (", et al" if len(names) > 6 else "")
    parts = []
    if head:
        parts.append(_end(head))
    parts.append(_end(doc.get("title") or "Sem título"))
    tail = ". ".join(x for x in (doc.get("venue"), str(doc["year"]) if doc.get("year") else None) if x)
    if tail:
        parts.append(_end(tail))
    if doc.get("doi"):
        parts.append(f"doi:{doc['doi']}")
    return " ".join(parts)


def _first_last(names: list[str], conj: str) -> str:
    """Chicago/MLA: first author inverted ("Family, Given"), the rest in natural order."""
    if not names:
        return ""
    g0, f0 = split_name(names[0])
    first = f"{f0}, {g0}" if g0 else f0
    if len(names) == 1:
        return first
    if len(names) > 3:
        return f"{first}, et al"
    return _join_and([first] + names[1:], conj)


def format_chicago(doc: dict[str, Any]) -> str:
    head = _first_last(_authors(doc), "and")
    parts = []
    if head:
        parts.append(_end(head))
    parts.append(_end(str(doc["year"])) if doc.get("year") else "n.d.")
    parts.append(f"“{_end(doc.get('title') or 'Sem título')}”")
    if doc.get("venue"):
        parts.append(_end(doc["venue"]))
    url = _doi_url(doc)
    if url:
        parts.append(url + ".")
    return " ".join(parts)


def format_mla(doc: dict[str, Any]) -> str:
    head = _first_last(_authors(doc), "and")
    parts = []
    if head:
        parts.append(_end(head))
    parts.append(f"“{_end(doc.get('title') or 'Sem título')}”")
    tail = ", ".join(x for x in (doc.get("venue"), str(doc["year"]) if doc.get("year") else None, _doi_url(doc)) if x)
    if tail:
        parts.append(_end(tail))
    return " ".join(parts)


def _bib_escape(s: str) -> str:
    return s.replace("\\", " ").replace("{", "(").replace("}", ")").replace("\n", " ").strip()


def format_bibtex(doc: dict[str, Any], key: str) -> str:
    names = _authors(doc)
    fields = []
    if names:
        fam_given = []
        for n in names:
            given, fam = split_name(n)
            fam_given.append(f"{fam}, {given}" if given else fam)
        fields.append(("author", " and ".join(fam_given)))
    fields.append(("title", doc.get("title") or "Sem título"))
    if doc.get("venue"):
        fields.append(("journal", doc["venue"]))
    if doc.get("year"):
        fields.append(("year", str(doc["year"])))
    if doc.get("doi"):
        fields.append(("doi", doc["doi"]))
    kind = "article" if doc.get("venue") else "misc"
    body = ",\n".join(f"  {k} = {{{_bib_escape(v)}}}" for k, v in fields)
    return f"@{kind}{{{key},\n{body}\n}}"


def _bibtex_keys(docs: list[dict[str, Any]]) -> list[str]:
    seen: dict[str, int] = {}
    keys = []
    for d in docs:
        names = _authors(d)
        base = re.sub(r"[^a-z0-9]", "", ascii_fold(family_name(names[0]) if names else (d.get("title") or "ref").split()[0]).lower()) or "ref"
        base += str(d.get("year") or "nd")
        n = seen.get(base, 0)
        seen[base] = n + 1
        keys.append(base if n == 0 else base + chr(ord("a") + n - 1))
    return keys


def _sort_key(doc: dict[str, Any]) -> tuple:
    names = _authors(doc)
    lead = family_name(names[0]) if names else (doc.get("title") or "")
    return (ascii_fold(lead).lower(), doc.get("year") or 0, ascii_fold(doc.get("title") or "").lower())


def export_bibliography(docs: list[dict[str, Any]], style: str) -> tuple[str, str, str]:
    """Return (text, file_extension, media_type). Raises ValueError for an unknown style."""
    style = style.lower()
    if style not in STYLES:
        raise ValueError(style)
    if style == "bibtex":
        keys = _bibtex_keys(docs)
        return "\n\n".join(format_bibtex(d, k) for d, k in zip(docs, keys)) + "\n", "bib", "application/x-bibtex; charset=utf-8"
    if style == "vancouver":  # numbered in citation order, which for us is the order of the library
        lines = [f"{i}. {format_vancouver(d)}" for i, d in enumerate(docs, start=1)]
    else:
        fn = {"abnt": format_abnt, "apa": format_apa, "chicago": format_chicago, "mla": format_mla}[style]
        lines = [fn(d) for d in sorted(docs, key=_sort_key)]
    return "\n\n".join(lines) + "\n", "txt", "text/plain; charset=utf-8"


# ----------------------------------------------------------------------------- parsing
_SURNAME_COMMA = re.compile(r"^[A-ZÀ-Ý][A-ZÀ-Ý'\- ]+,\s*\S")  # ABNT: "SILVA, Maria"


def _title_case_surname(s: str) -> str:
    return " ".join(w.lower() if w.lower() in _PARTICLES else w.capitalize() for w in s.split())


def _natural(name: str) -> str:
    """"SILVA, Maria J." -> "Maria J. Silva"; "Maria Silva" stays."""
    name = name.strip()
    if name.endswith(".") and len(name.rstrip(".").split()[-1]) > 1:  # keep the dot of an initial ("Maria J.")
        name = name.rstrip(".")
    if "," in name:
        fam, _, given = name.partition(",")
        fam = _title_case_surname(fam.strip()) if fam.strip().isupper() else fam.strip()
        return f"{given.strip()} {fam}".strip()
    return name


def _split_authors(block: str) -> list[str]:
    block = re.sub(r"\bet al\.?", "", block, flags=re.IGNORECASE).strip(" ;,.")
    if ";" in block:
        raw = block.split(";")
    elif re.search(r"\s(?:&|and|e)\s", block):
        raw = re.split(r"\s*(?:&|\band\b|\be\b)\s*|,\s*(?=[A-ZÀ-Ý][^,]*\s[A-ZÀ-Ý])", block)
    else:
        raw = [block]
    return [n for n in (_natural(r) for r in raw if r and r.strip()) if n]


def parse_citation(raw: str) -> dict[str, Any]:
    """Best-effort parse of a pasted reference (ABNT or APA shaped). Raises ValueError if no title is found.

    The result never contains a DOI that is not literally in the text.
    """
    text = re.sub(r"\s+", " ", raw).strip()
    if len(text) < 8:
        raise ValueError("referência curta demais")
    doi = None
    m = _DOI_IN_TEXT.search(text)
    if m:
        doi = m.group(0).rstrip(".,;)")
        text = (text[: m.start()] + text[m.end():]).strip()
    text = re.sub(r"(?:Dispon[ií]vel em|Available at|DOI|doi)\s*:?\s*(?:https?://(?:dx\.)?doi\.org/?)?\s*$", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"https?://\S+", "", text).strip()
    text = re.sub(r"(?:Dispon[ií]vel em|Acesso em)\s*:?[^.]*\.?", "", text, flags=re.IGNORECASE).strip()

    year = None
    paren = re.search(r"\(((?:19|20)\d{2})[a-z]?\)", text)
    if paren:
        year = int(paren.group(1))
    else:
        years = re.findall(r"\b((?:19|20)\d{2})\b", text)
        if years:
            year = int(years[-1])

    authors: list[str] = []
    rest = text
    if paren and paren.start() > 0 and not re.match(r"^[\"“]", text):  # APA: "Authors (2020). Title. Venue."
        head = text[: paren.start()].strip(" .,;")
        if head:
            authors = _split_authors(head)
        rest = text[paren.end():].lstrip(" .,")
    else:  # ABNT: leading "SURNAME, Given; SURNAME, Given. Title."
        sentences = re.split(r"(?<=[a-zà-ÿ\.])\.\s+(?=[A-ZÀ-Ý\"“])", text)
        if sentences and _SURNAME_COMMA.match(sentences[0]):
            authors = _split_authors(sentences[0])
            rest = ". ".join(sentences[1:])
    segs = [s.strip(" .") for s in re.split(r"(?<!\bv)(?<!\bn)(?<!\bp)(?<!\bpp)(?<!\bvol)(?<!\bed)\.\s+", rest) if s.strip(" .")]
    segs = [s for s in segs if not re.fullmatch(r"(?:(?:19|20)\d{2}|v\. ?\d+|n\. ?\d+|p\. ?[\d\-–]+)", s)]
    if not segs or not re.search(r"[A-Za-zÀ-ÿ]{3}", segs[0]):
        raise ValueError("título não identificado")
    title = segs[0].strip("\"“”")
    venue = None
    if len(segs) > 1:
        venue = re.split(r",\s*(?:v\.|n\.|p\.|(?:19|20)\d{2}|\[s\.d\.\])", segs[1])[0].strip(" ,") or None
    return {
        "doi": re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi).lower() if doi else None,
        "title": title[:300],
        "authors": authors,
        "year": year,
        "venue": venue[:300] if venue else None,
        "retracted": False,
        "metadata_source": "manual",
    }
