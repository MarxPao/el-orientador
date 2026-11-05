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
