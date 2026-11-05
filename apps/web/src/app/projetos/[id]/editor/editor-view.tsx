"use client";

import { useRouter } from "next/navigation";
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import {
  AdvisorMember,
  AiAssistResponse,
  ApiError,
  api,
  AuthorshipPrism,
  CoherenceWarning,
  downloadDocx,
  getToken,
  MapNode,
  Project,
  ParaphraseSearchResponse,
  ParaphraseSuggestion,
  ProjectAuthorshipResponse,
  ProjectClaim,
  Section,
  SectionComment,
  SectionVersion,
  listSectionVersions,
  restoreSectionVersion,
  TextAnalysisWorkspace,
  TextCompareResult,
} from "@/lib/api";
import { AppHeader } from "@/components/app-header";
import {
  AdvisorBubble,
  AlertBanner,
  AlertIcon,
  AuthorshipPrismBar,
  Button,
  CheckIcon,
  StudentCard,
} from "@/components/ui";

type AutonomyMode = "socratic" | "polish" | "coauthor" | "draft";

function getGradientZoneMeta(intensity: number): {
  mode: AutonomyMode;
  zoneTitle: string;
  badgeText: string;
  badgeClass: string;
  description: string;
  buttonLabel: string;
} {
  if (intensity <= 15) {
    return {
      mode: "socratic",
      zoneTitle: "Zona 1 · Orientador Socrático Puro (0–15%)",
      badgeText: "Isento · 0% IA no texto",
      badgeClass: "bg-done text-paper",
      description:
        "A IA nunca escreve nem altera seu texto: atua apenas com perguntas socráticas e verificação de evidências.",
      buttonLabel: "Modo Socrático Ativo",
    };
  }
  if (intensity <= 35) {
    return {
      mode: "polish",
      zoneTitle: "Zona 2 · Revisão Ortográfica e Gramatical Estrita (16–35%)",
      badgeText: "Isento COPE/ICMJE",
      badgeClass: "bg-done text-paper",
      description:
        "Corrige apenas ortografia, pontuação e concordância sem trocar seu vocabulário nem reestruturar períodos.",
      buttonLabel: `Revisar ortografia (${intensity}%)`,
    };
  }
  if (intensity <= 60) {
    return {
      mode: "polish",
      zoneTitle: "Zona 3 · Lapidação de Estilo Acadêmico (36–60%)",
      badgeText: "Revisão Leve · Isento",
      badgeClass: "bg-purple text-paper",
      description:
        "Aprimora coesão, voz impessoal e norma culta científica preservando 100% das suas ideias e argumentos.",
      buttonLabel: `Lapidar estilo acadêmico (${intensity}%)`,
    };
  }
  if (intensity <= 80) {
    return {
      mode: "coauthor",
      zoneTitle: "Zona 4 · Co-escrita Híbrida com Evidência (61–80%)",
      badgeText: "Híbrido · Declara coautoria",
      badgeClass: "bg-orange text-ink",
      description:
        "Preserva sua frase inicial (tópico frasal) e costura 1 citação literal verificada (quote + página) do projeto.",
      buttonLabel: `Expandir minha frase com fonte (${intensity}%)`,
    };
  }
  return {
    mode: "draft",
    zoneTitle: "Zona 5 · Redação Guiada por Evidências Verificadas (81–100%)",
    badgeText: "Declaração Obrigatória ABNT",
    badgeClass: "bg-orange text-ink",
    description:
      "Redige um parágrafo acadêmico completo articulando exclusivamente as citações literais verificadas da seção.",
    buttonLabel: `Redigir parágrafo com fontes (${intensity}%)`,
  };
}

const PROVENANCE_LABEL: Record<string, string> = {
  ai_draft: "Rascunho gerado por IA",
  ai_coauthor: "Coautoria com IA",
  ai_polish: "Revisão leve por IA",
  ai_paraphrase: "Reescrita de rascunho da IA (confirmada por você)",
  paste: "Texto colado de fora",
  paraphrase_dismissed: "Sugestão de reescrita dispensada por você",
};

const MIN_PASTE_WORDS = 15;

