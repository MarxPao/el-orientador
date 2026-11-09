"""Roteador para busca e importação direta em repositórios abertos (T7.1).

Endpoints:
- GET /repositories/search: Busca federada em SciELO, CAPES/BDTD e OpenAlex.
- POST /projects/{project_id}/documents/import-repository: Importa documento e baixa PDF de acesso aberto se disponível.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials

from .. import storage as file_store
from ..main_models import RepositoryImportIn
from ..repo import DocumentExists
from ..repositories import download_open_pdf, federated_search
from ._ctx import AppCtx

logger = logging.getLogger(__name__)


def register_routes(app: FastAPI, ctx: AppCtx) -> None:
    bearer = ctx.bearer

    def _current_user(
        cred: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> dict:
        return ctx.current_user(None, cred)

    @app.get("/repositories/search")
    def search_repositories(
        q: str = Query(..., min_length=2, description="Termo de pesquisa"),
        source: str = Query("all", description="scielo | bdtd | openalex | all"),
        oa_only: bool = Query(False, description="Apenas acesso aberto com PDF"),
        limit: int = Query(10, ge=1, le=25, description="Limite de resultados"),
        user: dict = Depends(_current_user),
    ):
        """Busca federada em repositórios acadêmicos abertos sem LLM."""
        fetcher = getattr(ctx, "fetch_json", None)
        kwargs = {"fetch": fetcher} if fetcher else {}
        return federated_search(
            query=q,
            source=source,
            oa_only=oa_only,
            limit=limit,
            **kwargs,
        )

    @app.post("/projects/{project_id}/documents/import-repository", status_code=status.HTTP_201_CREATED)
    def import_from_repository(
        project_id: str,
        body: RepositoryImportIn,
        user: dict = Depends(_current_user),
    ):
        """Importa referência de repositório aberto e baixa PDF integral caso disponível."""
        ctx.owned_project(user, project_id)

        existing = ctx.repo.list_documents(project_id)
        if body.doi and any((d.get("doi") or "").lower() == body.doi.lower() for d in existing):
            raise HTTPException(status.HTTP_409_CONFLICT, "Este DOI já está na biblioteca do projeto.")

        if any(d.get("title", "").strip().lower() == body.title.strip().lower() for d in existing):
            raise HTTPException(status.HTTP_409_CONFLICT, "Um documento com este título já está na biblioteca.")

        doc_data = {
            "doi": body.doi,
            "title": body.title.strip(),
            "authors": body.authors,
            "year": body.year,
            "venue": body.venue,
            "metadata_source": body.repository,
            "storage_path": None,
            "analysis": "abstract_only",
            "status": "pending",
        }

        try:
            doc = ctx.repo.create_document(project_id, doc_data)
        except DocumentExists:
            raise HTTPException(status.HTTP_409_CONFLICT, "Documento já existe no projeto.") from None

        download_warning = None
        if body.fetch_pdf and body.pdf_url:
            try:
                pdf_bytes = download_open_pdf(body.pdf_url)
                key = f"{project_id}/{doc['id']}.pdf"
                file_store.write_atomic(ctx.storage_dir, key, pdf_bytes)
                ctx.repo.update_document(doc["id"], storage_path=key, analysis="full_text")
                if ctx.job_queue:
                    ctx.job_queue.enqueue(doc["id"])
            except Exception as exc:
                download_warning = f"Metadados importados, mas não foi possível baixar o PDF automaticamente: {exc}"
                logger.warning("Falha ao baixar PDF de %s: %s", body.pdf_url, exc)

        saved = ctx.repo.get_document(doc["id"])
        return {
            "document": saved,
            "warning": download_warning,
            "downloaded": saved.get("storage_path") is not None,
        }
