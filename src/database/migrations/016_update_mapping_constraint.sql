-- Migration 016: Update ps_project_mapping unique constraint
-- Allow mapping multiple PS projects under the same client to the same Clockify client
-- Old constraint: UNIQUE(ps_client_name, clockify_client_name)
-- New constraint: UNIQUE(ps_client_name, COALESCE(ps_project_name, ''), clockify_client_name)

ALTER TABLE ps_project_mapping
  DROP CONSTRAINT IF EXISTS ps_project_mapping_ps_client_name_clockify_client_name_key;

-- Deduplicate before adding new constraint (keep the most recent)
DELETE FROM ps_project_mapping a USING ps_project_mapping b
WHERE a.id < b.id
  AND a.ps_client_name = b.ps_client_name
  AND COALESCE(a.ps_project_name, '') = COALESCE(b.ps_project_name, '')
  AND a.clockify_client_name = b.clockify_client_name;

CREATE UNIQUE INDEX idx_ps_mapping_unique
  ON ps_project_mapping (ps_client_name, COALESCE(ps_project_name, ''), clockify_client_name);
