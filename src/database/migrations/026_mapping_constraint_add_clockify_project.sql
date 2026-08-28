-- Migration 026: Expand ps_project_mapping unique constraint to include clockify_project_name
-- Allows multiple rows per (ps_client, clockify_client) with different clockify project names
-- Old: UNIQUE(ps_client_name, COALESCE(ps_project_name, ''), clockify_client_name)
-- New: UNIQUE(ps_client_name, COALESCE(ps_project_name, ''), clockify_client_name, COALESCE(clockify_project_name, ''))

DROP INDEX IF EXISTS idx_ps_mapping_unique;

-- Deduplicate any rows that would violate the new constraint (keep most recent)
DELETE FROM ps_project_mapping a USING ps_project_mapping b
WHERE a.id < b.id
  AND a.ps_client_name = b.ps_client_name
  AND COALESCE(a.ps_project_name, '') = COALESCE(b.ps_project_name, '')
  AND a.clockify_client_name = b.clockify_client_name
  AND COALESCE(a.clockify_project_name, '') = COALESCE(b.clockify_project_name, '');

CREATE UNIQUE INDEX idx_ps_mapping_unique
  ON ps_project_mapping (
    ps_client_name,
    COALESCE(ps_project_name, ''),
    clockify_client_name,
    COALESCE(clockify_project_name, '')
  );
