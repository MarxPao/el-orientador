import os
import sys
from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-with-enough-length-32bytes")
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import create_app
from app.repo import InMemoryRepo
from app.schedule import calculate_schedule, parse_typical_weeks
from app.tree import load_template


def test_parse_typical_weeks():
    assert parse_typical_weeks("1 semana") == (1.0, 1.0, 1.0)
    assert parse_typical_weeks("2 semanas") == (2.0, 2.0, 2.0)
    assert parse_typical_weeks("1 a 2 semanas") == (1.0, 2.0, 1.5)
    assert parse_typical_weeks("3 a 5 semanas") == (3.0, 5.0, 4.0)


def test_schedule_on_track():
    template = load_template("tcc")
    # All nodes initially available/locked
    nodes_state = [{"node_key": n["key"], "status": "locked", "queued": False} for n in template["nodes"]]
    # Far away deadline (2 years)
    deadline = (date.today() + timedelta(days=700)).isoformat()
    res = calculate_schedule(template, nodes_state, weekly_hours=15, deadline=deadline)

    assert res["is_at_risk"] is False
    assert res["weekly_hours"] == 15
    assert "dentro do prazo" in res["alert"]
    assert res["total_estimated_weeks"] > 0
    assert len(res["items"]) == len(template["nodes"])


def test_schedule_at_risk_calculates_suggested_hours():
    template = load_template("tcc")
    nodes_state = [{"node_key": n["key"], "status": "locked", "queued": False} for n in template["nodes"]]
    # Very short deadline (30 days ~ 4 weeks) for ~25 weeks of work at 5h/wk
    deadline = (date.today() + timedelta(days=30)).isoformat()
    res = calculate_schedule(template, nodes_state, weekly_hours=5, deadline=deadline)

    assert res["is_at_risk"] is True
    assert "ultrapassando o prazo" in res["alert"]
    assert res["suggested_weekly_hours"] is not None
    assert res["suggested_weekly_hours"] > 5


def test_schedule_api_endpoint():
    repo = InMemoryRepo()
    app = create_app(repo=repo)
    c = TestClient(app)

    # Register & create project
    r_reg = c.post("/auth/register", json={"email": "cronograma@usp.br", "password": "password123", "name": "Aluno"})
    token = r_reg.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    deadline = (date.today() + timedelta(days=180)).isoformat()
    p = c.post(
        "/projects",
        json={"title": "TCC Cronograma", "work": "tcc", "weekly_hours": 12, "deadline": deadline},
        headers=headers,
    ).json()

    pid = p["id"]
    r = c.get(f"/projects/{pid}/schedule", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["weekly_hours"] == 12
    assert data["deadline"] == deadline
    assert len(data["items"]) > 0
    assert "alert" in data
