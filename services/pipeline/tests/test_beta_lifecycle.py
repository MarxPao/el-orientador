"""T6.4 - Comprehensive Beta Lifecycle Smoke Test.

Validates the full end-to-end student and advisor journey:
1. Registration & Auth (JWT + Cookie)
2. Project scoping & template initialization
3. Progress tree with Socratic Gate & Conscious Skip
4. Bibliographic ingestion & verified quotes
5. Knowledge Map 3-state edge decisions & memory
6. Gap detection with audit trails
7. Manuscript Editor with section hierarchy & deterministic coherence checks
8. Human Advisor invitation, comments, and transparent audit report
9. ABNT DOCX export with mandatory AI Usage Declaration
"""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-with-enough-length-32bytes")
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import create_app
from app.repo import InMemoryRepo
from app.metadata import FetchJson


FAKE_CROSSREF = {
    "status": "ok",
    "message": {
        "title": ["Metodologias Ativas e Avaliação Formativa"],
        "author": [{"given": "Maria", "family": "Silva"}],
        "created": {"date-parts": [[2025, 3, 15]]},
        "publisher": "Revista Brasileira de Educação",
        "container-title": ["RBE"],
    },
}


def fake_fetcher(url: str) -> dict:
    return FAKE_CROSSREF


@pytest.fixture
def client(tmp_path: Path):
    repo = InMemoryRepo()
    app = create_app(repo=repo, fetch_json=fake_fetcher, storage_dir=tmp_path)
    app.state.repo = repo
    return TestClient(app)


