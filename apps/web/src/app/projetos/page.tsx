"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import React, { useCallback, useEffect, useState } from "react";
import { ApiError, api, clearToken, getToken, Project, TreeData, WORK_LABELS } from "@/lib/api";
import { AppHeader } from "@/components/app-header";
import { AlertBanner, Button } from "@/components/ui";

type ProjectSummary = {
  doneCount: number;
  availableCount: number;
  totalCount: number;
  nextStepTitle: string | null;
  phase: string | null;
};

function phaseFromProgress(doneCount: number, totalCount: number): string {
  if (totalCount === 0) return "Não iniciado";
  const pct = doneCount / totalCount;
  if (pct === 0) return "Não iniciado";
  if (pct < 0.25) return "Ideia";
  if (pct < 0.5) return "Planejamento";
  if (pct < 0.85) return "Desenvolvimento";
  if (pct < 1) return "Finalização";
  return "Concluído";
}

const PHASE_COLORS: Record<string, string> = {
  "Não iniciado": "bg-borda text-locked",
  "Ideia": "bg-skipped-bg text-purple",
  "Planejamento": "bg-orange/20 text-ink",
  "Desenvolvimento": "bg-done/20 text-done",
  "Finalização": "bg-purple/15 text-purple",
  "Concluído": "bg-done text-paper",
};

const navLinkCls = "inline-flex min-h-[36px] items-center rounded-[8px] border border-borda px-3 text-[13px] font-medium text-locked hover:border-purple hover:text-purple transition";
const navLinkPrimaryCls = "inline-flex min-h-[36px] items-center rounded-[8px] border border-purple px-3 text-[13px] font-medium text-purple hover:bg-purple hover:text-paper transition";

