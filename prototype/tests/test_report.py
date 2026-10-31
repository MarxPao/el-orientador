import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from report import REVIEW_COL, build_report  # noqa: E402


def acc(method="exact", page=1):
    return {"concept": "c", "statement": "afirmação de teste", "quote": "trecho literal de teste aqui",
            "page_verified": page, "verify_method": method, "certainty": "sugere", "quote_verified": True}


def rej():
    return {**acc("none"), "quote_verified": False}


def setup(tmp_path: Path) -> tuple[Path, Path]:
    out = tmp_path / "out"
    (out / "pages").mkdir(parents=True)
    pdfs = tmp_path / "pdfs"
    pdfs.mkdir()
    for n in ("a", "b", "scan", "broken"):
        (pdfs / f"{n}.pdf").write_bytes(b"x")
    d1 = {"doc_id": "a", "accepted": [acc("exact"), acc("exact"), acc("loose")], "rejected": [rej()], "errors": [], "approval_rate": 0.75}
    d2 = {"doc_id": "b", "accepted": [acc("exact")], "rejected": [], "errors": [{"pages": [1, 5]}], "approval_rate": 1.0}
    (out / "a.json").write_text(json.dumps(d1), encoding="utf-8")
    (out / "b.json").write_text(json.dumps(d2), encoding="utf-8")
    long_text = "texto " * 100
    for n, text in (("a", long_text), ("b", long_text), ("scan", "")):
        (out / "pages" / f"{n}.json").write_text(json.dumps({"doc_id": n, "pages": [text]}), encoding="utf-8")
    edge = {"doc_a": "a", "concept_a": "x", "relation": "apoia", "doc_b": "b", "concept_b": "y",
            "evidence_a": {"quote": "qa", "page": 1}, "evidence_b": {"quote": "qb", "page": 2},
            "confidence": 0.8, "second_check": {"verdict": "implica", "reason": "ok"}, "display_by_default": True}
    (out / "edges.json").write_text(json.dumps([edge]), encoding="utf-8")
    return out, pdfs


def test_metrics(tmp_path):
    out, pdfs = setup(tmp_path)
    m = build_report(out, pdfs)
    assert m["claims_generated"] == 5 and m["claims_accepted"] == 4
    assert m["approval_rate"] == 0.8
    assert m["accepted_exact_pct"] == 0.75 and m["accepted_loose_pct"] == 0.25
    assert m["parsing_failures"] == ["broken", "scan"] and m["parsing_failure_rate"] == 0.5
    assert m["edges_suggested"] == 1 and m["edges_displayed_by_default"] == 1
    assert json.loads((out / "metrics.json").read_text(encoding="utf-8"))["n_documents"] == 2
    assert {d["doc_id"]: d["chunk_errors"] for d in m["per_document"]} == {"a": 0, "b": 1}


def test_claims_csv_has_review_column_and_only_accepted(tmp_path):
    out, pdfs = setup(tmp_path)
    build_report(out, pdfs)
    with (out / "claims_review.csv").open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    assert len(rows) == 4 and REVIEW_COL in rows[0] and rows[0][REVIEW_COL] == ""
    assert {"claim", "quote", "page"} <= set(rows[0]) or {"claim", "quote"} <= set(rows[0])


def test_empty_output_dir_does_not_crash(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    m = build_report(out)
    assert m["approval_rate"] is None and m["claims_csv_rows"] == 0
