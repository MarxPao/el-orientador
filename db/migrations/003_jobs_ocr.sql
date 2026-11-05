-- Persistent job queue, staged pipeline progress and OCR page source (Phase 1). Idempotent.
ALTER TABLE documents ADD COLUMN IF NOT EXISTS stage text;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS progress jsonb;
ALTER TABLE document_pages ADD COLUMN IF NOT EXISTS source text NOT NULL DEFAULT 'native';

CREATE TABLE IF NOT EXISTS jobs (
  id bigserial PRIMARY KEY,
  document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  stage text NOT NULL,
  status text NOT NULL DEFAULT 'queued',
  attempts int NOT NULL DEFAULT 0,
  max_attempts int NOT NULL DEFAULT 3,
  run_after timestamptz NOT NULL DEFAULT now(),
  locked_by text,
  locked_until timestamptz,
  last_error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz
);
CREATE UNIQUE INDEX IF NOT EXISTS jobs_active_uniq ON jobs (document_id, stage) WHERE status IN ('queued', 'running');
CREATE INDEX IF NOT EXISTS jobs_poll_idx ON jobs (run_after) WHERE status = 'queued';
