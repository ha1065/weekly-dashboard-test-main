-- Migration 028: Backfill category on existing ps_project_mapping rows
-- Infers category from ps_project_status issue_type:
--   category='MC'  when the client exists ONLY as Managed Services in ps_project_status
--   category='PS'  when the client exists ONLY as non-Managed Services
--   NULL stays NULL when the client exists in both (ambiguous — user can re-save from correct tab)

UPDATE ps_project_mapping m
SET category = 'MC'
WHERE m.category IS NULL
  AND EXISTS (
      SELECT 1 FROM ps_project_status p
      WHERE LOWER(p.client_name) = LOWER(m.ps_client_name)
        AND p.issue_type = 'Managed Services'
  )
  AND NOT EXISTS (
      SELECT 1 FROM ps_project_status p
      WHERE LOWER(p.client_name) = LOWER(m.ps_client_name)
        AND (p.issue_type IS NULL OR p.issue_type != 'Managed Services')
  );

UPDATE ps_project_mapping m
SET category = 'PS'
WHERE m.category IS NULL
  AND EXISTS (
      SELECT 1 FROM ps_project_status p
      WHERE LOWER(p.client_name) = LOWER(m.ps_client_name)
        AND (p.issue_type IS NULL OR p.issue_type != 'Managed Services')
  )
  AND NOT EXISTS (
      SELECT 1 FROM ps_project_status p
      WHERE LOWER(p.client_name) = LOWER(m.ps_client_name)
        AND p.issue_type = 'Managed Services'
  );
