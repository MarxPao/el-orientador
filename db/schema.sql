-- El Orientador: PostgreSQL schema (v0.1). Requires pgvector.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE work_type AS ENUM ('tcc','pre_projeto_mestrado','pre_projeto_doutorado','dissertacao','tese','artigo');
CREATE TYPE certainty_level AS ENUM ('demonstra','sugere','especula','desconhecido');
CREATE TYPE relation_type AS ENUM ('apoia','contrasta','estende','aplica','critica');
CREATE TYPE edge_status AS ENUM ('suggested','confirmed','rejected');
CREATE TYPE actor_type AS ENUM ('ai','user');
CREATE TYPE node_status AS ENUM ('locked','available','done','skipped','needs_review');
CREATE TYPE analysis_depth AS ENUM ('full_text','abstract_only');

CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email text UNIQUE NOT NULL,
  name text,
  password_hash text,                  -- migration 001
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE projects (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title text NOT NULL,
  work work_type NOT NULL,
  institution text,
  citation_style text NOT NULL DEFAULT 'abnt',
  deadline date,
  weekly_hours int,
  research_problem text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  doi text,
  title text NOT NULL,
  authors jsonb NOT NULL DEFAULT '[]',
  year int,
  venue text,
  metadata_source text,                -- crossref | openalex | semantic_scholar | manual | filename | pdf
  retracted boolean NOT NULL DEFAULT false,
  storage_path text,                   -- encrypted object storage key
  analysis analysis_depth NOT NULL DEFAULT 'full_text',
  parse_quality real,                  -- 0..1
  status text NOT NULL DEFAULT 'pending', -- pending | parsed | extracted | failed
  stage text,                          -- pipeline stage running or queued (parse | extract), NULL when idle (migration 003)
  progress jsonb,                      -- {phase, done, total, ocr_pages} for the UI (migration 003)
  summary jsonb,                       -- AI summary of the whole document, labelled as such (migration 005)
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (project_id, doi)
);

CREATE TABLE document_pages (
  document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  page_no int NOT NULL,                -- 1-based
  text text NOT NULL,
  source text NOT NULL DEFAULT 'native', -- native | ocr (migration 003)
  PRIMARY KEY (document_id, page_no)
);

CREATE TABLE concepts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  label text NOT NULL,
  label_en text,
  aliases text[] NOT NULL DEFAULT '{}',
  theme text,
  embedding vector(1024),              -- dimension depends on the embedding model chosen
  merged_into uuid REFERENCES concepts(id),
  created_by actor_type NOT NULL DEFAULT 'ai',
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX concepts_project_idx ON concepts(project_id);

CREATE TABLE claims (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  concept_id uuid REFERENCES concepts(id) ON DELETE SET NULL,
  statement text NOT NULL,
  quote text NOT NULL,
  page_no int NOT NULL,
  char_start int,
  char_end int,
  quote_verified boolean NOT NULL,
  verify_method text NOT NULL,         -- exact | loose
  scope jsonb NOT NULL DEFAULT '{}',   -- {population, method, context}
  certainty certainty_level NOT NULL DEFAULT 'desconhecido',
  prompt_version text,
  model text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT claims_must_be_verified CHECK (quote_verified = true)
);
CREATE INDEX claims_doc_idx ON claims(document_id);

CREATE TABLE edges (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  source_concept uuid NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
  target_concept uuid NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
  relation relation_type NOT NULL,
  status edge_status NOT NULL DEFAULT 'suggested',
  confidence real,
  rationale text,
  created_by actor_type NOT NULL DEFAULT 'ai',
  user_note text,                      -- why the user rejected/edited
  created_at timestamptz NOT NULL DEFAULT now(),
  decided_at timestamptz,
  display_by_default boolean NOT NULL DEFAULT true, -- migration 002
  UNIQUE (project_id, source_concept, target_concept, relation)
);
-- Rejected edges are NEVER deleted: they prevent the same suggestion from coming back.

CREATE TABLE edge_evidence (
  edge_id uuid NOT NULL REFERENCES edges(id) ON DELETE CASCADE,
  claim_id uuid NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
  side text NOT NULL CHECK (side IN ('source','target')),
  PRIMARY KEY (edge_id, claim_id, side)
);

