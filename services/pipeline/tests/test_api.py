import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-with-enough-length-32bytes")
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.main import create_app  # noqa: E402
from app.repo import InMemoryRepo  # noqa: E402
from app.security import create_token, hash_password, verify_password  # noqa: E402

PROJECT = {"title": "Aprendizagem significativa no ensino mÃ©dio", "work": "tcc", "institution": "UFX",
           "deadline": "2027-06-30", "weekly_hours": 10}


@pytest.fixture
def client():
    return TestClient(create_app(InMemoryRepo()))


def register(client, email="ana@exemplo.com", password="senha-segura-1"):
    r = client.post("/auth/register", json={"email": email, "password": password, "name": "Ana"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_password_hash_roundtrip():
    h = hash_password("abc12345")
    assert "abc12345" not in h and verify_password("abc12345", h) and not verify_password("outra", h)


def test_register_then_login_then_me(client):
    register(client)
    r = client.post("/auth/login", json={"email": "ANA@exemplo.com", "password": "senha-segura-1"})
    assert r.status_code == 200
    me = client.get("/me", headers={"Authorization": f"Bearer {r.json()['token']}"})
    assert me.json()["email"] == "ana@exemplo.com" and "password_hash" not in me.json()


def test_duplicate_email_and_short_password(client):
    register(client)
    assert client.post("/auth/register", json={"email": "ana@exemplo.com", "password": "senha-segura-1"}).status_code == 409
    assert client.post("/auth/register", json={"email": "b@exemplo.com", "password": "curta"}).status_code == 422


def test_login_failures_share_one_message(client):
    register(client)
    wrong = client.post("/auth/login", json={"email": "ana@exemplo.com", "password": "errada-123"})
    unknown = client.post("/auth/login", json={"email": "x@exemplo.com", "password": "errada-123"})
    assert wrong.status_code == unknown.status_code == 401 and wrong.json() == unknown.json()


def test_projects_require_auth(client):
    assert client.post("/projects", json=PROJECT).status_code == 401
    assert client.get("/projects", headers={"Authorization": "Bearer lixo"}).status_code == 401
    assert client.get("/projects", headers={"Authorization": f"Bearer {create_token('nao-existe')}"}).status_code == 401


def test_create_and_list_project(client):
    h = register(client)
    r = client.post("/projects", json=PROJECT, headers=h)
    assert r.status_code == 201 and r.json()["citation_style"] == "abnt" and r.json()["work"] == "tcc"
    assert [p["id"] for p in client.get("/projects", headers=h).json()] == [r.json()["id"]]


def test_invalid_project_is_rejected(client):
    h = register(client)
    assert client.post("/projects", json={**PROJECT, "work": "romance"}, headers=h).status_code == 422
    assert client.post("/projects", json={**PROJECT, "title": "ab"}, headers=h).status_code == 422


def test_projects_are_isolated_between_users(client):
    a = register(client)
    b = register(client, email="bia@exemplo.com")
    pid = client.post("/projects", json=PROJECT, headers=a).json()["id"]
    assert client.get("/projects", headers=b).json() == []
    assert client.get(f"/projects/{pid}", headers=b).status_code == 404
    assert client.get(f"/projects/{pid}", headers=a).status_code == 200


def test_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["app"] == "El Orientador"


def test_cookie_authentication_and_logout(client):
    # Register sets cookie when requested via X-Auth-Cookie
    r = client.post(
        "/auth/register",
        json={"email": "cookie_user@exemplo.com", "password": "senha-segura-1", "name": "Cookie User"},
        headers={"X-Auth-Cookie": "1"}
    )
    assert r.status_code == 201
    assert "orientador_token" in r.cookies

    # Calling /me without Authorization header uses cookie
    me = client.get("/me")
    assert me.status_code == 200
    assert me.json()["email"] == "cookie_user@exemplo.com"

    # Logout clears the cookie
    logout_res = client.post("/auth/logout")
    assert logout_res.status_code == 200
    assert client.get("/me").status_code == 401


def test_beta_metrics_endpoint(client):
    h = register(client, email="metrics_user@exemplo.com")
    r = client.get("/beta-metrics", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert "students_registered" in data
    assert "activation" in data
    assert "knowledge_map" in data
    assert "socratic_gate" in data
    assert data["activation"]["threshold_sources"] == 5
    assert data["knowledge_map"]["target_acceptance_rate"] == 0.50
