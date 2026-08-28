-- Migration 032: Deduplicate ps_project_mapping
--
-- Problem: auto_populate_mappings created one row per (ps_client_name, ps_project_name)
-- pair. Since clockify_project_name is always NULL on auto-created rows, every row
-- with the same clockify_client_name matches ALL Clockify time entries for that client,
-- multiplying hours N times in views and reports.
--
-- Fix: for each clockify_client_name keep only the best single row:
--   1. A manually-created row (ps_project_name IS NULL) if one exists, OR
--   2. The lowest-id auto-created row otherwise.
-- All other rows for the same clockify_client_name are deactivated.

-- Step 1: identify the "keeper" row for each clockify_client_name
WITH keepers AS (
    SELECT DISTINCT ON (LOWER(clockify_client_name))
        id
    FROM ps_project_mapping
    WHERE is_active = TRUE
    ORDER BY
        LOWER(clockify_client_name),
        (ps_project_name IS NOT NULL),  -- prefer NULL ps_project_name (client-level)
        id
)

-- Step 2: deactivate every OTHER active row for the same clockify client
UPDATE ps_project_mapping
SET    is_active = FALSE
WHERE  is_active = TRUE
  AND  id NOT IN (SELECT id FROM keepers)
  AND  clockify_client_name IN (
           SELECT clockify_client_name FROM ps_project_mapping WHERE is_active = TRUE
       );
