"""Migrations bring an older database up to date, once each, and never break a current one."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from app import migrate  # noqa: E402

DSN = os.environ.get("TEST_DATABASE_URL")
PG_OK = bool(DSN) and "test" in (DSN or "").rsplit("/", 1)[-1].split("?")[0].lower()
MIGRATIONS = Path(__file__).parent.parent.parent.parent / "db" / "migrations"

pytestmark = pytest.mark.skipif(not PG_OK, reason="TEST_DATABASE_URL not set to a *test* database")


def _tables(c):
    return {r[0] for r in c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")}


def test_runs_each_migration_once_and_is_idempotent():
    import psycopg

    with psycopg.connect(DSN) as c:
        c.execute("DROP TABLE IF EXISTS schema_migrations")
    first = migrate.apply_all(DSN, MIGRATIONS)
    assert first == sorted(p.name for p in MIGRATIONS.glob("*.sql"))  # all of them, on a DB already at head: safe
    assert migrate.apply_all(DSN, MIGRATIONS) == []
    with psycopg.connect(DSN) as c:
        assert {"provenance_events", "error_events", "chunks"} <= _tables(c)


def test_failed_migration_is_not_recorded(tmp_path):
    import psycopg

    (tmp_path / "001_ok.sql").write_text("CREATE TABLE IF NOT EXISTS mig_probe (x int);")
    (tmp_path / "002_bad.sql").write_text("CREATE TABLE mig_probe2 (x int); SELECT * FROM does_not_exist;")
    with psycopg.connect(DSN) as c:
        c.execute("DROP TABLE IF EXISTS schema_migrations")
        c.execute("DROP TABLE IF EXISTS mig_probe, mig_probe2")
    with pytest.raises(Exception):
        migrate.apply_all(DSN, tmp_path)
    with psycopg.connect(DSN) as c:
        names = {r[0] for r in c.execute("SELECT name FROM schema_migrations")}
        assert names == {"001_ok.sql"}
        assert "mig_probe2" not in _tables(c)  # the failing migration rolled back as a whole
        c.execute("DROP TABLE IF EXISTS schema_migrations, mig_probe")
