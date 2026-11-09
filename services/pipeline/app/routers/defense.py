"""Rotas do Simulador Socrático de Defesa de Banca Acadêmica.

Permite que o estudante realize sessões interativas de arguição oral com perfis
examinadores (estrito vs construtivo) baseadas nas seções e evidências reais.
"""
from __future__ import annotations

from datetime import datetime, timezone
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from ..banca import (
    compile_defense_context,
    evaluate_turn_and_reply,
    generate_opening_question,
    synthesize_final_report,
)
from ..main_models import BancaSessionCreateIn, BancaTurnIn
from ._ctx import AppCtx


def register_routes(app: FastAPI, ctx: AppCtx) -> None:
    @app.post("/projects/{project_id}/banca/sessions", status_code=status.HTTP_201_CREATED)
    def create_defense_session(
        project_id: str,
        body: BancaSessionCreateIn,
        request: Request,
        cred: HTTPAuthorizationCredentials | None = Depends(ctx.bearer),
    ):
        user = ctx.current_user(request, cred)
        ctx.accessible_project(user, project_id)

        profile = body.examiner_profile if body.examiner_profile in ("estrito", "construtivo") else "estrito"
        session = ctx.repo.create_banca_session(project_id, profile)

        # Contexto grounded no texto real e nas evidências do aluno
        context = compile_defense_context(ctx.repo, project_id)
        opening = generate_opening_question(context, profile, client=ctx.client)

        first_turn = {
            "turn_no": 1,
            "speaker": "examiner",
            "content": opening["question"],
            "focus_area": opening.get("focus_area", "geral"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        updated = ctx.repo.update_banca_session(session["id"], turns=[first_turn])

        if opening.get("prompt_version") and ctx.client:
            ctx.repo.log_ai_usage(
                project_id,
                "banca_defense_question",
                session["id"],
                getattr(ctx.client, "model", None),
                opening.get("prompt_version"),
            )

        return {
            "session": updated or session,
            "context_summary": {
                "sections_count": context["sections_count"],
                "claims_count": context["claims_count"],
                "research_problem": context["research_problem"],
            },
        }

    @app.get("/projects/{project_id}/banca/sessions")
    def list_defense_sessions(
        project_id: str,
        request: Request,
        cred: HTTPAuthorizationCredentials | None = Depends(ctx.bearer),
    ):
        user = ctx.current_user(request, cred)
        ctx.accessible_project(user, project_id)
        return {"sessions": ctx.repo.list_banca_sessions(project_id)}

    @app.get("/projects/{project_id}/banca/sessions/{session_id}")
    def get_defense_session(
        project_id: str,
        session_id: str,
        request: Request,
        cred: HTTPAuthorizationCredentials | None = Depends(ctx.bearer),
    ):
        user = ctx.current_user(request, cred)
        ctx.accessible_project(user, project_id)

        session = ctx.repo.get_banca_session(session_id)
        if not session or session.get("project_id") != project_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Sessão de defesa não encontrada.")

        context = compile_defense_context(ctx.repo, project_id)
        return {
            "session": session,
            "context_summary": {
                "sections_count": context["sections_count"],
                "claims_count": context["claims_count"],
                "research_problem": context["research_problem"],
            },
        }

    @app.post("/projects/{project_id}/banca/sessions/{session_id}/turn")
    def submit_defense_turn(
        project_id: str,
        session_id: str,
        body: BancaTurnIn,
        request: Request,
        cred: HTTPAuthorizationCredentials | None = Depends(ctx.bearer),
    ):
        user = ctx.current_user(request, cred)
        ctx.accessible_project(user, project_id)

        session = ctx.repo.get_banca_session(session_id)
        if not session or session.get("project_id") != project_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Sessão de defesa não encontrada.")

        if session.get("status") == "completed":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Esta sessão de defesa já foi concluída. Inicie uma nova sessão para nova arguição.",
            )

        context = compile_defense_context(ctx.repo, project_id)
        turns = list(session.get("turns") or [])

        # 1. Registra resposta do estudante
        student_turn = {
            "turn_no": len(turns) + 1,
            "speaker": "student",
            "content": body.answer.strip(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        turns.append(student_turn)

        # 2. Avalia a resposta e formula réplica/próxima pergunta
        evaluation = evaluate_turn_and_reply(
            context,
            session.get("examiner_profile", "estrito"),
            turns,
            body.answer.strip(),
            client=ctx.client,
        )

        student_turn["rubric_scores"] = evaluation.get("rubric_scores")
        student_turn["feedback"] = evaluation.get("turn_feedback")

        examiner_turn = {
            "turn_no": len(turns) + 1,
            "speaker": "examiner",
            "content": evaluation["next_question"],
            "focus_area": evaluation.get("focus_area", "geral"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        turns.append(examiner_turn)

        updated = ctx.repo.update_banca_session(session_id, turns=turns)

        if evaluation.get("prompt_version") and ctx.client:
            ctx.repo.log_ai_usage(
                project_id,
                "banca_defense_turn",
                session_id,
                getattr(ctx.client, "model", None),
                evaluation.get("prompt_version"),
            )

        return {
            "session": updated,
            "latest_evaluation": {
                "rubric_scores": evaluation.get("rubric_scores"),
                "feedback": evaluation.get("turn_feedback"),
            },
        }

    @app.post("/projects/{project_id}/banca/sessions/{session_id}/conclude")
    def conclude_defense_session(
        project_id: str,
        session_id: str,
        request: Request,
        cred: HTTPAuthorizationCredentials | None = Depends(ctx.bearer),
    ):
        user = ctx.current_user(request, cred)
        ctx.accessible_project(user, project_id)

        session = ctx.repo.get_banca_session(session_id)
        if not session or session.get("project_id") != project_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Sessão de defesa não encontrada.")

        context = compile_defense_context(ctx.repo, project_id)
        turns = session.get("turns") or []

        final_report = synthesize_final_report(
            context,
            session.get("examiner_profile", "estrito"),
            turns,
            client=ctx.client,
        )

        updated = ctx.repo.update_banca_session(
            session_id,
            status="completed",
            final_report=final_report,
        )

        if final_report.get("prompt_version") and ctx.client:
            ctx.repo.log_ai_usage(
                project_id,
                "banca_defense_conclude",
                session_id,
                getattr(ctx.client, "model", None),
                final_report.get("prompt_version"),
            )

        return {"session": updated}
