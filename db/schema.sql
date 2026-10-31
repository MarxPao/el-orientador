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
  metadata_source text,                -- crossref | openalex | semantic_scholar | manual
  retracted boolean NOT NULL DEFAULT false,
  storage_path text,                   -- encrypted object storage key
  analysis analysis_depth NOT NULL DEFAULT 'full_text',
  parse_quality real,                  -- 0..1
  status text NOT NULL DEFAULT 'pending', -- pending | parsed | extracted | failed
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (project_id, doi)
);

CREATE TABLE document_pages (
  document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  page_no int NOT NULL,                -- 1-based
  text text NOT NULL,
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

-- Row Level Security: enable on every table with project_id and restrict to owner/advisor.
