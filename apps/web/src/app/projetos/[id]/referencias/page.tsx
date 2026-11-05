"use client";

import { useParams, useRouter } from "next/navigation";
import React, { Suspense, useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  CitationIssue,
  ConsistencyReport,
  Document,
  RefSearchResult,
  SearchResponse,
  api,
  checkConsistency,
  deleteDocument,
  downloadBibliography,
  fetchByDoi,
  getToken,
  importCitation,
  listDocuments,
  reindexLibrary,
  searchCrossRef,
  searchLibrary,
  uploadDocumentPdf,
  Project,
} from "@/lib/api";
import { AppHeader } from "@/components/app-header";
import { AlertBanner, Button } from "@/components/ui";

// ── Helpers ───────────────────────────────────────────────────────────────────

function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

function Spinner({ size = 16 }: { size?: number }) {
  return (
    <svg
      className="animate-spin text-purple"
      style={{ width: size, height: size }}
      viewBox="0 0 24 24"
      fill="none"
    >
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="40 60" strokeLinecap="round" />
    </svg>
  );
}

function severityDot(s: CitationIssue["severity"]) {
  return s === "error"
    ? "bg-brand-red"
    : "bg-orange";
}

// ── Sub-components ────────────────────────────────────────────────────────────

function SearchResultCard({
  result,
  onImport,
  importing,
  imported,
}: {
  result: RefSearchResult;
  onImport: (r: RefSearchResult) => void;
  importing: boolean;
  imported: boolean;
}) {
  return (
    <div className="rounded-[12px] border border-borda bg-superficie p-4 flex flex-col gap-2">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <p className="font-medium text-[15px] text-ink leading-snug line-clamp-2">{result.title}</p>
          {result.authors.length > 0 && (
            <p className="mt-0.5 text-[13px] text-locked truncate">
              {result.authors.slice(0, 3).join("; ")}
              {result.authors.length > 3 ? " et al." : ""}
              {result.year ? ` (${result.year})` : ""}
            </p>
          )}
          {result.journal && (
            <p className="text-[12px] text-locked italic truncate">{result.journal}</p>
          )}
        </div>
        <button
          onClick={() => onImport(result)}
          disabled={importing || imported}
          className={[
            "shrink-0 inline-flex h-8 items-center gap-1.5 rounded-[8px] px-3 text-[13px] font-medium transition",
            imported
              ? "bg-done/20 text-done cursor-default"
              : "bg-purple text-paper hover:bg-purple/90 disabled:opacity-60",
          ].join(" ")}
        >
          {importing ? (
            <Spinner size={13} />
          ) : imported ? (
            <>
              <svg viewBox="0 0 16 16" fill="none" className="h-3.5 w-3.5"><path d="M3 8.5l3 3 7-7" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" /></svg>
              Importado
            </>
          ) : (
            "+ Importar"
          )}
        </button>
      </div>
      {result.doi && (
        <p className="text-[12px] text-locked font-mono truncate">
          DOI:{" "}
          <a href={`https://doi.org/${result.doi}`} target="_blank" rel="noreferrer" className="text-purple hover:underline">
            {result.doi}
          </a>
        </p>
      )}
      {result.abstract && (
        <p className="text-[12px] text-locked leading-relaxed line-clamp-3">{result.abstract}</p>
      )}
    </div>
  );
}

