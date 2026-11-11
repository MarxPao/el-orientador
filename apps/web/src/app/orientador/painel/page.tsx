"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  clearToken,
  CohortDashboardResponse,
  CohortStudentOverview,
  downloadCohortExport,
  getCohortSummary,
  getToken,
  linkAdvisee,
  WORK_LABELS,
} from "@/lib/api";
import { AppHeader } from "@/components/app-header";
import { AlertBanner, Button } from "@/components/ui";

function RiskBadge({ level, label }: { level: CohortStudentOverview["schedule"]["risk_level"]; label: string }) {
  if (level === "overdue") {
    return (
      <span className="inline-flex items-center gap-1 rounded-[6px] border border-brand-red/40 bg-brand-red/10 px-2 py-0.5 text-[12px] font-semibold text-brand-red">
        <span className="h-1.5 w-1.5 rounded-full bg-brand-red" />
        {label}
      </span>
    );
  }
  if (level === "critical") {
    return (
      <span className="inline-flex items-center gap-1 rounded-[6px] border border-orange/40 bg-orange/15 px-2 py-0.5 text-[12px] font-semibold text-orange">
        <span className="h-1.5 w-1.5 rounded-full bg-orange" />
        {label}
      </span>
    );
  }
  if (level === "warning") {
    return (
      <span className="inline-flex items-center gap-1 rounded-[6px] border border-orange/30 bg-orange/10 px-2 py-0.5 text-[12px] font-medium text-ink">
        <span className="h-1.5 w-1.5 rounded-full bg-orange" />
        {label}
      </span>
    );
  }
  if (level === "ontrack") {
    return (
      <span className="inline-flex items-center gap-1 rounded-[6px] border border-done/30 bg-done/15 px-2 py-0.5 text-[12px] font-medium text-done">
        <span className="h-1.5 w-1.5 rounded-full bg-done" />
        {label}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-[6px] border border-borda bg-card px-2 py-0.5 text-[12px] text-locked">
      {label}
    </span>
  );
}

export default function AdvisorCohortDashboardPage() {
  const router = useRouter();
  const [data, setData] = useState<CohortDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Filters & Controls
  const [searchQuery, setSearchQuery] = useState("");
  const [riskFilter, setRiskFilter] = useState<"all" | "at_risk" | "skipped" | "comments">("all");
  const [workFilter, setWorkFilter] = useState<string>("all");
  const [sortBy, setSortBy] = useState<"deadline" | "progress_asc" | "progress_desc" | "name">("deadline");

  // Link advisee modal
  const [showLinkModal, setShowLinkModal] = useState(false);
  const [linkInput, setLinkInput] = useState("");
  const [linking, setLinking] = useState(false);

  const leave = useCallback(() => {
    clearToken();
    router.replace("/entrar");
  }, [router]);

  const loadData = useCallback(() => {
    if (!getToken()) {
      router.replace("/entrar");
      return;
    }
    setLoading(true);
    getCohortSummary()
      .then((res) => {
        setData(res);
        setError(null);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          leave();
          return;
        }
        setError(err instanceof Error ? err.message : "Erro ao carregar painel da turma.");
      })
      .finally(() => setLoading(false));
  }, [leave, router]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function handleExport(format: "csv" | "markdown") {
    try {
      await downloadCohortExport(format);
      setNotice(`Ata de acompanhamento exportada com sucesso (${format.toUpperCase()}).`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao exportar ata.");
    }
  }

  async function handleLinkAdvisee(e: React.FormEvent) {
    e.preventDefault();
    if (!linkInput.trim()) return;
    setLinking(true);
    setError(null);
    try {
      const val = linkInput.trim();
      const payload = val.includes("/") ? { share_token: val.split("/").pop() } : { project_id: val };
      const res = await linkAdvisee(payload);
      setNotice(res.message);
      setShowLinkModal(false);
      setLinkInput("");
      loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao vincular orientando.");
    } finally {
      setLinking(false);
    }
  }

  // Filtered and sorted students
  const filteredStudents = useMemo(() => {
    if (!data) return [];
    let list = [...data.students];

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter(
        (s) =>
          s.student.name.toLowerCase().includes(q) ||
          s.student.email.toLowerCase().includes(q) ||
          s.title.toLowerCase().includes(q) ||
          s.institution.toLowerCase().includes(q)
      );
    }

    if (riskFilter === "at_risk") {
      list = list.filter((s) => s.schedule.risk_level === "critical" || s.schedule.risk_level === "overdue");
    } else if (riskFilter === "skipped") {
      list = list.filter((s) => s.progress.skipped_count > 0);
    } else if (riskFilter === "comments") {
      list = list.filter((s) => s.governance.unresolved_comments_count > 0);
    }

    if (workFilter !== "all") {
      list = list.filter((s) => s.work === workFilter);
    }

    list.sort((a, b) => {
      if (sortBy === "deadline") {
        const da = a.schedule.days_until_deadline ?? 99999;
        const db = b.schedule.days_until_deadline ?? 99999;
        return da - db;
      }
      if (sortBy === "progress_asc") {
        return a.progress.completion_rate - b.progress.completion_rate;
      }
      if (sortBy === "progress_desc") {
        return b.progress.completion_rate - a.progress.completion_rate;
      }
      return a.student.name.localeCompare(b.student.name);
    });

    return list;
  }, [data, searchQuery, riskFilter, workFilter, sortBy]);

  return (
    <div className="min-h-screen flex flex-col bg-paper text-ink">
      <AppHeader onLeave={leave} />

      <main className="flex-1 w-full max-w-[1440px] mx-auto px-6 sm:px-10 py-8 space-y-8">
        {/* Breadcrumb & Title */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <nav aria-label="Navegação estrutural" className="flex items-center gap-2 text-[14px] text-locked mb-1">
              <Link href="/projetos" className="hover:text-purple transition">Projetos</Link>
              <span>›</span>
              <span className="text-ink font-medium">Painel Multi-orientandos & Turmas</span>
            </nav>
            <h1 className="font-display text-3xl sm:text-4xl text-ink">
              Coordenação & Orientação de Turmas
            </h1>
            <p className="mt-1 text-[15px] text-locked max-w-2xl">
              Acompanhamento centralizado de entregas, auditoria de etapas puladas e alertas preditivos de prazo para múltiplos orientandos.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setShowLinkModal(true)}
            >
              + Vincular Orientando
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => handleExport("csv")}
            >
              Exportar Ata (CSV)
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => handleExport("markdown")}
            >
              Exportar Ata (MD)
            </Button>
          </div>
        </div>

        {error && <AlertBanner variant="error">{error}</AlertBanner>}
        {notice && (
          <div role="status" className="rounded-[10px] bg-done/15 border border-done/30 px-4 py-3 text-[14px] text-done flex items-center justify-between">
            <span>{notice}</span>
            <button onClick={() => setNotice(null)} className="text-done/70 hover:text-done text-sm font-semibold">✕</button>
          </div>
        )}

        {/* Aggregated Metric Cards */}
        {data && (
          <section aria-label="Métricas gerais da turma" className="grid grid-cols-2 lg:grid-cols-5 gap-4">
            <div className="rounded-[14px] border border-borda bg-superficie p-4 flex flex-col justify-between">
              <span className="text-[12px] font-medium uppercase tracking-wider text-locked">Total de Orientandos</span>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="font-display text-3xl text-ink">{data.metrics.total_advisees}</span>
                <span className="text-[13px] text-locked">estudantes</span>
              </div>
            </div>

            <div className="rounded-[14px] border border-borda bg-superficie p-4 flex flex-col justify-between">
              <span className="text-[12px] font-medium uppercase tracking-wider text-locked">Média de Conclusão</span>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="font-display text-3xl text-purple">{data.metrics.average_progress}%</span>
                <span className="text-[13px] text-locked">da árvore</span>
              </div>
            </div>

            <div className="rounded-[14px] border border-borda bg-superficie p-4 flex flex-col justify-between">
              <span className="text-[12px] font-medium uppercase tracking-wider text-locked">Em Risco de Prazo</span>
              <div className="mt-2 flex items-baseline gap-2">
                <span className={`font-display text-3xl ${data.metrics.at_risk_count > 0 ? "text-orange" : "text-done"}`}>
                  {data.metrics.at_risk_count}
                </span>
                <span className="text-[13px] text-locked">urgentes / atrasados</span>
              </div>
            </div>

            <div className="rounded-[14px] border border-borda bg-superficie p-4 flex flex-col justify-between">
              <span className="text-[12px] font-medium uppercase tracking-wider text-locked">Etapas Puladas (Aviso)</span>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="font-display text-3xl text-ink">{data.metrics.total_skipped_steps}</span>
                <span className="text-[13px] text-locked">com justificativa</span>
              </div>
            </div>

            <div className="rounded-[14px] border border-borda bg-superficie p-4 flex flex-col justify-between col-span-2 lg:col-span-1">
              <span className="text-[12px] font-medium uppercase tracking-wider text-locked">Comentários Pendentes</span>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="font-display text-3xl text-ink">{data.metrics.total_unresolved_comments}</span>
                <span className="text-[13px] text-locked">sem resolução</span>
              </div>
            </div>
          </section>
        )}

        {/* Filter Toolbar */}
        <section aria-label="Filtros e ordenação" className="rounded-[14px] border border-borda bg-superficie p-4 flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3 flex-1 min-w-[280px]">
            <input
              type="text"
              placeholder="Buscar por estudante, projeto ou instituição…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-10 rounded-[8px] border border-borda bg-paper px-3 text-[14px] text-ink placeholder:text-locked focus:border-purple outline-none flex-1 min-w-[220px]"
            />

            <select
              value={riskFilter}
              onChange={(e) => setRiskFilter(e.target.value as typeof riskFilter)}
              className="h-10 rounded-[8px] border border-borda bg-paper px-3 text-[13px] text-ink focus:border-purple outline-none"
            >
              <option value="all">Todos os status</option>
              <option value="at_risk">Apenas em Risco / Atrasados</option>
              <option value="skipped">Com Etapas Puladas</option>
              <option value="comments">Com Comentários Pendentes</option>
            </select>

            <select
              value={workFilter}
              onChange={(e) => setWorkFilter(e.target.value)}
              className="h-10 rounded-[8px] border border-borda bg-paper px-3 text-[13px] text-ink focus:border-purple outline-none"
            >
              <option value="all">Todos os tipos de trabalho</option>
              <option value="tcc">TCC</option>
              <option value="pre_projeto_mestrado">Pré-projeto Mestrado</option>
              <option value="dissertacao">Dissertação</option>
              <option value="tese">Tese de Doutorado</option>
              <option value="artigo">Artigo Científico</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[13px] text-locked">Ordenar por:</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
              className="h-10 rounded-[8px] border border-borda bg-paper px-3 text-[13px] text-ink focus:border-purple outline-none"
            >
              <option value="deadline">Prazo mais urgente</option>
              <option value="progress_asc">Menor progresso primeiro</option>
              <option value="progress_desc">Maior progresso primeiro</option>
              <option value="name">Nome do estudante (A-Z)</option>
            </select>
          </div>
        </section>

        {/* Advisees List */}
        {loading ? (
          <div className="rounded-[16px] border border-borda bg-superficie p-12 text-center text-locked">
            Carregando painel de orientandos…
          </div>
        ) : filteredStudents.length === 0 ? (
          <div className="rounded-[16px] border border-borda bg-superficie p-12 text-center space-y-3">
            <h3 className="font-display text-xl text-ink">Nenhum orientando encontrado</h3>
            <p className="text-[14px] text-locked max-w-md mx-auto">
              Nenhum projeto corresponde aos filtros aplicados, ou você ainda não possui orientandos vinculados ao seu e-mail.
            </p>
            <Button type="button" variant="primary" onClick={() => setShowLinkModal(true)}>
              Vincular Orientando Agora
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center justify-between text-[13px] text-locked px-2">
              <span>Exibindo {filteredStudents.length} de {data?.students.length ?? 0} orientandos</span>
            </div>

            <div className="grid grid-cols-1 gap-4">
              {filteredStudents.map((s) => {
                const isOverdueOrCritical = s.schedule.risk_level === "overdue" || s.schedule.risk_level === "critical";

                return (
                  <article
                    key={s.project_id}
                    className="rounded-[16px] border border-borda bg-superficie p-6 hover:border-purple/40 transition space-y-4"
                  >
                    {/* Top Row: Student & Project details */}
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div className="flex items-start gap-3.5">
                        <div className="h-11 w-11 rounded-full bg-purple/10 border border-purple/20 flex items-center justify-center font-display text-base font-bold text-purple shrink-0">
                          {s.student.initials}
                        </div>
                        <div>
                          <div className="flex flex-wrap items-center gap-2 mb-1">
                            <h2 className="font-semibold text-lg text-ink">{s.student.name}</h2>
                            <span className="text-[13px] text-locked font-mono">({s.student.email})</span>
                            <span className="rounded-[6px] bg-skipped-bg px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider text-purple">
                              {WORK_LABELS[s.work] ?? s.work}
                            </span>
                            {s.institution && (
                              <span className="text-[12px] text-locked">· {s.institution}</span>
                            )}
                          </div>
                          <p className="text-[15px] font-medium text-ink/90">{s.title}</p>
                        </div>
                      </div>

                      <div className="flex flex-wrap items-center gap-2">
                        <RiskBadge level={s.schedule.risk_level} label={s.schedule.risk_label} />
                        {s.deadline && (
                          <span className="text-[13px] text-locked border border-borda rounded-[6px] px-2.5 py-0.5 bg-paper">
                            Prazo: {s.deadline.split("-").reverse().join("/")}
                            {s.schedule.days_until_deadline !== null && (
                              <span className="ml-1 font-semibold">
                                ({s.schedule.days_until_deadline > 0 ? `${s.schedule.days_until_deadline}d restantes` : `${Math.abs(s.schedule.days_until_deadline)}d atrasado`})
                              </span>
                            )}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Progress Bar & Stages */}
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between text-[13px]">
                        <span className="font-medium text-ink">
                          Progresso na Árvore: <strong className="text-purple">{s.progress.completion_rate}%</strong>
                        </span>
                        <span className="text-locked text-[12px]">
                          {s.progress.done_nodes} concluídas · {s.progress.skipped_count} puladas · {s.progress.available_nodes} disponíveis · {s.progress.total_nodes} total
                        </span>
                      </div>
                      <div className="h-2.5 w-full rounded-full bg-paper overflow-hidden flex border border-borda/40">
                        <div
                          className="bg-done transition-all duration-300"
                          style={{ width: `${(s.progress.done_nodes / s.progress.total_nodes) * 100}%` }}
                          title={`${s.progress.done_nodes} etapas concluídas`}
                        />
                        <div
                          className="bg-orange/80 transition-all duration-300"
                          style={{ width: `${(s.progress.skipped_count / s.progress.total_nodes) * 100}%` }}
                          title={`${s.progress.skipped_count} etapas puladas com aviso consciente`}
                        />
                        <div
                          className="bg-purple/40 transition-all duration-300"
                          style={{ width: `${(s.progress.available_nodes / s.progress.total_nodes) * 100}%` }}
                          title={`${s.progress.available_nodes} etapas disponíveis`}
                        />
                      </div>
                    </div>

                    {/* Transparency Box: Skipped steps alerts */}
                    {s.progress.skipped_steps.length > 0 && (
                      <div className="rounded-[10px] border border-orange/40 bg-orange/10 p-3.5 space-y-2 text-[13px]">
                        <div className="flex items-center gap-2 font-semibold text-ink">
                          <span className="text-orange font-bold">⚠</span>
                          <span>{s.progress.skipped_steps.length} etapa(s) pulada(s) com aviso consciente do estudante:</span>
                        </div>
                        <ul className="space-y-1.5 pl-5 list-disc text-locked">
                          {s.progress.skipped_steps.map((step) => (
                            <li key={step.node_key}>
                              <strong className="text-ink">{step.title}</strong>: <em>&ldquo;{step.reason}&rdquo;</em>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Schedule Warning if critical/overdue */}
                    {isOverdueOrCritical && s.schedule.alert && (
                      <div className="rounded-[10px] border border-brand-red/30 bg-brand-red/10 p-3 text-[13px] text-ink flex items-start gap-2">
                        <span className="text-brand-red font-bold">!</span>
                        <span>{s.schedule.alert}</span>
                      </div>
                    )}

                    {/* Governance & Integrity Indicators */}
                    <div className="flex flex-wrap items-center justify-between gap-4 pt-2 border-t border-borda text-[13px] text-locked">
                      <div className="flex flex-wrap items-center gap-4">
                        <span>Fontes: <strong className="text-ink">{s.governance.sources_count}</strong></span>
                        <span>Citações verificadas: <strong className="text-ink">{s.governance.verified_claims_count}</strong></span>
                        <span>
                          Prisma autoria:{" "}
                          {s.governance.direct_human_pct !== null && s.governance.direct_human_pct !== undefined ? (
                            <>
                              <strong className="text-ink">{s.governance.direct_human_pct}% humano</strong>
                              {s.governance.ai_assisted_pct != null && s.governance.ai_assisted_pct > 0 && ` / ${s.governance.ai_assisted_pct}% IA`}
                              {s.governance.pasted_pct != null && s.governance.pasted_pct > 0 && ` / ${s.governance.pasted_pct}% colado de fora`}
                            </>
                          ) : (
                            <strong className="text-brand-red font-medium">Indisponível</strong>
                          )}
                        </span>
                        {s.governance.unresolved_comments_count > 0 ? (
                          <span className="text-orange font-semibold">
                            💬 {s.governance.unresolved_comments_count} comentário(s) pendente(s)
                          </span>
                        ) : (
                          <span className="text-done font-medium">💬 Comentários em dia</span>
                        )}
                        {s.governance.banca_status === "indisponivel" ? (
                          <span className="border border-brand-red/30 bg-brand-red/10 text-brand-red rounded-[6px] px-2 py-0.5 text-[11px] font-semibold">
                            Banca: Indisponível
                          </span>
                        ) : s.governance.banca_verdict ? (
                          <span className="border border-purple/30 bg-purple/10 text-purple rounded-[6px] px-2 py-0.5 text-[11px] font-semibold">
                            Banca: {s.governance.banca_verdict} ({s.governance.banca_score}/10)
                          </span>
                        ) : null}
                      </div>

                      {/* Action Links */}
                      <div className="flex flex-wrap items-center gap-2">
                        <Link
                          href={`/projetos/${s.project_id}/arvore`}
                          className="inline-flex min-h-[34px] items-center rounded-[8px] border border-purple px-2.5 text-[13px] font-medium text-purple hover:bg-purple hover:text-paper transition"
                        >
                          Árvore
                        </Link>
                        <Link
                          href={`/projetos/${s.project_id}/editor`}
                          className="inline-flex min-h-[34px] items-center rounded-[8px] border border-borda px-2.5 text-[13px] font-medium text-locked hover:border-purple hover:text-purple transition"
                        >
                          Editor
                        </Link>
                        <Link
                          href={`/projetos/${s.project_id}/relatorio`}
                          className="inline-flex min-h-[34px] items-center rounded-[8px] border border-borda px-2.5 text-[13px] font-medium text-locked hover:border-purple hover:text-purple transition"
                        >
                          Relatório Formal
                        </Link>
                        <Link
                          href={`/projetos/${s.project_id}/defesa`}
                          className="inline-flex min-h-[34px] items-center rounded-[8px] border border-borda px-2.5 text-[13px] font-medium text-locked hover:border-purple hover:text-purple transition"
                        >
                          Banca
                        </Link>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          </div>
        )}
      </main>

      {/* Link advisee modal */}
      {showLinkModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-[16px] border border-borda bg-superficie p-6 space-y-4 shadow-xl">
            <div className="flex items-center justify-between">
              <h2 className="font-display text-xl text-ink">Vincular Novo Orientando</h2>
              <button
                type="button"
                onClick={() => setShowLinkModal(false)}
                className="text-locked hover:text-ink text-lg font-bold"
              >
                ✕
              </button>
            </div>
            <p className="text-[14px] text-locked">
              Cole o identificador (UUID) do projeto ou o link mágico fornecido pelo estudante para integrá-lo ao seu painel.
            </p>
            <form onSubmit={handleLinkAdvisee} className="space-y-4">
              <input
                type="text"
                placeholder="Ex: 550e8400-e29b-41d4-a716-446655440000 ou link"
                value={linkInput}
                onChange={(e) => setLinkInput(e.target.value)}
                required
                className="w-full h-11 rounded-[8px] border border-borda bg-paper px-3 text-[14px] text-ink focus:border-purple outline-none"
              />
              <div className="flex items-center justify-end gap-2">
                <Button type="button" variant="secondary" onClick={() => setShowLinkModal(false)}>
                  Cancelar
                </Button>
                <Button type="submit" variant="primary" disabled={linking}>
                  {linking ? "Vinculando…" : "Confirmar Vínculo"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