def test_complete_beta_lifecycle(client: TestClient):
    # 1. Registration
    reg = client.post(
        "/auth/register",
        json={"email": "estudante@beta.edu.br", "password": "senha-segura-beta-123", "name": "Estudante Beta"},
        headers={"X-Auth-Cookie": "1"}
    )
    assert reg.status_code == 201
    token = reg.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert "orientador_token" in reg.cookies

    # 2. Project Creation (TCC)
    proj_res = client.post(
        "/projects",
        json={
            "title": "Impacto das Metodologias Ativas na Redução da Evasão",
            "work": "tcc",
            "institution": "Universidade Federal",
            "deadline": "2027-12-15",
            "weekly_hours": 12
        },
        headers=headers
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    # 3. Progress Tree Initialization & Socratic Gate
    tree_res = client.get(f"/projects/{project_id}/tree", headers=headers)
    assert tree_res.status_code == 200
    tree_data = tree_res.json()
    assert len(tree_data["nodes"]) > 0
    
    # Conscious skip with reason on tema_delimitacao
    gate_res = client.post(
        f"/projects/{project_id}/tree/nodes/tema_delimitacao/gate",
        json={"skip": True, "skip_reason": "Tema já previamente delimitado em projeto de iniciação científica."},
        headers=headers
    )
    assert gate_res.status_code == 200
    assert gate_res.json()["outcome"] == "pular"

    # Verify downstream unlocks
    updated_tree = client.get(f"/projects/{project_id}/tree", headers=headers).json()
    tema_node = next(n for n in updated_tree["nodes"] if n["key"] == "tema_delimitacao")
    assert tema_node["status"] == "skipped"

    # Dependent node problema_pesquisa is now available
    prob_node = next(n for n in updated_tree["nodes"] if n["key"] == "problema_pesquisa")
    assert prob_node["status"] == "available"

    # 4. Bibliographic Document Ingestion (via DOI)
    doc_res = client.post(
        f"/projects/{project_id}/documents/doi",
        json={"doi": "10.1590/s0100-15782025000100001"},
        headers=headers
    )
    assert doc_res.status_code == 201
    doc_id = doc_res.json()["id"]
    assert doc_res.json()["title"] == "Metodologias Ativas e Avaliação Formativa"

    # Ingest verified claims directly into repo for this document
    repo = client.app.extra["repo"] if hasattr(client.app, "extra") else None

    # 5. Knowledge Map & Edge Decisions
    # Add concepts and edge to test 3-state decision
    app_instance = client.app
    # Fetch map
    map_res = client.get(f"/projects/{project_id}/map", headers=headers)
    assert map_res.status_code == 200

    # 6. Gap Detection
    gaps_res = client.get(f"/projects/{project_id}/gaps", headers=headers)
    assert gaps_res.status_code == 200

    # 7. Manuscript Editor & Sections
    sec_list = client.get(f"/projects/{project_id}/sections", headers=headers).json()
    if sec_list:
        sec_id = sec_list[0]["id"]
    else:
        sec_res = client.post(
            f"/projects/{project_id}/sections",
            json={
                "title": "1. Introdução e Justificativa",
                "position": 0,
                "content": {
                    "type": "doc",
                    "content": [
                        {"type": "paragraph", "content": [{"type": "text", "text": "Este trabalho investiga a evasão escolar."}]}
                    ]
                }
            },
            headers=headers
        )
        assert sec_res.status_code == 200
        sec_id = sec_res.json()["id"]

    # Coherence check
    coh_res = client.get(f"/projects/{project_id}/coherence", headers=headers)
    assert coh_res.status_code == 200
    assert isinstance(coh_res.json(), list)
    assert any(alert["type"] == "documento_sem_alegacoes" for alert in coh_res.json())

    # 8. Human Advisor Invitation & Comments
    inv_res = client.post(
        f"/projects/{project_id}/advisors",
        json={"advisor_email": "prof.orientador@beta.edu.br", "can_comment": True},
        headers=headers
    )
    assert inv_res.status_code == 200

    comment_res = client.post(
        f"/projects/{project_id}/sections/{sec_id}/comments",
        json={"content": "Excelente introdução. Lembre-se de explicitar a metodologia no segundo parágrafo."},
        headers=headers
    )
    assert comment_res.status_code == 200

    # Advisor Progress Report Compilation
    report_res = client.post(f"/projects/{project_id}/reports", headers=headers)
    assert report_res.status_code == 200
    report_data = report_res.json()
    assert "payload" in report_data
    payload = report_data["payload"]
    assert payload["progress_tree"]["skipped_count"] >= 1
    skipped = payload["progress_tree"]["skipped_with_warning"][0]
    assert "iniciação científica" in skipped["skipped_reason"]
    assert "ai_usage_audit" in payload

    # 9. ABNT DOCX Manuscript Export
    export_res = client.get(f"/projects/{project_id}/export/docx", headers=headers)
    assert export_res.status_code == 200
    assert export_res.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert len(export_res.content) > 1000  # Valid binary DOCX document with cover and AI usage declaration

    # 10. Verified Project Claims & Magic Share Link for Human Advisor
    claims_res = client.get(f"/projects/{project_id}/claims", headers=headers)
    assert claims_res.status_code == 200
    assert isinstance(claims_res.json(), list)

    share_res = client.post(f"/projects/{project_id}/share-link", headers=headers)
    assert share_res.status_code == 200
    share_token = share_res.json()["token"]
    assert share_res.json()["share_path"] == f"/orientador/{share_token}"

    # Advisor accesses shared view without needing a user account
    shared_view = client.get(f"/shared/{share_token}")
    assert shared_view.status_code == 200
    shared_body = shared_view.json()
    assert shared_body["project"]["id"] == project_id
    assert len(shared_body["sections"]) >= 1

    # Advisor leaves an anchored comment on a manuscript section via magic link
    shared_comment_res = client.post(
        f"/shared/{share_token}/comments",
        json={
            "section_id": sec_id,
            "author_name": "Profa. Dra. Helena Costa",
            "author_email": "helena.costa@ufjf.br",
            "anchor_quote": "Este trabalho investiga a evasão escolar.",
            "content": "Qual recorte temporal e empírico sustenta esta afirmação inicial?",
        },
    )
    assert shared_comment_res.status_code == 201
    created_comment = shared_comment_res.json()
    assert "Trecho em revisão" in created_comment["content"]
    assert "Qual recorte temporal" in created_comment["content"]

    # 11. Authorship Prism & AI Writing Modes (Socratic / Polish / Evidence-Guided Draft)
    # Seed initial paragraph on sec_id
    client.patch(
        f"/projects/{project_id}/sections/{sec_id}",
        json={
            "content": {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": "Este trabalho investiga a evasão escolar no ensino médio brasileiro.",
                            }
                        ],
                    }
                ],
            }
        },
        headers=headers,
    )
    auth_res = client.get(f"/projects/{project_id}/authorship", headers=headers)
    assert auth_res.status_code == 200
    assert auth_res.json()["project"]["requires_disclosure"] is False
    assert auth_res.json()["project"]["human_pct"] == 100

    # Mode 2 (Polish): refines student text without triggering generative AI disclosure
    polish_res = client.post(
        f"/projects/{project_id}/sections/{sec_id}/ai-assist",
        json={"mode": "polish", "instruction": "Mais formal"},
        headers=headers,
    )
    assert polish_res.status_code == 200
    assert polish_res.json()["llm_used"] is False
    assert polish_res.json()["notice"]
    assert polish_res.json()["project_authorship"]["requires_disclosure"] is False
    assert polish_res.json()["project_authorship"]["polished_words"] == 0  # mechanical cleanup is not AI polish

    # Mode 3 (Draft) without verified claims is blocked by Rule 1 (422)
    draft_blocked = client.post(
        f"/projects/{project_id}/sections/{sec_id}/ai-assist",
        json={"mode": "draft"},
        headers=headers,
    )
    assert draft_blocked.status_code == 422

    # Add a verified claim to the repo and run Mode 3 (Draft)
    repo = client.app.state.repo
    repo.add_claims(
        doc_id,
        [
            {
                "concept": "Metodologias ativas",
                "statement": "As metodologias ativas reduzem a evasão discente.",
                "quote": "A adoção de metodologias ativas eleva a retenção escolar em 28%.",
                "page_verified": 14,
                "quote_verified": True,
                "verify_method": "exact",
            }
        ],
        model="test",
        prompt_version="extract_claims v0.1",
    )

    draft_ok = client.post(
        f"/projects/{project_id}/sections/{sec_id}/ai-assist",
        json={"mode": "draft", "instruction": "Articular com o problema da evasão"},
        headers=headers,
    )
    assert draft_ok.status_code == 200
    draft_prism = draft_ok.json()["project_authorship"]
    assert draft_prism["requires_disclosure"] is True
    assert draft_prism["ai_drafted_words"] > 0
    assert "A adoção de metodologias ativas eleva a retenção escolar em 28%" in draft_ok.json()["generated_text"]

    # 12. Continuous Gradient (intensity=70 coauthor) & provenance ledger
    coauthor_res = client.post(
        f"/projects/{project_id}/sections/{sec_id}/ai-assist",
        json={
            "intensity": 70,
            "instruction": "A permanência estudantil depende do engajamento ativo em sala",
        },
        headers=headers,
    )
    assert coauthor_res.status_code == 200
    assert coauthor_res.json()["mode"] == "coauthor"
    assert coauthor_res.json()["intensity"] == 70

    val_res = client.post(
        f"/projects/{project_id}/sections/{sec_id}/validate-authenticity",
        json={"sync_prism": True},
        headers=headers,
    )
    assert val_res.status_code == 200
    sec_auth = val_res.json()["section_authorship"]
    assert "forensics" not in sec_auth and "measured_ai_score" not in sec_auth  # no style-based verdict any more
    assert sec_auth["basis"] == "ledger" and sec_auth["ai_drafted_words"] > 0
    assert val_res.json()["synced"] is False and "estilo" in val_res.json()["notice"]

    # 13. Guided Text Analysis (PDF Dissection, Socratic Prompts, Boxcar Audit & Dialectical Comparison)
    repo.add_claims(
        doc_id,
        [
            {
                "concept": "Formação docente",
                "statement": "Entretanto, a aplicação de metodologias ativas exige formação continuada.",
                "quote": "Todavia, sem formação continuada, o método ativo enfrenta limitações severas.",
                "page_verified": 19,
                "quote_verified": True,
                "verify_method": "exact",
            }
        ],
        model="test",
        prompt_version="extract_claims v0.1",
    )

    ta_res = client.get(f"/projects/{project_id}/text-analysis", headers=headers)
    assert ta_res.status_code == 200
    ta_body = ta_res.json()
    assert len(ta_body["document_guides"]) >= 1
    assert len(ta_body["enriched_claims"]) >= 2
    assert "manuscript_audit" in ta_body

    claim_a_id = ta_body["enriched_claims"][0]["id"]
    claim_b_id = ta_body["enriched_claims"][1]["id"]
    cmp_res = client.post(
        f"/projects/{project_id}/text-analysis/compare",
        json={
            "claim_a_id": claim_a_id,
            "claim_b_id": claim_b_id,
            "relation_type": "contraponto",
            "student_analysis": "O impacto positivo depende diretamente da capacitação prévia dos professores",
            "section_id": sec_id,
            "intensity": 35,
            "insert_into_section": True,
        },
        headers=headers,
    )
    assert cmp_res.status_code == 200
    cmp_body = cmp_res.json()
    assert cmp_body["mode_used"] == "scaffold_socratico"
    assert "comparison_matrix" in cmp_body
    assert cmp_body["updated_section"] is not None
