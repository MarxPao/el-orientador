"use client";

import React, { useEffect, useState } from "react";
import { api, GateAttempt, GateTurnResult, ProgressNode } from "@/lib/api";
import { AdvisorBubble, AlertBanner, Button, StudentCard } from "@/components/ui";

type Message = {
  role: "user" | "assistant";
  content: string;
};

export function GateDialog({
  projectId,
  node,
  onClose,
  onComplete,
}: {
  projectId: string;
  node: ProgressNode;
  onClose: () => void;
  onComplete: () => void;
}) {
  const [history, setHistory] = useState<Message[]>([]);
  const [userInput, setUserInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GateTurnResult | null>(null);

  // Skip warning state
  const [showSkipConfirm, setShowSkipConfirm] = useState(false);
  const [skipReason, setSkipReason] = useState("");

  useEffect(() => {
    let cancelled = false;
    const initialQuestion = `Qual é a sua decisão para "${node.title}" e que evidência a sustenta?`;

    api<{ node_key: string; attempts: GateAttempt[] }>(
      `/projects/${projectId}/tree/nodes/${node.key}/gate`
    )
      .then((data) => {
        if (cancelled) return;
        if (data.attempts.length > 0) {
          const lastAttempt = data.attempts[data.attempts.length - 1];
          if (Array.isArray(lastAttempt.transcript) && lastAttempt.transcript.length > 0) {
            setHistory(
              lastAttempt.transcript.map((t) => ({
                role: t.role as "user" | "assistant",
                content: t.content,
              }))
            );
            return;
          }
        }
        setHistory([{ role: "assistant", content: initialQuestion }]);
      })
      .catch(() => {
        if (!cancelled) {
          setHistory([{ role: "assistant", content: initialQuestion }]);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [projectId, node.key, node.title]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!userInput.trim() || loading) return;

    const currentText = userInput.trim();
    setUserInput("");
    setError(null);
    setLoading(true);

    const updatedHistory: Message[] = [...history, { role: "user", content: currentText }];
    setHistory(updatedHistory);

    try {
      const res = await api<GateTurnResult>(`/projects/${projectId}/tree/nodes/${node.key}/gate`, {
        method: "POST",
        body: {
          user_input: currentText,
          history,
          skip: false,
        },
      });

      setResult(res);
      setHistory((prev) => [...prev, { role: "assistant", content: res.message_to_student }]);

      if (res.done && res.outcome === "liberar") {
        onComplete();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao enviar resposta ao orientador.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSkip() {
    setLoading(true);
    setError(null);
    try {
      const res = await api<GateTurnResult>(`/projects/${projectId}/tree/nodes/${node.key}/gate`, {
        method: "POST",
        body: {
          user_input: "Solicitou pular etapa com aviso consciente.",
          history,
          skip: true,
          skip_reason: skipReason.trim() || "Avançado com aviso consciente pelo aluno",
        },
      });
      setResult(res);
      onComplete();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao pular etapa.");
    } finally {
      setLoading(false);
    }
  }

  const isCompleted = result?.done && (result.outcome === "liberar" || result.outcome === "pular");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/60 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="gate-modal-title"
        className="flex max-h-[90vh] w-full max-w-2xl flex-col rounded-[16px] border border-borda bg-paper shadow-lg"
      >
        {/* Modal Header */}
        <div className="flex items-start justify-between border-b border-borda p-6">
          <div>
            <div className="flex items-center gap-3">
              <span className="rounded-[6px] bg-skipped-bg px-2.5 py-0.5 text-[13px] font-bold uppercase tracking-wider text-purple">
                Orientação Socrática
              </span>
              <span className="text-[14px] text-locked">{node.typical_time}</span>
            </div>
            <h2 id="gate-modal-title" className="mt-2 font-display text-2xl text-ink">
              {node.title}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-[10px] text-ink hover:bg-borda/40 text-lg cursor-pointer"
            aria-label="Fechar"
          >
            ✕
          </button>
        </div>

        {/* Modal Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {/* Gate Criteria Callout */}
          <div className="rounded-[12px] border border-borda bg-superficie p-4 text-[15px] leading-relaxed text-ink">
            <span className="font-bold text-purple">Critério da etapa: </span>
            <span>{node.gate_criteria}</span>
          </div>

          {/* Conversation Transcript */}
          <div className="space-y-4 pt-1">
            {history.map((msg, i) =>
              msg.role === "assistant" ? (
                <AdvisorBubble key={i} label="Orientador">
                  {msg.content}
                </AdvisorBubble>
              ) : (
                <StudentCard key={i} label="Sua resposta" className="ml-6">
                  {msg.content}
                </StudentCard>
              )
            )}
          </div>

          {/* Rubric Score Display (when evaluated) */}
          {result?.rubric_scores && (
            <div className="rounded-[12px] border border-done bg-superficie p-4 text-[15px]">
              <div className="mb-2 text-[13px] font-bold uppercase tracking-wider text-done">
                Avaliação da Etapa ({result.outcome === "liberar" ? "Aprovado" : "Em revisão"})
              </div>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="rounded-[8px] border border-borda bg-paper p-2.5">
                  <div className="text-[13px] font-bold uppercase text-locked">Clareza</div>
                  <div className="text-lg font-bold text-ink">{result.rubric_scores.clareza ?? "-"}/2</div>
                </div>
                <div className="rounded-[8px] border border-borda bg-paper p-2.5">
                  <div className="text-[13px] font-bold uppercase text-locked">Justificativa</div>
                  <div className="text-lg font-bold text-ink">{result.rubric_scores.justificativa ?? "-"}/2</div>
                </div>
                <div className="rounded-[8px] border border-borda bg-paper p-2.5">
                  <div className="text-[13px] font-bold uppercase text-locked">Coerência</div>
                  <div className="text-lg font-bold text-ink">{result.rubric_scores.coerencia ?? "-"}/2</div>
                </div>
              </div>
              {result.guidance && (
                <p className="mt-3 text-[15px] text-ink italic">{result.guidance}</p>
              )}
            </div>
          )}

          {error && <AlertBanner variant="error">{error}</AlertBanner>}

          {/* Skip Warning Section (texto e registro inalterados conforme solicitado) */}
          {showSkipConfirm && !isCompleted && (
            <div className="rounded-[12px] border-2 border-dotted border-purple bg-superficie p-5 text-[15px] space-y-3">
              <h4 className="font-bold text-purple uppercase tracking-wider text-[13px]">
                Aviso Consciente de Pulo de Etapa
              </h4>
              <p className="text-ink leading-relaxed">
                Ao pular esta etapa, as etapas seguintes serão liberadas, mas esta ação será
                registrada no seu relatório formal ao orientador humano como &quot;etapa pulada sem validação socrática&quot;.
              </p>
              <div>
                <label className="block text-[15px] font-medium text-ink mb-1.5">
                  Motivo ou justificativa do pulo (opcional):
                </label>
                <input
                  type="text"
                  value={skipReason}
                  onChange={(e) => setSkipReason(e.target.value)}
                  placeholder="Ex: Alinhado diretamente com o orientador na reunião presencial."
                  className="w-full h-[46px] rounded-[10px] border border-borda bg-superficie px-3.5 text-[15px] text-ink focus:border-purple"
                />
              </div>
              <div className="flex flex-wrap items-center gap-3 pt-2">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={loading}
                  onClick={handleSkip}
                >
                  {loading ? "Registrando…" : "Confirmar e Pular com Registro"}
                </Button>
                <button
                  type="button"
                  onClick={() => setShowSkipConfirm(false)}
                  className="inline-flex min-h-[44px] items-center px-3 text-[15px] font-medium text-locked hover:text-ink underline cursor-pointer"
                >
                  Cancelar
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="border-t border-borda p-5 bg-superficie rounded-b-[16px]">
          {isCompleted ? (
            <div className="flex flex-wrap items-center justify-between gap-4">
              <span className="text-[15px] font-medium text-done">
                {result.outcome === "liberar"
                  ? "Etapa validada com sucesso pelo orientador."
                  : "Etapa pulada com registro de aviso consciente."}
              </span>
              <Button type="button" variant="primary" onClick={onClose}>
                Concluir e Retornar à Árvore
              </Button>
            </div>
          ) : (
            <form onSubmit={handleSend} className="space-y-3">
              <div className="flex flex-col sm:flex-row gap-3">
                <textarea
                  rows={2}
                  value={userInput}
                  disabled={loading}
                  onChange={(e) => setUserInput(e.target.value)}
                  placeholder="Escreva sua resposta e justificativa para o orientador…"
                  className="flex-1 resize-none rounded-[10px] border border-borda bg-paper/40 p-3 text-[15px] text-ink focus:border-purple"
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                      e.preventDefault();
                      void handleSend(e);
                    }
                  }}
                />
                <Button
                  type="submit"
                  variant="primary"
                  disabled={loading || !userInput.trim()}
                  className="shrink-0"
                >
                  {loading ? "Orientando…" : "Responder"}
                </Button>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2 text-[14px] text-locked">
                <span>Pressione Ctrl + Enter para responder.</span>
                {!showSkipConfirm && (
                  <button
                    type="button"
                    onClick={() => setShowSkipConfirm(true)}
                    className="inline-flex min-h-[44px] items-center font-medium text-purple underline cursor-pointer"
                  >
                    Pular etapa (com justificativa)
                  </button>
                )}
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
