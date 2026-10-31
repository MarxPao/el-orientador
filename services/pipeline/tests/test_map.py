import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-with-enough-length-32bytes")
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.jobs import InlineQueue  # noqa: E402
from app.main import create_app  # noqa: E402
from app.repo import InMemoryRepo  # noqa: E402
from tests.test_jobs import FakeLLM, make_pdf  # noqa: E402

Q1 = "A aprendizagem significativa depende de conhecimentos prévios do aluno em sala."
Q2 = "Conhecimentos prévios do aluno influenciam a aprendizagem em sala de aula."
FILL = "Texto adicional de enchimento para passar do mínimo de caracteres do parser. " * 6


def c(concept, quote):
    return {"concept": concept, "statement": quote, "quote": quote, "page": 1}


CLS = {"relation": "apoia", "rationale": "ambos tratam de conhecimentos prévios", "confidence": 0.8}
IMPLICA = {"verdict": "implica", "reason": "ok"}
NAO = {"verdict": "nao_implica", "reason": "inferido"}


def setup(tmp_path, *llm_responses):
    llm = FakeLLM(*llm_responses)
    repo = InMemoryRepo()
    storage = tmp_path / "st"
    factory = lambda: llm  # noqa: E731
    client = TestClient(create_app(repo, storage_dir=storage, llm_factory=factory,
                                   job_queue=InlineQueue(repo, storage, factory)))
    token = client.post("/auth/register", json={"email": "a@exemplo.com", "password": "senha-segura-1"}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    pid = client.post("/projects", json={"title": "Projeto de teste", "work": "tcc"}, headers=h).json()["id"]
    for i, q in enumerate((Q1, Q2)):
        pdf = make_pdf(tmp_path / f"d{i}.pdf", [q + " " + FILL])
        r = client.post(f"/projects/{pid}/documents/upload", headers=h, data={"title": f"Doc {i}"},
                        files={"file": (f"d{i}.pdf", pdf, "application/pdf")})
        assert r.status_code == 201
    return repo, client, h, pid


def extraction():
    return [{"claims": [c("Aprendizagem significativa", Q1)]}, {"claims": [c("Conhecimento prévio", Q2)]}]


def test_map_lists_concepts_without_edges_initially(tmp_path):
    _, client, h, pid = setup(tmp_path, *extraction())
    m = client.get(f"/projects/{pid}/map", headers=h).json()
    assert {n["label"] for n in m["nodes"]} == {"Aprendizagem significativa", "Conhecimento prévio"}
    assert all(n["n_claims"] == 1 for n in m["nodes"]) and m["edges"] == []


def test_suggest_creates_suggested_edge_with_evidence(tmp_path):
    repo, client, h, pid = setup(tmp_path, *extraction(), CLS, IMPLICA)
    assert client.post(f"/projects/{pid}/map/suggest", headers=h).json() == {"created": 1}
    m = client.get(f"/projects/{pid}/map", headers=h).json()
    e = m["edges"][0]
    assert e["status"] == "suggested" and e["relation"] == "apoia" and e["display_by_default"] is True
    assert {e["source"], e["target"]} == {n["id"] for n in m["nodes"]}
    assert {ev["side"] for ev in repo.edges[0]["evidence"]} == {"source", "target"}
    assert any(u["action"] == "relate" for u in repo.ai_usage)


def test_failed_second_check_is_hidden_by_default(tmp_path):
    _, client, h, pid = setup(tmp_path, *extraction(), CLS, NAO)
    client.post(f"/projects/{pid}/map/suggest", headers=h)
    e = client.get(f"/projects/{pid}/map", headers=h).json()["edges"][0]
    assert e["display_by_default"] is False and e["confidence"] < 0.8


def test_pair_with_existing_edge_is_not_suggested_again(tmp_path):
    repo, client, h, pid = setup(tmp_path, *extraction(), CLS, IMPLICA)
    client.post(f"/projects/{pid}/map/suggest", headers=h)
    repo.edges[0]["status"] = "rejected"  # user rejected it: memory must prevent a new suggestion
    assert client.post(f"/projects/{pid}/map/suggest", headers=h).json() == {"created": 0}
    assert len(repo.edges) == 1


def test_suggest_without_llm_returns_503_and_map_is_scoped(tmp_path):
    _, client, h, pid = setup(tmp_path, *extraction())
    other = client.post("/auth/register", json={"email": "b@exemplo.com", "password": "senha-segura-1"}).json()["token"]
    ho = {"Authorization": f"Bearer {other}"}
    assert client.get(f"/projects/{pid}/map", headers=ho).status_code == 404
    assert client.post(f"/projects/{pid}/map/suggest", headers=ho).status_code == 404
    assert client.get(f"/projects/{pid}/map").status_code == 401


def _suggested_edge(tmp_path):
    repo, client, h, pid = setup(tmp_path, *extraction(), CLS, IMPLICA)
    client.post(f"/projects/{pid}/map/suggest", headers=h)
    edge_id = client.get(f"/projects/{pid}/map", headers=h).json()["edges"][0]["id"]
    return repo, client, h, pid, edge_id


def test_evidence_returns_literal_quote_page_and_context(tmp_path):
    _, client, h, pid, edge_id = _suggested_edge(tmp_path)
    ev = client.get(f"/projects/{pid}/edges/{edge_id}/evidence", headers=h).json()
    assert [e["side"] for e in ev] == ["source", "target"]
    assert {e["quote"] for e in ev} == {Q1, Q2}  # text taken from the stored page, not from the model
    assert all(e["page"] == 1 and e["has_pdf"] and e["document_title"].startswith("Doc") for e in ev)
    assert any("enchimento" in e["context_after"] for e in ev)


def test_document_file_is_served_to_owner_only(tmp_path):
    repo, client, h, pid, edge_id = _suggested_edge(tmp_path)
    ev = client.get(f"/projects/{pid}/edges/{edge_id}/evidence", headers=h).json()
    url = f"/projects/{pid}/documents/{ev[0]['document_id']}/file"
    r = client.get(url, headers=h)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF-")
    assert client.get(url).status_code == 401
    other = client.post("/auth/register", json={"email": "b@exemplo.com", "password": "senha-segura-1"}).json()["token"]
    assert client.get(url, headers={"Authorization": f"Bearer {other}"}).status_code == 404


def test_evidence_unknown_edge_and_other_user(tmp_path):
    _, client, h, pid, edge_id = _suggested_edge(tmp_path)
    assert client.get(f"/projects/{pid}/edges/nao-existe/evidence", headers=h).status_code == 404
    other = client.post("/auth/register", json={"email": "b@exemplo.com", "password": "senha-segura-1"}).json()["token"]
    assert client.get(f"/projects/{pid}/edges/{edge_id}/evidence", headers={"Authorization": f"Bearer {other}"}).status_code == 404


def test_confirm_edge(tmp_path):
    repo, client, h, pid, edge_id = _suggested_edge(tmp_path)
    r = client.patch(f"/projects/{pid}/edges/{edge_id}", json={"action": "confirm"}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "confirmed" and r.json()["relation"] == "apoia"


def test_rejected_link_is_not_suggested_again(tmp_path):
    """T2.3 acceptance: a rejected link is remembered and never suggested again."""
    llm_extra = [CLS, IMPLICA, CLS, IMPLICA]  # a second suggest round would consume these if it asked the LLM
    repo, client, h, pid = setup(tmp_path, *extraction(), CLS, IMPLICA, *llm_extra)
    assert client.post(f"/projects/{pid}/map/suggest", headers=h).json() == {"created": 1}
    edge_id = client.get(f"/projects/{pid}/map", headers=h).json()["edges"][0]["id"]
    r = client.patch(f"/projects/{pid}/edges/{edge_id}", json={"action": "reject", "note": "não é o mesmo construto"}, headers=h)
    assert r.json()["status"] == "rejected" and repo.edges[0]["user_note"] == "não é o mesmo construto"
    assert client.post(f"/projects/{pid}/map/suggest", headers=h).json() == {"created": 0}
    m = client.get(f"/projects/{pid}/map", headers=h).json()
    assert len(m["edges"]) == 1 and m["edges"][0]["status"] == "rejected"  # kept, not deleted


def test_edit_relation_confirms_with_new_type(tmp_path):
    _, client, h, pid, edge_id = _suggested_edge(tmp_path)
    r = client.patch(f"/projects/{pid}/edges/{edge_id}", json={"action": "edit", "relation": "contrasta"}, headers=h)
    assert r.json()["relation"] == "contrasta" and r.json()["status"] == "confirmed"
    assert client.patch(f"/projects/{pid}/edges/{edge_id}", json={"action": "edit"}, headers=h).status_code == 422
    assert client.patch(f"/projects/{pid}/edges/{edge_id}", json={"action": "edit", "relation": "nenhuma"}, headers=h).status_code == 422


def test_edit_to_existing_relation_conflicts(tmp_path):
    repo, client, h, pid, edge_id = _suggested_edge(tmp_path)
    first = repo.edges[0]
    repo.add_edges(pid, [{**first, "relation": "contrasta", "evidence": first["evidence"]}])
    r = client.patch(f"/projects/{pid}/edges/{edge_id}", json={"action": "edit", "relation": "contrasta"}, headers=h)
    assert r.status_code == 409


def test_decision_is_scoped_to_owner_and_validates_input(tmp_path):
    _, client, h, pid, edge_id = _suggested_edge(tmp_path)
    other = client.post("/auth/register", json={"email": "b@exemplo.com", "password": "senha-segura-1"}).json()["token"]
    ho = {"Authorization": f"Bearer {other}"}
    assert client.patch(f"/projects/{pid}/edges/{edge_id}", json={"action": "confirm"}, headers=ho).status_code == 404
    assert client.patch(f"/projects/{pid}/edges/{edge_id}", json={"action": "confirm"}).status_code == 401
    assert client.patch(f"/projects/{pid}/edges/nao-existe", json={"action": "confirm"}, headers=h).status_code == 404
    assert client.patch(f"/projects/{pid}/edges/{edge_id}", json={"action": "apagar"}, headers=h).status_code == 422
