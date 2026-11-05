"""Roteador de orientadores, relatórios, comentários de seção e link mágico.

Endpoints: /advising-projects, /advisors, /reports, /comments, /share-link, /shared/{token}
"""
from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from ..reports import generate_advisor_report_payload
from ..security import create_share_token, decode_share_token
from ._ctx import AppCtx
from ..main_models import (
    AdvisorInviteIn,
    CommentIn,
    CommentUpdateIn,
    NodeFeedbackIn,
    SharedCommentIn,
    SharedNodeFeedbackIn,
)

DEFAULT_SECTIONS = [
    ("1. Introdução", 0),
    ("2. Referencial Teórico", 1),
    ("3. Metodologia", 2),
    ("4. Resultados e Discussão", 3),
    ("5. Considerações Finais", 4),
]


def register_routes(app: FastAPI, ctx: AppCtx) -> None:
    bearer = ctx.bearer

    def _current_user(
        request: Request,
        cred: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> dict:
        return ctx.current_user(request, cred)

    # ── helpers internos ──────────────────────────────────────────────

    def _section_of(project_id: str, section_id: str) -> dict:
        sec = ctx.repo.get_section(project_id, section_id)
        if not sec:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Seção não encontrada.")
        return sec

    def _comment_of(project_id: str, section_id: str, comment_id: str) -> dict:
        _section_of(project_id, section_id)
        comment = ctx.repo.get_section_comment(section_id, comment_id)
        if not comment:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Comentário não encontrado.")
        return comment

    def _node_of(project_id: str, node_key: str) -> dict:
        node = ctx.repo.get_progress_node(project_id, node_key)
        if not node:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Etapa não encontrada.")
        return node

    def _project_from_share_token(token: str) -> tuple[str, dict]:
        project_id = decode_share_token(token)
        if not project_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Link de compartilhamento inválido ou expirado.")
        project = ctx.repo.get_project_by_id(project_id)
        if not project:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Projeto não encontrado.")
        return project_id, project

    # ── Projetos assessorados ─────────────────────────────────────────

    @app.get("/advising-projects")
    def get_advising_projects(user: dict = Depends(_current_user)):
        """List all projects where current user is invited as advisor."""
        return ctx.repo.list_advising_projects(user["email"])

    # ── Convites de orientador ────────────────────────────────────────

    @app.post("/projects/{project_id}/advisors")
    def invite_project_advisor(project_id: str, body: AdvisorInviteIn, user: dict = Depends(_current_user)):
        """Invite human advisor by email (owner only)."""
        ctx.owned_project(user, project_id)
        return ctx.repo.invite_advisor(project_id, body.advisor_email, body.can_comment)

    @app.get("/projects/{project_id}/advisors")
    def list_project_advisors(project_id: str, user: dict = Depends(_current_user)):
        """List invited advisors for project (owner or advisor)."""
        ctx.accessible_project(user, project_id)
        return ctx.repo.list_advisors(project_id)

    @app.delete("/projects/{project_id}/advisors/{advisor_email}")
    def delete_project_advisor(project_id: str, advisor_email: str, user: dict = Depends(_current_user)):
        """Remove invited advisor (owner only)."""
        ctx.owned_project(user, project_id)
        ctx.repo.remove_advisor(project_id, advisor_email)
        return {"ok": True}

    # ── Relatórios ────────────────────────────────────────────────────

    @app.post("/projects/{project_id}/reports")
    def create_project_report(project_id: str, user: dict = Depends(_current_user)):
        """Generate and persist formal progress report for advisor."""
        project = ctx.accessible_project(user, project_id)
        payload = generate_advisor_report_payload(ctx.repo, project_id, project)
        return ctx.repo.create_advisor_report(project_id, payload)

    @app.get("/projects/{project_id}/reports")
    def list_project_reports(project_id: str, user: dict = Depends(_current_user)):
        """List all historical progress reports generated for project."""
        ctx.accessible_project(user, project_id)
        return ctx.repo.list_advisor_reports(project_id)

    @app.get("/projects/{project_id}/reports/{report_id}")
    def get_project_report(project_id: str, report_id: str, user: dict = Depends(_current_user)):
        """Get single progress report payload."""
        ctx.accessible_project(user, project_id)
        rep = ctx.repo.get_advisor_report(project_id, report_id)
        if not rep:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Relatório não encontrado.")
        return rep

    # ── Comentários de seção ──────────────────────────────────────────

    @app.get("/projects/{project_id}/sections/{section_id}/comments")
    def list_comments(project_id: str, section_id: str, user: dict = Depends(_current_user)):
        """List comments for section (student or advisor)."""
        ctx.accessible_project(user, project_id)
        _section_of(project_id, section_id)
        return ctx.repo.list_section_comments(section_id)

    @app.post("/projects/{project_id}/sections/{section_id}/comments")
    def post_comment(project_id: str, section_id: str, body: CommentIn, user: dict = Depends(_current_user)):
        """Add comment to section (student or advisor)."""
        ctx.accessible_project(user, project_id)
        _section_of(project_id, section_id)
        return ctx.repo.create_section_comment(
            section_id=section_id,
            author_email=user["email"],
            author_name=user.get("name"),
            content=body.content,
        )

    @app.patch("/projects/{project_id}/sections/{section_id}/comments/{comment_id}")
    def patch_comment(
        project_id: str,
        section_id: str,
        comment_id: str,
        body: CommentUpdateIn,
        user: dict = Depends(_current_user),
    ):
        """Update or resolve comment."""
        ctx.accessible_project(user, project_id)
        _comment_of(project_id, section_id, comment_id)
        fields: dict = {}
        if body.content is not None:
            fields["content"] = body.content
        if body.resolved is not None:
            fields["resolved"] = body.resolved
        if not fields:
            return _comment_of(project_id, section_id, comment_id)
        comment = ctx.repo.update_section_comment(comment_id, **fields)
        if not comment:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Comentário não encontrado.")
        return comment

    @app.post("/projects/{project_id}/sections/{section_id}/comments/{comment_id}/resolve")
    def resolve_comment(project_id: str, section_id: str, comment_id: str, user: dict = Depends(_current_user)):
        """Mark a comment as resolved."""
        ctx.accessible_project(user, project_id)
        _comment_of(project_id, section_id, comment_id)
        return ctx.repo.update_section_comment(comment_id, resolved=True)

    @app.delete("/projects/{project_id}/sections/{section_id}/comments/{comment_id}")
    def delete_comment(project_id: str, section_id: str, comment_id: str, user: dict = Depends(_current_user)):
        """Delete comment."""
        ctx.accessible_project(user, project_id)
        _comment_of(project_id, section_id, comment_id)
        ctx.repo.delete_section_comment(comment_id)
        return {"ok": True}

    # ── Versões de seção (restore points) ────────────────────────────

    @app.get("/projects/{project_id}/sections/{section_id}/versions")
    def list_section_versions(project_id: str, section_id: str, user: dict = Depends(_current_user)):
        """Restore points, newest first."""
        ctx.accessible_project(user, project_id)
        _section_of(project_id, section_id)
        return ctx.repo.list_section_versions(project_id, section_id)

    @app.post("/projects/{project_id}/sections/{section_id}/versions/{version_id}/restore")
    def restore_section_version(
        project_id: str, section_id: str, version_id: str, user: dict = Depends(_current_user)
    ):
        """Restore an earlier section content. Current content is saved first so it's undoable."""
        ctx.owned_project(user, project_id)
        sec = _section_of(project_id, section_id)
        version = ctx.repo.get_section_version(project_id, section_id, version_id)
        if not version:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Versão não encontrada.")
        content = dict(version["content_snapshot"])
        current = sec.get("content")
        if isinstance(current, dict) and "_authorship" in current:
            content["_authorship"] = current["_authorship"]
        else:
            content.pop("_authorship", None)
        restored = ctx.repo.update_section(project_id, section_id, content=content, version_by="restore", force_version=True)
        if not restored:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Seção não encontrada.")
        return restored

    # ── Feedback de orientador em nós da árvore ───────────────────────

    @app.get("/projects/{project_id}/tree/{node_key}/feedback")
    def list_node_feedback(project_id: str, node_key: str, user: dict = Depends(_current_user)):
        ctx.accessible_project(user, project_id)
        _node_of(project_id, node_key)
        return ctx.repo.list_node_feedback(project_id, node_key)

    @app.post("/projects/{project_id}/tree/{node_key}/feedback", status_code=201)
    def post_node_feedback(
        project_id: str, node_key: str, body: NodeFeedbackIn, user: dict = Depends(_current_user)
    ):
        ctx.accessible_project(user, project_id)
        _node_of(project_id, node_key)
        return ctx.repo.add_node_feedback(
            project_id, node_key, user["email"], user.get("name"), body.content.strip()
        )

    # ── Link mágico de compartilhamento ──────────────────────────────

    @app.post("/projects/{project_id}/share-link")
    def create_advisor_share_link(project_id: str, user: dict = Depends(_current_user)):
        """Generate signed shareable link for human advisor inspection."""
        ctx.accessible_project(user, project_id)
        token = create_share_token(project_id)
        ctx.repo.log_ai_usage(project_id, "share_report", None, "system", "advisor_share_v1")
        return {"token": token, "share_path": f"/orientador/{token}"}

    @app.get("/shared/{token}")
    def get_shared_project_view(token: str):
        """Public token-authenticated view: report, concepts, and sections for the human advisor."""
        project_id, project = _project_from_share_token(token)
        payload = generate_advisor_report_payload(ctx.repo, project_id, project)
        concepts = ctx.repo.list_concepts(project_id)
        raw_sections = ctx.repo.list_sections(project_id)
        if not raw_sections:
            for title, pos in DEFAULT_SECTIONS:
                ctx.repo.create_section(project_id, title=title, parent_id=None, position=pos)
            raw_sections = ctx.repo.list_sections(project_id)
        sections_out = [
            {
                "id": s["id"],
                "title": s["title"],
                "position": s["position"],
                "content": s.get("content") or {},
                "concept_ids": s.get("concept_ids") or [],
                "comments": ctx.repo.list_section_comments(s["id"]),
            }
            for s in raw_sections
        ]
        return {
            "project": project,
            "report_payload": payload,
            "concepts": concepts,
            "sections": sections_out,
        }

    @app.post("/shared/{token}/comments", status_code=201)
    def post_shared_advisor_comment(token: str, body: SharedCommentIn):
        """Allow human advisor to record a comment via magic link."""
        project_id, _ = _project_from_share_token(token)
        sec = ctx.repo.get_section(project_id, body.section_id)
        if not sec:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Seção não encontrada.")
        ctx.repo.invite_advisor(project_id, body.author_email, True)
        formatted_content = body.content.strip()
        if body.anchor_quote and body.anchor_quote.strip():
            formatted_content = f'[Trecho em revisão: "{body.anchor_quote.strip()}"]\n{formatted_content}'
        return ctx.repo.create_section_comment(
            section_id=body.section_id,
            author_email=body.author_email,
            author_name=body.author_name.strip(),
            content=formatted_content,
        )

    @app.post("/shared/{token}/tree/{node_key}/feedback", status_code=201)
    def post_shared_node_feedback(token: str, node_key: str, body: SharedNodeFeedbackIn):
        """Human advisor leaves feedback on a progress-tree step through magic link."""
        project_id, _ = _project_from_share_token(token)
        _node_of(project_id, node_key)
        ctx.repo.invite_advisor(project_id, body.advisor_email, True)
        name = body.advisor_name.strip() or None
        return ctx.repo.add_node_feedback(project_id, node_key, body.advisor_email, name, body.content.strip())
