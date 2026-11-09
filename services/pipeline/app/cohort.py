"""Multi-Advisee Cohort Dashboard and Academic Coordination Module (T7.4).

Aggregates progress, skipped steps, deadline alerts, evidence linkages,
and authorship metrics across multiple students for professors and course coordinators.
"""
from __future__ import annotations

import csv
import io
import math
from collections import Counter
from datetime import date, datetime, timezone
from typing import Any

from .authorship import compute_project_authorship
from .repo import Repo
from .schedule import calculate_schedule
from .tree import load_template


def _compute_risk_level(days_until_deadline: int | None, is_at_risk: bool) -> tuple[str, str]:
    """Classify deadline risk into standard academic monitoring tiers."""
    if days_until_deadline is None:
        return "no_deadline", "Sem prazo definido"
    if days_until_deadline <= 0:
        return "overdue", "Prazo Vencido"
    if days_until_deadline <= 15 or is_at_risk:
        return "critical", "Crítico (< 15 dias)"
    if days_until_deadline <= 30:
        return "warning", "Atenção (< 30 dias)"
    return "ontrack", "Em dia"


def compute_student_overview(repo: Repo, project: dict[str, Any]) -> dict[str, Any]:
    """Compute consolidated progress, skipped steps, and alerts for a single advisee."""
    project_id = project["id"]
    owner_id = project.get("owner_id")
    owner = repo.get_user(owner_id) if owner_id else None

    student_name = (owner.get("name") if owner else None) or "Estudante"
    student_email = (owner.get("email") if owner else None) or ""

    # Tree progress & skipped steps
    work_type = project.get("work") or "tcc"
    template = load_template(work_type)
    nodes_state = repo.get_progress_nodes(project_id)
    node_map = {n["node_key"]: n for n in nodes_state}

    template_nodes = template.get("nodes", [])
    total_nodes = len(template_nodes)
    done_count = 0
    available_count = 0
    skipped_steps: list[dict[str, Any]] = []

    for n in template_nodes:
        k = n["key"]
        st = node_map.get(k, {})
        status = st.get("status", "locked")
        if status == "done":
            done_count += 1
        elif status == "skipped":
            skipped_steps.append({
                "node_key": k,
                "title": n.get("title", k),
                "phase": n.get("phase", ""),
                "reason": st.get("skipped_reason") or "Avançado com aviso consciente",
                "skipped_at": st.get("updated_at"),
            })
        elif status == "available":
            available_count += 1

    completion_rate = round((done_count / total_nodes * 100), 1) if total_nodes > 0 else 0.0

    # Schedule & deadline analysis
    schedule_data = calculate_schedule(
        template=template,
        nodes_state=nodes_state,
        weekly_hours=project.get("weekly_hours"),
        deadline=project.get("deadline"),
    )

    days_until_deadline = schedule_data.get("days_until_deadline")
    is_at_risk = schedule_data.get("is_at_risk", False)
    risk_level, risk_label = _compute_risk_level(days_until_deadline, is_at_risk)

    # Documents & Evidence
    docs = repo.list_documents(project_id)
    claims = repo.list_project_claims(project_id)

    # Sections & Unresolved Comments
    sections = repo.list_sections(project_id)
    unresolved_comments = 0
    for sec in sections:
        comments = repo.list_section_comments(sec["id"])
        unresolved_comments += sum(1 for c in comments if not c.get("resolved"))

    # Authorship & AI Usage
    try:
        authorship = compute_project_authorship(repo, project_id)
        direct_human_pct = authorship.get("direct_human_pct", 100)
        ai_assisted_pct = authorship.get("ai_assisted_pct", 0)
        requires_disclosure = authorship.get("requires_disclosure", False)
    except Exception:
        direct_human_pct = 100
        ai_assisted_pct = 0
        requires_disclosure = False

    # Oral Defense Simulation Status
    banca_verdict = None
    banca_score = None
    try:
        banca_sessions = repo.list_banca_sessions(project_id)
        if banca_sessions:
            latest = banca_sessions[0]
            rep = latest.get("final_report")
            if rep:
                banca_verdict = rep.get("verdict_title")
                banca_score = rep.get("overall_score")
    except Exception:
        pass

    return {
        "project_id": project_id,
        "title": project.get("title") or "Sem título",
        "work": work_type,
        "institution": project.get("institution") or "",
        "citation_style": project.get("citation_style") or "abnt",
        "deadline": project.get("deadline"),
        "weekly_hours": project.get("weekly_hours") or 10,
        "student": {
            "name": student_name,
            "email": student_email,
            "initials": "".join([part[0].upper() for part in student_name.split()[:2]]) or "E",
        },
        "progress": {
            "total_nodes": total_nodes,
            "done_nodes": done_count,
            "available_nodes": available_count,
            "completion_rate": completion_rate,
            "skipped_count": len(skipped_steps),
            "skipped_steps": skipped_steps,
        },
        "schedule": {
            "days_until_deadline": days_until_deadline,
            "is_at_risk": is_at_risk,
            "risk_level": risk_level,
            "risk_label": risk_label,
            "alert": schedule_data.get("alert") or "",
            "suggested_weekly_hours": schedule_data.get("suggested_weekly_hours"),
            "estimated_completion_date": schedule_data.get("estimated_completion_date"),
        },
        "governance": {
            "sources_count": len(docs),
            "verified_claims_count": len(claims),
            "sections_count": len(sections),
            "unresolved_comments_count": unresolved_comments,
            "direct_human_pct": direct_human_pct,
            "ai_assisted_pct": ai_assisted_pct,
            "requires_disclosure": requires_disclosure,
            "banca_verdict": banca_verdict,
            "banca_score": banca_score,
        },
    }


