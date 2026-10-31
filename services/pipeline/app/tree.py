"""Progress tree logic (T3.1, T3.2, T3.3).

Manages JSON templates (TCC, pré-projeto de mestrado) and node states (locked, available, done, skipped, needs_review).
Pure deterministic rules: nodes unlock when all prerequisites are done or skipped.
"""
from __future__ import annotations

import json
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent / "templates"


def load_template(work_type: str) -> dict:
    template_file = TEMPLATES_DIR / f"{work_type}.json"
    if not template_file.exists():
        template_file = TEMPLATES_DIR / "tcc.json"
    return json.loads(template_file.read_text(encoding="utf-8"))


def initial_nodes(template: dict) -> list[dict]:
    """Build the initial node state for a project based on its template."""
    nodes = []
    for n in template["nodes"]:
        has_prereqs = bool(n.get("prerequisites"))
        nodes.append({
            "node_key": n["key"],
            "template_key": template["key"],
            "status": "locked" if has_prereqs else "available",
            "queued": False,
            "skipped_reason": None,
        })
    return nodes


def resolve_node_states(template: dict, current_nodes: list[dict]) -> list[dict]:
    """Update node statuses: locked nodes unlock to 'available' if all prerequisites are done or skipped."""
    by_key = {n["node_key"]: dict(n) for n in current_nodes}
    prereqs_map = {n["key"]: n.get("prerequisites", []) for n in template["nodes"]}

    changed = True
    while changed:
        changed = False
        for node_key, node in by_key.items():
            if node["status"] == "locked":
                prereqs = prereqs_map.get(node_key, [])
                all_done = all(by_key.get(p, {}).get("status") in ("done", "skipped") for p in prereqs)
                if all_done:
                    node["status"] = "available"
                    changed = True

    return list(by_key.values())


def merge_template_with_nodes(template: dict, nodes: list[dict]) -> dict:
    """Combine template definition with project node execution states."""
    nodes_state = {n["node_key"]: n for n in nodes}
    enriched_nodes = []
    for defn in template["nodes"]:
        state = nodes_state.get(defn["key"], {
            "status": "available" if not defn.get("prerequisites") else "locked",
            "queued": False,
            "skipped_reason": None,
            "id": None,
        })
        enriched_nodes.append({
            **defn,
            "node_id": state.get("id"),
            "status": state.get("status", "locked"),
            "queued": state.get("queued", False),
            "skipped_reason": state.get("skipped_reason"),
            "updated_at": state.get("updated_at"),
        })

    return {
        "template_key": template["key"],
        "template_title": template["title"],
        "phases": template["phases"],
        "nodes": enriched_nodes,
    }
