"use client";

import { useRouter } from "next/navigation";
import React, { useEffect, useMemo, useState } from "react";
import {
  AdvisorReport,
  ApiError,
  api,
  GAP_STATUS_LABELS,
  Gap,
  getToken,
  MapData,
  MapNode,
  Project,
  WORK_LABELS,
} from "@/lib/api";
import { AppHeader } from "@/components/app-header";
import { AlertBanner, Button, StatusBadge } from "@/components/ui";

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
  const [mapNodes, setMapNodes] = useState<MapNode[]>([]);
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
      api<MapData>(`/projects/${id}/map`).catch(() => ({ nodes: [], edges: [] })),
    ])
      .then(([projData, reportsData, mapData]) => {
        if (cancelled) return;
        setProject(projData);
        setReports(reportsData);
        setMapNodes(mapData.nodes ?? []);
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

  const labelOf = useMemo(
    () => new Map(mapNodes.map((n) => [n.id, n.label])),
    [mapNodes]
  );

  async function handleGenerateReport() {
    setGenerating(true);
    setError(null);
    try {
      const created = await api<AdvisorReport>(`/projects/${id}/reports`, {
        method: "POST",
      });
      setReports((prev) => [created, ...prev]);
      setCurrentReport(created);
      setNotice("Relatório de progresso atualizado com sucesso.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao gerar relatório.");
    } finally {
      setGenerating(false);
    }
  }

  const payload = currentReport?.payload;

  return (
    <div className="min-h-screen flex flex-col bg-paper text-ink">
      <AppHeader projectId={id} />

      <main className="mx-auto w-full max-w-[1360px] flex-1 px-6 py-8 sm:px-10 space-y-6">
        {/* Cabeçalho do Relatório */}
        <header className="flex flex-wrap items-center justify-between gap-4 border-b border-borda pb-5 print:border-none">
          <div>
            <span className="text-[13px] font-bold uppercase tracking-wider text-locked">
              Governança & Supervisão Acadêmica
            </span>
            <h1 className="mt-1 font-display text-3xl sm:text-[36px] text-ink">
              Relatório de progresso para orientação
            </h1>
            <p className="mt-1 text-[15px] text-locked">
              {project?.title} · {project?.work ? WORK_LABELS[project.work] : "Projeto"}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3 print:hidden">
            <Button
              type="button"
              variant="secondary"
              disabled={generating}
              onClick={handleGenerateReport}
            >
              {generating ? "Atualizando…" : "Atualizar relatório"}
            </Button>

            {/* Único botão principal roxo da tela */}
            <Button
              type="button"
              variant="primary"
              onClick={() => window.print()}
            >
              Imprimir / Salvar PDF
            </Button>
          </div>
        </header>

        {/* Seletor de Histórico */}
        {reports.length > 1 && (
          <div className="flex flex-wrap items-center gap-3 text-[15px] print:hidden">
            <label htmlFor="report-snapshot-select" className="font-medium text-locked">
              Histórico de relatórios:
            </label>
            <select
              id="report-snapshot-select"
              value={currentReport?.id}
              onChange={(e) => {
                const selected = reports.find((r) => r.id === e.target.value);
                if (selected) setCurrentReport(selected);
              }}
              className="h-[44px] rounded-[10px] border border-borda bg-superficie px-3.5 text-[15px] text-ink"
            >
              {reports.map((r, i) => (
                <option key={r.id} value={r.id}>
                  Relatório #{reports.length - i} — {formatDate(r.created_at)}
                </option>
              ))}
            </select>
          </div>
        )}

        {error && <AlertBanner variant="error">{error}</AlertBanner>}
        {notice && <AlertBanner variant="notice">{notice}</AlertBanner>}

        {!payload ? (
          <div className="rounded-[16px] border border-borda bg-superficie p-8 text-[15px] text-locked space-y-4">
            <p>Nenhum relatório de progresso foi gerado para este projeto ainda.</p>
            <Button
              type="button"
              variant="secondary"
              disabled={generating}
              onClick={handleGenerateReport}
            >
              {generating ? "Gerando…" : "Atualizar relatório"}
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 items-start">
            {/* Coluna Principal (7 colunas): Identificação + Progresso na Árvore */}
            <div className="lg:col-span-7 space-y-6">
              {/* Seção 1: Identificação */}
              <section className="rounded-[16px] border border-borda bg-superficie p-6 space-y-4">
                <h2 className="font-display text-2xl text-ink border-b border-borda pb-3">
                  1. Identificação do projeto e metas
                </h2>
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 text-[15px]">
                  <div>
                    <span className="text-[13px] font-bold uppercase tracking-wider text-locked">
                      Instituição
                    </span>
                    <p className="mt-1 font-medium text-ink">
                      {(payload.project.institution as string) || "Não informada"}
                    </p>
                  </div>
                  <div>
                    <span className="text-[13px] font-bold uppercase tracking-wider text-locked">
                      Formato
                    </span>
                    <p className="mt-1 font-medium text-ink">
                      {WORK_LABELS[(payload.project.work as string) || "tcc"]}
                    </p>
                  </div>
                  <div>
                    <span className="text-[13px] font-bold uppercase tracking-wider text-locked">
                      Prazo final
                    </span>
                    <p className="mt-1 font-medium text-ink">
                      {formatDate(payload.project.deadline as string)}
                    </p>
                  </div>
                  <div>
                    <span className="text-[13px] font-bold uppercase tracking-wider text-locked">
                      Dedicação semanal
                    </span>
                    <p className="mt-1 font-medium text-ink">
                      {(payload.project.weekly_hours as number) || 10} horas/semana
                    </p>
                  </div>
                </div>

                {Boolean(payload.project.research_problem) && (
                  <div className="rounded-[12px] border border-borda bg-paper p-4">
                    <span className="text-[13px] font-bold uppercase tracking-wider text-purple">
                      Problema de pesquisa central:
                    </span>
                    <p className="mt-1 font-serif-academic text-[17px] italic text-ink">
                      {payload.project.research_problem as string}
                    </p>
                  </div>
                )}
              </section>

              {/* Seção 2: Progresso na Árvore Metodológica */}
              <section className="rounded-[16px] border border-borda bg-superficie p-6 space-y-5">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-borda pb-3">
                  <h2 className="font-display text-2xl text-ink">
                    2. Progresso na árvore metodológica
                  </h2>
                  <div className="flex flex-wrap gap-2">
                    <StatusBadge
                      status="done"
                      label={`${payload.progress_tree.completed_count} concluída(s)`}
                    />
                    {payload.progress_tree.skipped_count > 0 && (
                      <StatusBadge
                        status="skipped"
                        label={`${payload.progress_tree.skipped_count} pulada(s)`}
                      />
                    )}
                    <StatusBadge
                      status="available"
                      label={`${payload.progress_tree.pending_count} pendente(s)`}
                    />
                  </div>
                </div>

                {/* Etapas Concluídas */}
                <div>
                  <h3 className="text-[13px] font-bold uppercase tracking-wider text-locked mb-3">
                    Etapas concluídas ({payload.progress_tree.completed.length})
                  </h3>
                  {payload.progress_tree.completed.length === 0 ? (
                    <p className="text-[15px] text-locked italic">
                      Nenhuma etapa concluída até o momento.
                    </p>
                  ) : (
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                      {payload.progress_tree.completed.map((node) => (
                        <div
                          key={node.key}
                          className="rounded-[12px] border-2 border-done bg-paper/40 p-3.5"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <span className="text-[15px] font-bold text-ink">{node.title}</span>
                            <StatusBadge status="done" />
                          </div>
                          <span className="mt-1 block text-[13px] text-locked capitalize">
                            Fase: {node.phase}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Etapas Puladas com Registro de Aviso Consciente */}
                {payload.progress_tree.skipped_with_warning.length > 0 && (
                  <div className="border-t border-borda pt-4">
                    <h3 className="text-[13px] font-bold uppercase tracking-wider text-purple mb-3">
                      Etapas puladas com registro de aviso consciente (
                      {payload.progress_tree.skipped_with_warning.length})
                    </h3>
                    <div className="space-y-3">
                      {payload.progress_tree.skipped_with_warning.map((node) => (
                        <div
                          key={node.key}
                          className="rounded-[12px] border border-purple/40 bg-skipped-bg p-4"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-[15px] font-bold text-ink">{node.title}</span>
                            <StatusBadge status="skipped" label="Pulada" />
                          </div>
                          <p className="mt-2 text-[15px] text-ink">
                            <strong>Motivo registrado pelo aluno: </strong>
                            {node.skipped_reason}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </section>
            </div>

            {/* Coluna Direita (5 colunas): Mapa de Conhecimento + Auditoria de IA */}
            <div className="lg:col-span-5 space-y-6">
              {/* Seção 3: Mapa de Conhecimento, Evidências e Lacunas */}
              <section className="rounded-[16px] border border-borda bg-superficie p-6 space-y-5">
                <h2 className="font-display text-2xl text-ink border-b border-borda pb-3">
                  3. Mapa, evidências e lacunas
                </h2>

                <div className="grid grid-cols-3 gap-3 text-center">
                  <div className="rounded-[12px] border border-borda p-3.5 bg-paper">
                    <div className="font-display text-2xl text-ink">
                      {payload.knowledge_map.documents_count}
                    </div>
                    <div className="mt-1 text-[13px] font-bold uppercase text-locked">
                      Artigos
                    </div>
                  </div>
                  <div className="rounded-[12px] border border-borda p-3.5 bg-paper">
                    <div className="font-display text-2xl text-ink">
                      {payload.knowledge_map.verified_claims_count}
                    </div>
                    <div className="mt-1 text-[13px] font-bold uppercase text-locked">
                      Citações
                    </div>
                  </div>
                  <div className="rounded-[12px] border border-borda p-3.5 bg-paper">
                    <div className="font-display text-2xl text-ink">
                      {payload.knowledge_map.confirmed_relations_count}
                    </div>
                    <div className="mt-1 text-[13px] font-bold uppercase text-locked">
                      Relações
                    </div>
                  </div>
                </div>

                {/* Relações Rejeitadas */}
                {payload.knowledge_map.rejected_relations.length > 0 && (
                  <div className="border-t border-borda pt-4">
                    <h3 className="text-[13px] font-bold uppercase tracking-wider text-locked mb-2.5">
                      Relações rejeitadas pelo aluno (memória de decisões)
                    </h3>
                    <ul className="space-y-2 text-[15px]">
                      {payload.knowledge_map.rejected_relations.map((rel, i) => (
                        <li
                          key={i}
                          className="rounded-[10px] border border-borda bg-paper/40 p-3"
                        >
                          <span className="font-medium text-ink">
                            {labelOf.get(rel.source) ?? rel.source} ↮{" "}
                            {labelOf.get(rel.target) ?? rel.target} ({rel.relation})
                          </span>
                          {rel.user_note && (
                            <p className="mt-1 text-[14px] text-locked italic">
                              Nota: &quot;{rel.user_note}&quot;
                            </p>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Lacunas Investigadas (Nomes dos Conceitos em vez de UUIDs) */}
                {payload.knowledge_map.gaps.length > 0 && (
                  <div className="border-t border-borda pt-4">
                    <h3 className="text-[13px] font-bold uppercase tracking-wider text-purple mb-2.5">
                      Lacunas de pesquisa investigadas ({payload.knowledge_map.gaps.length})
                    </h3>
                    <ul className="space-y-2.5 text-[15px]">
                      {payload.knowledge_map.gaps.map((gap, i) => {
                        const nameA = labelOf.get(gap.concept_a) ?? gap.concept_a;
                        const nameB = labelOf.get(gap.concept_b) ?? gap.concept_b;
                        const statusLabel =
                          GAP_STATUS_LABELS[gap.status as Gap["status"]] ?? gap.status;
                        return (
                          <li
                            key={i}
                            className="rounded-[12px] border-2 border-dotted border-purple bg-paper/50 p-3.5 space-y-1.5"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <span className="font-bold text-ink">
                                {nameA} <span className="text-purple">↔</span> {nameB}
                              </span>
                              <StatusBadge status="gap" label={statusLabel} />
                            </div>
                            {gap.note && (
                              <p className="text-[14px] text-ink italic">
                                &quot;{gap.note}&quot;
                              </p>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                )}
              </section>

              {/* Seção 4: Auditoria de Governança e Uso de IA */}
              <section className="rounded-[16px] border border-borda bg-superficie p-6 space-y-4">
                <h2 className="font-display text-2xl text-ink border-b border-borda pb-3">
                  4. Auditoria de uso de IA
                </h2>
                <p className="text-[15px] text-ink leading-relaxed">
                  Nenhuma afirmação entra sem citação literal verificada por código contra o PDF original, e nenhum capítulo completo é redigido pela IA.
                </p>

                <div className="rounded-[12px] border border-borda overflow-x-auto">
                  <table className="w-full text-left text-[14px]">
                    <thead className="bg-paper border-b border-borda text-[13px] font-bold uppercase tracking-wider text-locked">
                      <tr>
                        <th className="p-3">Ação</th>
                        <th className="p-3">Modelo</th>
                        <th className="p-3">Prompt</th>
                        <th className="p-3">Data</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-borda">
                      {payload.ai_usage_audit.logs.map((log, i) => (
                        <tr key={i} className="hover:bg-paper/40">
                          <td className="p-3 font-mono text-ink">{log.action}</td>
                          <td className="p-3 text-locked">{log.model || "sistema"}</td>
                          <td className="p-3 text-locked">{log.prompt_version || "-"}</td>
                          <td className="p-3 text-locked">{formatDate(log.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
