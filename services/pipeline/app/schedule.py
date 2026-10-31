"""Schedule and deadline alert calculation (T3.3).

Computes estimated timeline for remaining progress nodes and research queue based on:
- node typical times (parsed into weeks)
- student weekly dedication hours (scaled relative to baseline of 10h/week)
- project deadline
Generates alerts when timeline is at risk and calculates suggested weekly hours to meet deadline.
"""
from __future__ import annotations

import math
import re
from datetime import date, timedelta
from typing import Any

_RANGE_PATTERN = re.compile(r"(\d+)\s+a\s+(\d+)\s+semanas?", re.IGNORECASE)
_SINGLE_PATTERN = re.compile(r"(\d+)\s+semanas?", re.IGNORECASE)
BASELINE_HOURS_PER_WEEK = 10.0


def parse_typical_weeks(typical_time: str) -> tuple[float, float, float]:
    """Parse 'X semana(s)' or 'X a Y semanas' into (min_weeks, max_weeks, avg_weeks)."""
    text = (typical_time or "").strip()
    m_range = _RANGE_PATTERN.search(text)
    if m_range:
        low = float(m_range.group(1))
        high = float(m_range.group(2))
        return low, high, (low + high) / 2.0

    m_single = _SINGLE_PATTERN.search(text)
    if m_single:
        val = float(m_single.group(1))
        return val, val, val

    # Default fallback if unparseable
    return 1.0, 2.0, 1.5


def calculate_schedule(
    template: dict[str, Any],
    nodes_state: list[dict[str, Any]],
    weekly_hours: int | None = None,
    deadline: date | str | None = None,
    start_date: date | None = None,
) -> dict[str, Any]:
    """Calculate projected completion dates, research queue highlights, and deadline alerts."""
    start = start_date or date.today()
    hours = float(weekly_hours) if weekly_hours and weekly_hours > 0 else BASELINE_HOURS_PER_WEEK
    # Dedication pace factor: if student has 5h/wk, factor is 2.0 (takes twice as long).
    pace_factor = max(0.2, min(5.0, BASELINE_HOURS_PER_WEEK / hours))

    parsed_deadline: date | None = None
    if isinstance(deadline, str) and deadline.strip():
        parsed_deadline = date.fromisoformat(deadline.strip())
    elif isinstance(deadline, date):
        parsed_deadline = deadline

    state_by_key = {n["node_key"]: n for n in nodes_state}
    template_nodes = template.get("nodes", [])

    # Identify remaining nodes (not done and not skipped)
    remaining_nodes: list[dict[str, Any]] = []
    queued_keys: list[str] = []

    for defn in template_nodes:
        key = defn["key"]
        st = state_by_key.get(key, {})
        status = st.get("status", "locked")
        is_queued = bool(st.get("queued", False))
        if is_queued:
            queued_keys.append(key)
        if status not in ("done", "skipped"):
            remaining_nodes.append({
                "defn": defn,
                "status": status,
                "queued": is_queued,
            })

    # Sort remaining: queued items first if available, then template order
    remaining_nodes.sort(key=lambda item: (not (item["queued"] and item["status"] == "available"), 0))

    # Calculate item dates sequentially
    schedule_items = []
    current_cursor = start
    total_base_avg_weeks = 0.0

    for item in remaining_nodes:
        defn = item["defn"]
        typical_time = defn.get("typical_time", "1 semana")
        low_w, high_w, avg_w = parse_typical_weeks(typical_time)
        total_base_avg_weeks += avg_w

        effective_weeks = avg_w * pace_factor
        duration_days = max(1, round(effective_weeks * 7))

        item_start = current_cursor
        item_end = item_start + timedelta(days=duration_days)
        current_cursor = item_end

        schedule_items.append({
            "node_key": defn["key"],
            "title": defn["title"],
            "phase": defn["phase"],
            "status": item["status"],
            "queued": item["queued"],
            "typical_time": typical_time,
            "estimated_weeks": round(effective_weeks, 1),
            "estimated_start": item_start.isoformat(),
            "estimated_end": item_end.isoformat(),
        })

    estimated_completion_date = current_cursor
    total_estimated_weeks = round((current_cursor - start).days / 7.0, 1)

    is_at_risk = False
    alert: str
    suggested_hours: int | None = None
    days_until_deadline: int | None = None

    if parsed_deadline:
        days_until_deadline = (parsed_deadline - start).days
        if days_until_deadline <= 0:
            is_at_risk = True
            alert = f"Prazo final expirado ({parsed_deadline.strftime('%d/%m/%Y')}). É necessário redefinir a data com o orientador."
            suggested_hours = int(math.ceil(hours * 1.5))
        elif estimated_completion_date > parsed_deadline:
            is_at_risk = True
            weeks_avail = max(1.0, days_until_deadline / 7.0)
            required_pace = total_base_avg_weeks / weeks_avail
            suggested_hours = max(int(hours) + 1, min(60, int(math.ceil(BASELINE_HOURS_PER_WEEK * required_pace))))
            est_str = estimated_completion_date.strftime("%d/%m/%Y")
            dl_str = parsed_deadline.strftime("%d/%m/%Y")
            alert = (
                f"Atenção ao prazo: no ritmo atual ({int(hours)}h/semana), a conclusão estimada é {est_str}, "
                f"ultrapassando o prazo de {dl_str}. Sugere-se elevar a dedicação para pelo menos {suggested_hours}h/semana."
            )
        else:
            buffer_days = (parsed_deadline - estimated_completion_date).days
            est_str = estimated_completion_date.strftime("%d/%m/%Y")
            dl_str = parsed_deadline.strftime("%d/%m/%Y")
            if buffer_days < 14:
                alert = (
                    f"Cronograma justo: conclusão estimada em {est_str}, com apenas {buffer_days} dias de margem "
                    f"até o prazo de {dl_str}. Mantenha a disciplina de {int(hours)}h/semana."
                )
            else:
                alert = (
                    f"Cronograma em dia: conclusão estimada em {est_str}, dentro do prazo ({dl_str}) com margem de segurança."
                )
    else:
        est_str = estimated_completion_date.strftime("%d/%m/%Y")
        alert = (
            f"Previsão de conclusão em {est_str} ({total_estimated_weeks} semanas restantes no ritmo de {int(hours)}h/semana). "
            "Defina um prazo final nas configurações do projeto para habilitar alertas de risco."
        )

    return {
        "start_date": start.isoformat(),
        "weekly_hours": int(hours),
        "deadline": parsed_deadline.isoformat() if parsed_deadline else None,
        "days_until_deadline": days_until_deadline,
        "is_at_risk": is_at_risk,
        "alert": alert,
        "suggested_weekly_hours": suggested_hours,
        "total_estimated_weeks": total_estimated_weeks,
        "estimated_completion_date": estimated_completion_date.isoformat(),
        "queued_keys": queued_keys,
        "remaining_count": len(remaining_nodes),
        "items": schedule_items,
    }
