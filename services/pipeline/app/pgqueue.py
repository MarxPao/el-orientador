"""Persistent job queue on Postgres (no extra infrastructure).

- `enqueue` inserts a row in `jobs`; at most one active (queued or running) job per (document, stage).
- Workers claim with `FOR UPDATE SKIP LOCKED`, so any number of workers (API-embedded or separate
  processes) can run at once and no job is taken twice.
- A claim is a lease (`locked_until`). Stages call a heartbeat as they make progress; if a worker dies,
  the lease expires and another worker picks the job up again. If it keeps dying, the job ends `dead`.
- Failures retry with exponential backoff up to `max_attempts`, then the document is marked `failed`.

Only the exception type is stored in `last_error`: never document text.
"""
from __future__ import annotations

import logging
import os
import socket
import threading
from dataclasses import dataclass
from pathlib import Path

from .jobs import STAGE_PARSE, LLMFactory, RetryableJobError, run_stage
from .repo import Repo

log = logging.getLogger("orientador.queue")

DEFAULT_LEASE_SECONDS = 300
BACKOFF_BASE_SECONDS = 30  # 30s, 2min, 8min... (x4 per attempt)


class LeaseLost(RuntimeError):
    """This worker no longer owns the job (lease expired and someone else took it)."""


@dataclass(frozen=True)
class Job:
    id: int
    document_id: str
    stage: str
    attempts: int
    max_attempts: int


class PgJobQueue:
    def __init__(
        self,
        dsn: str,
        worker_id: str | None = None,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
        max_attempts: int = 3,
    ) -> None:
        self.dsn = dsn
        self.worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}:{threading.get_ident()}"
        self.lease_seconds = lease_seconds
        self.max_attempts = max_attempts

    def _conn(self):
        import psycopg

        return psycopg.connect(self.dsn)

    # ------------------------------------------------------------------ producer
    def enqueue(self, document_id: str, stage: str = STAGE_PARSE) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO jobs (document_id, stage, max_attempts) VALUES (%s::uuid, %s, %s) "
                "ON CONFLICT (document_id, stage) WHERE status IN ('queued', 'running') DO NOTHING",
                (document_id, stage, self.max_attempts),
            )

    # ------------------------------------------------------------------ consumer
    def reap_dead(self) -> list[str]:
        """Jobs whose worker died on the last allowed attempt: mark dead, return their document ids."""
        with self._conn() as c:
            rows = c.execute(
                "UPDATE jobs SET status = 'dead', last_error = 'LeaseExpired', finished_at = now() "
                "WHERE status = 'running' AND locked_until < now() AND attempts >= max_attempts "
                "RETURNING document_id"
            ).fetchall()
        return [str(r[0]) for r in rows]

    def claim(self) -> Job | None:
        with self._conn() as c:
            row = c.execute(
                "UPDATE jobs SET status = 'running', attempts = attempts + 1, locked_by = %s, "
                "locked_until = now() + make_interval(secs => %s) "
                "WHERE id = ("
                "  SELECT id FROM jobs "
                "  WHERE (status = 'queued' AND run_after <= now()) "
                "     OR (status = 'running' AND locked_until < now() AND attempts < max_attempts) "
                "  ORDER BY run_after, id FOR UPDATE SKIP LOCKED LIMIT 1"
                ") RETURNING id, document_id, stage, attempts, max_attempts",
                (self.worker_id, self.lease_seconds),
            ).fetchone()
        return Job(row[0], str(row[1]), row[2], row[3], row[4]) if row else None

    def heartbeat(self, job: Job) -> None:
        with self._conn() as c:
            cur = c.execute(
                "UPDATE jobs SET locked_until = now() + make_interval(secs => %s) "
                "WHERE id = %s AND locked_by = %s AND status = 'running'",
                (self.lease_seconds, job.id, self.worker_id),
            )
            if cur.rowcount == 0:
                raise LeaseLost(str(job.id))

    def complete(self, job: Job, next_stage: str | None) -> None:
        """Mark done and enqueue the next stage in the same transaction."""
        with self._conn() as c:
            cur = c.execute(
                "UPDATE jobs SET status = 'done', finished_at = now(), locked_until = NULL "
                "WHERE id = %s AND locked_by = %s AND status = 'running'",
                (job.id, self.worker_id),
            )
            if cur.rowcount == 0:
                raise LeaseLost(str(job.id))
            if next_stage:
                c.execute(
                    "INSERT INTO jobs (document_id, stage, max_attempts) VALUES (%s::uuid, %s, %s) "
                    "ON CONFLICT (document_id, stage) WHERE status IN ('queued', 'running') DO NOTHING",
                    (job.document_id, next_stage, job.max_attempts),
                )

    def fail(self, job: Job, error: str) -> bool:
        """Retry with backoff, or give up. Returns True when the job is dead (no more attempts)."""
        dead = job.attempts >= job.max_attempts
        with self._conn() as c:
            if dead:
                c.execute(
                    "UPDATE jobs SET status = 'dead', last_error = %s, finished_at = now(), locked_until = NULL "
                    "WHERE id = %s AND locked_by = %s",
                    (error, job.id, self.worker_id),
                )
            else:
                backoff = BACKOFF_BASE_SECONDS * 4 ** (job.attempts - 1)
                c.execute(
                    "UPDATE jobs SET status = 'queued', last_error = %s, locked_by = NULL, locked_until = NULL, "
                    "run_after = now() + make_interval(secs => %s) WHERE id = %s AND locked_by = %s",
                    (error, backoff, job.id, self.worker_id),
                )
        return dead

    # ------------------------------------------------------------------ worker loop
    def run_once(self, repo: Repo, storage_dir: Path, llm_factory: LLMFactory) -> bool:
        """Claim and run one job. Returns False when there was nothing to do."""
        for doc_id in self.reap_dead():
            repo.update_document(doc_id, status="failed", stage=None)
        job = self.claim()
        if job is None:
            return False
        log.info("job %d start stage=%s attempt=%d/%d", job.id, job.stage, job.attempts, job.max_attempts)
        try:
            nxt = run_stage(repo, storage_dir, job.document_id, job.stage, llm_factory,
                            heartbeat=lambda: self.heartbeat(job))
            self.complete(job, nxt)
            log.info("job %d done next=%s", job.id, nxt)
        except LeaseLost:
            log.warning("job %d lost its lease; another worker owns it now", job.id)
        except Exception as exc:  # RetryableJobError and anything unexpected: retry, then give up
            name = type(exc).__name__
            level = log.warning if isinstance(exc, RetryableJobError) else log.error
            level("job %d failed: %s", job.id, name)
            if not isinstance(exc, RetryableJobError):
                from .errors import record

                record(repo, "worker", exc, f"job {job.id} stage={job.stage}", None)
            if self.fail(job, name):
                repo.update_document(job.document_id, status="failed", stage=None)
        return True

    def run_forever(
        self,
        repo: Repo,
        storage_dir: Path,
        llm_factory: LLMFactory,
        stop: threading.Event,
        poll_seconds: float = 2.0,
    ) -> None:
        while not stop.is_set():
            try:
                busy = self.run_once(repo, storage_dir, llm_factory)
            except Exception as exc:  # database hiccup: keep the worker alive
                log.error("worker loop error: %s", type(exc).__name__)
                busy = False
            if not busy:
                stop.wait(poll_seconds)