const DEFAULT_PRISM: AuthorshipPrism = {
  total_words: 0,
  human_words: 0,
  polished_words: 0,
  ai_drafted_words: 0,
  human_pct: 100,
  polished_pct: 0,
  ai_drafted_pct: 0,
  requires_disclosure: false,
};

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
  const selectedSectionIdRef = useRef<string | null>(null);
  selectedSectionIdRef.current = selectedSectionId;
  const [coherence, setCoherence] = useState<CoherenceWarning[]>([]);
  const [concepts, setConcepts] = useState<MapNode[]>([]);
  const [claims, setClaims] = useState<ProjectClaim[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<"saved" | "saving" | "unsaved">("saved");
  const [activeTab, setActiveTab] = useState<"analysis" | "coherence" | "evidence" | "comments" | "versions">("analysis");
  const [analysisSubTab, setAnalysisSubTab] = useState<"dissect" | "compare" | "boxcar">("dissect");
  const [textAnalysis, setTextAnalysis] = useState<TextAnalysisWorkspace | null>(null);
  const [selectedDocGuideId, setSelectedDocGuideId] = useState<string>("");
  const [claimAId, setClaimAId] = useState<string>("");
  const [claimBId, setClaimBId] = useState<string>("");
  const [relationType, setRelationType] = useState<"corroboracao" | "contraponto" | "complementaridade" | "lacuna">("complementaridade");
  const [studentAnalysisNote, setStudentAnalysisNote] = useState<string>("");
  const [compareResult, setCompareResult] = useState<TextCompareResult | null>(null);
  const [comparingBusy, setComparingBusy] = useState<boolean>(false);
  const [newTitle, setNewTitle] = useState("");
  const [isExporting, setIsExporting] = useState(false);
  const [comments, setComments] = useState<SectionComment[]>([]);
  const [versions, setVersions] = useState<SectionVersion[]>([]);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [restoringVersionId, setRestoringVersionId] = useState<string | null>(null);
  const [newComment, setNewComment] = useState("");
  const [anchorQuote, setAnchorQuote] = useState<string | null>(null);
  const [showCitePicker, setShowCitePicker] = useState(false);
  const [citeQuery, setCiteQuery] = useState("");
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [advisorEmail, setAdvisorEmail] = useState("");
  const [advisors, setAdvisors] = useState<AdvisorMember[]>([]);
  const [autonomyIntensity, setAutonomyIntensity] = useState<number>(0);
  const [prism, setPrism] = useState<AuthorshipPrism>(DEFAULT_PRISM);
  const [sectionPrisms, setSectionPrisms] = useState<Record<string, AuthorshipPrism>>({});
  const [showLedger, setShowLedger] = useState<boolean>(false);
  const [declaringEvent, setDeclaringEvent] = useState<string | null>(null);
  const [paraphrases, setParaphrases] = useState<ParaphraseSearchResponse | null>(null);
  const [searchingParaphrases, setSearchingParaphrases] = useState(false);
  const [dismissedParaphrases, setDismissedParaphrases] = useState<string[]>([]);
  const [aiInstruction, setAiInstruction] = useState("");
  const [aiBusy, setAiBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [omitDeclaration, setOmitDeclaration] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const activeZone = useMemo(
    () => getGradientZoneMeta(autonomyIntensity),
    [autonomyIntensity]
  );

  function handleIntensityChange(nextVal: number) {
    const clamped = Math.max(0, Math.min(100, nextVal));
    setAutonomyIntensity(clamped);
  }

  const activeSection = useMemo(
    () => sections.find((s) => s.id === selectedSectionId) ?? null,
    [sections, selectedSectionId]
  );

  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const refreshCoherence = useCallback(async () => {
    try {
      const [cohData, authData, analysisData] = await Promise.all([
        api<CoherenceWarning[]>(`/projects/${id}/coherence`),
        api<ProjectAuthorshipResponse>(`/projects/${id}/authorship`).catch(() => null),
        api<TextAnalysisWorkspace>(`/projects/${id}/text-analysis`).catch(() => null),
      ]);
      setCoherence(cohData);
      if (authData?.project) {
        setPrism(authData.project);
        setSectionPrisms(authData.sections || {});
      }
      if (analysisData) {
        setTextAnalysis(analysisData);
      }
    } catch {
      // Quiet
    }
  }, [id]);

  // Tiptap Editor initialization (Source Serif 4, corpo 18-20px, entrelinha ~1.58)
  /** Text that came from outside the editor (paste or drop): the ledger records it; the insertion is never blocked. */
  function recordOutsideText(text: string) {
    const words = text.trim().split(/\s+/).filter(Boolean).length;
    const sid = selectedSectionIdRef.current;
    if (words < MIN_PASTE_WORDS || !sid) return;
    void api(`/projects/${id}/sections/${sid}/provenance/paste`, { method: "POST", body: { text } })
      .then(() => api<ProjectAuthorshipResponse>(`/projects/${id}/authorship`))
      .then((all) => {
        setPrism(all.project);
        setSectionPrisms(all.sections);
      })
      .catch(() => {
        /* o registro é melhor-esforço */
      });
  }

  const editor = useEditor({
    extensions: [StarterKit],
    immediatelyRender: false,
    editorProps: {
      attributes: {
        class:
          "min-h-[480px] w-full p-6 sm:p-8 font-serif-academic text-[19px] leading-[1.58] text-ink focus:outline-none",
      },
      handlePaste: (_view, event) => {
        // colagens internas (copiadas do próprio editor) carregam data-pm-slice e não são texto de fora
        const html = event.clipboardData?.getData("text/html") ?? "";
        const text = event.clipboardData?.getData("text/plain") ?? "";
        if (!html.includes("data-pm-slice")) recordOutsideText(text);
        return false;
      },
      handleDrop: (_view, event) => {
        // texto arrastado de outra janela entra sem passar pelo teclado nem pela colagem: também é registrado
        const html = event.dataTransfer?.getData("text/html") ?? "";
        const text = event.dataTransfer?.getData("text/plain") ?? "";
        if (!html.includes("data-pm-slice")) recordOutsideText(text);
        return false;
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
      api<ProjectAuthorshipResponse>(`/projects/${id}/authorship`).catch(() => null),
      api<TextAnalysisWorkspace>(`/projects/${id}/text-analysis`).catch(() => null),
    ])
      .then(([projData, secData, mapData, cohData, claimsData, authData, analysisData]) => {
        if (cancelled) return;
        setProject(projData);
        setSections(secData);
        setConcepts(mapData.nodes || []);
        setCoherence(cohData);
        setClaims(claimsData);
        if (authData?.project) {
          setPrism(authData.project);
          setSectionPrisms(authData.sections || {});
        }
        if (analysisData) {
          setTextAnalysis(analysisData);
          if (analysisData.document_guides.length > 0) {
            setSelectedDocGuideId(analysisData.document_guides[0].document_id);
          }
          if (analysisData.enriched_claims.length >= 2) {
            setClaimAId(analysisData.enriched_claims[0].id);
            setClaimBId(analysisData.enriched_claims[1].id);
          } else if (analysisData.enriched_claims.length === 1) {
            setClaimAId(analysisData.enriched_claims[0].id);
            setClaimBId(analysisData.enriched_claims[0].id);
          }
        }
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

  // Suggestions the author has not answered yet: the export stops once to say so (the document states it either way).
  const [pendingReview, setPendingReview] = useState<{ total: number; sections: { section_id: string; title: string | null; count: number }[] } | null>(null);

  async function handleExport(force = false) {
    setIsExporting(true);
    try {
      if (!force) {
        const pend = await api<{ available: boolean; total: number; sections: { section_id: string; title: string | null; count: number }[] }>(
          `/projects/${id}/provenance/pending`
        ).catch(() => null);
        if (pend && pend.available && pend.total > 0) {
          setPendingReview({ total: pend.total, sections: pend.sections });
          return;
        }
      }
      setPendingReview(null);
      const canOmit = !prism.requires_disclosure && omitDeclaration;
      await downloadDocx(id, `${project?.title || "trabalho"}.docx`, canOmit);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao exportar DOCX.");
    } finally {
      setIsExporting(false);
    }
  }

  async function handleRunAiAssist(modeOverride?: "polish" | "coauthor" | "draft") {
    if (!activeSection) return;
    const effectiveMode =
      modeOverride ??
      (activeZone.mode === "socratic" ? "polish" : activeZone.mode);
    const effectiveIntensity =
      autonomyIntensity <= 15
        ? effectiveMode === "polish"
          ? 45
          : 90
        : autonomyIntensity;

    setAiBusy(true);
    setError(null);
    setNotice(null);
    try {
      let selectedText = "";
      if (editor) {
        const { from, to } = editor.state.selection;
        selectedText = editor.state.doc.textBetween(from, to, " ").trim();
      }
      const res = await api<AiAssistResponse>(
        `/projects/${id}/sections/${activeSection.id}/ai-assist`,
        {
          method: "POST",
          body: {
            mode: effectiveMode,
            intensity: effectiveIntensity,
            selected_text: selectedText || undefined,
            instruction: aiInstruction.trim() || undefined,
          },
        }
      );
      setSections((prev) =>
        prev.map((s) => (s.id === res.section.id ? res.section : s))
      );
      if (editor && res.section.content) {
        editor.commands.setContent(res.section.content, { emitUpdate: false });
      }
      setPrism(res.project_authorship);
      setSectionPrisms((prev) => ({
        ...prev,
        [res.section.id]: res.section_authorship,
      }));
      setAiInstruction("");
      setNotice(
        res.notice
          ? res.notice
          : res.mode === "polish"
          ? `Trecho revisado na intensidade ${res.intensity}% (registrado na faixa de revisão leve do Prisma).`
          : res.mode === "coauthor"
          ? `Co-escrita híbrida (${res.intensity}%) concluída com citação verificada.`
          : `Parágrafo redigido (${res.intensity}%) com base nos trechos literais verificados (declaração de IA ativada no Prisma).`
      );
      void refreshCoherence();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao executar assistência de IA.");
    } finally {
      setAiBusy(false);
    }
  }

  async function handleDeclarePaste(eventId: string, declared: "own_text" | null) {
    if (!activeSection) return;
    setDeclaringEvent(eventId);
    setError(null);
    try {
      const secPrism = await api<AuthorshipPrism>(
        `/projects/${id}/sections/${activeSection.id}/provenance/events/${eventId}/declare`,
        { method: "POST", body: { declared } }
      );
      setSectionPrisms((prev) => ({ ...prev, [activeSection.id]: secPrism }));
      const all = await api<ProjectAuthorshipResponse>(`/projects/${id}/authorship`);
      setPrism(all.project);
      setSectionPrisms(all.sections);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao registrar a declaração.");
    } finally {
      setDeclaringEvent(null);
    }
  }

  useEffect(() => {
    setParaphrases(null); // suggestions belong to the section they were found in
    setDismissedParaphrases([]);
  }, [selectedSectionId]);

  async function handleFindParaphrases() {
    if (!activeSection) return;
    setSearchingParaphrases(true);
    setError(null);
    try {
      const res = await api<ParaphraseSearchResponse>(
        `/projects/${id}/sections/${activeSection.id}/provenance/paraphrases`,
        { method: "POST" }
      );
      setParaphrases(res);
      setDismissedParaphrases([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao comparar o texto com os rascunhos da IA.");
    } finally {
      setSearchingParaphrases(false);
    }
  }

  async function handleConfirmParaphrase(s: ParaphraseSuggestion) {
    if (!activeSection) return;
    setError(null);
    try {
      await api(`/projects/${id}/sections/${activeSection.id}/provenance/paraphrases/confirm`, {
        method: "POST",
        body: { text: s.text, event_id: s.event_id },
      });
      const all = await api<ProjectAuthorshipResponse>(`/projects/${id}/authorship`);
      setPrism(all.project);
      setSectionPrisms(all.sections);
      setParaphrases((prev) =>
        prev ? { ...prev, suggestions: prev.suggestions.filter((x) => x.text !== s.text) } : prev
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao registrar a confirmação.");
    }
  }

  async function handleDismissParaphrase(s: ParaphraseSuggestion) {
    if (!activeSection) return;
    setError(null);
    try {
      await api(`/projects/${id}/sections/${activeSection.id}/provenance/paraphrases/dismiss`, {
        method: "POST",
        body: { text: s.text },
      });
      setDismissedParaphrases((prev) => [...prev, s.text]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao registrar a revisão.");
    }
  }

  const activeSectionPrism = activeSection
    ? sectionPrisms[activeSection.id] ?? prism
    : prism;

  const activeDocGuide = useMemo(() => {
    if (!textAnalysis || textAnalysis.document_guides.length === 0) return null;
    return (
      textAnalysis.document_guides.find((d) => d.document_id === selectedDocGuideId) ??
      textAnalysis.document_guides[0]
    );
  }, [textAnalysis, selectedDocGuideId]);

  const activeSectionAudit = useMemo(() => {
    if (!textAnalysis || !activeSection) return null;
    return (
      textAnalysis.manuscript_audit.sections.find((s) => s.section_id === activeSection.id) ??
      null
    );
  }, [textAnalysis, activeSection]);

  async function handleCompareTexts(insertIntoSection: boolean = false) {
    if (!claimAId || !claimBId) {
      setError("Selecione dois trechos verificados (Trecho A e Trecho B) para comparar.");
      return;
    }
    setComparingBusy(true);
    setError(null);
    setNotice(null);
    try {
      const res = await api<TextCompareResult>(
        `/projects/${id}/text-analysis/compare`,
        {
          method: "POST",
          body: {
            claim_a_id: claimAId,
            claim_b_id: claimBId,
            relation_type: relationType,
            student_analysis: studentAnalysisNote.trim() || undefined,
            section_id: activeSection?.id ?? undefined,
            intensity: autonomyIntensity,
            insert_into_section: insertIntoSection,
          },
        }
      );
      setCompareResult(res);
      setPrism(res.project_authorship);
      if (res.notice) setNotice(res.notice);
      if (insertIntoSection && res.updated_section) {
        const upSec = res.updated_section;
        setSections((prev) => prev.map((s) => (s.id === upSec.id ? upSec : s)));
        if (editor && upSec.content) {
          editor.commands.setContent(upSec.content, { emitUpdate: false });
        }
        setNotice(
          res.notice
            ? `${res.notice} O esqueleto foi inserido na seção atual.`
            : res.mode_used === "scaffold_socratico"
            ? "Esqueleto analítico socrático com as duas citações verificadas inserido na seção atual!"
            : "Parágrafo dialético comparando os dois autores inserido na seção e registrado no Prisma!"
        );
        void refreshCoherence();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao comparar trechos.");
    } finally {
      setComparingBusy(false);
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
              onClick={() => void handleExport()}
            >
              {isExporting ? "Gerando Word…" : "Exportar DOCX (ABNT)"}
            </Button>
          </div>
        </div>

        {error && <AlertBanner variant="error">{error}</AlertBanner>}
        {notice && <AlertBanner variant="notice">{notice}</AlertBanner>}
        {pendingReview && (
          <div role="alert" className="rounded-[12px] border border-orange bg-skipped-bg/60 p-4 space-y-3">
            <p className="text-[15px] font-semibold text-ink">
              {pendingReview.total} trecho(s) parecem reescrita de rascunhos da IA e ainda não foram revisados por você.
            </p>
            <p className="text-[14px] text-locked">
              Em: {pendingReview.sections.map((s) => `${s.title ?? "seção"} (${s.count})`).join(", ")}. Enquanto não forem
              revisados, não contam como revisão de IA no Prisma; o documento exportado informa isso na declaração.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="primary"
                onClick={() => {
                  setSelectedSectionId(pendingReview.sections[0].section_id);
                  setShowLedger(true);
                  setPendingReview(null);
                }}
              >
                Revisar agora
              </Button>
              <Button type="button" variant="secondary" onClick={() => void handleExport(true)}>
                Exportar mesmo assim
              </Button>
            </div>
          </div>
        )}

        {/* Gradiente Contínuo de Autonomia (0–100%) + Prisma de Autoria */}
        <section
          aria-label="Gradiente de autonomia da IA e Validador de Autoria"
          className="space-y-4"
        >
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-12 items-stretch">
            {/* Gradiente Contínuo de Intervenção (7 cols) */}
            <div className="lg:col-span-7 rounded-[12px] border border-borda bg-superficie p-4 flex flex-col justify-between gap-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-[13px] font-bold uppercase tracking-wider text-locked">
                    Gradiente de Autonomia da IA ({autonomyIntensity}%)
                  </span>
                  <span
                    className={`rounded-[6px] px-2 py-0.5 text-[11px] font-bold uppercase ${activeZone.badgeClass}`}
                  >
                    {activeZone.badgeText}
                  </span>
                </div>

                {!prism.requires_disclosure && (
                  <label className="flex items-center gap-2 text-[13px] font-medium text-ink cursor-pointer">
                    <input
                      type="checkbox"
                      checked={omitDeclaration}
                      onChange={(e) => setOmitDeclaration(e.target.checked)}
                      className="h-4 w-4 accent-purple"
                    />
                    <span>Omitir anexo de IA no DOCX (texto autoral)</span>
                  </label>
                )}
              </div>

              {/* Barra em Gradiente Contínuo + Slider Interativo */}
              <div className="space-y-2 pt-1">
                <div className="relative flex items-center">
                  <div
                    className="h-3.5 w-full rounded-full border border-borda"
                    style={{
                      background:
                        "linear-gradient(90deg, #5F6E2F 0%, #5F6E2F 25%, #4B2A7B 50%, #E8761E 80%, #E8761E 100%)",
                    }}
                  />
                  {/* Marco de 60% (Limiar de Isenção COPE/SciELO) */}
                  <div
                    className="pointer-events-none absolute top-[-6px] bottom-[-6px] w-[2px] bg-ink"
                    style={{ left: "60%" }}
                    title="Limiar 60% COPE/SciELO: abaixo = revisão isenta; acima = declaração obrigatória"
                  />
                  <input
                    type="range"
                    aria-label="Gradiente de autonomia da IA"
                    min={0}
                    max={100}
                    step={5}
                    value={autonomyIntensity}
                    onChange={(e) => handleIntensityChange(Number(e.target.value))}
                    className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
                  />
                  {/* Cursor visual do gradiente */}
                  <div
                    className="pointer-events-none absolute h-6 w-6 -translate-x-1/2 rounded-full border-2 border-ink bg-paper shadow flex items-center justify-center text-[10px] font-bold text-ink transition-all"
                    style={{ left: `${autonomyIntensity}%` }}
                  >
                    {autonomyIntensity}
                  </div>
                </div>

                <div className="flex items-center justify-between text-[11px] font-semibold text-locked">
                  <span>0% Socrático</span>
                  <span>25% Ortografia</span>
                  <span>60% Limiar COPE/SciELO</span>
                  <span>100% Redator com Fontes</span>
                </div>
              </div>

              {/* Presets rápidos do Espectro + Descrição da Zona Ativa */}
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-[10px] border border-borda bg-paper/60 px-3 py-2">
                <div className="space-y-0.5">
                  <div className="text-[14px] font-bold text-ink">{activeZone.zoneTitle}</div>
                  <p className="text-[13px] text-locked">{activeZone.description}</p>
                </div>

                <div className="flex flex-wrap items-center gap-1.5">
                  {[
                    { label: "0% Socrático", val: 0 },
                    { label: "25% Gramática", val: 25 },
                    { label: "50% Estilo", val: 50 },
                    { label: "70% Co-escrita", val: 70 },
                    { label: "95% Redator", val: 95 },
                  ].map((preset) => (
                    <button
                      key={preset.val}
                      type="button"
                      onClick={() => handleIntensityChange(preset.val)}
                      className={`min-h-[44px] rounded-[6px] border px-3 py-1 text-[12px] font-bold transition cursor-pointer ${
                        autonomyIntensity === preset.val
                          ? "border-purple bg-purple text-paper"
                          : "border-borda bg-superficie text-ink hover:bg-paper"
                      }`}
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Prisma de Autoria + Registro de autoria (5 cols) */}
            <div className="lg:col-span-5 flex flex-col justify-between gap-2.5">
              <AuthorshipPrismBar prism={prism} />

              <div className="flex flex-wrap items-center justify-between gap-2 rounded-[10px] border border-borda bg-superficie px-3.5 py-2.5">
                <div className="text-[13px] text-ink">
                  <strong>Registro de autoria:</strong> mostra o que a IA inseriu e o que foi colado nesta seção. Não analisa estilo.
                </div>
                <button
                  type="button"
                  disabled={!activeSection}
                  onClick={() => setShowLedger((v) => !v)}
                  className="rounded-[8px] border border-purple bg-skipped-bg/60 px-3 py-1.5 text-[13px] font-bold text-purple hover:bg-purple hover:text-paper transition cursor-pointer"
                >
                  {showLedger ? "Ocultar registro" : "Ver registro desta seção"}
                </button>
              </div>
            </div>
          </div>

          {/* Registro de proveniência da seção ativa */}
          {showLedger && (
            <div
              aria-label="Registro de autoria da seção"
              className="rounded-[14px] border-2 border-purple bg-superficie p-5 space-y-3"
            >
              <h2 className="font-display text-lg text-ink">
                Registro de autoria · {activeSection?.title}
              </h2>
              {(activeSectionPrism.events ?? []).length === 0 ? (
                <p className="text-[14px] text-locked">
                  Nada registrado: nenhum texto de IA foi inserido e nenhuma colagem foi informada nesta seção.
                </p>
              ) : (
                <ul className="space-y-2">
                  {(activeSectionPrism.events ?? []).map((ev) => (
                    <li
                      key={ev.id ?? `${ev.kind}-${ev.created_at}`}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-[10px] border border-borda bg-paper/40 p-3 text-[14px] text-ink"
                    >
                      <span>
                        <strong>{PROVENANCE_LABEL[ev.kind] ?? ev.kind}</strong> · {ev.words} palavras
                        {ev.created_at ? ` · ${new Date(ev.created_at).toLocaleString("pt-BR")}` : ""}
                        {ev.declared === "own_text" ? " · declarado como texto do autor" : ""}
                      </span>
                      {ev.kind === "paste" && ev.id && (
                        <Button
                          type="button"
                          variant="secondary"
                          disabled={declaringEvent === ev.id}
                          onClick={() => void handleDeclarePaste(ev.id as string, ev.declared ? null : "own_text")}
                        >
                          {ev.declared ? "Desfazer declaração" : "Este texto é meu"}
                        </Button>
                      )}
                    </li>
                  ))}
                </ul>
              )}
              <p className="text-[12px] leading-snug text-locked">
                “Este texto é meu” fica registrado como declaração sua, não como verificação.
              </p>

              <div className="space-y-2 border-t border-borda pt-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-[14px] text-ink">
                    <strong>Reescritas de rascunhos da IA:</strong> compara seus parágrafos, pelo significado, com os
                    rascunhos que a IA gerou aqui.
                  </div>
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={searchingParaphrases || !activeSection}
                    onClick={() => void handleFindParaphrases()}
                  >
                    {searchingParaphrases ? "Comparando…" : "Procurar trechos parecidos"}
                  </Button>
                </div>
                {paraphrases && !paraphrases.available && (
                  <p role="status" className="text-[13px] text-locked">{paraphrases.notice}</p>
                )}
                {paraphrases?.available && (
                  <>
                    {paraphrases.suggestions.filter((s) => !dismissedParaphrases.includes(s.text)).length === 0 ? (
                      <p role="status" className="text-[13px] text-locked">
                        Nenhum parágrafo seu parece reescrita de um rascunho da IA registrado.
                      </p>
                    ) : (
                      <ul className="space-y-2">
                        {paraphrases.suggestions
                          .filter((s) => !dismissedParaphrases.includes(s.text))
                          .map((s) => (
                            <li key={s.text} className="space-y-2 rounded-[10px] border border-borda bg-paper/40 p-3 text-[14px] text-ink">
                              <p className="font-serif-academic leading-snug">{s.text}</p>
                              <p className="text-[12px] text-locked">
                                Parecido com o rascunho da IA: “{s.ai_excerpt}…” (semelhança {Math.round(s.similarity * 100)}%)
                              </p>
                              <div className="flex flex-wrap gap-2">
                                <Button type="button" variant="secondary" onClick={() => void handleConfirmParaphrase(s)}>
                                  Parte do rascunho da IA
                                </Button>
                                <Button
                                  type="button"
                                  variant="secondary"
                                  onClick={() => void handleDismissParaphrase(s)}
                                >
                                  É texto meu
                                </Button>
                              </div>
                            </li>
                          ))}
                      </ul>
                    )}
                    {paraphrases.limits && (
                      <p className="text-[12px] leading-snug text-locked">{paraphrases.limits.join(" ")}</p>
                    )}
                  </>
                )}
              </div>
            </div>
          )}
        </section>

        {/* Mobile: toggle sumário de seções */}
        <button
          type="button"
          onClick={() => setSidebarOpen((v) => !v)}
          className="lg:hidden flex items-center justify-between w-full rounded-[12px] border border-borda bg-superficie px-4 py-3 text-[15px] font-medium text-ink"
        >
          <span>Sumário de seções ({sections.length})</span>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" className={`h-5 w-5 text-locked transition-transform ${sidebarOpen ? "rotate-180" : ""}`}>
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </button>

        {/* Layout de 3 colunas */}
        <div className="grid flex-1 grid-cols-1 gap-6 lg:grid-cols-12 items-start">
          {/* Coluna Esquerda: Sumário de Seções (3 cols) */}
          <aside
            aria-label="Árvore de seções"
            className={`rounded-[16px] border border-borda bg-superficie p-5 lg:col-span-3 flex-col gap-4 ${sidebarOpen ? "flex" : "hidden"} lg:flex`}
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
                aria-label="Título da nova seção"
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
                  className={`min-h-[44px] min-w-[44px] rounded-[8px] px-2.5 font-bold cursor-pointer ${
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
                  className={`min-h-[44px] min-w-[44px] rounded-[8px] px-2.5 italic cursor-pointer ${
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

            {/* Barra de Execução do Gradiente (>15%: Revisão, Co-escrita Híbrida ou Redação Guiada) */}
            {autonomyIntensity > 15 && activeSection && (
              <div
                className={`border-b border-borda px-4 py-3 space-y-2.5 ${
                  autonomyIntensity <= 60 ? "bg-skipped-bg/50" : "bg-paper"
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-[13px] font-bold uppercase tracking-wider text-purple">
                    {activeZone.zoneTitle}
                  </span>
                </div>

                <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5">
                  <input
                    type="text"
                    value={aiInstruction}
                    onChange={(e) => setAiInstruction(e.target.value)}
                    placeholder={
                      autonomyIntensity <= 60
                        ? "Orientação opcional (ex.: mais conciso, formalizar conectivos)…"
                        : autonomyIntensity <= 80
                        ? "Sua frase inicial / premissa para a IA expandir com uma citação verificada…"
                        : "Foco do parágrafo (ex.: relacionar aprendizagem significativa à motivação)…"
                    }
                    className="flex-1 h-[42px] rounded-[10px] border border-borda bg-superficie px-3.5 text-[15px] text-ink"
                  />
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={aiBusy}
                    onClick={() => void handleRunAiAssist()}
                  >
                    {aiBusy ? "Processando…" : activeZone.buttonLabel}
                  </Button>
                </div>
              </div>
            )}

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
            <div className="flex flex-wrap border-b border-borda gap-1.5 text-[14px]">
              <button
                type="button"
                onClick={() => setActiveTab("analysis")}
                className={`min-h-[44px] px-2.5 font-bold transition cursor-pointer border-b-2 ${
                  activeTab === "analysis"
                    ? "border-purple text-purple"
                    : "border-transparent text-locked hover:text-ink"
                }`}
              >
                Analisar & Conectar
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("coherence")}
                className={`min-h-[44px] px-2.5 font-bold transition cursor-pointer border-b-2 ${
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
                className={`min-h-[44px] px-2.5 font-bold transition cursor-pointer border-b-2 ${
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
                className={`min-h-[44px] px-2.5 font-bold transition cursor-pointer border-b-2 ${
                  activeTab === "comments"
                    ? "border-purple text-purple"
                    : "border-transparent text-locked hover:text-ink"
                }`}
              >
                Comentários ({comments.length})
              </button>
              <button
                type="button"
                onClick={() => {
                  setActiveTab("versions");
                  if (selectedSectionId) {
                    setVersionsLoading(true);
                    listSectionVersions(id, selectedSectionId).then(setVersions).catch(() => {}).finally(() => setVersionsLoading(false));
                  }
                }}
                className={`min-h-[44px] px-2.5 font-bold transition cursor-pointer border-b-2 ${
                  activeTab === "versions"
                    ? "border-purple text-purple"
                    : "border-transparent text-locked hover:text-ink"
                }`}
              >
                Versões
              </button>
            </div>

            {/* Aba: Laboratório de Análise Guiada e Comparação de Textos */}
            {activeTab === "analysis" && (
              <div className="space-y-4 text-[14px] max-h-[640px] overflow-y-auto pr-1">
                {/* Sub-seletor das 3 frentes de análise */}
                <div className="grid grid-cols-3 gap-1.5 rounded-[10px] border border-borda bg-paper p-1">
                  <button
                    type="button"
                    onClick={() => setAnalysisSubTab("dissect")}
                    className={`rounded-[8px] py-1.5 px-2 text-[12px] font-bold transition cursor-pointer ${
                      analysisSubTab === "dissect"
                        ? "bg-purple text-paper"
                        : "text-ink hover:bg-superficie"
                    }`}
                  >
                    1. Dissecar PDF
                  </button>
                  <button
                    type="button"
                    onClick={() => setAnalysisSubTab("compare")}
                    className={`rounded-[8px] py-1.5 px-2 text-[12px] font-bold transition cursor-pointer ${
                      analysisSubTab === "compare"
                        ? "bg-purple text-paper"
                        : "text-ink hover:bg-superficie"
                    }`}
                  >
                    2. Comparar A×B
                  </button>
                  <button
                    type="button"
                    onClick={() => setAnalysisSubTab("boxcar")}
                    className={`rounded-[8px] py-1.5 px-2 text-[12px] font-bold transition cursor-pointer ${
                      analysisSubTab === "boxcar"
                        ? "bg-purple text-paper"
                        : "text-ink hover:bg-superficie"
                    }`}
                  >
                    3. Vagão de Trem
                  </button>
                </div>

                {/* SUB-ABA 1: Guia de Leitura e Dissecação Estruturada de PDF */}
                {analysisSubTab === "dissect" && (
                  <div className="space-y-3">
                    {!textAnalysis || textAnalysis.document_guides.length === 0 ? (
                      <p className="text-[14px] text-locked">
                        Envie um PDF no Mapa de Conhecimento para liberar o Guia de Leitura Analítica e Dissecação do Artigo.
                      </p>
                    ) : (
                      <>
                        <div className="space-y-1">
                          <label className="block text-[12px] font-bold uppercase tracking-wider text-locked">
                            Escolha o artigo / PDF para analisar:
                          </label>
                          <select
                            aria-label="Escolher documento para análise guiada"
                            value={activeDocGuide?.document_id ?? ""}
                            onChange={(e) => setSelectedDocGuideId(e.target.value)}
                            className="w-full h-[40px] rounded-[8px] border border-borda bg-paper/60 px-2.5 text-[14px] font-bold text-ink"
                          >
                            {textAnalysis.document_guides.map((dg) => (
                              <option key={dg.document_id} value={dg.document_id}>
                                {dg.title} ({dg.year ?? "s.d."}) · {dg.claims_count} trechos
                              </option>
                            ))}
                          </select>
                        </div>

                        {activeDocGuide && (
                          <div className="space-y-3">
                            {/* Tese Central */}
                            <div className="rounded-[10px] border border-borda bg-paper/50 p-3 space-y-1">
                              <span className="text-[11px] font-bold uppercase tracking-wider text-purple">
                                Tese Central Identificada no Texto
                              </span>
                              <p className="text-[14px] font-medium text-ink leading-snug">
                                {activeDocGuide.core_thesis}
                              </p>
                            </div>

                            {/* Roteiro Socrático de Leitura Crítica */}
                            <AdvisorBubble label="Roteiro para você analisar este artigo">
                              <ul className="space-y-1.5 text-[13px] list-disc pl-4">
                                {activeDocGuide.study_questions.map((q, idx) => (
                                  <li key={idx}>{q}</li>
                                ))}
                              </ul>
                            </AdvisorBubble>

                            {/* Pontes automáticas com outros PDFs */}
                            {activeDocGuide.shared_bridges.length > 0 && (
                              <div className="rounded-[10px] border border-done bg-paper/40 p-2.5 space-y-1">
                                <span className="text-[11px] font-bold uppercase tracking-wider text-done">
                                  Pontes com outros PDFs da sua biblioteca
                                </span>
                                {activeDocGuide.shared_bridges.map((br, i) => (
                                  <p key={i} className="text-[13px] text-ink">
                                    Conecta o conceito <strong>{br.concept_label}</strong> com{" "}
                                    <em>{br.other_document_title}</em>.
                                  </p>
                                ))}
                              </div>
                            )}

                            {/* Passagens Dissecadas por Papel Retórico-Científico */}
                            <div className="space-y-2">
                              <span className="text-[12px] font-bold uppercase tracking-wider text-locked">
                                Anatomia dos Trechos Verificados ({activeDocGuide.passages.length})
                              </span>
                              {activeDocGuide.passages.map((p) => (
                                <div
                                  key={p.id}
                                  className="rounded-[10px] border border-borda bg-superficie p-3 space-y-2"
                                >
                                  <div className="flex flex-wrap items-center justify-between gap-1.5">
                                    <span
                                      className={`rounded-[6px] px-2 py-0.5 text-[11px] font-bold uppercase ${
                                        p.role_code === "evidencia_empirica"
                                          ? "bg-done text-paper"
                                          : p.role_code === "limite_contraponto"
                                          ? "bg-orange text-ink"
                                          : "bg-purple text-paper"
                                      }`}
                                    >
                                      {p.role_label}
                                    </span>
                                    <span className="text-[12px] font-bold text-locked">
                                      {p.citation_ref}
                                    </span>
                                  </div>

                                  <blockquote className="font-serif-academic text-[14px] leading-snug text-ink">
                                    <mark className="mark-orange">{p.quote}</mark>
                                  </blockquote>

                                  <p className="text-[12px] text-ink bg-paper/60 rounded p-2">
                                    <strong>Como analisar e usar:</strong> {p.reading_tip}
                                  </p>

                                  <div className="space-y-1 text-[12px] text-locked border-t border-borda pt-1.5">
                                    {p.socratic_prompts.map((sp, idx) => (
                                      <div key={idx}>• {sp}</div>
                                    ))}
                                  </div>

                                  <div className="flex flex-wrap items-center gap-1.5 pt-1">
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setClaimAId(p.id);
                                        setAnalysisSubTab("compare");
                                      }}
                                      className="rounded-[6px] border border-purple px-2 py-1 text-[12px] font-bold text-purple hover:bg-skipped-bg cursor-pointer"
                                    >
                                      Usar como Trecho A
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setClaimBId(p.id);
                                        setAnalysisSubTab("compare");
                                      }}
                                      className="rounded-[6px] border border-purple px-2 py-1 text-[12px] font-bold text-purple hover:bg-skipped-bg cursor-pointer"
                                    >
                                      Usar como Trecho B
                                    </button>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                )}

                {/* SUB-ABA 2: Mesa de Confronto & Costureiro Dialético (A vs. B) */}
                {analysisSubTab === "compare" && (
                  <div className="space-y-3">
                    <p className="text-[13px] text-locked">
                      Selecione dois trechos verificados para o Orientador ajudar você a analisar convergências, tensões e costurar o diálogo no capítulo:
                    </p>

                    <div className="space-y-2">
                      <div>
                        <label className="block text-[12px] font-bold uppercase tracking-wider text-locked">
                          Trecho A (Tese / Primeira Evidência):
                        </label>
                        <select
                          aria-label="Selecionar Trecho A"
                          value={claimAId}
                          onChange={(e) => setClaimAId(e.target.value)}
                          className="w-full h-[38px] rounded-[8px] border border-borda bg-paper/60 px-2 text-[13px] text-ink"
                        >
                          <option value="">Selecione um trecho verificado…</option>
                          {(textAnalysis?.enriched_claims ?? []).map((ec) => (
                            <option key={ec.id} value={ec.id}>
                              {ec.citation_ref} [{ec.role_label}] — {ec.quote.slice(0, 55)}…
                            </option>
                          ))}
                        </select>
                      </div>

                      <div>
                        <label className="block text-[12px] font-bold uppercase tracking-wider text-locked">
                          Trecho B (Contraponto / Segunda Evidência):
                        </label>
                        <select
                          aria-label="Selecionar Trecho B"
                          value={claimBId}
                          onChange={(e) => setClaimBId(e.target.value)}
                          className="w-full h-[38px] rounded-[8px] border border-borda bg-paper/60 px-2 text-[13px] text-ink"
                        >
                          <option value="">Selecione um trecho verificado…</option>
                          {(textAnalysis?.enriched_claims ?? []).map((ec) => (
                            <option key={ec.id} value={ec.id}>
                              {ec.citation_ref} [{ec.role_label}] — {ec.quote.slice(0, 55)}…
                            </option>
                          ))}
                        </select>
                      </div>

                      <div>
                        <label className="block text-[12px] font-bold uppercase tracking-wider text-locked">
                          Tipo de relação analítica que você quer construir:
                        </label>
                        <select
                          aria-label="Selecionar tipo de relação analítica"
                          value={relationType}
                          onChange={(e) =>
                            setRelationType(
                              e.target.value as
                                | "corroboracao"
                                | "contraponto"
                                | "complementaridade"
                                | "lacuna"
                            )
                          }
                          className="w-full h-[38px] rounded-[8px] border border-borda bg-paper/60 px-2 text-[13px] font-bold text-ink"
                        >
                          <option value="complementaridade">
                            Complementaridade: Teoria (A) → Prática/Método (B)
                          </option>
                          <option value="corroboracao">
                            Corroboração: B comprova e reforça A (A + B)
                          </option>
                          <option value="contraponto">
                            Contraponto / Tensão: B mostra o limite de A (A vs. B)
                          </option>
                          <option value="lacuna">
                            Ponte / Lacuna: Conectar dois eixos ainda isolados
                          </option>
                        </select>
                      </div>

                      <div>
                        <label className="block text-[12px] font-bold uppercase tracking-wider text-locked">
                          Sua leitura crítica (o que você percebeu ao comparar os dois?):
                        </label>
                        <textarea
                          rows={2}
                          value={studentAnalysisNote}
                          onChange={(e) => setStudentAnalysisNote(e.target.value)}
                          placeholder="Ex.: O primeiro autor define a base cognitiva, enquanto o segundo comprova o impacto na retenção escolar…"
                          className="w-full rounded-[8px] border border-borda bg-superficie p-2.5 text-[13px] text-ink"
                        />
                      </div>

                      <div className="flex flex-wrap items-center gap-2 pt-1">
                        <Button
                          type="button"
                          variant="secondary"
                          disabled={comparingBusy || !claimAId || !claimBId}
                          onClick={() => void handleCompareTexts(false)}
                          className="flex-1"
                        >
                          {comparingBusy ? "Analisando…" : "Analisar e Comparar A × B"}
                        </Button>
                      </div>
                    </div>

                    {/* Resultado da Matriz de Comparação + Costura Dialética */}
                    {compareResult && (
                      <div className="rounded-[12px] border-2 border-purple bg-paper/50 p-3.5 space-y-3">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[12px] font-bold uppercase tracking-wider text-purple">
                            Matriz de Triangulação: {compareResult.passage_a.citation_ref} ×{" "}
                            {compareResult.passage_b.citation_ref}
                          </span>
                          <span className="rounded bg-purple px-2 py-0.5 text-[11px] font-bold text-paper">
                            {compareResult.mode_used === "scaffold_socratico"
                              ? "Esqueleto Socrático (≤55%)"
                              : "Síntese Assistida (>55%)"}
                          </span>
                        </div>

                        <div className="space-y-1.5 text-[13px]">
                          <div className="rounded-[8px] border border-borda bg-superficie p-2.5">
                            <strong className="text-done">Onde convergem:</strong>{" "}
                            {compareResult.comparison_matrix.convergence}
                          </div>
                          <div className="rounded-[8px] border border-borda bg-superficie p-2.5">
                            <strong className="text-ink">Onde divergem / limite:</strong>{" "}
                            {compareResult.comparison_matrix.difference}
                          </div>
                          <div className="rounded-[8px] border border-borda bg-superficie p-2.5">
                            <strong className="text-purple">Pergunta socrática:</strong>{" "}
                            {compareResult.comparison_matrix.guiding_question}
                          </div>
                        </div>

                        {compareResult.synthesis_text && (
                          <div className="space-y-2">
                            <span className="text-[12px] font-bold uppercase tracking-wider text-locked">
                              Parágrafo Dialético Gerado (modo {compareResult.mode_used === "scaffold_socratico" ? "esqueleto" : "síntese"})
                            </span>
                            <blockquote className="font-serif-academic text-[14px] leading-relaxed text-ink rounded-[10px] border border-purple bg-paper/50 p-3">
                              {compareResult.synthesis_text}
                            </blockquote>
                            <Button
                              type="button"
                              variant="secondary"
                              disabled={comparingBusy || !activeSection}
                              onClick={() => void handleCompareTexts(true)}
                              className="w-full"
                            >
                              Inserir parágrafo na seção atual
                            </Button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {/* SUB-ABA 3: Vagão de Trem (Roadmap Socrático de Argumentação) */}
                {analysisSubTab === "boxcar" && (
                  <div className="space-y-3">
                    {!textAnalysis?.manuscript_audit ? (
                      <p className="text-[14px] text-locked">
                        Nenhuma auditoria do manuscrito disponível ainda. Adicione fontes e seções para gerar o Vagão de Trem.
                      </p>
                    ) : (
                      <>
                        <AdvisorBubble label="Vagão de Trem · Roadmap do Manuscrito">
                          <p className="text-[13px]">
                            {textAnalysis.manuscript_audit.total_integrated_paragraphs === 0 &&
                            textAnalysis.manuscript_audit.total_boxcar_paragraphs === 0
                              ? "Escreva parágrafos com citações (Autor, Ano, p. X) para ver aqui se eles dialogam com mais de uma fonte."
                              : `${textAnalysis.manuscript_audit.total_integrated_paragraphs} parágrafo(s) articulam as fontes com análise própria; ${textAnalysis.manuscript_audit.total_boxcar_paragraphs} citam uma fonte isolada (efeito vagão de trem).`}
                          </p>
                        </AdvisorBubble>

                        {activeSectionAudit ? (
                          <div className="space-y-2">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-locked">
                              Seção atual: {activeSection?.title}
                            </div>
                            <div className="rounded-[10px] border border-borda bg-superficie p-3 space-y-2">
                              <div className="text-[13px] text-ink">
                                {activeSectionAudit.paragraph_count} parágrafo(s) · {activeSectionAudit.integrated_count} com síntese entre fontes · {activeSectionAudit.boxcar_count} com fonte isolada
                              </div>
                              {activeSectionAudit.paragraphs.length === 0 ? (
                                <p className="text-[13px] text-locked">
                                  Esta seção ainda não tem parágrafos para analisar.
                                </p>
                              ) : (
                                <div className="space-y-2">
                                  {activeSectionAudit.paragraphs.map((para) => (
                                    <div
                                      key={para.index}
                                      className="rounded-[8px] border border-borda bg-paper/60 p-2 text-[12px] space-y-1"
                                    >
                                      <span
                                        className={`inline-block rounded-[6px] px-2 py-0.5 text-[11px] font-bold uppercase ${
                                          para.status_code === "analise_integrada"
                                            ? "bg-done text-paper"
                                            : para.status_code === "vagao_de_trem"
                                            ? "bg-orange text-ink"
                                            : "border border-borda text-locked"
                                        }`}
                                      >
                                        {para.status_label}
                                      </span>
                                      <div className="text-locked italic">“{para.excerpt}”</div>
                                      <div className="text-ink">{para.feedback}</div>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>
                        ) : (
                          <p className="text-[14px] text-locked">
                            Selecione uma seção para ver sua análise no Vagão de Trem.
                          </p>
                        )}

                        <div className="space-y-2">
                          <div className="text-[12px] font-bold uppercase tracking-wider text-locked">
                            Todas as seções
                          </div>
                          {textAnalysis.manuscript_audit.sections.map((sa) => {
                            const sec = sections.find((s) => s.id === sa.section_id);
                            return (
                              <div
                                key={sa.section_id}
                                onClick={() => setSelectedSectionId(sa.section_id)}
                                className="flex items-center gap-3 rounded-[10px] border border-borda bg-superficie p-2.5 cursor-pointer hover:bg-paper/60"
                              >
                                <div
                                  className={`w-2.5 h-2.5 rounded-full shrink-0 ${
                                    sa.paragraph_count === 0
                                      ? "bg-locked"
                                      : sa.boxcar_count > 0
                                      ? "bg-orange"
                                      : sa.integrated_count > 0
                                      ? "bg-done"
                                      : "bg-borda"
                                  }`}
                                />
                                <div className="flex-1 min-w-0">
                                  <div className="text-[13px] font-bold text-ink truncate">
                                    {sec?.title ?? sa.section_title}
                                  </div>
                                  <div className="text-[12px] text-locked">
                                    {sa.paragraph_count} parágrafo(s) · {sa.integrated_count} integrado(s) · {sa.boxcar_count} vagão
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Aba: Alertas de Coerência */}
            {activeTab === "coherence" && (
              <div className="space-y-3 text-[14px] max-h-[640px] overflow-y-auto pr-1">
                {coherence.length === 0 ? (
                  <div className="flex items-center gap-2 rounded-[10px] border border-done bg-paper/50 p-3">
                    <CheckIcon className="h-4 w-4 text-done" />
                    <span className="text-[14px] font-medium text-ink">
                      Nenhum alerta de coerência. Projeto coeso!
                    </span>
                  </div>
                ) : (
                  coherence.map((w, idx) => (
                    <div
                      key={idx}
                      className="rounded-[10px] border border-borda bg-superficie p-3 space-y-1"
                    >
                      <span className="inline-block rounded-[6px] bg-orange px-2 py-0.5 text-[11px] font-bold uppercase text-ink">
                        {COHERENCE_WARNING_LABELS[w.type] ?? w.type}
                      </span>
                      <p className="text-[14px] text-ink">{w.message}</p>
                    </div>
                  ))
                )}
              </div>
            )}

            {/* Aba: Conceitos Vinculados */}
            {activeTab === "evidence" && (
              <div className="space-y-2 text-[14px] max-h-[640px] overflow-y-auto pr-1">
                {concepts.length === 0 ? (
                  <p className="text-[14px] text-locked">
                    Nenhum conceito no mapa. Acesse o Mapa de Conhecimento para criar nós conceituais.
                  </p>
                ) : (
                  concepts.map((c) => {
                    const isLinked = activeSection?.concept_ids.includes(c.id) ?? false;
                    return (
                      <div
                        key={c.id}
                        className={`flex items-center justify-between rounded-[10px] border p-3 cursor-pointer transition ${
                          isLinked
                            ? "border-purple bg-skipped-bg/60"
                            : "border-borda bg-superficie hover:bg-paper/60"
                        }`}
                        onClick={() => void toggleConceptLink(c.id)}
                      >
                        <div>
                          <div className="text-[14px] font-bold text-ink">{c.label}</div>
                          {c.summary && (
                            <div className="text-[12px] text-locked mt-0.5 line-clamp-2">
                              {c.summary}
                            </div>
                          )}
                        </div>
                        {isLinked && (
                          <CheckIcon className="h-5 w-5 shrink-0 text-purple" />
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            )}

            {/* Aba: Comentários & Perguntas do Orientador */}
            {activeTab === "comments" && (
              <div className="space-y-4 text-[14px] max-h-[640px] overflow-y-auto pr-1">
                {comments.length === 0 && (
                  <p className="text-[14px] text-locked">
                    Nenhum comentário nesta seção ainda.
                  </p>
                )}

                {comments.map((c) => {
                  const { anchor, body } = parseAnchoredComment(c.content);
                  return (
                    <div
                      key={c.id}
                      className={`rounded-[10px] border p-3 space-y-2 ${
                        c.resolved
                          ? "border-done bg-paper/30 opacity-70"
                          : "border-borda bg-superficie"
                      }`}
                    >
                      {anchor && (
                        <blockquote className="rounded-[6px] bg-orange/20 px-2.5 py-1.5 font-serif-academic text-[13px] italic text-ink border-l-2 border-orange">
                          "{anchor}"
                        </blockquote>
                      )}
                      <p className="text-[14px] text-ink whitespace-pre-wrap">{body}</p>
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[12px] text-locked">
                          {new Date(c.created_at).toLocaleDateString("pt-BR")}
                          {c.author_name ? ` · ${c.author_name}` : ""}
                        </span>
                        <button
                          type="button"
                          onClick={() => void toggleCommentResolved(c.id, c.resolved)}
                          className={`rounded-[6px] px-2 py-0.5 text-[12px] font-bold cursor-pointer transition ${
                            c.resolved
                              ? "bg-paper text-locked hover:text-ink"
                              : "bg-done text-paper hover:opacity-80"
                          }`}
                        >
                          {c.resolved ? "Reabrir" : "Resolver ✓"}
                        </button>
                      </div>
                    </div>
                  );
                })}

                <form onSubmit={handleAddComment} className="space-y-2.5 border-t border-borda pt-3">
                  {anchorQuote && (
                    <div className="flex items-start gap-2 rounded-[10px] bg-orange/20 px-3 py-2">
                      <blockquote className="flex-1 font-serif-academic text-[13px] italic text-ink truncate">
                        "{anchorQuote}"
                      </blockquote>
                      <button
                        type="button"
                        onClick={() => setAnchorQuote(null)}
                        className="text-[13px] font-bold text-locked hover:text-ink cursor-pointer shrink-0"
                      >
                        ✕
                      </button>
                    </div>
                  )}
                  <textarea
                    rows={3}
                    value={newComment}
                    onChange={(e) => setNewComment(e.target.value)}
                    placeholder="Escreva um comentário, pergunta socrática ou sugestão para esta seção…"
                    className="w-full rounded-[10px] border border-borda bg-superficie p-3 text-[14px] text-ink"
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

            {/* Aba: Versões da Seção */}
            {activeTab === "versions" && (
              <div className="space-y-3 text-[14px] max-h-[640px] overflow-y-auto pr-1">
                {versionsLoading ? (
                  <p className="text-[14px] text-locked">Carregando versões…</p>
                ) : versions.length === 0 ? (
                  <p className="text-[14px] text-locked">Nenhuma versão salva para esta seção.</p>
                ) : (
                  versions.map((v) => (
                    <div
                      key={v.id}
                      className="rounded-[10px] border border-borda bg-superficie p-3 space-y-2"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div>
                          <div className="text-[13px] font-bold text-ink">
                            {new Date(v.created_at).toLocaleString("pt-BR")}
                          </div>
                          <div className="text-[12px] text-locked">
                            {v.word_count} palavras · {v.change_summary ?? "Versão salva"}
                          </div>
                        </div>
                        <Button
                          type="button"
                          variant="secondary"
                          disabled={restoringVersionId === v.id}
                          onClick={async () => {
                            if (!selectedSectionId) return;
                            setRestoringVersionId(v.id);
                            try {
                              const restored = await restoreSectionVersion(id, selectedSectionId, v.id);
                              setSections((prev) => prev.map((s) => (s.id === restored.id ? restored : s)));
                              if (editor && restored.content) {
                                editor.commands.setContent(restored.content, { emitUpdate: false });
                              }
                              setNotice(`Versão de ${new Date(v.created_at).toLocaleString("pt-BR")} restaurada com sucesso.`);
                            } catch (err) {
                              setError(err instanceof Error ? err.message : "Erro ao restaurar versão.");
                            } finally {
                              setRestoringVersionId(null);
                            }
                          }}
                        >
                          {restoringVersionId === v.id ? "Restaurando…" : "Restaurar"}
                        </Button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}
          </aside>
        </div>

        {/* Modal: Convidar Orientador */}
        {showInviteModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 px-4">
            <div className="w-full max-w-md rounded-[20px] border border-borda bg-paper p-6 shadow-2xl space-y-5">
              <div className="flex items-center justify-between">
                <h2 className="font-display text-xl text-ink">Convidar Orientador</h2>
                <button
                  type="button"
                  onClick={() => setShowInviteModal(false)}
                  className="text-locked hover:text-ink text-xl font-bold cursor-pointer"
                >
                  ✕
                </button>
              </div>

              <div className="space-y-2">
                <div className="text-[13px] font-bold uppercase tracking-wider text-locked">
                  Orientadores atuais ({advisors.length})
                </div>
                {advisors.length === 0 ? (
                  <p className="text-[14px] text-locked">Nenhum orientador convidado ainda.</p>
                ) : (
                  advisors.map((a) => (
                    <StudentCard key={a.advisor_email} label="Orientador">
                      {a.advisor_email}
                    </StudentCard>
                  ))
                )}
              </div>

              <form onSubmit={handleInviteAdvisor} className="space-y-3">
                <input
                  type="email"
                  value={advisorEmail}
                  onChange={(e) => setAdvisorEmail(e.target.value)}
                  placeholder="E-mail do orientador…"
                  required
                  className="w-full h-[44px] rounded-[10px] border border-borda bg-superficie px-3.5 text-[15px] text-ink focus:border-purple"
                />
                <Button type="submit" variant="primary" disabled={!advisorEmail.trim()} className="w-full">
                  Enviar convite
                </Button>
              </form>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
