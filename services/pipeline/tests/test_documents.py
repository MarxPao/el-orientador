import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-with-enough-length-32bytes")
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.main import create_app  # noqa: E402
from app.metadata import LookupFailed, NotFound, lookup_doi, normalize_doi  # noqa: E402
from app.repo import InMemoryRepo  # noqa: E402

PROJECT = {"title": "Aprendizagem significativa no ensino médio", "work": "tcc"}
PDF = b"%PDF-1.4\n% fake pdf for tests\n"

CROSSREF = {"message": {
    "title": ["Meaningful learning in practice"],
    "author": [{"given": "Ana", "family": "Silva"}, {"name": "Grupo X"}],
    "issued": {"date-parts": [[2019, 5]]},
    "container-title": ["Journal of Learning"],
}}
CROSSREF_RETRACTED = {"message": {**CROSSREF["message"], "updated-by": [{"type": "retraction"}]}}
OPENALEX = {"title": "Aprendizagem significativa", "publication_year": 2020, "is_retracted": True,
            "authorships": [{"author": {"display_name": "Bia Souza"}}],
            "primary_location": {"source": {"display_name": "Revista Y"}}}


def fake_fetch(crossref=None, openalex=None):
    def fetch(url):
        for host, result in (("crossref", crossref), ("openalex", openalex)):
            if host in url:
                if isinstance(result, Exception):
                    raise result
                return result
        raise AssertionError(url)
    return fetch


class NoQueue:
    def enqueue(self, document_id):
        pass


