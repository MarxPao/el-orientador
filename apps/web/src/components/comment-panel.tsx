"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  SectionComment,
  SectionVersion,
  createSectionComment,
  listSectionComments,
  listSectionVersions,
  resolveSectionComment,
  restoreSectionVersion,
} from "@/lib/api";

// ── Helpers ───────────────────────────────────────────────────────────────────

function relativeTime(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "agora";
  if (diff < 3600) return `${Math.floor(diff / 60)} min atrás`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} h atrás`;
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
}

function Spinner() {
  return (
    <svg className="animate-spin h-4 w-4 text-purple" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="40 60" strokeLinecap="round" />
    </svg>
  );
}

// ── Types ─────────────────────────────────────────────────────────────────────

type PanelTab = "comentarios" | "versoes";

interface Props {
  projectId: string;
  sectionId: string | null;
  sectionTitle?: string;
  onRestoreVersion?: (sectionId: string) => void;
  onClose: () => void;
}

// ── Comment thread ────────────────────────────────────────────────────────────

function CommentThread({
  projectId,
  sectionId,
}: {
  projectId: string;
  sectionId: string;
}) {
  const [comments, setComments] = useState<SectionComment[]>([]);
  const [loading, setLoading] = useState(true);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [resolvingId, setResolvingId] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setLoading(true);
    listSectionComments(projectId, sectionId)
      .then((c) => { setComments(c); setLoading(false); })
      .catch(() => setLoading(false));
  }, [projectId, sectionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [comments]);

  async function send() {
    if (!draft.trim()) return;
    setSending(true);
    try {
      const c = await createSectionComment(projectId, sectionId, draft.trim());
      setComments((prev) => [...prev, c]);
      setDraft("");
    } finally {
      setSending(false);
    }
  }

  async function resolve(commentId: string) {
    setResolvingId(commentId);
    try {
      const updated = await resolveSectionComment(projectId, sectionId, commentId);
      setComments((prev) => prev.map((c) => c.id === commentId ? updated : c));
    } finally {
      setResolvingId(null);
    }
  }

  const open = comments.filter((c) => !c.resolved);
  const resolved = comments.filter((c) => c.resolved);

  return (
    <div className="flex flex-col h-full">
      {/* Thread */}
      <div className="flex-1 overflow-y-auto space-y-3 pr-1">
        {loading ? (
          <div className="flex items-center justify-center py-8 text-locked gap-2"><Spinner /> Carregando…</div>
        ) : comments.length === 0 ? (
          <div className="py-8 text-center text-[14px] text-locked">Nenhum comentário ainda.<br />Seja o primeiro a comentar esta seção.</div>
        ) : (
          <>
            {open.map((c) => (
              <div key={c.id} className="rounded-[10px] border border-borda bg-paper p-3 group">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 mb-1">
                      <span className="h-6 w-6 rounded-full bg-purple/15 text-purple text-[11px] font-bold flex items-center justify-center shrink-0">
                        {(c.author_name ?? c.author_email).charAt(0).toUpperCase()}
                      </span>
                      <span className="text-[13px] font-medium text-ink truncate">{c.author_name ?? c.author_email.split("@")[0]}</span>
                      <span className="text-[12px] text-locked">{relativeTime(c.created_at)}</span>
                    </div>
                    <p className="text-[14px] text-ink leading-relaxed whitespace-pre-wrap">{c.content}</p>
                  </div>
                  <button
                    onClick={() => resolve(c.id)}
                    disabled={resolvingId === c.id}
                    title="Marcar como resolvido"
                    className="shrink-0 opacity-0 group-hover:opacity-100 h-6 w-6 rounded-full border border-borda flex items-center justify-center text-locked hover:text-done hover:border-done transition disabled:opacity-50"
                  >
                    {resolvingId === c.id ? <Spinner /> : (
                      <svg viewBox="0 0 16 16" fill="none" className="h-3 w-3"><path d="M3 8.5l3 3 7-7" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" /></svg>
                    )}
                  </button>
                </div>
              </div>
            ))}
            {resolved.length > 0 && (
              <details className="group">
                <summary className="text-[12px] text-locked cursor-pointer select-none hover:text-ink list-none flex items-center gap-1">
                  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-3.5 w-3.5 rotate-0 group-open:rotate-90 transition-transform"><path d="M6 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" /></svg>
                  {resolved.length} resolvido{resolved.length > 1 ? "s" : ""}
                </summary>
                <div className="mt-2 space-y-2">
                  {resolved.map((c) => (
                    <div key={c.id} className="rounded-[10px] border border-borda/50 bg-paper/50 p-3 opacity-60">
                      <div className="flex items-center gap-1.5 mb-1">
                        <span className="h-5 w-5 rounded-full bg-done/20 text-done text-[10px] font-bold flex items-center justify-center shrink-0">✓</span>
                        <span className="text-[12px] font-medium text-locked">{c.author_name ?? c.author_email.split("@")[0]}</span>
                      </div>
                      <p className="text-[13px] text-locked line-through leading-relaxed">{c.content}</p>
                    </div>
                  ))}
                </div>
              </details>
            )}
          </>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Compose */}
      <div className="mt-3 border-t border-borda pt-3 shrink-0">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) send(); }}
          rows={3}
          placeholder="Adicionar comentário… (Ctrl+Enter para enviar)"
          className="w-full resize-none rounded-[10px] border border-borda bg-superficie px-3 py-2.5 text-[14px] text-ink focus:border-purple outline-none transition"
        />
        <div className="flex justify-end mt-2">
          <button
            onClick={send}
            disabled={sending || !draft.trim()}
            className="inline-flex h-8 items-center gap-1.5 rounded-[8px] bg-purple px-3.5 text-[13px] font-medium text-paper hover:bg-purple/90 disabled:opacity-50 transition"
          >
            {sending ? <Spinner /> : "Enviar"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Version list ──────────────────────────────────────────────────────────────

function VersionList({
  projectId,
  sectionId,
  onRestore,
}: {
  projectId: string;
  sectionId: string;
  onRestore: (sectionId: string) => void;
}) {
  const [versions, setVersions] = useState<SectionVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [restoringId, setRestoringId] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    listSectionVersions(projectId, sectionId)
      .then((v) => { setVersions(v); setLoading(false); })
      .catch(() => setLoading(false));
  }, [projectId, sectionId]);

  async function handleRestore(versionId: string) {
    if (!confirm("Restaurar esta versão? O conteúdo atual será sobrescrito.")) return;
    setRestoringId(versionId);
    try {
      await restoreSectionVersion(projectId, sectionId, versionId);
      onRestore(sectionId);
    } finally {
      setRestoringId(null);
    }
  }

  if (loading) return <div className="flex items-center justify-center py-8 text-locked gap-2"><Spinner /> Carregando…</div>;

  if (versions.length === 0) return (
    <div className="py-8 text-center text-[14px] text-locked">
      Nenhuma versão salva ainda.<br />O histórico é criado a cada salvamento.
    </div>
  );

  return (
    <ul className="space-y-2">
      {versions.map((v, i) => (
        <li key={v.id} className="rounded-[10px] border border-borda bg-paper p-3 flex items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 mb-0.5">
              <span className="text-[12px] font-bold text-locked uppercase tracking-wider">V{versions.length - i}</span>
              <span className="text-[13px] text-ink">{new Date(v.created_at).toLocaleDateString("pt-BR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}</span>
            </div>
            <p className="text-[13px] text-locked">{v.word_count} {v.word_count === 1 ? "palavra" : "palavras"}</p>
          </div>
          <button
            onClick={() => handleRestore(v.id)}
            disabled={restoringId === v.id}
            className="shrink-0 inline-flex h-7 items-center gap-1 rounded-[7px] border border-borda px-2.5 text-[12px] font-medium text-locked hover:border-purple hover:text-purple disabled:opacity-50 transition"
          >
            {restoringId === v.id ? <Spinner /> : "Restaurar"}
          </button>
        </li>
      ))}
    </ul>
  );
}

// ── Panel ─────────────────────────────────────────────────────────────────────

export function CommentPanel({ projectId, sectionId, sectionTitle, onRestoreVersion, onClose }: Props) {
  const [tab, setTab] = useState<PanelTab>("comentarios");

  return (
    <aside className="flex flex-col w-full sm:w-[340px] shrink-0 h-full border-l border-borda bg-superficie">
      {/* Header */}
      <div className="flex items-center justify-between gap-2 px-4 py-3 border-b border-borda shrink-0">
        <div className="min-w-0">
          <p className="text-[11px] font-bold uppercase tracking-wider text-locked">Painel</p>
          {sectionTitle && <p className="text-[14px] font-medium text-ink truncate">{sectionTitle}</p>}
        </div>
        <button onClick={onClose} className="h-7 w-7 flex items-center justify-center rounded-[7px] text-locked hover:text-ink hover:bg-borda/50 transition" aria-label="Fechar painel">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" className="h-4 w-4"><path d="M4 4l8 8M12 4l-8 8" /></svg>
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-0 border-b border-borda shrink-0">
        {(["comentarios", "versoes"] as PanelTab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={[
              "flex-1 py-2.5 text-[13px] font-medium transition border-b-2",
              tab === t ? "border-purple text-purple" : "border-transparent text-locked hover:text-ink",
            ].join(" ")}
          >
            {t === "comentarios" ? "Comentários" : "Versões"}
          </button>
        ))}
      </div>

      {/* Body */}
      <div className="flex-1 overflow-hidden flex flex-col p-4 min-h-0">
        {!sectionId ? (
          <div className="flex flex-1 items-center justify-center">
            <p className="text-[14px] text-locked text-center">Selecione uma seção para ver comentários e versões.</p>
          </div>
        ) : tab === "comentarios" ? (
          <CommentThread projectId={projectId} sectionId={sectionId} />
        ) : (
          <div className="overflow-y-auto">
            <VersionList
              projectId={projectId}
              sectionId={sectionId}
              onRestore={(sid) => { onRestoreVersion?.(sid); }}
            />
          </div>
        )}
      </div>
    </aside>
  );
}
