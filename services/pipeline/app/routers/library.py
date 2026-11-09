"""Roteador de biblioteca de documentos.

Endpoints: /projects/{id}/documents, /claims, /search, /consistency, /bibliography
"""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, Response
from fastapi.security import HTTPAuthorizationCredentials

from .. import embeddings
from .. import storage as file_store
from ..metadata import InvalidDOI, LookupFailed, NotFound, lookup_doi, normalize_doi
from ..repo import DocumentExists
from ..search import rrf, snippet, tsquery
from ..bibliography import STYLES, export_bibliography, parse_citation
from ..consistency import check_consistency
from ..authorship import _cite
from ..llm_gateway import LLMUnavailable
from ._ctx import AppCtx
from ..main_models import (
    DoiIn,
    ImportCitationIn,
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
        doi_match = re.search(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", body.raw_citation)
        doi = normalize_doi(doi_match.group(0)) if doi_match else None

        parsed = None
        try:
            parsed = parse_citation(body.raw_citation)
        except ValueError:
            parsed = None

        target_doi = doi or (parsed.get("doi") if parsed else None)
        if target_doi:
            try:
                meta = _metadata_for(target_doi)
                parsed = {**(parsed or {}), **meta}
            except HTTPException:
                pass

        if not parsed or not parsed.get("title"):
            raise HTTPException(422, "Não foi possível interpretar a citação. Verifique o formato.")

        existing = ctx.repo.list_documents(project_id)
        if any(d.get("title", "").strip().lower() == parsed["title"].strip().lower() for d in existing):
            raise HTTPException(status.HTTP_409_CONFLICT, "Este documento já está na biblioteca do projeto.")
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
        elif title:
            data = {"doi": None, "title": title.strip(), "authors": [], "year": None, "venue": None,
                    "metadata_source": "manual"}
        else:
            fallback = Path(file.filename or "documento").stem[:300]
            data = {"doi": None, "title": fallback.strip(), "authors": [], "year": None, "venue": None,
                    "metadata_source": "filename"}
        try:
            doc = ctx.repo.create_document(project_id, {**data, "storage_path": None, "analysis": "full_text", "status": "pending"})
        except DocumentExists:
            raise HTTPException(status.HTTP_409_CONFLICT, "Este DOI já está na biblioteca do projeto.") from None
        key = f"{project_id}/{doc['id']}.pdf"
        try:
            file_store.write_atomic(ctx.storage_dir, key, content)
        except file_store.StorageError as exc:
            ctx.repo.delete_document(project_id, doc["id"])
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Falha ao gravar arquivo: {exc}") from None
        ctx.repo.update_document(doc["id"], storage_path=key)
        if ctx.job_queue:
            ctx.job_queue.enqueue(doc["id"])
        return ctx.repo.get_document(doc["id"])

    @app.get("/projects/{project_id}/documents/{document_id}/pdf")
    @app.get("/projects/{project_id}/documents/{document_id}/file")
    def get_document_pdf(project_id: str, document_id: str, user: dict = Depends(_current_user)):
        ctx.accessible_project(user, project_id)
        doc = ctx.repo.get_document(document_id)
        if not doc or doc["project_id"] != project_id or not doc.get("storage_path"):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "PDF não encontrado.")
        try:
            path = file_store.resolve(ctx.storage_dir, doc["storage_path"])
        except file_store.StorageError:
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
        ctx.repo.delete_document(project_id, document_id)
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
                "venue": doc.get("venue"),
                "doi": doc.get("doi"),
                "statement": c["statement"],
                "quote": c["quote"],
                "page_no": c["page_no"],
                "concepts": ([{"id": c["concept_id"], "label": c["concept"]}] if c.get("concept_id") else []),
            })
        return out

    # ── Busca ─────────────────────────────────────────────────────────

    @app.get("/projects/{project_id}/search")
    def search_project(
        project_id: str,
        q: str = Query(..., min_length=2, max_length=400),
        limit: int = Query(default=10, ge=1, le=50),
        user: dict = Depends(_current_user),
    ):
        ctx.accessible_project(user, project_id)
        clean_q = q.strip()
        if len(clean_q) < 2 or tsquery(clean_q) is None:
            raise HTTPException(422, "A consulta não contém termos de busca válidos.")

        embedder = embeddings.resolve(ctx.client)
        embed_model = getattr(embedder, "embed_model", None) if embedder else None
        coverage = ctx.repo.chunk_stats(project_id, embed_model)

        kw_hits = ctx.repo.search_keyword(project_id, clean_q, limit=max(20, limit * 2))

        mode = "keyword"
        notice = None
        vec_hits = []

        if embedder and coverage["embedded"] > 0:
            try:
                vecs = embedder.embed([clean_q], task="query")
                vec_hits = ctx.repo.search_vector(project_id, vecs[0], model=embed_model, limit=max(20, limit * 2))
                mode = "hybrid"
            except (LLMUnavailable, Exception):
                mode = "keyword"
                notice = "Busca semântica temporariamente indisponível; usando correspondência exata."
        elif embedder and coverage["chunks"] > 0 and coverage["embedded"] == 0:
            mode = "keyword"
            notice = "Documentos ainda não indexados para busca semântica; usando correspondência exata."
        elif not embedder:
            mode = "keyword"
            notice = "Busca por palavras-chave: modelo de embeddings não configurado."

        lists: dict[str, list[str]] = {}
        if kw_hits:
            lists["keyword"] = [h["id"] for h in kw_hits]
        if vec_hits:
            lists["semantic"] = [h["id"] for h in vec_hits]

        if not lists:
            return {"mode": mode, "notice": notice, "coverage": coverage, "results": []}

        fused = rrf(lists)
        hits_by_id = {h["id"]: h for h in kw_hits + vec_hits}
        docs = {d["id"]: d for d in ctx.repo.list_documents(project_id)}

        results = []
        for cid, score, matched_by in fused[:limit]:
            hit = hits_by_id.get(cid)
            if not hit:
                continue
            doc = docs.get(hit["document_id"]) or ctx.repo.get_document(hit["document_id"]) or {}
            _, cite_str = _cite(doc, hit["page_no"])
            results.append({
                "id": cid,
                "document_id": hit["document_id"],
                "document_title": doc.get("title"),
                "authors": doc.get("authors") or [],
                "year": doc.get("year"),
                "page_no": hit["page_no"],
                "snippet": snippet(hit["text"], clean_q),
                "cite": cite_str,
                "matched_by": matched_by,
                "score": score,
            })
        return {
            "mode": mode,
            "notice": notice,
            "coverage": coverage,
            "results": results,
        }

    @app.post("/projects/{project_id}/library/reindex", status_code=202)
    def reindex_library(project_id: str, user: dict = Depends(_current_user)):
        ctx.owned_project(user, project_id)
        docs = ctx.repo.list_documents(project_id)
        queued = 0
        if ctx.job_queue:
            from ..jobs import STAGE_INDEX
            for d in docs:
                if d.get("storage_path") or ctx.repo.get_pages(d["id"]):
                    ctx.job_queue.enqueue(d["id"], stage=STAGE_INDEX)
                    queued += 1
        return {"queued": queued}

    # ── Consistência ─────────────────────────────────────────────────

    @app.get("/projects/{project_id}/consistency")
    def get_project_consistency(project_id: str, user: dict = Depends(_current_user)):
        ctx.accessible_project(user, project_id)
        return check_consistency(ctx.repo, project_id)

    # ── Bibliografia ─────────────────────────────────────────────────

    @app.get("/projects/{project_id}/export/bibliography")
    def export_project_bibliography(
        project_id: str,
        format: str = Query(default="abnt"),
        user: dict = Depends(_current_user),
    ):
        ctx.accessible_project(user, project_id)
        docs = ctx.repo.list_documents(project_id)
        fmt = (format or "abnt").lower()
        if fmt not in STYLES:
            raise HTTPException(422, f"Formato não suportado. Disponíveis: {', '.join(STYLES)}.")
        text, ext, media_type = export_bibliography(docs, fmt)
        filename = f"bibliografia-{project_id[:8]}.{ext}"
        return Response(
            content=text,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.get("/projects/{project_id}/bibliography")
    def get_project_bibliography(
        project_id: str,
        style: str = Query(default="abnt", pattern="^[a-z0-9_-]{2,20}$"),
        user: dict = Depends(_current_user),
    ):
        project = ctx.accessible_project(user, project_id)
        docs = ctx.repo.list_documents(project_id)
        style = (project.get("citation_style") or style).lower()
        if style not in STYLES:
            raise HTTPException(422, f"Estilo não suportado. Disponíveis: {', '.join(STYLES)}.")
        text, _, _ = export_bibliography(docs, style)
        return {"style": style, "text": text}
