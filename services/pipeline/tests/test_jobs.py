import os
import sys
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-with-enough-length-32bytes")
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.jobs import InlineQueue, process_document  # noqa: E402
from app.main import create_app  # noqa: E402
from app.pipeline.llm_client import LLMError  # noqa: E402
from app.repo import InMemoryRepo, UnverifiedClaim  # noqa: E402

REAL = "A aprendizagem significativa ocorre quando o novo conteúdo se ancora em conhecimentos prévios."
FAKE = "Esta frase inventada nunca aparece em nenhuma página do documento analisado."
BODY = (REAL + " ") * 3 + "Texto adicional de enchimento para passar do mínimo de caracteres do parser. " * 5


def make_pdf(path: Path, pages: list[str]) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        if text:
            page.insert_textbox(pymupdf.Rect(40, 40, 560, 800), text, fontsize=9)
    doc.save(path)
    doc.close()
    return path.read_bytes()


def claim(quote, page=1):
    return {"concept": "Aprendizagem significativa", "statement": "A aprendizagem depende de conhecimentos prévios.",
            "quote": quote, "page": page}


class FakeLLM:
    model = "fake-model"

    def __init__(self, *responses):
        self.responses = list(responses)

    def complete_json(self, system, user, schema, temperature=0.1):
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def setup(tmp_path, llm):
    repo = InMemoryRepo()
    storage = tmp_path / "st"
    factory = lambda: llm  # noqa: E731
    client = TestClient(create_app(repo, storage_dir=storage, llm_factory=factory,
                                   job_queue=InlineQueue(repo, storage, factory)))
    token = client.post("/auth/register", json={"email": "a@exemplo.com", "password": "senha-segura-1"}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    pid = client.post("/projects", json={"title": "Projeto de teste", "work": "tcc"}, headers=h).json()["id"]
    return repo, client, h, pid


def upload(client, h, pid, tmp_path, pages=(BODY,), name="a.pdf"):
    pdf = make_pdf(tmp_path / name, list(pages))
    r = client.post(f"/projects/{pid}/documents/upload", headers=h, data={"title": "Artigo"},
                    files={"file": (name, pdf, "application/pdf")})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_upload_triggers_extraction_and_persists_only_verified_claims(tmp_path):
    repo, client, h, pid = setup(tmp_path, FakeLLM({"claims": [claim(REAL), claim(FAKE)]}))
    doc_id = upload(client, h, pid, tmp_path)
    assert repo.get_document(doc_id)["status"] == "extracted"
    claims = client.get(f"/projects/{pid}/documents/{doc_id}/claims", headers=h).json()
    assert len(claims) == 1 and claims[0]["quote"] == REAL and claims[0]["quote_verified"] is True
    assert claims[0]["page_no"] == 1 and claims[0]["concept_id"]
    assert not any(c["quote"] == FAKE for c in repo.claims)
    assert len(repo.get_pages(doc_id)) == 1


def test_ai_usage_is_logged_without_content(tmp_path):
    repo, client, h, pid = setup(tmp_path, FakeLLM({"claims": [claim(REAL)]}))
    doc_id = upload(client, h, pid, tmp_path)
    assert len(repo.ai_usage) == 1
    u = repo.ai_usage[0]
    assert u["action"] == "extract" and u["model"] == "fake-model" and u["prompt_version"] == "v0.1"
    assert u["target_ref"] == doc_id and "quote" not in u


def test_same_concept_label_reuses_concept(tmp_path):
    repo, client, h, pid = setup(tmp_path, FakeLLM({"claims": [claim(REAL), {**claim(REAL), "concept": "aprendizagem SIGNIFICATIVA"}]}))
    upload(client, h, pid, tmp_path)
    assert len({c["concept_id"] for c in repo.claims}) == 1


def test_without_llm_document_is_parsed_but_not_extracted(tmp_path):
    repo = InMemoryRepo()
    storage = tmp_path / "st"
    factory = lambda: None  # noqa: E731
    client = TestClient(create_app(repo, storage_dir=storage, llm_factory=factory,
                                   job_queue=InlineQueue(repo, storage, factory)))
    token = client.post("/auth/register", json={"email": "a@exemplo.com", "password": "senha-segura-1"}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    pid = client.post("/projects", json={"title": "Projeto de teste", "work": "tcc"}, headers=h).json()["id"]
    doc_id = upload(client, h, pid, tmp_path)
    assert repo.get_document(doc_id)["status"] == "parsed" and repo.claims == []


def test_scanned_pdf_without_text_fails(tmp_path):
    repo, client, h, pid = setup(tmp_path, FakeLLM())
    doc_id = upload(client, h, pid, tmp_path, pages=("", ""))
    assert repo.get_document(doc_id)["status"] == "failed"


def test_corrupted_pdf_fails_without_raising(tmp_path):
    repo, client, h, pid = setup(tmp_path, FakeLLM())
    r = client.post(f"/projects/{pid}/documents/upload", headers=h,
                    files={"file": ("a.pdf", b"%PDF-1.4 broken", "application/pdf")})
    assert r.status_code == 201
    assert repo.get_document(r.json()["id"])["status"] == "failed"


def test_all_chunks_failing_marks_document_failed(tmp_path):
    repo, client, h, pid = setup(tmp_path, FakeLLM(LLMError("falhou")))
    doc_id = upload(client, h, pid, tmp_path)
    assert repo.get_document(doc_id)["status"] == "failed" and repo.claims == []


def test_repo_refuses_unverified_claims():
    repo = InMemoryRepo()
    doc = repo.create_document("p1", {"title": "t", "doi": None})
    with pytest.raises(UnverifiedClaim):
        repo.add_claims(doc["id"], [{"concept": "x", "quote_verified": False}], None, None)


def test_claims_endpoint_is_scoped_to_owner(tmp_path):
    repo, client, h, pid = setup(tmp_path, FakeLLM({"claims": [claim(REAL)]}))
    doc_id = upload(client, h, pid, tmp_path)
    other = client.post("/auth/register", json={"email": "b@exemplo.com", "password": "senha-segura-1"}).json()["token"]
    assert client.get(f"/projects/{pid}/documents/{doc_id}/claims", headers={"Authorization": f"Bearer {other}"}).status_code == 404
