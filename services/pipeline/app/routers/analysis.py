"""Roteador de análise textual, dissecação e comparação de fontes.

Endpoints: /projects/{id}/text-analysis, /documents/{id}/dissect, /text-analysis/compare
"""
from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from ..authorship import compute_project_authorship, count_words
from ..main_models import TextCompareIn
from ..text_analysis import (
    analyze_project_texts,
    compare_and_connect_passages,
    extract_verified_passages_deterministic,
)
from ._ctx import AppCtx


def register_routes(app: FastAPI, ctx: AppCtx) -> None:
    bearer = ctx.bearer

    def _current_user(
        request: Request,
        cred: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> dict:
        return ctx.current_user(request, cred)

    def _build_raw_claims(project_id: str, docs_by_id: dict) -> list:
        raw = []
        for c in ctx.repo.list_project_claims(project_id):
            doc = docs_by_id.get(c["document_id"]) or {}
            raw.append({
                "id": c["id"],
                "document_id": c["document_id"],
                "document_title": doc.get("title"),
                "authors": doc.get("authors") or [],
                "year": doc.get("year"),
                "statement": c["statement"],
                "quote": c["quote"],
                "page_no": c["page_no"],
                "concepts": ([{"id": c["concept_id"], "label": c["concept"]}] if c.get("concept_id") else []),
            })
        return raw

    # ── Text Analysis Workbench ───────────────────────────────────────

    @app.get("/projects/{project_id}/text-analysis")
    def get_project_text_analysis(project_id: str, user: dict = Depends(_current_user)):
        project = ctx.accessible_project(user, project_id)
        docs = ctx.repo.list_documents(project_id)
        docs_by_id = {d["id"]: d for d in docs}
        raw_claims = _build_raw_claims(project_id, docs_by_id)
        sections = ctx.repo.list_sections(project_id)
        return analyze_project_texts(project, docs, raw_claims, sections)

    @app.post("/projects/{project_id}/documents/{document_id}/dissect")
    def post_dissect_document(project_id: str, document_id: str, user: dict = Depends(_current_user)):
        project = ctx.owned_project(user, project_id)
        doc = ctx.repo.get_document(document_id)
        if not doc or doc["project_id"] != project_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado.")
        existing_claims = ctx.repo.list_claims(document_id)
        if not existing_claims:
            pages = ctx.repo.get_pages(document_id)
            if not pages and doc.get("storage_path"):
                from ..jobs import parse_pdf
                try:
                    pages = parse_pdf(ctx.storage_dir / doc["storage_path"])
                    ctx.repo.save_pages(document_id, pages)
                except Exception:
                    pages = []
            if pages:
                extracted = extract_verified_passages_deterministic(pages, doc.get("title") or "Documento")
                if extracted:
                    ctx.repo.add_claims(document_id, extracted, "deterministic_dissector_v1", "dissect_v1")
                    ctx.repo.update_document(document_id, status="extracted")
                    ctx.repo.log_ai_usage(project_id, "dissect_pdf", document_id, "deterministic_dissector_v1", "dissect_v1")
        docs = ctx.repo.list_documents(project_id)
        docs_by_id = {d["id"]: d for d in docs}
        raw_claims = _build_raw_claims(project_id, docs_by_id)
        sections = ctx.repo.list_sections(project_id)
        return analyze_project_texts(project, docs, raw_claims, sections)

    @app.post("/projects/{project_id}/text-analysis/compare")
    def post_compare_and_connect_texts(
        project_id: str,
        body: TextCompareIn,
        user: dict = Depends(_current_user),
    ):
        project = ctx.accessible_project(user, project_id)
        all_claims = ctx.repo.list_project_claims(project_id)
        claim_a = next((c for c in all_claims if c["id"] == body.claim_a_id), None)
        claim_b = next((c for c in all_claims if c["id"] == body.claim_b_id), None)
        if not claim_a or not claim_b:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Selecione dois trechos verificados válidos para comparar e conectar.")

        doc_a = ctx.repo.get_document(claim_a["document_id"]) or {}
        doc_b = ctx.repo.get_document(claim_b["document_id"]) or {}
        sec = ctx.repo.get_section(project_id, body.section_id) if body.section_id else None
        sec_title = sec["title"] if sec else project.get("title", "Referencial Teórico")

        comparison = compare_and_connect_passages(
            claim_a=claim_a, claim_b=claim_b, doc_a=doc_a, doc_b=doc_b,
            relation_type=body.relation_type, student_analysis=body.student_analysis,
            section_title=sec_title, intensity=body.intensity, client=ctx.client,
        )

        updated_sec = None
        if body.insert_into_section and sec:
            ctx.owned_project(user, project_id)
            content_dict = dict(sec.get("content") or {"type": "doc", "content": []})
            if not isinstance(content_dict.get("content"), list):
                content_dict = {"type": "doc", "content": []}
            auth_meta = dict(content_dict.get("_authorship") or {"polished_words": 0, "ai_drafted_words": 0})
            auth_meta["last_intensity"] = body.intensity
            words_added = count_words(comparison["synthesis_text"])
            student_words = count_words(body.student_analysis or "")
            if comparison["mode_used"] == "scaffold_socratico":
                auth_meta["polished_words"] = int(auth_meta.get("polished_words", 0)) + max(1, words_added - student_words)
            else:
                auth_meta["ai_drafted_words"] = int(auth_meta.get("ai_drafted_words", 0)) + max(1, words_added - student_words)
            content_dict["content"] = list(content_dict["content"]) + [
                {"type": "paragraph", "content": [{"type": "text", "text": comparison["synthesis_text"]}]}
            ]
            content_dict["_authorship"] = auth_meta
            updated_sec = ctx.repo.update_section(project_id, sec["id"], content=content_dict, version_by="ai", force_version=True)
            sec_concepts = set(sec.get("concept_ids") or [])
            for c_item in (claim_a, claim_b):
                if c_item.get("concept_id"):
                    sec_concepts.add(c_item["concept_id"])
            ctx.repo.set_section_concepts(sec["id"], list(sec_concepts))
            updated_sec["concept_ids"] = list(sec_concepts)

        ctx.repo.log_ai_usage(
            project_id, "compare_texts", sec["id"] if sec else None,
            getattr(ctx.client, "model", None) if comparison["llm_used"] else "scaffold",
            f"compare_{body.relation_type}_{body.intensity}",
        )

        all_sections = ctx.repo.list_sections(project_id)
        verified_quotes = [c.get("quote", "") for c in all_claims]
        ev: dict = {}
        for e in ctx.repo.list_provenance_events(project_id):
            ev.setdefault(e["section_id"], []).append(e)
        return {
            **comparison,
            "updated_section": updated_sec,
            "project_authorship": compute_project_authorship(all_sections, verified_quotes=verified_quotes, events_by_section=ev),
        }
