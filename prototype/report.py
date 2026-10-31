"""T0.7 - Metrics and human-review spreadsheets for the prototype evaluation.

Usage:
    python report.py [out_dir] [pdf_dir]

Reads  out/<doc>.json (extract.py), out/edges.json (relate.py), out/pages/*.json (ingest.py).
Writes out/metrics.json, out/claims_review.csv, out/edges_review.csv.
The CSVs are UTF-8 with BOM so Excel opens accents correctly.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from ingest import MIN_TEXT_CHARS

REVIEW_COL = "correto? (s/n)"


def _load(out_dir: Path) -> list[dict]:
    return [json.loads(f.read_text(encoding="utf-8")) for f in sorted(out_dir.glob("*.json"))
            if f.name not in ("metrics.json", "edges.json", "rejected_edges.json")]


def _pct(n: int, d: int) -> float | None:
    return round(n / d, 4) if d else None


def compute_metrics(docs: list[dict], edges: list[dict], pdf_names: list[str], page_docs: list[dict]) -> dict:
    accepted = [c for d in docs for c in d["accepted"]]
    rejected = [c for d in docs for c in d["rejected"]]
    generated = len(accepted) + len(rejected)
    exact = sum(c["verify_method"] == "exact" for c in accepted)
    loose = sum(c["verify_method"] == "loose" for c in accepted)

    ingested = {p["doc_id"] for p in page_docs}
    no_text = sorted(p["doc_id"] for p in page_docs if sum(map(len, p["pages"])) < MIN_TEXT_CHARS)
    not_ingested = sorted(n for n in (Path(x).stem for x in pdf_names) if n not in ingested)
    parsing_failures = sorted(set(no_text) | set(not_ingested))
    total_pdfs = len(pdf_names) or len(ingested)

    return {
        "n_documents": len(docs),
        "claims_generated": generated,
        "claims_accepted": len(accepted),
        "approval_rate": _pct(len(accepted), generated),
        "accepted_exact_pct": _pct(exact, len(accepted)),
        "accepted_loose_pct": _pct(loose, len(accepted)),
        "parsing_failures": parsing_failures,
        "parsing_failure_rate": _pct(len(parsing_failures), total_pdfs),
        "per_document": [
            {
                "doc_id": d["doc_id"],
                "accepted": len(d["accepted"]),
                "rejected": len(d["rejected"]),
                "approval_rate": d.get("approval_rate"),
                "chunk_errors": len(d.get("errors", [])),
            }
            for d in docs
        ],
        "edges_suggested": len(edges),
        "edges_displayed_by_default": sum(e.get("display_by_default", False) for e in edges),
    }


def write_claims_csv(docs: list[dict], path: Path) -> int:
    rows = 0
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["doc_id", "concept", "claim", "quote", "page", "verify_method", "certainty", REVIEW_COL])
        for d in docs:
            for c in d["accepted"]:
                w.writerow([d["doc_id"], c["concept"], c["statement"], c["quote"],
                            c.get("page_verified"), c["verify_method"], c.get("certainty"), ""])
                rows += 1
    return rows


def write_edges_csv(edges: list[dict], path: Path) -> int:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["doc_a", "concept_a", "relation", "doc_b", "concept_b", "quote_a", "page_a",
                    "quote_b", "page_b", "confidence", "second_check", REVIEW_COL])
        for e in edges:
            w.writerow([e["doc_a"], e["concept_a"], e["relation"], e["doc_b"], e["concept_b"],
                        e["evidence_a"]["quote"], e["evidence_a"]["page"],
                        e["evidence_b"]["quote"], e["evidence_b"]["page"],
                        e["confidence"], e["second_check"]["verdict"], ""])
    return len(edges)


def build_report(out_dir: Path, pdf_dir: Path | None = None) -> dict:
    docs = _load(out_dir)
    edges_file = out_dir / "edges.json"
    edges = json.loads(edges_file.read_text(encoding="utf-8")) if edges_file.exists() else []
    page_docs = [json.loads(f.read_text(encoding="utf-8")) for f in sorted((out_dir / "pages").glob("*.json"))]
    pdf_names = [p.name for p in sorted(pdf_dir.glob("*.pdf"))] if pdf_dir and pdf_dir.exists() else []
    metrics = compute_metrics(docs, edges, pdf_names, page_docs)
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    metrics["claims_csv_rows"] = write_claims_csv(docs, out_dir / "claims_review.csv")
    metrics["edges_csv_rows"] = write_edges_csv(edges, out_dir / "edges_review.csv")
    return metrics


def _fmt(x: float | None) -> str:
    return "n/d" if x is None else f"{x:.0%}"


def main(argv: list[str]) -> int:
    base = Path(__file__).parent
    out_dir = Path(argv[1]) if len(argv) > 1 else base / "out"
    pdf_dir = Path(argv[2]) if len(argv) > 2 else base / "data" / "pdfs"
    if not out_dir.exists():
        print(f"{out_dir} não existe. Rode ingest.py e extract.py primeiro.")
        return 1
    m = build_report(out_dir, pdf_dir)
    print(f"Documentos: {m['n_documents']} | claims gerados: {m['claims_generated']} | aceitos: {m['claims_accepted']}")
    print(f"Taxa de verificação literal: {_fmt(m['approval_rate'])} (meta >= 85%)")
    print(f"Aceitos exact: {_fmt(m['accepted_exact_pct'])} | loose: {_fmt(m['accepted_loose_pct'])}")
    print(f"Falhas de parsing: {_fmt(m['parsing_failure_rate'])} (meta <= 10%) {m['parsing_failures']}")
    print(f"Ligações sugeridas: {m['edges_suggested']} ({m['edges_displayed_by_default']} exibidas por padrão)")
    print(f"Planilhas: claims_review.csv ({m['claims_csv_rows']} linhas), edges_review.csv ({m['edges_csv_rows']} linhas)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
