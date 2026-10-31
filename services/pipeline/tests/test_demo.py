import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-with-enough-length-32bytes")
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.demo import DEMO_EMAIL, DEMO_PASSWORD, seed_demo  # noqa: E402
from app.main import create_app  # noqa: E402
from app.repo import InMemoryRepo  # noqa: E402


class NoQueue:
    def enqueue(self, document_id):
        pass


def test_demo_seed_gives_a_clickable_map_with_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_SEED", "1")
    client = TestClient(create_app(InMemoryRepo(), storage_dir=tmp_path / "st", job_queue=NoQueue()))
    token = client.post("/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    pid = client.get("/projects", headers=h).json()[0]["id"]
    m = client.get(f"/projects/{pid}/map", headers=h).json()
    assert len(m["nodes"]) == 3 and {e["status"] for e in m["edges"]} == {"suggested", "confirmed"}
    ev = client.get(f"/projects/{pid}/edges/{m['edges'][0]['id']}/evidence", headers=h).json()
    assert all(e["page"] == 1 and e["quote"] for e in ev)
    assert client.get(f"/projects/{pid}/documents/{ev[0]['document_id']}/file", headers=h).content.startswith(b"%PDF-")


def test_seed_is_idempotent_and_off_by_default(tmp_path, monkeypatch):
    repo = InMemoryRepo()
    seed_demo(repo, tmp_path)
    seed_demo(repo, tmp_path)
    assert len(repo.users) == 1
    monkeypatch.delenv("DEMO_SEED", raising=False)
    other = InMemoryRepo()
    create_app(other, storage_dir=tmp_path, job_queue=NoQueue())
    assert other.users == {}
