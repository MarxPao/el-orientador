"""Tests for open repositories federated search and import (T7.1)."""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-with-enough-length-32bytes")
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import create_app
from app.repo import InMemoryRepo
from app.repositories import (
    _reconstruct_abstract,
    download_open_pdf,
    federated_search,
    search_bdtd,
    search_openalex,
    search_scielo,
)

FAKE_OPENALEX_WORK = {
    "id": "https://openalex.org/W2741809807",
    "doi": "https://doi.org/10.1016/j.compedu.2017.08.005",
    "title": "Active learning in computer science education",
    "display_name": "Active learning in computer science education",
    "publication_year": 2018,
    "authorships": [
        {"author": {"display_name": "Maria Silva"}},
        {"author": {"display_name": "Carlos Souza"}},
    ],
    "primary_location": {
        "source": {"display_name": "Computers & Education"},
        "is_oa": True,
        "pdf_url": "https://arxiv.org/pdf/1708.00001.pdf",
        "landing_page_url": "https://doi.org/10.1016/j.compedu.2017.08.005",
    },
    "open_access": {
        "is_oa": True,
        "oa_url": "https://arxiv.org/pdf/1708.00001.pdf",
    },
    "cited_by_count": 87,
    "abstract_inverted_index": {
        "Active": [0],
        "learning": [1],
        "improves": [2],
        "student": [3],
        "retention": [4],
        "significantly.": [5],
    },
}

FAKE_CROSSREF_SCIELO_WORK = {
    "DOI": "10.1590/s0100-15782020000100005",
    "title": ["Metodologias Ativas no Ensino Superior Brasileiro"],
    "author": [
        {"given": "Ana", "family": "Ribeiro"},
    ],
    "issued": {"date-parts": [[2020, 5, 12]]},
    "container-title": ["Revista Brasileira de Educação"],
    "is-referenced-by-count": 34,
    "abstract": "<jats:p>Este artigo investiga práticas pedagógicas ativas no ensino superior.</jats:p>",
    "link": [
        {"content-type": "application/pdf", "URL": "https://www.scielo.br/j/rbe/a/xyz/?format=pdf"}
    ],
}


def fake_fetcher(url: str) -> dict:
    if "crossref.org" in url:
        return {
            "status": "ok",
            "message": {
                "total-results": 1,
                "items": [FAKE_CROSSREF_SCIELO_WORK],
            },
        }
    if "openalex.org" in url:
        return {
            "meta": {"count": 1},
            "results": [FAKE_OPENALEX_WORK],
        }
    raise ValueError(f"Unexpected url: {url}")


def test_reconstruct_abstract():
    idx = {"O": [0], "aluno": [1], "aprende": [2], "melhor": [3]}
    res = _reconstruct_abstract(idx)
    assert res == "O aluno aprende melhor"
    assert _reconstruct_abstract(None) is None
    assert _reconstruct_abstract({}) is None


def test_search_openalex_formatting():
    res = search_openalex("active learning", limit=5, fetch=fake_fetcher)
    assert res["status"] == "ok"
    assert res["total"] == 1
    assert len(res["results"]) == 1
    item = res["results"][0]
    assert item["title"] == "Active learning in computer science education"
    assert item["authors"] == ["Maria Silva", "Carlos Souza"]
    assert item["year"] == 2018
    assert item["venue"] == "Computers & Education"
    assert item["doi"] == "10.1016/j.compedu.2017.08.005"
    assert item["is_open_access"] is True
    assert item["pdf_url"] == "https://arxiv.org/pdf/1708.00001.pdf"
    assert item["abstract"] == "Active learning improves student retention significantly."


def test_search_scielo_formatting():
    res = search_scielo("metodologias ativas", limit=5, fetch=fake_fetcher)
    assert res["status"] == "ok"
    assert len(res["results"]) == 1
    item = res["results"][0]
    assert item["source"] == "scielo"
    assert item["title"] == "Metodologias Ativas no Ensino Superior Brasileiro"
    assert item["authors"] == ["Ana Ribeiro"]
    assert item["year"] == 2020
    assert item["venue"] == "Revista Brasileira de Educação"
    assert item["doi"] == "10.1590/s0100-15782020000100005"
    assert item["is_open_access"] is True
    assert item["pdf_url"] == "https://www.scielo.br/j/rbe/a/xyz/?format=pdf"
    assert item["abstract"] == "Este artigo investiga práticas pedagógicas ativas no ensino superior."


