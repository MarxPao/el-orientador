"""Rotas de exportação acadêmica (LaTeX/Overleaf, formatos institucionais avançados).

Permite o download de pacotes compiláveis para submissão e diagramação.
"""
from __future__ import annotations

import re
import unicodedata
from fastapi import Depends, FastAPI, Request, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials

from ..export_latex import build_latex_package
from ._ctx import AppCtx


def slugify_filename(title: str) -> str:
    s = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s[:40] or "trabalho_academico"


def register_routes(app: FastAPI, ctx: AppCtx) -> None:
    @app.get("/projects/{project_id}/export/latex")
    def export_project_latex(
        project_id: str,
        request: Request,
        include_approval: bool = True,
        include_ai_declaration: bool = True,
        cred: HTTPAuthorizationCredentials | None = Depends(ctx.bearer),
    ):
        user = ctx.current_user(request, cred)
        project = ctx.accessible_project(user, project_id)

        # Gera o pacote .zip completo em memória
        zip_buf = build_latex_package(
            ctx.repo,
            project_id,
            include_approval=include_approval,
            include_ai_declaration=include_ai_declaration,
        )

        slug = slugify_filename(project.get("title") or "projeto")
        filename = f"{slug}_latex_overleaf.zip"

        return StreamingResponse(
            zip_buf,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
