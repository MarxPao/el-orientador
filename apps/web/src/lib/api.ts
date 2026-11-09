const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "orientador_token";

export type Project = {
  id: string;
  title: string;
  work: string;
  institution: string | null;
  citation_style: string;
  deadline: string | null;
  weekly_hours: number | null;
};

export const WORK_LABELS: Record<string, string> = {
  tcc: "TCC",
  pre_projeto_mestrado: "Pré-projeto de mestrado",
  pre_projeto_doutorado: "Pré-projeto de doutorado",
  dissertacao: "Dissertação",
  tese: "Tese",
  artigo: "Artigo",
};

export const getToken = () => (typeof window === "undefined" ? null : window.localStorage.getItem(TOKEN_KEY));
export const setToken = (t: string) => window.localStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => window.localStorage.removeItem(TOKEN_KEY);

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

/** Turn a FastAPI error body into a readable Portuguese message. */
function messageFrom(body: unknown): string {
  const detail = (body as { detail?: unknown })?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return "Confira os campos preenchidos e tente novamente.";
  return "Algo deu errado. Tente novamente.";
}

export async function api<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  const token = getToken();
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method: init.method ?? "GET",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
    });
  } catch {
    throw new ApiError(0, "Não foi possível conectar ao servidor.");
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, messageFrom(body));
  return body as T;
}

export type MapNode = { id: string; label: string; n_claims: number; summary?: string | null };

export type MapLink = {
  id: string;
  source: string;
  target: string;
  relation: string;
  status: "suggested" | "confirmed" | "rejected";
  confidence: number | null;
  rationale: string | null;
  display_by_default: boolean;
};

export type MapData = { nodes: MapNode[]; edges: MapLink[]; gaps?: Gap[] };

export type GapSearch = {
  source: string;
  query: string;
  total: number | null;
  results: { title: string | null; year: number | null; doi: string | null }[];
  status: "ok" | "failed";
};

export type Gap = {
  id: string;
  project_id: string;
  concept_a: string;
  concept_b: string;
  searches: GapSearch[];
  found_links: { title: string | null; year: number | null; doi: string | null }[];
  note: string | null;
  status: "open" | "adopted_as_problem" | "dismissed";
  created_at?: string;
};

export type Evidence = {
  side: "source" | "target";
  concept: string;
  statement: string;
  document_id: string;
  document_title: string | null;
  page: number;
  quote: string;
  context_before: string;
  context_after: string;
  has_pdf: boolean;
};

