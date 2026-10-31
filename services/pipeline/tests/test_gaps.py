import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-with-enough-length-32bytes")
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.gaps import build_note, detect_gaps, find_gap_pairs, run_searches  # noqa: E402
from app.jobs import InlineQueue  # noqa: E402
from app.main import create_app  # noqa: E402
from app.metadata import LookupFailed  # noqa: E402
from app.repo import InMemoryRepo  # noqa: E402
from tests.test_jobs import FakeLLM, make_pdf  # noqa: E402

Q1 = "A aprendizagem significativa depende de conhecimentos prévios do aluno em sala de aula."
Q2 = "Conhecimentos prévios do aluno influenciam a aprendizagem em sala de aula."
Q3 = "A motivação intrínseca orienta o esforço e a atenção dos estudantes."
FILL = "Texto adicional de enchimento para passar do mínimo de caracteres do parser. " * 6


def c(concept, quote):
    return {"concept": concept, "statement": quote, "quote": quote, "page": 1}


CLS = {"relation": "apoia", "rationale": "ambos tratam de conhecimentos prévios", "confidence": 0.8}
IMPLICA = {"verdict": "implica", "reason": "ok"}


def mock_fetch(url: str):
    if "openalex" in url:
        return {"meta": {"count": 0}, "results": []}
    if "semanticscholar" in url:
        return {"total": 0, "data": []}
    raise AssertionError(url)


def test_note_never_claims_nothing_exists():
    searches = [
        {"source": "openalex", "query": '"A" AND "B"', "total": 0, "results": [], "status": "ok"},
        {"source": "semantic_scholar", "query": "A B", "total": 0, "results": [], "status": "ok"},
    ]
    note = build_note(searches)
    assert "Não encontrei estudos nas buscas feitas" in note
    assert "não existem estudos" not in note.casefold()

    failed = [
        {"source": "openalex", "query": "q", "total": None, "results": [], "status": "failed"},
        {"source": "semantic_scholar", "query": "q", "total": 0, "results": [], "status": "ok"},
    ]
    assert "Busca incompleta" in build_note(failed)


def test_find_gap_pairs_excludes_linked_and_known_gaps():
    concepts = [{"id": "c1", "label": "A"}, {"id": "c2", "label": "B"}, {"id": "c3", "label": "C"}]
    claims = [
        {"concept_id": "c1", "statement": "alpha beta"},
        {"concept_id": "c2", "statement": "alpha gamma"},
        {"concept_id": "c3", "statement": "delta epsilon"},
    ]
    linked = {frozenset(("c1", "c2"))}
    known = {frozenset(("c2", "c3"))}
    pairs = find_gap_pairs(concepts, claims, linked, known)
    assert len(pairs) == 1
    assert {pairs[0][0]["id"], pairs[0][1]["id"]} == {"c1", "c3"}


def test_run_searches_tolerates_service_failures():
    def failing_fetch(url):
        raise LookupFailed("timeout")

    searches = run_searches("Conceito A", "Conceito B", failing_fetch)
    assert len(searches) == 2
    assert all(s["status"] == "failed" for s in searches)


def setup_project_with_3_concepts(tmp_path):
    repo = InMemoryRepo()
    storage = tmp_path / "st"
    llm = FakeLLM(
        {"claims": [c("Aprendizagem significativa", Q1)]},
        {"claims": [c("Conhecimento prévio", Q2)]},
        {"claims": [c("Motivação", Q3)]},
        CLS,
        IMPLICA,
    )
    factory = lambda: llm  # noqa: E731
    client = TestClient(
        create_app(
            repo,
            fetch_json=mock_fetch,
            storage_dir=storage,
            llm_factory=factory,
            job_queue=InlineQueue(repo, storage, factory),
        )
    )
    token = client.post("/auth/register", json={"email": "a@exemplo.com", "password": "senha-segura-1"}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    pid = client.post("/projects", json={"title": "Projeto Lacunas", "work": "tcc"}, headers=h).json()["id"]

    for i, q in enumerate((Q1, Q2, Q3)):
        pdf = make_pdf(tmp_path / f"d{i}.pdf", [q + " " + FILL])
        r = client.post(
            f"/projects/{pid}/documents/upload",
            headers=h,
            data={"title": f"Doc {i}"},
            files={"file": (f"d{i}.pdf", pdf, "application/pdf")},
        )
        assert r.status_code == 201

    # Suggest 1 link between Aprendizagem and Conhecimento prévio
    client.post(f"/projects/{pid}/map/suggest", headers=h)
    return repo, client, h, pid


def test_gaps_api_detect_list_and_decide(tmp_path):
    repo, client, h, pid = setup_project_with_3_concepts(tmp_path)

    # Detect gaps
    r = client.post(f"/projects/{pid}/gaps/detect", headers=h)
    assert r.status_code == 200
    res = r.json()
    assert res["created"] >= 1
    gap = res["gaps"][0]
    assert gap["status"] == "open"
    assert "Não encontrei estudos nas buscas feitas" in gap["note"]
    assert len(gap["searches"]) == 2

    # Map returns gaps
    m = client.get(f"/projects/{pid}/map", headers=h).json()
    assert len(m["gaps"]) == res["created"]

    # List gaps endpoint
    gaps_list = client.get(f"/projects/{pid}/gaps", headers=h).json()
    assert len(gaps_list) == res["created"]

    # Decide gap: adopt as research problem
    patch_r = client.patch(
        f"/projects/{pid}/gaps/{gap['id']}",
        json={"status": "adopted_as_problem", "note": "Tema promissor para o TCC"},
        headers=h,
    )
    assert patch_r.status_code == 200
    updated = patch_r.json()
    assert updated["status"] == "adopted_as_problem"
    assert updated["note"] == "Tema promissor para o TCC"

    # Gaps detection on second run does not duplicate known gaps
    r2 = client.post(f"/projects/{pid}/gaps/detect", headers=h)
    assert r2.status_code == 200
    assert r2.json()["created"] == 0
