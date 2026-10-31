"""Advisor Progress Report generation (T5.2).

Aggregates project progress into a transparent, structured academic report for human advisors:
- Node progression, gates passed, and steps skipped with conscious warnings.
- Knowledge map metrics (confirmed vs rejected edges, literature gaps discovered).
- Manuscript sections & evidence linkage.
- AI Usage Audit (models, prompts, actions) ensuring compliance with academic integrity guidelines.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .authorship import compute_project_authorship, compute_section_authorship
from .repo import Repo
from .tree import load_template


def generate_advisor_report_payload(repo: Repo, project_id: str, project: dict[str, Any]) -> dict[str, Any]:
    """Compile comprehensive progress and governance data for the student's advisor."""
    template = load_template(project.get("work", "tcc"))
    nodes = repo.get_progress_nodes(project_id)
    node_map = {n["node_key"]: n for n in nodes}

    # Aggregate nodes status
    completed_nodes: list[dict[str, Any]] = []
    skipped_nodes: list[dict[str, Any]] = []
    pending_nodes: list[dict[str, Any]] = []

    for defn in template["nodes"]:
        key = defn["key"]
        st = node_map.get(key, {})
        status = st.get("status", "locked")
        node_info = {
            "key": key,
            "title": defn["title"],
            "phase": defn["phase"],
            "status": status,
            "typical_time": defn.get("typical_time"),
            "queued": st.get("queued", False),
            "updated_at": st.get("updated_at"),
        }

        if status == "done":
            completed_nodes.append(node_info)
        elif status == "skipped":
            node_info["skipped_reason"] = st.get("skipped_reason") or "Avançado com aviso consciente"
            skipped_nodes.append(node_info)
        else:
            pending_nodes.append(node_info)

    # Knowledge Map data
    concepts = repo.list_concepts(project_id)
    edges = repo.list_edges(project_id)
    confirmed_edges = [e for e in edges if e.get("status") == "confirmed"]
    rejected_edges = [e for e in edges if e.get("status") == "rejected"]
    gaps = repo.list_gaps(project_id)
    documents = repo.list_documents(project_id)
    claims = repo.list_project_claims(project_id)

    # Sections data
    sections = repo.list_sections(project_id)
    sections_with_evidence = [s for s in sections if len(s.get("concept_ids", [])) > 0]

    # AI Usage Audit
    ai_logs = repo.list_ai_usage(project_id)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": {
            "id": project_id,
            "title": project.get("title"),
            "work": project.get("work"),
            "institution": project.get("institution"),
            "citation_style": project.get("citation_style", "abnt"),
            "deadline": project.get("deadline"),
            "weekly_hours": project.get("weekly_hours"),
            "research_problem": project.get("research_problem"),
        },
        "progress_tree": {
            "total_nodes": len(template["nodes"]),
            "completed_count": len(completed_nodes),
            "skipped_count": len(skipped_nodes),
            "pending_count": len(pending_nodes),
            "completed": completed_nodes,
            "skipped_with_warning": skipped_nodes,
            "pending": pending_nodes,
        },
        "knowledge_map": {
            "documents_count": len(documents),
            "verified_claims_count": len(claims),
            "concepts_count": len(concepts),
            "confirmed_relations_count": len(confirmed_edges),
            "rejected_relations_count": len(rejected_edges),
            "gaps_count": len(gaps),
            "confirmed_relations": [
                {
                    "source": e.get("source_concept"),
                    "target": e.get("target_concept"),
                    "relation": e.get("relation"),
                }
                for e in confirmed_edges
            ],
            "rejected_relations": [
                {
                    "source": e.get("source_concept"),
                    "target": e.get("target_concept"),
                    "relation": e.get("relation"),
                    "user_note": e.get("user_note"),
                }
                for e in rejected_edges
            ],
            "gaps": [
                {
                    "concept_a": g.get("concept_a"),
                    "concept_b": g.get("concept_b"),
                    "status": g.get("status"),
                    "note": g.get("note"),
                }
                for g in gaps
            ],
        },
        "manuscript": {
            "sections_count": len(sections),
            "sections_with_evidence_count": len(sections_with_evidence),
            "authorship_prism": compute_project_authorship(sections),
            "sections": [
                {
                    "id": s["id"],
                    "title": s["title"],
                    "position": s["position"],
                    "concepts_linked_count": len(s.get("concept_ids", [])),
                    "authorship": compute_section_authorship(s),
                }
                for s in sections
            ],
        },
        "ai_usage_audit": {
            "total_ai_interactions": len(ai_logs),
            "actions_summary": {
                "gate": sum(1 for l in ai_logs if l.get("action") == "gate"),
                "extract": sum(1 for l in ai_logs if l.get("action") == "extract"),
                "relate": sum(1 for l in ai_logs if l.get("action") == "relate"),
                "polish_text": sum(1 for l in ai_logs if l.get("action") == "polish_text"),
                "draft_section": sum(1 for l in ai_logs if l.get("action") == "draft_section"),
            },
            "logs": ai_logs[-20:],  # Recent audit logs
        },
    }
