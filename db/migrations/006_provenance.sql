-- 006: provenance ledger. Replaces the style-based "AI probability" with a record of what the assistant inserted
-- and what the editor saw pasted. Texts are kept so the current section text can be matched against them.
CREATE TABLE IF NOT EXISTS provenance_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  section_id uuid NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
  kind text NOT NULL CHECK (kind IN ('ai_draft','ai_coauthor','ai_polish','paste','legacy_counters')),
  source text NOT NULL DEFAULT 'server', -- server (the API produced it) | client (the editor reported it)
  words int NOT NULL DEFAULT 0,
  text text,                             -- NULL only for legacy_counters
  meta jsonb NOT NULL DEFAULT '{}',      -- model, mode, intensity; ai_words/student_words; legacy counters
  declared text CHECK (declared IS NULL OR declared = 'own_text'), -- the author's statement about a paste
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS provenance_section_idx ON provenance_events (section_id, created_at);
CREATE INDEX IF NOT EXISTS provenance_project_idx ON provenance_events (project_id);
