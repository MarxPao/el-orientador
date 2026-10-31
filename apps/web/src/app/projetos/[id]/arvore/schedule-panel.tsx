"use client";

import React, { useEffect, useState } from "react";
import { api, ScheduleData } from "@/lib/api";
import { AlertIcon, CheckIcon } from "@/components/ui";

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
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [projectId, reloadKey]);

  if (!schedule && loading) {
    return (
      <div className="rounded-[14px] border border-borda bg-superficie p-4 text-[15px] text-locked">
        Calculando cronograma e estimativas de prazo…
      </div>
    );
  }

  if (!schedule) return null;

  const queuedItems = schedule.items.filter((item) => item.queued);
  const upcomingItems = schedule.items.slice(0, 5);

  return (
    <section
      aria-label="Cronograma e Fila de Pesquisa"
      className="rounded-[14px] border border-borda bg-superficie p-5 sm:p-6 space-y-4"
    >
      {/* Header & Alert Bar */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1.5">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="font-display text-xl text-ink">Cronograma & Prazos</h2>
            <span
              className={`inline-flex items-center gap-1.5 rounded-[6px] px-2.5 py-0.5 text-[13px] font-bold uppercase tracking-wider ${
                schedule.is_at_risk
                  ? "border-2 border-dotted border-purple bg-superficie text-purple"
                  : schedule.deadline
                  ? "bg-done text-paper"
                  : "border border-borda bg-paper text-locked"
              }`}
            >
              {schedule.is_at_risk ? (
                <>
                  <AlertIcon className="h-3.5 w-3.5 text-purple" />
                  <span>Atenção ao prazo</span>
                </>
              ) : schedule.deadline ? (
                <>
                  <CheckIcon className="h-3.5 w-3.5 text-paper" />
                  <span>No prazo</span>
                </>
              ) : (
                <span>Sem prazo definido</span>
              )}
            </span>
          </div>
          <p className="text-[15px] leading-relaxed text-ink">{schedule.alert}</p>
        </div>

        <div className="flex items-center gap-6 text-right">
          <div>
            <div className="text-[13px] font-bold uppercase tracking-wider text-locked">Dedicação</div>
            <div className="text-[15px] font-bold text-ink">{schedule.weekly_hours}h/semana</div>
          </div>
          <div>
            <div className="text-[13px] font-bold uppercase tracking-wider text-locked">Conclusão prevista</div>
            <div className="text-[15px] font-bold text-ink">{formatDate(schedule.estimated_completion_date)}</div>
          </div>
        </div>
      </div>

      {/* Suggested Hours Callout if at risk */}
      {schedule.is_at_risk && schedule.suggested_weekly_hours && (
        <div className="flex items-start gap-3 rounded-[10px] border-2 border-dotted border-purple bg-paper p-3.5 text-[15px] text-ink">
          <AlertIcon className="mt-0.5 h-5 w-5 shrink-0 text-purple" />
          <div>
            <span className="font-bold text-purple">Ajuste recomendado de ritmo: </span>
            <span>
              Para concluir até a data limite ({formatDate(schedule.deadline)}), a dedicação sugerida é de{" "}
              <strong>{schedule.suggested_weekly_hours}h/semana</strong>.
            </span>
          </div>
        </div>
      )}

      {/* Fila de Pesquisa Highlights */}
      {queuedItems.length > 0 && (
        <div className="rounded-[12px] border border-borda bg-paper p-4 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-[13px] font-bold uppercase tracking-wider text-ink">
              Fila de pesquisa prioritária ({queuedItems.length})
            </span>
            <span className="text-[14px] text-locked">Próximos focos de investigação</span>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
            {queuedItems.map((item) => (
              <button
                type="button"
                key={item.node_key}
                onClick={() => onSelectNode?.(item.node_key)}
                className="text-left cursor-pointer rounded-[10px] border border-borda bg-superficie p-3.5 transition hover:border-purple min-h-[44px]"
              >
                <div className="flex items-center justify-between gap-2">
                  <mark className="mark-orange text-[15px] font-medium truncate">{item.title}</mark>
                  <span className="shrink-0 text-[13px] font-bold text-locked">{item.typical_time}</span>
                </div>
                <div className="mt-1.5 text-[14px] text-locked">
                  Previsão: {formatDate(item.estimated_start)} até {formatDate(item.estimated_end)}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Upcoming Steps Timeline Toggle */}
      <div className="border-t border-borda pt-2">
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="flex min-h-[44px] w-full items-center justify-between text-left text-[15px] font-medium text-purple hover:underline cursor-pointer"
        >
          <span>
            {expanded
              ? "Ocultar projeção detalhada de etapas"
              : `Visualizar projeção das próximas ${upcomingItems.length} etapas restantes`}
          </span>
          <span aria-hidden>{expanded ? "▲" : "▼"}</span>
        </button>

        {expanded && (
          <div className="mt-2 space-y-1.5 pt-1">
            {schedule.items.map((item, idx) => (
              <button
                type="button"
                key={item.node_key}
                onClick={() => onSelectNode?.(item.node_key)}
                className="flex min-h-[44px] w-full items-center justify-between rounded-[8px] px-3 py-2 text-left text-[15px] hover:bg-paper cursor-pointer transition"
              >
                <div className="flex items-center gap-3">
                  <span className="w-6 text-[14px] font-mono text-locked">{idx + 1}.</span>
                  <span className="font-medium text-ink">{item.title}</span>
                  {item.queued && (
                    <mark className="mark-orange text-[13px] font-bold uppercase tracking-wider">fila</mark>
                  )}
                </div>
                <div className="flex items-center gap-4 text-[14px] text-locked">
                  <span>{item.typical_time}</span>
                  <span>
                    {formatDate(item.estimated_start)} → {formatDate(item.estimated_end)}
                  </span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
