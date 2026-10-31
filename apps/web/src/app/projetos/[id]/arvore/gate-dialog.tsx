"use client";

import { useEffect, useState } from "react";
import {
  api,
  GateAttempt,
  GateTurnResult,
  ProgressNode,
} from "@/lib/api";

type Message = {
  role: "user" | "assistant";
  content: string;
};

interface GateDialogProps {
  projectId: string;
  node: ProgressNode;
  onClose: () => void;
  onComplete: () => void;
}

export function GateDialog({ projectId, node, onClose, onComplete }: GateDialogProps) {
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
    // Load existing gate attempts
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
          }
        } else {
          // Initial greeting question from advisor
          setHistory([
            {
              role: "assistant",
              content: `Olá. Vamos avaliar a etapa "${node.title}". Como você justifica a formulação e a escolha desta etapa no contexto do seu trabalho?`,
            },
          ]);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setHistory([
            {
              role: "assistant",
              content: `Olá. Vamos avaliar a etapa "${node.title}". Como você justifica a formulação e a escolha desta etapa no contexto do seu trabalho?`,
            },
          ]);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [projectId, node.key, node.title]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!userInput.trim() || loading) return;

    const messageText = userInput.trim();
    setUserInput("");
    setError(null);
    setLoading(true);

    const updatedHistory: Message[] = [...history, { role: "user", content: messageText }];
    setHistory(updatedHistory);

    try {
      const res = await api<GateTurnResult>(`/projects/${projectId}/tree/nodes/${node.key}/gate`, {
        method: "POST",
        body: {
          user_input: messageText,
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="flex max-h-[90vh] w-full max-w-2xl flex-col rounded-lg border border-ink/20 bg-white shadow-xl">
        {/* Modal Header */}
        <div className="flex items-start justify-between border-b border-ink/10 p-5">
          <div>
            <div className="flex items-center gap-2">
              <span className="rounded bg-ink/10 px-2 py-0.5 text-[11px] font-medium uppercase tracking-wider text-ink/70">
                Gate Socrático
              </span>
              <span className="text-xs text-ink/60">{node.typical_time}</span>
            </div>
            <h2 className="mt-1 font-serif-academic text-xl font-bold text-ink">{node.title}</h2>
          </div>
          <button
            onClick={onClose}
            className="rounded p-1 text-ink/50 hover:bg-paper hover:text-ink text-sm"
            aria-label="Fechar"
          >
            ✕
          </button>
        </div>

        {/* Modal Content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* Gate Criteria Callout */}
          <div className="rounded border border-available/30 bg-available/5 p-3 text-xs leading-relaxed text-ink/80">
            <span className="font-semibold text-available">Critério avaliativo: </span>
            <span>{node.gate_criteria}</span>
          </div>

          {/* Conversation Transcript */}
          <div className="space-y-3 pt-2">
            {history.map((msg, i) => (
              <div
                key={i}
                className={`rounded-lg p-3 text-xs leading-relaxed ${
                  msg.role === "assistant"
                    ? "border border-ink/10 bg-paper/60 text-ink"
                    : "ml-6 border border-available/20 bg-available/5 text-ink"
                }`}
              >
                <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-ink/50">
                  {msg.role === "assistant" ? "Orientador Acadêmico" : "Sua Resposta"}
                </div>
                <p className="whitespace-pre-wrap">{msg.content}</p>
              </div>
            ))}
          </div>

          {/* Rubric Evaluation Results */}
          {result?.rubric_scores && (
            <div className="rounded border border-done/40 bg-done/5 p-4 text-xs space-y-2">
              <h4 className="font-semibold text-done uppercase tracking-wider text-[11px]">
                Avaliação da Rubrica
              </h4>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="rounded bg-white/80 p-2 border border-done/20">
                  <div className="text-[10px] text-ink/60 font-medium">Clareza</div>
                  <div className="text-sm font-bold text-ink">{result.rubric_scores.clareza ?? "-"}/2</div>
                </div>
                <div className="rounded bg-white/80 p-2 border border-done/20">
                  <div className="text-[10px] text-ink/60 font-medium">Justificativa</div>
                  <div className="text-sm font-bold text-ink">{result.rubric_scores.justificativa ?? "-"}/2</div>
                </div>
                <div className="rounded bg-white/80 p-2 border border-done/20">
                  <div className="text-[10px] text-ink/60 font-medium">Coerência</div>
                  <div className="text-sm font-bold text-ink">{result.rubric_scores.coerencia ?? "-"}/2</div>
                </div>
              </div>
              {result.guidance && (
                <p className="mt-2 text-[11px] text-ink/80 italic">{result.guidance}</p>
              )}
            </div>
          )}

          {error && (
            <p role="alert" className="text-xs text-danger">
              {error}
            </p>
          )}

          {/* Skip Warning Section */}
          {showSkipConfirm && !isCompleted && (
            <div className="rounded border border-gap/40 bg-gap/5 p-4 text-xs space-y-3">
              <h4 className="font-semibold text-gap uppercase tracking-wider text-[11px]">
                Aviso Consciente de Pulo de Etapa
              </h4>
              <p className="text-ink/80 leading-relaxed">
                Ao pular esta etapa, as etapas seguintes serão liberadas, mas esta ação será
                registrada no seu relatório formal ao orientador humano como &quot;etapa pulada sem validação socrática&quot;.
              </p>
              <div>
                <label className="block text-[11px] font-medium text-ink/70 mb-1">
                  Motivo ou justificativa do pulo (opcional):
                </label>
                <input
                  type="text"
                  value={skipReason}
                  onChange={(e) => setSkipReason(e.target.value)}
                  placeholder="Ex: Alinhado diretamente com o orientador na reunião presencial."
                  className="w-full rounded border border-ink/20 px-3 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-gap"
                />
              </div>
              <div className="flex items-center gap-2 pt-1">
                <button
                  type="button"
                  disabled={loading}
                  onClick={handleSkip}
                  className="rounded bg-gap px-3 py-1.5 text-xs font-medium text-white hover:bg-gap/90 disabled:opacity-50"
                >
                  {loading ? "Registrando…" : "Confirmar e Pular com Registro"}
                </button>
                <button
                  type="button"
                  onClick={() => setShowSkipConfirm(false)}
                  className="rounded border border-ink/20 px-3 py-1.5 text-xs text-ink/70 hover:bg-paper"
                >
                  Cancelar
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="border-t border-ink/10 p-4">
          {isCompleted ? (
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-done">
                {result.outcome === "liberar"
                  ? "Etapa validada com sucesso pelo orientador!"
                  : "Etapa pulada com registro de aviso consciente."}
              </span>
              <button
                type="button"
                onClick={onClose}
                className="rounded bg-ink px-4 py-2 text-xs font-medium text-white hover:bg-ink/90"
              >
                Concluir e Retornar à Árvore
              </button>
            </div>
          ) : (
            <form onSubmit={handleSend} className="space-y-3">
              <div className="flex gap-2">
                <textarea
                  rows={2}
                  value={userInput}
                  disabled={loading}
                  onChange={(e) => setUserInput(e.target.value)}
                  placeholder="Escreva sua resposta e justificativa para o orientador…"
                  className="flex-1 resize-none rounded border border-ink/20 p-2.5 text-xs focus:outline-none focus:ring-1 focus:ring-ink"
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                      e.preventDefault();
                      void handleSend(e);
                    }
                  }}
                />
                <button
                  type="submit"
                  disabled={loading || !userInput.trim()}
                  className="rounded bg-ink px-4 py-2 text-xs font-medium text-white hover:bg-ink/90 disabled:opacity-50"
                >
                  {loading ? "Orientando…" : "Responder"}
                </button>
              </div>

              <div className="flex items-center justify-between text-[11px] text-ink/60">
                <span>Dica: Pressione Ctrl + Enter para enviar.</span>
                {!showSkipConfirm && (
                  <button
                    type="button"
                    onClick={() => setShowSkipConfirm(true)}
                    className="text-ink/60 hover:text-gap underline"
                  >
                    Pular etapa com aviso consciente
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
