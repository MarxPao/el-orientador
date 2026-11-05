-- 004: restore points for sections and advisor feedback on progress-tree nodes.
CREATE TABLE IF NOT EXISTS section_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  section_id uuid NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
  content_snapshot jsonb NOT NULL,
  word_count int NOT NULL DEFAULT 0,
  created_by text,                     -- NULL = the student's own edits; 'ai' = AI-assisted write; 'restore'
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS section_versions_idx ON section_versions (section_id, created_at DESC);

CREATE TABLE IF NOT EXISTS node_feedback (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  node_key text NOT NULL,
  advisor_email text NOT NULL,
  advisor_name text,
  content text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS node_feedback_idx ON node_feedback (project_id, node_key, created_at);
