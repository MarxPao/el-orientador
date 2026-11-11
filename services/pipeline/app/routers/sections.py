"""Roteador de seções do manuscrito e assistência de IA.

Endpoints: /sections CRUD, /ai-assist, /export, /coherence
"""
from __future__ import annotations

import re
import unicodedata

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials

from .. import embeddings
from ..authorship import (
    coauthor_with_evidence,
    compute_project_authorship,
    count_words,
    draft_evidence_paragraph,
    mechanical_cleanup,
    polish_academic_text,
)
from ..coherence import check_coherence, extract_plain_text
from ..export_docx import build_docx_manuscript
from ..llm_gateway import LLMUnavailable
from ..provenance import attribute
from ._ctx import AppCtx
from ..main_models import (
    AiAssistIn,
    SectionIn,
    SectionUpdateIn,
    AI_ASSIST_NO_LLM_MSG,
    AI_ASSIST_DEGRADED_MSG,
)


def register_routes(app: FastAPI, ctx: AppCtx) -> None:  # noqa: C901
    bearer = ctx.bearer

    def _current_user(
        request: Request,
        cred: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> dict:
        return ctx.current_user(request, cred)

    DEFAULT_SECTIONS = [
        ("1. Introdução", 0),
        ("2. Referencial Teórico", 1),
        ("3. Metodologia", 2),
        ("4. Resultados e Discussão", 3),
        ("5. Considerações Finais", 4),
    ]

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

    def _record_ai(project_id: str, sec_before: dict, kind: str, text: str, user: dict, meta: dict) -> None:
        _ensure_ledger(project_id, sec_before)
        ctx.repo.add_provenance_event(
            project_id, sec_before["id"], kind, "server", count_words(text), text, meta, user.get("email")
        )

    def _ai_share(project_id: str, sec: dict, text: str) -> float:
        block = {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}]}
        w = attribute(block, ctx.repo.list_provenance_events(project_id, sec["id"]))
        return (w["ai_drafted_words"] + w["ai_revised_words"]) / w["total_words"] if w["total_words"] else 0.0

    def _section_authorship_for(project_id: str, sec: dict) -> dict:
        from ..authorship import compute_section_authorship
        quotes = [c.get("quote", "") for c in ctx.repo.list_project_claims(project_id)]
        return compute_section_authorship(sec, verified_quotes=quotes, events=ctx.repo.list_provenance_events(project_id, sec["id"]))

    def _mechanical_cleanup_nodes(nodes: list, only: str | None = None) -> list:
        out = []
        first_text = True
        for node in nodes:
            if not isinstance(node, dict):
                out.append(node)
                continue
            n = dict(node)
            if n.get("type") == "text" and isinstance(n.get("text"), str):
                if only is None:
                    if n["text"].strip():
                        n["text"] = mechanical_cleanup(n["text"], capitalize_first=first_text)
                elif only in n["text"]:
                    n["text"] = n["text"].replace(only, mechanical_cleanup(only, capitalize_first=False))
                first_text = False
            elif isinstance(n.get("content"), list):
                n["content"] = _mechanical_cleanup_nodes(n["content"], only)
            out.append(n)
        return out

    # ── CRUD de seções ────────────────────────────────────────────────

    @app.get("/projects/{project_id}/sections")
    def get_sections(project_id: str, user: dict = Depends(_current_user)):
        """Lista seções do manuscrito. Semeia padrões se vazio."""
        ctx.accessible_project(user, project_id)
        sections = ctx.repo.list_sections(project_id)
        if not sections:
            for title, pos in DEFAULT_SECTIONS:
                ctx.repo.create_section(project_id, title=title, parent_id=None, position=pos)
            sections = ctx.repo.list_sections(project_id)
        return sections

    @app.post("/projects/{project_id}/sections")
    def post_section(project_id: str, body: SectionIn, user: dict = Depends(_current_user)):
        ctx.owned_project(user, project_id)
        sec = ctx.repo.create_section(
            project_id=project_id, title=body.title, parent_id=body.parent_id,
            position=body.position, content=body.content,
        )
        if body.concept_ids:
            ctx.repo.set_section_concepts(sec["id"], body.concept_ids)
            sec["concept_ids"] = body.concept_ids
        return sec

    @app.patch("/projects/{project_id}/sections/{section_id}")
    def patch_section(
        project_id: str, section_id: str, body: SectionUpdateIn, user: dict = Depends(_current_user)
    ):
        ctx.owned_project(user, project_id)
        existing_sec = ctx.repo.get_section(project_id, section_id)
        if not existing_sec:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Seção não encontrada.")

        fields: dict = {}
        if body.title is not None:
            fields["title"] = body.title
        if body.parent_id is not None:
            fields["parent_id"] = body.parent_id
        if body.position is not None:
            fields["position"] = body.position
        if body.content is not None:
            new_content = dict(body.content)
            old_content = existing_sec.get("content")
            if isinstance(old_content, dict) and "_authorship" in old_content:
                new_content["_authorship"] = old_content["_authorship"]
            elif "_authorship" in new_content:
                new_content.pop("_authorship", None)
            fields["content"] = new_content

        sec = ctx.repo.update_section(project_id, section_id, version_by=user.get("email"), **fields)
        if not sec:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Seção não encontrada.")

        if body.concept_ids is not None:
            ctx.repo.set_section_concepts(section_id, body.concept_ids)
            sec["concept_ids"] = body.concept_ids
        return sec

    @app.delete("/projects/{project_id}/sections/{section_id}")
    def delete_section(project_id: str, section_id: str, user: dict = Depends(_current_user)):
        ctx.owned_project(user, project_id)
        ctx.repo.delete_section(project_id, section_id)
        return {"ok": True}

    # ── Coerência ─────────────────────────────────────────────────────

    @app.get("/projects/{project_id}/coherence")
    def get_project_coherence(project_id: str, user: dict = Depends(_current_user)):
        project = ctx.owned_project(user, project_id)
        return check_coherence(ctx.repo, project_id, project)

    # ── Assistência de IA ─────────────────────────────────────────────

    @app.post("/projects/{project_id}/sections/{section_id}/ai-assist")
    def post_section_ai_assist(  # noqa: C901
        project_id: str,
        section_id: str,
        body: AiAssistIn,
        user: dict = Depends(_current_user),
    ):
        """Assistência de escrita em gradiente 0-100%: polish / coauthor / draft."""
        ctx.owned_project(user, project_id)
        sec = ctx.repo.get_section(project_id, section_id)
        if not sec:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Seção não encontrada.")

        # Resolve modo e intensidade
        if body.intensity is not None:
            intensity = body.intensity
            if body.mode:
                resolved_mode = body.mode
            elif intensity <= 60:
                resolved_mode = "polish"
            elif intensity <= 80:
                resolved_mode = "coauthor"
            else:
                resolved_mode = "draft"
        else:
            resolved_mode = body.mode or "polish"
            intensity = 45 if resolved_mode == "polish" else (70 if resolved_mode == "coauthor" else 90)

        if intensity <= 15 and body.mode is None:
            raise HTTPException(
                422,
                "No nível Socrático (0–15%), a IA não altera o texto. Aumente o gradiente para pelo menos 20% para revisão ou redação.",
            )

        content_dict = dict(sec.get("content") or {"type": "doc", "content": []})
        if not isinstance(content_dict.get("content"), list):
            content_dict = {"type": "doc", "content": []}
        auth_meta = dict(content_dict.get("_authorship") or {"polished_words": 0, "ai_drafted_words": 0})
        auth_meta["last_intensity"] = intensity

        llm_used = False
        notice: str | None = None

        def run_generator(fn, **kwargs) -> str:
            nonlocal llm_used, notice
            if ctx.client is not None and ctx.client.available:
                try:
                    out = fn(client=ctx.client, **kwargs)
                    llm_used = True
                    return out
                except LLMUnavailable:
                    notice = AI_ASSIST_DEGRADED_MSG
            else:
                notice = AI_ASSIST_NO_LLM_MSG if ctx.client is None else AI_ASSIST_DEGRADED_MSG
            return fn(client=None, **kwargs)

        generated_text = ""
        if resolved_mode == "polish":
            selected = (body.selected_text or "").strip()
            raw_text = selected or extract_plain_text(content_dict).strip()
            if not raw_text:
                raise HTTPException(422, "Escreva um rascunho na seção antes de solicitar a lapidação acadêmica.")
            generated_text = run_generator(
                polish_academic_text, text=raw_text, section_title=sec["title"],
                instruction=body.instruction, intensity=intensity,
            )
            polish_ai_share = _ai_share(project_id, sec, raw_text) if llm_used else 0.0
            if llm_used:
                auth_meta["polished_words"] = int(auth_meta.get("polished_words", 0)) + count_words(generated_text)
                paragraphs = [p.strip() for p in generated_text.split("\n\n") if p.strip()] or [generated_text]
                if not selected:
                    content_dict["content"] = [
                        {"type": "paragraph", "content": [{"type": "text", "text": p}]}
                        for p in paragraphs
                    ]
                else:
                    content_dict["content"] = list(content_dict["content"]) + [
                        {"type": "paragraph", "content": [{"type": "text", "text": generated_text}]}
                    ]
            else:
                content_dict["content"] = _mechanical_cleanup_nodes(list(content_dict["content"]), only=selected or None)
                generated_text = mechanical_cleanup(raw_text)
                notice = (
                    "IA indisponível: apliquei só correções mecânicas (espaçamento, pontuação e maiúsculas), "
                    "sem trocar nenhuma palavra sua."
                )

            content_dict["_authorship"] = auth_meta
            updated_sec = ctx.repo.update_section(project_id, section_id, content=content_dict, version_by="ai", force_version=True)
            if llm_used:
                out_words = count_words(generated_text)
                if polish_ai_share > 0:
                    ai_w = round(out_words * polish_ai_share)
                    _record_ai(project_id, sec, "ai_coauthor", generated_text, user,
                               {"op": "polish", "ai_words": ai_w, "student_words": out_words - ai_w,
                                "model": ctx.client.model, "intensity": intensity})
                else:
                    _record_ai(project_id, sec, "ai_polish", generated_text, user,
                               {"op": "polish", "model": ctx.client.model, "intensity": intensity})
            ctx.repo.log_ai_usage(project_id, "polish_text", section_id,
                                  ctx.client.model if llm_used else "mechanical_cleanup", f"academic_polish_intensity_{intensity}")

        elif resolved_mode == "coauthor":
            all_claims = ctx.repo.list_project_claims(project_id)
            if not all_claims:
                raise HTTPException(422, "Sem evidência verificada, não há co-escrita com IA. Adicione um PDF ou artigo com citações verificadas primeiro.")
            sec_concepts = set(sec.get("concept_ids") or [])
            relevant_claims = [c for c in all_claims if c.get("concept_id") in sec_concepts] or all_claims[:1]
            new_concept_ids = list(sec_concepts | {c["concept_id"] for c in relevant_claims if c.get("concept_id")})
            ctx.repo.set_section_concepts(section_id, new_concept_ids)

            docs_by_id = {d["id"]: d for d in ctx.repo.list_documents(project_id)}
            premise = (body.selected_text or "").strip() or (body.instruction or "").strip()
            generated_text = run_generator(coauthor_with_evidence, student_premise=premise, claims=relevant_claims,
                                           docs_by_id=docs_by_id, section_title=sec["title"], instruction=body.instruction)
            words_added = count_words(generated_text)
            premise_words = min(words_added, count_words(premise))
            ai_expansion_words = max(1, words_added - premise_words)
            auth_meta["polished_words"] = int(auth_meta.get("polished_words", 0)) + premise_words
            auth_meta["ai_drafted_words"] = int(auth_meta.get("ai_drafted_words", 0)) + ai_expansion_words

            content_dict["content"] = list(content_dict["content"]) + [
                {"type": "paragraph", "content": [{"type": "text", "text": generated_text}]}
            ]
            content_dict["_authorship"] = auth_meta
            updated_sec = ctx.repo.update_section(project_id, section_id, content=content_dict, version_by="ai", force_version=True)
            _record_ai(project_id, sec, "ai_coauthor", generated_text, user,
                       {"op": "coauthor", "ai_words": ai_expansion_words, "student_words": premise_words,
                        "model": ctx.client.model if llm_used else None, "llm_used": llm_used, "intensity": intensity})
            ctx.repo.log_ai_usage(project_id, "draft_section", section_id,
                                  ctx.client.model if llm_used else "evidence_scaffold", f"coauthor_intensity_{intensity}")

        else:  # draft
            all_claims = ctx.repo.list_project_claims(project_id)
            if not all_claims:
                raise HTTPException(422, "Sem evidência verificada, não há redação por IA. Adicione um PDF ou artigo com citações verificadas primeiro.")
            sec_concepts = set(sec.get("concept_ids") or [])
            relevant_claims = [c for c in all_claims if c.get("concept_id") in sec_concepts]
            if not relevant_claims:
                relevant_claims = all_claims[:3]
                new_concept_ids = list(sec_concepts | {c["concept_id"] for c in relevant_claims if c.get("concept_id")})
                ctx.repo.set_section_concepts(section_id, new_concept_ids)

            docs_by_id = {d["id"]: d for d in ctx.repo.list_documents(project_id)}
            generated_text = run_generator(draft_evidence_paragraph, claims=relevant_claims, docs_by_id=docs_by_id,
                                           section_title=sec["title"], instruction=body.instruction)
            words_added = count_words(generated_text)
            auth_meta["ai_drafted_words"] = int(auth_meta.get("ai_drafted_words", 0)) + words_added

            content_dict["content"] = list(content_dict["content"]) + [
                {"type": "paragraph", "content": [{"type": "text", "text": generated_text}]}
            ]
            content_dict["_authorship"] = auth_meta
            updated_sec = ctx.repo.update_section(project_id, section_id, content=content_dict, version_by="ai", force_version=True)
            _record_ai(project_id, sec, "ai_draft", generated_text, user,
                       {"op": "draft", "model": ctx.client.model if llm_used else None, "llm_used": llm_used, "intensity": intensity})
            ctx.repo.log_ai_usage(project_id, "draft_section", section_id,
                                  ctx.client.model if llm_used else "evidence_scaffold", f"evidence_draft_intensity_{intensity}")

        all_sections = ctx.repo.list_sections(project_id)
        verified_quotes = [c.get("quote", "") for c in ctx.repo.list_project_claims(project_id)]
        return {
            "section": updated_sec,
            "generated_text": generated_text,
            "llm_used": llm_used,
            "notice": notice,
            "mode": resolved_mode,
            "intensity": intensity,
            "section_authorship": _section_authorship_for(project_id, updated_sec),
            "project_authorship": compute_project_authorship(
                all_sections, verified_quotes=verified_quotes, events_by_section=_events_by_section(project_id)
            ),
        }

    # ── Exportação ────────────────────────────────────────────────────

    @app.get("/projects/{project_id}/export/docx")
    def export_project_docx(
        project_id: str,
        omit_declaration: bool = False,
        user: dict = Depends(_current_user),
    ):
        """Exporta o manuscrito como Word ABNT com Prisma de Autoria e declaração de uso de IA."""
        from .. import paraphrase as _paraphrase
        project = ctx.owned_project(user, project_id)
        project["owner_name"] = user.get("name") or "Autor(a)"

        embedder = embeddings.resolve(ctx.client)
        pending_total = 0
        paraphrase_available = embedder is not None
        if paraphrase_available:
            quotes = [c.get("quote", "") for c in ctx.repo.list_project_claims(project_id)]
            try:
                for sec in ctx.repo.list_sections(project_id):
                    events = ctx.repo.list_provenance_events(project_id, sec["id"])
                    found = _paraphrase.find(
                        sec.get("content"), events,
                        lambda texts, task: embedder.embed(texts, task=task, operation="paraphrase"), quotes,
                    )
                    pending_total += len(found)
            except LLMUnavailable:
                paraphrase_available = False

        buf = build_docx_manuscript(
            ctx.repo, project_id, project,
            omit_ai_declaration=omit_declaration,
            unreviewed_paraphrases=pending_total if paraphrase_available else None,
        )
        raw_title = project.get("title", "trabalho")[:30].strip()
        ascii_title = unicodedata.normalize("NFKD", raw_title).encode("ascii", "ignore").decode("ascii")
        clean_slug = re.sub(r"[^\w\-]+", "_", ascii_title).strip("_") or "trabalho"
        filename = f"{clean_slug}.docx"
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Paraphrase-Verification": "available" if paraphrase_available else "unavailable",
        }
        return Response(
            content=buf.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers=headers,
        )
