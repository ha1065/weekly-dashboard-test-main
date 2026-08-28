-- Migration 033: Normalize Happy Numbers client names in ps_project_status
--
-- The Jira issue summary parser split old summaries incorrectly, creating
-- three different client_name variants for the same customer:
--   'Happy'                  (from summary "Happy Numbers" — pattern 4 split)
--   'HappyNumbers MAP'       (from "HappyNumbers MAP - Assessment")
--   'Happy Numbers-Migration' (from "Happy Numbers-Migration - Assess")
--
-- The canonical Clockify client name is 'Happy Numbers'.

-- Step 1: normalize ps_project_status client names
UPDATE ps_project_status
SET    client_name = 'Happy Numbers'
WHERE  client_name IN ('Happy', 'HappyNumbers MAP', 'Happy Numbers-Migration');

-- Step 2: update the mapping row to use the canonical client name
UPDATE ps_project_mapping
SET    ps_client_name = 'Happy Numbers',
       ps_project_name = NULL
WHERE  ps_client_name = 'Happy Numbers-Migration'
  AND  clockify_client_name = 'Happy Numbers';

-- Step 3: remove any leftover duplicate mapping rows for Happy Numbers
-- (keep only the one we just updated — lowest id)
WITH keeper AS (
    SELECT MIN(id) AS keep_id
    FROM   ps_project_mapping
    WHERE  LOWER(ps_client_name) = 'happy numbers'
      AND  is_active = TRUE
)
UPDATE ps_project_mapping
SET    is_active = FALSE
WHERE  LOWER(ps_client_name) = 'happy numbers'
  AND  is_active = TRUE
  AND  id NOT IN (SELECT keep_id FROM keeper);
