-- 008: the author can confirm that a paragraph is a rewrite of an AI draft (kind 'ai_paraphrase').
ALTER TABLE provenance_events DROP CONSTRAINT IF EXISTS provenance_events_kind_check;
ALTER TABLE provenance_events ADD CONSTRAINT provenance_events_kind_check
  CHECK (kind IN ('ai_draft','ai_coauthor','ai_polish','ai_paraphrase','paste','legacy_counters'));
