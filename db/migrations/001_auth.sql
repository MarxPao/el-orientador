-- Auth: password hash for email+password login (T1.1).
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash text;
