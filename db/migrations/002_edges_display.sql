-- Map (T2.1): hide edges whose second verification did not fully imply the relation.
ALTER TABLE edges ADD COLUMN IF NOT EXISTS display_by_default boolean NOT NULL DEFAULT true;
