-- Migration 029: Add category column to ps_project_status
-- Stores explicit PS/MC classification set during ingestion,
-- replacing inline issue_type filtering throughout the codebase.
ALTER TABLE ps_project_status
  ADD COLUMN IF NOT EXISTS category VARCHAR(10);

-- Backfill existing rows
UPDATE ps_project_status
   SET category = CASE
         WHEN issue_type = 'Managed Services' THEN 'MC'
         ELSE 'PS'
       END
 WHERE category IS NULL;
