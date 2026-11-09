"""Tests for Multi-Advisee Cohort Dashboard and Academic Coordination (T7.4)."""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient

from services.pipeline.app.cohort import (
    compute_cohort_dashboard,
    compute_student_overview,
    export_cohort_summary_csv,
    export_cohort_summary_markdown,
)
from services.pipeline.app.main import create_app
from services.pipeline.app.repo import InMemoryRepo
from services.pipeline.app.security import hash_password, create_token
from services.pipeline.app.tree import initial_nodes, load_template


def _setup_test_cohort(repo: InMemoryRepo):
    advisor = repo.create_user("prof.silva@universidade.br", "Prof. Silva", hash_password("senha123"))

    # Student 1: TCC, comfortable deadline (200 days), 2 done, 0 skipped -> on track
    s1 = repo.create_user("aluno1@universidade.br", "Mariana Silva", hash_password("senha123"))
    p1 = repo.create_project(s1["id"], {
        "title": "TCC sobre Redes Neurais",
        "work": "tcc",
        "institution": "UFMG",
        "deadline": (date.today() + timedelta(days=200)).isoformat(),
        "weekly_hours": 15,
    })
    repo.invite_advisor(p1["id"], advisor["email"], True)
    tmpl1 = load_template("tcc")
    repo.save_progress_nodes(p1["id"], initial_nodes(tmpl1))
    repo.update_progress_node(p1["id"], "tema_delimitacao", status="done")
    repo.update_progress_node(p1["id"], "problema_pesquisa", status="done")

    # Student 2: Dissertação, critical deadline (10 days), 1 done, 1 skipped with conscious warning
    s2 = repo.create_user("aluno2@universidade.br", "Carlos Mendes", hash_password("senha123"))
    p2 = repo.create_project(s2["id"], {
        "title": "Dissertação sobre Ética e IA",
        "work": "tcc",
        "institution": "USP",
        "deadline": (date.today() + timedelta(days=10)).isoformat(),
        "weekly_hours": 8,
    })
    repo.invite_advisor(p2["id"], advisor["email"], True)
    repo.save_progress_nodes(p2["id"], initial_nodes(tmpl1))
    repo.update_progress_node(p2["id"], "tema_delimitacao", status="done")
    repo.update_progress_node(p2["id"], "problema_pesquisa", status="skipped", skipped_reason="Problema previamente validado no edital")

    # Add section with unresolved comment for Student 2
    sec = repo.create_section(p2["id"], "Introdução", None, 1)
    repo.create_section_comment(sec["id"], advisor["email"], advisor["name"], "Ajustar justificativa metodológica.")

    return advisor, [p1, p2]


def test_compute_student_overview():
    repo = InMemoryRepo()
    advisor, projects = _setup_test_cohort(repo)
    p2 = projects[1]

    overview = compute_student_overview(repo, p2)

    assert overview["project_id"] == p2["id"]
    assert overview["student"]["name"] == "Carlos Mendes"
    assert overview["student"]["email"] == "aluno2@universidade.br"
    assert overview["progress"]["done_nodes"] == 1
    assert overview["progress"]["skipped_count"] == 1
    assert overview["progress"]["skipped_steps"][0]["node_key"] == "problema_pesquisa"
    assert "previamente validado" in overview["progress"]["skipped_steps"][0]["reason"]
    assert overview["schedule"]["days_until_deadline"] == 10
    assert overview["schedule"]["risk_level"] == "critical"
    assert overview["governance"]["unresolved_comments_count"] == 1


def test_compute_cohort_dashboard():
    repo = InMemoryRepo()
    advisor, projects = _setup_test_cohort(repo)

    dashboard = compute_cohort_dashboard(repo, advisor["email"])

    assert dashboard["advisor_email"] == advisor["email"]
    metrics = dashboard["metrics"]
    assert metrics["total_advisees"] == 2
    assert metrics["at_risk_count"] == 1
    assert metrics["total_skipped_steps"] == 1
    assert metrics["total_unresolved_comments"] == 1
    assert len(dashboard["students"]) == 2


def test_cohort_export_csv_and_markdown():
    repo = InMemoryRepo()
    advisor, _ = _setup_test_cohort(repo)
    dashboard = compute_cohort_dashboard(repo, advisor["email"])

    csv_out = export_cohort_summary_csv(dashboard)
    assert "Carlos Mendes" in csv_out
    assert "Problema previamente validado no edital" in csv_out
    assert "aluno1@universidade.br" in csv_out

    md_out = export_cohort_summary_markdown(dashboard)
    assert "# Relatório de Acompanhamento de Turma / Multi-orientandos" in md_out
    assert "Total de Orientandos:** 2" in md_out
    assert "Carlos Mendes" in md_out
    assert "Auditoria de Etapas Puladas (Avisos Conscientes)" in md_out


def test_cohort_api_endpoints():
    repo = InMemoryRepo()
    advisor, projects = _setup_test_cohort(repo)
    app = create_app(repo=repo)
    client = TestClient(app)

    token = create_token(advisor["id"])
    auth_header = {"Authorization": f"Bearer {token}"}

    # 1. Unauthenticated gets 401
    res = client.get("/advisor/cohort-summary")
    assert res.status_code == 401

    # 2. Authenticated gets summary
    res = client.get("/advisor/cohort-summary", headers=auth_header)
    assert res.status_code == 200
    data = res.json()
    assert data["metrics"]["total_advisees"] == 2
    assert len(data["students"]) == 2

    # 3. CSV export
    res_csv = client.get("/advisor/cohort-export?format=csv", headers=auth_header)
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "Carlos Mendes" in res_csv.text

    # 4. Markdown export
    res_md = client.get("/advisor/cohort-export?format=markdown", headers=auth_header)
    assert res_md.status_code == 200
    assert "text/markdown" in res_md.headers["content-type"]
    assert "Relatório de Acompanhamento de Turma" in res_md.text


def test_link_advisee_endpoint():
    repo = InMemoryRepo()
    advisor, projects = _setup_test_cohort(repo)
    app = create_app(repo=repo)
    client = TestClient(app)

    # Another advisor
    adv2 = repo.create_user("prof.costa@universidade.br", "Prof. Costa", hash_password("senha123"))
    token2 = create_token(adv2["id"])
    auth_header = {"Authorization": f"Bearer {token2}"}

    # Initially adv2 has 0 advisees
    res = client.get("/advisor/cohort-summary", headers=auth_header)
    assert res.json()["metrics"]["total_advisees"] == 0

    # Link p1 to adv2
    link_res = client.post("/advisor/link-advisee", json={"project_id": projects[0]["id"]}, headers=auth_header)
    assert link_res.status_code == 200
    assert link_res.json()["ok"] is True

    # Now adv2 has 1 advisee
    res2 = client.get("/advisor/cohort-summary", headers=auth_header)
    assert res2.json()["metrics"]["total_advisees"] == 1
