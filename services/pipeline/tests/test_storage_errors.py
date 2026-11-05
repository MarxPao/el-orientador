"""Local storage (safe keys, atomic writes, checksums) and the local error log (no external tracker)."""
import hashlib
import os
import sys
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-with-enough-length-32bytes")
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import errors, repo as repo_mod, storage  # noqa: E402
from app.jobs import InlineQueue  # noqa: E402
from app.main import create_app  # noqa: E402
from app.repo import InMemoryRepo  # noqa: E402

DSN = os.environ.get("TEST_DATABASE_URL")
PG_OK = bool(DSN) and "test" in (DSN or "").rsplit("/", 1)[-1].split("?")[0].lower()


# ----------------------------------------------------------------------------- storage module
def test_write_is_atomic_and_returns_checksum(tmp_path):
    data = b"%PDF-1.4 conteudo" * 1000
    digest = storage.write_atomic(tmp_path, "p1/a.pdf", data)
    assert digest == hashlib.sha256(data).hexdigest()
    assert (tmp_path / "p1" / "a.pdf").read_bytes() == data
    assert storage.manifest(tmp_path) == {"p1/a.pdf": digest}
    assert not [p for p in tmp_path.rglob(".tmp-*")]  # no temporary file left behind


def test_failed_write_leaves_no_partial_file(tmp_path, monkeypatch):
    storage.write_atomic(tmp_path, "p1/a.pdf", b"original")

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(storage.os, "replace", boom)
    with pytest.raises(OSError):
        storage.write_atomic(tmp_path, "p1/a.pdf", b"novo conteudo")
    assert (tmp_path / "p1" / "a.pdf").read_bytes() == b"original"  # the old file is intact
    assert not [p for p in tmp_path.rglob(".tmp-*")]


@pytest.mark.parametrize("key", ["../fora.pdf", "/etc/passwd", "p1/../../fora.pdf", "", ".", "a\x00b"])
def test_keys_outside_the_root_are_refused(tmp_path, key):
    root = tmp_path / "st"
    root.mkdir()
    with pytest.raises(storage.StorageError):
        storage.resolve(root, key)
    assert storage.delete(root, key) is False
    assert storage.exists(root, key) is False


def test_symlink_pointing_outside_is_refused(tmp_path):
    root = tmp_path / "st"
    root.mkdir()
    outside = tmp_path / "segredo.txt"
    outside.write_text("x")
    (root / "link.pdf").symlink_to(outside)
    with pytest.raises(storage.StorageError):
        storage.resolve(root, "link.pdf")
    assert outside.exists()


def test_delete_only_removes_inside_files(tmp_path):
    root = tmp_path / "st"
    storage.write_atomic(root, "p/a.pdf", b"x")
    assert storage.delete(root, "p/a.pdf") is True
    assert storage.delete(root, "p/a.pdf") is False


# ----------------------------------------------------------------------------- API uses it
def _pdf(path: Path) -> bytes:
    d = pymupdf.open()
    d.new_page().insert_textbox(pymupdf.Rect(50, 50, 545, 790), "Texto de teste sobre evasão escolar. " * 8)
    d.save(path)
    return path.read_bytes()


