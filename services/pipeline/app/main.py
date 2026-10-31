"""FastAPI app: register, login and projects (T1.1). Projects are always scoped to their owner."""
from __future__ import annotations

import os
import re
import unicodedata
from datetime import date
from enum import Enum
from typing import Literal

import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field

from .jobs import InlineQueue, JobQueue, LLMFactory, ThreadQueue
from .gaps import detect_gaps
from .metadata import FetchJson, InvalidDOI, LookupFailed, NotFound, http_fetch_json, lookup_doi, normalize_doi
from .pipeline.relate import suggest_edges
from .repo import DocumentExists, EdgeExists, EmailTaken, InMemoryRepo, PostgresRepo, Repo
from .security import TOKEN_TTL_SECONDS, create_token, decode_token, hash_password, verify_password
from .tree import initial_nodes, load_template, merge_template_with_nodes, resolve_node_states
from .gate import run_gate_turn
from .pipeline.llm import LLMClient
from .schedule import calculate_schedule
from .coherence import check_coherence
from .export_docx import build_docx_manuscript
from .reports import generate_advisor_report_payload


class WorkType(str, Enum):
    tcc = "tcc"
    pre_projeto_mestrado = "pre_projeto_mestrado"
    pre_projeto_doutorado = "pre_projeto_doutorado"
    dissertacao = "dissertacao"
    tese = "tese"
    artigo = "artigo"


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ProjectIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    work: WorkType
    institution: str | None = Field(default=None, max_length=200)
    citation_style: str = "abnt"
    deadline: date | None = None
    weekly_hours: int | None = Field(default=None, ge=1, le=100)
    research_problem: str | None = Field(default=None, max_length=2000)


def default_llm_factory():
    """GeminiClient when LLM_API_KEY is set, otherwise None (documents are parsed but not extracted)."""
    if not (os.environ.get("LLM_API_KEY") or os.environ.get("GEMINI_API_KEY")):
        return None
    from .pipeline.llm_client import GeminiClient

    return GeminiClient()


def default_repo() -> Repo:
    dsn = os.environ.get("DATABASE_URL")
    return PostgresRepo(dsn) if dsn else InMemoryRepo()


MAX_PDF_BYTES = 50 * 1024 * 1024
CONTEXT_CHARS = 250


class DoiIn(BaseModel):
    doi: str = Field(min_length=7, max_length=300)


class RelationType(str, Enum):
    apoia = "apoia"
    contrasta = "contrasta"
    estende = "estende"
    aplica = "aplica"
    critica = "critica"


class EdgeDecisionIn(BaseModel):
    action: Literal["confirm", "reject", "edit"]
    relation: RelationType | None = None
    note: str | None = Field(default=None, max_length=500)


class GapDecisionIn(BaseModel):
    status: Literal["open", "adopted_as_problem", "dismissed"]
    note: str | None = Field(default=None, max_length=1000)


class NodeUpdateIn(BaseModel):
    status: Literal["locked", "available", "done", "skipped", "needs_review"] | None = None
    queued: bool | None = None
    skipped_reason: str | None = Field(default=None, max_length=500)


class GateTurnIn(BaseModel):
    user_input: str = Field(default="", max_length=5000)
    history: list[dict[str, str]] = Field(default_factory=list)
    skip: bool = False
    skip_reason: str | None = Field(default=None, max_length=500)


class SectionIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    parent_id: str | None = None
    position: int = 0
    content: dict = Field(default_factory=dict)
    concept_ids: list[str] = Field(default_factory=list)


class SectionUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    parent_id: str | None = None
    position: int | None = None
    content: dict | None = None
    concept_ids: list[str] | None = None


class AdvisorInviteIn(BaseModel):
    advisor_email: EmailStr
    can_comment: bool = True


class CommentIn(BaseModel):
    content: str = Field(min_length=1, max_length=5000)


class CommentUpdateIn(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=5000)
    resolved: bool | None = None


