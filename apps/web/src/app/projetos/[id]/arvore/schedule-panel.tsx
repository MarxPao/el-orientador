"use client";

import { useEffect, useState } from "react";
import { api, ScheduleData } from "@/lib/api";

function formatDate(isoStr: string | null | undefined): string {
  if (!isoStr) return "-";
  const [year, month, day] = isoStr.split("-");
  return `${day}/${month}/${year}`;
}

export function SchedulePanel({
  projectId,
  reloadKey,
  onSelectNode,
}: {
  projectId: string;
  reloadKey: number;
  onSelectNode?: (key: string) => void;
}) {
  const [schedule, setSchedule] = useState<ScheduleData | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    api<ScheduleData>(`/projects/${projectId}/schedule`)
      .then((data) => {
        if (!cancelled) setSchedule(data);
      })
      .catch(() => {
        // Ignored or handled quietly
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [projectId, reloadKey]);

  if (!schedule && loading) {
    return (
      <div className="rounded border border-ink/10 bg-paper/30 p-3 text-xs text-ink/60">
        Calculando cronograma e estimativas de prazo…
      </div>
    );
  }

  if (!schedule) return null;

  const queuedItems = schedule.items.filter((item) => item.queued);
  const upcomingItems = schedule.items.slice(0, 5);

  return (
    <div className="rounded-lg border border-ink/15 bg-white p-4 text-xs shadow-sm space-y-3">
      {/* Header & Alert Bar */}
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-serif-academic font-bold text-sm text-ink">Cronograma & Prazos</h3>
            <span
              className={`rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
                schedule.is_at_risk
                  ? "bg-gap text-white"
                  : schedule.deadline
                  ? "bg-done text-white"
                  : "bg-ink/10 text-ink/70"
              }`}
            >
              {schedule.is_at_risk
                ? "Atenção ao Prazo"
                : schedule.deadline
                ? "No Prazo"
                : "Sem Prazo Definido"}
            </span>
          </div>
          <p
            className={`mt-1.5 leading-relaxed ${
              schedule.is_at_risk ? "font-medium text-gap" : "text-ink/80"
            }`}
          >
            {schedule.alert}
          </p>
        </div>

        <div className="flex items-center gap-3 text-right">
          <div>
            <div className="text-[10px] uppercase tracking-wide text-ink/50">Dedicação</div>
            <div className="font-semibold text-ink">{schedule.weekly_hours}h/semana</div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-wide text-ink/50">Conclusão Prevista</div>
            <div className="font-semibold text-ink">{formatDate(schedule.estimated_completion_date)}</div>
          </div>
        </div>
      </div>

      {/* Suggested Hours Callout if at risk */}
      {schedule.is_at_risk && schedule.suggested_weekly_hours && (
        <div className="rounded border border-gap/30 bg-gap/5 p-2.5 text-[11px] text-ink/80">
          <span className="font-semibold text-gap">Ajuste recomendado de ritmo: </span>
          <span>
            Para concluir até a data limite ({formatDate(schedule.deadline)}), a dedicação sugerida é de{" "}
            <strong>{schedule.suggested_weekly_hours}h/semana</strong>.
          </span>
        </div>
      )}

      {/* Fila de Pesquisa Highlights */}
      {queuedItems.length > 0 && (
        <div className="rounded border border-available/30 bg-available/5 p-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-available text-[11px] uppercase tracking-wider">
              Fila de Pesquisa Prioritária ({queuedItems.length})
            </span>
            <span className="text-[10px] text-ink/60">Próximos focos de investigação</span>
          </div>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 md:grid-cols-3">
            {queuedItems.map((item) => (
              <div
                key={item.node_key}
                onClick={() => onSelectNode?.(item.node_key)}
                className="cursor-pointer rounded border border-available/20 bg-white p-2.5 transition hover:shadow-sm"
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-ink truncate text-xs">{item.title}</span>
                  <span className="text-[10px] text-available font-semibold">{item.typical_time}</span>
                </div>
                <div className="mt-1 text-[10px] text-ink/60">
                  Previsão: {formatDate(item.estimated_start)} até {formatDate(item.estimated_end)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Upcoming Steps Timeline Toggle */}
      <div className="border-t border-ink/10 pt-2">
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="flex items-center justify-between w-full text-left text-ink/70 hover:text-ink text-[11px] py-1"
        >
          <span>
            {expanded
              ? "Ocultar projeção detalhada de etapas"
              : `Visualizar projeção das próximas ${upcomingItems.length} etapas restantes`}
          </span>
          <span>{expanded ? "▲" : "▼"}</span>
        </button>

        {expanded && (
          <div className="mt-2 space-y-1.5 pt-1">
            {schedule.items.map((item, idx) => (
              <div
                key={item.node_key}
                onClick={() => onSelectNode?.(item.node_key)}
                className="flex items-center justify-between rounded p-1.5 hover:bg-paper cursor-pointer transition text-[11px]"
              >
                <div className="flex items-center gap-2">
                  <span className="w-5 text-[10px] text-ink/40 font-mono">{idx + 1}.</span>
                  <span className="font-medium text-ink">{item.title}</span>
                  {item.queued && (
                    <span className="rounded bg-available/10 px-1.5 py-0.2 text-[9px] text-available font-semibold">
                      fila
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-3 text-ink/60 text-[10px]">
                  <span>{item.typical_time}</span>
                  <span>
                    {formatDate(item.estimated_start)} → {formatDate(item.estimated_end)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
