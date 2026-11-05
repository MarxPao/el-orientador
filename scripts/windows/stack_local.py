"""Sobe o Orientador sem Docker: Postgres embutido (pixeltable-pgserver) + API.

Uso: python scripts/windows/stack_local.py [--pg-only]
Dados ficam em ./data (pg, storage). Ctrl+C encerra tudo.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("ORIENTADOR_DATA", ROOT / "data"))


def main() -> int:
    import pixeltable_pgserver as pgserver
    import psycopg

    (DATA / "pg").mkdir(parents=True, exist_ok=True)
    (DATA / "storage").mkdir(parents=True, exist_ok=True)
    srv = pgserver.get_server(DATA / "pg", cleanup_mode=None)  # fica de pé entre execuções
    admin = srv.get_uri()
    with psycopg.connect(admin, autocommit=True) as c:
        if not c.execute("SELECT 1 FROM pg_database WHERE datname='orientador'").fetchone():
            c.execute("CREATE DATABASE orientador")
    dsn = admin.replace("/postgres?", "/orientador?")
    with psycopg.connect(dsn, autocommit=True) as c:
        c.execute("CREATE EXTENSION IF NOT EXISTS vector")
        fresh = c.execute("SELECT to_regclass('public.projects')").fetchone()[0] is None
        if fresh:
            sql = (ROOT / "db" / "schema.sql").read_text(encoding="utf-8-sig")
            sql = sql.replace("CREATE EXTENSION IF NOT EXISTS pgcrypto;", "-- pgcrypto: gen_random_uuid() já é nativo")
            c.execute(sql)
            print("Banco criado.")
    secret_file = DATA / "jwt_secret.txt"
    if not secret_file.exists():
        import secrets
        secret_file.write_text(secrets.token_hex(32))
    env = dict(os.environ)
    env.update(
        DATABASE_URL=dsn,
        STORAGE_DIR=str(DATA / "storage"),
        JWT_SECRET=env.get("JWT_SECRET") or secret_file.read_text().strip(),
        AUTO_MIGRATE="1",
        MIGRATIONS_DIR=str(ROOT / "db" / "migrations"),
    )
    env.setdefault("EMBED_PROVIDER", "local")
    env.setdefault("FASTEMBED_CACHE_PATH", str(DATA / "models"))
    if "--pg-only" in sys.argv:
        print(dsn)
        return 0
    port = env.get("API_PORT", "8000")
    print(f"API em http://localhost:{port}")
    return subprocess.call(
        [sys.executable, "-m", "uvicorn", "app.main:create_app", "--factory", "--host", "127.0.0.1", "--port", port],
        cwd=ROOT / "services" / "pipeline", env=env)


if __name__ == "__main__":
    sys.exit(main())
