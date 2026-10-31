"use client";

import "@xyflow/react/dist/style.css";

import { Background, Controls, MarkerType, ReactFlow, type Edge, type Node } from "@xyflow/react";
import { useRouter } from "next/navigation";
import React, { useEffect, useMemo, useState } from "react";
import {
  ApiError,
  api,
  Evidence,
  fetchPdfBlobUrl,
  GAP_STATUS_LABELS,
  Gap,
  getToken,
  MapData,
  MapLink,
  openPdfAtPage,
  RELATION_LABELS,
  STATUS_LABELS,
  TextAnalysisWorkspace,
  uploadDocumentPdf,
} from "@/lib/api";
import { AppHeader } from "@/components/app-header";
import {
  AdvisorBubble,
  AlertBanner,
  Button,
  CheckIcon,
  GapIcon,
  LockIcon,
} from "@/components/ui";

type Status = MapLink["status"];

// Color is never the only cue: stroke style (solid / dashed / dotted) and a text label are always present.
const STATUS_STYLE: Record<Status, { stroke: string; dash?: string }> = {
  confirmed: { stroke: "#5F6E2F" },
  suggested: { stroke: "#4B2A7B", dash: "6 4" },
  rejected: { stroke: "#6F665D", dash: "2 4" },
};

function EdgeStatusPill({ status }: { status: Status }) {
  if (status === "confirmed") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-[6px] bg-done px-2.5 py-0.5 text-[13px] font-medium text-paper">
        <CheckIcon className="h-3.5 w-3.5" />
        <span>{STATUS_LABELS.confirmed}</span>
      </span>
    );
  }
  if (status === "suggested") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-[6px] bg-orange px-2.5 py-0.5 text-[13px] font-medium text-ink">
        <span>{STATUS_LABELS.suggested}</span>
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-[6px] border border-dashed border-locked/60 bg-paper px-2.5 py-0.5 text-[13px] font-medium text-locked">
      <LockIcon className="h-3.5 w-3.5" />
      <span>{STATUS_LABELS.rejected}</span>
    </span>
  );
}

