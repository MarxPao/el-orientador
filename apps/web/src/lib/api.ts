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

export type MapNode = { id: string; label: string; n_claims: number };

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

export type ForensicSentence = {
  index: number;
  text: string;
  word_count: number;
  ai_probability: number;
  classification: "human" | "hybrid" | "ai_pattern";
  reasons: string[];
  has_verified_citation: boolean;
};

export type ForensicAnalysis = {
  measured_ai_score: number;
  measured_human_pct: number;
  measured_hybrid_pct: number;
  measured_ai_pct: number;
  burstiness_score: number;
  burstiness_cv: number;
  lexical_diversity_score: number;
  llm_markers_found: string[];
  verdict_code: "empty" | "human_dominant" | "hybrid" | "ai_dominant";
  verdict_label: string;
  sentences: ForensicSentence[];
};

export type AuthorshipPrism = {
  total_words: number;
  human_words: number;
  polished_words: number;
  ai_drafted_words: number;
  human_pct: number;
  polished_pct: number;
  ai_drafted_pct: number;
  last_intensity?: number;
  measured_ai_score?: number;
  burstiness_score?: number;
  llm_markers_found?: string[];
  telemetry_discrepancy?: boolean;
  discrepancy_message?: string | null;
  forensics?: ForensicAnalysis;
  requires_disclosure: boolean;
  status_label?: string;
};

export type ProjectAuthorshipResponse = {
  project: AuthorshipPrism;
  sections: Record<string, AuthorshipPrism>;
};

export type AiAssistResponse = {
  section: Section;
  generated_text: string;
  mode: "polish" | "coauthor" | "draft";
  intensity: number;
  section_authorship: AuthorshipPrism;
  project_authorship: AuthorshipPrism;
};

export type ValidateAuthenticityResponse = {
  section_id: string;
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
