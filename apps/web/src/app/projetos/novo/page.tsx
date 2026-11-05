"use client";

import { useRouter } from "next/navigation";
import React, { useCallback, useRef, useState } from "react";
import { ApiError, api, getToken, uploadDocumentPdf, WORK_LABELS } from "@/lib/api";
import { AppHeader } from "@/components/app-header";
import { AlertBanner, Button } from "@/components/ui";

// ── Types ──────────────────────────────────────────────────────────────────────

type Step = 1 | 2 | 3;

interface ProjectDraft {
  title: string;
  work: string;
  institution: string;
  citation_style: string;
  deadline: string;
  weekly_hours: string;
}

interface RefEntry {
  id: string; // local uuid
  raw: string; // raw pasted text OR filename
  type: "text" | "pdf";
  file?: File;
  status: "pending" | "processing" | "done" | "error";
  errorMsg?: string;
  result?: { id: string; title: string };
}

// ── Constants ──────────────────────────────────────────────────────────────────

const CITATION_STYLES = [
  { value: "abnt", label: "ABNT (Brasil)" },
  { value: "apa", label: "APA 7ª ed." },
  { value: "vancouver", label: "Vancouver" },
  { value: "chicago", label: "Chicago" },
  { value: "mla", label: "MLA" },
];

const inputCls =
  "mt-1.5 w-full h-[46px] rounded-[10px] border border-borda bg-superficie px-3.5 text-[15px] text-ink focus:border-purple outline-none transition";

const selectCls =
  "mt-1.5 w-full h-[46px] rounded-[10px] border border-borda bg-superficie px-3.5 text-[15px] text-ink focus:border-purple outline-none transition";

// ── Step indicator ─────────────────────────────────────────────────────────────

