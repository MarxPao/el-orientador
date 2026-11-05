"""Measures how well passage search finds the right page in YOUR books. Everything runs locally.

    python -m app.eval_search --pdfs ./livros --questions perguntas.json [--k 1 5 10] [--out relatorio.json]

perguntas.json:
    [{"pdf": "livro1.pdf", "question": "Como o autor define evasão?", "pages": [34, 35]}, ...]
`pages` lists every page that answers the question (1-based, as printed by a PDF viewer, not the book's own
numbering). A hit is any result chunk on one of those pages. The same index the app builds (chunks of one page,
BM25 keyword, embeddings with the active EMBED_PROVIDER, RRF fusion) is searched over ALL the PDFs together, so a
question also has to beat the other books, as it will in a real project.

Reported per method (keyword / semantic / hybrid): recall@k = share of questions with a right page in the top k,
and MRR = mean of 1/rank of the first right page. Questions that no method finds are listed, to read and fix.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Sequence

from .search import bm25_rank, chunk_pages, cosine, rrf

Embed = Callable[[list[str], str], list[list[float]]]
METHODS = ("keyword", "semantic", "hybrid")


def build_index(pages_by_pdf: dict[str, list[str]]) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for pdf, pages in pages_by_pdf.items():
        for c in chunk_pages(pages):
            chunks.append({**c, "id": f"{pdf}#{c['chunk_no']}", "pdf": pdf})
    return chunks


def rank(question: str, chunks: Sequence[dict], vectors: Sequence[Sequence[float]] | None,
         qvec: Sequence[float] | None, limit: int = 50) -> dict[str, list[dict]]:
    """Ranked chunks for each method."""
    keyword = [c for c, _ in bm25_rank(question, chunks)][:limit]
    out = {"keyword": keyword, "semantic": [], "hybrid": keyword}
    if vectors is not None and qvec is not None:
        scored = sorted(range(len(chunks)), key=lambda i: -cosine(qvec, vectors[i]))[:limit]
        semantic = [chunks[i] for i in scored]
        by_id = {c["id"]: c for c in (*keyword, *semantic)}
        out["semantic"] = semantic
        out["hybrid"] = [by_id[cid] for cid, _, _ in
                         rrf({"keyword": [c["id"] for c in keyword], "semantic": [c["id"] for c in semantic]})][:limit]
    return out


def first_hit(results: Sequence[dict], pdf: str, pages: Sequence[int]) -> int | None:
    """1-based rank of the first chunk that sits on a right page of the right PDF."""
    for i, c in enumerate(results, start=1):
        if c["pdf"] == pdf and c["page_no"] in pages:
            return i
    return None


def evaluate(pages_by_pdf: dict[str, list[str]], questions: Sequence[dict], embed: Embed | None,
             ks: Sequence[int] = (1, 5, 10)) -> dict[str, Any]:
    chunks = build_index(pages_by_pdf)
    vectors = None
    if embed is not None and chunks:
        vectors = []
        for i in range(0, len(chunks), 32):
            vectors.extend(embed([c["text"] for c in chunks[i:i + 32]], "document"))
    ranks: dict[str, list[int | None]] = {m: [] for m in METHODS}
    misses = []
    for q in questions:
        qvec = embed([q["question"]], "query")[0] if embed is not None else None
        per = rank(q["question"], chunks, vectors, qvec)
        got = {m: first_hit(per[m], q["pdf"], q["pages"]) for m in METHODS}
        for m in METHODS:
            ranks[m].append(got[m])
        if all(r is None or r > max(ks) for r in got.values()):
            misses.append(q)
    n = len(questions)
    report: dict[str, Any] = {"questions": n, "chunks": len(chunks), "semantic_available": embed is not None, "methods": {}}
    for m in METHODS:
        if m == "semantic" and embed is None:
            continue
        rs = ranks[m]
        report["methods"][m] = {
            **{f"recall@{k}": round(sum(1 for r in rs if r is not None and r <= k) / n, 3) if n else 0.0 for k in ks},
            "mrr": round(sum(1 / r for r in rs if r) / n, 3) if n else 0.0,
        }
    report["not_found_by_any_method"] = misses
    return report


def load_questions(path: Path, pdfs: set[str]) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    out = []
    for i, q in enumerate(data, start=1):
        if not isinstance(q, dict) or not all(k in q for k in ("pdf", "question", "pages")):
            raise SystemExit(f"pergunta {i}: faltam campos (pdf, question, pages)")
        if q["pdf"] not in pdfs:
            raise SystemExit(f"pergunta {i}: o PDF '{q['pdf']}' não está na pasta")
        pages = q["pages"] if isinstance(q["pages"], list) else [q["pages"]]
        if not pages or not all(isinstance(p, int) and p >= 1 for p in pages):
            raise SystemExit(f"pergunta {i}: 'pages' deve ser uma lista de números de página (1, 2, ...)")
        out.append({"pdf": q["pdf"], "question": str(q["question"]), "pages": pages})
    return out


def format_report(r: dict[str, Any]) -> str:
    cols = [c for c in next(iter(r["methods"].values())).keys()]
    lines = [f"{r['questions']} perguntas, {r['chunks']} trechos indexados", "",
             f"{'método':<10}" + "".join(f"{c:>11}" for c in cols)]
    for m, vals in r["methods"].items():
        lines.append(f"{m:<10}" + "".join(f"{vals[c]:>11.3f}" for c in cols))
    if not r["semantic_available"]:
        lines += ["", "Busca semântica não avaliada: nenhum modelo de embeddings ativo (EMBED_PROVIDER)."]
    if r["not_found_by_any_method"]:
        lines += ["", f"{len(r['not_found_by_any_method'])} pergunta(s) que nenhum método achou no top 10:"]
        lines += [f"  - [{q['pdf']} p.{q['pages']}] {q['question']}" for q in r["not_found_by_any_method"]]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdfs", type=Path, required=True, help="pasta com os PDFs")
    ap.add_argument("--questions", type=Path, required=True, help="JSON de perguntas")
    ap.add_argument("--k", type=int, nargs="+", default=[1, 5, 10])
    ap.add_argument("--out", type=Path, help="grava o relatório completo em JSON")
    args = ap.parse_args(argv)

    from . import embeddings
    from .jobs import parse_pdf

    files = sorted(args.pdfs.glob("*.pdf"))
    if not files:
        raise SystemExit(f"nenhum PDF em {args.pdfs}")
    questions = load_questions(args.questions, {f.name for f in files})
    used = {q["pdf"] for q in questions}
    pages_by_pdf = {}
    for f in files:
        if f.name in used:
            print(f"lendo {f.name} ...", file=sys.stderr)
            pages_by_pdf[f.name] = parse_pdf(f)
    # distractors: PDFs without questions still compete in the index, as other references would in a project
    for f in files:
        pages_by_pdf.setdefault(f.name, parse_pdf(f))
    emb = embeddings.resolve(None)
    embed = (lambda texts, task: emb.embed(texts, task=task, operation="eval")) if emb is not None else None
    report = evaluate(pages_by_pdf, questions, embed, args.k)
    print(format_report(report))
    if args.out:
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
