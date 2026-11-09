"""FastAPI app factory — El Orientador API.

A fábrica monta o contexto compartilhado (AppCtx) e delega o registro de
rotas para módulos por domínio. Cada roteador recebe o contexto via
register_routes(app, ctx) e nunca precisa de globais.
"""
from __future__ import annotations

from dotenv import load_dotenv
load_dotenv(override=False)

import os
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import errors as error_log
from .jobs import InlineQueue, JobQueue, LLMFactory, ThreadQueue
from .metadata import FetchJson, http_fetch_json
from .pipeline.llm import LLMClient
from .repo import InMemoryRepo, PostgresRepo, Repo
from .llm_gateway import wrap as wrap_llm

from .routers._ctx import AppCtx
from .routers import auth, projects, library, map, tree, sections, authorship, advisor, analysis, repositories, defense, export, cohort
from .main_models import _LOGIN_FAILS, _login_failed, _login_lock_remaining


def default_llm_factory():
    """LLM client para LLM_PROVIDER (gemini | grok) quando há chave; None caso contrário."""
    from .pipeline.llm_client import build_client
    return build_client()


def default_repo() -> Repo:
    dsn = os.environ.get("DATABASE_URL")
    return PostgresRepo(dsn) if dsn else InMemoryRepo()


_DEFAULT_CLIENT = object()


def create_app(
    repo: Repo | None = None,
    fetch_json: FetchJson | None = None,
    storage_dir: Path | None = None,
    llm_factory: LLMFactory | None = None,
    job_queue: JobQueue | None = None,
    client: Any = _DEFAULT_CLIENT,
) -> FastAPI:
    app = FastAPI(title="El Orientador API")

    # ── Repositório ───────────────────────────────────────────────────
    repo = repo or default_repo()
    fetch_json = fetch_json or http_fetch_json
    storage_dir = Path(storage_dir or os.environ.get("STORAGE_DIR", "storage"))

    if os.environ.get("DEMO_SEED") == "1":
        from .demo import seed_demo
        seed_demo(repo, storage_dir, with_cohort=os.environ.get("DEMO_COHORT") == "1")

    # ── Cliente LLM ───────────────────────────────────────────────────
    if client is _DEFAULT_CLIENT:
        factory = llm_factory or default_llm_factory
        client = factory() if factory else None
    client = wrap_llm(client)

    # ── Fila de jobs ──────────────────────────────────────────────────
    if job_queue is None:
        if isinstance(repo, PostgresRepo):
            from .pgqueue import PgJobQueue

            pg_queue = PgJobQueue(repo.dsn)
            if os.environ.get("JOB_WORKER", "embedded") != "external":
                threading.Thread(
                    target=pg_queue.run_forever,
                    args=(repo, storage_dir, lambda: client, threading.Event()),
                    daemon=True,
                    name="pipeline-worker",
                ).start()
            job_queue = pg_queue
        else:
            job_queue = ThreadQueue(repo, storage_dir, llm_factory)

    # ── Migrações e manutenção ────────────────────────────────────────
    if isinstance(repo, PostgresRepo):
        if os.environ.get("AUTO_MIGRATE") == "1":
            from .migrate import apply_all
            apply_all(repo.dsn)
        error_log.purge_old(repo)

    # ── Middleware: request-ID + captura de erros ─────────────────────
    @app.middleware("http")
    async def request_id_and_errors(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        try:
            response = await call_next(request)
        except Exception as exc:
            error_log.record(repo, "api", exc, f"{request.method} {request.url.path}", rid)
            return JSONResponse(
                {"detail": "Erro interno. Informe este código ao suporte: " + rid, "request_id": rid},
                status_code=500,
                headers={"X-Request-ID": rid},
            )
        response.headers["X-Request-ID"] = rid
        return response

    # ── CORS ──────────────────────────────────────────────────────────
    origins = os.environ.get(
        "WEB_ORIGINS",
        "http://localhost:3000,http://localhost:3001,http://localhost:3005,"
        "http://127.0.0.1:3000,http://127.0.0.1:3001,http://127.0.0.1:3005",
    ).split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Contexto compartilhado ────────────────────────────────────────
    ctx = AppCtx(
        repo=repo,
        storage_dir=storage_dir,
        job_queue=job_queue,
        client=client,
        fetch_json=fetch_json,
    )

    # ── Registro de rotas por domínio ─────────────────────────────────
    auth.register_routes(app, ctx)
    projects.register_routes(app, ctx)
    library.register_routes(app, ctx)
    map.register_routes(app, ctx)
    tree.register_routes(app, ctx)
    sections.register_routes(app, ctx)
    authorship.register_routes(app, ctx)
    advisor.register_routes(app, ctx)
    analysis.register_routes(app, ctx)
    repositories.register_routes(app, ctx)
    defense.register_routes(app, ctx)
    export.register_routes(app, ctx)
    cohort.register_routes(app, ctx)

    return app

app = create_app()