/** Open a project PDF at a given page. The file needs the auth header, so it is fetched as a blob first. */
export async function openPdfAtPage(projectId: string, documentId: string, page: number): Promise<void> {
  const popup = window.open("", "_blank"); // opened synchronously so the browser does not block it
  try {
    const token = getToken();
    const res = await fetch(`${API_URL}/projects/${projectId}/documents/${documentId}/file`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new ApiError(res.status, "Não foi possível abrir o PDF.");
    const url = URL.createObjectURL(await res.blob());
    if (popup) popup.location.href = `${url}#page=${page}`;
  } catch (err) {
    popup?.close();
    throw err instanceof ApiError ? err : new ApiError(0, "Não foi possível abrir o PDF.");
  }
}

/** Fetch an authenticated PDF as an object URL for side-by-side embedded viewing. */
export async function fetchPdfBlobUrl(projectId: string, documentId: string, page: number): Promise<string> {
  const token = getToken();
  const res = await fetch(`${API_URL}/projects/${projectId}/documents/${documentId}/file`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new ApiError(res.status, "Não foi possível carregar o PDF.");
  const url = URL.createObjectURL(await res.blob());
  return `${url}#page=${page}`;
}

export async function uploadDocumentPdf(
  projectId: string,
  file: File,
  title?: string
): Promise<{ id: string; title: string; status: string }> {
  const token = getToken();
  const fd = new FormData();
  fd.append("file", file);
  if (title && title.trim()) {
    fd.append("title", title.trim());
  }
  const res = await fetch(`${API_URL}/projects/${projectId}/documents/upload`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: fd,
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw new ApiError(res.status, data?.detail ?? "Não foi possível enviar o PDF.");
  }
  return data;
}

export const RELATION_LABELS: Record<string, string> = {
  apoia: "apoia",
  contrasta: "contrasta com",
  estende: "estende",
  aplica: "aplica",
  critica: "critica",
};

export const STATUS_LABELS: Record<MapLink["status"], string> = {
  confirmed: "Confirmada",
  suggested: "Sugerida",
  rejected: "Rejeitada",
};

export const GAP_STATUS_LABELS: Record<Gap["status"], string> = {
  open: "Aberta",
  adopted_as_problem: "Adotada como problema",
  dismissed: "Descartada",
};

export type Phase = {
  key: string;
  label: string;
  order: number;
};

export type ProgressNode = {
  key: string;
  phase: string;
  title: string;
  description: string;
  prerequisites: string[];
  typical_time: string;
  unlocks: string[];
  gate_criteria: string;
  node_id?: string;
  status: "locked" | "available" | "done" | "skipped" | "needs_review";
  queued: boolean;
  skipped_reason?: string | null;
  updated_at?: string | null;
};

export type TreeData = {
  template_key: string;
  template_title: string;
  phases: Phase[];
  nodes: ProgressNode[];
};

export const NODE_STATUS_LABELS: Record<ProgressNode["status"], string> = {
  locked: "Bloqueado",
  available: "Disponível",
  done: "Concluído",
  skipped: "Pulado",
  needs_review: "Revisar",
};

export type GateAttempt = {
  id: string;
  progress_node_id: string;
  transcript: { role: string; content: string }[];
  rubric_scores: { clareza?: number; justificativa?: number; coerencia?: number } | null;
  outcome: "liberar" | "revisar" | "pular" | "em_andamento";
  created_at: string;
};

export type GateTurnResult = {
  message_to_student: string;
  done: boolean;
  outcome?: "liberar" | "revisar" | "pular";
  rubric_scores?: { clareza?: number; justificativa?: number; coerencia?: number } | null;
  guidance?: string | null;
  attempt_id: string;
  prompt_version?: string;
};

export type ScheduleItem = {
  node_key: string;
  title: string;
  phase: string;
  status: "locked" | "available" | "done" | "skipped" | "needs_review";
  queued: boolean;
  typical_time: string;
  estimated_weeks: number;
  estimated_start: string;
  estimated_end: string;
};

export type ScheduleData = {
  start_date: string;
  weekly_hours: number;
  deadline: string | null;
  days_until_deadline: number | null;
  is_at_risk: boolean;
  alert: string;
  suggested_weekly_hours: number | null;
  total_estimated_weeks: number;
  estimated_completion_date: string;
  queued_keys: string[];
  remaining_count: number;
  items: ScheduleItem[];
};

export type Section = {
  id: string;
  project_id: string;
  parent_id: string | null;
  title: string;
  position: number;
  content: Record<string, unknown>;
  concept_ids: string[];
  updated_at: string;
};

export type CoherenceWarning = {
  type: "secao_sem_fonte" | "referencia_orfa" | "objetivo_sem_capitulo" | "conceito_nao_mencionado" | "documento_sem_alegacoes";
  severity: "warning" | "info";
  message: string;
  section_id?: string;
  section_title?: string;
  concept_id?: string;
  concept_label?: string;
  document_id?: string;
  document_title?: string;
};

export type ProvenanceEventSummary = {
  id: string | null;
  kind: "ai_draft" | "ai_coauthor" | "ai_polish" | "ai_paraphrase" | "paste";
  words: number;
  source?: string | null;
  declared?: "own_text" | null;
  created_at?: string | null;
};

export type AuthorshipPrism = {
  total_words: number;
  human_words: number;
  polished_words: number;
  ai_drafted_words: number;
  ai_revised_words?: number;
  pasted_words?: number;
  quoted_words?: number;
  declared_own_words?: number;
  human_pct: number;
  polished_pct: number;
  ai_drafted_pct: number;
  ai_revised_pct?: number;
  pasted_pct?: number;
  quoted_pct?: number;
  declared_own_pct?: number;
  last_intensity?: number;
  requires_disclosure: boolean;
  status_label?: string;
  /** "ledger" = registro de proveniência; "counters" = contadores antigos (sem registro) */
  basis?: "ledger" | "counters";
  notes?: string[];
  limits?: string[];
  events?: ProvenanceEventSummary[];
  pending_paste_events?: string[];
};

export type ParaphraseSuggestion = {
  text: string;
  similarity: number;
  event_id: string;
  ai_excerpt: string;
};

export type ParaphraseSearchResponse = {
  available: boolean;
  suggestions: ParaphraseSuggestion[];
  notice: string | null;
  limits?: string[];
};

export type ProjectAuthorshipResponse = {
  project: AuthorshipPrism;
  sections: Record<string, AuthorshipPrism>;
};

export type AiAssistResponse = {
  section: Section;
  generated_text: string;
  /** false when the backend answered in an honest non-generative mode (scaffold / mechanical cleanup) */
  llm_used: boolean;
  /** shown to the student when AI was unavailable and a degraded mode was used */
  notice?: string | null;
  mode: "polish" | "coauthor" | "draft";
  intensity: number;
  section_authorship: AuthorshipPrism;
  project_authorship: AuthorshipPrism;
};

export type ValidateAuthenticityResponse = {
  section_id: string;
  synced?: boolean;
  notice?: string | null;
  section_authorship: AuthorshipPrism;
  project_authorship: AuthorshipPrism;
};

export async function downloadDocx(
  projectId: string,
  defaultFilename: string = "trabalho.docx",
  omitDeclaration: boolean = false
): Promise<void> {
  const token = getToken();
  const qs = omitDeclaration ? "?omit_declaration=true" : "";
  const res = await fetch(`${API_URL}/projects/${projectId}/export/docx${qs}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new ApiError(res.status, "Erro ao exportar documento Word.");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = defaultFilename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function downloadLatexPackage(
  projectId: string,
  defaultFilename: string = "trabalho_latex_overleaf.zip",
  options?: { includeApproval?: boolean; includeAiDeclaration?: boolean }
): Promise<void> {
  const token = getToken();
  const params = new URLSearchParams();
  if (options?.includeApproval === false) params.set("include_approval", "false");
  if (options?.includeAiDeclaration === false) params.set("include_ai_declaration", "false");
  const qs = params.toString() ? `?${params.toString()}` : "";
  const res = await fetch(`${API_URL}/projects/${projectId}/export/latex${qs}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new ApiError(res.status, "Erro ao exportar pacote LaTeX para Overleaf.");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = defaultFilename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export type AdvisorMember = {
  project_id: string;
  advisor_email: string;
  can_comment: boolean;
  invited_at: string;
};

export type AdvisorReport = {
  id: string;
  project_id: string;
  period_start: string | null;
  period_end: string | null;
  payload: {
    generated_at: string;
    project: Record<string, unknown>;
    progress_tree: {
      total_nodes: number;
      completed_count: number;
      skipped_count: number;
      pending_count: number;
      completed: { key: string; title: string; phase: string; status: string; updated_at?: string }[];
      skipped_with_warning: { key: string; title: string; phase: string; status: string; skipped_reason: string }[];
      pending: { key: string; title: string; phase: string; status: string }[];
    };
    knowledge_map: {
      documents_count: number;
      verified_claims_count: number;
      concepts_count: number;
      confirmed_relations_count: number;
      rejected_relations_count: number;
      gaps_count: number;
      confirmed_relations: { source: string; target: string; relation: string }[];
      rejected_relations: { source: string; target: string; relation: string; user_note?: string }[];
      gaps: { concept_a: string; concept_b: string; status: string; note?: string }[];
    };
    manuscript: {
      sections_count: number;
      sections_with_evidence_count: number;
      authorship_prism?: AuthorshipPrism;
      sections: {
        id: string;
        title: string;
        position: number;
        concepts_linked_count: number;
        authorship?: AuthorshipPrism;
      }[];
    };
    ai_usage_audit: {
      total_ai_interactions: number;
      actions_summary: Record<string, number>;
      logs: { action: string; model?: string; prompt_version?: string; created_at: string }[];
    };
  };
  created_at: string;
};

export type SectionComment = {
  id: string;
  section_id: string;
  author_email: string;
  author_name: string | null;
  content: string;
  resolved: boolean;
  created_at: string;
};

export type ProjectClaim = {
  id: string;
  document_id: string;
  document_title: string | null;
  authors: string[];
  year: number | null;
  statement: string;
  quote: string;
  page_no: number;
  concepts: { id: string; label: string }[];
};

export type ShareLinkResponse = {
  token: string;
  share_path: string;
};

export type SharedProjectData = {
  project: Project;
  report_payload: AdvisorReport["payload"];
  concepts: MapNode[];
  sections: {
    id: string;
    title: string;
    position: number;
    content: Record<string, unknown>;
    concept_ids: string[];
    comments: SectionComment[];
  }[];
};

export type EnrichedClaim = {
  id: string;
  document_id: string;
  document_title: string;
  authors: string[];
  year: number | null;
  page_no: number;
  citation_ref: string;
  statement: string;
  quote: string;
  concepts: { id: string; label: string }[];
  role_code: "definicao_conceitual" | "evidencia_empirica" | "metodo_recorte" | "limite_contraponto";
  role_label: string;
  reading_tip: string;
  socratic_prompts: string[];
};

export type DocumentGuide = {
  document_id: string;
  title: string;
  authors: string[];
  year: number | null;
  status: string;
  claims_count: number;
  core_thesis: string;
  concepts: { id: string; label: string }[];
  shared_bridges: {
    concept_id: string;
    concept_label: string;
    other_document_id: string;
    other_document_title: string;
  }[];
  study_questions: string[];
  passages: EnrichedClaim[];
};

export type ManuscriptParagraphAudit = {
  index: number;
  excerpt: string;
  citation_count: number;
  status_code: "analise_integrada" | "vagao_de_trem" | "sem_ancoragem";
  status_label: string;
  feedback: string;
};

export type TextAnalysisWorkspace = {
  document_guides: DocumentGuide[];
  enriched_claims: EnrichedClaim[];
  manuscript_audit: {
    total_boxcar_paragraphs: number;
    total_integrated_paragraphs: number;
    sections: {
      section_id: string;
      section_title: string;
      paragraph_count: number;
      boxcar_count: number;
      integrated_count: number;
      paragraphs: ManuscriptParagraphAudit[];
    }[];
  };
};

export type TextCompareResult = {
  relation_type: "corroboracao" | "contraponto" | "complementaridade" | "lacuna";
  relation_label: string;
  intensity: number;
  mode_used: "scaffold_socratico" | "sintese_assistida";
  llm_used: boolean;
  notice?: string | null;
  passage_a: {
    id: string;
    citation_ref: string;
    concept: string;
    quote: string;
    role_label: string;
    reading_tip: string;
  };
  passage_b: {
    id: string;
    citation_ref: string;
    concept: string;
    quote: string;
    role_label: string;
    reading_tip: string;
  };
  comparison_matrix: {
    shared_terms: string[];
    convergence: string;
    difference: string;
    guiding_question: string;
  };
  synthesis_text: string;
  updated_section?: Section | null;
  project_authorship: AuthorshipPrism;
};


// ── Reference search (CrossRef / OpenAlex) ────────────────────────────────────

export type RefSearchResult = {
  doi: string | null;
  title: string;
  authors: string[];
  year: number | null;
  journal: string | null;
  volume: string | null;
  issue: string | null;
  pages: string | null;
  publisher: string | null;
  type: string | null;
  url: string | null;
  abstract: string | null;
  source: "crossref" | "openalex";
};

/** Search CrossRef by free-text query (title, author, keyword). */
export async function searchCrossRef(query: string, rows = 10): Promise<RefSearchResult[]> {
  const url = `https://api.crossref.org/works?query=${encodeURIComponent(query)}&rows=${rows}&select=DOI,title,author,published,container-title,volume,issue,page,publisher,type,URL,abstract`;
  const res = await fetch(url, { headers: { "User-Agent": "ElOrientador/1.0 (mailto:suporte@elorientador.app)" } });
  if (!res.ok) return [];
  const data = await res.json();
  return (data?.message?.items ?? []).map((item: Record<string, unknown>) => ({
    doi: (item.DOI as string) ?? null,
    title: Array.isArray(item.title) ? (item.title as string[])[0] : (item.title as string) ?? "Sem título",
    authors: Array.isArray(item.author)
      ? (item.author as { given?: string; family?: string }[]).slice(0, 5).map((a) => [a.family, a.given].filter(Boolean).join(", "))
      : [],
    year: (item["published"] as { "date-parts"?: number[][] })?.[  "date-parts"]?.[0]?.[0] ?? null,
    journal: Array.isArray(item["container-title"]) ? (item["container-title"] as string[])[0] : null,
    volume: (item.volume as string) ?? null,
    issue: (item.issue as string) ?? null,
    pages: (item.page as string) ?? null,
    publisher: (item.publisher as string) ?? null,
    type: (item.type as string) ?? null,
    url: (item.URL as string) ?? null,
    abstract: typeof item.abstract === "string" ? (item.abstract as string).replace(/<[^>]+>/g, "").slice(0, 400) : null,
    source: "crossref" as const,
  }));
}

/** Fetch a single work by DOI from CrossRef. */
export async function fetchByDoi(doi: string): Promise<RefSearchResult | null> {
  const clean = doi.replace(/^https?:\/\/doi\.org\//i, "");
  const url = `https://api.crossref.org/works/${encodeURIComponent(clean)}`;
  try {
    const res = await fetch(url, { headers: { "User-Agent": "ElOrientador/1.0 (mailto:suporte@elorientador.app)" } });
    if (!res.ok) return null;
    const data = await res.json();
    const item = data?.message;
    if (!item) return null;
    return {
      doi: (item.DOI as string) ?? null,
      title: Array.isArray(item.title) ? (item.title as string[])[0] : (item.title as string) ?? "Sem título",
      authors: Array.isArray(item.author)
        ? (item.author as { given?: string; family?: string }[]).slice(0, 5).map((a) => [a.family, a.given].filter(Boolean).join(", "))
        : [],
      year: (item["published"] as { "date-parts"?: number[][] })?.[  "date-parts"]?.[0]?.[0] ?? null,
      journal: Array.isArray(item["container-title"]) ? (item["container-title"] as string[])[0] : null,
      volume: (item.volume as string) ?? null,
      issue: (item.issue as string) ?? null,
      pages: (item.page as string) ?? null,
      publisher: (item.publisher as string) ?? null,
      type: (item.type as string) ?? null,
      url: (item.URL as string) ?? null,
      abstract: typeof item.abstract === "string" ? (item.abstract as string).replace(/<[^>]+>/g, "").slice(0, 400) : null,
      source: "crossref" as const,
    };
  } catch {
    return null;
  }
}

// ── Bibliography export ───────────────────────────────────────────────────────

export async function downloadBibliography(
  projectId: string,
  format: "abnt" | "apa" | "vancouver" | "chicago" | "mla" | "bibtex" = "abnt",
  filename = "referencias.txt"
): Promise<void> {
  const token = getToken();
  const res = await fetch(`${API_URL}/projects/${projectId}/export/bibliography?format=${format}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new ApiError(res.status, "Erro ao exportar bibliografia.");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// ── Citation consistency check ────────────────────────────────────────────────

export type CitationIssue = {
  type: "citacao_sem_referencia" | "referencia_nao_citada" | "doi_duplicado";
  severity: "error" | "warning";
  message: string;
  document_id?: string;
  document_title?: string;
  section_id?: string;
  section_title?: string;
};

export type ConsistencyReport = {
  issues: CitationIssue[];
  total_documents: number;
  total_sections: number;
  cited_document_ids: string[];
  uncited_document_ids: string[];
  ok: boolean;
};

export async function checkConsistency(projectId: string): Promise<ConsistencyReport> {
  return api<ConsistencyReport>(`/projects/${projectId}/consistency`);
}

// ── Document list for reference manager ──────────────────────────────────────

export type Document = {
  id: string;
  project_id: string;
  title: string;
  authors: string[];
  year: number | null;
  doi: string | null;
  status: string;
  /** null for a reference imported by citation or DOI (no PDF attached) */
  storage_path?: string | null;
  claims_count: number;
  created_at: string;
  /** share of pages with readable text (0..1), set once the PDF has been read */
  parse_quality?: number | null;
  /** pipeline stage running or queued ("parse" | "extract"), null when idle */
  stage?: "parse" | "index" | "embed" | "extract" | "summarize" | null;
  progress?: {
    phase: "parse" | "ocr" | "parsed" | "indexed" | "extract" | "extracted";
    done: number;
    total: number;
    ocr_pages?: number;
    chunks?: number;
  } | null;
  /** AI summary of the whole document. Always labelled as AI-generated: it is not evidence. */
  summary?: DocumentSummary | null;
};

export type DocumentSummary = {
  overview: string;
  sections: { page_start: number; page_end: number; summary: string }[];
  model: string | null;
  ai_generated: true;
};

export type SearchResult = {
  chunk_id: string;
  document_id: string;
  document_title: string | null;
  authors: string[];
  year: number | null;
  page_no: number;
  snippet: string;
  score: number;
  /** which rankers found it: exact words ("keyword") and/or meaning ("semantic") */
  matched_by: ("keyword" | "semantic")[];
  /** ready-to-use in-text citation, e.g. "(Moran, 2015, p. 12)" */
  cite: string;
};

export type SearchResponse = {
  query: string;
  mode: "hybrid" | "keyword";
  notice: string | null;
  results: SearchResult[];
  coverage: { chunks: number; embedded: number };
};

export async function searchLibrary(projectId: string, q: string, limit = 10): Promise<SearchResponse> {
  return api<SearchResponse>(`/projects/${projectId}/search?q=${encodeURIComponent(q)}&limit=${limit}`);
}

/** Rebuild the passage index of every document (needed once for PDFs uploaded before search existed). */
export async function reindexLibrary(projectId: string): Promise<{ queued: number }> {
  return api<{ queued: number }>(`/projects/${projectId}/library/reindex`, { method: "POST" });
}

export async function listDocuments(projectId: string): Promise<Document[]> {
  return api<Document[]>(`/projects/${projectId}/documents`);
}

export async function deleteDocument(projectId: string, documentId: string): Promise<void> {
  await api(`/projects/${projectId}/documents/${documentId}`, { method: "DELETE" });
}

export async function importCitation(
  projectId: string,
  rawCitation: string,
  citationStyle: string
): Promise<{ id: string; title: string }> {
  return api(`/projects/${projectId}/documents/import-citation`, {
    method: "POST",
    body: { raw_citation: rawCitation, citation_style: citationStyle },
  });
}

// ── Section comments ──────────────────────────────────────────────────────────

export async function listSectionComments(projectId: string, sectionId: string): Promise<SectionComment[]> {
  return api<SectionComment[]>(`/projects/${projectId}/sections/${sectionId}/comments`);
}

export async function createSectionComment(
  projectId: string,
  sectionId: string,
  content: string
): Promise<SectionComment> {
  return api<SectionComment>(`/projects/${projectId}/sections/${sectionId}/comments`, {
    method: "POST",
    body: { content },
  });
}

export async function resolveSectionComment(
  projectId: string,
  sectionId: string,
  commentId: string
): Promise<SectionComment> {
  return api<SectionComment>(
    `/projects/${projectId}/sections/${sectionId}/comments/${commentId}/resolve`,
    { method: "POST" }
  );
}

// ── Section versions (history) ────────────────────────────────────────────────

export type SectionVersion = {
  id: string;
  section_id: string;
  content_snapshot: Record<string, unknown>;
  word_count: number;
  created_at: string;
  created_by: string | null;
  change_summary?: string | null;
};

export async function listSectionVersions(
  projectId: string,
  sectionId: string
): Promise<SectionVersion[]> {
  return api<SectionVersion[]>(`/projects/${projectId}/sections/${sectionId}/versions`);
}

export async function restoreSectionVersion(
  projectId: string,
  sectionId: string,
  versionId: string
): Promise<Section> {
  return api<Section>(`/projects/${projectId}/sections/${sectionId}/versions/${versionId}/restore`, {
    method: "POST",
  });
}

// ── Advisor node feedback ─────────────────────────────────────────────────────

export type NodeFeedback = {
  id: string;
  project_id: string;
  node_key: string;
  advisor_email: string;
  content: string;
  created_at: string;
};

export async function listNodeFeedback(projectId: string, nodeKey: string): Promise<NodeFeedback[]> {
  return api<NodeFeedback[]>(`/projects/${projectId}/tree/${nodeKey}/feedback`);
}

export async function createNodeFeedback(
  projectId: string,
  nodeKey: string,
  content: string
): Promise<NodeFeedback> {
  return api<NodeFeedback>(`/projects/${projectId}/tree/${nodeKey}/feedback`, {
    method: "POST",
    body: { content },
  });
}

export type Capabilities = {
  llm_configured: boolean;
  llm_available: boolean;
  llm_model: string | null;
  features: {
    gate_dialogue: "ai" | "unavailable";
    map_suggest: "ai" | "unavailable";
    claim_extraction: "ai" | "deterministic";
    polish: "ai" | "mechanical";
    coauthor: "ai" | "scaffold";
    draft: "ai" | "scaffold";
    compare_synthesis: "ai" | "scaffold";
    authorship?: "provenance_ledger";
    search?: "hybrid" | "keyword";
    summaries?: "ai" | "unavailable";
  };
};

// ── Beta feedback & metrics ───────────────────────────────────────────────────

export type BetaFeedback = {
  id: string;
  user_id: string;
  project_id: string | null;
  overall_rating: number;
  socratic_gate_helpful: number;
  evidence_trust: number;
  relief_level: number;
  pricing_preference: string;
  brand_impression: string;
  comments: string | null;
  created_at: string;
};

export type BetaMetrics = {
  students_registered: number;
  projects_total: number;
  projects_by_work: Record<string, number>;
  activation: {
    threshold_sources: number;
    activated_projects: number;
    activation_rate: number;
  };
  knowledge_map: {
    total_edges: number;
    total_decisions: number;
    confirmed: number;
    rejected: number;
    acceptance_rate: number;
    target_acceptance_rate: number;
  };
  socratic_gate: {
    total_attempts: number;
    passed: number;
    skipped_with_warning: number;
  };
  feedback?: {
    total_responses: number;
    average_overall_rating: number;
    average_socratic_gate_helpful: number;
    average_evidence_trust: number;
    average_relief_level: number;
    pricing_preferences: Record<string, number>;
    recent_brand_impressions: string[];
  };
  pricing_validation: {
    hypothesis_a: string;
    hypothesis_b: string;
    cohort_target: string;
  };
};

export async function submitBetaFeedback(data: {
  project_id?: string;
  overall_rating: number;
  socratic_gate_helpful: number;
  evidence_trust: number;
  relief_level: number;
  pricing_preference: string;
  brand_impression: string;
  comments?: string;
}): Promise<{ feedback: BetaFeedback }> {
  return api<{ feedback: BetaFeedback }>("/beta/feedback", {
    method: "POST",
    body: data,
  });
}

export async function getBetaMetrics(): Promise<BetaMetrics> {
  return api<BetaMetrics>("/beta-metrics");
}

// ── Federated repository search (T7.1) ───────────────────────────────────────

export type RepositoryItem = {
  id: string;
  source: "scielo" | "bdtd" | "openalex" | string;
  title: string;
  authors: string[];
  year: number | null;
  venue: string | null;
  doi: string | null;
  abstract: string | null;
  citation_count: number;
  is_open_access: boolean;
  pdf_url: string | null;
  landing_page_url: string | null;
};

export type RepositorySearchResponse = {
  source: string;
  query: string;
  total: number;
  results: RepositoryItem[];
  status: string;
  sources_searched?: string[];
};

export async function searchRepositories(params: {
  q: string;
  source?: "all" | "scielo" | "bdtd" | "openalex";
  oa_only?: boolean;
  limit?: number;
}): Promise<RepositorySearchResponse> {
  const sp = new URLSearchParams();
  sp.set("q", params.q);
  if (params.source) sp.set("source", params.source);
  if (params.oa_only !== undefined) sp.set("oa_only", String(params.oa_only));
  if (params.limit) sp.set("limit", String(params.limit));
  return api<RepositorySearchResponse>(`/repositories/search?${sp.toString()}`);
}

export async function importFromRepository(
  projectId: string,
  item: {
    source_id?: string;
    repository: string;
    title: string;
    authors: string[];
    year?: number | null;
    venue?: string | null;
    doi?: string | null;
    pdf_url?: string | null;
    fetch_pdf?: boolean;
  }
): Promise<{ document: Document; warning?: string | null; downloaded: boolean }> {
  return api<{ document: Document; warning?: string | null; downloaded: boolean }>(
    `/projects/${projectId}/documents/import-repository`,
    {
      method: "POST",
      body: item,
    }
  );
}

// ── Academic defense simulator (T7.2) ───────────────────────────────────────

export type BancaTurn = {
  turn_no: number;
  speaker: "examiner" | "student";
  content: string;
  focus_area?: string;
  rubric_scores?: {
    dominio_conteudo: number;
    fundamentacao_evidencias: number;
    coerencia_metodologica: number;
    postura_argumentativa: number;
  };
  feedback?: string;
  created_at: string;
};

export type BancaFinalReport = {
  verdict: "apto_com_louvor" | "apto_com_ressalvas" | "recomenda_revisao" | string;
  verdict_title: string;
  overall_score: number;
  strengths: string[];
  vulnerabilities: string[];
  recommendations: string[];
  examiner_profile?: string;
  prompt_version?: string | null;
};

export type BancaSession = {
  id: string;
  project_id: string;
  examiner_profile: "estrito" | "construtivo" | string;
  status: "in_progress" | "completed" | string;
  turns: BancaTurn[];
  final_report: BancaFinalReport | null;
  created_at: string;
  updated_at: string;
};

export type BancaContextSummary = {
  sections_count: number;
  claims_count: number;
  research_problem: string;
};

export async function createBancaSession(
  projectId: string,
  examinerProfile: "estrito" | "construtivo" = "estrito"
): Promise<{ session: BancaSession; context_summary: BancaContextSummary }> {
  return api<{ session: BancaSession; context_summary: BancaContextSummary }>(
    `/projects/${projectId}/banca/sessions`,
    {
      method: "POST",
      body: { examiner_profile: examinerProfile },
    }
  );
}

export async function listBancaSessions(
  projectId: string
): Promise<{ sessions: BancaSession[] }> {
  return api<{ sessions: BancaSession[] }>(`/projects/${projectId}/banca/sessions`);
}

export async function getBancaSession(
  projectId: string,
  sessionId: string
): Promise<{ session: BancaSession; context_summary: BancaContextSummary }> {
  return api<{ session: BancaSession; context_summary: BancaContextSummary }>(
    `/projects/${projectId}/banca/sessions/${sessionId}`
  );
}

export async function submitBancaTurn(
  projectId: string,
  sessionId: string,
  answer: string
): Promise<{
  session: BancaSession;
  latest_evaluation: {
    rubric_scores: {
      dominio_conteudo: number;
      fundamentacao_evidencias: number;
      coerencia_metodologica: number;
      postura_argumentativa: number;
    };
    feedback: string;
  };
}> {
  return api<{
    session: BancaSession;
    latest_evaluation: {
      rubric_scores: {
        dominio_conteudo: number;
        fundamentacao_evidencias: number;
        coerencia_metodologica: number;
        postura_argumentativa: number;
      };
      feedback: string;
    };
  }>(`/projects/${projectId}/banca/sessions/${sessionId}/turn`, {
    method: "POST",
    body: { answer },
  });
}

export async function concludeBancaSession(
  projectId: string,
  sessionId: string
): Promise<{ session: BancaSession }> {
  return api<{ session: BancaSession }>(
    `/projects/${projectId}/banca/sessions/${sessionId}/conclude`,
    {
      method: "POST",
    }
  );
}

// ── Multi-advisee cohort dashboard (T7.4) ───────────────────────────────────

export type CohortSkippedStep = {
  node_key: string;
  title: string;
  phase: string;
  reason: string;
  skipped_at: string | null;
};

export type CohortStudentOverview = {
  project_id: string;
  title: string;
  work: string;
  institution: string;
  citation_style: string;
  deadline: string | null;
  weekly_hours: number;
  student: {
    name: string;
    email: string;
    initials: string;
  };
  progress: {
    total_nodes: number;
    done_nodes: number;
    available_nodes: number;
    completion_rate: number;
    skipped_count: number;
    skipped_steps: CohortSkippedStep[];
  };
  schedule: {
    days_until_deadline: number | null;
    is_at_risk: boolean;
    risk_level: "overdue" | "critical" | "warning" | "ontrack" | "no_deadline";
    risk_label: string;
    alert: string;
    suggested_weekly_hours: number | null;
    estimated_completion_date: string | null;
  };
  governance: {
    sources_count: number;
    verified_claims_count: number;
    sections_count: number;
    unresolved_comments_count: number;
    direct_human_pct: number;
    ai_assisted_pct: number;
    requires_disclosure: boolean;
    banca_verdict: string | null;
    banca_score: number | null;
  };
};

export type CohortDashboardMetrics = {
  total_advisees: number;
  average_progress: number;
  at_risk_count: number;
  total_skipped_steps: number;
  total_unresolved_comments: number;
  by_work: Record<string, number>;
  by_risk: Record<string, number>;
};

export type CohortDashboardResponse = {
  advisor_email: string;
  metrics: CohortDashboardMetrics;
  students: CohortStudentOverview[];
};

export async function getCohortSummary(): Promise<CohortDashboardResponse> {
  return api<CohortDashboardResponse>("/advisor/cohort-summary");
}

export async function downloadCohortExport(
  format: "csv" | "markdown" = "csv",
  defaultFilename?: string
): Promise<void> {
  const token = getToken();
  const res = await fetch(`${API_URL}/advisor/cohort-export?format=${format}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new ApiError(res.status, "Erro ao exportar ata de acompanhamento.");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = defaultFilename || (format === "markdown" ? "relatorio_turma.md" : "relatorio_turma.csv");
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function linkAdvisee(data: {
  project_id?: string;
  share_token?: string;
}): Promise<{ ok: boolean; project_id: string; title: string; message: string }> {
  return api<{ ok: boolean; project_id: string; title: string; message: string }>(
    "/advisor/link-advisee",
    {
      method: "POST",
      body: data,
    }
  );
}


