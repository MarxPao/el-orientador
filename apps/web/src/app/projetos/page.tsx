"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import React, { useCallback, useEffect, useState } from "react";
import { ApiError, api, clearToken, getToken, Project, TreeData, WORK_LABELS } from "@/lib/api";
import { AppHeader } from "@/components/app-header";
import { AlertBanner, Button } from "@/components/ui";

const inputClass =
  "mt-1.5 w-full h-[46px] rounded-[10px] border border-borda bg-superficie px-3.5 text-[15px] text-ink focus:border-purple";

type ProjectSummary = {
  doneCount: number;
  availableCount: number;
  totalCount: number;
  nextStepTitle: string | null;
};

export default function ProjetosPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [summaries, setSummaries] = useState<Record<string, ProjectSummary>>({});
  const [advisingProjects, setAdvisingProjects] = useState<Project[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const leave = useCallback(() => {
    clearToken();
    router.replace("/entrar");
  }, [router]);

  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/entrar");
      return;
    }
    let cancelled = false;
    api<Project[]>("/projects")
      .then(async (list) => {
        if (cancelled) return;

        const entries = await Promise.all(
          list.map(async (p) => {
            try {
              const tree = await api<TreeData>(`/projects/${p.id}/tree`);
              const doneCount = tree.nodes.filter(
                (n) => n.status === "done" || n.status === "skipped"
              ).length;
              const availableNodes = tree.nodes.filter((n) => n.status === "available");
              const queuedNext = availableNodes.find((n) => n.queued) ?? availableNodes[0] ?? null;
              return [
                p.id,
                {
                  doneCount,
                  availableCount: availableNodes.length,
                  totalCount: tree.nodes.length,
                  nextStepTitle: queuedNext ? queuedNext.title : null,
                },
              ] as const;
            } catch {
              return [
                p.id,
                {
                  doneCount: 0,
                  availableCount: 0,
                  totalCount: 0,
                  nextStepTitle: null,
                },
              ] as const;
            }
          })
        );

        if (!cancelled) {
          setSummaries(Object.fromEntries(entries));
          setProjects(list);
        }
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) return leave();
        setError(err instanceof Error ? err.message : "Algo deu errado.");
      });

    api<Project[]>("/advising-projects")
      .then((list) => {
        if (!cancelled) setAdvisingProjects(list);
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [reloadKey, leave, router]);

  async function onCreate(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    const hours = f.get("weekly_hours");
    setBusy(true);
    setError(null);
    try {
      await api<Project>("/projects", {
        method: "POST",
        body: {
          title: f.get("title"),
          work: f.get("work"),
          institution: f.get("institution") || null,
          citation_style: f.get("citation_style"),
          deadline: f.get("deadline") || null,
          weekly_hours: hours ? Number(hours) : null,
        },
      });
      form.reset();
      setReloadKey((k) => k + 1);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return leave();
      setError(err instanceof Error ? err.message : "Algo deu errado.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-paper text-ink">
      <AppHeader onLeave={leave} />

      <main className="mx-auto w-full max-w-[1360px] flex-1 px-6 py-10 sm:px-10">
        <div className="flex flex-col lg:flex-row items-start gap-10">
          {/* Coluna principal: Seus projetos */}
          <div className="w-full flex-1 space-y-8">
            <section aria-label="Projetos existentes">
              <h1 className="font-display text-3xl sm:text-[38px] text-ink">Seus projetos</h1>

              {projects === null && !error && (
                <p className="mt-6 text-[15px] text-locked">Carregando seus projetos…</p>
              )}

              {projects?.length === 0 && (
                <div className="mt-6 rounded-[14px] border border-borda bg-superficie p-6 text-[15px] text-locked">
                  Você ainda não tem projetos cadastrados. Use o formulário ao lado para criar o primeiro.
                </div>
              )}

              <ul className="mt-6 space-y-5">
                {projects?.map((p) => {
                  const summary = summaries[p.id];
                  const doneCount = summary?.doneCount ?? 0;
                  const availableCount = summary?.availableCount ?? 0;
                  const totalCount = summary?.totalCount ?? 0;
                  const progressPct =
                    totalCount > 0 ? Math.max(doneCount > 0 ? 10 : 0, Math.round((doneCount / totalCount) * 100)) : 0;

                  return (
                    <li
                      key={p.id}
                      className="rounded-[16px] border border-borda bg-superficie p-6 sm:p-7 space-y-4"
                    >
                      <div className="flex flex-wrap items-baseline justify-between gap-4">
                        <h2 className="font-display text-xl sm:text-[24px] leading-snug text-ink max-w-xl">
                          {p.title}
                        </h2>
                        <span className="text-[14px] text-locked">
                          {WORK_LABELS[p.work] ?? p.work}
                          {p.institution ? ` · ${p.institution}` : ""} · {p.citation_style.toUpperCase()}
                          {p.deadline ? ` · prazo ${p.deadline.split("-").reverse().join("/")}` : ""}
                          {p.weekly_hours ? ` · ${p.weekly_hours} h/semana` : ""}
                        </span>
                      </div>

                      {/* Barra de progresso em oliva */}
                      <div className="space-y-1.5">
                        <div
                          role="progressbar"
                          aria-valuenow={progressPct}
                          aria-valuemin={0}
                          aria-valuemax={100}
                          className="h-2.5 w-full overflow-hidden rounded-full bg-paper"
                        >
                          <div
                            className="h-full rounded-full bg-done transition-all"
                            style={{ width: `${progressPct}%` }}
                          />
                        </div>
                        <p className="text-[14px] text-locked">
                          {doneCount > 0
                            ? `${doneCount} ${doneCount === 1 ? "etapa concluída" : "etapas concluídas"} · ${availableCount} ${
                                availableCount === 1 ? "disponível" : "disponíveis"
                              }`
                            : "Sem etapas concluídas ainda"}
                        </p>
                      </div>

                      {/* Próxima etapa com marca-texto laranja e texto tinta */}
                      {summary?.nextStepTitle && (
                        <p className="text-[15px] text-ink">
                          <span>Próxima etapa: </span>
                          <mark className="mark-orange font-medium">{summary.nextStepTitle}</mark>
                        </p>
                      )}

                      {/* Links de atalho em roxo */}
                      <div className="pt-1 flex flex-wrap items-center gap-5 text-[15px]">
                        <Link
                          href={`/projetos/${p.id}/arvore`}
                          className="inline-flex min-h-[44px] items-center font-bold text-purple hover:underline"
                        >
                          Árvore de progresso
                        </Link>
                        <Link
                          href={`/projetos/${p.id}/mapa`}
                          className="inline-flex min-h-[44px] items-center font-bold text-purple hover:underline"
                        >
                          Mapa de conhecimento
                        </Link>
                        <Link
                          href={`/projetos/${p.id}/editor`}
                          className="inline-flex min-h-[44px] items-center font-bold text-purple hover:underline"
                        >
                          Editor
                        </Link>
                        <Link
                          href={`/projetos/${p.id}/relatorio`}
                          className="inline-flex min-h-[44px] items-center font-bold text-purple hover:underline"
                        >
                          Relatório
                        </Link>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </section>

            {advisingProjects.length > 0 && (
              <section aria-label="Projetos sob orientação" className="pt-4">
                <h2 className="font-display text-2xl text-ink">
                  Projetos sob sua orientação ({advisingProjects.length})
                </h2>
                <ul className="mt-4 space-y-4">
                  {advisingProjects.map((p) => (
                    <li
                      key={p.id}
                      className="rounded-[16px] border border-borda bg-superficie p-6 space-y-3"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <h3 className="font-display text-xl text-ink">{p.title}</h3>
                        <span className="rounded-[6px] bg-skipped-bg px-3 py-1 text-[13px] font-bold uppercase tracking-wider text-purple">
                          Orientando
                        </span>
                      </div>
                      <p className="text-[14px] text-locked">
                        {WORK_LABELS[p.work] ?? p.work}
                        {p.institution ? ` · ${p.institution}` : ""} · {p.citation_style.toUpperCase()}
                        {p.deadline ? ` · prazo ${p.deadline.split("-").reverse().join("/")}` : ""}
                      </p>
                      <div className="flex flex-wrap items-center gap-5 text-[15px]">
                        <Link
                          href={`/projetos/${p.id}/arvore`}
                          className="inline-flex min-h-[44px] items-center font-bold text-purple hover:underline"
                        >
                          Árvore de progresso
                        </Link>
                        <Link
                          href={`/projetos/${p.id}/mapa`}
                          className="inline-flex min-h-[44px] items-center font-bold text-purple hover:underline"
                        >
                          Mapa de conhecimento
                        </Link>
                        <Link
                          href={`/projetos/${p.id}/editor`}
                          className="inline-flex min-h-[44px] items-center font-bold text-purple hover:underline"
                        >
                          Editor
                        </Link>
                        <Link
                          href={`/projetos/${p.id}/relatorio`}
                          className="inline-flex min-h-[44px] items-center font-bold text-purple hover:underline"
                        >
                          Relatório
                        </Link>
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>

          {/* Coluna lateral de 400 px: Novo projeto */}
          <aside
            aria-label="Novo projeto"
            className="w-full lg:w-[400px] shrink-0 rounded-[16px] border border-borda bg-superficie p-6 sm:p-7"
          >
            <h2 className="font-display text-2xl text-ink">Novo projeto</h2>

            <form onSubmit={onCreate} className="mt-5 space-y-4">
              <label className="block text-[15px] font-medium text-ink">
                Título do trabalho
                <input name="title" required minLength={3} maxLength={200} className={inputClass} />
              </label>

              <label className="block text-[15px] font-medium text-ink">
                Tipo de trabalho
                <select name="work" required defaultValue="tcc" className={inputClass}>
                  {Object.entries(WORK_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="block text-[15px] font-medium text-ink">
                Instituição (opcional)
                <input name="institution" maxLength={200} className={inputClass} />
              </label>

              <label className="block text-[15px] font-medium text-ink">
                Norma de citação
                <select name="citation_style" defaultValue="abnt" className={inputClass}>
                  <option value="abnt">ABNT</option>
                  <option value="apa">APA</option>
                  <option value="vancouver">Vancouver</option>
                </select>
              </label>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <label className="block text-[15px] font-medium text-ink">
                  Prazo de entrega
                  <input name="deadline" type="date" className={inputClass} />
                </label>

                <label className="block text-[15px] font-medium text-ink">
                  Horas / semana
                  <input name="weekly_hours" type="number" min={1} max={100} className={inputClass} />
                </label>
              </div>

              {error && <AlertBanner variant="error">{error}</AlertBanner>}

              <div className="pt-2">
                <Button type="submit" variant="primary" disabled={busy} className="w-full">
                  {busy ? "Criando…" : "Criar projeto"}
                </Button>
              </div>
            </form>
          </aside>
        </div>
      </main>
    </div>
  );
}
