"""Roteador de árvore de progresso e gate socrático.

Endpoints: /tree, /tree/nodes, /tree/nodes/{key}/gate, /schedule
"""
from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from ..gate import run_gate_turn
from ..llm_gateway import LLMUnavailable
from ..schedule import calculate_schedule
from ..tree import initial_nodes, load_template, merge_template_with_nodes, resolve_node_states
from ._ctx import AppCtx
from ..main_models import GateTurnIn, NodeUpdateIn, LLM_DOWN_MSG, GATE_NO_LLM_MSG


def register_routes(app: FastAPI, ctx: AppCtx) -> None:  # noqa: C901
    bearer = ctx.bearer

    def _current_user(
        request: Request,
        cred: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> dict:
        return ctx.current_user(request, cred)

    def _propagate_states(project_id: str, template: dict) -> None:
        """Re-resolve e persiste mudanças de estado em cascata."""
        all_nodes = ctx.repo.get_progress_nodes(project_id)
        resolved = resolve_node_states(template, all_nodes)
        for r in resolved:
            orig = next((n for n in all_nodes if n["node_key"] == r["node_key"]), None)
            if orig and orig["status"] != r["status"]:
                ctx.repo.update_progress_node(project_id, r["node_key"], status=r["status"])

    # ── Árvore ────────────────────────────────────────────────────────

    @app.get("/projects/{project_id}/tree")
    def get_project_tree(project_id: str, user: dict = Depends(_current_user)):
        """Árvore de progresso: fases, nós, pré-requisitos e status atual."""
        project = ctx.accessible_project(user, project_id)
        template = load_template(project.get("work", "tcc"))
        nodes = ctx.repo.get_progress_nodes(project_id)
        if not nodes:
            nodes = ctx.repo.save_progress_nodes(project_id, initial_nodes(template))
        resolved = resolve_node_states(template, nodes)
        for r in resolved:
            orig = next((n for n in nodes if n["node_key"] == r["node_key"]), None)
            if orig and orig["status"] != r["status"]:
                ctx.repo.update_progress_node(project_id, r["node_key"], status=r["status"])
        return merge_template_with_nodes(template, resolved)

    @app.patch("/projects/{project_id}/tree/nodes/{node_key}")
    def update_project_node(
        project_id: str, node_key: str, body: NodeUpdateIn, user: dict = Depends(_current_user)
    ):
        """Atualiza status ou flag de fila de pesquisa de um nó de progresso."""
        project = ctx.owned_project(user, project_id)
        template = load_template(project.get("work", "tcc"))
        node_def = next((n for n in template["nodes"] if n["key"] == node_key), None)
        if not node_def:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Nó não encontrado no template do projeto.")
        node = ctx.repo.get_progress_node(project_id, node_key)
        if not node:
            ctx.repo.save_progress_nodes(project_id, initial_nodes(template))
            node = ctx.repo.get_progress_node(project_id, node_key)

        fields: dict = {}
        if body.status is not None:
            effective = next(
                (r["status"] for r in resolve_node_states(template, ctx.repo.get_progress_nodes(project_id))
                 if r["node_key"] == node_key),
                node["status"],
            )
            if effective == "locked":
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "Esta etapa ainda está trancada: conclua as etapas anteriores primeiro.",
                )
            fields["status"] = body.status
        if body.queued is not None:
            fields["queued"] = body.queued
        if body.skipped_reason is not None:
            fields["skipped_reason"] = body.skipped_reason
        if fields:
            node = ctx.repo.update_progress_node(project_id, node_key, **fields)
        _propagate_states(project_id, template)
        return {"node_key": node_key, **node}

    # ── Gate socrático ────────────────────────────────────────────────

    @app.post("/projects/{project_id}/tree/nodes/{node_key}/gate")
    def post_gate_turn(
        project_id: str,
        node_key: str,
        body: GateTurnIn,
        user: dict = Depends(_current_user),
    ):
        """Turno interativo do diálogo socrático. Avalia resposta do estudante ou regista pulo consciente."""
        project = ctx.owned_project(user, project_id)
        template = load_template(project.get("work", "tcc"))
        node_def = next((n for n in template["nodes"] if n["key"] == node_key), None)
        if not node_def:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Nó não encontrado no template do projeto.")

        node = ctx.repo.get_progress_node(project_id, node_key)
        if not node:
            ctx.repo.save_progress_nodes(project_id, initial_nodes(template))
            node = ctx.repo.get_progress_node(project_id, node_key)

        if body.skip:
            user_msg = body.user_input if body.user_input.strip() else "Solicitou pular etapa com aviso consciente."
            transcript = body.history + [
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": "Etapa pulada com registro de aviso consciente no relatório do orientador."},
            ]
            attempt = ctx.repo.save_gate_attempt(
                progress_node_id=node["id"], transcript=transcript, rubric_scores=None, outcome="pular",
            )
            reason = body.skip_reason or "Avançado com aviso consciente"
            ctx.repo.update_progress_node(project_id, node_key, status="skipped", skipped_reason=reason)
            ctx.repo.log_ai_usage(project_id, "gate", node["id"], "system", "socratic_gate_v0.1")
            _propagate_states(project_id, template)
            return {
                "done": True, "outcome": "pular",
                "message_to_student": "Etapa pulada com registro de aviso consciente no relatório do orientador.",
                "rubric_scores": None,
                "guidance": "Esta etapa foi pulada conscientemente.",
                "attempt_id": attempt["id"],
            }

        if ctx.client is None:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, GATE_NO_LLM_MSG)

        all_nodes = ctx.repo.get_progress_nodes(project_id)
        done_nodes = [n["node_key"] for n in all_nodes if n["status"] in ("done", "skipped")]
        prev = (
            f"Etapas concluídas ou puladas: {', '.join(done_nodes)}"
            if done_nodes
            else "Nenhuma etapa concluída anteriormente."
        )
        try:
            result = run_gate_turn(
                client=ctx.client,
                work_type=project.get("work", "tcc"),
                node_title=node_def["title"],
                node_description=node_def.get("description", ""),
                previous_decisions=prev,
                history=body.history,
                user_input=body.user_input,
            )
        except LLMUnavailable:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, LLM_DOWN_MSG)

        new_transcript = body.history + [
            {"role": "user", "content": body.user_input},
            {"role": "assistant", "content": result["message_to_student"]},
        ]
        outcome = result.get("outcome") or ("liberar" if result.get("done") else "em_andamento")
        attempt = ctx.repo.save_gate_attempt(
            progress_node_id=node["id"],
            transcript=new_transcript,
            rubric_scores=result.get("rubric_scores"),
            outcome=outcome,
        )
        ctx.repo.log_ai_usage(
            project_id, "gate", node["id"],
            getattr(ctx.client, "model", None),
            result.get("prompt_version"),
        )

        if result.get("done") and outcome == "liberar":
            ctx.repo.update_progress_node(project_id, node_key, status="done")
            _propagate_states(project_id, template)
        elif result.get("done") and outcome == "revisar":
            ctx.repo.update_progress_node(project_id, node_key, status="needs_review")

        return {**result, "attempt_id": attempt["id"]}

    @app.get("/projects/{project_id}/tree/nodes/{node_key}/gate")
    def get_gate_attempts(project_id: str, node_key: str, user: dict = Depends(_current_user)):
        """Lista tentativas históricas do gate e transcrição de um nó."""
        ctx.owned_project(user, project_id)
        node = ctx.repo.get_progress_node(project_id, node_key)
        if not node:
            return {"node_key": node_key, "attempts": []}
        attempts = ctx.repo.list_gate_attempts(node["id"])
        return {"node_key": node_key, "progress_node_id": node["id"], "attempts": attempts}

    # ── Cronograma ────────────────────────────────────────────────────

    @app.get("/projects/{project_id}/schedule")
    def get_project_schedule(project_id: str, user: dict = Depends(_current_user)):
        """Projeção de prazo e alerta de deadline com base nos nós restantes e horas semanais."""
        project = ctx.owned_project(user, project_id)
        template = load_template(project.get("work", "tcc"))
        nodes = ctx.repo.get_progress_nodes(project_id)
        if not nodes:
            nodes = ctx.repo.save_progress_nodes(project_id, initial_nodes(template))
        return calculate_schedule(
            template=template,
            nodes_state=nodes,
            weekly_hours=project.get("weekly_hours"),
            deadline=project.get("deadline"),
        )
