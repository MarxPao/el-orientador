"use client";

import { useRouter } from "next/navigation";
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import {
  AdvisorMember,
  ApiError,
  api,
  CoherenceWarning,
  downloadDocx,
  getToken,
  MapNode,
  Project,
  ProjectClaim,
  Section,
  SectionComment,
} from "@/lib/api";
import { AppHeader } from "@/components/app-header";
import {
  AdvisorBubble,
  AlertBanner,
  AlertIcon,
  Button,
  CheckIcon,
  StudentCard,
} from "@/components/ui";

/**
 * Mapa de tradução de acentuação na interface (mantém inalterados os valores de enum da API).
 */
const COHERENCE_WARNING_LABELS: Record<CoherenceWarning["type"], string> = {
  secao_sem_fonte: "SEÇÃO SEM FONTE",
  referencia_orfa: "REFERÊNCIA ÓRFÃ",
  objetivo_sem_capitulo: "OBJETIVO SEM CAPÍTULO",
  conceito_nao_mencionado: "CONCEITO NÃO MENCIONADO",
  documento_sem_alegacoes: "DOCUMENTO SEM ALEGAÇÕES",
};

function formatClaimCitation(claim: ProjectClaim): string {
  const firstAuthor = claim.authors?.[0]
    ? claim.authors[0].split(" ").slice(-1)[0]
    : (claim.document_title ?? "Fonte").split(" ").slice(0, 2).join(" ");
  const yearPart = claim.year ? `, ${claim.year}` : "";
  return `(${firstAuthor}${yearPart}, p. ${claim.page_no})`;
}

function parseAnchoredComment(raw: string): { anchor: string | null; body: string } {
  const match = raw.match(/^\[Trecho em revisão:\s*"([^"]+)"\]\n?([\s\S]*)$/);
  if (!match) return { anchor: null, body: raw };
  return { anchor: match[1], body: match[2] };
}

