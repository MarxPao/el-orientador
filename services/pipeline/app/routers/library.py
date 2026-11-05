"""Roteador de biblioteca de documentos.

Endpoints: /projects/{id}/documents, /claims, /text-analysis, /search, /bibliography
"""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials

from .. import embeddings
from .. import storage as file_store
from ..metadata import InvalidDOI, LookupFailed, NotFound, lookup_doi, normalize_doi
from ..repo import DocumentExists
from ..search import rrf, snippet, tokens as search_tokens
from ..bibliography import STYLES, export_bibliography, parse_citation
from ..consistency import check_consistency
from ..text_analysis import (
    analyze_project_texts,
    compare_and_connect_passages,
    extract_verified_passages_deterministic,
)
from ..authorship import count_words, compute_project_authorship
from ..llm_gateway import LLMUnavailable
from ._ctx import AppCtx
from ..main_models import (
    DoiIn,
    ImportCitationIn,
    TextCompareIn,
    LLM_DOWN_MSG,
    CONTEXT_CHARS,
)


def register_routes(app: FastAPI, ctx: AppCtx) -> None:  # noqa: C901
    bearer = ctx.bearer

    def _current_user(
        request: Request,
        cred: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> dict:
        return ctx.current_user(request, cred)

    def _max_pdf_bytes() -> int:
        import os
        try:
            return max(0, int(float(os.environ.get("MAX_PDF_MB") or 0) * 1024 * 1024))
        except ValueError:
            return 0

    def _metadata_for(raw_doi: str) -> dict:
        try:
            return lookup_doi(normalize_doi(raw_doi), ctx.fetch_json)
        except InvalidDOI:
            raise HTTPException(422, "DOI inválido. Exemplo: 10.1000/xyz123.") from None
        except NotFound:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "DOI não encontrado nas bases consultadas.") from None
        except LookupFailed:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "As bases bibliográficas não responderam. Tente novamente.") from None

    def _add_document(project_id: str, data: dict) -> dict:
        try:
            return ctx.repo.create_document(project_id, data)
        except DocumentExists:
            raise HTTPException(status.HTTP_409_CONFLICT, "Este DOI já está na biblioteca do projeto.") from None

    # ── Documentos ───────────────────────────────────────────────────

    @app.get("/projects/{project_id}/documents")
    def list_documents(project_id: str, user: dict = Depends(_current_user)):
        ctx.owned_project(user, project_id)
        return ctx.repo.list_documents(project_id)

    @app.post("/projects/{project_id}/documents/doi", status_code=201)
    def add_by_doi(project_id: str, body: DoiIn, user: dict = Depends(_current_user)):
        ctx.owned_project(user, project_id)
        meta = _metadata_for(body.doi)
        return _add_document(project_id, {**meta, "storage_path": None, "analysis": "abstract_only", "status": "pending"})

    @app.post("/projects/{project_id}/documents/import-citation", status_code=201)
    def import_citation(project_id: str, body: ImportCitationIn, user: dict = Depends(_current_user)):
        ctx.owned_project(user, project_id)
        parsed = parse_citation(body.raw_citation, body.citation_style)
        if not parsed or not parsed.get("title"):
            raise HTTPException(422, "Não foi possível interpretar a citação. Verifique o formato.")
        return _add_document(project_id, {**parsed, "storage_path": None, "analysis": "abstract_only", "status": "pending"})

    @app.post("/projects/{project_id}/documents/upload", status_code=201)
    async def upload_pdf(
        project_id: str,
        file: UploadFile = File(...),
        title: str | None = Form(default=None, max_length=300),
        doi: str | None = Form(default=None, max_length=300),
        user: dict = Depends(_current_user),
    ):
        ctx.owned_project(user, project_id)
        cap = _max_pdf_bytes()
        content = await file.read(cap + 1) if cap else await file.read()
        if cap and len(content) > cap:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, f"O PDF excede o limite de {cap // (1024 * 1024)} MB.")
        if not content.startswith(b"%PDF-"):
            raise HTTPException(422, "O arquivo enviado não é um PDF.")
        if doi:
            data = _metadata_for(doi)
        else:
            fallback = Path(file.filename or "documento").stem[:300]
            data = {"doi": None, "title": (title or fallback).strip(), "authors": [], "year": None, "venue": None,
                    "retracted": False, "metadata_source": "manual" if title else "filename"}
        if not data["title"]:
            raise HTTPException(422, "Informe o título do documento.")
        key = f"{project_id}/{uuid.uuid4()}.pdf"
        file_store.write_atomic(ctx.storage_dir, key, content)
        try:
            doc = _add_document(project_id, {**data, "storage_path": key, "analysis": "full_text", "status": "pending"})
        except HTTPException:
            file_store.delete(ctx.storage_dir, key)
            raise
        ctx.job_queue.enqueue(doc["id"])
        return doc

    @app.get("/projects/{project_id}/documents/{document_id}/file")
    def document_file(project_id: str, document_id: str, user: dict = Depends(_current_user)):
        ctx.owned_project(user, project_id)
        doc = ctx.repo.get_document(document_id)
        if not doc or doc["project_id"] != project_id or not doc.get("storage_path"):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "PDF não encontrado.")
        try:
            path = file_store.resolve(ctx.storage_dir, doc["storage_path"])
        except file_store.StorageError:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "PDF não encontrado.") from None
        if not path.is_file():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "PDF não encontrado.")
        return FileResponse(path, media_type="application/pdf", headers={"Content-Disposition": "inline"})

    @app.delete("/projects/{project_id}/documents/{document_id}")
    def delete_document(project_id: str, document_id: str, user: dict = Depends(_current_user)):
        ctx.owned_project(user, project_id)
        doc = ctx.repo.get_document(document_id)
        if not doc or doc["project_id"] != project_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado.")
        if doc.get("storage_path"):
            file_store.delete(ctx.storage_dir, doc["storage_path"])
        ctx.repo.delete_document(document_id)
        return {"ok": True}

    # ── Claims / evidências ───────────────────────────────────────────

    @app.get("/projects/{project_id}/documents/{document_id}/claims")
    def list_claims(project_id: str, document_id: str, user: dict = Depends(_current_user)):
        ctx.owned_project(user, project_id)
        doc = ctx.repo.get_document(document_id)
        if not doc or doc["project_id"] != project_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado.")
        return ctx.repo.list_claims(document_id)

    @app.get("/projects/{project_id}/claims")
    def list_all_project_claims(project_id: str, user: dict = Depends(_current_user)):
        """Todas as evidências verificadas do projeto com metadados bibliográficos."""
        ctx.accessible_project(user, project_id)
        docs = {d["id"]: d for d in ctx.repo.list_documents(project_id)}
        out = []
        for c in ctx.repo.list_project_claims(project_id):
            doc = docs.get(c["document_id"]) or ctx.repo.get_document(c["document_id"]) or {}
            out.append({
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
        return out

    # ── Análise textual ───────────────────────────────────────────────

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

    # ── Busca ─────────────────────────────────────────────────────────

    @app.get("/projects/{project_id}/search")
    def search_project(
        project_id: str,
        q: str = Query(..., min_length=2, max_length=400),
        limit: int = Query(default=10, ge=1, le=50),
        user: dict = Depends(_current_user),
    ):
        ctx.accessible_project(user, project_id)
        claims = ctx.repo.list_project_claims(project_id)
        docs = {d["id"]: d for d in ctx.repo.list_documents(project_id)}
        embedder = embeddings.resolve(ctx.client)
        kw_hits = {c["id"]: i for i, c in enumerate(ctx.repo.keyword_search(project_id, q, limit * 2))}
        vec_hits: dict[str, int] = {}
        if embedder:
            try:
                vecs = embedder.embed([q], task="retrieval.query", operation="search")
                vec_hits = {c["id"]: i for i, c in enumerate(ctx.repo.vector_search(project_id, vecs[0], limit * 2))}
            except LLMUnavailable:
                pass
        combined = rrf(kw_hits, vec_hits) if vec_hits else {k: float(v) for k, v in kw_hits.items()}
        top_ids = sorted(combined, key=lambda x: combined[x])[:limit]
        result = []
        for c in claims:
            if c["id"] not in top_ids:
                continue
            doc = docs.get(c["document_id"]) or {}
            result.append({
                "id": c["id"], "document_id": c["document_id"], "document_title": doc.get("title"),
                "authors": doc.get("authors") or [], "year": doc.get("year"),
                "statement": c["statement"], "quote": c["quote"], "page_no": c["page_no"],
                "snippet": snippet(c.get("quote") or c.get("statement") or "", search_tokens(q)),
                "score": combined[c["id"]],
            })
        result.sort(key=lambda x: combined[x["id"]])
        return result

    # ── Consistência ─────────────────────────────────────────────────

    @app.get("/projects/{project_id}/consistency")
    def get_project_consistency(project_id: str, user: dict = Depends(_current_user)):
        project = ctx.accessible_project(user, project_id)
        return check_consistency(ctx.repo, project_id, project)

    # ── Bibliografia ─────────────────────────────────────────────────

    @app.get("/projects/{project_id}/bibliography")
    def get_project_bibliography(
        project_id: str,
        style: str = Query(default="abnt", regex="^[a-z0-9_-]{2,20}$"),
        user: dict = Depends(_current_user),
    ):
        project = ctx.accessible_project(user, project_id)
        docs = ctx.repo.list_documents(project_id)
        style = project.get("citation_style") or style
        if style not in STYLES:
            raise HTTPException(422, f"Estilo não suportado. Disponíveis: {', '.join(STYLES)}.")
        return {"style": style, "entries": export_bibliography(docs, style)}

    # ── Helpers privados ──────────────────────────────────────────────

    def _build_raw_claims(project_id: str, docs_by_id: dict) -> list:
        raw = []
        for c in ctx.repo.list_project_claims(project_id):
            doc = docs_by_id.get(c["document_id"]) or {}
            raw.append({
                "id": c["id"], "document_id": c["document_id"], "document_title": doc.get("title"),
                "authors": doc.get("authors") or [], "year": doc.get("year"),
                "statement": c["statement"], "quote": c["quote"], "page_no": c["page_no"],
                "concepts": ([{"id": c["concept_id"], "label": c["concept"]}] if c.get("concept_id") else []),
            })
        return raw
