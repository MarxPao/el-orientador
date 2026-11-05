import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-with-enough-length-32bytes")
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import create_app
from app.repo import InMemoryRepo


class ApprovingGateLLM:
    """Test double: the Socratic gate approves on the first substantive answer."""
    model = "mock-gate"

    def complete_json(self, system, user, schema):
        return {
            "message_to_student": "Delimitação clara e justificada.",
            "done": True,
            "outcome": "liberar",
            "rubric_scores": {"clareza": 2, "justificativa": 2, "coerencia": 2},
        }


def make_client(llm_client=None):
    repo = InMemoryRepo()
    app = create_app(repo=repo, client=llm_client)
    return TestClient(app), repo


def register(c, email, name):
    r = c.post("/auth/register", json={"email": email, "password": "password123", "name": name})
    assert r.status_code == 201
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_advisor_invite_and_advising_access():
    c, repo = make_client()
    student_headers = register(c, "estudante@usp.br", "Estudante")
    advisor_headers = register(c, "orientador@usp.br", "Prof. Silva")
    stranger_headers = register(c, "estranho@usp.br", "Estranho")

    # 1. Student creates project
    p = c.post("/projects", json={"title": "TCC Orientado", "work": "tcc"}, headers=student_headers).json()
    pid = p["id"]

    # 2. Student invites advisor
    r_inv = c.post(
        f"/projects/{pid}/advisors",
        json={"advisor_email": "orientador@usp.br", "can_comment": True},
        headers=student_headers,
    )
    assert r_inv.status_code == 200
    assert r_inv.json()["advisor_email"] == "orientador@usp.br"

    # 3. Advisor lists their advising projects
    r_adv_list = c.get("/advising-projects", headers=advisor_headers)
    assert r_adv_list.status_code == 200
    adv_projects = r_adv_list.json()
    assert any(proj["id"] == pid for proj in adv_projects)

    # 4. Advisor can view project tree and sections
    r_tree = c.get(f"/projects/{pid}/tree", headers=advisor_headers)
    assert r_tree.status_code == 200
    assert "phases" in r_tree.json()

    # 5. Stranger gets 404
    r_stranger = c.get(f"/projects/{pid}/tree", headers=stranger_headers)
    assert r_stranger.status_code == 404


def test_advisor_report_generation():
    c, repo = make_client(ApprovingGateLLM())
    student_headers = register(c, "estudante2@usp.br", "Estudante 2")
    p = c.post("/projects", json={"title": "TCC Relatorio", "work": "tcc"}, headers=student_headers).json()
    pid = p["id"]

    # Student completes one node and skips another
    c.post(
        f"/projects/{pid}/tree/nodes/tema_delimitacao/gate",
        json={
            "user_input": "Delimitação detalhada de visão computacional na agricultura familiar com mais de oitenta caracteres.",
            "history": [{"role": "user", "content": "início"}],
        },
        headers=student_headers,
    )
    c.post(
        f"/projects/{pid}/tree/nodes/problema_pesquisa/gate",
        json={"skip": True, "skip_reason": "Alinhado presencialmente com orientador."},
        headers=student_headers,
    )

    # Generate progress report
    r_rep = c.post(f"/projects/{pid}/reports", headers=student_headers)
    assert r_rep.status_code == 200
    rep_data = r_rep.json()
    assert "payload" in rep_data
    payload = rep_data["payload"]

    # Verify report contents
    assert payload["progress_tree"]["completed_count"] >= 1
    assert payload["progress_tree"]["skipped_count"] >= 1
    skipped = payload["progress_tree"]["skipped_with_warning"][0]
    assert "presencialmente com orientador" in skipped["skipped_reason"]
    assert "ai_usage_audit" in payload
    assert payload["ai_usage_audit"]["actions_summary"]["gate"] >= 1

    # List reports
    r_list = c.get(f"/projects/{pid}/reports", headers=student_headers)
    assert r_list.status_code == 200
    assert len(r_list.json()) == 1

    # Get single report
    rep_id = rep_data["id"]
    r_single = c.get(f"/projects/{pid}/reports/{rep_id}", headers=student_headers)
    assert r_single.status_code == 200
    assert r_single.json()["id"] == rep_id


def test_section_comments_lifecycle():
    c, repo = make_client()
    student_headers = register(c, "aluno@usp.br", "Aluno")
    advisor_headers = register(c, "prof@usp.br", "Prof")

    p = c.post("/projects", json={"title": "TCC Comentarios", "work": "tcc"}, headers=student_headers).json()
    pid = p["id"]
    c.post(f"/projects/{pid}/advisors", json={"advisor_email": "prof@usp.br"}, headers=student_headers)

    # Create sections
    sections = c.get(f"/projects/{pid}/sections", headers=student_headers).json()
    sec_id = sections[0]["id"]

    # 1. Advisor adds comment
    r_c1 = c.post(
        f"/projects/{pid}/sections/{sec_id}/comments",
        json={"content": "Excelente introdução, mas adicione uma citação direta sobre os custos operacionais."},
        headers=advisor_headers,
    )
    assert r_c1.status_code == 200
    comment = r_c1.json()
    assert comment["author_email"] == "prof@usp.br"
    assert comment["resolved"] is False

    # 2. Student lists comments
    r_list = c.get(f"/projects/{pid}/sections/{sec_id}/comments", headers=student_headers)
    assert r_list.status_code == 200
    assert len(r_list.json()) == 1

    # 3. Student resolves comment
    cid = comment["id"]
    r_patch = c.patch(
        f"/projects/{pid}/sections/{sec_id}/comments/{cid}",
        json={"resolved": True},
        headers=student_headers,
    )
    assert r_patch.status_code == 200
    assert r_patch.json()["resolved"] is True

    # 4. Delete comment
    r_del = c.delete(f"/projects/{pid}/sections/{sec_id}/comments/{cid}", headers=student_headers)
    assert r_del.status_code == 200
    assert len(c.get(f"/projects/{pid}/sections/{sec_id}/comments", headers=student_headers).json()) == 0