def compute_cohort_dashboard(repo: Repo, advisor_email: str) -> dict[str, Any]:
    """Aggregate progress, risks, and governance for all projects advised by a professor."""
    email = advisor_email.strip().lower()
    projects = repo.list_advising_projects(email)

    students = [compute_student_overview(repo, p) for p in projects]

    total_advisees = len(students)
    avg_progress = (
        round(sum(s["progress"]["completion_rate"] for s in students) / total_advisees, 1)
        if total_advisees > 0
        else 0.0
    )

    at_risk_count = sum(1 for s in students if s["schedule"]["risk_level"] in ("overdue", "critical"))
    total_skipped_steps = sum(s["progress"]["skipped_count"] for s in students)
    total_unresolved_comments = sum(s["governance"]["unresolved_comments_count"] for s in students)

    by_work = dict(Counter(s["work"] for s in students))
    by_risk = dict(Counter(s["schedule"]["risk_level"] for s in students))

    return {
        "advisor_email": email,
        "metrics": {
            "total_advisees": total_advisees,
            "average_progress": avg_progress,
            "at_risk_count": at_risk_count,
            "total_skipped_steps": total_skipped_steps,
            "total_unresolved_comments": total_unresolved_comments,
            "by_work": by_work,
            "by_risk": by_risk,
        },
        "students": students,
    }


def export_cohort_summary_csv(cohort_data: dict[str, Any]) -> str:
    """Generate a CSV document of advisees for academic department records."""
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    # Header
    writer.writerow([
        "Estudante",
        "E-mail",
        "Título do Trabalho",
        "Tipo",
        "Instituição",
        "% Concluído",
        "Etapas Concluídas",
        "Total de Etapas",
        "Etapas Puladas (Qtd)",
        "Etapas Puladas (Detalhes)",
        "Prazo Final",
        "Dias Restantes",
        "Status de Risco",
        "Fontes Verificadas",
        "Comentários Pendentes",
        "Prisma Autoria (% Humano)",
        "Última Banca Simulada",
    ])

    for s in cohort_data.get("students", []):
        skipped_details = " | ".join(
            f"{step['title']}: {step['reason']}" for step in s["progress"]["skipped_steps"]
        )
        writer.writerow([
            s["student"]["name"],
            s["student"]["email"],
            s["title"],
            s["work"].upper(),
            s["institution"],
            f"{s['progress']['completion_rate']}%",
            s["progress"]["done_nodes"],
            s["progress"]["total_nodes"],
            s["progress"]["skipped_count"],
            skipped_details,
            s["deadline"] or "Sem prazo",
            s["schedule"]["days_until_deadline"] if s["schedule"]["days_until_deadline"] is not None else "N/A",
            s["schedule"]["risk_label"],
            s["governance"]["sources_count"],
            s["governance"]["unresolved_comments_count"],
            f"{s['governance']['direct_human_pct']}%",
            f"{s['governance']['banca_verdict']} ({s['governance']['banca_score']}/10)" if s["governance"]["banca_verdict"] else "Não realizada",
        ])

    return output.getvalue()


def export_cohort_summary_markdown(cohort_data: dict[str, Any]) -> str:
    """Generate a clean Markdown report for course coordination meetings."""
    metrics = cohort_data.get("metrics", {})
    students = cohort_data.get("students", [])
    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y às %H:%M UTC")

    md = f"""# Relatório de Acompanhamento de Turma / Multi-orientandos
**Coordenação e Orientação Acadêmica — El Orientador**  
*Emitido em: {now_str}*  
*Orientador(a): {cohort_data.get('advisor_email')}*

---

## 1. Quadro Geral da Turma

- **Total de Orientandos:** {metrics.get('total_advisees', 0)}
- **Média de Conclusão da Turma:** {metrics.get('average_progress', 0.0)}%
- **Estudantes em Risco de Prazo:** {metrics.get('at_risk_count', 0)}
- **Total de Etapas Puladas com Aviso:** {metrics.get('total_skipped_steps', 0)}
- **Comentários Pendentes de Resolução:** {metrics.get('total_unresolved_comments', 0)}

---

## 2. Acompanhamento Individual por Estudante

| Estudante | Trabalho | Progresso | Prazo | Risco | Etapas Puladas | Comentários |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
"""
    for s in students:
        skipped_str = f"{s['progress']['skipped_count']} etapa(s)" if s['progress']['skipped_count'] > 0 else "Nenhuma"
        md += f"| **{s['student']['name']}**<br>`{s['student']['email']}` | {s['title']}<br>*{s['work'].upper()}* | {s['progress']['completion_rate']}% ({s['progress']['done_nodes']}/{s['progress']['total_nodes']}) | {s['deadline'] or 'Sem prazo'} | `{s['schedule']['risk_label']}` | {skipped_str} | {s['governance']['unresolved_comments_count']} pendentes |\n"

    # Detail skipped steps
    skipped_any = [s for s in students if s["progress"]["skipped_steps"]]
    if skipped_any:
        md += "\n---\n\n## 3. Auditoria de Etapas Puladas (Avisos Conscientes)\n\n"
        for s in skipped_any:
            md += f"### {s['student']['name']} ({s['title']})\n"
            for step in s["progress"]["skipped_steps"]:
                md += f"- **{step['title']}** ({step['phase']}): {step['reason']}\n"
            md += "\n"

    return md
