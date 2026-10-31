"use client";

import { useRouter } from "next/navigation";
import React, { useEffect, useMemo, useState } from "react";
import {
  ApiError,
  api,
  getToken,
  ProgressNode,
  TreeData,
} from "@/lib/api";
import { AppHeader } from "@/components/app-header";
import { AlertBanner, Button, StatusBadge } from "@/components/ui";
import { GateDialog } from "./gate-dialog";
import { SchedulePanel } from "./schedule-panel";

type NodeStatus = ProgressNode["status"];

const STATUS_CARD_STYLE: Record<NodeStatus, string> = {
  done: "border-2 border-done bg-superficie text-ink",
  available: "border-2 border-orange bg-superficie text-ink",
  locked: "border border-dashed border-locked/60 bg-paper text-locked",
  skipped: "border border-purple/40 bg-skipped-bg text-ink",
  needs_review: "border-2 border-dotted border-purple bg-superficie text-ink",
};

export default function TreeView({ id }: { id: string }) {
  const router = useRouter();
  const [tree, setTree] = useState<TreeData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [gateNode, setGateNode] = useState<ProgressNode | null>(null);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/entrar");
      return;
    }
    let cancelled = false;
    api<TreeData>(`/projects/${id}/tree`)
      .then((d) => {
        if (!cancelled) {
          setTree(d);
          if (!selectedKey && d.nodes.length > 0) {
            const firstAvail = d.nodes.find((n) => n.status === "available");
            setSelectedKey(firstAvail ? firstAvail.key : d.nodes[0].key);
          }
        }
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) return router.replace("/entrar");
        setError(err instanceof Error ? err.message : "Algo deu errado.");
      });
    return () => {
      cancelled = true;
    };
  }, [id, reloadKey, router, selectedKey]);

  const nodeMap = useMemo(() => new Map((tree?.nodes ?? []).map((n) => [n.key, n])), [tree]);

  const selectedNode = useMemo(
    () => (selectedKey ? nodeMap.get(selectedKey) ?? null : null),
    [selectedKey, nodeMap]
  );

  const counts = useMemo(() => {
    const list = tree?.nodes ?? [];
    return {
      done: list.filter((n) => n.status === "done").length,
      available: list.filter((n) => n.status === "available").length,
      locked: list.filter((n) => n.status === "locked").length,
      skipped: list.filter((n) => n.status === "skipped").length,
      needsReview: list.filter((n) => n.status === "needs_review").length,
      total: list.length,
    };
  }, [tree]);

  const queuedNodes = useMemo(() => (tree?.nodes ?? []).filter((n) => n.queued), [tree]);

  async function updateNode(
    nodeKey: string,
    payload: { status?: NodeStatus; queued?: boolean; skipped_reason?: string }
  ) {
    setBusy(true);
    setError(null);
    try {
      await api(`/projects/${id}/tree/nodes/${nodeKey}`, {
        method: "PATCH",
        body: payload,
      });
      if (payload.status === "done") {
        setNotice(`Etapa "${nodeMap.get(nodeKey)?.title}" marcada como concluída.`);
      } else if (payload.status === "skipped") {
        setNotice(`Etapa "${nodeMap.get(nodeKey)?.title}" pulada com aviso registrado.`);
      }
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Algo deu errado ao atualizar.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-paper text-ink">
      <AppHeader projectId={id} />

      <main className="mx-auto w-full max-w-[1440px] flex-1 px-6 py-8 sm:px-10 space-y-6">
        {/* Cabeçalho da página */}
        <div className="flex flex-wrap items-baseline justify-between gap-4 border-b border-borda pb-5">
          <div>
            <h1 className="font-display text-3xl sm:text-[36px] text-ink">Árvore de progresso</h1>
            <p className="mt-1 text-[15px] text-locked">
              {tree?.template_title ?? "Plano Acadêmico"}
            </p>
          </div>

          {/* Contadores unificados de estado (Disponível usa o mesmo laranja dos cartões, texto tinta) */}
          <div className="flex flex-wrap items-center gap-3">
            <StatusBadge status="done" label={`${counts.done} Concluído(s)`} />
            <StatusBadge status="available" label={`${counts.available} Disponível(is)`} />
            {counts.needsReview > 0 && (
              <StatusBadge status="needs_review" label={`${counts.needsReview} Revisar`} />
            )}
            {counts.skipped > 0 && (
              <StatusBadge status="skipped" label={`${counts.skipped} Pulado(s)`} />
            )}
            <StatusBadge status="locked" label={`${counts.locked} Bloqueado(s)`} />
          </div>
        </div>

        {/* Fila de pesquisa destacada */}
        {queuedNodes.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 rounded-[10px] border border-borda bg-superficie px-4 py-2.5 text-[15px]">
            <span className="font-bold text-ink">Fila de pesquisa atual:</span>
            <div className="flex flex-wrap items-center gap-2">
              {queuedNodes.map((n) => (
                <mark key={n.key} className="mark-orange font-medium">
                  {n.title}
                </mark>
              ))}
            </div>
          </div>
        )}

        {error && <AlertBanner variant="error">{error}</AlertBanner>}
        {notice && <AlertBanner variant="notice">{notice}</AlertBanner>}

        {/* Cronograma & Prazos */}
        <SchedulePanel
          projectId={id}
          reloadKey={reloadKey}
          onSelectNode={(k) => setSelectedKey(k)}
        />

        {tree === null && !error && (
          <p className="py-8 text-[15px] text-locked">Carregando fases e etapas do trabalho…</p>
        )}

        {tree && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 items-start">
            {/* Colunas de Fases (8 colunas no desktop) */}
            <section
              aria-label="Fases do trabalho"
              className="flex gap-4 overflow-x-auto pb-4 lg:col-span-8"
            >
              {tree.phases.map((phase) => {
                const phaseNodes = tree.nodes.filter((n) => n.phase === phase.key);
                return (
                  <div
                    key={phase.key}
                    className="w-[260px] shrink-0 rounded-[14px] border border-borda bg-superficie/60 p-4 space-y-3"
                  >
                    <h2 className="border-b border-borda pb-2.5 font-display text-lg text-ink">
                      {phase.label}
                    </h2>

                    <div className="space-y-3">
                      {phaseNodes.map((node) => {
                        const isSelected = selectedKey === node.key;
                        return (
                          <button
                            type="button"
                            key={node.key}
                            onClick={() => setSelectedKey(node.key)}
                            className={`w-full text-left cursor-pointer rounded-[12px] p-3.5 transition ${
                              STATUS_CARD_STYLE[node.status]
                            } ${isSelected ? "ring-2 ring-purple ring-offset-2 ring-offset-paper" : ""}`}
                          >
                            <div className="flex items-start justify-between gap-2">
                              <h3 className="text-[15px] font-bold leading-snug text-ink">
                                {node.title}
                              </h3>
                            </div>

                            <div className="mt-2">
                              <StatusBadge status={node.status} />
                            </div>

                            <p className="mt-2.5 line-clamp-2 text-[14px] leading-snug text-locked">
                              {node.description}
                            </p>

                            <div className="mt-3 flex items-center justify-between text-[13px] text-locked">
                              <span>{node.typical_time}</span>
                              {node.queued && (
                                <mark className="mark-orange text-[12px] font-bold uppercase">
                                  Na fila
                                </mark>
                              )}
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </section>

            {/* Painel Lateral de Detalhes da Etapa (4 colunas no desktop) */}
            <aside
              aria-label="Painel de detalhes do nó"
              className="rounded-[16px] border border-borda bg-superficie p-6 lg:col-span-4 space-y-5"
            >
              {selectedNode ? (
                <div className="space-y-5">
                  <div>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-[13px] font-bold uppercase tracking-wider text-locked">
                        {tree.phases.find((p) => p.key === selectedNode.phase)?.label}
                      </span>
                      <StatusBadge status={selectedNode.status} />
                    </div>
                    <h2 className="mt-2 font-display text-2xl leading-snug text-ink">
                      {selectedNode.title}
                    </h2>
                    <p className="mt-2 text-[15px] leading-relaxed text-ink">
                      {selectedNode.description}
                    </p>
                  </div>

                  {/* Pré-requisitos */}
                  <div className="border-t border-borda pt-4">
                    <h3 className="text-[13px] font-bold uppercase tracking-wider text-locked">
                      Requisitos
                    </h3>
                    {selectedNode.prerequisites.length === 0 ? (
                      <p className="mt-1.5 text-[15px] text-locked">
                        Nenhum pré-requisito (etapa inicial).
                      </p>
                    ) : (
                      <ul className="mt-2 space-y-2 text-[15px]">
                        {selectedNode.prerequisites.map((reqKey) => {
                          const reqNode = nodeMap.get(reqKey);
                          return (
                            <li
                              key={reqKey}
                              className="flex items-center justify-between gap-2 text-ink"
                            >
                              <span>{reqNode?.title ?? reqKey}</span>
                              <StatusBadge status={reqNode?.status ?? "locked"} />
                            </li>
                          );
                        })}
                      </ul>
                    )}
                  </div>

                  {/* Tempo estimado e o que libera */}
                  <div className="border-t border-borda pt-4 text-[15px] space-y-2">
                    <div>
                      <span className="font-bold text-ink">Tempo típico estimado: </span>
                      <span className="text-locked">{selectedNode.typical_time}</span>
                    </div>
                    {selectedNode.unlocks.length > 0 && (
                      <div>
                        <span className="font-bold text-ink">O que libera: </span>
                        <span className="text-locked">
                          {selectedNode.unlocks
                            .map((k) => nodeMap.get(k)?.title ?? k)
                            .join(", ")}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Critério de Desbloqueio */}
                  <div className="rounded-[12px] border border-borda bg-paper p-4 text-[15px]">
                    <h3 className="text-[13px] font-bold uppercase tracking-wider text-purple">
                      Critério de Desbloqueio
                    </h3>
                    <p className="mt-1.5 font-serif-academic text-[16px] italic leading-relaxed text-ink">
                      {selectedNode.gate_criteria}
                    </p>
                  </div>

                  {/* Ações */}
                  <div className="border-t border-borda pt-4 space-y-3">
                    <label className="flex min-h-[44px] items-center gap-2.5 text-[15px] font-medium text-ink cursor-pointer">
                      <input
                        type="checkbox"
                        checked={selectedNode.queued}
                        disabled={busy}
                        onChange={(e) =>
                          void updateNode(selectedNode.key, { queued: e.target.checked })
                        }
                        className="h-4 w-4 accent-purple"
                      />
                      <span>Marcar na fila de pesquisa</span>
                    </label>

                    <div className="flex flex-col gap-2.5 pt-1">
                      {selectedNode.status === "available" && (
                        <>
                          <Button
                            type="button"
                            variant="primary"
                            disabled={busy}
                            onClick={() => setGateNode(selectedNode)}
                            className="w-full"
                          >
                            Responder ao orientador
                          </Button>

                          <Button
                            type="button"
                            variant="secondary"
                            disabled={busy}
                            onClick={() => void updateNode(selectedNode.key, { status: "done" })}
                            className="w-full"
                          >
                            {busy ? "Gravando…" : "Concluir sem perguntas"}
                          </Button>

                          <Button
                            type="button"
                            variant="secondary"
                            disabled={busy}
                            onClick={() =>
                              void updateNode(selectedNode.key, {
                                status: "skipped",
                                skipped_reason: "Pulado pelo usuário com aviso consciente",
                              })
                            }
                            className="w-full"
                          >
                            Pular etapa (com justificativa)
                          </Button>
                        </>
                      )}

                      {selectedNode.status === "needs_review" && (
                        <Button
                          type="button"
                          variant="primary"
                          disabled={busy}
                          onClick={() => setGateNode(selectedNode)}
                          className="w-full"
                        >
                          Responder ao orientador
                        </Button>
                      )}

                      {selectedNode.status === "done" && (
                        <Button
                          type="button"
                          variant="secondary"
                          disabled={busy}
                          onClick={() => void updateNode(selectedNode.key, { status: "available" })}
                          className="w-full"
                        >
                          Reabrir etapa
                        </Button>
                      )}

                      {selectedNode.status === "skipped" && (
                        <Button
                          type="button"
                          variant="secondary"
                          disabled={busy}
                          onClick={() => void updateNode(selectedNode.key, { status: "available" })}
                          className="w-full"
                        >
                          Retomar etapa pulada
                        </Button>
                      )}

                      {selectedNode.status === "locked" && (
                        <p className="text-center text-[14px] text-locked py-2">
                          Conclua os pré-requisitos para liberar esta etapa.
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-[15px] text-locked">
                  Selecione uma etapa para visualizar os detalhes.
                </p>
              )}
            </aside>
          </div>
        )}

        {gateNode && (
          <GateDialog
            projectId={id}
            node={gateNode}
            onClose={() => setGateNode(null)}
            onComplete={() => {
              setReloadKey((k) => k + 1);
              setGateNode(null);
            }}
          />
        )}
      </main>
    </div>
  );
}