def _env(tmp_path, repo=None):
    repo = repo or InMemoryRepo()
    st = tmp_path / "st"
    fac = lambda: None  # noqa: E731
    app = create_app(repo=repo, storage_dir=st, llm_factory=fac, client=None, job_queue=InlineQueue(repo, st, fac))
    c = TestClient(app)
    tok = c.post("/auth/register", json={"email": "a@usp.br", "password": "password123", "name": "Ana"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    pid = c.post("/projects", json={"title": "Projeto Teste", "work": "tcc", "citation_style": "abnt"}, headers=h).json()["id"]
    return c, repo, h, pid, st


def test_upload_serve_delete_roundtrip(tmp_path):
    c, repo, h, pid, st = _env(tmp_path)
    pdf = _pdf(tmp_path / "x.pdf")
    r = c.post(f"/projects/{pid}/documents/upload", headers=h, data={"title": "Doc"},
               files={"file": ("x.pdf", pdf, "application/pdf")})
    assert r.status_code in (200, 201), r.text
    doc = r.json()
    assert storage.manifest(st)[doc["storage_path"]] == hashlib.sha256(pdf).hexdigest()
    got = c.get(f"/projects/{pid}/documents/{doc['id']}/file", headers=h)
    assert got.status_code == 200 and got.content == pdf
    assert c.delete(f"/projects/{pid}/documents/{doc['id']}", headers=h).status_code == 200
    assert storage.manifest(st) == {}


def test_crafted_storage_path_cannot_read_or_delete_outside(tmp_path):
    c, repo, h, pid, st = _env(tmp_path)
    secret = tmp_path / "segredo.pdf"
    secret.write_bytes(b"nao pode vazar")
    d = repo.create_document(pid, {"title": "Mal", "storage_path": "../segredo.pdf", "analysis": "full_text",
                                   "status": "extracted"})
    assert c.get(f"/projects/{pid}/documents/{d['id']}/file", headers=h).status_code == 404
    assert c.delete(f"/projects/{pid}/documents/{d['id']}", headers=h).status_code == 200
    assert secret.exists()


# ----------------------------------------------------------------------------- error log
def test_scrub_masks_secrets():
    s = errors.scrub("fail postgresql://orientador:senha123@db:5432/x Authorization: Bearer abc.def.ghi api_key=XYZ")
    assert "senha123" not in s and "abc.def.ghi" not in s and "XYZ" not in s
    assert "postgresql://orientador:***@db" in s


@pytest.fixture(params=["memory", "postgres"])
def err_repo(request):
    if request.param == "postgres":
        if not PG_OK:
            pytest.skip("TEST_DATABASE_URL not set to a *test* database")
        import psycopg

        with psycopg.connect(DSN) as c:
            c.execute("TRUNCATE users CASCADE")
            c.execute("TRUNCATE error_events")
        return repo_mod.PostgresRepo(DSN)
    return InMemoryRepo()


def test_unexpected_error_is_recorded_with_request_id(tmp_path, err_repo, monkeypatch):
    c, repo, h, pid, st = _env(tmp_path, err_repo)

    def boom(*a, **k):
        raise RuntimeError("falha em postgresql://u:topsecret@h/db")

    monkeypatch.setattr(repo, "list_projects", boom)
    r = c.get("/projects", headers=h)
    assert r.status_code == 500
    rid = r.headers["X-Request-ID"]
    assert r.json()["request_id"] == rid and rid in r.json()["detail"]
    ev = repo.list_error_events()
    assert len(ev) == 1 and ev[0]["request_id"] == rid and ev[0]["error_type"] == "RuntimeError"
    assert ev[0]["route"] == "GET /projects" and ev[0]["source"] == "api"
    assert "topsecret" not in ev[0]["message"] and "topsecret" not in (ev[0]["stack"] or "")


def test_normal_and_http_errors_are_not_logged(tmp_path, err_repo):
    c, repo, h, pid, st = _env(tmp_path, err_repo)
    assert c.get("/health").headers["X-Request-ID"]
    assert c.get("/projects/00000000-0000-0000-0000-000000000000/documents", headers=h).status_code in (403, 404)
    assert repo.list_error_events() == []


def test_admin_endpoint_is_closed_unless_listed(tmp_path, err_repo, monkeypatch):
    c, repo, h, pid, st = _env(tmp_path, err_repo)
    repo.add_error_event("api", "X", "m", None, "GET /x", "rid1", None)
    monkeypatch.delenv("ADMIN_EMAILS", raising=False)
    assert c.get("/admin/errors", headers=h).status_code == 403
    assert c.get("/admin/errors").status_code == 401
    monkeypatch.setenv("ADMIN_EMAILS", "outra@x.com, A@usp.br")
    r = c.get("/admin/errors", headers=h)
    assert r.status_code == 200 and r.json()["errors"][0]["request_id"] == "rid1"


def test_purge_removes_only_old_rows(err_repo):
    old = err_repo.add_error_event("api", "Old", "m", None, None, "old", None)
    err_repo.add_error_event("api", "New", "m", None, None, "new", None)
    if isinstance(err_repo, InMemoryRepo):
        err_repo.error_events[0]["created_at"] = "2000-01-01T00:00:00+00:00"
    else:
        with err_repo._conn() as c:
            c.execute("UPDATE error_events SET created_at = now() - interval '90 days' WHERE id = %s::uuid", (old["id"],))
    assert err_repo.purge_error_events(30) == 1
    assert [e["request_id"] for e in err_repo.list_error_events()] == ["new"]


def test_record_never_raises_when_the_log_is_down():
    class Broken:
        def add_error_event(self, *a):
            raise RuntimeError("db down")

    assert errors.record(Broken(), "api", ValueError("x")) is None