def make(tmp_path, **kw):
    client = TestClient(create_app(InMemoryRepo(), fetch_json=fake_fetch(**kw), storage_dir=tmp_path / "st", job_queue=NoQueue()))
    token = client.post("/auth/register", json={"email": "a@exemplo.com", "password": "senha-segura-1"}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    pid = client.post("/projects", json=PROJECT, headers=h).json()["id"]
    return client, h, pid


def test_normalize_doi():
    assert normalize_doi("https://doi.org/10.1000/ABC.1") == "10.1000/abc.1"
    assert normalize_doi("doi:10.1000/x") == "10.1000/x"
    with pytest.raises(ValueError):
        normalize_doi("não é doi")


def test_lookup_uses_crossref_then_falls_back_to_openalex():
    m = lookup_doi("10.1000/x", fake_fetch(crossref=CROSSREF))
    assert m["metadata_source"] == "crossref" and m["authors"] == ["Ana Silva", "Grupo X"] and m["year"] == 2019
    m = lookup_doi("10.1000/x", fake_fetch(crossref=NotFound(), openalex=OPENALEX))
    assert m["metadata_source"] == "openalex" and m["retracted"] is True
    assert lookup_doi("10.1000/x", fake_fetch(crossref=CROSSREF_RETRACTED))["retracted"] is True


def test_lookup_errors_distinguish_not_found_from_outage():
    with pytest.raises(NotFound):
        lookup_doi("10.1000/x", fake_fetch(crossref=NotFound(), openalex=NotFound()))
    with pytest.raises(LookupFailed):
        lookup_doi("10.1000/x", fake_fetch(crossref=LookupFailed(), openalex=NotFound()))


def test_add_by_doi_creates_document_with_real_metadata(tmp_path):
    client, h, pid = make(tmp_path, crossref=CROSSREF)
    r = client.post(f"/projects/{pid}/documents/doi", json={"doi": "https://doi.org/10.1000/ABC"}, headers=h)
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["doi"] == "10.1000/abc" and d["title"] == "Meaningful learning in practice"
    assert d["metadata_source"] == "crossref" and d["analysis"] == "abstract_only"
    assert client.post(f"/projects/{pid}/documents/doi", json={"doi": "10.1000/abc"}, headers=h).status_code == 409
    assert len(client.get(f"/projects/{pid}/documents", headers=h).json()) == 1


def test_doi_errors(tmp_path):
    client, h, pid = make(tmp_path, crossref=NotFound(), openalex=NotFound())
    assert client.post(f"/projects/{pid}/documents/doi", json={"doi": "isto nao e doi"}, headers=h).status_code == 422
    assert client.post(f"/projects/{pid}/documents/doi", json={"doi": "10.1000/zzz"}, headers=h).status_code == 404
    client, h, pid = make(tmp_path, crossref=LookupFailed(), openalex=LookupFailed())
    assert client.post(f"/projects/{pid}/documents/doi", json={"doi": "10.1000/zzz"}, headers=h).status_code == 502


def test_upload_pdf_stores_file_with_server_name(tmp_path):
    client, h, pid = make(tmp_path)
    r = client.post(f"/projects/{pid}/documents/upload", headers=h, data={"title": "Meu artigo"},
                    files={"file": ("../../evil.pdf", PDF, "application/pdf")})
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["title"] == "Meu artigo" and d["metadata_source"] == "manual" and d["analysis"] == "full_text"
    stored = tmp_path / "st" / d["storage_path"]
    assert stored.read_bytes() == PDF and "evil" not in d["storage_path"]


def test_upload_with_doi_uses_database_metadata(tmp_path):
    client, h, pid = make(tmp_path, crossref=CROSSREF)
    r = client.post(f"/projects/{pid}/documents/upload", headers=h, data={"doi": "10.1000/abc"},
                    files={"file": ("a.pdf", PDF, "application/pdf")})
    assert r.status_code == 201 and r.json()["metadata_source"] == "crossref"


def test_upload_rejects_non_pdf_and_duplicate_cleans_file(tmp_path):
    client, h, pid = make(tmp_path, crossref=CROSSREF)
    r = client.post(f"/projects/{pid}/documents/upload", headers=h, files={"file": ("a.pdf", b"hello", "application/pdf")})
    assert r.status_code == 422
    up = lambda: client.post(f"/projects/{pid}/documents/upload", headers=h, data={"doi": "10.1000/abc"},
                             files={"file": ("a.pdf", PDF, "application/pdf")})
    assert up().status_code == 201 and up().status_code == 409
    assert len(list((tmp_path / "st").rglob("*.pdf"))) == 1


def test_documents_are_scoped_to_project_owner(tmp_path):
    client, h, pid = make(tmp_path, crossref=CROSSREF)
    other = client.post("/auth/register", json={"email": "b@exemplo.com", "password": "senha-segura-1"}).json()["token"]
    ho = {"Authorization": f"Bearer {other}"}
    assert client.get(f"/projects/{pid}/documents", headers=ho).status_code == 404
    assert client.post(f"/projects/{pid}/documents/doi", json={"doi": "10.1000/abc"}, headers=ho).status_code == 404
    assert client.post(f"/projects/{pid}/documents/upload", headers=ho,
                       files={"file": ("a.pdf", PDF, "application/pdf")}).status_code == 404
    assert client.get(f"/projects/{pid}/documents").status_code == 401


def test_upload_has_no_size_cap_by_default_and_MAX_PDF_MB_sets_one(tmp_path, monkeypatch):
    big = PDF + b"0" * (3 * 1024 * 1024)  # larger than the cap set below
    monkeypatch.delenv("MAX_PDF_MB", raising=False)
    client, h, pid = make(tmp_path)
    r = client.post(f"/projects/{pid}/documents/upload", headers=h, data={"title": "Livro inteiro"},
                    files={"file": ("livro.pdf", big, "application/pdf")})
    assert r.status_code == 201, r.text  # local app: no cap unless the owner asks for one
    monkeypatch.setenv("MAX_PDF_MB", "2")
    r = client.post(f"/projects/{pid}/documents/upload", headers=h, data={"title": "Outro livro"},
                    files={"file": ("outro.pdf", big, "application/pdf")})
    assert r.status_code == 413 and "2 MB" in r.json()["detail"]
    monkeypatch.setenv("MAX_PDF_MB", "lixo")  # a malformed value never blocks uploads
    r = client.post(f"/projects/{pid}/documents/upload", headers=h, data={"title": "Terceiro livro"},
                    files={"file": ("terceiro.pdf", big, "application/pdf")})
    assert r.status_code == 201, r.text
