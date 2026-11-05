-- 009: the author can dismiss a paraphrase suggestion ("this paragraph is not a rewrite of an AI draft").
-- The dismissal is recorded (kind 'paraphrase_dismissed') so the same paragraph is not suggested again and the
-- export can tell reviewed suggestions from unreviewed ones. It never counts in the Authorship Prism.
ALTER TABLE provenance_events DROP CONSTRAINT IF EXISTS provenance_events_kind_check;
ALTER TABLE provenance_events ADD CONSTRAINT provenance_events_kind_check
  CHECK (kind IN ('ai_draft','ai_coauthor','ai_polish','ai_paraphrase','paraphrase_dismissed','paste','legacy_counters'));
