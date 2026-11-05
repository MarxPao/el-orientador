-- 005: passage index for whole-library search, and AI summaries per document.
-- Embeddings are stored as real[] and compared in the application (project-scoped scan), so this works on any
-- Postgres. If a library grows past ~50k chunks per project, move `embedding` to pgvector + HNSW.
CREATE TABLE IF NOT EXISTS chunks (
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
CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS chunks_project_idx ON chunks (project_id);

ALTER TABLE documents ADD COLUMN IF NOT EXISTS summary jsonb;  -- {overview, sections[{page_start,page_end,summary}], model, ai_generated}