/** What the pipeline is doing with an uploaded PDF, in words the student understands. */
function processingInfo(doc: Document): { label: string; busy: boolean; failed: boolean } | null {
  const p = doc.progress;
  if (doc.status === "failed") {
    return { label: "Não foi possível ler este PDF (arquivo corrompido, protegido ou sem texto reconhecível).", busy: false, failed: true };
  }
  if (doc.status === "pending" && !doc.storage_path) {
    // Imported by citation or DOI: there is no PDF to read, so nothing is running.
    return { label: "Só os dados da referência (sem PDF). Anexe o PDF para extrair trechos citáveis.", busy: false, failed: false };
  }
  if (doc.status === "pending") {
    const pages = p && p.total ? ` (${p.done}/${p.total} páginas)` : "";
    return { label: p?.phase === "ocr" ? `Reconhecendo texto das páginas escaneadas${pages}` : `Lendo o PDF${pages}`, busy: true, failed: false };
  }
  if (doc.stage === "index" || doc.stage === "embed") {
    return { label: doc.stage === "index" ? "Indexando o texto para busca" : "Criando o índice por significado", busy: true, failed: false };
  }
  if (doc.stage === "extract") {
    const chunks = p?.phase === "extract" && p.total ? ` (${p.done}/${p.total})` : "";
    return { label: `Extraindo trechos com citação verificada${chunks}`, busy: true, failed: false };
  }
  if (doc.stage === "summarize") {
    return { label: "Resumindo o documento", busy: true, failed: false };
  }
  return null;
}

