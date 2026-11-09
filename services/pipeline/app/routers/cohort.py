"""Roteador do Painel Multi-orientandos e Coordenação Acadêmica (T7.4).

Permite a visualização agregada de entregas, etapas puladas e alertas
de prazo para orientadores com múltiplos estudantes, além de exportações.
"""
from __future__ import annotations

import io
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from ..cohort import compute_cohort_dashboard, export_cohort_summary_csv, export_cohort_summary_markdown
from ..security import decode_share_token
from ._ctx import AppCtx


class LinkAdviseeIn(BaseModel):
    project_id: str | None = Field(default=None, description="UUID do projeto do estudante")
    share_token: str | None = Field(default=None, description="Token do link mágico compartilhado")


def register_routes(app: FastAPI, ctx: AppCtx) -> None:
    bearer = ctx.bearer

    def _current_user(
        request: Request,
        cred: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> dict:
        return ctx.current_user(request, cred)

    @app.get("/advisor/cohort-summary")
    def get_cohort_summary(user: dict = Depends(_current_user)):
        """Quadro geral consolidado de todos os orientandos de um professor/coordenador."""
        return compute_cohort_dashboard(ctx.repo, user["email"])

    @app.get("/advisor/cohort-export")
    def get_cohort_export(
        format: str = "csv",
        user: dict = Depends(_current_user),
    ):
        """Exporta ata sintética da turma em CSV ou Markdown para colegiado/departamento."""
        dashboard = compute_cohort_dashboard(ctx.repo, user["email"])
        fmt = format.strip().lower()

        if fmt == "markdown" or fmt == "md":
            content = export_cohort_summary_markdown(dashboard)
            media_type = "text/markdown; charset=utf-8"
            filename = "relatorio_turma_orientandos.md"
        else:
            content = export_cohort_summary_csv(dashboard)
            media_type = "text/csv; charset=utf-8"
            filename = "relatorio_turma_orientandos.csv"

        stream = io.BytesIO(content.encode("utf-8"))
        return StreamingResponse(
            stream,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )

    @app.post("/advisor/link-advisee")
    def link_advisee(body: LinkAdviseeIn, user: dict = Depends(_current_user)):
        """Vincula o orientador a um projeto de orientando via ID ou token mágico."""
        target_project_id = body.project_id
        if not target_project_id and body.share_token:
            target_project_id = decode_share_token(body.share_token)

        if not target_project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Informe um project_id válido ou um share_token de orientador.",
            )

        project = ctx.repo.get_project_by_id(target_project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Projeto acadêmico não encontrado.",
            )

        # Adiciona vínculo de orientador
        ctx.repo.invite_advisor(target_project_id, user["email"], can_comment=True)
        return {
            "ok": True,
            "project_id": target_project_id,
            "title": project.get("title"),
            "message": f"Vínculo de orientação estabelecido com sucesso.",
        }