export default function ProjetosPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [summaries, setSummaries] = useState<Record<string, ProjectSummary>>({});
  const [advisingProjects, setAdvisingProjects] = useState<Project[]>([]);
  const [error, setError] = useState<string | null>(null);

  const leave = useCallback(() => {
    clearToken();
    router.replace("/entrar");
  }, [router]);

  useEffect(() => {
    if (!getToken()) { router.replace("/entrar"); return; }
    let cancelled = false;
    api<Project[]>("/projects")
      .then(async (list) => {
        if (cancelled) return;
        const entries = await Promise.all(
          list.map(async (p) => {
            try {
              const tree = await api<TreeData>(`/projects/${p.id}/tree`);
              const doneCount = tree.nodes.filter((n) => n.status === "done" || n.status === "skipped").length;
              const availableNodes = tree.nodes.filter((n) => n.status === "available");
              const queuedNext = availableNodes.find((n) => n.queued) ?? availableNodes[0] ?? null;
              return [p.id, {
                doneCount, availableCount: availableNodes.length,
                totalCount: tree.nodes.length,
                nextStepTitle: queuedNext ? queuedNext.title : null,
                phase: phaseFromProgress(doneCount, tree.nodes.length),
              }] as const;
            } catch {
              return [p.id, { doneCount: 0, availableCount: 0, totalCount: 0, nextStepTitle: null, phase: "Não iniciado" }] as const;
            }
          })
        );
        if (!cancelled) { setSummaries(Object.fromEntries(entries)); setProjects(list); }
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) return leave();
        setError(err instanceof Error ? err.message : "Algo deu errado.");
      });

    api<Project[]>("/advising-projects")
      .then((list) => { if (!cancelled) setAdvisingProjects(list); })
      .catch(() => {});

    return () => { cancelled = true; };
  }, [leave, router]);

  const totalDone = Object.values(summaries).reduce((acc, s) => acc + s.doneCount, 0);
  const totalSteps = Object.values(summaries).reduce((acc, s) => acc + s.totalCount, 0);
  const projectCount = projects?.length ?? 0;
  const activeCount = Object.values(summaries).filter((s) => s.doneCount > 0 && s.doneCount < s.totalCount).length;

  return (
    <div className="min-h-screen flex flex-col bg-paper text-ink">
      <AppHeader onLeave={leave} />

      <main className="mx-auto w-full max-w-[1360px] flex-1 px-4 py-8 sm:px-10 sm:py-10">

        {/* Page heading + CTA */}
        <div className="flex flex-wrap items-end justify-between gap-4 mb-8">
          <div>
            <h1 className="font-display text-3xl sm:text-[38px] text-ink leading-tight">Seus projetos</h1>
            {projects !== null && (
              <p className="mt-1 text-[15px] text-locked">
                {projectCount === 0
                  ? "Nenhum projeto ainda."
                  : `${projectCount} ${projectCount === 1 ? "projeto" : "projetos"} · ${activeCount} em andamento`}
              </p>
            )}
          </div>
          <Button type="button" variant="primary" onClick={() => router.push("/projetos/novo")} className="shrink-0">
            + Novo projeto
          </Button>
        </div>

        {/* KPI tiles */}
        {projectCount > 0 && totalSteps > 0 && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4 mb-8">
            {[
              { label: "Projetos", value: projectCount },
              { label: "Em andamento", value: activeCount },
              { label: "Etapas concluídas", value: totalDone },
              { label: "Progresso geral", value: totalSteps > 0 ? Math.round((totalDone / totalSteps) * 100) : 0, suffix: "%" },
            ].map((kpi) => (
              <div key={kpi.label} className="rounded-[14px] border border-borda bg-superficie p-4 sm:p-5">
                <p className="text-[11px] sm:text-[12px] font-bold uppercase tracking-wider text-locked">{kpi.label}</p>
                <p className="mt-1.5 font-display text-[28px] sm:text-[32px] text-ink">
                  {kpi.value}
                  {kpi.suffix && <span className="text-[16px] text-locked font-sans">{kpi.suffix}</span>}
                </p>
              </div>
            ))}
          </div>
        )}

        {error && <AlertBanner variant="error">{error}</AlertBanner>}

        {/* Loading skeleton */}
        {projects === null && !error && (
          <div className="space-y-4">
            {[1, 2].map((i) => (
              <div key={i} className="rounded-[16px] border border-borda bg-superficie p-6 sm:p-7 animate-pulse">
                <div className="h-6 w-2/3 rounded bg-borda mb-3" />
                <div className="h-3 w-1/3 rounded bg-borda mb-4" />
                <div className="h-2.5 w-full rounded-full bg-borda" />
              </div>
            ))}
          </div>
        )}

        {/* Empty state */}
        {projects?.length === 0 && (
          <div className="rounded-[16px] border border-borda bg-superficie p-10 text-center">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-purple/10">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-7 w-7 text-purple">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-3-3v6M3 6l3-3h12l3 3v14a1 1 0 01-1 1H4a1 1 0 01-1-1V6z" />
              </svg>
            </div>
            <h2 className="font-display text-xl text-ink">Nenhum projeto ainda</h2>
            <p className="mt-2 text-[15px] text-locked max-w-sm mx-auto">Crie seu primeiro projeto de pesquisa e comece a orientação socrática.</p>
            <Button type="button" variant="primary" className="mt-5" onClick={() => router.push("/projetos/novo")}>
              + Criar primeiro projeto
            </Button>
          </div>
        )}

        {/* Project list */}
        <ul className="space-y-5">
          {projects?.map((p) => {
            const summary = summaries[p.id];
            const doneCount = summary?.doneCount ?? 0;
            const availableCount = summary?.availableCount ?? 0;
            const totalCount = summary?.totalCount ?? 0;
            const progressPct = totalCount > 0 ? Math.max(doneCount > 0 ? 4 : 0, Math.round((doneCount / totalCount) * 100)) : 0;
            const phase = summary?.phase ?? "Não iniciado";
            const phaseClass = PHASE_COLORS[phase] ?? "bg-borda text-locked";

            return (
              <li key={p.id} className="group rounded-[16px] border border-borda bg-superficie p-5 sm:p-7 hover:border-purple/40 hover:shadow-sm transition-all">
                {/* Header */}
                <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2 mb-1.5">
                      <span className={`inline-flex items-center rounded-[6px] px-2.5 py-0.5 text-[12px] font-bold uppercase tracking-wider ${phaseClass}`}>{phase}</span>
                      <span className="text-[12px] sm:text-[13px] text-locked">
                        {WORK_LABELS[p.work] ?? p.work}
                        {p.institution ? ` · ${p.institution}` : ""}
                        {" · "}{p.citation_style.toUpperCase()}
                      </span>
                    </div>
                    <h2 className="font-display text-lg sm:text-[22px] leading-snug text-ink">{p.title}</h2>
                  </div>
                  <div className="text-right shrink-0">
                    <span className="font-display text-2xl text-ink">{progressPct}<span className="text-[14px] text-locked font-sans">%</span></span>
                    <p className="text-[12px] text-locked">concluído</p>
                  </div>
                </div>

                {/* Progress bar */}
                <div className="mb-4">
                  <div role="progressbar" aria-valuenow={progressPct} aria-valuemin={0} aria-valuemax={100} className="h-2 w-full overflow-hidden rounded-full bg-paper">
                    <div className="h-full rounded-full bg-done transition-all duration-500" style={{ width: `${progressPct}%` }} />
                  </div>
                  <div className="mt-1.5 flex items-center justify-between text-[13px] text-locked">
                    <span>{doneCount} {doneCount === 1 ? "etapa concluída" : "etapas concluídas"} de {totalCount}</span>
                    {availableCount > 0 && <span className="text-purple font-medium">{availableCount} {availableCount === 1 ? "disponível" : "disponíveis"}</span>}
                  </div>
                </div>

                {/* Next step */}
                {summary?.nextStepTitle && (
                  <div className="mb-4 flex items-start gap-2 rounded-[10px] border border-borda bg-paper px-4 py-3">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" className="h-4 w-4 shrink-0 text-purple mt-0.5"><polyline points="9 18 15 12 9 6" /></svg>
                    <p className="text-[14px] text-ink">
                      <span className="font-medium text-locked">Próxima etapa: </span>
                      <span className="font-medium text-ink bg-orange/30 px-1 rounded">{summary.nextStepTitle}</span>
                    </p>
                  </div>
                )}

                {/* Footer */}
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex flex-wrap items-center gap-1.5 text-[13px] text-locked">
                    {p.deadline && (
                      <span className="inline-flex items-center gap-1 rounded-[6px] border border-borda px-2 py-0.5">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" className="h-3.5 w-3.5">
                          <rect x="3" y="4" width="18" height="18" rx="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" />
                        </svg>
                        Prazo: {p.deadline.split("-").reverse().join("/")}
                      </span>
                    )}
                    {p.weekly_hours && <span className="inline-flex items-center gap-1 rounded-[6px] border border-borda px-2 py-0.5">{p.weekly_hours} h/sem</span>}
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Link href={`/projetos/${p.id}/arvore`} className={navLinkPrimaryCls}>Árvore</Link>
                    <Link href={`/projetos/${p.id}/editor`} className={navLinkPrimaryCls}>Editor</Link>
                    <Link href={`/projetos/${p.id}/referencias`} className={navLinkCls}>Referências</Link>
                    <Link href={`/projetos/${p.id}/mapa`} className={navLinkCls}>Mapa</Link>
                    <Link href={`/projetos/${p.id}/relatorio`} className={navLinkCls}>Relatório</Link>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>

        {/* Advising projects */}
        {advisingProjects.length > 0 && (
          <section aria-label="Projetos sob orientação" className="mt-12">
            <div className="flex items-center gap-3 mb-5">
              <h2 className="font-display text-2xl text-ink">Projetos sob sua orientação</h2>
              <span className="rounded-full bg-purple/10 px-2.5 py-0.5 text-[13px] font-bold text-purple">{advisingProjects.length}</span>
            </div>
            <ul className="space-y-4">
              {advisingProjects.map((p) => (
                <li key={p.id} className="rounded-[16px] border border-borda bg-superficie p-5 sm:p-6 hover:border-purple/40 transition">
                  <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
                    <div>
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className="rounded-[6px] bg-skipped-bg px-2.5 py-0.5 text-[12px] font-bold uppercase tracking-wider text-purple">Orientando</span>
                        <span className="text-[13px] text-locked">
                          {WORK_LABELS[p.work] ?? p.work}{p.institution ? ` · ${p.institution}` : ""} · {p.citation_style.toUpperCase()}
                        </span>
                      </div>
                      <h3 className="font-display text-xl text-ink">{p.title}</h3>
                    </div>
                    {p.deadline && <span className="text-[13px] text-locked">Prazo: {p.deadline.split("-").reverse().join("/")}</span>}
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Link href={`/projetos/${p.id}/arvore`} className={navLinkPrimaryCls}>Árvore</Link>
                    <Link href={`/projetos/${p.id}/editor`} className={navLinkPrimaryCls}>Editor</Link>
                    <Link href={`/projetos/${p.id}/referencias`} className={navLinkCls}>Referências</Link>
                    <Link href={`/projetos/${p.id}/mapa`} className={navLinkCls}>Mapa</Link>
                    <Link href={`/projetos/${p.id}/relatorio`} className={navLinkCls}>Relatório</Link>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        )}
      </main>
    </div>
  );
}