export default function MapView({ id }: { id: string }) {
  const router = useRouter();
  const [data, setData] = useState<MapData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [shown, setShown] = useState<Record<Status, boolean>>({
    confirmed: true,
    suggested: true,
    rejected: false,
  });
  const [showLowConfidence, setShowLowConfidence] = useState(false);
  const [showGaps, setShowGaps] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedGapId, setSelectedGapId] = useState<string | null>(null);
  const [evidence, setEvidence] = useState<Evidence[] | null>(null);
  const [evidenceError, setEvidenceError] = useState<string | null>(null);
  const [deciding, setDeciding] = useState(false);
  const [decidingGap, setDecidingGap] = useState(false);
  const [previewPdf, setPreviewPdf] = useState<{
    url: string;
    title: string;
    page: number;
    quote: string;
    concept: string;
  } | null>(null);
  const [textAnalysis, setTextAnalysis] = useState<TextAnalysisWorkspace | null>(null);
  const [workbenchTab, setWorkbenchTab] = useState<"dissect" | "compare_table">("dissect");
  const [selectedDocId, setSelectedDocId] = useState<string>("");
  const [compareDocAId, setCompareDocAId] = useState<string>("");
  const [compareDocBId, setCompareDocBId] = useState<string>("");
  const [uploadingPdf, setUploadingPdf] = useState<boolean>(false);
  const [pdfTitleInput, setPdfTitleInput] = useState<string>("");
  const [studyAnswers, setStudyAnswers] = useState<Record<string, string>>({});

  async function onPreviewPdf(ev: Evidence) {
    setEvidenceError(null);
    try {
      const url = await fetchPdfBlobUrl(id, ev.document_id, ev.page);
      setPreviewPdf({
        url,
        title: ev.document_title ?? "Documento PDF",
        page: ev.page,
        quote: ev.quote,
        concept: ev.concept,
      });
    } catch (err) {
      setEvidenceError(err instanceof Error ? err.message : "Não foi possível carregar o PDF.");
    }
  }

  async function selectLink(linkId: string) {
    setSelectedId(linkId);
    setSelectedGapId(null);
    setEvidence(null);
    setEvidenceError(null);
    try {
      setEvidence(await api<Evidence[]>(`/projects/${id}/edges/${linkId}/evidence`));
    } catch (err) {
      setEvidenceError(err instanceof Error ? err.message : "Algo deu errado.");
    }
  }

  function selectGap(gapId: string) {
    setSelectedGapId(gapId === selectedGapId ? null : gapId);
    setSelectedId(null);
  }

  async function onOpenPdf(documentId: string, page: number) {
    setEvidenceError(null);
    try {
      await openPdfAtPage(id, documentId, page);
    } catch (err) {
      setEvidenceError(err instanceof Error ? err.message : "Não foi possível abrir o PDF.");
    }
  }

  async function decide(
    linkId: string,
    body: { action: "confirm" | "reject" | "edit"; relation?: string; note?: string }
  ) {
    setDeciding(true);
    setEvidenceError(null);
    try {
      await api<MapLink>(`/projects/${id}/edges/${linkId}`, { method: "PATCH", body });
      setNotice(
        body.action === "reject"
          ? "Ligação rejeitada. Ela não será sugerida novamente."
          : "Ligação confirmada."
      );
      setReloadKey((k) => k + 1);
    } catch (err) {
      setEvidenceError(err instanceof Error ? err.message : "Algo deu errado.");
    } finally {
      setDeciding(false);
    }
  }

  async function decideGap(gapId: string, status: Gap["status"], note?: string) {
    setDecidingGap(true);
    setError(null);
    try {
      await api<Gap>(`/projects/${id}/gaps/${gapId}`, {
        method: "PATCH",
        body: { status, note },
      });
      setNotice(
        status === "adopted_as_problem"
          ? "Lacuna adotada como problema de pesquisa."
          : status === "dismissed"
          ? "Lacuna descartada."
          : "Lacuna reaberta."
      );
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Algo deu errado.");
    } finally {
      setDecidingGap(false);
    }
  }

  useEffect(() => {
    if (!getToken()) {
      router.replace("/entrar");
      return;
    }
    let cancelled = false;
    Promise.all([
      api<MapData>(`/projects/${id}/map`),
      api<TextAnalysisWorkspace>(`/projects/${id}/text-analysis`).catch(() => null),
    ])
      .then(([d, ta]) => {
        if (cancelled) return;
        setData(d);
        if (ta) {
          setTextAnalysis(ta);
          if (ta.document_guides.length > 0 && !selectedDocId) {
            setSelectedDocId(ta.document_guides[0].document_id);
          }
          if (ta.document_guides.length >= 2 && !compareDocAId) {
            setCompareDocAId(ta.document_guides[0].document_id);
            setCompareDocBId(ta.document_guides[1].document_id);
          } else if (ta.document_guides.length === 1 && !compareDocAId) {
            setCompareDocAId(ta.document_guides[0].document_id);
            setCompareDocBId(ta.document_guides[0].document_id);
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
  }, [id, reloadKey, router, selectedDocId, compareDocAId]);

  async function handlePdfUpload(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const fileInput = form.elements.namedItem("pdf_file") as HTMLInputElement | null;
    const file = fileInput?.files?.[0];
    if (!file) {
      setError("Selecione um arquivo PDF para enviar e analisar.");
      return;
    }
    setUploadingPdf(true);
    setError(null);
    setNotice(null);
    try {
      const uploaded = await uploadDocumentPdf(id, file, pdfTitleInput);
      const updatedTa = await api<TextAnalysisWorkspace>(
        `/projects/${id}/documents/${uploaded.id}/dissect`,
        { method: "POST" }
      );
      setTextAnalysis(updatedTa);
      setSelectedDocId(uploaded.id);
      setWorkbenchTab("dissect");
      setPdfTitleInput("");
      form.reset();
      setNotice(
        `PDF “${uploaded.title}” enviado e dissecado com sucesso! Veja o Raio-X Analítico e as passagens verificadas abaixo.`
      );
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao enviar e analisar o PDF.");
    } finally {
      setUploadingPdf(false);
    }
  }

  async function handleDissectExistingDoc(docId: string) {
    setBusy(true);
    setError(null);
    try {
      const updatedTa = await api<TextAnalysisWorkspace>(
        `/projects/${id}/documents/${docId}/dissect`,
        { method: "POST" }
      );
      setTextAnalysis(updatedTa);
      setNotice("Passagens literais verificadas extraídas e classificadas por papel científico.");
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao dissecar documento.");
    } finally {
      setBusy(false);
    }
  }

  const activeDocGuide = useMemo(() => {
    if (!textAnalysis || textAnalysis.document_guides.length === 0) return null;
    return (
      textAnalysis.document_guides.find((d) => d.document_id === selectedDocId) ??
      textAnalysis.document_guides[0]
    );
  }, [textAnalysis, selectedDocId]);

  const docGuideA = useMemo(() => {
    if (!textAnalysis || textAnalysis.document_guides.length === 0) return null;
    return (
      textAnalysis.document_guides.find((d) => d.document_id === compareDocAId) ??
      textAnalysis.document_guides[0]
    );
  }, [textAnalysis, compareDocAId]);

  const docGuideB = useMemo(() => {
    if (!textAnalysis || textAnalysis.document_guides.length === 0) return null;
    return (
      textAnalysis.document_guides.find((d) => d.document_id === compareDocBId) ??
      textAnalysis.document_guides[Math.min(1, textAnalysis.document_guides.length - 1)]
    );
  }, [textAnalysis, compareDocBId]);

  const visibleLinks = useMemo(
    () =>
      (data?.edges ?? []).filter(
        (e) => shown[e.status] && (showLowConfidence || e.display_by_default)
      ),
    [data, shown, showLowConfidence]
  );
  const hiddenLowConfidence = (data?.edges ?? []).filter(
    (e) => !e.display_by_default && shown[e.status]
  ).length;
  const labelOf = useMemo(
    () => new Map((data?.nodes ?? []).map((n) => [n.id, n.label])),
    [data]
  );

  const visibleGaps = useMemo(
    () => (data?.gaps ?? []).filter((g) => g.status !== "dismissed"),
    [data]
  );

  const { nodes, edges } = useMemo(() => {
    const list = data?.nodes ?? [];
    const radius = Math.max(165, list.length * 48);
    const posMap = new Map<string, { x: number; y: number }>();
    const activeLink = visibleLinks.find((l) => l.id === selectedId) ?? null;

    const conceptNodes: Node[] = list.map((n, i) => {
      const angle = (2 * Math.PI * i) / Math.max(list.length, 1);
      const pos = { x: radius * Math.cos(angle), y: radius * Math.sin(angle) };
      posMap.set(n.id, pos);
      const isHighlighted =
        activeLink !== null && (activeLink.source === n.id || activeLink.target === n.id);
      return {
        id: n.id,
        position: pos,
        data: { label: `${n.label} (${n.n_claims})` },
        style: {
          border: isHighlighted ? "2.5px solid #4B2A7B" : "1.5px solid #241E1A",
          boxShadow: isHighlighted ? "0 0 0 3px rgba(75, 42, 123, 0.18)" : "none",
          borderRadius: 10,
          background: "#FFFFFF",
          padding: 10,
          fontSize: 14,
          fontWeight: isHighlighted ? 700 : 500,
          color: "#241E1A",
          width: 185,
        },
      };
    });

    const gapNodes: Node[] = [];
    const gapEdges: Edge[] = [];

    if (showGaps) {
      visibleGaps.forEach((g) => {
        const posA = posMap.get(g.concept_a) || { x: 0, y: 0 };
        const posB = posMap.get(g.concept_b) || { x: 0, y: 0 };
        const midPos = { x: (posA.x + posB.x) / 2, y: (posA.y + posB.y) / 2 };
        const gapNodeId = `gap-${g.id}`;

        gapNodes.push({
          id: gapNodeId,
          position: midPos,
          data: {
            label: `[Lacuna] ${labelOf.get(g.concept_a) ?? g.concept_a} ↔ ${
              labelOf.get(g.concept_b) ?? g.concept_b
            }`,
          },
          style: {
            border: "2px dotted #4B2A7B",
            borderRadius: 10,
            background: "#FFFFFF",
            padding: 8,
            fontSize: 13,
            fontWeight: 500,
            color: "#4B2A7B",
            width: 170,
            cursor: "pointer",
          },
        });

        gapEdges.push(
          {
            id: `edge-${gapNodeId}-a`,
            source: g.concept_a,
            target: gapNodeId,
            style: { stroke: "#4B2A7B", strokeWidth: 1.5, strokeDasharray: "2 4" },
          },
          {
            id: `edge-${gapNodeId}-b`,
            source: gapNodeId,
            target: g.concept_b,
            style: { stroke: "#4B2A7B", strokeWidth: 1.5, strokeDasharray: "2 4" },
          }
        );
      });
    }

    const relationEdges: Edge[] = visibleLinks.map((e) => {
      const s = STATUS_STYLE[e.status];
      const isSelectedEdge = e.id === selectedId;
      return {
        id: e.id,
        source: e.source,
        target: e.target,
        label: `${RELATION_LABELS[e.relation] ?? e.relation} · ${STATUS_LABELS[
          e.status
        ].toLowerCase()}`,
        markerEnd: { type: MarkerType.ArrowClosed, color: s.stroke },
        style: {
          stroke: s.stroke,
          strokeWidth: isSelectedEdge ? 3.5 : 2,
          strokeDasharray: s.dash,
        },
        labelStyle: { fontSize: 12, fill: "#241E1A", fontWeight: isSelectedEdge ? 700 : 500 },
        labelBgStyle: { fill: "#F6EEDC" },
      };
    });

    return {
      nodes: [...conceptNodes, ...gapNodes],
      edges: [...relationEdges, ...gapEdges],
    };
  }, [data, visibleLinks, visibleGaps, showGaps, labelOf, selectedId]);

  async function onSuggest() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const r = await api<{ created: number }>(`/projects/${id}/map/suggest`, { method: "POST" });
      setNotice(
        r.created === 0
          ? "Nenhuma ligação nova encontrada nas evidências disponíveis."
          : `${r.created} ligação(ões) sugerida(s). Revise cada uma antes de confirmar.`
      );
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Algo deu errado.");
    } finally {
      setBusy(false);
    }
  }

  async function onDetectGaps() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const r = await api<{ created: number }>(`/projects/${id}/gaps/detect`, { method: "POST" });
      setNotice(
        r.created === 0
          ? "Nenhuma nova lacuna identificada para os conceitos atuais."
          : `${r.created} lacuna(s) identificada(s) após buscas externas nas bases.`
      );
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Algo deu errado.");
    } finally {
      setBusy(false);
    }
  }

  const empty = data !== null && data.nodes.length === 0;

  return (
    <div className="min-h-screen flex flex-col bg-paper text-ink">
      <AppHeader projectId={id} />

      <main className="mx-auto w-full max-w-[1440px] flex-1 px-6 py-8 sm:px-10 space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-borda pb-5">
          <div>
            <h1 className="font-display text-3xl sm:text-[36px] text-ink">Mapa de conhecimento</h1>
            <p className="mt-1 text-[15px] text-locked">
              Conceitos extraídos da bibliografia e ligações apoiadas em trechos literais verificados.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button type="button" variant="secondary" onClick={onDetectGaps} disabled={busy}>
              {busy ? "Buscando…" : "Buscar lacunas"}
            </Button>
            <Button type="button" variant="primary" onClick={onSuggest} disabled={busy}>
              {busy ? "Analisando…" : "Sugerir ligações"}
            </Button>
          </div>
        </div>

        {error && <AlertBanner variant="error">{error}</AlertBanner>}
        {notice && <AlertBanner variant="notice">{notice}</AlertBanner>}

        {/* Bancada de Upload de PDF + Análise Guiada e Confronto Lado a Lado */}
        <section
          aria-label="Bancada de upload e análise guiada de PDFs"
          className="rounded-[16px] border border-borda bg-superficie p-6 space-y-5"
        >
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-borda pb-4">
            <div>
              <h2 className="font-display text-2xl text-ink">
                Bancada de análise guiada e confronto de textos
              </h2>
              <p className="mt-0.5 text-[14px] text-locked">
                Envie um PDF para o Orientador dissecar a tese, classificar as evidências por papel científico e comparar autores lado a lado.
              </p>
            </div>

            {/* Formulário rápido de Upload de PDF */}
            <form
              onSubmit={handlePdfUpload}
              className="flex flex-wrap items-center gap-2.5"
            >
              <input
                type="text"
                value={pdfTitleInput}
                onChange={(e) => setPdfTitleInput(e.target.value)}
                placeholder="Título do artigo (opcional)"
                className="h-[42px] rounded-[10px] border border-borda bg-paper/50 px-3 text-[14px] text-ink"
              />
              <input
                type="file"
                name="pdf_file"
                accept="application/pdf"
                aria-label="Arquivo PDF para análise"
                className="text-[13px] text-ink file:mr-2 file:rounded-[8px] file:border file:border-purple file:bg-skipped-bg file:px-3 file:py-1.5 file:text-[13px] file:font-bold file:text-purple file:cursor-pointer"
              />
              <Button type="submit" variant="secondary" disabled={uploadingPdf}>
                {uploadingPdf ? "Dissecando PDF…" : "Enviar e analisar PDF"}
              </Button>
            </form>
          </div>

          {textAnalysis && textAnalysis.document_guides.length > 0 && (
            <div className="space-y-4">
              {/* Abas da Bancada */}
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => setWorkbenchTab("dissect")}
                    className={`min-h-[40px] rounded-[8px] px-3.5 text-[14px] font-bold transition cursor-pointer ${
                      workbenchTab === "dissect"
                        ? "bg-purple text-paper"
                        : "border border-borda bg-paper text-ink hover:bg-skipped-bg/40"
                    }`}
                  >
                    1. Guia de Leitura e Dissecação ({textAnalysis.document_guides.length} PDFs)
                  </button>
                  <button
                    type="button"
                    onClick={() => setWorkbenchTab("compare_table")}
                    className={`min-h-[40px] rounded-[8px] px-3.5 text-[14px] font-bold transition cursor-pointer ${
                      workbenchTab === "compare_table"
                        ? "bg-purple text-paper"
                        : "border border-borda bg-paper text-ink hover:bg-skipped-bg/40"
                    }`}
                  >
                    2. Mesa de Confronto Lado a Lado (PDF 1 × PDF 2)
                  </button>
                </div>

                <button
                  type="button"
                  onClick={() => router.push(`/projetos/${id}/editor`)}
                  className="text-[14px] font-bold text-purple underline cursor-pointer"
                >
                  Ir para o Costureiro Dialético no Editor →
                </button>
              </div>

              {/* ABA 1: Dissecação e Estudo Dirigido do PDF */}
              {workbenchTab === "dissect" && activeDocGuide && (
                <div className="grid grid-cols-1 gap-5 lg:grid-cols-12 items-start">
                  {/* Coluna Esquerda: Seleção do PDF + Tese + Roteiro Socrático (5 cols) */}
                  <div className="lg:col-span-5 space-y-4 rounded-[12px] border border-borda bg-paper/50 p-4">
                    <div>
                      <label className="block text-[12px] font-bold uppercase tracking-wider text-locked mb-1">
                        Artigo em dissecação:
                      </label>
                      <select
                        aria-label="Selecionar artigo para dissecação"
                        value={activeDocGuide.document_id}
                        onChange={(e) => setSelectedDocId(e.target.value)}
                        className="w-full h-[42px] rounded-[10px] border border-borda bg-superficie px-3 text-[15px] font-bold text-ink"
                      >
                        {textAnalysis.document_guides.map((dg) => (
                          <option key={dg.document_id} value={dg.document_id}>
                            {dg.title} ({dg.year ?? "s.d."}) — {dg.claims_count} trechos verificados
                          </option>
                        ))}
                      </select>
                    </div>

                    {activeDocGuide.claims_count === 0 && (
                      <div className="rounded-[10px] border border-purple bg-superficie p-3 flex items-center justify-between gap-2">
                        <span className="text-[13px] text-ink">
                          Este PDF já foi lido, mas ainda não teve seus trechos classificados.
                        </span>
                        <Button
                          type="button"
                          variant="secondary"
                          disabled={busy}
                          onClick={() => void handleDissectExistingDoc(activeDocGuide.document_id)}
                        >
                          Extrair trechos
                        </Button>
                      </div>
                    )}

                    {/* Raio-X da Tese Central */}
                    <div className="rounded-[10px] border border-borda bg-superficie p-3.5 space-y-1">
                      <span className="text-[12px] font-bold uppercase tracking-wider text-purple">
                        Tese central extraída do texto
                      </span>
                      <p className="text-[15px] font-medium text-ink leading-relaxed">
                        {activeDocGuide.core_thesis}
                      </p>
                    </div>

                    {/* Pontes com outros PDFs */}
                    {activeDocGuide.shared_bridges.length > 0 && (
                      <div className="rounded-[10px] border border-done bg-superficie p-3.5 space-y-1.5">
                        <span className="text-[12px] font-bold uppercase tracking-wider text-done">
                          Raio-X de Impacto · Conexões com sua biblioteca
                        </span>
                        {activeDocGuide.shared_bridges.map((br, i) => (
                          <p key={i} className="text-[14px] text-ink">
                            Compartilha o conceito <strong>{br.concept_label}</strong> com{" "}
                            <em>{br.other_document_title}</em>.
                          </p>
                        ))}
                      </div>
                    )}

                    {/* Estudo Dirigido Socrático (Perguntas + Anotação do Aluno) */}
                    <AdvisorBubble label="Estudo dirigido: perguntas para você analisar o texto">
                      <div className="space-y-2.5 text-[14px]">
                        {activeDocGuide.study_questions.map((q, idx) => (
                          <div key={idx} className="space-y-1">
                            <p>{q}</p>
                            <input
                              type="text"
                              value={
                                studyAnswers[`${activeDocGuide.document_id}_${idx}`] ?? ""
                              }
                              onChange={(e) =>
                                setStudyAnswers((prev) => ({
                                  ...prev,
                                  [`${activeDocGuide.document_id}_${idx}`]: e.target.value,
                                }))
                              }
                              placeholder="Anote sua resposta crítica aqui…"
                              className="w-full h-[36px] rounded-[8px] border border-paper/40 bg-paper px-2.5 text-[13px] text-ink"
                            />
                          </div>
                        ))}
                      </div>
                    </AdvisorBubble>
                  </div>

                  {/* Coluna Direita: Passagens Classificadas por Papel Científico (7 cols) */}
                  <div className="lg:col-span-7 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-[13px] font-bold uppercase tracking-wider text-locked">
                        Anatomia dos trechos literais verificados ({activeDocGuide.passages.length})
                      </span>
                    </div>

                    {activeDocGuide.passages.map((p) => (
                      <div
                        key={p.id}
                        className="rounded-[12px] border border-borda bg-paper/40 p-4 space-y-2.5"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span
                              className={`rounded-[6px] px-2.5 py-0.5 text-[12px] font-bold uppercase ${
                                p.role_code === "evidencia_empirica"
                                  ? "bg-done text-paper"
                                  : p.role_code === "limite_contraponto"
                                  ? "bg-orange text-ink"
                                  : "bg-purple text-paper"
                              }`}
                            >
                              {p.role_label}
                            </span>
                            <span className="text-[13px] font-bold text-ink">
                              {p.concepts.map((c) => c.label).join(", ")}
                            </span>
                          </div>
                          <span className="text-[13px] font-bold text-purple">
                            {p.citation_ref}
                          </span>
                        </div>

                        <blockquote className="font-serif-academic text-[16px] leading-relaxed text-ink">
                          <mark className="mark-orange">{p.quote}</mark>
                        </blockquote>

                        <div className="rounded-[8px] border border-borda bg-superficie p-2.5 text-[13px] text-ink">
                          <strong className="text-purple">Guia de leitura:</strong> {p.reading_tip}
                        </div>

                        <div className="flex flex-wrap items-center justify-between gap-2 pt-1 text-[13px]">
                          <button
                            type="button"
                            onClick={() =>
                              void onPreviewPdf({
                                side: "source",
                                concept: p.concepts[0]?.label ?? "Conceito",
                                statement: p.statement,
                                document_id: p.document_id,
                                document_title: p.document_title,
                                page: p.page_no,
                                quote: p.quote,
                                context_before: "",
                                context_after: "",
                                has_pdf: true,
                              })
                            }
                            className="font-bold text-purple underline cursor-pointer"
                          >
                            Inspecionar no PDF original (pág. {p.page_no})
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* ABA 2: Tabela de Confronto Lado a Lado (PDF 1 × PDF 2) */}
              {workbenchTab === "compare_table" && docGuideA && docGuideB && (
                <div className="space-y-4">
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div>
                      <label className="block text-[12px] font-bold uppercase tracking-wider text-locked mb-1">
                        Texto / PDF 1:
                      </label>
                      <select
                        aria-label="Selecionar Texto 1 para confronto"
                        value={docGuideA.document_id}
                        onChange={(e) => setCompareDocAId(e.target.value)}
                        className="w-full h-[40px] rounded-[8px] border border-borda bg-paper px-3 text-[14px] font-bold text-ink"
                      >
                        {textAnalysis.document_guides.map((dg) => (
                          <option key={dg.document_id} value={dg.document_id}>
                            {dg.title} ({dg.year ?? "s.d."})
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="block text-[12px] font-bold uppercase tracking-wider text-locked mb-1">
                        Texto / PDF 2:
                      </label>
                      <select
                        aria-label="Selecionar Texto 2 para confronto"
                        value={docGuideB.document_id}
                        onChange={(e) => setCompareDocBId(e.target.value)}
                        className="w-full h-[40px] rounded-[8px] border border-borda bg-paper px-3 text-[14px] font-bold text-ink"
                      >
                        {textAnalysis.document_guides.map((dg) => (
                          <option key={dg.document_id} value={dg.document_id}>
                            {dg.title} ({dg.year ?? "s.d."})
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="overflow-x-auto rounded-[12px] border border-borda">
                    <table className="w-full text-left border-collapse text-[14px]">
                      <thead>
                        <tr className="border-b border-borda bg-paper text-[12px] font-bold uppercase tracking-wider text-locked">
                          <th className="p-3.5 w-1/5">Lente de Análise</th>
                          <th className="p-3.5 w-[30%] text-ink">
                            PDF 1: {docGuideA.title} ({docGuideA.year ?? "s.d."})
                          </th>
                          <th className="p-3.5 w-[30%] text-ink">
                            PDF 2: {docGuideB.title} ({docGuideB.year ?? "s.d."})
                          </th>
                          <th className="p-3.5 w-1/5 text-purple">
                            Diagnóstico do Orientador
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-borda bg-superficie">
                        <tr>
                          <td className="p-3.5 font-bold text-ink">
                            1. Tese / Como define o conceito
                          </td>
                          <td className="p-3.5 font-serif-academic">
                            {docGuideA.passages[0] ? (
                              <>
                                <mark className="mark-orange">
                                  “{docGuideA.passages[0].quote}”
                                </mark>{" "}
                                <span className="text-[12px] font-sans text-locked">
                                  (p. {docGuideA.passages[0].page_no})
                                </span>
                              </>
                            ) : (
                              docGuideA.core_thesis
                            )}
                          </td>
                          <td className="p-3.5 font-serif-academic">
                            {docGuideB.passages[0] ? (
                              <>
                                <mark className="mark-orange">
                                  “{docGuideB.passages[0].quote}”
                                </mark>{" "}
                                <span className="text-[12px] font-sans text-locked">
                                  (p. {docGuideB.passages[0].page_no})
                                </span>
                              </>
                            ) : (
                              docGuideB.core_thesis
                            )}
                          </td>
                          <td className="p-3.5 text-[13px] text-ink">
                            Use o primeiro para fundamentar o conceito-base e o segundo para expandir o mecanismo observado.
                          </td>
                        </tr>

                        <tr>
                          <td className="p-3.5 font-bold text-ink">
                            2. Papel Científico Predominante
                          </td>
                          <td className="p-3.5">
                            <span className="rounded bg-purple px-2 py-0.5 text-[12px] font-bold text-paper">
                              {docGuideA.passages[0]?.role_label ?? "Base Teórica"}
                            </span>
                          </td>
                          <td className="p-3.5">
                            <span className="rounded bg-done px-2 py-0.5 text-[12px] font-bold text-paper">
                              {docGuideB.passages[0]?.role_label ?? "Achado Complementar"}
                            </span>
                          </td>
                          <td className="p-3.5 text-[13px] text-ink">
                            Combinar papéis distintos evita o “fichamento em vagão de trem” no capítulo.
                          </td>
                        </tr>

                        <tr>
                          <td className="p-3.5 font-bold text-ink">
                            3. Conceitos em Jogo
                          </td>
                          <td className="p-3.5">
                            {docGuideA.concepts.map((c) => c.label).join(", ") || "—"}
                          </td>
                          <td className="p-3.5">
                            {docGuideB.concepts.map((c) => c.label).join(", ") || "—"}
                          </td>
                          <td className="p-3.5 text-[13px] text-purple font-bold">
                            Pergunta Socrática: Qual é o elo causal entre os conceitos de {docGuideA.title} e os de {docGuideB.title} no recorte do seu TCC?
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </section>

        {data === null && !error && (
          <p className="py-8 text-[15px] text-locked">Carregando mapa de conhecimento…</p>
        )}

        {empty && (
          <div className="rounded-[16px] border border-borda bg-superficie p-8 text-[15px] text-locked">
            Ainda não há conceitos neste projeto. Envie PDFs para a biblioteca ou busque artigos por DOI para gerar o mapa.
          </div>
        )}

        {data && !empty && (
          <>
            {/* Barra de Filtros */}
            <section
              aria-label="Filtros do mapa"
              className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-[12px] border border-borda bg-superficie px-5 py-3 text-[15px]"
            >
              <span className="text-[13px] font-bold uppercase tracking-wider text-locked">
                Exibir no grafo:
              </span>
              {(Object.keys(STATUS_LABELS) as Status[]).map((s) => (
                <label
                  key={s}
                  className="flex min-h-[44px] items-center gap-2 font-medium text-ink cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={shown[s]}
                    onChange={(e) => setShown({ ...shown, [s]: e.target.checked })}
                    className="h-4 w-4 accent-purple"
                  />
                  <span>{STATUS_LABELS[s]}</span>
                </label>
              ))}
              <label className="flex min-h-[44px] items-center gap-2 font-medium text-ink cursor-pointer">
                <input
                  type="checkbox"
                  checked={showLowConfidence}
                  onChange={(e) => setShowLowConfidence(e.target.checked)}
                  className="h-4 w-4 accent-purple"
                />
                <span>
                  Baixa confiança{hiddenLowConfidence > 0 ? ` (${hiddenLowConfidence} ocultas)` : ""}
                </span>
              </label>
              <label className="flex min-h-[44px] items-center gap-2 font-bold text-purple cursor-pointer">
                <input
                  type="checkbox"
                  checked={showGaps}
                  onChange={(e) => setShowGaps(e.target.checked)}
                  className="h-4 w-4 accent-purple"
                />
                <span>Lacunas ({visibleGaps.length})</span>
              </label>
            </section>

            {/* Layout em duas colunas: Grafo + Lacunas (esquerda) e Ligações + Evidência (direita) */}
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 items-start">
              <div className="lg:col-span-7 space-y-6">
                <section
                  aria-label="Grafo de conceitos"
                  className="hidden h-[500px] overflow-hidden rounded-[16px] border border-borda bg-superficie md:block"
                >
                  <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    fitView
                    nodesConnectable={false}
                    onEdgeClick={(_, edge) => {
                      if (!edge.id.startsWith("edge-gap-")) {
                        void selectLink(edge.id);
                      }
                    }}
                    onNodeClick={(_, node) => {
                      if (node.id.startsWith("gap-")) {
                        selectGap(node.id.replace("gap-", ""));
                      }
                    }}
                    proOptions={{ hideAttribution: true }}
                  >
                    <Background color="#D9CDB4" gap={20} />
                    <Controls showInteractive={false} />
                  </ReactFlow>
                </section>

                {/* Seção de Lacunas de Pesquisa */}
                {(data.gaps ?? []).length > 0 && (
                  <section
                    aria-label="Lacunas de pesquisa"
                    className="rounded-[16px] border border-borda bg-superficie p-6 space-y-4"
                  >
                    <div className="flex items-center gap-2">
                      <GapIcon className="h-5 w-5 text-purple" />
                      <h2 className="font-display text-2xl text-ink">
                        Lacunas de pesquisa ({(data.gaps ?? []).length})
                      </h2>
                    </div>

                    <ul className="space-y-3 text-[15px]">
                      {(data.gaps ?? []).map((g) => (
                        <li
                          key={g.id}
                          className="rounded-[12px] border-2 border-dotted border-purple bg-paper/50 p-4 space-y-2"
                        >
                          <div className="flex flex-wrap items-baseline justify-between gap-2">
                            <p className="font-bold text-ink">
                              {labelOf.get(g.concept_a) ?? g.concept_a}{" "}
                              <span className="text-purple">↔</span>{" "}
                              {labelOf.get(g.concept_b) ?? g.concept_b}
                            </p>
                            <span className="rounded-[6px] bg-skipped-bg px-2.5 py-0.5 text-[13px] font-bold uppercase tracking-wider text-purple">
                              {GAP_STATUS_LABELS[g.status]}
                            </span>
                          </div>
                          {g.note && <p className="text-ink leading-relaxed">{g.note}</p>}
                          <button
                            type="button"
                            onClick={() => selectGap(g.id)}
                            aria-expanded={selectedGapId === g.id}
                            className="inline-flex min-h-[44px] items-center font-bold text-purple underline cursor-pointer"
                          >
                            {selectedGapId === g.id
                              ? "Ocultar buscas feitas"
                              : "Ver buscas externas feitas"}
                          </button>
                          {selectedGapId === g.id && (
                            <GapPanel
                              gap={g}
                              deciding={decidingGap}
                              onDecide={(status, note) => void decideGap(g.id, status, note)}
                            />
                          )}
                        </li>
                      ))}
                    </ul>
                  </section>
                )}
              </div>

              {/* Coluna lateral: Lista de Ligações e Painel de Evidência */}
              <section
                aria-label="Lista de ligações"
                className="lg:col-span-5 rounded-[16px] border border-borda bg-superficie p-6 space-y-4"
              >
                <h2 className="font-display text-2xl text-ink">
                  Ligações ({visibleLinks.length})
                </h2>

                {visibleLinks.length === 0 ? (
                  <p className="text-[15px] text-locked">
                    Nenhuma ligação para os filtros escolhidos.
                  </p>
                ) : (
                  <ul className="space-y-3 text-[15px]">
                    {visibleLinks.map((e) => (
                      <li
                        key={e.id}
                        className={`rounded-[12px] border p-4 transition ${
                          selectedId === e.id
                            ? "border-2 border-purple bg-paper/40"
                            : "border-borda bg-superficie"
                        }`}
                      >
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <p className="text-[15px] leading-snug text-ink">
                            <strong>{labelOf.get(e.source)}</strong>{" "}
                            <span className="text-locked">
                              {RELATION_LABELS[e.relation] ?? e.relation}
                            </span>{" "}
                            <strong>{labelOf.get(e.target)}</strong>
                          </p>
                          <EdgeStatusPill status={e.status} />
                        </div>

                        <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[14px] text-locked">
                          <span>
                            {e.confidence != null
                              ? `Confiança ${Math.round(e.confidence * 100)}%`
                              : ""}
                            {!e.display_by_default ? " · baixa confiança" : ""}
                          </span>

                          <button
                            type="button"
                            onClick={() =>
                              selectedId === e.id ? setSelectedId(null) : void selectLink(e.id)
                            }
                            aria-expanded={selectedId === e.id}
                            className="inline-flex min-h-[44px] items-center font-bold text-purple underline cursor-pointer"
                          >
                            {selectedId === e.id ? "Ocultar evidência" : "Ver evidência"}
                          </button>
                        </div>

                        {selectedId === e.id && (
                          <EvidencePanel
                            link={e}
                            evidence={evidence}
                            error={evidenceError}
                            deciding={deciding}
                            onOpenPdf={onOpenPdf}
                            onPreviewPdf={(ev) => void onPreviewPdf(ev)}
                            onDecide={(body) => void decide(e.id, body)}
                          />
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </div>
          </>
        )}

        {/* Modal de Leitura Lado a Lado: Trecho Verificado × PDF Original */}
        {previewPdf && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/60 p-4 sm:p-6">
            <div
              role="dialog"
              aria-modal="true"
              aria-label="Visualização lado a lado do PDF"
              className="flex h-[88vh] w-full max-w-6xl flex-col overflow-hidden rounded-[16px] border border-borda bg-paper shadow-xl"
            >
              <div className="flex items-center justify-between border-b border-borda bg-superficie px-6 py-4">
                <div>
                  <span className="text-[13px] font-bold uppercase tracking-wider text-purple">
                    Inspeção de Fonte Original · Página {previewPdf.page}
                  </span>
                  <h3 className="font-display text-xl text-ink">{previewPdf.title}</h3>
                </div>
                <button
                  type="button"
                  onClick={() => setPreviewPdf(null)}
                  className="inline-flex min-h-[44px] items-center rounded-[10px] border border-borda px-4 text-[15px] font-bold text-ink hover:bg-paper cursor-pointer"
                >
                  Fechar visualização
                </button>
              </div>

              <div className="grid flex-1 grid-cols-1 lg:grid-cols-12 overflow-hidden">
                <div className="lg:col-span-4 border-b lg:border-b-0 lg:border-r border-borda p-6 overflow-y-auto space-y-4 bg-paper">
                  <span className="text-[13px] font-bold uppercase tracking-wider text-locked">
                    Trecho literal verificado ({previewPdf.concept})
                  </span>
                  <blockquote className="rounded-[12px] border border-borda bg-superficie p-4 font-serif-academic text-[18px] leading-[1.6] text-ink">
                    <mark className="mark-orange font-medium">{previewPdf.quote}</mark>
                  </blockquote>
                  <p className="text-[14px] text-locked leading-relaxed">
                    Este trecho foi conferido por código determinístico contra o texto extraído da página {previewPdf.page} do PDF original ao lado.
                  </p>
                </div>

                <div className="lg:col-span-8 bg-superficie h-full">
                  <iframe
                    src={previewPdf.url}
                    title={`${previewPdf.title} - página ${previewPdf.page}`}
                    className="h-full w-full border-0"
                  />
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

function GapPanel({
  gap,
  deciding,
  onDecide,
}: {
  gap: Gap;
  deciding: boolean;
  onDecide: (status: Gap["status"], note?: string) => void;
}) {
  const [note, setNote] = useState(gap.note ?? "");
  return (
    <div className="mt-3 space-y-4 border-t border-borda pt-4 text-[15px]" aria-live="polite">
      <div className="space-y-2">
        <p className="text-[13px] font-bold uppercase tracking-wider text-locked">
          Buscas externas realizadas
        </p>
        <ul className="space-y-2">
          {gap.searches.map((s, idx) => (
            <li key={idx} className="rounded-[10px] border border-borda bg-superficie p-3.5">
              <div className="flex items-center justify-between">
                <span className="text-[13px] font-bold uppercase tracking-wider text-ink">
                  {s.source === "openalex" ? "OpenAlex" : "Semantic Scholar"}
                </span>
                <span
                  className={`text-[14px] font-bold ${
                    s.status === "ok" ? "text-done" : "text-purple"
                  }`}
                >
                  {s.status === "ok" ? `${s.total ?? 0} resultado(s)` : "Falha na busca"}
                </span>
              </div>
              <p className="mt-1 font-mono text-[14px] text-locked">Busca: {s.query}</p>
              {s.results && s.results.length > 0 && (
                <ul className="mt-2 list-disc pl-5 space-y-1 text-[14px]">
                  {s.results.map((r, rIdx) => (
                    <li key={rIdx}>
                      <span>{r.title}</span>{" "}
                      {r.year && <span className="text-locked">({r.year})</span>}
                      {r.doi && (
                        <a
                          href={`https://doi.org/${r.doi}`}
                          target="_blank"
                          rel="noreferrer"
                          className="ml-1.5 font-bold text-purple underline"
                        >
                          DOI
                        </a>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      </div>

      <div className="space-y-3 border-t border-borda pt-3">
        <p className="text-[13px] font-bold uppercase tracking-wider text-locked">
          Decisão sobre a lacuna
        </p>
        <label className="block">
          <span className="sr-only">Anotação pessoal</span>
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            maxLength={500}
            placeholder="Anotação pessoal sobre a lacuna (opcional)"
            className="w-full h-[46px] rounded-[10px] border border-borda bg-superficie px-3.5 text-[15px] text-ink"
          />
        </label>
        <div className="flex flex-wrap items-center gap-2.5">
          {gap.status !== "adopted_as_problem" && (
            <Button
              type="button"
              variant="secondary"
              disabled={deciding}
              onClick={() => onDecide("adopted_as_problem", note)}
            >
              Adotar como problema de pesquisa
            </Button>
          )}
          {gap.status !== "dismissed" && (
            <Button
              type="button"
              variant="secondary"
              disabled={deciding}
              onClick={() => onDecide("dismissed", note)}
            >
              Descartar lacuna
            </Button>
          )}
          {gap.status !== "open" && (
            <Button
              type="button"
              variant="secondary"
              disabled={deciding}
              onClick={() => onDecide("open", note)}
            >
              Reabrir como aberta
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

function EvidencePanel({
  link,
  evidence,
  error,
  deciding,
  onOpenPdf,
  onPreviewPdf,
  onDecide,
}: {
  link: MapLink;
  evidence: Evidence[] | null;
  error: string | null;
  deciding: boolean;
  onOpenPdf: (documentId: string, page: number) => void;
  onPreviewPdf: (ev: Evidence) => void;
  onDecide: (body: { action: "confirm" | "reject" | "edit"; relation?: string; note?: string }) => void;
}) {
  const [relation, setRelation] = useState(link.relation);
  const [note, setNote] = useState("");
  return (
    <div className="mt-4 space-y-4 border-t border-borda pt-4 text-[15px]" aria-live="polite">
      {link.rationale && link.status === "suggested" && (
        <p className="text-ink leading-relaxed">
          <strong className="text-purple">Justificativa da sugestão:</strong> {link.rationale}
        </p>
      )}
      {error && <AlertBanner variant="error">{error}</AlertBanner>}
      {evidence === null && !error && (
        <p className="text-locked">Carregando evidência literal…</p>
      )}
      {evidence?.map((ev) => (
        <figure
          key={ev.side}
          className="rounded-[12px] border border-borda bg-paper p-4 space-y-2"
        >
          <figcaption className="text-[13px] font-bold uppercase tracking-wider text-locked">
            {ev.side === "source" ? "Evidência de origem" : "Evidência de destino"} · {ev.concept}
          </figcaption>
          <blockquote className="font-serif-academic text-[17px] leading-[1.6] text-ink">
            <span className="text-locked">{ev.context_before} </span>
            <mark className="mark-orange font-medium">{ev.quote}</mark>
            <span className="text-locked"> {ev.context_after}</span>
          </blockquote>
          <p className="text-[14px] font-medium text-locked">
            {ev.document_title ?? "Documento"} · página {ev.page}
          </p>
          {ev.has_pdf ? (
            <div className="flex flex-wrap items-center gap-4">
              <button
                type="button"
                onClick={() => onPreviewPdf(ev)}
                className="inline-flex min-h-[44px] items-center text-[15px] font-bold text-purple underline cursor-pointer"
              >
                Inspecionar PDF lado a lado (pág. {ev.page})
              </button>
              <button
                type="button"
                onClick={() => onOpenPdf(ev.document_id, ev.page)}
                className="inline-flex min-h-[44px] items-center text-[14px] font-medium text-locked underline cursor-pointer"
              >
                Abrir PDF na página {ev.page}
              </button>
            </div>
          ) : (
            <p className="text-[14px] text-locked">
              Documento sem PDF anexado (apenas metadados).
            </p>
          )}
        </figure>
      ))}

      <div className="space-y-3 border-t border-borda pt-3">
        <p className="text-[13px] font-bold uppercase tracking-wider text-locked">Sua decisão</p>
        <div className="flex flex-wrap items-center gap-2.5">
          <Button
            type="button"
            variant="secondary"
            disabled={deciding || link.status === "confirmed"}
            onClick={() => onDecide({ action: "confirm" })}
          >
            Confirmar
          </Button>
          <label className="flex items-center gap-2">
            <span className="sr-only">Tipo de relação</span>
            <select
              value={relation}
              onChange={(e) => setRelation(e.target.value)}
              className="h-[44px] rounded-[10px] border border-borda bg-superficie px-3 text-[15px] text-ink"
            >
              {Object.entries(RELATION_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <Button
            type="button"
            variant="secondary"
            disabled={deciding || relation === link.relation}
            onClick={() => onDecide({ action: "edit", relation })}
          >
            Editar tipo
          </Button>
        </div>

        {link.status !== "rejected" && (
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5">
            <label className="flex-1">
              <span className="sr-only">Motivo da rejeição (opcional)</span>
              <input
                value={note}
                onChange={(e) => setNote(e.target.value)}
                maxLength={500}
                placeholder="Motivo da rejeição (opcional)"
                className="w-full h-[44px] rounded-[10px] border border-borda bg-superficie px-3.5 text-[15px] text-ink"
              />
            </label>
            <Button
              type="button"
              variant="secondary"
              disabled={deciding}
              onClick={() => onDecide({ action: "reject", note: note || undefined })}
            >
              Rejeitar
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
