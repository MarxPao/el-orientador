"""Standalone job worker: `python -m app.worker`.

Runs the same PgJobQueue loop that the API can embed, but in its own process, so uploads keep being
processed while the API restarts and the worker count can scale independently. Safe to run several.

Env: DATABASE_URL (required), STORAGE_DIR, LLM_API_KEY / LLM_MODEL (optional), WORKER_POLL_SECONDS.
"""
from __future__ import annotations

import logging
import os
import signal
import sys
import threading
from pathlib import Path

from .llm_gateway import wrap
from .pgqueue import PgJobQueue
from .repo import PostgresRepo


def main() -> int:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(name)s %(message)s")
    log = logging.getLogger("orientador.worker")
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        log.error("DATABASE_URL is required for the worker")
        return 2

    from .main import default_llm_factory  # reuse the API's rule: Gemini only when a key is set

    shared: list = []

    def llm_factory():
        # one gateway for the whole process, so the circuit breaker remembers recent failures
        if not shared:
            raw = default_llm_factory()
            if raw is None:
                return None
            shared.append(wrap(raw))
        return shared[0]

    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())

    if os.environ.get("AUTO_MIGRATE") == "1":
        from .migrate import apply_all

        apply_all(dsn)
    repo = PostgresRepo(dsn)
    queue = PgJobQueue(dsn)
    storage = Path(os.environ.get("STORAGE_DIR", "storage"))
    log.info("worker %s started", queue.worker_id)
    queue.run_forever(repo, storage, llm_factory, stop, poll_seconds=float(os.environ.get("WORKER_POLL_SECONDS", "2")))
    log.info("worker stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
