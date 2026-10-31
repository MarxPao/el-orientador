"""Socratic Gate module (T3.2).

Facilitates an interactive dialogue between the AI academic advisor and the student for progress nodes.
Evaluates through rubric: clareza, justificativa, coerência (0 to 2 each).
Outcomes:
  - 'liberar' (node marked done, unlocks dependent nodes)
  - 'revisar' (node marked needs_review, returns guidance)
  - 'pular' (student skipped with warning recorded, node marked skipped)
All attempts are persisted in `gate_attempts` and logged in `ai_usage_log`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .pipeline.extract import load_prompt
from .pipeline.llm import LLMClient

GATE_SCHEMA = {
    "type": "object",
    "required": ["message_to_student", "done"],
    "properties": {
        "message_to_student": {"type": "string"},
        "done": {"type": "boolean"},
        "outcome": {"enum": ["liberar", "revisar"]},
        "rubric_scores": {
            "type": "object",
            "properties": {
                "clareza": {"type": "integer", "minimum": 0, "maximum": 2},
                "justificativa": {"type": "integer", "minimum": 0, "maximum": 2},
                "coerencia": {"type": "integer", "minimum": 0, "maximum": 2},
            },
        },
        "guidance": {"type": "string"},
    },
}


def build_gate_user_message(
    work_type: str,
    node_title: str,
    node_description: str,
    previous_decisions: str,
    history: list[dict[str, str]],
    user_input: str,
) -> str:
    conversation = "\n".join(
        f"{'Orientador' if t['role'] == 'assistant' else 'Aluno'}: {t['content']}"
        for t in history
    )
    return (
        f"Tipo de trabalho: {work_type}\n"
        f"Nó atual: {node_title} ({node_description})\n"
        f"Decisões anteriores do aluno: {previous_decisions or 'Nenhuma decisão anterior registrada.'}\n\n"
        f"Histórico da conversa até aqui:\n{conversation}\n\n"
        f"Nova resposta do aluno: \"{user_input}\"\n\n"
        "Avalie a resposta pela rubrica (clareza, justificativa, coerência: 0 a 2 cada). "
        "Se a conversa já tiver 3 rodadas ou a justificativa estiver sólida, conclua com done=true e outcome ('liberar' ou 'revisar'). "
        "Caso contrário, devolva done=false com a próxima pergunta orientadora (sem dar a resposta pronta)."
    )


def run_gate_turn(
    client: LLMClient,
    work_type: str,
    node_title: str,
    node_description: str,
    previous_decisions: str,
    history: list[dict[str, str]],
    user_input: str,
) -> dict[str, Any]:
    version, system, _ = load_prompt("socratic_gate.md")
    prompt = build_gate_user_message(
        work_type, node_title, node_description, previous_decisions, history, user_input
    )
    result = client.complete_json(system, prompt, GATE_SCHEMA)
    result["prompt_version"] = version
    return result
