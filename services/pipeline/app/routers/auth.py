"""Roteador de autenticação e identidade.

Endpoints: /health, /capabilities, /auth/register, /auth/login,
           /auth/logout, /me, /admin/errors, /beta-metrics
"""
from __future__ import annotations

import os

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials

from .. import embeddings
from .. import errors as error_log
from ..repo import EmailTaken
from ..security import (
    TOKEN_TTL_SECONDS,
    create_token,
    hash_password,
    verify_password,
)
from ._ctx import AppCtx
from ..main_models import LoginIn, RegisterIn


def register_routes(app: FastAPI, ctx: AppCtx) -> None:  # noqa: C901
    bearer = ctx.bearer

    def _current_user(
        request: Request,
        cred: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> dict:
        return ctx.current_user(request, cred)

    def _should_set_cookie(request: Request) -> bool:
        return (
            os.environ.get("USE_AUTH_COOKIES") == "1"
            or request.headers.get("x-auth-cookie") == "1"
            or request.query_params.get("cookie") == "1"
        )

    def _set_auth_cookie(request: Request, response: Response, token: str) -> None:
        if not _should_set_cookie(request):
            return
        is_prod = os.environ.get("ENV") == "production"
        response.set_cookie(
            key="orientador_token",
            value=token,
            httponly=True,
            samesite="lax",
            max_age=TOKEN_TTL_SECONDS,
            secure=is_prod,
        )

    # ── sistema ───────────────────────────────────────────────────────

    @app.get("/health")
    def health():
        return {"status": "ok", "app": "El Orientador", "version": "0.1.0-beta"}

    @app.get("/capabilities")
    def capabilities():
        """What the backend can honestly do right now."""
        client = ctx.client
        ai = client is not None and client.available
        return {
            "llm_configured": client is not None,
            "llm_available": ai,
            "llm_model": getattr(client, "model", None) if client is not None else None,
            "llm_provider": os.environ.get("LLM_PROVIDER", "gemini").strip().lower()
            if client is not None
            else None,
            "features": {
                "gate_dialogue": "ai" if ai else "unavailable",
                "map_suggest": "ai" if ai else "unavailable",
                "claim_extraction": "ai" if ai else "deterministic",
                "polish": "ai" if ai else "mechanical",
                "coauthor": "ai" if ai else "scaffold",
                "draft": "ai" if ai else "scaffold",
                "compare_synthesis": "ai" if ai else "scaffold",
                "authorship": "provenance_ledger",
                "search": "hybrid"
                if embeddings.resolve(client) is not None
                else "keyword",
                "summaries": "ai" if ai else "unavailable",
            },
        }

    @app.get("/admin/errors")
    def admin_errors(
        limit: int = 100,
        user: dict = Depends(_current_user),
    ):
        """Errors recorded locally. Only ADMIN_EMAILS may read them."""
        from fastapi import Query

        if (user.get("email") or "").lower() not in error_log.admin_emails():
            from fastapi import HTTPException

            raise HTTPException(status.HTTP_403_FORBIDDEN, "Acesso restrito ao administrador.")
        return {
            "retention_days": error_log.retention_days(),
            "errors": ctx.repo.list_error_events(limit),
        }

    @app.get("/beta-metrics")
    def beta_metrics(user: dict = Depends(_current_user)):
        return ctx.repo.get_beta_metrics()

    # ── auth ──────────────────────────────────────────────────────────

    @app.post("/auth/register", status_code=201)
    def register(body: RegisterIn, request: Request, response: Response):
        from fastapi import HTTPException

        try:
            user = ctx.repo.create_user(
                body.email, body.name, hash_password(body.password)
            )
        except EmailTaken:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Este e-mail já está cadastrado."
            ) from None
        token = create_token(user["id"])
        _set_auth_cookie(request, response, token)
        return {"user": ctx.public(user), "token": token}

    @app.post("/auth/login")
    def login(body: LoginIn, request: Request, response: Response):
        from fastapi import HTTPException
        from ..main_models import _login_failed, _login_lock_remaining

        key = body.email.strip().lower()
        wait = _login_lock_remaining(key)
        if wait:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Muitas tentativas. Tente de novo em {wait // 60 + 1} min.",
                headers={"Retry-After": str(wait)},
            )
        user = ctx.repo.get_user_by_email(body.email)
        if not user or not verify_password(body.password, user["password_hash"]):
            _login_failed(key)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha incorretos.")
        from ..main_models import _LOGIN_FAILS

        _LOGIN_FAILS.pop(key, None)
        token = create_token(user["id"])
        _set_auth_cookie(request, response, token)
        return {"user": ctx.public(user), "token": token}

    @app.post("/auth/logout")
    def logout(response: Response):
        response.delete_cookie(key="orientador_token")
        return {"ok": True}

    @app.get("/me")
    def me(user: dict = Depends(_current_user)):
        return ctx.public(user)
