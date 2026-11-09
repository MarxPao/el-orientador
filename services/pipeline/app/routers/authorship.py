"""Roteador de autoria, proveniência e detecção de paráfrase.

Endpoints: /authorship, /validate-authenticity, /provenance, /paste, /paraphrases
"""
from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from .. import embeddings
from .. import paraphrase
from ..authorship import compute_project_authorship, compute_section_authorship, count_words
from ..llm_gateway import LLMUnavailable
from ._ctx import AppCtx
from ..main_models import (
    ConfirmParaphraseIn,
    DeclarePasteIn,
    DismissParaphraseIn,
    PasteIn,
    ValidateAuthenticityIn,
)

MIN_PASTE_WORDS = 15
DISMISSED_KIND = "paraphrase_dismissed"


def _section_blocks(content: dict | None) -> list[str]:
    """Extrai blocos de parágrafo simples de um doc ProseMirror."""
    if not isinstance(content, dict):
        return []
    out = []
    for node in content.get("content") or []:
        if node.get("type") == "paragraph":
            texts = []
            for n in node.get("content") or []:
                if n.get("type") == "text":
                    texts.append(n.get("text") or "")
            block = "".join(texts).strip()
            if block:
                out.append(block)
    return out


def register_routes(app: FastAPI, ctx: AppCtx) -> None:
    bearer = ctx.bearer

    def _current_user(
        request: Request,
        cred: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> dict:
        return ctx.current_user(request, cred)

    # ── helpers de proveniência (compartilhados com sections.py) ─────

    def _events_by_section(project_id: str) -> dict[str, list[dict]]:
        out: dict[str, list[dict]] = {}
        for e in ctx.repo.list_provenance_events(project_id):
            out.setdefault(e["section_id"], []).append(e)
        return out

    def _ensure_ledger(project_id: str, sec: dict) -> None:
        if ctx.repo.list_provenance_events(project_id, sec["id"]):
            return
        meta = (sec.get("content") or {}).get("_authorship") if isinstance(sec.get("content"), dict) else None
        meta = meta if isinstance(meta, dict) else {}
        ai = int(meta.get("ai_drafted_words", 0) or 0)
        pol = int(meta.get("polished_words", 0) or 0)
        if ai or pol:
            ctx.repo.add_provenance_event(
                project_id, sec["id"], "legacy_counters", "server", ai + pol, None,
                {"ai_words": ai, "polished_words": pol}, None,
            )

    def _section_authorship_for(project_id: str, sec: dict) -> dict:
        quotes = [c.get("quote", "") for c in ctx.repo.list_project_claims(project_id)]
        return compute_section_authorship(
            sec, verified_quotes=quotes, events=ctx.repo.list_provenance_events(project_id, sec["id"])
        )

    def _section_of(project_id: str, section_id: str) -> dict:
        sec = ctx.repo.get_section(project_id, section_id)
        if not sec:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Seção não encontrada.")
        return sec

    # ── Prisma de Autoria ─────────────────────────────────────────────

    @app.get("/projects/{project_id}/authorship")
    def get_project_authorship(project_id: str, user: dict = Depends(_current_user)):
        """Authorship Prism from the provenance ledger: project totals and one entry per section."""
        ctx.accessible_project(user, project_id)
        sections = ctx.repo.list_sections(project_id)
        verified_quotes = [c.get("quote", "") for c in ctx.repo.list_project_claims(project_id)]
        ev = _events_by_section(project_id)
        return {
            "project": compute_project_authorship(sections, verified_quotes=verified_quotes, events_by_section=ev),
            "sections": {
                s["id"]: compute_section_authorship(s, verified_quotes=verified_quotes, events=ev.get(s["id"], []))
                for s in sections
            },
        }

    @app.post("/projects/{project_id}/sections/{section_id}/validate-authenticity")
    def post_validate_section_authenticity(
        project_id: str,
        section_id: str,
        body: ValidateAuthenticityIn | None = None,
        user: dict = Depends(_current_user),
    ):
        """Recompute authorship from ledger (old-name endpoint kept for backward compat)."""
        ctx.accessible_project(user, project_id)
        sec = _section_of(project_id, section_id)
        verified_quotes = [c.get("quote", "") for c in ctx.repo.list_project_claims(project_id)]
        return {
            "section_id": section_id,
            "section_authorship": _section_authorship_for(project_id, sec),
            "project_authorship": compute_project_authorship(
                ctx.repo.list_sections(project_id), verified_quotes=verified_quotes,
                events_by_section=_events_by_section(project_id),
            ),
            "synced": False,
            "notice": (
                "A sincronização por análise de estilo foi removida: estilo não prova autoria. "
                "O Prisma mostra apenas o que o editor registrou."
            ) if (body and body.sync_prism) else None,
        }

    # ── Ledger de proveniência ────────────────────────────────────────

    @app.get("/projects/{project_id}/sections/{section_id}/provenance")
    def get_section_provenance(project_id: str, section_id: str, user: dict = Depends(_current_user)):
        """The ledger of one section (events with a short excerpt) and the attribution it produces."""
        ctx.accessible_project(user, project_id)
        sec = _section_of(project_id, section_id)
        events = ctx.repo.list_provenance_events(project_id, section_id)
        return {
            "authorship": _section_authorship_for(project_id, sec),
            "events": [
                {
                    "id": e["id"], "kind": e["kind"], "source": e["source"], "words": e["words"],
                    "declared": e["declared"], "created_at": e["created_at"], "created_by": e["created_by"],
                    "excerpt": (e["text"] or "")[:200],
                }
                for e in events
            ],
        }

    @app.post("/projects/{project_id}/sections/{section_id}/provenance/paste")
    def post_section_paste(project_id: str, section_id: str, body: PasteIn, user: dict = Depends(_current_user)):
        """Editor reports text pasted from outside the document."""
        ctx.owned_project(user, project_id)
        sec = _section_of(project_id, section_id)
        words = count_words(body.text)
        if words < MIN_PASTE_WORDS:
            return {"recorded": False, "reason": f"colagens com menos de {MIN_PASTE_WORDS} palavras não são registradas"}
        _ensure_ledger(project_id, sec)
        ev = ctx.repo.add_provenance_event(
            project_id, section_id, "paste", "client", words, body.text.strip(), {}, user.get("email")
        )
        return {"recorded": True, "event_id": ev["id"], "words": words}

    # ── Detecção de paráfrases ────────────────────────────────────────

    @app.get("/projects/{project_id}/provenance/pending")
    def get_pending_paraphrases(project_id: str, user: dict = Depends(_current_user)):
        """What is still unreviewed before the manuscript export."""
        ctx.owned_project(user, project_id)
        embedder = embeddings.resolve(ctx.client)
        if embedder is None:
            return {"available": False, "total": 0, "sections": []}
        quotes = [c.get("quote", "") for c in ctx.repo.list_project_claims(project_id)]
        rows, total = [], 0
        try:
            for sec in ctx.repo.list_sections(project_id):
                events = ctx.repo.list_provenance_events(project_id, sec["id"])
                found = paraphrase.find(
                    sec.get("content"), events,
                    lambda texts, task: embedder.embed(texts, task=task, operation="paraphrase"), quotes,
                )
                if found:
                    rows.append({"section_id": sec["id"], "title": sec.get("title"), "count": len(found)})
                    total += len(found)
        except LLMUnavailable:
            return {"available": False, "total": 0, "sections": []}
        return {"available": True, "total": total, "sections": rows}

    @app.post("/projects/{project_id}/sections/{section_id}/provenance/paraphrases")
    def find_paraphrases(project_id: str, section_id: str, user: dict = Depends(_current_user)):
        """Suggest paragraphs that look like a rewrite of an AI draft (by meaning)."""
        ctx.owned_project(user, project_id)
        sec = _section_of(project_id, section_id)
        embedder = embeddings.resolve(ctx.client)
        if embedder is None:
            return {
                "available": False, "suggestions": [],
                "notice": "A comparação por significado precisa de um modelo de embeddings ativo (EMBED_PROVIDER).",
            }
        events = ctx.repo.list_provenance_events(project_id, section_id)
        quotes = [c.get("quote", "") for c in ctx.repo.list_project_claims(project_id)]
        try:
            found = paraphrase.find(
                sec.get("content"), events,
                lambda texts, task: embedder.embed(texts, task=task, operation="paraphrase"), quotes,
            )
        except LLMUnavailable:
            return {
                "available": False, "suggestions": [],
                "notice": "O modelo de embeddings está indisponível agora. Tente de novo em instantes.",
            }
        return {
            "available": True,
            "suggestions": found,
            "notice": None,
            "limits": [
                "São sugestões por semelhança de significado com rascunhos da IA registrados aqui. "
                "Dois textos sobre o mesmo tema também ficam próximos: só você sabe se este parágrafo parte do rascunho."
            ],
        }

    @app.post("/projects/{project_id}/sections/{section_id}/provenance/paraphrases/dismiss")
    def dismiss_paraphrase(
        project_id: str, section_id: str, body: DismissParaphraseIn, user: dict = Depends(_current_user)
    ):
        """Author says this paragraph is NOT a rewrite of an AI draft."""
        ctx.owned_project(user, project_id)
        sec = _section_of(project_id, section_id)
        text = body.text.strip()
        _ensure_ledger(project_id, sec)
        ev = ctx.repo.add_provenance_event(
            project_id, section_id, DISMISSED_KIND, "client", count_words(text), text, {}, user.get("email")
        )
        return {"recorded": True, "event_id": ev["id"]}

    @app.post("/projects/{project_id}/sections/{section_id}/provenance/paraphrases/confirm")
    def confirm_paraphrase(
        project_id: str, section_id: str, body: ConfirmParaphraseIn, user: dict = Depends(_current_user)
    ):
        """Author confirms this paragraph IS a rewrite of an AI draft."""
        ctx.owned_project(user, project_id)
        sec = _section_of(project_id, section_id)
        text = body.text.strip()
        words = count_words(text)
        if words < paraphrase.MIN_BLOCK_WORDS:
            raise HTTPException(422, f"Informe um parágrafo com ao menos {paraphrase.MIN_BLOCK_WORDS} palavras.")
        if text not in _section_blocks(sec.get("content")):
            raise HTTPException(422, "Este parágrafo não está na seção (o texto pode ter mudado). Procure de novo.")
        _ensure_ledger(project_id, sec)
        ev = ctx.repo.add_provenance_event(
            project_id, section_id, "ai_paraphrase", "client", words, text,
            {"from_event": body.event_id}, user.get("email"),
        )
        return {"recorded": True, "event_id": ev["id"], "authorship": _section_authorship_for(project_id, sec)}

    @app.post("/projects/{project_id}/sections/{section_id}/provenance/events/{event_id}/declare")
    def declare_paste(
        project_id: str, section_id: str, event_id: str, body: DeclarePasteIn, user: dict = Depends(_current_user)
    ):
        """Author states that a pasted text is their own (or clears that statement)."""
        ctx.owned_project(user, project_id)
        sec = _section_of(project_id, section_id)
        ev = ctx.repo.declare_provenance_event(project_id, event_id, body.declared)
        if not ev or ev["section_id"] != section_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Registro não encontrado.")
        return _section_authorship_for(project_id, sec)
