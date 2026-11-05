"""Roteador de projetos.

Endpoints: /projects CRUD e /projects/{id}/update
"""
from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from ._ctx import AppCtx
from ..main_models import ProjectIn


def register_routes(app: FastAPI, ctx: AppCtx) -> None:
    bearer = ctx.bearer

    def _current_user(
        request: Request,
        cred: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> dict:
        return ctx.current_user(request, cred)

    # ── CRUD de projetos ──────────────────────────────────────────────

    @app.post("/projects", status_code=201)
    def create_project(body: ProjectIn, user: dict = Depends(_current_user)):
        data = body.model_dump(mode="json")
        return ctx.repo.create_project(user["id"], data)

    @app.get("/projects")
    def list_projects(user: dict = Depends(_current_user)):
        return ctx.repo.list_projects(user["id"])

    @app.get("/projects/{project_id}")
    def get_project(project_id: str, user: dict = Depends(_current_user)):
        return ctx.accessible_project(user, project_id)

    @app.patch("/projects/{project_id}")
    def patch_project(project_id: str, body: ProjectIn, user: dict = Depends(_current_user)):
        ctx.owned_project(user, project_id)
        data = {k: v for k, v in body.model_dump(mode="json").items() if v is not None}
        project = ctx.repo.update_project(user["id"], project_id, **data)
        if not project:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Projeto não encontrado.")
        return project

    @app.delete("/projects/{project_id}")
    def delete_project(project_id: str, user: dict = Depends(_current_user)):
        ctx.owned_project(user, project_id)
        ctx.repo.delete_project(user["id"], project_id)
        return {"ok": True}
