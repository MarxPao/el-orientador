"""Phase 1 against a REAL Postgres. Runs only when TEST_DATABASE_URL points at a database that has
db/schema.sql applied (the same convention as PostgresRepo). Example:
    TEST_DATABASE_URL=postgresql://user@localhost:5432/orientador_test pytest tests/test_pg_queue.py
"""
import os
import sys
import threading
import time
from pathlib import Path

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret-with-enough-length-32bytes")
sys.path.insert(0, str(Path(__file__).parent.parent))

DSN = os.environ.get("TEST_DATABASE_URL")
# These tests TRUNCATE tables: refuse to run unless the database name says it is a test database.
_DB_NAME = (DSN or "").rsplit("/", 1)[-1].split("?")[0].lower()
pytestmark = pytest.mark.skipif(
    not DSN or "test" not in _DB_NAME,
    reason="set TEST_DATABASE_URL to a database whose name contains 'test' (the suite truncates tables)",
)

if DSN:
    import psycopg

    from app.pgqueue import Job, LeaseLost, PgJobQueue
    from app.repo import PostgresRepo

from tests.test_pipeline_stages import SENTENCE, OneClaimLLM, make_mixed_pdf  # noqa: E402


@pytest.fixture()
def env(tmp_path):
    repo = PostgresRepo(DSN)
    with psycopg.connect(DSN) as c:
        c.execute("TRUNCATE jobs, users CASCADE")
    user = repo.create_user("pg@exemplo.com", "PG", "hash")
    project = repo.create_project(user["id"], {"title": "Projeto PG", "work": "tcc", "citation_style": "abnt"})
    storage = tmp_path / "st"
    (storage / "p").mkdir(parents=True)
    return repo, project["id"], storage


def new_doc(repo, project_id, storage, kinds=("text",), name="a.pdf"):
    make_mixed_pdf(storage / "p" / name, list(kinds))
    return repo.create_document(project_id, {"title": "Artigo", "year": 2020, "storage_path": f"p/{name}"})["id"]


def job_rows(stage=None):
    with psycopg.connect(DSN) as c:
        return c.execute("SELECT stage, status, attempts, last_error FROM jobs ORDER BY id").fetchall()


def test_enqueue_is_deduplicated_while_active(env):
    repo, pid, storage = env
    doc = new_doc(repo, pid, storage)
    q = PgJobQueue(DSN)
    q.enqueue(doc)
    q.enqueue(doc)
    assert len(job_rows()) == 1


def test_many_workers_never_take_the_same_job(env):
    repo, pid, storage = env
    docs = [new_doc(repo, pid, storage, name=f"{i}.pdf") for i in range(12)]
    q = PgJobQueue(DSN)
    for d in docs:
        q.enqueue(d)
    claimed, lock = [], threading.Lock()

    def worker(n):
        w = PgJobQueue(DSN, worker_id=f"w{n}")
        deadline = time.time() + 20
        while time.time() < deadline:
            with lock:
                if len(claimed) >= len(docs):
                    return
            # SKIP LOCKED can return nothing while the remaining rows are momentarily locked by another worker
            # (that is how a real worker loop works too: it polls again), so an empty claim is not the end
            if job := w.claim():
                with lock:
                    claimed.append(job.id)
            else:
                time.sleep(0.01)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(claimed) == 12 and len(set(claimed)) == 12


def test_full_pipeline_through_postgres_with_ocr(env):
    repo, pid, storage = env
    doc = new_doc(repo, pid, storage, kinds=("scan", "text"))
    q = PgJobQueue(DSN)
    q.enqueue(doc)
    factory = lambda: OneClaimLLM()  # noqa: E731
    assert q.run_once(repo, storage, factory) is True  # parse (+ OCR) -> enqueues index
    d = repo.get_document(doc)
    assert d["status"] == "parsed" and d["progress"]["ocr_pages"] == 1
    assert q.run_once(repo, storage, factory) is True  # index: chunks for search (this LLM cannot embed)
    assert repo.chunk_stats(pid, None)["chunks"] >= 1
    assert q.run_once(repo, storage, factory) is True  # extract -> enqueues summarize
    assert q.run_once(repo, storage, factory) is True  # summarize (disabled in tests: a no-op)
    assert q.run_once(repo, storage, factory) is False  # queue drained
    d = repo.get_document(doc)
    assert d["status"] == "extracted" and d["stage"] is None and d["progress"]["ocr_pages"] == 1
    assert [r[:2] for r in job_rows()] == [("parse", "done"), ("index", "done"), ("extract", "done"),
                                           ("summarize", "done")]
    claims = repo.list_claims(doc)
    assert len(claims) == 1 and claims[0]["quote"] == SENTENCE
    assert len(repo.get_pages(doc)) == 2