def create_app(
    repo: Repo | None = None,
    fetch_json: FetchJson | None = None,
    storage_dir: Path | None = None,
    llm_factory: LLMFactory | None = None,
    job_queue: JobQueue | None = None,
    client: LLMClient | None = None,
) -> FastAPI:
    app = FastAPI(title="El Orientador API")
    repo = repo or default_repo()
    fetch_json = fetch_json or http_fetch_json
    storage_dir = Path(storage_dir or os.environ.get("STORAGE_DIR", "storage"))
    if os.environ.get("DEMO_SEED") == "1":  # opt-in demo data, see app/demo.py
        from .demo import seed_demo

        seed_demo(repo, storage_dir)
    llm_factory = llm_factory or default_llm_factory
    job_queue = job_queue or ThreadQueue(repo, storage_dir, llm_factory)
    if client is None and llm_factory:
        client = llm_factory()
    origins = os.environ.get("WEB_ORIGINS", "http://localhost:3000").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    bearer = HTTPBearer(auto_error=False)

    @app.get("/health")
    def health():
        return {"status": "ok", "app": "El Orientador", "version": "0.1.0-beta"}

    def current_user(
        request: Request,
        cred: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> dict:
        token = cred.credentials if (cred and cred.credentials) else request.cookies.get("orientador_token")
        user_id = decode_token(token) if token else None
        user = repo.get_user(user_id) if user_id else None
        if not user:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão inválida ou expirada. Entre novamente.")
        return user

    def public(user: dict) -> dict:
        return {"id": user["id"], "email": user["email"], "name": user["name"]}

    @app.get("/beta-metrics")
    def beta_metrics(user: dict = Depends(current_user)):
        return repo.get_beta_metrics()

    def _should_set_cookie(request: Request) -> bool:
        return (
            os.environ.get("USE_AUTH_COOKIES") == "1"
            or request.headers.get("x-auth-cookie") == "1"
            or request.query_params.get("cookie") == "1"
        )

    def _set_auth_cookie(request: Request, response: Response, token: str) -> None:
        if not _should_set_cookie(request):
            return
        is_prod = os.environ.get("ENV") == "production"
        response.set_cookie(
            key="orientador_token",
            value=token,
            httponly=True,
            samesite="lax",
            max_age=TOKEN_TTL_SECONDS,
            secure=is_prod,
        )

    @app.post("/auth/register", status_code=201)
    def register(body: RegisterIn, request: Request, response: Response):
        try:
            user = repo.create_user(body.email, body.name, hash_password(body.password))
        except EmailTaken:
            raise HTTPException(status.HTTP_409_CONFLICT, "Este e-mail já está cadastrado.") from None
        token = create_token(user["id"])
        _set_auth_cookie(request, response, token)
        return {"user": public(user), "token": token}

    @app.post("/auth/login")
    def login(body: LoginIn, request: Request, response: Response):
        user = repo.get_user_by_email(body.email)
        # same message for unknown e-mail and wrong password: do not reveal which accounts exist
        if not user or not verify_password(body.password, user["password_hash"]):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha incorretos.")
        token = create_token(user["id"])
        _set_auth_cookie(request, response, token)
        return {"user": public(user), "token": token}

    @app.post("/auth/logout")
    def logout(response: Response):
        response.delete_cookie(key="orientador_token")
        return {"ok": True}

    @app.get("/me")
    def me(user: dict = Depends(current_user)):
        return public(user)

    @app.post("/projects", status_code=201)
    def create_project(body: ProjectIn, user: dict = Depends(current_user)):
        data = body.model_dump(mode="json")
        return repo.create_project(user["id"], data)

    @app.get("/projects")
    def list_projects(user: dict = Depends(current_user)):
        return repo.list_projects(user["id"])

    @app.get("/projects/{project_id}")
    def get_project(project_id: str, user: dict = Depends(current_user)):
        return accessible_project(user, project_id)

    def owned_project(user: dict, project_id: str) -> dict:
        project = repo.get_project(user["id"], project_id)
        if not project:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Projeto não encontrado.")
        return project

    def accessible_project(user: dict, project_id: str) -> dict:
        project = repo.get_project(user["id"], project_id)
        if project:
            return project
        if repo.is_advisor(project_id, user.get("email", "")):
            adv_project = repo.get_project_by_id(project_id)
            if adv_project:
                return adv_project
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Projeto não encontrado.")

    def add_document(project_id: str, data: dict) -> dict:
        try:
            return repo.create_document(project_id, data)
        except DocumentExists:
            raise HTTPException(status.HTTP_409_CONFLICT, "Este DOI já está na biblioteca do projeto.") from None

    def metadata_for(raw_doi: str) -> dict:
        try:
            return lookup_doi(normalize_doi(raw_doi), fetch_json)
        except InvalidDOI:
            raise HTTPException(422, "DOI inválido. Exemplo: 10.1000/xyz123.") from None
        except NotFound:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "DOI não encontrado nas bases consultadas.") from None
        except LookupFailed:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "As bases bibliográficas não responderam. Tente novamente.") from None

    @app.get("/projects/{project_id}/documents")
    def list_documents(project_id: str, user: dict = Depends(current_user)):
        owned_project(user, project_id)
        return repo.list_documents(project_id)

    @app.post("/projects/{project_id}/documents/doi", status_code=201)
    def add_by_doi(project_id: str, body: DoiIn, user: dict = Depends(current_user)):
        owned_project(user, project_id)
        meta = metadata_for(body.doi)  # metadata comes from Crossref/OpenAlex, never from an LLM
        return add_document(project_id, {**meta, "storage_path": None, "analysis": "abstract_only", "status": "pending"})

    @app.post("/projects/{project_id}/documents/upload", status_code=201)
    async def upload_pdf(
        project_id: str,
        file: UploadFile = File(...),
        title: str | None = Form(default=None, max_length=300),
        doi: str | None = Form(default=None, max_length=300),
        user: dict = Depends(current_user),
    ):
        owned_project(user, project_id)
        content = await file.read(MAX_PDF_BYTES + 1)
        if len(content) > MAX_PDF_BYTES:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "O PDF excede o limite de 50 MB.")
        if not content.startswith(b"%PDF-"):
            raise HTTPException(422, "O arquivo enviado não é um PDF.")
        if doi:
            data = metadata_for(doi)
        else:
            fallback = Path(file.filename or "documento").stem[:300]
            data = {"doi": None, "title": (title or fallback).strip(), "authors": [], "year": None, "venue": None,
                    "retracted": False, "metadata_source": "manual"}
        if not data["title"]:
            raise HTTPException(422, "Informe o título do documento.")
        key = f"{project_id}/{uuid.uuid4()}.pdf"  # server-generated name: the client filename is never used on disk
        path = storage_dir / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        try:
            doc = add_document(project_id, {**data, "storage_path": key, "analysis": "full_text", "status": "pending"})
        except HTTPException:
            path.unlink(missing_ok=True)
            raise
        job_queue.enqueue(doc["id"])  # parse + extract + verify in the background
        return doc

    @app.get("/projects/{project_id}/documents/{document_id}/claims")
    def list_claims(project_id: str, document_id: str, user: dict = Depends(current_user)):
        owned_project(user, project_id)
        doc = repo.get_document(document_id)
        if not doc or doc["project_id"] != project_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado.")
        return repo.list_claims(document_id)

    @app.get("/projects/{project_id}/map")
    def knowledge_map(project_id: str, user: dict = Depends(current_user)):
        """Concept graph: one node per concept, one link per edge (status: suggested | confirmed | rejected)."""
        owned_project(user, project_id)
        edges = [
            {"id": e["id"], "source": e["source_concept"], "target": e["target_concept"], "relation": e["relation"],
             "status": e["status"], "confidence": e.get("confidence"), "rationale": e.get("rationale"),
             "display_by_default": e.get("display_by_default", True)}
            for e in repo.list_edges(project_id)
        ]
        return {"nodes": repo.list_concepts(project_id), "edges": edges, "gaps": repo.list_gaps(project_id)}

    @app.post("/projects/{project_id}/map/suggest")
    def suggest_links(project_id: str, user: dict = Depends(current_user)):
        """Ask the AI for up to 5 new link suggestions (status `suggested`, evidence on both sides)."""
        owned_project(user, project_id)
        client = llm_factory()
        if client is None:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "O modelo de IA não está configurado (LLM_API_KEY).")
        claims = repo.list_project_claims(project_id)
        existing = {frozenset((e["source_concept"], e["target_concept"])) for e in repo.list_edges(project_id)}
        pages = {did: repo.get_pages(did) for did in {c["document_id"] for c in claims}}
        suggestions = suggest_edges(claims, client, existing, pages)
        created = repo.add_edges(project_id, suggestions)
        repo.log_ai_usage(project_id, "relate", None, getattr(client, "model", None), "classify_relation v0.1")
        return {"created": len(created)}

    @app.get("/projects/{project_id}/edges/{edge_id}/evidence")
    def edge_evidence(project_id: str, edge_id: str, user: dict = Depends(current_user)):
        """Literal quote, page and surrounding context for both sides of a link."""
        owned_project(user, project_id)
        items = repo.get_edge_evidence(project_id, edge_id)
        if items is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Ligação não encontrada.")
        out = []
        for it in items:
            doc = repo.get_document(it["document_id"]) or {}
            pages = repo.get_pages(it["document_id"])
            page_text = pages[it["page_no"] - 1] if 1 <= it["page_no"] <= len(pages) else ""
            s, e = it.get("char_start"), it.get("char_end")
            if s is not None and e is not None and page_text:
                before, quote, after = page_text[max(0, s - CONTEXT_CHARS):s], page_text[s:e], page_text[e:e + CONTEXT_CHARS]
            else:  # no offsets: show the stored quote without context
                before, quote, after = "", it["quote"], ""
            out.append({"side": it["side"], "concept": it["concept"], "statement": it["statement"],
                        "document_id": it["document_id"], "document_title": doc.get("title"),
                        "page": it["page_no"], "quote": quote, "context_before": before, "context_after": after,
                        "has_pdf": bool(doc.get("storage_path"))})
        return sorted(out, key=lambda x: x["side"] != "source")

    @app.get("/projects/{project_id}/documents/{document_id}/file")
    def document_file(project_id: str, document_id: str, user: dict = Depends(current_user)):
        owned_project(user, project_id)
        doc = repo.get_document(document_id)
        if not doc or doc["project_id"] != project_id or not doc.get("storage_path"):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "PDF não encontrado.")
        path = (storage_dir / doc["storage_path"]).resolve()
        if not path.is_relative_to(storage_dir.resolve()) or not path.is_file():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "PDF não encontrado.")
        return FileResponse(path, media_type="application/pdf", headers={"Content-Disposition": "inline"})

    @app.patch("/projects/{project_id}/edges/{edge_id}")
    def decide_edge(project_id: str, edge_id: str, body: EdgeDecisionIn, user: dict = Depends(current_user)):
        """User decision on a link: confirm, reject (remembered, never deleted) or edit the relation type."""
        owned_project(user, project_id)
        if body.action == "edit" and body.relation is None:
            raise HTTPException(422, "Informe o novo tipo de relação.")
        if body.action == "confirm":
            fields = {"status": "confirmed"}
        elif body.action == "reject":
            fields = {"status": "rejected"}
            if body.note:
                fields["user_note"] = body.note
        else:  # editing the type is also a confirmation of the (corrected) link
            fields = {"status": "confirmed", "relation": body.relation.value}
        try:
            edge = repo.update_edge(project_id, edge_id, **fields)
        except EdgeExists:
            raise HTTPException(status.HTTP_409_CONFLICT, "Já existe uma ligação com esse tipo entre os dois conceitos.") from None
        if not edge:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Ligação não encontrada.")
        return {"id": edge["id"], "source": edge["source_concept"], "target": edge["target_concept"],
                "relation": edge["relation"], "status": edge["status"], "confidence": edge.get("confidence"),
                "rationale": edge.get("rationale"), "display_by_default": edge.get("display_by_default", True)}

    @app.post("/projects/{project_id}/gaps/detect")
    def find_project_gaps(project_id: str, user: dict = Depends(current_user)):
        """Find concept pairs without links, check against bibliographic sources (OpenAlex/Semantic Scholar)."""
        owned_project(user, project_id)
        concepts = repo.list_concepts(project_id)
        claims = repo.list_project_claims(project_id)
        linked = {frozenset((e["source_concept"], e["target_concept"])) for e in repo.list_edges(project_id)}
        known_gaps = {frozenset((g["concept_a"], g["concept_b"])) for g in repo.list_gaps(project_id)}
        detected = detect_gaps(concepts, claims, linked, known_gaps, fetch=fetch_json)
        created = repo.add_gaps(project_id, detected)
        return {"created": len(created), "gaps": created}

    @app.get("/projects/{project_id}/gaps")
    def list_project_gaps(project_id: str, user: dict = Depends(current_user)):
        owned_project(user, project_id)
        return repo.list_gaps(project_id)

    @app.patch("/projects/{project_id}/gaps/{gap_id}")
    def decide_gap(project_id: str, gap_id: str, body: GapDecisionIn, user: dict = Depends(current_user)):
        owned_project(user, project_id)
        fields = {"status": body.status}
        if body.note is not None:
            fields["note"] = body.note
        gap = repo.update_gap(project_id, gap_id, **fields)
        if not gap:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Lacuna não encontrada.")
        return gap

    @app.get("/projects/{project_id}/tree")
    def get_project_tree(project_id: str, user: dict = Depends(current_user)):
        """Progress tree: phases, nodes, prerequisites, typical time and current status."""
        project = accessible_project(user, project_id)
        template = load_template(project.get("work", "tcc"))
        nodes = repo.get_progress_nodes(project_id)
        if not nodes:
            nodes = repo.save_progress_nodes(project_id, initial_nodes(template))
        resolved = resolve_node_states(template, nodes)
        for r in resolved:
            orig = next((n for n in nodes if n["node_key"] == r["node_key"]), None)
            if orig and orig["status"] != r["status"]:
                repo.update_progress_node(project_id, r["node_key"], status=r["status"])
        return merge_template_with_nodes(template, resolved)

    @app.patch("/projects/{project_id}/tree/nodes/{node_key}")
    def update_project_node(project_id: str, node_key: str, body: NodeUpdateIn, user: dict = Depends(current_user)):
        """Update a progress node status or research queue flag."""
        project = owned_project(user, project_id)
        template = load_template(project.get("work", "tcc"))
        node_def = next((n for n in template["nodes"] if n["key"] == node_key), None)
        if not node_def:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Nó não encontrado no template do projeto.")
        node = repo.get_progress_node(project_id, node_key)
        if not node:
            repo.save_progress_nodes(project_id, initial_nodes(template))
            node = repo.get_progress_node(project_id, node_key)
        fields = {}
        if body.status is not None:
            fields["status"] = body.status
        if body.queued is not None:
            fields["queued"] = body.queued
        if body.skipped_reason is not None:
            fields["skipped_reason"] = body.skipped_reason
        if fields:
            node = repo.update_progress_node(project_id, node_key, **fields)
        all_nodes = repo.get_progress_nodes(project_id)
        resolved = resolve_node_states(template, all_nodes)
        for r in resolved:
            orig = next((n for n in all_nodes if n["node_key"] == r["node_key"]), None)
            if orig and orig["status"] != r["status"]:
                repo.update_progress_node(project_id, r["node_key"], status=r["status"])
        return {"node_key": node_key, **node}

    @app.post("/projects/{project_id}/tree/nodes/{node_key}/gate")
    def post_gate_turn(
        project_id: str,
        node_key: str,
        body: GateTurnIn,
        user: dict = Depends(current_user),
    ):
        """Interactive Socratic Gate dialogue turn.
        Evaluates student response against rubric or records conscious skip."""
        project = owned_project(user, project_id)
        template = load_template(project.get("work", "tcc"))
        node_def = next((n for n in template["nodes"] if n["key"] == node_key), None)
        if not node_def:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Nó não encontrado no template do projeto.")

        node = repo.get_progress_node(project_id, node_key)
        if not node:
            repo.save_progress_nodes(project_id, initial_nodes(template))
            node = repo.get_progress_node(project_id, node_key)

        if body.skip:
            outcome = "pular"
            user_msg = body.user_input if body.user_input.strip() else "Solicitou pular etapa com aviso consciente."
            transcript = body.history + [
                {"role": "user", "content": user_msg},
                {
                    "role": "assistant",
                    "content": "Etapa pulada com registro de aviso consciente no relatório do orientador.",
                },
            ]
            attempt = repo.save_gate_attempt(
                progress_node_id=node["id"],
                transcript=transcript,
                rubric_scores=None,
                outcome=outcome,
            )
            reason = body.skip_reason or "Avançado com aviso consciente"
            repo.update_progress_node(project_id, node_key, status="skipped", skipped_reason=reason)
            repo.log_ai_usage(project_id, "gate", node["id"], "system", "socratic_gate_v0.1")

            all_nodes = repo.get_progress_nodes(project_id)
            resolved = resolve_node_states(template, all_nodes)
            for r in resolved:
                orig = next((n for n in all_nodes if n["node_key"] == r["node_key"]), None)
                if orig and orig["status"] != r["status"]:
                    repo.update_progress_node(project_id, r["node_key"], status=r["status"])

            return {
                "done": True,
                "outcome": "pular",
                "message_to_student": "Etapa pulada com registro de aviso consciente no relatório do orientador.",
                "rubric_scores": None,
                "guidance": "Esta etapa foi pulada conscientemente.",
                "attempt_id": attempt["id"],
            }

        if client:
            all_nodes = repo.get_progress_nodes(project_id)
            done_nodes = [n["node_key"] for n in all_nodes if n["status"] in ("done", "skipped")]
            prev = (
                f"Etapas concluídas ou puladas: {', '.join(done_nodes)}"
                if done_nodes
                else "Nenhuma etapa concluída anteriormente."
            )
            result = run_gate_turn(
                client=client,
                work_type=project.get("work", "tcc"),
                node_title=node_def["title"],
                node_description=node_def.get("description", ""),
                previous_decisions=prev,
                history=body.history,
                user_input=body.user_input,
            )
        else:
            user_turns = [m for m in body.history if m.get("role") == "user"]
            if len(user_turns) < 1 and len(body.user_input.strip()) < 80:
                result = {
                    "message_to_student": f"Como você relaciona a escolha de '{node_def['title']}' com a justificativa teórica e o problema do seu trabalho?",
                    "done": False,
                    "outcome": None,
                    "rubric_scores": None,
                    "guidance": None,
                    "prompt_version": "socratic_gate_v0.1_fallback",
                }
            else:
                result = {
                    "message_to_student": "Sua resposta apresenta clareza e coerência com o escopo do projeto. Etapa liberada com sucesso!",
                    "done": True,
                    "outcome": "liberar",
                    "rubric_scores": {"clareza": 2, "justificativa": 2, "coerencia": 2},
                    "guidance": "Prossiga para a formulação dos próximos passos na árvore.",
                    "prompt_version": "socratic_gate_v0.1_fallback",
                }

        new_transcript = body.history + [
            {"role": "user", "content": body.user_input},
            {"role": "assistant", "content": result["message_to_student"]},
        ]
        outcome = result.get("outcome") or ("liberar" if result.get("done") else "em_andamento")
        attempt = repo.save_gate_attempt(
            progress_node_id=node["id"],
            transcript=new_transcript,
            rubric_scores=result.get("rubric_scores"),
            outcome=outcome,
        )
        repo.log_ai_usage(
            project_id,
            "gate",
            node["id"],
            getattr(client, "model", "fallback"),
            result.get("prompt_version"),
        )

        if result.get("done") and outcome == "liberar":
            repo.update_progress_node(project_id, node_key, status="done")
            all_nodes = repo.get_progress_nodes(project_id)
            resolved = resolve_node_states(template, all_nodes)
            for r in resolved:
                orig = next((n for n in all_nodes if n["node_key"] == r["node_key"]), None)
                if orig and orig["status"] != r["status"]:
                    repo.update_progress_node(project_id, r["node_key"], status=r["status"])
        elif result.get("done") and outcome == "revisar":
            repo.update_progress_node(project_id, node_key, status="needs_review")

        return {
            **result,
            "attempt_id": attempt["id"],
        }

    @app.get("/projects/{project_id}/tree/nodes/{node_key}/gate")
    def get_gate_attempts(
        project_id: str,
        node_key: str,
        user: dict = Depends(current_user),
    ):
        """List historical gate attempts and transcript for a node."""
        project = owned_project(user, project_id)
        node = repo.get_progress_node(project_id, node_key)
        if not node:
            return {"node_key": node_key, "attempts": []}
        attempts = repo.list_gate_attempts(node["id"])
        return {"node_key": node_key, "progress_node_id": node["id"], "attempts": attempts}

    @app.get("/projects/{project_id}/schedule")
    def get_project_schedule(
        project_id: str,
        user: dict = Depends(current_user),
    ):
        """Schedule projection and deadline alert based on remaining nodes and weekly hours."""
        project = owned_project(user, project_id)
        template = load_template(project.get("work", "tcc"))
        nodes = repo.get_progress_nodes(project_id)
        if not nodes:
            nodes = repo.save_progress_nodes(project_id, initial_nodes(template))
        return calculate_schedule(
            template=template,
            nodes_state=nodes,
            weekly_hours=project.get("weekly_hours"),
            deadline=project.get("deadline"),
        )

    DEFAULT_SECTIONS = [
        ("1. Introdução", 0),
        ("2. Referencial Teórico", 1),
        ("3. Metodologia", 2),
        ("4. Resultados e Discussão", 3),
        ("5. Considerações Finais", 4),
    ]

    @app.get("/projects/{project_id}/sections")
    def get_sections(project_id: str, user: dict = Depends(current_user)):
        """List manuscript sections with linked concepts. Auto-seeds defaults if empty."""
        accessible_project(user, project_id)
        sections = repo.list_sections(project_id)
        if not sections:
            for title, pos in DEFAULT_SECTIONS:
                repo.create_section(project_id, title=title, parent_id=None, position=pos)
            sections = repo.list_sections(project_id)
        return sections

    @app.post("/projects/{project_id}/sections")
    def post_section(project_id: str, body: SectionIn, user: dict = Depends(current_user)):
        """Create a new manuscript section."""
        owned_project(user, project_id)
        sec = repo.create_section(
            project_id=project_id,
            title=body.title,
            parent_id=body.parent_id,
            position=body.position,
            content=body.content,
        )
        if body.concept_ids:
            repo.set_section_concepts(sec["id"], body.concept_ids)
            sec["concept_ids"] = body.concept_ids
        return sec

    @app.patch("/projects/{project_id}/sections/{section_id}")
    def patch_section(
        project_id: str,
        section_id: str,
        body: SectionUpdateIn,
        user: dict = Depends(current_user),
    ):
        """Update section title, position, parent, content, or linked concepts."""
        owned_project(user, project_id)
        fields = {}
        if body.title is not None:
            fields["title"] = body.title
        if body.parent_id is not None:
            fields["parent_id"] = body.parent_id
        if body.position is not None:
            fields["position"] = body.position
        if body.content is not None:
            fields["content"] = body.content

        sec = repo.update_section(project_id, section_id, **fields)
        if not sec:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Seção não encontrada.")

        if body.concept_ids is not None:
            repo.set_section_concepts(section_id, body.concept_ids)
            sec["concept_ids"] = body.concept_ids
        return sec

    @app.delete("/projects/{project_id}/sections/{section_id}")
    def delete_section(project_id: str, section_id: str, user: dict = Depends(current_user)):
        """Delete section and recursively any child subsections."""
        owned_project(user, project_id)
        repo.delete_section(project_id, section_id)
        return {"ok": True}

    @app.get("/projects/{project_id}/coherence")
    def get_project_coherence(project_id: str, user: dict = Depends(current_user)):
        """Deterministic coherence checks: sections without source, orphan references, objectives without chapter."""
        project = owned_project(user, project_id)
        return check_coherence(repo, project_id, project)

    @app.get("/projects/{project_id}/export/docx")
    def export_project_docx(project_id: str, user: dict = Depends(current_user)):
        """Export manuscript as standard ABNT Word (.docx) with mandatory AI Usage declaration."""
        project = owned_project(user, project_id)
        project["owner_name"] = user.get("name") or "Autor(a)"
        buf = build_docx_manuscript(repo, project_id, project)
        raw_title = project.get("title", "trabalho")[:30].strip()
        ascii_title = unicodedata.normalize("NFKD", raw_title).encode("ascii", "ignore").decode("ascii")
        clean_slug = re.sub(r"[^\w\-]+", "_", ascii_title).strip("_") or "trabalho"
        filename = f"{clean_slug}.docx"
        return Response(
            content=buf.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # ------------------------------------------------------------------
    # Sprint 5: Advisor Invites, Reports & Section Comments
    # ------------------------------------------------------------------
    @app.get("/advising-projects")
    def get_advising_projects(user: dict = Depends(current_user)):
        """List all projects where current user is invited as advisor."""
        return repo.list_advising_projects(user["email"])

    @app.post("/projects/{project_id}/advisors")
    def invite_project_advisor(project_id: str, body: AdvisorInviteIn, user: dict = Depends(current_user)):
        """Invite human advisor by email (owner only)."""
        owned_project(user, project_id)
        return repo.invite_advisor(project_id, body.advisor_email, body.can_comment)

    @app.get("/projects/{project_id}/advisors")
    def list_project_advisors(project_id: str, user: dict = Depends(current_user)):
        """List invited advisors for project (owner or advisor)."""
        accessible_project(user, project_id)
        return repo.list_advisors(project_id)

    @app.delete("/projects/{project_id}/advisors/{advisor_email}")
    def delete_project_advisor(project_id: str, advisor_email: str, user: dict = Depends(current_user)):
        """Remove invited advisor (owner only)."""
        owned_project(user, project_id)
        repo.remove_advisor(project_id, advisor_email)
        return {"ok": True}

    @app.post("/projects/{project_id}/reports")
    def create_project_report(project_id: str, user: dict = Depends(current_user)):
        """Generate and persist formal progress report for advisor."""
        project = accessible_project(user, project_id)
        payload = generate_advisor_report_payload(repo, project_id, project)
        return repo.create_advisor_report(project_id, payload)

    @app.get("/projects/{project_id}/reports")
    def list_project_reports(project_id: str, user: dict = Depends(current_user)):
        """List all historical progress reports generated for project."""
        accessible_project(user, project_id)
        return repo.list_advisor_reports(project_id)

    @app.get("/projects/{project_id}/reports/{report_id}")
    def get_project_report(project_id: str, report_id: str, user: dict = Depends(current_user)):
        """Get single progress report payload (shareable / printable)."""
        accessible_project(user, project_id)
        rep = repo.get_advisor_report(project_id, report_id)
        if not rep:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Relatório não encontrado.")
        return rep

    @app.get("/projects/{project_id}/sections/{section_id}/comments")
    def list_comments(project_id: str, section_id: str, user: dict = Depends(current_user)):
        """List comments for section (student or advisor)."""
        accessible_project(user, project_id)
        return repo.list_section_comments(section_id)

    @app.post("/projects/{project_id}/sections/{section_id}/comments")
    def post_comment(project_id: str, section_id: str, body: CommentIn, user: dict = Depends(current_user)):
        """Add comment to section (student or advisor)."""
        accessible_project(user, project_id)
        return repo.create_section_comment(
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
        user: dict = Depends(current_user),
    ):
        """Update or resolve comment."""
        accessible_project(user, project_id)
        fields = {}
        if body.content is not None:
            fields["content"] = body.content
        if body.resolved is not None:
            fields["resolved"] = body.resolved
        comment = repo.update_section_comment(comment_id, **fields)
        if not comment:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Comentário não encontrado.")
        return comment

    @app.delete("/projects/{project_id}/sections/{section_id}/comments/{comment_id}")
    def delete_comment(project_id: str, section_id: str, comment_id: str, user: dict = Depends(current_user)):
        """Delete comment."""
        accessible_project(user, project_id)
        repo.delete_section_comment(comment_id)
        return {"ok": True}

    return app