function DocumentRow({
  doc,
  onDelete,
  deleting,
}: {
  doc: Document;
  onDelete: (id: string) => void;
  deleting: boolean;
}) {
  const processing = processingInfo(doc);
  return (
    <div className="flex items-start gap-3 rounded-[10px] border border-borda bg-superficie px-4 py-3 hover:border-purple/30 transition group">
      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-purple/10 text-purple">
        <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
          <path fillRule="evenodd" d="M4 2a2 2 0 00-2 2v12a2 2 0 002 2h12a2 2 0 002-2V7.414A2 2 0 0017.414 6L14 2.586A2 2 0 0012.586 2H4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm0 4a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1z" clipRule="evenodd" />
        </svg>
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[14px] font-medium text-ink leading-snug truncate">{doc.title}</p>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 mt-0.5 text-[12px] text-locked">
          {doc.authors?.length > 0 && <span>{doc.authors.slice(0, 2).join("; ")}{doc.authors.length > 2 ? " et al." : ""}</span>}
          {doc.year && <span>{doc.year}</span>}
          {doc.doi && (
            <a href={`https://doi.org/${doc.doi}`} target="_blank" rel="noreferrer" className="font-mono text-purple hover:underline truncate max-w-[200px]">
              {doc.doi}
            </a>
          )}
          {doc.claims_count > 0 && (
            <span className="rounded-full bg-purple/10 px-2 py-px text-purple font-medium">
              {doc.claims_count} {doc.claims_count === 1 ? "alegação" : "alegações"}
            </span>
          )}
        </div>
        {processing && (
          <p
            className={`mt-1 flex items-center gap-1.5 text-[12px] ${processing.failed ? "text-brand-red" : "text-locked"}`}
            role="status"
          >
            {processing.busy && <Spinner size={11} />}
            {processing.label}
          </p>
        )}
        {doc.summary && (
          <details className="mt-2 text-[12px] text-locked">
            <summary className="cursor-pointer select-none text-purple hover:underline">
              Resumo do documento (gerado por IA, não é evidência)
            </summary>
            <p className="mt-1.5 text-[13px] leading-relaxed text-ink">{doc.summary.overview}</p>
            <ul className="mt-2 space-y-1.5">
              {doc.summary.sections.map((s) => (
                <li key={s.page_start} className="leading-snug">
                  <span className="font-mono text-[11px] text-locked">p. {s.page_start}–{s.page_end}</span>{" "}
                  <span className="text-ink">{s.summary}</span>
                </li>
              ))}
            </ul>
          </details>
        )}
        {!processing && (doc.progress?.ocr_pages ?? 0) > 0 && (
          <p className="mt-1 text-[12px] text-locked">
            {doc.progress?.ocr_pages} {doc.progress?.ocr_pages === 1 ? "página lida" : "páginas lidas"} por reconhecimento de texto (OCR):
            confira as citações com o PDF original.
          </p>
        )}
      </div>
      <button
        onClick={() => onDelete(doc.id)}
        disabled={deleting}
        className="shrink-0 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 focus-visible:opacity-100 h-11 w-11 sm:h-9 sm:w-9 flex items-center justify-center rounded-[6px] text-locked hover:text-brand-red hover:bg-brand-red/10 transition disabled:opacity-50"
        aria-label="Remover referência"
      >
        {deleting ? <Spinner size={13} /> : (
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" className="h-3.5 w-3.5">
            <path d="M3 4h10M6 4V2h4v2M5 4l.5 9h5l.5-9" />
          </svg>
        )}
      </button>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

type Tab = "biblioteca" | "acervo" | "buscar" | "consistencia";

function ReferenciasInner() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [project, setProject] = useState<Project | null>(null);
  const [tab, setTab] = useState<Tab>("biblioteca");

  // biblioteca
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // buscar
  const [query, setQuery] = useState("");
  const [doiInput, setDoiInput] = useState("");
  const [results, setResults] = useState<RefSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [importingDoi, setImportingDoi] = useState<string | null>(null);
  const [importedDois, setImportedDois] = useState<Set<string>>(new Set());
  const [searchError, setSearchError] = useState<string | null>(null);

  // paste/upload rápido
  const [pasteInput, setPasteInput] = useState("");
  const [pasting, setPasting] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadingPdf, setUploadingPdf] = useState(false);

  // busca no acervo
  const [acervoQuery, setAcervoQuery] = useState("");
  const [acervo, setAcervo] = useState<SearchResponse | null>(null);
  const [searchingAcervo, setSearchingAcervo] = useState(false);
  const [reindexing, setReindexing] = useState(false);

  // consistência
  const [consistency, setConsistency] = useState<ConsistencyReport | null>(null);
  const [loadingConsistency, setLoadingConsistency] = useState(false);

  // exportação
  const [exporting, setExporting] = useState(false);
  const [exportFormat, setExportFormat] = useState<"abnt" | "apa" | "vancouver" | "bibtex">("abnt");

  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const debouncedQuery = useDebounce(query, 600);

  const leave = useCallback(() => {
    router.replace("/entrar");
  }, [router]);

  // Load project + documents
  useEffect(() => {
    if (!getToken()) { leave(); return; }
    api<Project>(`/projects/${id}`)
      .then(setProject)
      .catch(() => {});
    setLoadingDocs(true);
    listDocuments(id)
      .then((docs) => { setDocuments(docs); setLoadingDocs(false); })
      .catch((e) => {
        if (e instanceof ApiError && e.status === 401) return leave();
        setError(e instanceof Error ? e.message : "Erro ao carregar referências.");
        setLoadingDocs(false);
      });
  }, [id, leave]);

  // While the pipeline is still working on a PDF (reading, OCR, extraction), refresh its progress.
  const hasActiveDocs = documents.some((d) => (d.status === "pending" && !!d.storage_path) || !!d.stage);
  useEffect(() => {
    if (!hasActiveDocs) return;
    const timer = setTimeout(() => {
      listDocuments(id).then(setDocuments).catch(() => {});
    }, 3000);
    return () => clearTimeout(timer);
  }, [hasActiveDocs, documents, id]);

  // Auto-search
  useEffect(() => {
    if (!debouncedQuery.trim() || debouncedQuery.trim().length < 3) { setResults([]); return; }
    setSearching(true);
    setSearchError(null);
    searchCrossRef(debouncedQuery, 8)
      .then((r) => { setResults(r); setSearching(false); })
      .catch(() => { setSearchError("Não foi possível buscar. Verifique sua conexão."); setSearching(false); });
  }, [debouncedQuery]);

  async function handleDoiSearch() {
    if (!doiInput.trim()) return;
    setSearching(true);
    setSearchError(null);
    const r = await fetchByDoi(doiInput.trim());
    setSearching(false);
    if (!r) { setSearchError("DOI não encontrado na CrossRef."); return; }
    setResults([r]);
  }

  async function handleImport(result: RefSearchResult) {
    const key = result.doi ?? result.title;
    setImportingDoi(key);
    try {
      // Build raw citation string for the import-citation endpoint
      const rawParts: string[] = [];
      if (result.authors.length > 0) rawParts.push(result.authors.join("; "));
      if (result.year) rawParts.push(`(${result.year})`);
      rawParts.push(result.title);
      if (result.journal) rawParts.push(result.journal);
      if (result.volume) rawParts.push(`v. ${result.volume}`);
      if (result.issue) rawParts.push(`n. ${result.issue}`);
      if (result.pages) rawParts.push(`p. ${result.pages}`);
      if (result.doi) rawParts.push(`DOI: ${result.doi}`);
      const raw = rawParts.join(". ");
      await importCitation(id, raw, project?.citation_style ?? "abnt");
      setImportedDois((s) => new Set(s).add(key));
      setNotice(`"${result.title.slice(0, 60)}…" importado com sucesso.`);
      // Refresh library
      const updated = await listDocuments(id);
      setDocuments(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao importar.");
    } finally {
      setImportingDoi(null);
    }
  }

  async function handlePasteImport() {
    const lines = pasteInput.split("\n").map((l) => l.trim()).filter(Boolean);
    if (!lines.length) return;
    setPasting(true);
    let ok = 0;
    for (const line of lines) {
      try {
        await importCitation(id, line, project?.citation_style ?? "abnt");
        ok++;
      } catch { /* continue */ }
    }
    const updated = await listDocuments(id);
    setDocuments(updated);
    setPasteInput("");
    setPasting(false);
    setNotice(`${ok} de ${lines.length} referência(s) importada(s).`);
  }

  async function handlePdfDrop(file: File) {
    if (file.type !== "application/pdf") { setError("Selecione um arquivo PDF válido."); return; }
    setUploadingPdf(true);
    try {
      await uploadDocumentPdf(id, file);
      const updated = await listDocuments(id);
      setDocuments(updated);
      setNotice(`PDF "${file.name}" enviado.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao enviar PDF.");
    } finally {
      setUploadingPdf(false);
    }
  }

  async function handleDelete(docId: string) {
    if (!confirm("Remover esta referência do projeto? Isso também remove alegações vinculadas.")) return;
    setDeletingId(docId);
    try {
      await deleteDocument(id, docId);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao remover.");
    } finally {
      setDeletingId(null);
    }
  }

  async function handleCheckConsistency() {
    setLoadingConsistency(true);
    setConsistency(null);
    try {
      const r = await checkConsistency(id);
      setConsistency(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao verificar consistência.");
    } finally {
      setLoadingConsistency(false);
    }
  }

  async function handleExport() {
    setExporting(true);
    try {
      const ext = exportFormat === "bibtex" ? "bib" : "txt";
      await downloadBibliography(id, exportFormat, `referencias_${exportFormat}.${ext}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao exportar.");
    } finally {
      setExporting(false);
    }
  }

  async function handleAcervoSearch(e?: React.FormEvent) {
    e?.preventDefault();
    const q = acervoQuery.trim();
    if (q.length < 2) return;
    setSearchingAcervo(true);
    setError(null);
    try {
      setAcervo(await searchLibrary(id, q, 12));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao buscar no acervo.");
    } finally {
      setSearchingAcervo(false);
    }
  }

  async function handleReindex() {
    setReindexing(true);
    try {
      const r = await reindexLibrary(id);
      setNotice(r.queued > 0 ? `Reindexando ${r.queued} documento(s). Isso roda em segundo plano.` : "Nenhum documento com texto para indexar.");
      setDocuments(await listDocuments(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao reindexar.");
    } finally {
      setReindexing(false);
    }
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: "biblioteca", label: `Biblioteca (${documents.length})` },
    { key: "acervo", label: "Busca no acervo" },
    { key: "buscar", label: "Buscar & importar" },
    { key: "consistencia", label: "Consistência" },
  ];

  return (
    <div className="min-h-screen flex flex-col bg-paper text-ink">
      <AppHeader onLeave={leave} />

      <main className="mx-auto w-full max-w-[860px] flex-1 px-6 py-10 sm:px-8">

        {/* Breadcrumb */}
        <nav className="mb-6 flex items-center gap-2 text-[13px] text-locked">
          <button onClick={() => router.push("/projetos")} className="min-h-[44px] px-1 hover:text-purple transition">Projetos</button>
          <span>›</span>
          {project && <button onClick={() => router.push(`/projetos/${id}/arvore`)} className="min-h-[44px] px-1 hover:text-purple transition truncate max-w-[200px]">{project.title}</button>}
          {project && <span>›</span>}
          <span className="text-ink font-medium">Referências</span>
        </nav>

        <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
          <h1 className="font-display text-[28px] text-ink">Referências bibliográficas</h1>
          <div className="flex items-center gap-2">
            <select
              value={exportFormat}
              onChange={(e) => setExportFormat(e.target.value as typeof exportFormat)}
              className="h-9 rounded-[8px] border border-borda bg-superficie px-2.5 text-[13px] text-ink focus:border-purple outline-none"
            >
              <option value="abnt">ABNT</option>
              <option value="apa">APA</option>
              <option value="vancouver">Vancouver</option>
              <option value="bibtex">BibTeX</option>
            </select>
            <Button
              type="button"
              variant="secondary"
              onClick={handleExport}
              disabled={exporting || documents.length === 0}
            >
              {exporting ? <Spinner size={14} /> : "↓ Exportar lista"}
            </Button>
          </div>
        </div>

        {notice && (
          <div className="mb-4 rounded-[10px] bg-done/15 border border-done/30 px-4 py-3 text-[14px] text-done flex items-center gap-2">
            <svg viewBox="0 0 16 16" fill="none" className="h-4 w-4 shrink-0"><path d="M3 8.5l3 3 7-7" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" /></svg>
            {notice}
            <button onClick={() => setNotice(null)} className="ml-auto text-done/60 hover:text-done">×</button>
          </div>
        )}
        {error && <AlertBanner variant="error" className="mb-4">{error}<button onClick={() => setError(null)} className="ml-3 underline">Fechar</button></AlertBanner>}

        {/* Tab bar */}
        <div className="flex gap-1 rounded-[12px] bg-borda/30 p-1 mb-6">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={[
                "flex-1 rounded-[9px] py-2 text-[13px] font-medium transition",
                tab === t.key
                  ? "bg-superficie text-ink shadow-sm"
                  : "text-locked hover:text-ink",
              ].join(" ")}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* ── Tab: Biblioteca ── */}
        {tab === "biblioteca" && (
          <div className="space-y-3">
            {loadingDocs ? (
              <div className="flex items-center justify-center py-12 text-locked gap-2">
                <Spinner size={18} /> Carregando referências…
              </div>
            ) : documents.length === 0 ? (
              <div className="rounded-[14px] border border-dashed border-borda p-10 text-center">
                <p className="text-[15px] text-locked">Nenhuma referência ainda.</p>
                <p className="mt-1 text-[13px] text-locked">Use a aba "Buscar &amp; importar" para adicionar.</p>
              </div>
            ) : (
              documents.map((doc) => (
                <DocumentRow
                  key={doc.id}
                  doc={doc}
                  onDelete={handleDelete}
                  deleting={deletingId === doc.id}
                />
              ))
            )}
          </div>
        )}

        {/* ── Tab: Busca no acervo ── */}
        {tab === "acervo" && (
          <div className="space-y-4">
            <form onSubmit={handleAcervoSearch} className="flex gap-2">
              <input
                value={acervoQuery}
                onChange={(e) => setAcervoQuery(e.target.value)}
                placeholder="O que você procura nos seus PDFs? Ex.: abandono escolar"
                className="flex-1 rounded-[10px] border border-borda bg-superficie px-4 py-2.5 text-[14px] text-ink placeholder:text-locked focus:border-purple focus:outline-none"
                aria-label="Buscar no acervo"
              />
              <Button type="submit" disabled={searchingAcervo || acervoQuery.trim().length < 2}>
                {searchingAcervo ? <Spinner size={14} /> : "Buscar"}
              </Button>
            </form>
            <p className="text-[12px] text-locked">
              Procura em todas as páginas de todos os documentos enviados e mostra a página de cada trecho.
              {" "}
              <button type="button" onClick={handleReindex} disabled={reindexing} className="underline hover:text-ink disabled:opacity-50">
                {reindexing ? "Reindexando…" : "Reindexar acervo"}
              </button>
              {" "}(use uma vez para PDFs enviados antes desta função).
            </p>
            {acervo?.notice && (
              <p role="status" className="rounded-[10px] border border-borda bg-superficie px-4 py-3 text-[13px] text-locked">
                {acervo.notice}
              </p>
            )}
            {acervo && acervo.results.length === 0 && (
              <div className="rounded-[14px] border border-dashed border-borda p-8 text-center text-[14px] text-locked">
                Nada encontrado para “{acervo.query}”.
                {acervo.coverage.chunks === 0 && " Nenhum documento foi indexado ainda: envie um PDF ou reindexe o acervo."}
              </div>
            )}
            <ul className="space-y-3">
              {acervo?.results.map((r) => (
                <li key={r.chunk_id} className="rounded-[10px] border border-borda bg-superficie px-4 py-3">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-locked">
                    <span className="font-medium text-ink">{r.document_title}</span>
                    <span className="font-mono">p. {r.page_no}</span>
                    <span className="rounded-full bg-purple/10 px-2 py-px text-purple">
                      {r.matched_by.includes("keyword") && r.matched_by.includes("semantic")
                        ? "palavras + significado"
                        : r.matched_by.includes("keyword")
                          ? "palavras"
                          : "por significado"}
                    </span>
                    <span className="ml-auto font-mono">{r.cite}</span>
                  </div>
                  <p className="mt-1.5 text-[13px] leading-relaxed text-ink">{r.snippet}</p>
                </li>
              ))}
            </ul>
            {acervo && acervo.mode === "hybrid" && (
              <p className="text-[11px] text-locked">
                Trechos como estes são pistas para você ler a fonte; só viram evidência quando a citação é verificada no PDF.
              </p>
            )}
          </div>
        )}

        {/* ── Tab: Buscar & importar ── */}
        {tab === "buscar" && (
          <div className="space-y-6">
            {/* Busca por título / palavras-chave */}
            <section>
              <h2 className="text-[15px] font-semibold text-ink mb-3">Buscar por título ou palavra-chave</h2>
              <div className="relative">
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Ex.: machine learning education, Piaget 1976…"
                  className="w-full h-11 rounded-[10px] border border-borda bg-superficie pl-4 pr-10 text-[15px] text-ink focus:border-purple outline-none transition"
                />
                <div className="absolute right-3 top-1/2 -translate-y-1/2 text-locked">
                  {searching ? <Spinner size={15} /> : (
                    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.8} className="h-4 w-4">
                      <circle cx="9" cy="9" r="6" /><path d="M15 15l-3-3" strokeLinecap="round" />
                    </svg>
                  )}
                </div>
              </div>
              {searchError && <p className="mt-2 text-[13px] text-brand-red">{searchError}</p>}
            </section>

            {/* Busca por DOI */}
            <section>
              <h2 className="text-[15px] font-semibold text-ink mb-3">Buscar por DOI</h2>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={doiInput}
                  onChange={(e) => setDoiInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleDoiSearch()}
                  placeholder="10.1016/j.compedu.2021.104… ou https://doi.org/…"
                  className="flex-1 h-11 rounded-[10px] border border-borda bg-superficie px-4 text-[15px] font-mono text-ink focus:border-purple outline-none transition"
                />
                <Button type="button" variant="primary" onClick={handleDoiSearch} disabled={searching || !doiInput.trim()}>
                  Buscar
                </Button>
              </div>
            </section>

            {/* Resultados */}
            {results.length > 0 && (
              <section>
                <h2 className="text-[13px] font-semibold text-locked uppercase tracking-wider mb-3">
                  {results.length} resultado{results.length > 1 ? "s" : ""} (CrossRef)
                </h2>
                <div className="space-y-3">
                  {results.map((r, i) => (
                    <SearchResultCard
                      key={r.doi ?? i}
                      result={r}
                      onImport={handleImport}
                      importing={importingDoi === (r.doi ?? r.title)}
                      imported={importedDois.has(r.doi ?? r.title)}
                    />
                  ))}
                </div>
              </section>
            )}

            {/* Colar referências em texto */}
            <section className="pt-2 border-t border-borda">
              <h2 className="text-[15px] font-semibold text-ink mb-1">Colar referências em texto</h2>
              <p className="text-[13px] text-locked mb-3">Uma por linha, em qualquer formato (ABNT, APA, Vancouver…)</p>
              <textarea
                value={pasteInput}
                onChange={(e) => setPasteInput(e.target.value)}
                rows={5}
                placeholder={"SILVA, João. Título do livro. São Paulo: Editora, 2020.\nSMITH, J. (2019). Article title. Journal, 3(2), 10–20."}
                className="w-full rounded-[10px] border border-borda bg-superficie px-4 py-3 text-[14px] text-ink focus:border-purple outline-none resize-y transition"
              />
              <div className="mt-2 flex justify-end">
                <Button type="button" variant="primary" onClick={handlePasteImport} disabled={pasting || !pasteInput.trim()}>
                  {pasting ? <Spinner size={14} /> : "Importar"}
                </Button>
              </div>
            </section>

            {/* Upload de PDF */}
            <section className="pt-2 border-t border-borda">
              <h2 className="text-[15px] font-semibold text-ink mb-1">Adicionar PDF</h2>
              <p className="text-[13px] text-locked mb-3">Arraste ou clique para enviar um arquivo PDF para análise.</p>
              <div
                role="button"
                tabIndex={0}
                aria-label="Zona de upload de PDF"
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault(); setDragOver(false);
                  const f = e.dataTransfer.files[0];
                  if (f) handlePdfDrop(f);
                }}
                onClick={() => fileInputRef.current?.click()}
                onKeyDown={(e) => e.key === "Enter" && fileInputRef.current?.click()}
                className={[
                  "flex flex-col items-center justify-center gap-2 rounded-[12px] border-2 border-dashed px-6 py-8 cursor-pointer transition select-none",
                  dragOver
                    ? "border-purple bg-purple/10"
                    : uploadingPdf
                    ? "border-borda bg-borda/10 cursor-wait"
                    : "border-borda hover:border-purple/50 hover:bg-purple/5",
                ].join(" ")}
              >
                {uploadingPdf ? (
                  <><Spinner size={22} /><p className="text-[14px] text-locked">Enviando…</p></>
                ) : dragOver ? (
                  <p className="text-[15px] font-medium text-purple">Solte para enviar</p>
                ) : (
                  <>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" className="h-8 w-8 text-locked">
                      <path d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                    </svg>
                    <p className="text-[14px] text-locked">Arraste um PDF ou <span className="text-purple font-medium">clique para selecionar</span></p>
                  </>
                )}
              </div>
              <input ref={fileInputRef} type="file" accept="application/pdf" className="sr-only" onChange={(e) => { const f = e.target.files?.[0]; if (f) handlePdfDrop(f); e.target.value = ""; }} />
            </section>
          </div>
        )}

        {/* ── Tab: Consistência ── */}
        {tab === "consistencia" && (
          <div className="space-y-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[15px] text-ink">
                  Verifica se todas as referências cadastradas foram citadas no texto e se há citações sem referência correspondente.
                </p>
              </div>
              <Button type="button" variant="primary" onClick={handleCheckConsistency} disabled={loadingConsistency}>
                {loadingConsistency ? <><Spinner size={14} /> Verificando…</> : "Verificar agora"}
              </Button>
            </div>

            {consistency === null && !loadingConsistency && (
              <div className="rounded-[14px] border border-dashed border-borda p-10 text-center">
                <p className="text-[15px] text-locked">Clique em "Verificar agora" para analisar seu trabalho.</p>
              </div>
            )}

            {consistency && (
              <>
                {/* Status geral */}
                <div className={[
                  "rounded-[12px] border px-5 py-4 flex items-center gap-4",
                  consistency.ok
                    ? "border-done/40 bg-done/10"
                    : "border-brand-red/40 bg-brand-red/5",
                ].join(" ")}>
                  <div className={["h-10 w-10 rounded-full flex items-center justify-center shrink-0", consistency.ok ? "bg-done text-paper" : "bg-brand-red text-paper"].join(" ")}>
                    {consistency.ok ? (
                      <svg viewBox="0 0 16 16" fill="none" className="h-5 w-5"><path d="M3 8.5l3 3 7-7" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" /></svg>
                    ) : (
                      <svg viewBox="0 0 16 16" fill="none" className="h-5 w-5"><path d="M8 4v5M8 11v1" stroke="currentColor" strokeWidth={2} strokeLinecap="round" /></svg>
                    )}
                  </div>
                  <div>
                    <p className="font-semibold text-[15px] text-ink">
                      {consistency.ok ? "Tudo consistente!" : `${consistency.issues.length} problema${consistency.issues.length > 1 ? "s" : ""} encontrado${consistency.issues.length > 1 ? "s" : ""}`}
                    </p>
                    <p className="text-[13px] text-locked">
                      {consistency.total_documents} documento{consistency.total_documents !== 1 ? "s" : ""} · {consistency.cited_document_ids.length} citado{consistency.cited_document_ids.length !== 1 ? "s" : ""} · {consistency.uncited_document_ids.length} não citado{consistency.uncited_document_ids.length !== 1 ? "s" : ""}
                    </p>
                  </div>
                </div>

                {/* Lista de issues */}
                {consistency.issues.length > 0 && (
                  <ul className="space-y-2.5">
                    {consistency.issues.map((issue, i) => (
                      <li key={i} className="flex items-start gap-3 rounded-[10px] border border-borda bg-superficie px-4 py-3">
                        <span className={["mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full", severityDot(issue.severity)].join(" ")} />
                        <div>
                          <p className="text-[14px] text-ink">{issue.message}</p>
                          {(issue.document_title || issue.section_title) && (
                            <p className="text-[12px] text-locked mt-0.5">
                              {issue.document_title && <span>📄 {issue.document_title}</span>}
                              {issue.section_title && <span> · 📝 {issue.section_title}</span>}
                            </p>
                          )}
                        </div>
                        <span className={["ml-auto shrink-0 rounded-full px-2 py-px text-[11px] font-bold uppercase", issue.severity === "error" ? "bg-brand-red/15 text-brand-red" : "bg-orange/20 text-ink"].join(" ")}>
                          {issue.severity === "error" ? "Erro" : "Aviso"}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}

                {/* Documentos não citados */}
                {consistency.uncited_document_ids.length > 0 && (
                  <div className="rounded-[12px] border border-borda p-4">
                    <h3 className="text-[13px] font-bold uppercase tracking-wider text-locked mb-3">Referências não citadas no texto</h3>
                    <ul className="space-y-1.5">
                      {documents
                        .filter((d) => consistency.uncited_document_ids.includes(d.id))
                        .map((d) => (
                          <li key={d.id} className="flex items-center gap-2 text-[14px] text-ink">
                            <span className="h-1.5 w-1.5 rounded-full bg-orange shrink-0" />
                            {d.title}
                            {d.year && <span className="text-locked">({d.year})</span>}
                          </li>
                        ))}
                    </ul>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* Bottom nav */}
        <div className="mt-10 pt-6 border-t border-borda flex flex-wrap gap-3">
          <Button type="button" variant="secondary" onClick={() => router.push(`/projetos/${id}/mapa`)}>← Mapa</Button>
          <Button type="button" variant="secondary" onClick={() => router.push(`/projetos/${id}/editor`)}>Editor →</Button>
        </div>
      </main>
    </div>
  );
}

export default function ReferenciasPage() {
  return (
    <Suspense fallback={<main className="p-8 text-sm">Carregando referências…</main>}>
      <ReferenciasInner />
    </Suspense>
  );
}
