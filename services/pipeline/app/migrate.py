"""Applies db/migrations/*.sql in order, once each, so an existing local database follows the code.

`schema.sql` creates a fresh database; this brings an older one up to date. Every migration is idempotent
(IF NOT EXISTS / guarded), so the first run on a database that was created from the latest schema.sql is safe.
A migration runs inside one transaction; if it fails nothing is recorded and the error is raised.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger("orientador.migrate")

DEFAULT_DIR = Path(os.environ.get("MIGRATIONS_DIR", "/app/migrations"))


def pending(applied: set[str], directory: Path) -> list[Path]:
    return [p for p in sorted(directory.glob("*.sql")) if p.name not in applied]


def apply_all(dsn: str, directory: Path | None = None) -> list[str]:
    """Run the migrations not yet recorded. Returns the names applied."""
    import psycopg

    directory = Path(directory or DEFAULT_DIR)
    if not directory.is_dir():
        log.warning("migrations directory %s not found; skipping", directory)
        return []
    done: list[str] = []
    with psycopg.connect(dsn) as c:
        c.execute("SELECT pg_advisory_lock(727001)")  # API and worker may start together
        try:
            c.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY, "
                      "applied_at timestamptz NOT NULL DEFAULT now())")
            c.commit()
            applied = {r[0] for r in c.execute("SELECT name FROM schema_migrations").fetchall()}
            for path in pending(applied, directory):
                try:
                    c.execute(path.read_text(encoding="utf-8-sig"))
                    c.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
                    c.commit()
                except Exception:
                    c.rollback()
                    log.error("migration %s failed; database left as it was before it", path.name)
                    raise
                log.info("migration %s applied", path.name)
                done.append(path.name)
        finally:
            c.execute("SELECT pg_advisory_unlock(727001)")
            c.commit()
    return done