function StepDots({ current, total }: { current: number; total: number }) {
  return (
    <div className="flex items-center gap-3" role="list" aria-label="Etapas do assistente">
      {Array.from({ length: total }, (_, i) => {
        const n = i + 1;
        const done = n < current;
        const active = n === current;
        return (
          <div
            key={n}
            role="listitem"
            aria-current={active ? "step" : undefined}
            className={[
              "flex h-8 w-8 items-center justify-center rounded-full text-[14px] font-bold transition-all",
              done
                ? "bg-done text-paper"
                : active
                ? "bg-purple text-paper ring-4 ring-purple/20"
                : "border-2 border-borda text-locked",
            ].join(" ")}
          >
            {done ? (
              <svg viewBox="0 0 16 16" fill="none" className="h-4 w-4">
                <path d="M3 8.5l3 3 7-7" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            ) : (
              n
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Ref drag-and-drop zone ─────────────────────────────────────────────────────

function RefDropZone({ onFiles }: { onFiles: (files: File[]) => void }) {
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label="Arraste PDFs aqui ou clique para selecionar"
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragEnter={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        const files = Array.from(e.dataTransfer.files).filter((f) => f.type === "application/pdf");
        if (files.length) onFiles(files);
      }}
      onClick={() => inputRef.current?.click()}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") inputRef.current?.click(); }}
      className={[
        "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-[12px] border-2 border-dashed px-6 py-8 text-center transition select-none",
        dragOver
          ? "border-purple bg-skipped-bg/60 scale-[1.01]"
          : "border-borda bg-paper/40 hover:border-purple/60 hover:bg-skipped-bg/20",
      ].join(" ")}
    >
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        multiple
        className="sr-only"
        onChange={(e) => {
          const files = Array.from(e.target.files ?? []).filter(
            (f) => f.type === "application/pdf"
          );
          if (files.length) onFiles(files);
          e.target.value = "";
        }}
      />
      {dragOver ? (
        <>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" className="h-9 w-9 text-purple">
            <path d="M12 16V4m0 0L8 8m4-4l4 4" />
            <rect x="3" y="16" width="18" height="5" rx="2" />
          </svg>
          <span className="text-[15px] font-bold text-purple">Solte para adicionar</span>
        </>
      ) : (
        <>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" className="h-9 w-9 text-locked">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="12" y1="18" x2="12" y2="12" />
            <line x1="9" y1="15" x2="15" y2="15" />
          </svg>
          <p className="text-[14px] text-locked">
            <span className="font-bold text-purple">Clique para selecionar PDFs</span>
            {" "}ou arraste aqui
          </p>
          <p className="text-[12px] text-locked/70">Múltiplos arquivos aceitos</p>
        </>
      )}
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function NovoProjetoPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>(1);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Step 1 data
  const [draft, setDraft] = useState<ProjectDraft>({
    title: "",
    work: "tcc",
    institution: "",
    citation_style: "abnt",
    deadline: "",
    weekly_hours: "",
  });

  // Created project id (set after step 1 submit)
  const [projectId, setProjectId] = useState<string | null>(null);

  // Step 2 data
  const [refText, setRefText] = useState("");
  const [refs, setRefs] = useState<RefEntry[]>([]);

  // Step 3 processing log
  const [processingLog, setProcessingLog] = useState<string[]>([]);
  const [allDone, setAllDone] = useState(false);

  // ── Helpers ──────────────────────────────────────────────────────────────────

  function makeId() {
    return Math.random().toString(36).slice(2, 10);
  }

  function addTextRefs() {
    const lines = refText
      .split("\n")
      .map((l) => l.trim())
      .filter((l) => l.length > 10);
    if (lines.length === 0) return;
    setRefs((prev) => [
      ...prev,
      ...lines.map((raw) => ({
        id: makeId(),
        raw,
        type: "text" as const,
        status: "pending" as const,
      })),
    ]);
    setRefText("");
  }

  function addPdfRefs(files: File[]) {
    setRefs((prev) => [
      ...prev,
      ...files.map((f) => ({
        id: makeId(),
        raw: f.name,
        type: "pdf" as const,
        file: f,
        status: "pending" as const,
      })),
    ]);
  }

  function removeRef(id: string) {
    setRefs((prev) => prev.filter((r) => r.id !== id));
  }

  // ── Step 1: create project ───────────────────────────────────────────────────

  async function handleCreateProject(e: React.FormEvent) {
    e.preventDefault();
    if (!getToken()) { router.replace("/entrar"); return; }
    setBusy(true);
    setError(null);
    try {
      const created = await api<{ id: string }>("/projects", {
        method: "POST",
        body: {
          title: draft.title,
          work: draft.work,
          institution: draft.institution || null,
          citation_style: draft.citation_style,
          deadline: draft.deadline || null,
          weekly_hours: draft.weekly_hours ? Number(draft.weekly_hours) : null,
        },
      });
      setProjectId(created.id);
      setStep(2);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) { router.replace("/entrar"); return; }
      setError(err instanceof Error ? err.message : "Algo deu errado.");
    } finally {
      setBusy(false);
    }
  }

  // ── Step 2: go to processing ─────────────────────────────────────────────────

  function handleGoToProcessing() {
    if (refs.length === 0) {
      // Skip refs entirely
      router.push(`/projetos/${projectId}/arvore`);
      return;
    }
    setStep(3);
    void processRefs();
  }

  // ── Step 3: process all refs ─────────────────────────────────────────────────

  const processRefs = useCallback(async () => {
    if (!projectId) return;
    setAllDone(false);
    const log: string[] = [];

    for (const ref of refs) {
      setRefs((prev) =>
        prev.map((r) => (r.id === ref.id ? { ...r, status: "processing" } : r))
      );

      if (ref.type === "pdf" && ref.file) {
        log.push(`📄 Enviando PDF: ${ref.file.name}…`);
        setProcessingLog([...log]);
        try {
          const uploaded = await uploadDocumentPdf(projectId, ref.file, undefined);
          log.push(`   ✓ Recebido como "${uploaded.title}". Dissecando trechos…`);
          setProcessingLog([...log]);
          await api(`/projects/${projectId}/documents/${uploaded.id}/dissect`, { method: "POST" });
          log.push(`   ✓ Análise completa — trechos classificados e indexados.`);
          setProcessingLog([...log]);
          setRefs((prev) =>
            prev.map((r) =>
              r.id === ref.id ? { ...r, status: "done", result: { id: uploaded.id, title: uploaded.title } } : r
            )
          );
        } catch (err) {
          const msg = err instanceof Error ? err.message : "Erro desconhecido";
          log.push(`   ✗ Falha: ${msg}`);
          setProcessingLog([...log]);
          setRefs((prev) =>
            prev.map((r) => (r.id === ref.id ? { ...r, status: "error", errorMsg: msg } : r))
          );
        }
      } else if (ref.type === "text") {
        log.push(`📚 Processando referência: ${ref.raw.slice(0, 60)}…`);
        setProcessingLog([...log]);
        try {
          // Send raw citation string to the bibliography endpoint
          const result = await api<{ id: string; title: string }>(
            `/projects/${projectId}/documents/import-citation`,
            { method: "POST", body: { raw_citation: ref.raw, citation_style: draft.citation_style } }
          );
          log.push(`   ✓ Importada: "${result.title}"`);
          setProcessingLog([...log]);
          setRefs((prev) =>
            prev.map((r) => (r.id === ref.id ? { ...r, status: "done", result } : r))
          );
        } catch (err) {
          const msg = err instanceof Error ? err.message : "Erro desconhecido";
          log.push(`   ✗ Falha: ${msg}`);
          setProcessingLog([...log]);
          setRefs((prev) =>
            prev.map((r) => (r.id === ref.id ? { ...r, status: "error", errorMsg: msg } : r))
          );
        }
      }
    }

    log.push("─────────────────────────────────────");
    const doneCount = refs.filter((r) => r.status !== "error").length;
    log.push(`✅ ${doneCount} de ${refs.length} referências processadas com sucesso.`);
    setProcessingLog([...log]);
    setAllDone(true);
  }, [projectId, refs, draft.citation_style]);

  // ── Render ───────────────────────────────────────────────────────────────────

  const stepLabels = ["Dados do projeto", "Referências bibliográficas", "Processando"];

  return (
    <div className="min-h-screen flex flex-col bg-paper text-ink">
      <AppHeader />

      <main className="mx-auto w-full max-w-[760px] flex-1 px-6 py-10 sm:px-10">

        {/* Progress header */}
        <div className="mb-8">
          <button
            type="button"
            onClick={() => router.push("/projetos")}
            className="mb-4 inline-flex min-h-[44px] items-center gap-1.5 text-[14px] font-bold text-locked hover:text-ink transition cursor-pointer"
          >
            <svg viewBox="0 0 16 16" fill="none" className="h-4 w-4">
              <path d="M10 3L5 8l5 5" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Voltar para projetos
          </button>

          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h1 className="font-display text-3xl sm:text-[36px] text-ink leading-tight">
                Novo projeto
              </h1>
              <p className="mt-1 text-[15px] text-locked">
                {stepLabels[step - 1]}
                {step < 3 && (
                  <span className="ml-2 text-[13px] text-locked/60">
                    — etapa {step} de 3
                  </span>
                )}
              </p>
            </div>
            <StepDots current={step} total={3} />
          </div>
        </div>

        {error && <AlertBanner variant="error">{error}</AlertBanner>}

        {/* ─── ETAPA 1: Dados básicos ───────────────────────────────────────── */}
        {step === 1 && (
          <form onSubmit={handleCreateProject} className="space-y-5">
            <div className="rounded-[16px] border border-borda bg-superficie p-6 sm:p-8 space-y-5">

              <label className="block text-[15px] font-medium text-ink">
                Título do trabalho <span className="text-brand-red">*</span>
                <input
                  name="title"
                  required
                  minLength={3}
                  maxLength={200}
                  value={draft.title}
                  onChange={(e) => setDraft({ ...draft, title: e.target.value })}
                  className={inputCls}
                  placeholder="Ex: Análise da política fiscal brasileira 2020–2024"
                />
              </label>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <label className="block text-[15px] font-medium text-ink">
                  Tipo de trabalho <span className="text-brand-red">*</span>
                  <select
                    name="work"
                    required
                    value={draft.work}
                    onChange={(e) => setDraft({ ...draft, work: e.target.value })}
                    className={selectCls}
                  >
                    {Object.entries(WORK_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                </label>

                <label className="block text-[15px] font-medium text-ink">
                  Norma de citação <span className="text-brand-red">*</span>
                  <select
                    name="citation_style"
                    required
                    value={draft.citation_style}
                    onChange={(e) => setDraft({ ...draft, citation_style: e.target.value })}
                    className={selectCls}
                  >
                    {CITATION_STYLES.map(({ value, label }) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                </label>
              </div>

              <label className="block text-[15px] font-medium text-ink">
                Instituição
                <input
                  name="institution"
                  maxLength={200}
                  value={draft.institution}
                  onChange={(e) => setDraft({ ...draft, institution: e.target.value })}
                  className={inputCls}
                  placeholder="Ex: UFJF – Universidade Federal de Juiz de Fora"
                />
              </label>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <label className="block text-[15px] font-medium text-ink">
                  Prazo de entrega
                  <input
                    name="deadline"
                    type="date"
                    value={draft.deadline}
                    onChange={(e) => setDraft({ ...draft, deadline: e.target.value })}
                    className={inputCls}
                  />
                </label>

                <label className="block text-[15px] font-medium text-ink">
                  Horas disponíveis por semana
                  <input
                    name="weekly_hours"
                    type="number"
                    min={1}
                    max={168}
                    value={draft.weekly_hours}
                    onChange={(e) => setDraft({ ...draft, weekly_hours: e.target.value })}
                    className={inputCls}
                    placeholder="Ex: 10"
                  />
                </label>
              </div>
            </div>

            <div className="flex justify-end gap-3">
              <Button
                type="button"
                variant="secondary"
                onClick={() => router.push("/projetos")}
              >
                Cancelar
              </Button>
              <Button type="submit" variant="primary" disabled={busy || !draft.title.trim()}>
                {busy ? "Criando…" : "Criar projeto →"}
              </Button>
            </div>
          </form>
        )}

        {/* ─── ETAPA 2: Referências bibliográficas ─────────────────────────── */}
        {step === 2 && (
          <div className="space-y-5">
            <div className="rounded-[16px] border border-borda bg-superficie p-6 sm:p-8 space-y-6">

              {/* Texto livre: cole lista de referências */}
              <section>
                <h2 className="font-display text-xl text-ink mb-1">
                  Cole sua lista de referências
                </h2>
                <p className="text-[14px] text-locked mb-3">
                  Cole em qualquer formato — ABNT, APA, Vancouver, texto livre. Uma referência por linha.
                  O Orientador vai interpretar e indexar cada entrada.
                </p>
                <textarea
                  value={refText}
                  onChange={(e) => setRefText(e.target.value)}
                  rows={5}
                  placeholder={`SILVA, João. Título do livro. São Paulo: Editora, 2022.\nAUTOR, A. Title of paper. Journal, v. 10, n. 2, p. 100–115, 2020.\n…`}
                  className="w-full rounded-[12px] border border-borda bg-paper px-4 py-3 text-[14px] text-ink focus:border-purple outline-none transition resize-y font-mono leading-relaxed"
                />
                <div className="mt-2 flex justify-end">
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={!refText.trim()}
                    onClick={addTextRefs}
                  >
                    Adicionar à lista
                  </Button>
                </div>
              </section>

              {/* Divider */}
              <div className="flex items-center gap-3 text-[13px] text-locked">
                <div className="flex-1 border-t border-borda" />
                <span>ou</span>
                <div className="flex-1 border-t border-borda" />
              </div>

              {/* PDF drop zone */}
              <section>
                <h2 className="font-display text-xl text-ink mb-1">
                  Arraste os PDFs diretamente
                </h2>
                <p className="text-[14px] text-locked mb-3">
                  Os PDFs serão enviados, dissecados automaticamente e as referências indexadas no mapa de conhecimento.
                </p>
                <RefDropZone onFiles={addPdfRefs} />
              </section>

              {/* Fila de referências adicionadas */}
              {refs.length > 0 && (
                <section>
                  <h3 className="text-[13px] font-bold uppercase tracking-wider text-locked mb-3">
                    Referências na fila ({refs.length})
                  </h3>
                  <ul className="space-y-2">
                    {refs.map((r) => (
                      <li
                        key={r.id}
                        className="flex items-start gap-3 rounded-[10px] border border-borda bg-paper/60 px-4 py-3"
                      >
                        <span className={[
                          "mt-0.5 shrink-0 rounded-[5px] px-2 py-0.5 text-[11px] font-bold uppercase",
                          r.type === "pdf"
                            ? "bg-purple text-paper"
                            : "bg-skipped-bg text-purple",
                        ].join(" ")}>
                          {r.type === "pdf" ? "PDF" : "Ref"}
                        </span>
                        <p className="flex-1 text-[13px] text-ink leading-snug break-all">
                          {r.raw}
                        </p>
                        <button
                          type="button"
                          onClick={() => removeRef(r.id)}
                          aria-label="Remover"
                          className="shrink-0 text-locked hover:text-brand-red transition cursor-pointer"
                        >
                          <svg viewBox="0 0 16 16" fill="none" className="h-4 w-4">
                            <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth={2} strokeLinecap="round" />
                          </svg>
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3">
              <button
                type="button"
                onClick={() => setStep(1)}
                className="text-[14px] font-bold text-locked hover:text-ink transition cursor-pointer"
              >
                ← Voltar
              </button>
              <div className="flex gap-3">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => router.push(`/projetos/${projectId}/arvore`)}
                >
                  Pular por agora
                </Button>
                <Button
                  type="button"
                  variant="primary"
                  disabled={refs.length === 0}
                  onClick={handleGoToProcessing}
                >
                  Processar {refs.length > 0 ? `${refs.length} referência${refs.length > 1 ? "s" : ""}` : "referências"} →
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* ─── ETAPA 3: Processando ─────────────────────────────────────────── */}
        {step === 3 && (
          <div className="space-y-5">
            <div className="rounded-[16px] border border-borda bg-superficie p-6 sm:p-8 space-y-5">
              <div className="flex items-center gap-3">
                {!allDone ? (
                  <svg className="h-6 w-6 animate-spin text-purple" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                  </svg>
                ) : (
                  <div className="flex h-6 w-6 items-center justify-center rounded-full bg-done">
                    <svg viewBox="0 0 16 16" fill="none" className="h-4 w-4 text-paper">
                      <path d="M3 8.5l3 3 7-7" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </div>
                )}
                <h2 className="font-display text-xl text-ink">
                  {allDone ? "Processamento concluído!" : "Processando referências…"}
                </h2>
              </div>

              {/* Status per ref */}
              <ul className="space-y-2">
                {refs.map((r) => (
                  <li key={r.id} className="flex items-center gap-3 text-[14px]">
                    {r.status === "pending" && (
                      <div className="h-4 w-4 rounded-full border-2 border-borda" />
                    )}
                    {r.status === "processing" && (
                      <svg className="h-4 w-4 animate-spin text-purple" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                      </svg>
                    )}
                    {r.status === "done" && (
                      <div className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-done">
                        <svg viewBox="0 0 16 16" fill="none" className="h-2.5 w-2.5 text-paper">
                          <path d="M3 8l3 3 7-7" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      </div>
                    )}
                    {r.status === "error" && (
                      <div className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-brand-red">
                        <svg viewBox="0 0 16 16" fill="none" className="h-2.5 w-2.5 text-paper">
                          <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth={2} strokeLinecap="round" />
                        </svg>
                      </div>
                    )}
                    <span className={[
                      "truncate",
                      r.status === "done" ? "text-done" : r.status === "error" ? "text-brand-red" : "text-ink",
                    ].join(" ")}>
                      {r.result?.title ?? r.raw.slice(0, 70)}
                      {r.raw.length > 70 && r.status !== "done" ? "…" : ""}
                    </span>
                  </li>
                ))}
              </ul>

              {/* Terminal-style log */}
              {processingLog.length > 0 && (
                <div className="rounded-[10px] bg-ink p-4 font-mono text-[13px] text-paper/80 space-y-0.5 max-h-[220px] overflow-y-auto">
                  {processingLog.map((line, i) => (
                    <p key={i} className={line.startsWith("✅") ? "text-done font-bold" : line.startsWith("   ✗") ? "text-brand-red" : ""}>
                      {line}
                    </p>
                  ))}
                </div>
              )}
            </div>

            {allDone && (
              <div className="flex justify-end gap-3">
                <Button
                  type="button"
                  variant="primary"
                  onClick={() => router.push(`/projetos/${projectId}/arvore`)}
                >
                  Abrir projeto → Árvore de tarefas
                </Button>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