def test_crashed_worker_job_is_recovered_by_another_worker(env):
    repo, pid, storage = env
    doc = new_doc(repo, pid, storage)
    PgJobQueue(DSN).enqueue(doc)
    dying = PgJobQueue(DSN, worker_id="dies")
    job = dying.claim()  # claimed... and the process is killed here: never completes
    assert job and job.attempts == 1
    assert PgJobQueue(DSN, worker_id="other").claim() is None  # lease still valid: hands off
    with psycopg.connect(DSN) as c:
        c.execute("UPDATE jobs SET locked_until = now() - interval '1 second'")
    other = PgJobQueue(DSN, worker_id="other")
    assert other.run_once(repo, storage, lambda: None) is True
    assert repo.get_document(doc)["status"] == "parsed"
    assert job_rows()[0][:3] == ("parse", "done", 2)
    with pytest.raises(LeaseLost):  # the zombie wakes up and tries to report: refused
        dying.complete(job, None)


def test_heartbeat_keeps_a_slow_job_alive_and_detects_a_stolen_lease(env):
    repo, pid, storage = env
    doc = new_doc(repo, pid, storage)
    PgJobQueue(DSN).enqueue(doc)
    q = PgJobQueue(DSN, worker_id="slow", lease_seconds=60)
    job = q.claim()
    q.heartbeat(job)  # still ours
    with psycopg.connect(DSN) as c:
        c.execute("UPDATE jobs SET locked_by = 'thief'")
    with pytest.raises(LeaseLost):
        q.heartbeat(job)


def test_retry_with_backoff_then_dead_and_document_failed(env):
    repo, pid, storage = env
    doc = new_doc(repo, pid, storage)
    q = PgJobQueue(DSN, max_attempts=3)

    class Down:
        model = "down"

        def complete_json(self, *a, **k):
            raise RuntimeError("down")

    # parse works (and chains to extract); extract fails on every chunk -> retryable
    q.enqueue(doc)
    factory = lambda: Down()  # noqa: E731
    assert q.run_once(repo, storage, factory)  # parse ok
    assert q.run_once(repo, storage, factory)  # index ok
    for attempt in (1, 2, 3):
        assert q.run_once(repo, storage, factory)  # extract attempt
        status, attempts, err = [(r[1], r[2], r[3]) for r in job_rows() if r[0] == "extract"][0]
        if attempt < 3:
            assert (status, attempts) == ("queued", attempt) and err == "RetryableJobError"
            assert q.run_once(repo, storage, factory) is False  # backoff: not claimable yet
            with psycopg.connect(DSN) as c:
                c.execute("UPDATE jobs SET run_after = now() WHERE status = 'queued'")
    assert (status, attempts) == ("dead", 3)
    assert repo.get_document(doc)["status"] == "failed"


def test_worker_that_dies_on_the_last_attempt_is_reaped(env):
    repo, pid, storage = env
    doc = new_doc(repo, pid, storage)
    q = PgJobQueue(DSN, max_attempts=1)
    q.enqueue(doc)
    q.claim()
    with psycopg.connect(DSN) as c:
        c.execute("UPDATE jobs SET locked_until = now() - interval '1 second'")
    assert PgJobQueue(DSN).run_once(repo, storage, lambda: None) is False
    assert job_rows()[0][1] == "dead" and repo.get_document(doc)["status"] == "failed"


def test_corrupt_pdf_is_permanent_failure_without_retries(env):
    repo, pid, storage = env
    (storage / "p" / "bad.pdf").write_bytes(b"%PDF-1.4 broken")
    doc = repo.create_document(pid, {"title": "x", "storage_path": "p/bad.pdf"})["id"]
    q = PgJobQueue(DSN)
    q.enqueue(doc)
    assert q.run_once(repo, storage, lambda: None)
    assert repo.get_document(doc)["status"] == "failed"
    assert job_rows()[0][1:3] == ("done", 1)  # no pointless retries on a corrupt file


def test_run_forever_processes_and_stops(env):
    repo, pid, storage = env
    doc = new_doc(repo, pid, storage)
    q = PgJobQueue(DSN)
    q.enqueue(doc)
    stop = threading.Event()
    t = threading.Thread(target=q.run_forever, args=(repo, storage, lambda: None, stop, 0.05))
    t.start()
    deadline = time.time() + 10
    while time.time() < deadline and repo.get_document(doc)["status"] != "parsed":
        time.sleep(0.05)
    stop.set()
    t.join(timeout=5)
    assert repo.get_document(doc)["status"] == "parsed" and not t.is_alive()
