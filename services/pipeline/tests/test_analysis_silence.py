"""Tests for integrity error handling and removal of silent fallbacks (Analysis, Sections, Repo)."""
import pytest
from fastapi.testclient import TestClient

from services.pipeline.app.export_docx import build_docx_manuscript
from services.pipeline.app.main import create_app
from services.pipeline.app.repo import InMemoryRepo
from services.pipeline.app.security import create_token, hash_password


def test_dissect_pdf_failure_is_visible_and_marks_failed(monkeypatch):
    """When parse_pdf fails, the document must transition to status='failed' and return 422,
    never failing silently with 0 pages."""
    repo = InMemoryRepo()
    user = repo.create_user("student@usp.br", "Estudante", hash_password("pass123"))
    project = repo.create_project(user["id"], {"title": "TCC Test", "work": "tcc"})
    doc = repo.create_document(project["id"], {
        "title": "Artigo Corrompido",
        "storage_path": "corrupted.pdf",
        "mime_type": "application/pdf",
        "file_size": 1024,
    })

    app = create_app(repo=repo)
    client = TestClient(app)
    token = create_token(user["id"])
    headers = {"Authorization": f"Bearer {token}"}

    def _failing_parse_pdf(*args, **kwargs):
        raise ValueError("Formato de PDF corrompido ou protegido por senha")

    monkeypatch.setattr("services.pipeline.app.jobs.parse_pdf", _failing_parse_pdf)

    res = client.post(f"/projects/{project['id']}/documents/{doc['id']}/dissect", headers=headers)
    assert res.status_code == 422
    assert "Falha na leitura do PDF" in res.json()["detail"]

    # Verify document status in repo is failed with stage parse_failed
    saved_doc = repo.get_document(doc["id"])
    assert saved_doc["status"] == "failed"
    assert saved_doc["stage"] == "parse_failed"

    # Verify error was logged in repo error_events
    errors = repo.list_error_events()
    assert any(e["source"] == "dissect" and "ValueError" in e["error_type"] for e in errors)


def test_docx_export_signals_unavailable_paraphrase_verification():
    """When unreviewed_paraphrases is None (embeddings/model unavailable),
    the generated DOCX must explicitly state that automated paraphrase verification was unavailable."""
    repo = InMemoryRepo()
    user = repo.create_user("student@usp.br", "Estudante", hash_password("pass123"))
    project = repo.create_project(user["id"], {"title": "TCC Test", "work": "tcc"})
    project["owner_name"] = "Estudante"

    repo.create_section(project["id"], "Capítulo 1", None, 1, content={
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Texto inicial do trabalho acadêmico."}]}]
    })

    buf = build_docx_manuscript(
        repo, project["id"], project,
        omit_ai_declaration=False,
        unreviewed_paraphrases=None,  # Unavailable
    )

    import docx
    doc = docx.Document(buf)
    all_text = " ".join(p.text for p in doc.paragraphs)
    assert "Aviso de integridade: a verificação automatizada de paráfrases de IA estava indisponível" in all_text


def test_repo_get_beta_metrics_signals_indisponivel_on_failure(monkeypatch):
    """When reading beta_feedback fails, get_beta_metrics must report status='indisponivel'
    and None for averages, never zeroing metrics silently."""
    repo = InMemoryRepo()

    class _BrokenFeedbackList:
        def __len__(self):
            raise RuntimeError("Database table corrupted")

    monkeypatch.setattr(repo, "beta_feedback", _BrokenFeedbackList())

    metrics = repo.get_beta_metrics()
    fb = metrics["feedback"]
    assert fb["status"] == "indisponivel"
    assert fb["total_responses"] is None
    assert fb["average_overall_rating"] is None
    assert fb["average_socratic_gate_helpful"] is None
    assert fb["average_evidence_trust"] is None
    assert fb["average_relief_level"] is None
    assert fb["pricing_preferences"] is None
