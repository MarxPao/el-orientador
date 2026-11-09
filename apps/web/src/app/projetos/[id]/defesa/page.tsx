"use client";

import { useParams, useRouter } from "next/navigation";
import React, { Suspense, useCallback, useEffect, useState } from "react";
import {
  ApiError,
  BancaContextSummary,
  BancaSession,
  BancaTurn,
  Project,
  api,
  concludeBancaSession,
  createBancaSession,
  getBancaSession,
  getToken,
  listBancaSessions,
  submitBancaTurn,
} from "@/lib/api";
import { AppHeader } from "@/components/app-header";
import { AlertBanner, Button } from "@/components/ui";

function Spinner({ size = 16 }: { size?: number }) {
  return (
    <svg
      className="animate-spin text-purple"
      style={{ width: size, height: size }}
      viewBox="0 0 24 24"
      fill="none"
    >
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="40 60" strokeLinecap="round" />
    </svg>
  );
}

function RubricBadge({ label, score }: { label: string; score: number }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-[8px] border border-borda bg-superficie px-3 py-2 text-center">
      <span className="text-[11px] font-medium text-locked uppercase tracking-wider">{label}</span>
      <span className="mt-0.5 font-display text-[16px] text-purple font-semibold">{score} / 3</span>
    </div>
  );
}