def test_search_bdtd_thesis():
    res = search_bdtd("evasão escolar", limit=5, fetch=fake_fetcher)
    assert res["status"] == "ok"
    assert res["results"][0]["source"] == "bdtd"


def test_federated_search_all_resilient():
    # Test federated with one failing source
    def failing_fetcher(url: str):
        if "crossref.org" in url:
            raise RuntimeError("CrossRef down")
        return fake_fetcher(url)

    res = federated_search("aprendizagem", source="all", limit=10, fetch=failing_fetcher)
    assert res["status"] == "ok"
    # Even if CrossRef fails, OpenAlex results still return!
    assert len(res["results"]) >= 1


def test_download_open_pdf_validation():
    # Valid PDF
    mock_resp = MagicMock()
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.headers = {"Content-Type": "application/pdf"}
    mock_resp.read.return_value = b"%PDF-1.5 test file content"
    with patch("urllib.request.urlopen", return_value=mock_resp):
        pdf_bytes = download_open_pdf("https://example.org/test.pdf")
        assert pdf_bytes.startswith(b"%PDF-")

    # Invalid HTML page returned instead of PDF
    mock_resp.read.return_value = b"<!DOCTYPE html><html><body>Login required</body></html>"
    with patch("urllib.request.urlopen", return_value=mock_resp):
        with pytest.raises(ValueError, match="HTML"):
            download_open_pdf("https://example.org/paywalled.pdf")


@pytest.fixture
def api_client(tmp_path: Path):
    repo = InMemoryRepo()
    app = create_app(repo=repo, fetch_json=fake_fetcher, storage_dir=tmp_path)
    return TestClient(app)


def test_repositories_endpoints_flow(api_client: TestClient, tmp_path: Path):
    # 1. Register & Auth
    reg = api_client.post(
        "/auth/register",
        json={"email": "pesquisador@rep.br", "password": "senha-segura-123", "name": "Pesquisador Rep"},
    )
    token = reg.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Search Repositories
    s_res = api_client.get("/repositories/search?q=aprendizagem&source=all&limit=5", headers=headers)
    assert s_res.status_code == 200
    s_data = s_res.json()
    assert s_data["status"] == "ok"
    assert len(s_data["results"]) >= 1

    # 3. Create project
    proj = api_client.post(
        "/projects",
        json={"title": "Pesquisa Aberta", "work": "tcc", "citation_style": "abnt"},
        headers=headers,
    ).json()
    project_id = proj["id"]

    # 4. Import document without PDF (abstract_only)
    item = s_data["results"][0]
    imp_res = api_client.post(
        f"/projects/{project_id}/documents/import-repository",
        json={
            "source_id": item["id"],
            "repository": item["source"],
            "title": item["title"],
            "authors": item["authors"],
            "year": item["year"],
            "venue": item["venue"],
            "doi": item["doi"],
            "pdf_url": item["pdf_url"],
            "fetch_pdf": False,
        },
        headers=headers,
    )
    assert imp_res.status_code == 201
    doc = imp_res.json()["document"]
    assert doc["title"] == item["title"]
    assert doc["analysis"] == "abstract_only"
    assert imp_res.json()["downloaded"] is False

    # 5. Duplicate DOI prevention
    dup_res = api_client.post(
        f"/projects/{project_id}/documents/import-repository",
        json={
            "repository": item["source"],
            "title": "Outro título com mesmo DOI",
            "doi": item["doi"],
            "fetch_pdf": False,
        },
        headers=headers,
    )
    assert dup_res.status_code == 409

    # 6. Import with open PDF download simulation
    mock_resp = MagicMock()
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.headers = {"Content-Type": "application/pdf"}
    mock_resp.read.return_value = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    with patch("urllib.request.urlopen", return_value=mock_resp):
        imp_pdf = api_client.post(
            f"/projects/{project_id}/documents/import-repository",
            json={
                "repository": "scielo",
                "title": "Artigo com PDF integral aberto",
                "authors": ["Pesquisador Um"],
                "year": 2024,
                "venue": "SciELO Educação",
                "doi": "10.1590/novo-artigo-2024",
                "pdf_url": "https://www.scielo.br/pdf/artigo.pdf",
                "fetch_pdf": True,
            },
            headers=headers,
        )
        assert imp_pdf.status_code == 201
        doc_pdf = imp_pdf.json()["document"]
        assert imp_pdf.json()["downloaded"] is True
        assert doc_pdf["analysis"] == "full_text"
        assert doc_pdf["storage_path"] == f"{project_id}/{doc_pdf['id']}.pdf"
        assert (tmp_path / doc_pdf["storage_path"]).exists()
