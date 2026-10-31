"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import {
  ApiError,
  api,
  CoherenceWarning,
  downloadDocx,
  getToken,
  MapNode,
  Project,
  Section,
  SectionComment,
  AdvisorMember,
} from "@/lib/api";

export default function EditorView({ id }: { id: string }) {
  const router = useRouter();
  const [project, setProject] = useState<Project | null>(null);
  const [sections, setSections] = useState<Section[]>([]);
  const [selectedSectionId, setSelectedSectionId] = useState<string | null>(null);
  const [coherence, setCoherence] = useState<CoherenceWarning[]>([]);
  const [concepts, setConcepts] = useState<MapNode[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<"saved" | "saving" | "unsaved">("saved");
  const [activeTab, setActiveTab] = useState<"coherence" | "evidence" | "comments">("coherence");
  const [newTitle, setNewTitle] = useState("");
  const [isExporting, setIsExporting] = useState(false);
  const [comments, setComments] = useState<SectionComment[]>([]);
  const [newComment, setNewComment] = useState("");
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [advisorEmail, setAdvisorEmail] = useState("");
  const [advisors, setAdvisors] = useState<AdvisorMember[]>([]);

  // Selected section object
  const activeSection = useMemo(
    () => sections.find((s) => s.id === selectedSectionId) ?? null,
    [sections, selectedSectionId]
  );

  // Ref to keep track of current saving timeout
  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Tiptap Editor initialization
  const editor = useEditor({
    extensions: [StarterKit],
    immediatelyRender: false,
    editorProps: {
      attributes: {
        class:
          "min-h-[450px] w-full p-6 font-serif-academic text-base leading-relaxed text-ink focus:outline-none",
      },
    },
    onUpdate: ({ editor: ed }) => {
      setSaveStatus("unsaved");
      if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
      saveTimeoutRef.current = setTimeout(() => {
        if (!selectedSectionId) return;
        const jsonContent = ed.getJSON();
        setSaveStatus("saving");
        api<Section>(`/projects/${id}/sections/${selectedSectionId}`, {
          method: "PATCH",
          body: { content: jsonContent },
        })
          .then((updated) => {
            setSections((prev) =>
              prev.map((s) => (s.id === updated.id ? { ...s, content: updated.content } : s))
            );
            setSaveStatus("saved");
            // Refresh coherence checks quietly
            void refreshCoherence();
          })
          .catch(() => {
            setSaveStatus("unsaved");
          });
      }, 800);
    },
  });

  // Load project, sections, concepts, and coherence
  const refreshCoherence = useCallback(async () => {
    try {
      const data = await api<CoherenceWarning[]>(`/projects/${id}/coherence`);
      setCoherence(data);
    } catch {
      // Quiet
    }
  }, [id]);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/entrar");
      return;
    }
    let cancelled = false;

    Promise.all([
      api<Project>(`/projects/${id}`),
      api<Section[]>(`/projects/${id}/sections`),
      api<{ nodes: MapNode[] }>(`/projects/${id}/map`),
      api<CoherenceWarning[]>(`/projects/${id}/coherence`),
    ])
      .then(([projData, secData, mapData, cohData]) => {
        if (cancelled) return;
        setProject(projData);
        setSections(secData);
        setConcepts(mapData.nodes || []);
        setCoherence(cohData);
        if (secData.length > 0 && !selectedSectionId) {
          setSelectedSectionId(secData[0].id);
        }
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) return router.replace("/entrar");
        setError(err instanceof Error ? err.message : "Erro ao carregar dados do editor.");
      });

    return () => {
      cancelled = true;
    };
  }, [id, router, selectedSectionId]);

  // Synchronize editor content when selected section changes
  useEffect(() => {
    if (!editor || !activeSection) return;
    const content = activeSection.content;
    if (content && typeof content === "object" && Object.keys(content).length > 0) {
      editor.commands.setContent(content, { emitUpdate: false });
    } else {
      editor.commands.setContent("<p></p>", { emitUpdate: false });
    }
  }, [selectedSectionId, editor, activeSection]);

  // Load comments when active section changes
  useEffect(() => {
    if (!selectedSectionId) return;
    let cancelled = false;
    api<SectionComment[]>(`/projects/${id}/sections/${selectedSectionId}/comments`)
      .then((data) => {
        if (!cancelled) setComments(data);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [id, selectedSectionId]);

  // Load advisors
  useEffect(() => {
    let cancelled = false;
    api<AdvisorMember[]>(`/projects/${id}/advisors`)
      .then((data) => {
        if (!cancelled) setAdvisors(data);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [id]);

  async function handleAddComment(e: React.FormEvent) {
    e.preventDefault();
    if (!newComment.trim() || !selectedSectionId) return;
    try {
      const created = await api<SectionComment>(
        `/projects/${id}/sections/${selectedSectionId}/comments`,
        {
          method: "POST",
          body: { content: newComment.trim() },
        }
      );
      setComments((prev) => [...prev, created]);
      setNewComment("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao adicionar comentário.");
    }
  }

  async function toggleCommentResolved(commentId: string, currentResolved: boolean) {
    if (!selectedSectionId) return;
    try {
      const updated = await api<SectionComment>(
        `/projects/${id}/sections/${selectedSectionId}/comments/${commentId}`,
        {
          method: "PATCH",
          body: { resolved: !currentResolved },
        }
      );
      setComments((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao atualizar comentário.");
    }
  }

  async function handleInviteAdvisor(e: React.FormEvent) {
    e.preventDefault();
    if (!advisorEmail.trim()) return;
    try {
      const invited = await api<AdvisorMember>(`/projects/${id}/advisors`, {
        method: "POST",
        body: { advisor_email: advisorEmail.trim(), can_comment: true },
      });
      setAdvisors((prev) => [
        ...prev.filter((a) => a.advisor_email !== invited.advisor_email),
        invited,
      ]);
      setAdvisorEmail("");
      setShowInviteModal(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao convidar orientador.");
    }
  }

  // Create new section
  async function handleAddSection(e: React.FormEvent) {
    e.preventDefault();
    if (!newTitle.trim()) return;
    try {
      const nextPos = sections.length;
      const created = await api<Section>(`/projects/${id}/sections`, {
        method: "POST",
        body: {
          title: newTitle.trim(),
          position: nextPos,
          content: { type: "doc", content: [] },
        },
      });
      setSections((prev) => [...prev, created]);
      setSelectedSectionId(created.id);
      setNewTitle("");
      void refreshCoherence();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao criar seção.");
    }
  }

  // Delete section
  async function handleDeleteSection(sectionId: string) {
    if (!confirm("Tem certeza que deseja excluir esta seção?")) return;
    try {
      await api(`/projects/${id}/sections/${sectionId}`, { method: "DELETE" });
      const remaining = sections.filter((s) => s.id !== sectionId);
      setSections(remaining);
      if (selectedSectionId === sectionId) {
        setSelectedSectionId(remaining[0]?.id ?? null);
      }
      void refreshCoherence();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao excluir seção.");
    }
  }

  // Toggle concept link
  async function toggleConceptLink(conceptId: string) {
    if (!activeSection) return;
    const current = new Set(activeSection.concept_ids);
    if (current.has(conceptId)) {
      current.delete(conceptId);
    } else {
      current.add(conceptId);
    }
    const nextList = Array.from(current);
    try {
      const updated = await api<Section>(`/projects/${id}/sections/${activeSection.id}`, {
        method: "PATCH",
        body: { concept_ids: nextList },
      });
      setSections((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
      void refreshCoherence();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao vincular conceito.");
    }
  }

  // Export DOCX
  async function handleExport() {
    setIsExporting(true);
    try {
      await downloadDocx(id, `${project?.title || "trabalho"}.docx`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao exportar DOCX.");
    } finally {
      setIsExporting(false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-[1600px] px-6 py-6 flex flex-col min-h-screen">
      {/* Top Header */}
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-ink/10 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-serif-academic text-2xl font-bold text-ink">Editor do Manuscrito</h1>
            <span className="rounded bg-ink/10 px-2 py-0.5 text-[11px] font-medium text-ink/70">
              ABNT
            </span>
          </div>
          <p className="mt-0.5 text-xs text-ink/60">{project?.title ?? "Carregando…"}</p>
        </div>

        <div className="flex items-center gap-4 text-xs">
          <Link href={`/projetos/${id}/relatorio`} className="text-available underline">
            Relatório de Progresso
          </Link>
          <button
            type="button"
            onClick={() => setShowInviteModal(true)}
            className="text-ink/70 hover:text-ink underline"
          >
            Orientadores ({advisors.length})
          </button>
          <Link href={`/projetos/${id}/arvore`} className="text-ink/70 hover:text-ink underline">
            Árvore de Progresso
          </Link>
          <Link href={`/projetos/${id}/mapa`} className="text-ink/70 hover:text-ink underline">
            Mapa de Conhecimento
          </Link>
          <Link href="/projetos" className="text-ink/70 hover:text-ink underline">
            Voltar
          </Link>
          <button
            type="button"
            disabled={isExporting}
            onClick={handleExport}
            className="rounded bg-ink px-3 py-1.5 font-medium text-white hover:bg-ink/90 disabled:opacity-50"
          >
            {isExporting ? "Gerando Word…" : "Exportar DOCX (ABNT)"}
          </button>
        </div>
      </header>

      {error && (
        <p role="alert" className="mt-3 text-xs text-danger">
          {error}
        </p>
      )}

      {/* 3-Column Layout */}
      <div className="mt-4 grid flex-1 grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Left Column: Section Tree (3 cols) */}
        <aside
          aria-label="Árvore de seções"
          className="rounded-lg border border-ink/15 bg-paper/40 p-4 lg:col-span-3 flex flex-col"
        >
          <div className="flex items-center justify-between border-b border-ink/10 pb-2">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-ink/70">
              Sumário de Seções
            </h2>
            <span className="text-[11px] text-ink/50">{sections.length}</span>
          </div>

          <div className="mt-3 flex-1 space-y-1.5 overflow-y-auto">
            {sections.map((sec) => {
              const isSelected = sec.id === selectedSectionId;
              const hasWarning = coherence.some((w) => w.section_id === sec.id);

              return (
                <div
                  key={sec.id}
                  onClick={() => setSelectedSectionId(sec.id)}
                  className={`group flex items-center justify-between rounded p-2 text-xs cursor-pointer transition ${
                    isSelected
                      ? "bg-white font-medium shadow-sm ring-1 ring-ink/20 text-ink"
                      : "text-ink/70 hover:bg-white/60 hover:text-ink"
                  }`}
                >
                  <div className="flex items-center gap-1.5 truncate">
                    {hasWarning && (
                      <span className="h-1.5 w-1.5 rounded-full bg-gap shrink-0" title="Alerta de coerência" />
                    )}
                    <span className="truncate">{sec.title}</span>
                  </div>

                  <div className="flex items-center gap-2">
                    {sec.concept_ids.length > 0 && (
                      <span
                        className="rounded bg-available/10 px-1.5 py-0.2 text-[10px] text-available font-medium"
                        title={`${sec.concept_ids.length} conceitos vinculados`}
                      >
                        {sec.concept_ids.length}
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        void handleDeleteSection(sec.id);
                      }}
                      className="opacity-0 group-hover:opacity-100 text-[10px] text-ink/40 hover:text-gap"
                      title="Excluir seção"
                    >
                      ✕
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          <form onSubmit={handleAddSection} className="mt-3 border-t border-ink/10 pt-3 flex gap-2">
            <input
              type="text"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              placeholder="Nova seção (ex: 3.1 Hipóteses)"
              className="flex-1 rounded border border-ink/20 px-2.5 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-ink"
            />
            <button
              type="submit"
              disabled={!newTitle.trim()}
              className="rounded bg-ink px-2.5 py-1 text-xs font-medium text-white disabled:opacity-50"
            >
              +
            </button>
          </form>
        </aside>

        {/* Center Column: Text Editor (6 cols) */}
        <section
          aria-label="Editor de texto acadêmico"
          className="flex flex-col rounded-lg border border-ink/15 bg-white lg:col-span-6 shadow-sm"
        >
          {/* Editor Header / Formatting Toolbar */}
          <div className="flex flex-wrap items-center justify-between border-b border-ink/10 px-4 py-2 text-xs">
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => editor?.chain().focus().toggleHeading({ level: 1 }).run()}
                className={`rounded px-2 py-1 font-semibold ${
                  editor?.isActive("heading", { level: 1 }) ? "bg-ink/15 text-ink" : "text-ink/70 hover:bg-paper"
                }`}
              >
                H1
              </button>
              <button
                type="button"
                onClick={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()}
                className={`rounded px-2 py-1 font-semibold ${
                  editor?.isActive("heading", { level: 2 }) ? "bg-ink/15 text-ink" : "text-ink/70 hover:bg-paper"
                }`}
              >
                H2
              </button>
              <button
                type="button"
                onClick={() => editor?.chain().focus().toggleBold().run()}
                className={`rounded px-2 py-1 font-bold ${
                  editor?.isActive("bold") ? "bg-ink/15 text-ink" : "text-ink/70 hover:bg-paper"
                }`}
              >
                B
              </button>
              <button
                type="button"
                onClick={() => editor?.chain().focus().toggleItalic().run()}
                className={`rounded px-2 py-1 italic ${
                  editor?.isActive("italic") ? "bg-ink/15 text-ink" : "text-ink/70 hover:bg-paper"
                }`}
              >
                I
              </button>
              <button
                type="button"
                onClick={() => editor?.chain().focus().toggleBulletList().run()}
                className={`rounded px-2 py-1 ${
                  editor?.isActive("bulletList") ? "bg-ink/15 text-ink" : "text-ink/70 hover:bg-paper"
                }`}
              >
                Lista
              </button>
              <button
                type="button"
                onClick={() => editor?.chain().focus().toggleBlockquote().run()}
                className={`rounded px-2 py-1 ${
                  editor?.isActive("blockquote") ? "bg-ink/15 text-ink" : "text-ink/70 hover:bg-paper"
                }`}
              >
                Citação
              </button>
            </div>

            <div className="flex items-center gap-3 text-[11px] text-ink/60">
              <span>{activeSection ? activeSection.title : "Nenhuma seção"}</span>
              <span
                className={`font-medium ${
                  saveStatus === "saved"
                    ? "text-done"
                    : saveStatus === "saving"
                    ? "text-available"
                    : "text-gap"
                }`}
              >
                {saveStatus === "saved" ? "● Salvo" : saveStatus === "saving" ? "Salvando…" : "Não salvo"}
              </span>
            </div>
          </div>

          {/* Editor Body */}
          <div className="flex-1 overflow-y-auto">
            {activeSection ? (
              <EditorContent editor={editor} />
            ) : (
              <div className="flex h-full items-center justify-center p-8 text-xs text-ink/50">
                Selecione ou crie uma seção à esquerda para redigir.
              </div>
            )}
          </div>
        </section>

        {/* Right Column: Coherence & Evidence (3 cols) */}
        <aside
          aria-label="Painel de coerência e conceitos"
          className="rounded-lg border border-ink/15 bg-paper/40 p-4 lg:col-span-3 flex flex-col"
        >
          {/* Tab Selector */}
          <div className="flex border-b border-ink/10 pb-2 gap-2 text-xs">
            <button
              type="button"
              onClick={() => setActiveTab("coherence")}
              className={`pb-1 font-semibold transition ${
                activeTab === "coherence"
                  ? "border-b-2 border-ink text-ink"
                  : "text-ink/60 hover:text-ink"
              }`}
            >
              Coerência ({coherence.length})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("evidence")}
              className={`pb-1 font-semibold transition ${
                activeTab === "evidence"
                  ? "border-b-2 border-ink text-ink"
                  : "text-ink/60 hover:text-ink"
              }`}
            >
              Conceitos ({concepts.length})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("comments")}
              className={`pb-1 font-semibold transition ${
                activeTab === "comments"
                  ? "border-b-2 border-ink text-ink"
                  : "text-ink/60 hover:text-ink"
              }`}
            >
              Comentários ({comments.length})
            </button>
          </div>

          {/* Coherence Tab Content */}
          {activeTab === "coherence" && (
            <div className="mt-3 flex-1 overflow-y-auto space-y-2.5 text-xs">
              {coherence.length === 0 ? (
                <div className="rounded border border-done/30 bg-done/5 p-3 text-done text-[11px]">
                  Nenhum aviso de coerência identificado. Estrutura acadêmica consistente!
                </div>
              ) : (
                coherence.map((warn, i) => (
                  <div
                    key={i}
                    className={`rounded border p-2.5 text-[11px] leading-relaxed ${
                      warn.severity === "warning"
                        ? "border-gap/40 bg-gap/5 text-ink"
                        : "border-ink/20 bg-white text-ink/80"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span
                        className={`text-[9px] font-semibold uppercase tracking-wider ${
                          warn.severity === "warning" ? "text-gap" : "text-ink/60"
                        }`}
                      >
                        {warn.type.replace(/_/g, " ")}
                      </span>
                    </div>
                    <p>{warn.message}</p>
                  </div>
                ))
              )}
            </div>
          )}

          {/* Evidence / Concepts Tab Content */}
          {activeTab === "evidence" && (
            <div className="mt-3 flex-1 overflow-y-auto space-y-2 text-xs">
              <p className="text-[11px] text-ink/60 mb-2">
                Conceitos do mapa. Marque para vincular à seção ativa (&quot;{activeSection?.title}&quot;):
              </p>
              {concepts.map((concept) => {
                const isLinked = activeSection?.concept_ids.includes(concept.id);
                return (
                  <label
                    key={concept.id}
                    className={`flex items-center justify-between rounded p-2 text-xs cursor-pointer transition border ${
                      isLinked
                        ? "border-available/40 bg-available/5 text-ink font-medium"
                        : "border-ink/10 bg-white text-ink/70 hover:bg-white"
                    }`}
                  >
                    <div className="flex items-center gap-2 truncate">
                      <input
                        type="checkbox"
                        checked={isLinked}
                        onChange={() => void toggleConceptLink(concept.id)}
                      />
                      <span className="truncate">{concept.label}</span>
                    </div>
                    <span className="text-[10px] text-ink/50 shrink-0">
                      {concept.n_claims} citação(ões)
                    </span>
                  </label>
                );
              })}
            </div>
          )}

          {/* Comments Tab Content */}
          {activeTab === "comments" && (
            <div className="mt-3 flex-1 flex flex-col justify-between text-xs">
              <div className="space-y-2.5 overflow-y-auto flex-1 pr-1">
                {comments.length === 0 ? (
                  <p className="text-[11px] text-ink/50 italic">
                    Nenhum comentário nesta seção. Orientadores e alunos podem registrar observações aqui.
                  </p>
                ) : (
                  comments.map((comment) => (
                    <div
                      key={comment.id}
                      className={`rounded border p-2.5 space-y-1.5 transition ${
                        comment.resolved
                          ? "border-ink/10 bg-paper/30 opacity-60"
                          : "border-ink/20 bg-white shadow-xs"
                      }`}
                    >
                      <div className="flex items-center justify-between text-[10px] text-ink/50">
                        <span className="font-semibold text-ink/70">
                          {comment.author_name || comment.author_email}
                        </span>
                        <span>{comment.resolved ? "Resolvido" : "Pendente"}</span>
                      </div>
                      <p className="text-[11px] text-ink leading-relaxed whitespace-pre-wrap">
                        {comment.content}
                      </p>
                      <div className="flex items-center justify-end pt-1">
                        <button
                          type="button"
                          onClick={() => void toggleCommentResolved(comment.id, comment.resolved)}
                          className="text-[10px] text-ink/60 hover:text-ink underline"
                        >
                          {comment.resolved ? "Reabrir comentário" : "Marcar como resolvido"}
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>

              {/* Add comment form */}
              <form onSubmit={handleAddComment} className="mt-3 border-t border-ink/10 pt-2 flex flex-col gap-2">
                <textarea
                  rows={2}
                  value={newComment}
                  onChange={(e) => setNewComment(e.target.value)}
                  placeholder="Escreva um comentário ou feedback para o aluno…"
                  className="w-full resize-none rounded border border-ink/20 p-2 text-xs focus:outline-none focus:ring-1 focus:ring-ink"
                />
                <button
                  type="submit"
                  disabled={!newComment.trim()}
                  className="rounded bg-ink py-1.5 font-medium text-white text-xs disabled:opacity-50"
                >
                  Enviar Comentário
                </button>
              </form>
            </div>
          )}
        </aside>
      </div>

      {/* Invite Advisor Modal */}
      {showInviteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-lg border border-ink/20 bg-white p-5 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-ink/10 pb-3">
              <h3 className="font-serif-academic font-bold text-base text-ink">
                Orientadores do Projeto
              </h3>
              <button
                type="button"
                onClick={() => setShowInviteModal(false)}
                className="text-ink/50 hover:text-ink text-sm"
              >
                ✕
              </button>
            </div>

            {advisors.length > 0 && (
              <div className="space-y-1.5 text-xs">
                <span className="font-semibold text-ink/70 text-[11px] uppercase tracking-wider">
                  Orientadores convidados:
                </span>
                <ul className="divide-y divide-ink/10 rounded border border-ink/10">
                  {advisors.map((adv) => (
                    <li key={adv.advisor_email} className="flex items-center justify-between p-2">
                      <span className="font-medium text-ink">{adv.advisor_email}</span>
                      <span className="text-[10px] text-ink/50">Permissão de comentários</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <form onSubmit={handleInviteAdvisor} className="space-y-2 text-xs pt-2">
              <label className="block text-[11px] font-semibold text-ink/70">
                Convidar novo orientador:
              </label>
              <div className="flex gap-2">
                <input
                  type="email"
                  required
                  value={advisorEmail}
                  onChange={(e) => setAdvisorEmail(e.target.value)}
                  placeholder="orientador@universidade.br"
                  className="flex-1 rounded border border-ink/20 px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-ink"
                />
                <button
                  type="submit"
                  disabled={!advisorEmail.trim()}
                  className="rounded bg-ink px-3 py-1.5 font-medium text-white disabled:opacity-50"
                >
                  Convidar
                </button>
              </div>
              <p className="text-[10px] text-ink/50 leading-relaxed">
                O orientador terá acesso visual à árvore de progresso, mapa de conhecimento, relatórios
                e poderá comentar diretamente nas seções do texto.
              </p>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}