function DefesaInner() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [project, setProject] = useState<Project | null>(null);
  const [sessions, setSessions] = useState<BancaSession[]>([]);
  const [activeSession, setActiveSession] = useState<BancaSession | null>(null);
  const [contextSummary, setContextSummary] = useState<BancaContextSummary | null>(null);

  const [selectedProfile, setSelectedProfile] = useState<"estrito" | "construtivo">("estrito");
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [concluding, setConcluding] = useState(false);
  const [answerInput, setAnswerInput] = useState("");
  const [error, setError] = useState<string | null>(null);

  const leave = useCallback(() => {
    router.replace("/entrar");
  }, [router]);

  // Load project & sessions on mount
  useEffect(() => {
    if (!getToken()) { leave(); return; }

    api<Project>(`/projects/${id}`)
      .then(setProject)
      .catch(() => {});

    listBancaSessions(id)
      .then((res) => {
        setSessions(res.sessions);
        setLoading(false);
      })
      .catch((e) => {
        if (e instanceof ApiError && e.status === 401) return leave();
        setError(e instanceof Error ? e.message : "Erro ao carregar sessões de banca.");
        setLoading(false);
      });
  }, [id, leave]);

  async function handleStartSession() {
    setStarting(true);
    setError(null);
    try {
      const res = await createBancaSession(id, selectedProfile);
      setActiveSession(res.session);
      setContextSummary(res.context_summary);
      setSessions((prev) => [res.session, ...prev.filter((s) => s.id !== res.session.id)]);
      setAnswerInput("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao iniciar simulação de banca.");
    } finally {
      setStarting(false);
    }
  }

  async function handleOpenSession(sessionId: string) {
    setLoading(true);
    setError(null);
    try {
      const res = await getBancaSession(id, sessionId);
      setActiveSession(res.session);
      setContextSummary(res.context_summary);
      setAnswerInput("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao abrir sessão.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmitTurn(e?: React.FormEvent) {
    e?.preventDefault();
    if (!activeSession || !answerInput.trim() || submitting) return;

    setSubmitting(true);
    setError(null);
    try {
      const res = await submitBancaTurn(id, activeSession.id, answerInput.trim());
      setActiveSession(res.session);
      setAnswerInput("");
      setSessions((prev) => prev.map((s) => (s.id === res.session.id ? res.session : s)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao submeter resposta.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleConcludeSession() {
    if (!activeSession || concluding) return;
    if (!confirm("Deseja encerrar a arguição e emitir o Parecer Final (Ata de Defesa)?")) return;

    setConcluding(true);
    setError(null);
    try {
      const res = await concludeBancaSession(id, activeSession.id);
      setActiveSession(res.session);
      setSessions((prev) => prev.map((s) => (s.id === res.session.id ? res.session : s)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao concluir sessão de defesa.");
    } finally {
      setConcluding(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-paper text-ink">
      <AppHeader onLeave={leave} />

      <main className="mx-auto w-full max-w-[880px] flex-1 px-6 py-10 sm:px-8">
        {/* Breadcrumb */}
        <nav className="mb-6 flex items-center gap-2 text-[13px] text-locked">
          <button onClick={() => router.push("/projetos")} className="min-h-[44px] px-1 hover:text-purple transition">
            Projetos
          </button>
          <span>›</span>
          {project && (
            <button
              onClick={() => router.push(`/projetos/${id}/arvore`)}
              className="min-h-[44px] px-1 hover:text-purple transition truncate max-w-[200px]"
            >
              {project.title}
            </button>
          )}
          {project && <span>›</span>}
          <span className="text-ink font-medium">Simulador de Banca</span>
        </nav>

        {error && (
          <AlertBanner variant="error" className="mb-6">
            {error}
            <button onClick={() => setError(null)} className="ml-3 underline font-medium">
              Fechar
            </button>
          </AlertBanner>
        )}

        {/* ── TELA 1: Lobby de Configuração / Histórico ── */}
        {!activeSession && !loading && (
          <div className="space-y-8">
            <div>
              <h1 className="font-display text-[28px] text-ink leading-tight">Simulador de Defesa de Banca Acadêmica</h1>
              <p className="mt-2 text-[15px] text-locked leading-relaxed">
                Treine sua sustentação oral diante de um examinador acadêmico. A banca formula perguntas afiadas baseadas
                diretamente no texto que você escreveu no manuscrito e nas evidências verificadas na literatura.
              </p>
              {contextSummary && (
                <div className="mt-3 inline-flex items-center gap-2 rounded-[8px] bg-purple/10 px-3 py-1 text-[12px] font-medium text-purple">
                  <span>Base compilada: {contextSummary.sections_count} seções do manuscrito e {contextSummary.claims_count} alegações verificadas</span>
                </div>
              )}
            </div>

            {/* Painel de seleção de examinador */}
            <div className="rounded-[14px] border border-borda bg-superficie p-6 shadow-sm">
              <h2 className="text-[16px] font-semibold text-ink mb-1">Escolha o Perfil do Membro da Banca</h2>
              <p className="text-[13px] text-locked mb-5">
                Selecione a postura avaliativa que deseja enfrentar para calibrar sua preparação:
              </p>

              <div className="grid gap-4 sm:grid-cols-2">
                {/* Perfil Estrito */}
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => setSelectedProfile("estrito")}
                  onKeyDown={(e) => e.key === "Enter" && setSelectedProfile("estrito")}
                  className={[
                    "rounded-[12px] border p-4 cursor-pointer transition select-none text-left flex flex-col justify-between",
                    selectedProfile === "estrito"
                      ? "border-purple bg-purple/5 ring-1 ring-purple"
                      : "border-borda hover:border-purple/40 bg-paper/40",
                  ].join(" ")}
                >
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-semibold text-[15px] text-ink">Examinador Metodológico</span>
                      <span className="text-[11px] font-bold uppercase tracking-wider rounded px-2 py-0.5 bg-orange/15 text-orange">
                        Estrito
                      </span>
                    </div>
                    <p className="text-[13px] text-locked leading-relaxed">
                      Foco incisivo em validade metodológica, tamanho e representatividade da amostra, inferência causal,
                      risco de viés e contraexemplos não respondidos.
                    </p>
                  </div>
                  <div className="mt-4 pt-3 border-t border-borda/60 text-[12px] text-locked italic">
                    Ideal para testar a solidez dos seus dados e métodos.
                  </div>
                </div>

                {/* Perfil Construtivo */}
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => setSelectedProfile("construtivo")}
                  onKeyDown={(e) => e.key === "Enter" && setSelectedProfile("construtivo")}
                  className={[
                    "rounded-[12px] border p-4 cursor-pointer transition select-none text-left flex flex-col justify-between",
                    selectedProfile === "construtivo"
                      ? "border-purple bg-purple/5 ring-1 ring-purple"
                      : "border-borda hover:border-purple/40 bg-paper/40",
                  ].join(" ")}
                >
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-semibold text-[15px] text-ink">Examinador Temático</span>
                      <span className="text-[11px] font-bold uppercase tracking-wider rounded px-2 py-0.5 bg-purple/15 text-purple">
                        Construtivo
                      </span>
                    </div>
                    <p className="text-[13px] text-locked leading-relaxed">
                      Foco no diálogo teórico entre autores, relevância social e formativa do problema, originalidade da
                      contribuição e perspectivas futuras.
                    </p>
                  </div>
                  <div className="mt-4 pt-3 border-t border-borda/60 text-[12px] text-locked italic">
                    Ideal para testar o domínio teórico e o impacto prático.
                  </div>
                </div>
              </div>

              <div className="mt-6 flex flex-wrap items-center justify-between gap-4 pt-4 border-t border-borda">
                <p className="text-[12px] text-locked">
                  A arguição avalia clareza, fundamentação em citações, rigor e postura argumentativa.
                </p>
                <Button type="button" variant="primary" onClick={handleStartSession} disabled={starting}>
                  {starting ? (
                    <>
                      <Spinner size={15} /> Preparando banca…
                    </>
                  ) : (
                    "Iniciar Sessão de Arguição →"
                  )}
                </Button>
              </div>
            </div>

            {/* Histórico de Simulações */}
            {sessions.length > 0 && (
              <section className="space-y-4">
                <h2 className="text-[16px] font-semibold text-ink">Simulações Anteriores ({sessions.length})</h2>
                <div className="space-y-3">
                  {sessions.map((s) => {
                    const studentTurns = s.turns.filter((t) => t.speaker === "student").length;
                    return (
                      <div
                        key={s.id}
                        className="flex flex-wrap items-center justify-between gap-3 rounded-[12px] border border-borda bg-superficie px-5 py-4 transition hover:border-purple/30"
                      >
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-[12px] font-bold uppercase tracking-wider rounded px-2 py-0.5 bg-purple/10 text-purple">
                              {s.examiner_profile === "estrito" ? "Perfil Estrito" : "Perfil Construtivo"}
                            </span>
                            <span className="text-[12px] text-locked font-mono">
                              {new Date(s.created_at).toLocaleDateString("pt-BR")} às{" "}
                              {new Date(s.created_at).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
                            </span>
                          </div>
                          <p className="text-[14px] text-ink truncate">
                            {s.final_report ? (
                              <span className="font-medium text-done">
                                Parecer: {s.final_report.verdict_title} ({s.final_report.overall_score}/10.0)
                              </span>
                            ) : (
                              <span className="text-locked">
                                Em andamento · {studentTurns} resposta{studentTurns === 1 ? "" : "s"} fornecida{studentTurns === 1 ? "" : "s"}
                              </span>
                            )}
                          </p>
                        </div>
                        <Button
                          type="button"
                          variant="secondary"
                          onClick={() => handleOpenSession(s.id)}
                          className="shrink-0"
                        >
                          {s.status === "completed" ? "Ver Ata de Defesa" : "Continuar Arguição →"}
                        </Button>
                      </div>
                    );
                  })}
                </div>
              </section>
            )}
          </div>
        )}

        {/* ── TELA 2: Arguição em Andamento ── */}
        {activeSession && activeSession.status !== "completed" && (
          <div className="space-y-6">
            {/* Header da Sessão */}
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-[12px] border border-borda bg-superficie px-5 py-3">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-done animate-pulse" />
                <span className="text-[13px] font-semibold text-ink">
                  {activeSession.examiner_profile === "estrito"
                    ? "Examinador Metodológico (Perfil Estrito)"
                    : "Examinador Temático (Perfil Construtivo)"}
                </span>
                <span className="text-[12px] text-locked">
                  · {activeSession.turns.filter((t) => t.speaker === "examiner").length}ª pergunta
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setActiveSession(null)}
                  className="text-[12px]"
                >
                  Pausar
                </Button>
                <Button
                  type="button"
                  variant="primary"
                  onClick={handleConcludeSession}
                  disabled={concluding}
                  className="text-[12px]"
                >
                  {concluding ? <Spinner size={13} /> : "Encerrar & Emitir Ata"}
                </Button>
              </div>
            </div>

            {/* Timeline da Arguição */}
            <div className="space-y-4">
              {activeSession.turns.map((turn: BancaTurn, idx: number) => {
                const isExaminer = turn.speaker === "examiner";
                return (
                  <div
                    key={idx}
                    className={[
                      "rounded-[14px] border p-5 transition leading-relaxed",
                      isExaminer
                        ? "border-purple/30 bg-purple/5 text-ink ml-0 mr-8"
                        : "border-borda bg-superficie text-ink ml-8 mr-0",
                    ].join(" ")}
                  >
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <span className="text-[12px] font-semibold uppercase tracking-wider text-purple">
                        {isExaminer ? "Banca Examinadora" : "Sua Resposta"}
                      </span>
                      {turn.focus_area && (
                        <span className="text-[11px] font-mono text-locked bg-borda/40 px-2 py-0.5 rounded">
                          Foco: {turn.focus_area}
                        </span>
                      )}
                    </div>

                    <p className="text-[15px] leading-relaxed whitespace-pre-wrap">{turn.content}</p>

                    {/* Rubricas do turno do aluno */}
                    {!isExaminer && turn.rubric_scores && (
                      <div className="mt-4 pt-4 border-t border-borda/60 space-y-3">
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                          <RubricBadge label="Domínio" score={turn.rubric_scores.dominio_conteudo} />
                          <RubricBadge label="Evidências" score={turn.rubric_scores.fundamentacao_evidencias} />
                          <RubricBadge label="Método" score={turn.rubric_scores.coerencia_metodologica} />
                          <RubricBadge label="Postura" score={turn.rubric_scores.postura_argumentativa} />
                        </div>
                        {turn.feedback && (
                          <p className="text-[12px] text-locked bg-paper/60 p-2.5 rounded-[8px] border border-borda/50 italic">
                            Feedback da banca: &quot;{turn.feedback}&quot;
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Campo de resposta do aluno */}
            <form onSubmit={handleSubmitTurn} className="rounded-[14px] border border-borda bg-superficie p-5 space-y-3 shadow-sm">
              <label htmlFor="student-defense-input" className="block text-[14px] font-medium text-ink">
                Sua resposta à questão da banca:
              </label>
              <textarea
                id="student-defense-input"
                value={answerInput}
                onChange={(e) => setAnswerInput(e.target.value)}
                rows={4}
                placeholder="Defenda sua tese: cite nominalmente os autores do seu trabalho, reconheça delimitações de escopo e mantenha firmeza acadêmica..."
                className="w-full rounded-[10px] border border-borda bg-paper/60 p-3.5 text-[14px] text-ink focus:border-purple outline-none resize-y transition placeholder:text-locked"
              />
              <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                <span className="text-[12px] text-locked">
                  {answerInput.trim().split(/\s+/).filter(Boolean).length} palavras
                </span>
                <div className="flex items-center gap-2">
                  <Button
                    type="submit"
                    variant="primary"
                    disabled={submitting || !answerInput.trim()}
                  >
                    {submitting ? (
                      <>
                        <Spinner size={14} /> Avaliando resposta…
                      </>
                    ) : (
                      "Responder à Banca →"
                    )}
                  </Button>
                </div>
              </div>
            </form>
          </div>
        )}

        {/* ── TELA 3: Ata de Simulação / Parecer Final ── */}
        {activeSession && activeSession.status === "completed" && activeSession.final_report && (
          <div className="space-y-6">
            <div className="rounded-[14px] border-2 border-borda bg-superficie p-8 space-y-6 shadow-sm">
              {/* Cabeçalho da Ata */}
              <div className="text-center border-b border-borda pb-6">
                <span className="text-[11px] font-bold uppercase tracking-widest text-locked">
                  Comitê de Avaliação de Pós-Graduação &amp; Pesquisa
                </span>
                <h2 className="mt-1 font-display text-[24px] text-ink uppercase tracking-wide">
                  Ata de Simulação de Defesa Acadêmica
                </h2>
                {project && (
                  <p className="mt-1 text-[14px] text-locked italic">
                    Trabalho: &quot;{project.title}&quot; · {project.institution || "Instituição de Ensino"}
                  </p>
                )}
              </div>

              {/* Veredito e Nota Geral */}
              <div className="rounded-[12px] border border-borda bg-paper/60 p-5 flex flex-wrap items-center justify-between gap-4">
                <div>
                  <span className="text-[11px] font-bold uppercase tracking-wider text-locked">Veredito da Banca</span>
                  <p className="text-[18px] font-semibold text-ink mt-0.5">
                    {activeSession.final_report.verdict_title}
                  </p>
                </div>
                <div className="text-right">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-locked">Nota Global de Sustentação</span>
                  <p className="font-display text-[28px] text-purple font-bold leading-none mt-0.5">
                    {activeSession.final_report.overall_score} <span className="text-[16px] text-locked font-normal">/ 10.0</span>
                  </p>
                </div>
              </div>

              {/* Pontos Fortes */}
              <div>
                <h3 className="text-[14px] font-bold uppercase tracking-wider text-done flex items-center gap-2 mb-3">
                  <svg viewBox="0 0 16 16" fill="currentColor" className="h-4 w-4">
                    <path d="M8 1a7 7 0 100 14A7 7 0 008 1zm3.2 5.3l-4 4a.75.75 0 01-1 0l-2-2a.75.75 0 111-1L6.7 8.8l3.5-3.5a.75.75 0 111 1z" />
                  </svg>
                  Pontos Fortes Demonstrados na Sustentação
                </h3>
                <ul className="space-y-2">
                  {activeSession.final_report.strengths.map((str, i) => (
                    <li key={i} className="text-[14px] text-ink leading-relaxed flex items-start gap-2">
                      <span className="text-done font-bold shrink-0">✓</span>
                      <span>{str}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Vulnerabilidades */}
              <div>
                <h3 className="text-[14px] font-bold uppercase tracking-wider text-orange flex items-center gap-2 mb-3">
                  <svg viewBox="0 0 16 16" fill="currentColor" className="h-4 w-4">
                    <path d="M8 1a7 7 0 100 14A7 7 0 008 1zm-.75 4a.75.75 0 011.5 0v4a.75.75 0 01-1.5 0V5zm.75 7.5a1 1 0 100-2 1 1 0 000 2z" />
                  </svg>
                  Flancos e Vulnerabilidades Apontadas pela Banca
                </h3>
                <ul className="space-y-2">
                  {activeSession.final_report.vulnerabilities.map((vuln, i) => (
                    <li key={i} className="text-[14px] text-ink leading-relaxed flex items-start gap-2">
                      <span className="text-orange font-bold shrink-0">!</span>
                      <span>{vuln}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Recomendações Táticas */}
              <div>
                <h3 className="text-[14px] font-bold uppercase tracking-wider text-purple flex items-center gap-2 mb-3">
                  <svg viewBox="0 0 16 16" fill="currentColor" className="h-4 w-4">
                    <path d="M2.5 3A1.5 1.5 0 001 4.5v7A1.5 1.5 0 002.5 13h11a1.5 1.5 0 001.5-1.5v-7A1.5 1.5 0 0013.5 3h-11zM2 4.5a.5.5 0 01.5-.5h11a.5.5 0 01.5.5v1.2L8.3 8.8a.5.5 0 01-.6 0L2 5.7V4.5z" />
                  </svg>
                  Recomendações Prioritárias para o Dia da Defesa Real
                </h3>
                <ol className="space-y-2 list-decimal list-inside text-[14px] text-ink leading-relaxed">
                  {activeSession.final_report.recommendations.map((rec, i) => (
                    <li key={i} className="pl-1">
                      <span className="text-ink">{rec}</span>
                    </li>
                  ))}
                </ol>
              </div>

              {/* Ações da Ata */}
              <div className="pt-6 border-t border-borda flex flex-wrap items-center justify-between gap-3">
                <Button type="button" variant="secondary" onClick={() => setActiveSession(null)}>
                  ← Voltar ao Início do Simulador
                </Button>
                <div className="flex items-center gap-2">
                  <Button type="button" variant="secondary" onClick={() => window.print()}>
                    Imprimir Ata
                  </Button>
                  <Button type="button" variant="primary" onClick={handleStartSession} disabled={starting}>
                    Nova Simulação de Banca
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Navegação inferior */}
        <div className="mt-10 pt-6 border-t border-borda flex flex-wrap gap-3">
          <Button type="button" variant="secondary" onClick={() => router.push(`/projetos/${id}/editor`)}>
            ← Editor
          </Button>
          <Button type="button" variant="secondary" onClick={() => router.push(`/projetos/${id}/relatorio`)}>
            Relatório do Orientador →
          </Button>
        </div>
      </main>
    </div>
  );
}

export default function DefesaPage() {
  return (
    <Suspense fallback={<main className="p-8 text-sm">Carregando simulador de defesa…</main>}>
      <DefesaInner />
    </Suspense>
  );
}
