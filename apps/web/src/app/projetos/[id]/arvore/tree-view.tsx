"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  ApiError,
  api,
  getToken,
  NODE_STATUS_LABELS,
  ProgressNode,
  TreeData,
} from "@/lib/api";
import { GateDialog } from "./gate-dialog";
import { SchedulePanel } from "./schedule-panel";

type NodeStatus = ProgressNode["status"];

const STATUS_CARD_STYLE: Record<NodeStatus, string> = {
  done: "border-done bg-done/5 text-ink",
  available: "border-orange bg-orange/10 shadow-sm ring-1 ring-orange/30",
  locked: "border-dashed border-locked/60 bg-paper/60 text-ink/60",
  skipped: "border-ink/20 bg-paper/30 text-ink/50",
  needs_review: "border-gap border-dotted bg-gap/5 text-ink",
};

const STATUS_BADGE_STYLE: Record<NodeStatus, string> = {
  done: "bg-done text-white",
  available: "bg-orange text-ink",
  locked: "bg-locked/30 text-ink/70",
  skipped: "bg-ink/20 text-ink/70",
  needs_review: "bg-gap text-white",
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
            // Default selection to first available node or first node
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

  const selectedNode = useMemo(() => (selectedKey ? nodeMap.get(selectedKey) ?? null : null), [selectedKey, nodeMap]);

  const counts = useMemo(() => {
    const list = tree?.nodes ?? [];
    return {
      done: list.filter((n) => n.status === "done").length,
      available: list.filter((n) => n.status === "available").length,
      locked: list.filter((n) => n.status === "locked").length,
      total: list.length,
    };
  }, [tree]);

  const queuedNodes = useMemo(() => (tree?.nodes ?? []).filter((n) => n.queued), [tree]);

  async function updateNode(nodeKey: string, payload: { status?: NodeStatus; queued?: boolean; skipped_reason?: string }) {
    setBusy(true);
    setError(null);
    try {
      await api(`/projects/${id}/tree/nodes/${nodeKey}`, {
        method: "PATCH",
        body: payload,
      });
      if (payload.status === "done") {
        setNotice(`Etapa '${nodeMap.get(nodeKey)?.title}' marcada como concluída.`);
      } else if (payload.status === "skipped") {
        setNotice(`Etapa '${nodeMap.get(nodeKey)?.title}' pulada com aviso registrado.`);
      }
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Algo deu errado ao atualizar.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-7xl px-6 py-8">
      {/* Header */}
      <header className="flex flex-wrap items-baseline justify-between gap-4 border-b border-ink/10 pb-5">
        <div>
          <h1 className="font-serif-academic text-3xl">Árvore de Progresso</h1>
          <p className="mt-1 text-sm text-ink/70">{tree?.template_title ?? "Plano Acadêmico"}</p>
        </div>
        <div className="flex items-center gap-4 text-sm">
          <Link href={`/projetos/${id}/mapa`} className="text-available underline">
            Abrir mapa de conhecimento
          </Link>
          <Link href={`/projetos/${id}/editor`} className="text-available underline">
            Abrir editor
          </Link>
          <Link href="/projetos" className="text-ink/70 underline">
            Voltar aos projetos
          </Link>
        </div>
      </header>

      {/* Status Summary & Research Queue */}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1.5 font-medium text-done">
            <span className="h-2 w-2 rounded-full bg-done" /> {counts.done} Concluído(s)
          </span>
          <span className="flex items-center gap-1.5 font-medium text-available">
            <span className="h-2 w-2 rounded-full bg-available" /> {counts.available} Disponível(is)
          </span>
          <span className="flex items-center gap-1.5 text-ink/60">
            <span className="h-2 w-2 rounded-full bg-locked/50" /> {counts.locked} Bloqueado(s)
          </span>
        </div>

        {queuedNodes.length > 0 && (
          <div className="flex items-center gap-2 rounded bg-available/10 px-3 py-1 font-medium text-available">
            <span>Fila de pesquisa atual:</span>
            <span>{queuedNodes.map((n) => n.title).join(", ")}</span>
          </div>
        )}
      </div>

      {error && (
        <p role="alert" className="mt-4 text-sm text-danger">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="mt-4 text-sm font-medium text-done">
          {notice}
        </p>
      )}

      {/* Schedule & Deadline Alerts */}
      <div className="mt-5">
        <SchedulePanel
          projectId={id}
          reloadKey={reloadKey}
          onSelectNode={(k) => setSelectedKey(k)}
        />
      </div>

      {tree === null && !error && <p className="mt-8 text-sm">Carregando fases e etapas do trabalho…</p>}

      {tree && (
        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-4">
          {/* Phase Columns (3 cols on large screen) */}
          <section
            aria-label="Fases do trabalho"
            className="flex gap-4 overflow-x-auto pb-4 lg:col-span-3"
          >
            {tree.phases.map((phase) => {
              const phaseNodes = tree.nodes.filter((n) => n.phase === phase.key);
              return (
                <div key={phase.key} className="w-56 shrink-0 rounded-lg border border-ink/10 bg-paper/40 p-3">
                  <h2 className="border-b border-ink/10 pb-2 text-xs font-semibold uppercase tracking-wider text-ink/70">
                    {phase.label}
                  </h2>
                  <div className="mt-3 space-y-2.5">
                    {phaseNodes.map((node) => {
                      const isSelected = selectedKey === node.key;
                      const isLocked = node.status === "locked";
                      return (
                        <div
                          key={node.key}
                          onClick={() => setSelectedKey(node.key)}
                          className={`cursor-pointer rounded border p-3 transition-all ${
                            STATUS_CARD_STYLE[node.status]
                          } ${isSelected ? "ring-2 ring-ink ring-offset-1" : ""} ${
                            isLocked ? "opacity-75 hover:opacity-100" : ""
                          }`}
                        >
                          <div className="flex items-start justify-between gap-1.5">
                            <h3 className="text-xs font-semibold leading-tight">{node.title}</h3>
                            <span
                              className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${
                                STATUS_BADGE_STYLE[node.status]
                              }`}
                            >
                              {NODE_STATUS_LABELS[node.status]}
                            </span>
                          </div>
                          <p className="mt-1.5 line-clamp-2 text-[11px] text-ink/70">{node.description}</p>
                          <div className="mt-2 flex items-center justify-between text-[10px] text-ink/60">
                            <span>{node.typical_time}</span>
                            {node.queued && (
                              <span className="font-semibold text-available">Na fila</span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </section>

          {/* Side Panel (Painel lateral) */}
          <aside
            aria-label="Painel de detalhes do nó"
            className="rounded-lg border border-ink/20 bg-white p-5 lg:col-span-1"
          >
            {selectedNode ? (
              <div className="space-y-4">
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold uppercase tracking-wider text-ink/60">
                      {tree.phases.find((p) => p.key === selectedNode.phase)?.label}
                    </span>
                    <span
                      className={`rounded px-2 py-0.5 text-xs font-medium uppercase tracking-wide ${
                        STATUS_BADGE_STYLE[selectedNode.status]
                      }`}
                    >
                      {NODE_STATUS_LABELS[selectedNode.status]}
                    </span>
                  </div>
                  <h2 className="mt-1 font-serif-academic text-xl font-bold leading-tight">
                    {selectedNode.title}
                  </h2>
                  <p className="mt-2 text-xs leading-relaxed text-ink/80">{selectedNode.description}</p>
                </div>

                {/* Prerequisites */}
                <div className="border-t border-ink/10 pt-3">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-ink/70">Requisitos</h3>
                  {selectedNode.prerequisites.length === 0 ? (
                    <p className="mt-1 text-xs text-ink/60">Nenhum pré-requisito (etapa inicial).</p>
                  ) : (
                    <ul className="mt-1.5 space-y-1 text-xs">
                      {selectedNode.prerequisites.map((reqKey) => {
                        const reqNode = nodeMap.get(reqKey);
                        return (
                          <li key={reqKey} className="flex items-center justify-between text-ink/80">
                            <span>{reqNode?.title ?? reqKey}</span>
                            <span
                              className={`rounded px-1.5 py-0.2 text-[10px] ${
                                STATUS_BADGE_STYLE[reqNode?.status ?? "locked"]
                              }`}
                            >
                              {NODE_STATUS_LABELS[reqNode?.status ?? "locked"]}
                            </span>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </div>

                {/* Typical Time & What it unlocks */}
                <div className="border-t border-ink/10 pt-3 text-xs space-y-2">
                  <div>
                    <span className="font-semibold text-ink/70">Tempo típico estimado: </span>
                    <span className="text-ink/80">{selectedNode.typical_time}</span>
                  </div>
                  {selectedNode.unlocks.length > 0 && (
                    <div>
                      <span className="font-semibold text-ink/70">O que libera: </span>
                      <span className="text-ink/80">
                        {selectedNode.unlocks.map((k) => nodeMap.get(k)?.title ?? k).join(", ")}
                      </span>
                    </div>
                  )}
                </div>

                {/* Gate Criteria */}
                <div className="rounded border border-ink/15 bg-paper p-3 text-xs">
                  <h3 className="font-semibold text-ink/80">Critério de Desbloqueio (Gate)</h3>
                  <p className="mt-1 italic leading-relaxed text-ink/70">{selectedNode.gate_criteria}</p>
                </div>

                {/* Actions */}
                <div className="border-t border-ink/10 pt-3 space-y-2">
                  <label className="flex items-center gap-2 text-xs font-medium text-ink cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selectedNode.queued}
                      disabled={busy}
                      onChange={(e) => void updateNode(selectedNode.key, { queued: e.target.checked })}
                    />
                    Marcar na fila de pesquisa
                  </label>

                  <div className="flex flex-col gap-2 pt-2">
                    {selectedNode.status === "available" && (
                      <>
                        <button
                          disabled={busy}
                          onClick={() => setGateNode(selectedNode)}
                          className="w-full rounded bg-available py-2 text-xs font-medium text-white hover:bg-available/90 disabled:opacity-60"
                        >
                          Passar pelo Gate Socrático
                        </button>
                        <button
                          disabled={busy}
                          onClick={() => void updateNode(selectedNode.key, { status: "done" })}
                          className="w-full rounded border border-done/40 bg-done/5 py-1.5 text-xs font-medium text-done hover:bg-done/10 disabled:opacity-60"
                        >
                          {busy ? "Gravando…" : "Concluir diretamente"}
                        </button>
                        <button
                          disabled={busy}
                          onClick={() =>
                            void updateNode(selectedNode.key, {
                              status: "skipped",
                              skipped_reason: "Pulado pelo usuário com aviso consciente",
                            })
                          }
                          className="w-full rounded border border-ink/20 py-1.5 text-xs text-ink/70 hover:bg-paper disabled:opacity-60"
                        >
                          Pular etapa com aviso
                        </button>
                      </>
                    )}

                    {selectedNode.status === "needs_review" && (
                      <button
                        disabled={busy}
                        onClick={() => setGateNode(selectedNode)}
                        className="w-full rounded bg-gap py-2 text-xs font-medium text-white hover:bg-gap/90 disabled:opacity-60"
                      >
                        Retomar Gate Socrático
                      </button>
                    )}

                    {selectedNode.status === "done" && (
                      <button
                        disabled={busy}
                        onClick={() => void updateNode(selectedNode.key, { status: "available" })}
                        className="w-full rounded border border-ink/30 py-1.5 text-xs text-ink disabled:opacity-60"
                      >
                        Reabrir etapa
                      </button>
                    )}

                    {selectedNode.status === "skipped" && (
                      <button
                        disabled={busy}
                        onClick={() => void updateNode(selectedNode.key, { status: "available" })}
                        className="w-full rounded border border-ink/30 py-1.5 text-xs text-ink disabled:opacity-60"
                      >
                        Retomar etapa pulada
                      </button>
                    )}

                    {selectedNode.status === "locked" && (
                      <p className="text-center text-[11px] text-ink/50">
                        Complete os pré-requisitos para liberar esta etapa.
                      </p>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-sm text-ink/60">Selecione uma etapa para visualizar os detalhes.</p>
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
  );
}