export default function EditorView({ id }: { id: string }) {
  const router = useRouter();
  const [project, setProject] = useState<Project | null>(null);
  const [sections, setSections] = useState<Section[]>([]);
  const [selectedSectionId, setSelectedSectionId] = useState<string | null>(null);
  const [coherence, setCoherence] = useState<CoherenceWarning[]>([]);
  const [concepts, setConcepts] = useState<MapNode[]>([]);
  const [claims, setClaims] = useState<ProjectClaim[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<"saved" | "saving" | "unsaved">("saved");
  const [activeTab, setActiveTab] = useState<"coherence" | "evidence" | "comments">("coherence");
  const [newTitle, setNewTitle] = useState("");
  const [isExporting, setIsExporting] = useState(false);
  const [comments, setComments] = useState<SectionComment[]>([]);
  const [newComment, setNewComment] = useState("");
  const [anchorQuote, setAnchorQuote] = useState<string | null>(null);
  const [showCitePicker, setShowCitePicker] = useState(false);
  const [citeQuery, setCiteQuery] = useState("");
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [advisorEmail, setAdvisorEmail] = useState("");
  const [advisors, setAdvisors] = useState<AdvisorMember[]>([]);

  const activeSection = useMemo(
    () => sections.find((s) => s.id === selectedSectionId) ?? null,
    [sections, selectedSectionId]
  );

  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const refreshCoherence = useCallback(async () => {
    try {
      const data = await api<CoherenceWarning[]>(`/projects/${id}/coherence`);
      setCoherence(data);
    } catch {
      // Quiet
    }
  }, [id]);

  // Tiptap Editor initialization (Source Serif 4, corpo 18-20px, entrelinha ~1.58)
  const editor = useEditor({
    extensions: [StarterKit],
    immediatelyRender: false,
    editorProps: {
      attributes: {
        class:
          "min-h-[480px] w-full p-6 sm:p-8 font-serif-academic text-[19px] leading-[1.58] text-ink focus:outline-none",
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
            void refreshCoherence();
          })
          .catch(() => {
            setSaveStatus("unsaved");
          });
      }, 800);
    },
  });

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
      api<ProjectClaim[]>(`/projects/${id}/claims`).catch(() => [] as ProjectClaim[]),
    ])
      .then(([projData, secData, mapData, cohData, claimsData]) => {
        if (cancelled) return;
        setProject(projData);
        setSections(secData);
        setConcepts(mapData.nodes || []);
        setCoherence(cohData);
        setClaims(claimsData);
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

  useEffect(() => {
    if (!editor || !activeSection) return;
    const content = activeSection.content;
    if (content && typeof content === "object" && Object.keys(content).length > 0) {
      editor.commands.setContent(content, { emitUpdate: false });
    } else {
      editor.commands.setContent("<p></p>", { emitUpdate: false });
    }
  }, [selectedSectionId, editor, activeSection]);

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

  const filteredClaims = useMemo(() => {
    const q = citeQuery.trim().toLowerCase();
    if (!q) return claims;
    return claims.filter(
      (c) =>
        c.quote.toLowerCase().includes(q) ||
        c.statement.toLowerCase().includes(q) ||
        (c.document_title ?? "").toLowerCase().includes(q) ||
        c.concepts.some((co) => co.label.toLowerCase().includes(q))
    );
  }, [claims, citeQuery]);

  async function handleInsertClaimCitation(claim: ProjectClaim) {
    if (!editor || !activeSection) return;
    const refText = formatClaimCitation(claim);
    editor
      .chain()
      .focus()
      .insertContent(` ${refText} `)
      .run();
    setShowCitePicker(false);
    setCiteQuery("");

    // Automatically link the claim's concept to the active section
    const conceptId = claim.concepts?.[0]?.id;
    if (conceptId && !activeSection.concept_ids.includes(conceptId)) {
      const nextList = [...activeSection.concept_ids, conceptId];
      try {
        const updated = await api<Section>(
          `/projects/${id}/sections/${activeSection.id}`,
          {
            method: "PATCH",
            body: { concept_ids: nextList },
          }
        );
        setSections((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
        void refreshCoherence();
      } catch {
        // Ignore link error if already updated
      }
    }
  }

  function handleAnchorSelectionForComment() {
    if (!editor) return;
    const { from, to } = editor.state.selection;
    const selectedText = editor.state.doc.textBetween(from, to, " ").trim();
    const fallbackText = editor.getText().trim().slice(0, 140);
    const chosen = selectedText || fallbackText;
    if (chosen) {
      setAnchorQuote(chosen.slice(0, 220));
    }
    setActiveTab("comments");
  }

  async function handleAddComment(e: React.FormEvent) {
    e.preventDefault();
    if (!newComment.trim() || !selectedSectionId) return;
    const finalContent = anchorQuote
      ? `[Trecho em revisão: "${anchorQuote}"]\n${newComment.trim()}`
      : newComment.trim();
    try {
      const created = await api<SectionComment>(
        `/projects/${id}/sections/${selectedSectionId}/comments`,
        {
          method: "POST",
          body: { content: finalContent },
        }
      );
      setComments((prev) => [...prev, created]);
      setNewComment("");
      setAnchorQuote(null);
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
    <div className="min-h-screen flex flex-col bg-paper text-ink">
      <AppHeader projectId={id} />

      <main className="mx-auto w-full max-w-[1440px] flex-1 px-6 py-8 sm:px-10 flex flex-col gap-6">
        {/* Cabeçalho da tela do Editor */}
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-borda pb-5">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="font-display text-3xl sm:text-[36px] text-ink">
                Editor do manuscrito
              </h1>
              <span className="rounded-[6px] border border-borda bg-superficie px-2.5 py-0.5 text-[13px] font-bold uppercase tracking-wider text-locked">
                {project?.citation_style?.toUpperCase() ?? "ABNT"}
              </span>
            </div>
            <p className="mt-1 text-[15px] text-locked">{project?.title ?? "Carregando…"}</p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setShowInviteModal(true)}
            >
              Orientadores ({advisors.length})
            </Button>

            {/* Único botão principal roxo da tela */}
            <Button
              type="button"
              variant="primary"
              disabled={isExporting}
              onClick={handleExport}
            >
              {isExporting ? "Gerando Word…" : "Exportar DOCX (ABNT)"}
            </Button>
          </div>
        </div>

        {error && <AlertBanner variant="error">{error}</AlertBanner>}

        {/* Layout de 3 colunas */}
        <div className="grid flex-1 grid-cols-1 gap-6 lg:grid-cols-12 items-start">
          {/* Coluna Esquerda: Sumário de Seções (3 cols) */}
          <aside
            aria-label="Árvore de seções"
            className="rounded-[16px] border border-borda bg-superficie p-5 lg:col-span-3 flex flex-col gap-4"
          >
            <div className="flex items-center justify-between border-b border-borda pb-3">
              <h2 className="font-display text-lg text-ink">Sumário de seções</h2>
              <span className="rounded-[6px] bg-paper px-2.5 py-0.5 text-[13px] font-bold text-locked">
                {sections.length}
              </span>
            </div>

            <div className="space-y-2">
              {sections.map((sec) => {
                const isSelected = sec.id === selectedSectionId;
                const hasWarning = coherence.some((w) => w.section_id === sec.id);

                return (
                  <div
                    key={sec.id}
                    onClick={() => setSelectedSectionId(sec.id)}
                    className={`group flex min-h-[44px] items-center justify-between rounded-[10px] px-3 py-2 text-[15px] cursor-pointer transition border ${
                      isSelected
                        ? "border-2 border-purple bg-paper font-bold text-ink"
                        : "border-transparent text-ink hover:bg-paper/60"
                    }`}
                  >
                    <div className="flex items-center gap-2 truncate">
                      {hasWarning && (
                        <AlertIcon className="h-4 w-4 shrink-0 text-purple" />
                      )}
                      <span className="truncate">{sec.title}</span>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      {sec.concept_ids.length > 0 && (
                        <span
                          className="rounded-[6px] bg-skipped-bg px-2 py-0.5 text-[13px] font-bold text-purple"
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
                        aria-label={`Excluir seção ${sec.title}`}
                        className="opacity-0 group-hover:opacity-100 text-[14px] text-locked hover:text-ink px-1 cursor-pointer"
                        title="Excluir seção"
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>

            <form onSubmit={handleAddSection} className="border-t border-borda pt-4 space-y-2.5">
              <input
                type="text"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="Nova seção (ex: 3.1 Hipóteses)"
                className="w-full h-[44px] rounded-[10px] border border-borda bg-paper/40 px-3 text-[15px] text-ink focus:border-purple"
              />
              <Button
                type="submit"
                variant="secondary"
                disabled={!newTitle.trim()}
                className="w-full"
              >
                Adicionar seção
              </Button>
            </form>
          </aside>

          {/* Coluna Central: Área de Escrita do Manuscrito (5 cols) */}
          <section
            aria-label="Editor de texto acadêmico"
            className="flex flex-col rounded-[16px] border border-borda bg-superficie lg:col-span-5"
          >
            {/* Barra de Formatação + @Citação Verificada + Marca-Texto em Revisão */}
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-borda px-4 py-2.5 text-[15px]">
              <div className="flex flex-wrap items-center gap-1">
                <button
                  type="button"
                  onClick={() => editor?.chain().focus().toggleHeading({ level: 1 }).run()}
                  className={`min-h-[40px] rounded-[8px] px-2.5 font-bold cursor-pointer ${
                    editor?.isActive("heading", { level: 1 })
                      ? "bg-purple text-paper"
                      : "text-ink hover:bg-paper"
                  }`}
                >
                  H1
                </button>
                <button
                  type="button"
                  onClick={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()}
                  className={`min-h-[40px] rounded-[8px] px-2.5 font-bold cursor-pointer ${
                    editor?.isActive("heading", { level: 2 })
                      ? "bg-purple text-paper"
                      : "text-ink hover:bg-paper"
                  }`}
                >
                  H2
                </button>
                <button
                  type="button"
                  onClick={() => editor?.chain().focus().toggleBold().run()}
                  className={`min-h-[40px] rounded-[8px] px-2.5 font-bold cursor-pointer ${
                    editor?.isActive("bold")
                      ? "bg-purple text-paper"
                      : "text-ink hover:bg-paper"
                  }`}
                >
                  B
                </button>
                <button
                  type="button"
                  onClick={() => editor?.chain().focus().toggleItalic().run()}
                  className={`min-h-[40px] rounded-[8px] px-2.5 italic cursor-pointer ${
                    editor?.isActive("italic")
                      ? "bg-purple text-paper"
                      : "text-ink hover:bg-paper"
                  }`}
                >
                  I
                </button>
                <button
                  type="button"
                  onClick={() => editor?.chain().focus().toggleBlockquote().run()}
                  className={`min-h-[40px] rounded-[8px] px-2.5 cursor-pointer ${
                    editor?.isActive("blockquote")
                      ? "bg-purple text-paper"
                      : "text-ink hover:bg-paper"
                  }`}
                >
                  Recuo
                </button>

                {/* Botão @ Citar trecho verificado */}
                <button
                  type="button"
                  onClick={() => setShowCitePicker((prev) => !prev)}
                  className={`min-h-[40px] rounded-[8px] border px-3 text-[14px] font-bold cursor-pointer transition ${
                    showCitePicker
                      ? "border-purple bg-purple text-paper"
                      : "border-purple text-purple hover:bg-skipped-bg"
                  }`}
                >
                  @ Citar fonte ({claims.length})
                </button>

                {/* Botão Ancorar trecho com Marca-Texto Laranja */}
                <button
                  type="button"
                  onClick={handleAnchorSelectionForComment}
                  title="Selecionar trecho do texto para ancorar comentário ou pergunta"
                  className="min-h-[40px] rounded-[8px] bg-orange px-3 text-[14px] font-bold text-ink cursor-pointer hover:opacity-95"
                >
                  Grifar trecho
                </button>
              </div>

              <div className="flex items-center gap-3 text-[14px] text-locked">
                <span className="truncate max-w-[140px]">
                  {activeSection ? activeSection.title : "Nenhuma seção"}
                </span>
                <span
                  className={`inline-flex items-center gap-1 font-bold ${
                    saveStatus === "saved"
                      ? "text-done"
                      : saveStatus === "saving"
                      ? "text-purple"
                      : "text-locked"
                  }`}
                >
                  {saveStatus === "saved"
                    ? "Salvo"
                    : saveStatus === "saving"
                    ? "Salvando…"
                    : "Não salvo"}
                </span>
              </div>
            </div>

            {/* Gaveta de Inserção de @Citação Verificada */}
            {showCitePicker && (
              <div className="border-b border-borda bg-paper p-4 space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[13px] font-bold uppercase tracking-wider text-purple">
                    Inserir citação apoiada em trecho literal verificado
                  </span>
                  <button
                    type="button"
                    onClick={() => setShowCitePicker(false)}
                    className="text-[14px] font-bold text-locked hover:text-ink cursor-pointer"
                  >
                    Fechar ✕
                  </button>
                </div>

                <input
                  type="search"
                  value={citeQuery}
                  onChange={(e) => setCiteQuery(e.target.value)}
                  placeholder="Buscar por conceito, autor, documento ou palavra do trecho…"
                  className="w-full h-[42px] rounded-[10px] border border-borda bg-superficie px-3.5 text-[15px] text-ink"
                />

                {filteredClaims.length === 0 ? (
                  <p className="text-[14px] text-locked py-2">
                    Nenhum trecho verificado encontrado para este filtro.
                  </p>
                ) : (
                  <ul className="max-h-[240px] overflow-y-auto space-y-2 pr-1">
                    {filteredClaims.map((claim) => (
                      <li
                        key={claim.id}
                        className="rounded-[10px] border border-borda bg-superficie p-3 space-y-1.5"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="text-[14px] font-bold text-purple">
                            {formatClaimCitation(claim)} ·{" "}
                            {claim.concepts.map((c) => c.label).join(", ")}
                          </span>
                          <button
                            type="button"
                            onClick={() => void handleInsertClaimCitation(claim)}
                            className="rounded-[8px] border border-purple px-2.5 py-1 text-[13px] font-bold text-purple hover:bg-skipped-bg cursor-pointer"
                          >
                            Inserir citação
                          </button>
                        </div>
                        <blockquote className="font-serif-academic text-[15px] leading-snug text-ink">
                          <mark className="mark-orange">{claim.quote}</mark>
                        </blockquote>
                        <p className="text-[13px] text-locked">
                          {claim.document_title ?? "Documento"} · página {claim.page_no}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {/* Corpo do Manuscrito */}
            <div className="flex-1 overflow-y-auto">
              {activeSection ? (
                <EditorContent editor={editor} />
              ) : (
                <div className="flex h-[480px] items-center justify-center p-8 text-[15px] text-locked">
                  Selecione ou crie uma seção à esquerda para redigir.
                </div>
              )}
            </div>
          </section>

          {/* Coluna Direita: Coerência, Conceitos e Comentários (4 cols) */}
          <aside
            aria-label="Painel de coerência e conceitos"
            className="rounded-[16px] border border-borda bg-superficie p-5 lg:col-span-4 flex flex-col gap-4"
          >
            {/* Seletor de Abas */}
            <div className="flex flex-wrap border-b border-borda gap-2 text-[15px]">
              <button
                type="button"
                onClick={() => setActiveTab("coherence")}
                className={`min-h-[44px] px-3 font-bold transition cursor-pointer border-b-2 ${
                  activeTab === "coherence"
                    ? "border-purple text-purple"
                    : "border-transparent text-locked hover:text-ink"
                }`}
              >
                Coerência ({coherence.length})
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("evidence")}
                className={`min-h-[44px] px-3 font-bold transition cursor-pointer border-b-2 ${
                  activeTab === "evidence"
                    ? "border-purple text-purple"
                    : "border-transparent text-locked hover:text-ink"
                }`}
              >
                Conceitos ({concepts.length})
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("comments")}
                className={`min-h-[44px] px-3 font-bold transition cursor-pointer border-b-2 ${
                  activeTab === "comments"
                    ? "border-purple text-purple"
                    : "border-transparent text-locked hover:text-ink"
                }`}
              >
                Comentários ({comments.length})
              </button>
            </div>

            {/* Aba: Coerência */}
            {activeTab === "coherence" && (
              <div className="space-y-3 text-[15px]">
                {coherence.length === 0 ? (
                  <div className="flex items-start gap-3 rounded-[12px] border border-done bg-paper/40 p-4 text-ink">
                    <CheckIcon className="mt-0.5 h-5 w-5 shrink-0 text-done" />
                    <span>
                      Nenhum aviso de coerência identificado. Estrutura acadêmica consistente.
                    </span>
                  </div>
                ) : (
                  coherence.map((warn, i) => (
                    <div
                      key={i}
                      className={`rounded-[12px] p-4 space-y-2 ${
                        warn.severity === "warning"
                          ? "border-2 border-dotted border-purple bg-paper/50 text-ink"
                          : "border border-borda bg-paper/30 text-ink"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <AlertIcon className="h-4 w-4 shrink-0 text-purple" />
                        <span className="text-[13px] font-bold uppercase tracking-wider text-purple">
                          {COHERENCE_WARNING_LABELS[warn.type] ??
                            warn.type.replace(/_/g, " ").toUpperCase()}
                        </span>
                      </div>
                      <p className="text-[15px] leading-relaxed text-ink">{warn.message}</p>
                    </div>
                  ))
                )}
              </div>
            )}

            {/* Aba: Conceitos / Evidências com trechos literais */}
            {activeTab === "evidence" && (
              <div className="space-y-3 text-[15px] max-h-[520px] overflow-y-auto pr-1">
                <p className="text-[14px] text-locked">
                  Conceitos do mapa e seus trechos literais verificados para a seção{" "}
                  <strong>{activeSection?.title ?? "ativa"}</strong>:
                </p>
                {concepts.map((concept) => {
                  const isLinked = activeSection?.concept_ids.includes(concept.id) ?? false;
                  const conceptClaims = claims.filter((c) =>
                    c.concepts.some((co) => co.id === concept.id)
                  );
                  return (
                    <div
                      key={concept.id}
                      className={`rounded-[12px] p-3.5 transition border space-y-2.5 ${
                        isLinked
                          ? "border-2 border-purple bg-paper/60 text-ink"
                          : "border-borda bg-superficie text-ink"
                      }`}
                    >
                      <label className="flex min-h-[36px] items-center justify-between cursor-pointer">
                        <div className="flex items-center gap-2.5 truncate">
                          <input
                            type="checkbox"
                            checked={isLinked}
                            onChange={() => void toggleConceptLink(concept.id)}
                            className="h-4 w-4 accent-purple"
                          />
                          <span className="font-bold truncate">{concept.label}</span>
                        </div>
                        <span className="text-[13px] font-medium text-locked shrink-0">
                          {concept.n_claims} citação(ões)
                        </span>
                      </label>

                      {conceptClaims.length > 0 && (
                        <div className="space-y-2 border-t border-borda pt-2.5">
                          {conceptClaims.map((cl) => (
                            <div
                              key={cl.id}
                              className="rounded-[8px] border border-borda bg-superficie p-2.5 space-y-1.5"
                            >
                              <blockquote className="font-serif-academic text-[14px] leading-snug text-ink">
                                <mark className="mark-orange">{cl.quote}</mark>
                              </blockquote>
                              <div className="flex items-center justify-between gap-2 text-[13px]">
                                <span className="text-locked truncate">
                                  {cl.document_title ?? "Documento"} · p. {cl.page_no}
                                </span>
                                <button
                                  type="button"
                                  onClick={() => void handleInsertClaimCitation(cl)}
                                  className="shrink-0 font-bold text-purple underline cursor-pointer"
                                >
                                  Citar no texto
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {/* Aba: Comentários (Orientador em balão roxo, Aluno em cartão branco, com trecho ancorado em laranja) */}
            {activeTab === "comments" && (
              <div className="flex flex-col justify-between gap-4 text-[15px]">
                <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
                  {comments.length === 0 ? (
                    <p className="text-[15px] text-locked italic">
                      Nenhum comentário nesta seção. Orientadores e alunos podem registrar observações aqui.
                    </p>
                  ) : (
                    comments.map((comment, idx) => {
                      const isAdvisor =
                        advisors.some((a) => a.advisor_email === comment.author_email) ||
                        idx === 0;
                      const authorLabel = isAdvisor
                        ? `Orientador · ${comment.author_name || comment.author_email}`
                        : `Aluno · ${comment.author_name || comment.author_email}`;
                      const parsed = parseAnchoredComment(comment.content);

                      return (
                        <div
                          key={comment.id}
                          className={comment.resolved ? "opacity-65" : ""}
                        >
                          {parsed.anchor && (
                            <div className="mb-1.5 rounded-t-[10px] border border-b-0 border-borda bg-paper px-3 py-2 text-[14px]">
                              <span className="block text-[12px] font-bold uppercase tracking-wider text-locked">
                                Trecho em trabalho:
                              </span>
                              <mark className="mark-orange font-serif-academic text-[15px]">
                                “{parsed.anchor}”
                              </mark>
                            </div>
                          )}

                          {isAdvisor ? (
                            <AdvisorBubble label={authorLabel}>
                              <p className="whitespace-pre-wrap">{parsed.body}</p>
                              <div className="mt-2 flex items-center justify-between text-[13px] text-paper/85">
                                <span>{comment.resolved ? "Resolvido" : "Em aberto"}</span>
                                <button
                                  type="button"
                                  onClick={() =>
                                    void toggleCommentResolved(comment.id, comment.resolved)
                                  }
                                  className="underline cursor-pointer"
                                >
                                  {comment.resolved ? "Reabrir" : "Marcar como resolvido"}
                                </button>
                              </div>
                            </AdvisorBubble>
                          ) : (
                            <StudentCard label={authorLabel}>
                              <p className="whitespace-pre-wrap">{parsed.body}</p>
                              <div className="mt-2 flex items-center justify-between text-[13px] text-locked">
                                <span>{comment.resolved ? "Resolvido" : "Em aberto"}</span>
                                <button
                                  type="button"
                                  onClick={() =>
                                    void toggleCommentResolved(comment.id, comment.resolved)
                                  }
                                  className="text-purple underline cursor-pointer"
                                >
                                  {comment.resolved ? "Reabrir" : "Marcar como resolvido"}
                                </button>
                              </div>
                            </StudentCard>
                          )}
                        </div>
                      );
                    })
                  )}
                </div>

                {/* Formulário de novo comentário */}
                <form
                  onSubmit={handleAddComment}
                  className="border-t border-borda pt-4 flex flex-col gap-3"
                >
                  {anchorQuote && (
                    <div className="flex items-start justify-between gap-2 rounded-[10px] border border-borda bg-paper p-2.5 text-[14px]">
                      <div>
                        <span className="block text-[12px] font-bold uppercase tracking-wider text-locked">
                          Ancorado no trecho:
                        </span>
                        <mark className="mark-orange font-serif-academic">“{anchorQuote}”</mark>
                      </div>
                      <button
                        type="button"
                        onClick={() => setAnchorQuote(null)}
                        className="text-[13px] font-bold text-locked hover:text-ink cursor-pointer"
                      >
                        ✕
                      </button>
                    </div>
                  )}

                  <textarea
                    rows={2}
                    value={newComment}
                    onChange={(e) => setNewComment(e.target.value)}
                    placeholder="Escreva uma resposta ou observação nesta seção…"
                    className="w-full resize-none rounded-[10px] border border-borda bg-paper/40 p-3 text-[15px] text-ink focus:border-purple"
                  />
                  <Button
                    type="submit"
                    variant="secondary"
                    disabled={!newComment.trim()}
                    className="w-full"
                  >
                    Enviar comentário
                  </Button>
                </form>
              </div>
            )}
          </aside>
        </div>

        {/* Modal de Convite ao Orientador */}
        {showInviteModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/60 p-4">
            <div
              role="dialog"
              aria-modal="true"
              className="w-full max-w-md rounded-[16px] border border-borda bg-paper p-6 shadow-lg space-y-4"
            >
              <div className="flex items-center justify-between border-b border-borda pb-3">
                <h3 className="font-display text-xl text-ink">Orientadores do projeto</h3>
                <button
                  type="button"
                  onClick={() => setShowInviteModal(false)}
                  aria-label="Fechar"
                  className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-[10px] text-ink hover:bg-borda/40 cursor-pointer"
                >
                  ✕
                </button>
              </div>

              {advisors.length > 0 && (
                <div className="space-y-2 text-[15px]">
                  <span className="text-[13px] font-bold uppercase tracking-wider text-locked">
                    Orientadores convidados:
                  </span>
                  <ul className="divide-y divide-borda rounded-[10px] border border-borda bg-superficie">
                    {advisors.map((adv) => (
                      <li
                        key={adv.advisor_email}
                        className="flex items-center justify-between p-3 text-[15px]"
                      >
                        <span className="font-medium text-ink">{adv.advisor_email}</span>
                        <span className="text-[13px] text-locked">Comenta no texto</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <form onSubmit={handleInviteAdvisor} className="space-y-3 pt-2">
                <label className="block text-[15px] font-medium text-ink">
                  Convidar novo orientador por e-mail
                  <input
                    type="email"
                    required
                    value={advisorEmail}
                    onChange={(e) => setAdvisorEmail(e.target.value)}
                    placeholder="orientador@universidade.br"
                    className="mt-1.5 w-full h-[46px] rounded-[10px] border border-borda bg-superficie px-3.5 text-[15px] text-ink"
                  />
                </label>

                <Button
                  type="submit"
                  variant="secondary"
                  disabled={!advisorEmail.trim()}
                  className="w-full"
                >
                  Convidar orientador
                </Button>

                <p className="text-[14px] text-locked leading-relaxed">
                  O orientador terá acesso à árvore de progresso, mapa de conhecimento, relatórios e poderá comentar nas seções do manuscrito.
                </p>
              </form>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
