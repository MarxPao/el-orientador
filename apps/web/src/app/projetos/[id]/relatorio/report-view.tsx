"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  ApiError,
  api,
  AdvisorReport,
  getToken,
  Project,
  WORK_LABELS,
} from "@/lib/api";

function formatDate(isoStr: string | null | undefined): string {
  if (!isoStr) return "-";
  const [datePart] = isoStr.split("T");
  const [year, month, day] = datePart.split("-");
  return `${day}/${month}/${year}`;
}

export default function ReportView({ id }: { id: string }) {
  const router = useRouter();
  const [project, setProject] = useState<Project | null>(null);
  const [reports, setReports] = useState<AdvisorReport[]>([]);
  const [currentReport, setCurrentReport] = useState<AdvisorReport | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/entrar");
      return;
    }
    let cancelled = false;

    Promise.all([
      api<Project>(`/projects/${id}`),
      api<AdvisorReport[]>(`/projects/${id}/reports`),
    ])
      .then(([projData, reportsData]) => {
        if (cancelled) return;
        setProject(projData);
        setReports(reportsData);
        if (reportsData.length > 0) {
          setCurrentReport(reportsData[0]);
        }
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) return router.replace("/entrar");
        setError(err instanceof Error ? err.message : "Erro ao carregar relatório.");
      });

    return () => {
      cancelled = true;
    };
  }, [id, router]);

  async function handleGenerateReport() {
    setGenerating(true);
    setError(null);
    try {
      const created = await api<AdvisorReport>(`/projects/${id}/reports`, {
        method: "POST",
      });
      setReports((prev) => [created, ...prev]);
      setCurrentReport(created);
      setNotice("Novo instantâneo de progresso gerado com sucesso.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao gerar relatório.");
    } finally {
      setGenerating(false);
    }
  }

  const payload = currentReport?.payload;

  return (
    <main className="mx-auto w-full max-w-5xl px-6 py-8">
      {/* Header (No print for nav buttons) */}
      <header className="flex flex-wrap items-baseline justify-between gap-4 border-b border-ink/10 pb-4 print:border-none">
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-ink/60">
            Governança & Supervisão Acadêmica
          </span>
          <h1 className="font-serif-academic text-3xl font-bold text-ink">
            Relatório de Progresso para Orientação
          </h1>
          <p className="mt-1 text-xs text-ink/70">
            {project?.title} · {project?.work ? WORK_LABELS[project.work] : "Projeto"}
          </p>
        </div>

        <div className="flex items-center gap-3 text-xs print:hidden">
          <Link href={`/projetos/${id}/editor`} className="text-ink/70 hover:text-ink underline">
            Editor
          </Link>
          <Link href={`/projetos/${id}/arvore`} className="text-ink/70 hover:text-ink underline">
            Árvore
          </Link>
          <Link href={`/projetos/${id}/mapa`} className="text-ink/70 hover:text-ink underline">
            Mapa
          </Link>
          <button
            type="button"
            onClick={() => window.print()}
            className="rounded border border-ink/30 px-3 py-1.5 font-medium text-ink hover:bg-paper"
          >
            Imprimir / Salvar PDF
          </button>
          <button
            type="button"
            disabled={generating}
            onClick={handleGenerateReport}
            className="rounded bg-ink px-3 py-1.5 font-medium text-white hover:bg-ink/90 disabled:opacity-50"
          >
            {generating ? "Gerando…" : "Atualizar Instantâneo"}
          </button>
        </div>
      </header>

      {/* Snapshot selector */}
      {reports.length > 1 && (
        <div className="mt-4 flex items-center gap-2 text-xs print:hidden">
          <span className="text-ink/60">Histórico de instantâneos:</span>
          <select
            value={currentReport?.id}
            onChange={(e) => {
              const selected = reports.find((r) => r.id === e.target.value);
              if (selected) setCurrentReport(selected);
            }}
            className="rounded border border-ink/20 bg-white px-2.5 py-1 text-xs"
          >
            {reports.map((r, i) => (
              <option key={r.id} value={r.id}>
                Instantâneo #{reports.length - i} — {formatDate(r.created_at)}
              </option>
            ))}
          </select>
        </div>
      )}

      {error && (
        <p role="alert" className="mt-4 text-xs text-danger">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="mt-4 text-xs font-medium text-done">
          {notice}
        </p>
      )}

      {!payload ? (
        <div className="mt-8 rounded-lg border border-ink/15 bg-paper/40 p-8 text-center text-xs text-ink/60">
          <p>Nenhum instantâneo de progresso gerado ainda.</p>
          <button
            type="button"
            disabled={generating}
            onClick={handleGenerateReport}
            className="mt-3 rounded bg-ink px-4 py-2 font-medium text-white"
          >
            {generating ? "Gerando…" : "Gerar Primeiro Relatório"}
          </button>
        </div>
      ) : (
        <div className="mt-6 space-y-8 text-xs leading-relaxed text-ink">
          {/* Section 1: Identification */}
          <section className="rounded-lg border border-ink/15 bg-white p-5 space-y-3">
            <h2 className="font-serif-academic text-base font-bold text-ink border-b border-ink/10 pb-2">
              1. Identificação do Projeto & Metas
            </h2>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <div>
                <span className="text-[10px] uppercase text-ink/50 font-medium">Instituição</span>
                <p className="font-medium text-ink">{(payload.project.institution as string) || "Não informada"}</p>
              </div>
              <div>
                <span className="text-[10px] uppercase text-ink/50 font-medium">Formato</span>
                <p className="font-medium text-ink">
                  {WORK_LABELS[(payload.project.work as string) || "tcc"]}
                </p>
              </div>
              <div>
                <span className="text-[10px] uppercase text-ink/50 font-medium">Prazo Final</span>
                <p className="font-medium text-ink">
                  {formatDate(payload.project.deadline as string)}
                </p>
              </div>
              <div>
                <span className="text-[10px] uppercase text-ink/50 font-medium">Dedicação Semanal</span>
                <p className="font-medium text-ink">
                  {(payload.project.weekly_hours as number) || 10} horas/semana
                </p>
              </div>
            </div>

            {Boolean(payload.project.research_problem) && (
              <div className="rounded border border-ink/10 bg-paper/40 p-3 mt-2">
                <span className="font-semibold text-ink/70">Problema de Pesquisa Central:</span>
                <p className="mt-1 italic">{payload.project.research_problem as string}</p>
              </div>
            )}
          </section>

          {/* Section 2: Progress Tree Breakdown */}
          <section className="rounded-lg border border-ink/15 bg-white p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-ink/10 pb-2">
              <h2 className="font-serif-academic text-base font-bold text-ink">
                2. Progresso na Árvore Metodológica
              </h2>
              <div className="flex gap-3 text-[11px]">
                <span className="text-done font-medium">
                  {payload.progress_tree.completed_count} concluída(s)
                </span>
                <span className="text-ink/60 font-medium">
                  {payload.progress_tree.skipped_count} pulada(s) com aviso
                </span>
                <span className="text-available font-medium">
                  {payload.progress_tree.pending_count} pendente(s)
                </span>
              </div>
            </div>

            {/* Completed */}
            <div>
              <h3 className="font-semibold text-ink/80 text-[11px] uppercase tracking-wider mb-2">
                Etapas Concluídas ({payload.progress_tree.completed.length})
              </h3>
              {payload.progress_tree.completed.length === 0 ? (
                <p className="text-ink/50 italic">Nenhuma etapa concluída até o momento.</p>
              ) : (
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {payload.progress_tree.completed.map((node) => (
                    <div key={node.key} className="rounded border border-done/30 bg-done/5 p-2.5">
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-ink">{node.title}</span>
                        <span className="text-[10px] text-done font-semibold">Concluído</span>
                      </div>
                      <span className="text-[10px] text-ink/50 capitalize">Fase: {node.phase}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Skipped with Conscious Warning (Crucial for advisor transparency!) */}
            {payload.progress_tree.skipped_with_warning.length > 0 && (
              <div className="border-t border-ink/10 pt-3">
                <h3 className="font-semibold text-gap text-[11px] uppercase tracking-wider mb-2">
                  Etapas Puladas com Registro de Aviso Consciente ({payload.progress_tree.skipped_with_warning.length})
                </h3>
                <div className="space-y-2">
                  {payload.progress_tree.skipped_with_warning.map((node) => (
                    <div key={node.key} className="rounded border border-gap/30 bg-gap/5 p-3">
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-ink">{node.title}</span>
                        <span className="rounded bg-gap/10 px-2 py-0.5 text-[10px] font-semibold text-gap">
                          Pulada
                        </span>
                      </div>
                      <p className="mt-1 text-[11px] text-ink/80">
                        <strong>Motivo registrado pelo aluno: </strong>
                        {node.skipped_reason}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </section>

          {/* Section 3: Knowledge Map Summary */}
          <section className="rounded-lg border border-ink/15 bg-white p-5 space-y-4">
            <h2 className="font-serif-academic text-base font-bold text-ink border-b border-ink/10 pb-2">
              3. Mapa de Conhecimento, Evidências e Lacunas
            </h2>

            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="rounded border border-ink/10 p-3 bg-paper/40">
                <div className="text-xl font-bold text-ink">{payload.knowledge_map.documents_count}</div>
                <div className="text-[10px] text-ink/60 uppercase">Artigos Analisados</div>
              </div>
              <div className="rounded border border-ink/10 p-3 bg-paper/40">
                <div className="text-xl font-bold text-ink">{payload.knowledge_map.verified_claims_count}</div>
                <div className="text-[10px] text-ink/60 uppercase">Citações Verificadas</div>
              </div>
              <div className="rounded border border-ink/10 p-3 bg-paper/40">
                <div className="text-xl font-bold text-ink">{payload.knowledge_map.confirmed_relations_count}</div>
                <div className="text-[10px] text-ink/60 uppercase">Relações Confirmadas</div>
              </div>
            </div>

            {/* Rejected Relations */}
            {payload.knowledge_map.rejected_relations.length > 0 && (
              <div className="border-t border-ink/10 pt-3">
                <h3 className="font-semibold text-ink/70 text-[11px] uppercase tracking-wider mb-2">
                  Relações Rejeitadas pelo Aluno (Memória Permanente de Decisões)
                </h3>
                <ul className="space-y-1.5">
                  {payload.knowledge_map.rejected_relations.map((rel, i) => (
                    <li key={i} className="rounded border border-ink/10 p-2 text-[11px]">
                      <span>{rel.source} ↮ {rel.target} ({rel.relation})</span>
                      {rel.user_note && (
                        <p className="mt-0.5 text-ink/60 italic">Nota: &quot;{rel.user_note}&quot;</p>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Gaps Found */}
            {payload.knowledge_map.gaps.length > 0 && (
              <div className="border-t border-ink/10 pt-3">
                <h3 className="font-semibold text-available text-[11px] uppercase tracking-wider mb-2">
                  Lacunas de Pesquisa Investigadas em Bases Externas ({payload.knowledge_map.gaps.length})
                </h3>
                <ul className="space-y-1.5">
                  {payload.knowledge_map.gaps.map((gap, i) => (
                    <li key={i} className="rounded border border-available/30 bg-available/5 p-2 text-[11px]">
                      <span className="font-medium text-ink">{gap.concept_a} ↔ {gap.concept_b}</span>
                      <span className="ml-2 text-ink/60">({gap.status})</span>
                      {gap.note && <p className="mt-0.5 text-ink/70 italic">&quot;{gap.note}&quot;</p>}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>

          {/* Section 4: AI Governance & Audit Log */}
          <section className="rounded-lg border border-ink/15 bg-white p-5 space-y-3">
            <h2 className="font-serif-academic text-base font-bold text-ink border-b border-ink/10 pb-2">
              4. Auditoria de Governança e Uso de IA
            </h2>
            <p className="text-[11px] text-ink/80 leading-relaxed">
              O sistema adere às regras éticas da orientação acadêmica: nenhuma afirmação entra sem citação literal
              verificada deterministicamente contra o PDF original, e nenhum capítulo completo é redigido pela IA.
            </p>

            <div className="rounded border border-ink/10 overflow-hidden">
              <table className="w-full text-left text-[11px]">
                <thead className="bg-paper border-b border-ink/10 font-semibold text-ink/70">
                  <tr>
                    <th className="p-2">Ação</th>
                    <th className="p-2">Modelo</th>
                    <th className="p-2">Versão Prompt</th>
                    <th className="p-2">Data/Hora</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink/10">
                  {payload.ai_usage_audit.logs.map((log, i) => (
                    <tr key={i} className="hover:bg-paper/50">
                      <td className="p-2 font-mono">{log.action}</td>
                      <td className="p-2 text-ink/70">{log.model || "system"}</td>
                      <td className="p-2 text-ink/60">{log.prompt_version || "-"}</td>
                      <td className="p-2 text-ink/50">{formatDate(log.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}