CREATE TABLE gaps (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  concept_a uuid NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
  concept_b uuid NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
  searches jsonb NOT NULL DEFAULT '[]',  -- queries and sources searched
  found_links jsonb NOT NULL DEFAULT '[]',
  note text,                              -- "no studies found in the searches made"
  status text NOT NULL DEFAULT 'open',    -- open | adopted_as_problem | dismissed
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE sections (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  parent_id uuid REFERENCES sections(id) ON DELETE CASCADE,
  title text NOT NULL,
  position int NOT NULL DEFAULT 0,
  content jsonb,                        -- editor document (Tiptap JSON)
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE section_concepts (
  section_id uuid NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
  concept_id uuid NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
  PRIMARY KEY (section_id, concept_id)
);

CREATE TABLE progress_templates (
  key text PRIMARY KEY,                 -- e.g. 'tcc', 'pre_projeto_mestrado'
  version int NOT NULL,
  definition jsonb NOT NULL             -- nodes, phases, prerequisites, gate rubric
);

CREATE TABLE progress_nodes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  template_key text NOT NULL REFERENCES progress_templates(key),
  node_key text NOT NULL,
  status node_status NOT NULL DEFAULT 'locked',
  queued boolean NOT NULL DEFAULT false,  -- research queue
  skipped_reason text,
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (project_id, node_key)
);

CREATE TABLE gate_attempts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  progress_node_id uuid NOT NULL REFERENCES progress_nodes(id) ON DELETE CASCADE,
  transcript jsonb NOT NULL,
  rubric_scores jsonb,
  outcome text NOT NULL,                -- liberar | revisar | pular
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ai_usage_log (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  action text NOT NULL,                 -- extract | relate | gate | rephrase | feedback ...
  target_ref text,                      -- id of affected object (no document content here)
  model text,
  prompt_version text,
  accepted boolean,                     -- did the user accept the result?
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE advisor_members (
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  advisor_email text NOT NULL,
  can_comment boolean NOT NULL DEFAULT true,
  invited_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (project_id, advisor_email)
);

CREATE TABLE advisor_reports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  period_start date,
  period_end date,
  payload jsonb NOT NULL,               -- nodes done, decisions, edges, AI usage, pending
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE section_comments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  section_id uuid NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
  author_email text NOT NULL,
  author_name text,
  content text NOT NULL,
  resolved boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Migration 004: restore points for sections and advisor feedback on progress-tree nodes.
CREATE TABLE section_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  section_id uuid NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
  content_snapshot jsonb NOT NULL,
  word_count int NOT NULL DEFAULT 0,
  created_by text,                     -- NULL = the student's own edits; 'ai' = AI-assisted write; 'restore'
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX section_versions_idx ON section_versions (section_id, created_at DESC);

CREATE TABLE node_feedback (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  node_key text NOT NULL,
  advisor_email text NOT NULL,
  advisor_name text,
  content text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX node_feedback_idx ON node_feedback (project_id, node_key, created_at);

-- Migration 005: passage index for whole-library search (embeddings as real[]; see migrations/005 note).
CREATE TABLE chunks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  chunk_no int NOT NULL,
  page_no int NOT NULL,                -- 1-based; a chunk never crosses a page
  text text NOT NULL,
  search_text text NOT NULL,           -- folded (lowercase, no accents) copy used for keyword search
  tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', search_text)) STORED,
  embedding real[],                    -- unit-length vector, NULL until embedded
  embedding_model text,                -- vectors from different models are never compared
  UNIQUE (document_id, chunk_no)
);
CREATE INDEX chunks_tsv_idx ON chunks USING gin (tsv);
CREATE INDEX chunks_project_idx ON chunks (project_id);

-- Migration 006: provenance ledger. Replaces the style-based "AI probability" with a record of what the assistant inserted
-- and what the editor saw pasted. Texts are kept so the current section text can be matched against them.
CREATE TABLE provenance_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  section_id uuid NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
  kind text NOT NULL CHECK (kind IN ('ai_draft','ai_coauthor','ai_polish','ai_paraphrase','paraphrase_dismissed','paste','legacy_counters')),
  source text NOT NULL DEFAULT 'server', -- server (the API produced it) | client (the editor reported it)
  words int NOT NULL DEFAULT 0,
  text text,                             -- NULL only for legacy_counters
  meta jsonb NOT NULL DEFAULT '{}',      -- model, mode, intensity; ai_words/student_words; legacy counters
  declared text CHECK (declared IS NULL OR declared = 'own_text'), -- the author's statement about a paste
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX provenance_section_idx ON provenance_events (section_id, created_at);
CREATE INDEX provenance_project_idx ON provenance_events (project_id);

-- Background jobs (migration 003): persistent queue for the document pipeline.
CREATE TABLE jobs (
  id bigserial PRIMARY KEY,
  document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  stage text NOT NULL,                 -- parse | extract
  status text NOT NULL DEFAULT 'queued', -- queued | running | done | dead
  attempts int NOT NULL DEFAULT 0,
  max_attempts int NOT NULL DEFAULT 3,
  run_after timestamptz NOT NULL DEFAULT now(),
  locked_by text,
  locked_until timestamptz,            -- lease: a crashed worker's job becomes claimable again after this
  last_error text,                     -- exception type only, never document text
  created_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz
);
CREATE UNIQUE INDEX jobs_active_uniq ON jobs (document_id, stage) WHERE status IN ('queued', 'running');
CREATE INDEX jobs_poll_idx ON jobs (run_after) WHERE status = 'queued';

-- Row Level Security: enable on every table with project_id and restrict to owner/advisor.
-- 007: local error log (replaces an external error tracker). Rows older than ERROR_RETENTION_DAYS are purged.
CREATE TABLE IF NOT EXISTS error_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source text NOT NULL DEFAULT 'api',   -- api | worker
  error_type text NOT NULL,
  message text NOT NULL,
  stack text,
  route text,
  request_id text,
  user_id text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS error_events_created_idx ON error_events (created_at DESC);

-- Migration 008: student beta feedback (T6.5). Tracks pilot satisfaction, socratic gate rating, evidence trust, relief and pricing preference.
CREATE TABLE IF NOT EXISTS beta_feedback (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  project_id uuid REFERENCES projects(id) ON DELETE SET NULL,
  overall_rating int NOT NULL CHECK (overall_rating BETWEEN 1 AND 5),
  socratic_gate_helpful int NOT NULL CHECK (socratic_gate_helpful BETWEEN 1 AND 5),
  evidence_trust int NOT NULL CHECK (evidence_trust BETWEEN 1 AND 5),
  relief_level int NOT NULL CHECK (relief_level BETWEEN 1 AND 5),
  pricing_preference text NOT NULL,
  brand_impression text NOT NULL,
  comments text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_beta_feedback_user ON beta_feedback(user_id);

-- Migration 009: academic defense simulator (T7.2). Tracks interactive defense committee simulation sessions, turns and verdicts.
CREATE TABLE IF NOT EXISTS banca_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  examiner_profile text NOT NULL CHECK (examiner_profile IN ('estrito', 'construtivo')),
  status text NOT NULL DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'completed')),
  turns jsonb NOT NULL DEFAULT '[]',
  final_report jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_banca_sessions_project ON banca_sessions(project_id, created_at DESC);

