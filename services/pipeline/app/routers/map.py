"""Roteador de mapa de conhecimento.

Endpoints: /map, /edges, /gaps
"""
from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from ..gaps import detect_gaps
from ..pipeline.relate import suggest_edges
from ..repo import EdgeExists
from ._ctx import AppCtx
from ..main_models import EdgeDecisionIn, GapDecisionIn, LLM_DOWN_MSG, CONTEXT_CHARS


def register_routes(app: FastAPI, ctx: AppCtx) -> None:
    bearer = ctx.bearer

    def _current_user(
        request: Request,
        cred: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> dict:
        return ctx.current_user(request, cred)

    # ── Mapa de conceitos ─────────────────────────────────────────────

    @app.get("/projects/{project_id}/map")
    def knowledge_map(project_id: str, user: dict = Depends(_current_user)):
        """Grafo de conceitos: um nó por conceito, uma ligação por edge (status: suggested | confirmed | rejected)."""
        ctx.owned_project(user, project_id)
        edges = [
            {
                "id": e["id"], "source": e["source_concept"], "target": e["target_concept"],
                "relation": e["relation"], "status": e["status"], "confidence": e.get("confidence"),
                "rationale": e.get("rationale"), "display_by_default": e.get("display_by_default", True),
            }
            for e in ctx.repo.list_edges(project_id)
        ]
        return {"nodes": ctx.repo.list_concepts(project_id), "edges": edges, "gaps": ctx.repo.list_gaps(project_id)}

    @app.post("/projects/{project_id}/map/suggest")
    def suggest_links(project_id: str, user: dict = Depends(_current_user)):
        """Pede até 5 sugestões de ligação à IA (status `suggested`, evidência nos dois lados)."""
        ctx.owned_project(user, project_id)
        if ctx.client is None:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "O modelo de IA não está configurado (LLM_API_KEY).")
        if not ctx.client.available:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, LLM_DOWN_MSG)
        claims = ctx.repo.list_project_claims(project_id)
        existing = {frozenset((e["source_concept"], e["target_concept"])) for e in ctx.repo.list_edges(project_id)}
        pages = {did: ctx.repo.get_pages(did) for did in {c["document_id"] for c in claims}}
        suggestions = suggest_edges(claims, ctx.client, existing, pages)
        created = ctx.repo.add_edges(project_id, suggestions)
        ctx.repo.log_ai_usage(project_id, "relate", None, getattr(ctx.client, "model", None), "classify_relation v0.1")
        return {"created": len(created)}

    # ── Evidência de edge ─────────────────────────────────────────────

    @app.get("/projects/{project_id}/edges/{edge_id}/evidence")
    def edge_evidence(project_id: str, edge_id: str, user: dict = Depends(_current_user)):
        """Citação literal, página e contexto circundante dos dois lados de uma ligação."""
        ctx.owned_project(user, project_id)
        items = ctx.repo.get_edge_evidence(project_id, edge_id)
        if items is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Ligação não encontrada.")
        out = []
        for it in items:
            doc = ctx.repo.get_document(it["document_id"]) or {}
            pages = ctx.repo.get_pages(it["document_id"])
            page_text = pages[it["page_no"] - 1] if 1 <= it["page_no"] <= len(pages) else ""
            s, e = it.get("char_start"), it.get("char_end")
            if s is not None and e is not None and page_text:
                before = page_text[max(0, s - CONTEXT_CHARS):s]
                quote = page_text[s:e]
                after = page_text[e:e + CONTEXT_CHARS]
            else:
                before, quote, after = "", it["quote"], ""
            out.append({
                "side": it["side"], "concept": it["concept"], "statement": it["statement"],
                "document_id": it["document_id"], "document_title": doc.get("title"),
                "page": it["page_no"], "quote": quote, "context_before": before, "context_after": after,
                "has_pdf": bool(doc.get("storage_path")),
            })
        return sorted(out, key=lambda x: x["side"] != "source")

    @app.patch("/projects/{project_id}/edges/{edge_id}")
    def decide_edge(project_id: str, edge_id: str, body: EdgeDecisionIn, user: dict = Depends(_current_user)):
        """Decisão do utilizador sobre uma ligação: confirmar, rejeitar (fica gravado) ou editar o tipo de relação."""
        ctx.owned_project(user, project_id)
        if body.action == "edit" and body.relation is None:
            raise HTTPException(422, "Informe o novo tipo de relação.")
        if body.action == "confirm":
            fields: dict = {"status": "confirmed"}
        elif body.action == "reject":
            fields = {"status": "rejected"}
            if body.note:
                fields["user_note"] = body.note
        else:
            fields = {"status": "confirmed", "relation": body.relation.value}
        try:
            edge = ctx.repo.update_edge(project_id, edge_id, **fields)
        except EdgeExists:
            raise HTTPException(status.HTTP_409_CONFLICT, "Já existe uma ligação com esse tipo entre os dois conceitos.") from None
        if not edge:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Ligação não encontrada.")
        return {
            "id": edge["id"], "source": edge["source_concept"], "target": edge["target_concept"],
            "relation": edge["relation"], "status": edge["status"], "confidence": edge.get("confidence"),
            "rationale": edge.get("rationale"), "display_by_default": edge.get("display_by_default", True),
        }

    # ── Lacunas ───────────────────────────────────────────────────────

    @app.post("/projects/{project_id}/gaps/detect")
    def find_project_gaps(project_id: str, user: dict = Depends(_current_user)):
        """Encontra pares de conceitos sem ligações e cruza com fontes bibliográficas."""
        ctx.owned_project(user, project_id)
        concepts = ctx.repo.list_concepts(project_id)
        claims = ctx.repo.list_project_claims(project_id)
        linked = {frozenset((e["source_concept"], e["target_concept"])) for e in ctx.repo.list_edges(project_id)}
        known_gaps = {frozenset((g["concept_a"], g["concept_b"])) for g in ctx.repo.list_gaps(project_id)}
        detected = detect_gaps(concepts, claims, linked, known_gaps, fetch=ctx.fetch_json)
        created = ctx.repo.add_gaps(project_id, detected)
        return {"created": len(created), "gaps": created}

    @app.get("/projects/{project_id}/gaps")
    def list_project_gaps(project_id: str, user: dict = Depends(_current_user)):
        ctx.owned_project(user, project_id)
        return ctx.repo.list_gaps(project_id)

    @app.patch("/projects/{project_id}/gaps/{gap_id}")
    def decide_gap(project_id: str, gap_id: str, body: GapDecisionIn, user: dict = Depends(_current_user)):
        ctx.owned_project(user, project_id)
        fields: dict = {"status": body.status}
        if body.note is not None:
            fields["note"] = body.note
        gap = ctx.repo.update_gap(project_id, gap_id, **fields)
        if not gap:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Lacuna não encontrada.")
        return gap
